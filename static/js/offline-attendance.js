(function () {
  "use strict";

  var config = window.OfflineAttendanceConfig || {};
  var databasePromise = null;
  var queue = [];
  var attendanceData = {};

  var DATABASE_NAME = "edumanage-offline-v1";
  var STORE_NAME = "attendance_drafts";
  var tenantKey = String(config.tenantKey || window.location.hostname || "tenant");
  var userKey = config.userId
    ? "user-" + String(config.userId)
    : "session-" + stableHash(String(config.csrfToken || "anonymous"));
  var namespace = tenantKey + ":" + userKey;
  var scopeKey = String(config.scopeKey || "default");
  var maxAgeMilliseconds = Number(config.maxAgeHours || 48) * 60 * 60 * 1000;

  function stableHash(value) {
    var hash = 2166136261;
    for (var index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(36);
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value || {}));
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function draftId() {
    return [
      "attendance",
      namespace,
      config.offeringId,
      config.date,
      scopeKey,
    ].join(":");
  }

  function openDatabase() {
    if (databasePromise) {
      return databasePromise;
    }

    databasePromise = new Promise(function (resolve, reject) {
      if (!("indexedDB" in window)) {
        reject(new Error("Offline storage is not supported by this browser."));
        return;
      }

      var request = indexedDB.open(DATABASE_NAME, 1);

      request.onupgradeneeded = function () {
        if (!request.result.objectStoreNames.contains(STORE_NAME)) {
          var store = request.result.createObjectStore(STORE_NAME, {
            keyPath: "id",
          });
          store.createIndex("namespace", "namespace", { unique: false });
        }
      };

      request.onsuccess = function () {
        resolve(request.result);
      };

      request.onerror = function () {
        reject(request.error || new Error("Unable to open offline storage."));
      };
    });

    return databasePromise;
  }

  function runTransaction(mode, operation) {
    return openDatabase().then(function (database) {
      return new Promise(function (resolve, reject) {
        var transaction = database.transaction(STORE_NAME, mode);
        var store = transaction.objectStore(STORE_NAME);

        operation(store, transaction);

        transaction.oncomplete = function () {
          resolve();
        };

        transaction.onerror = function () {
          reject(transaction.error || new Error("Offline storage operation failed."));
        };

        transaction.onabort = function () {
          reject(transaction.error || new Error("Offline storage operation was cancelled."));
        };
      });
    });
  }

  function loadQueue() {
    return openDatabase().then(function (database) {
      return new Promise(function (resolve, reject) {
        var transaction = database.transaction(STORE_NAME, "readwrite");
        var store = transaction.objectStore(STORE_NAME);
        var request = store.index("namespace").getAll(namespace);

        request.onsuccess = function () {
          var now = Date.now();
          var activeDrafts = [];

          (request.result || []).forEach(function (draft) {
            var updatedAt = Date.parse(draft.updated_at || draft.created_at || "");
            var age = now - updatedAt;

            if (Number.isFinite(age) && age <= maxAgeMilliseconds) {
              activeDrafts.push(draft);
            } else {
              store.delete(draft.id);
            }
          });

          resolve(activeDrafts);
        };

        request.onerror = function () {
          reject(request.error || new Error("Unable to load offline attendance drafts."));
        };
      });
    });
  }

  function putDraft(draft) {
    return runTransaction("readwrite", function (store) {
      store.put(draft);
    });
  }

  function deleteDraft(id) {
    return runTransaction("readwrite", function (store) {
      store.delete(id);
    });
  }

  function deleteNamespaceDrafts() {
    return openDatabase().then(function (database) {
      return new Promise(function (resolve, reject) {
        var transaction = database.transaction(STORE_NAME, "readwrite");
        var store = transaction.objectStore(STORE_NAME);
        var request = store.index("namespace").openCursor(IDBKeyRange.only(namespace));

        request.onsuccess = function () {
          var cursor = request.result;
          if (!cursor) {
            return;
          }
          cursor.delete();
          cursor.continue();
        };

        request.onerror = function () {
          reject(request.error || new Error("Unable to clear offline attendance data."));
        };

        transaction.oncomplete = function () {
          resolve();
        };

        transaction.onerror = function () {
          reject(transaction.error || new Error("Unable to clear offline attendance data."));
        };
      });
    });
  }

  function notes() {
    return attendanceData.__notes || {};
  }

  function cleanAttendanceData() {
    var clean = {};

    Object.keys(attendanceData).forEach(function (studentId) {
      if (studentId !== "__notes") {
        clean[studentId] = attendanceData[studentId];
      }
    });

    return clean;
  }

  function collectFormState() {
    var form = document.querySelector("[data-offline-attendance-form]");
    var attendance = {};
    var noteValues = {};

    if (!form) {
      return;
    }

    form.querySelectorAll('input[name="student_ids"]').forEach(function (input) {
      var studentId = input.value;
      var statusInput = form.querySelector('[name="status_' + studentId + '"]');
      var noteInput = form.querySelector('[name="note_' + studentId + '"]');

      attendance[studentId] = statusInput ? statusInput.value : "PRESENT";
      noteValues[studentId] = noteInput ? noteInput.value : "";
    });

    attendanceData = attendance;
    attendanceData.__notes = noteValues;
    updateMarkedCount();
  }

  function buildPayload() {
    if (config.mode === "form") {
      collectFormState();
    }

    var timestamp = nowIso();
    var id = draftId();

    return {
      id: id,
      idempotency_key: id,
      namespace: namespace,
      tenant_key: tenantKey,
      user_id: config.userId || null,
      offering_id: config.offeringId,
      date: config.date,
      attendance: cleanAttendanceData(),
      notes: clone(notes()),
      created_at: timestamp,
      updated_at: timestamp,
    };
  }

  function enqueue(draft) {
    var existingIndex = queue.findIndex(function (item) {
      return item.id === draft.id;
    });

    if (existingIndex >= 0) {
      draft.created_at = queue[existingIndex].created_at || draft.created_at;
      queue[existingIndex] = draft;
    } else {
      queue.push(draft);
    }

    putDraft(draft).catch(function (error) {
      showToast("Offline save failed", error.message, "error");
    });

    renderQueueStatus();
  }

  function removeQueuedDraft(id) {
    queue = queue.filter(function (item) {
      return item.id !== id;
    });

    deleteDraft(id).catch(function () {
      // The server save already succeeded. A stale draft will expire automatically.
    });

    renderQueueStatus();
  }

  function postPayload(payload) {
    return fetch(config.saveUrl, {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": config.csrfToken || "",
        "X-Idempotency-Key": payload.idempotency_key,
      },
      body: JSON.stringify(payload),
    }).then(function (response) {
      return response
        .json()
        .catch(function () {
          return {};
        })
        .then(function (data) {
          if (!response.ok || !data.success) {
            throw new Error(data.error || "Failed to save attendance.");
          }
          return data;
        });
    });
  }

  function showToast(title, message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(title, message, type || "info");
      return;
    }

    window.alert(title + ": " + message);
  }

  function currentDraft() {
    var id = draftId();
    return (
      queue.find(function (item) {
        return item.id === id;
      }) || null
    );
  }

  function renderQueueStatus(errorMessage) {
    var panel = document.querySelector("[data-offline-attendance-status]");

    if (!panel) {
      return;
    }

    var online = navigator.onLine;
    var count = queue.length;
    var label = panel.querySelector("[data-offline-attendance-label]");
    var detail = panel.querySelector("[data-offline-attendance-detail]");
    var syncButton = panel.querySelector("[data-offline-attendance-sync]");

    panel.classList.toggle("is-offline", !online);
    panel.classList.toggle("has-pending", count > 0);

    if (syncButton) {
      syncButton.disabled = !online || count === 0;
    }

    if (label) {
      label.textContent = !online
        ? "Offline attendance mode"
        : count
          ? "Attendance waiting to sync"
          : "Attendance sync ready";
    }

    if (!detail) {
      return;
    }

    if (errorMessage) {
      detail.textContent = errorMessage;
    } else if (!online && currentDraft()) {
      detail.textContent =
        "This class is stored securely in browser database storage for this signed-in account and will sync when internet returns.";
    } else if (!online) {
      detail.textContent =
        "Mark attendance normally. The draft expires automatically and is cleared when you sign out.";
    } else if (count) {
      detail.textContent =
        count + " attendance update" + (count === 1 ? "" : "s") + " pending sync.";
    } else {
      detail.textContent = "Online. Saves go directly to Django.";
    }
  }

  function syncQueuedAttendance(showNotifications) {
    if (!navigator.onLine) {
      renderQueueStatus();
      return Promise.resolve({ synced: 0, pending: queue.length });
    }

    var synced = 0;
    var chain = Promise.resolve();

    queue.slice().forEach(function (draft) {
      chain = chain.then(function () {
        return postPayload(draft).then(function () {
          removeQueuedDraft(draft.id);
          synced += 1;
        });
      });
    });

    return chain
      .then(function () {
        renderQueueStatus();

        if (synced && showNotifications) {
          showToast(
            "Attendance synced",
            synced + " offline save" + (synced === 1 ? "" : "s") + " synced.",
            "success"
          );
        }

        return { synced: synced, pending: queue.length };
      })
      .catch(function (error) {
        renderQueueStatus(error.message);

        if (showNotifications) {
          showToast("Sync paused", error.message, "warning");
        }

        return { synced: synced, pending: queue.length, error: error };
      });
  }

  function updateMarkedCount() {
    var target = document.getElementById("marked-count");
    if (target) {
      target.textContent = Object.keys(cleanAttendanceData()).length;
    }
  }

  function setButtonState(button, status) {
    var row = button.closest("[data-student-id]");

    if (!row) {
      return;
    }

    row.querySelectorAll(".status-btn").forEach(function (candidate) {
      var candidateStatus = candidate.getAttribute("data-status");

      candidate.classList.remove(
        "bg-green-600",
        "bg-red-600",
        "bg-yellow-600",
        "bg-blue-600",
        "text-white",
        "border-green-600",
        "border-red-600",
        "border-yellow-600",
        "border-blue-600"
      );
      candidate.classList.add("bg-white", "text-slate-700", "border-slate-200");

      if (candidateStatus !== status) {
        return;
      }

      candidate.classList.remove("bg-white", "text-slate-700", "border-slate-200");

      var color = {
        PRESENT: "green",
        ABSENT: "red",
        LATE: "yellow",
        EXCUSED: "blue",
      }[status];

      if (color) {
        candidate.classList.add(
          "bg-" + color + "-600",
          "text-white",
          "border-" + color + "-600"
        );
      }
    });
  }

  function hydrateFromCurrentDraft() {
    var draft = currentDraft();

    if (!draft) {
      return;
    }

    attendanceData = clone(draft.attendance);
    attendanceData.__notes = clone(draft.notes);

    var form = document.querySelector("[data-offline-attendance-form]");

    if (form) {
      Object.keys(cleanAttendanceData()).forEach(function (studentId) {
        var statusInput = form.querySelector('[name="status_' + studentId + '"]');
        var noteInput = form.querySelector('[name="note_' + studentId + '"]');

        if (statusInput) {
          statusInput.value = attendanceData[studentId];
        }

        if (noteInput) {
          noteInput.value = notes()[studentId] || "";
        }
      });
      return;
    }

    Object.keys(cleanAttendanceData()).forEach(function (studentId) {
      var row = document.querySelector('[data-student-id="' + studentId + '"]');
      var button = row
        ? row.querySelector('[data-status="' + attendanceData[studentId] + '"]')
        : null;

      if (button) {
        setButtonState(button, attendanceData[studentId]);
      }
    });
  }

  window.markStudent = function (studentId, status, button) {
    attendanceData[studentId] = status;

    if (button) {
      setButtonState(button, status);
    }

    updateMarkedCount();

    if (!navigator.onLine) {
      enqueue(buildPayload());
    }
  };

  window.markAllPresent = function () {
    document.querySelectorAll("[data-student-id]").forEach(function (row) {
      var studentId = row.getAttribute("data-student-id");
      var presentButton = row.querySelector('[data-status="PRESENT"]');
      window.markStudent(parseInt(studentId, 10), "PRESENT", presentButton);
    });
  };

  window.saveAttendance = function () {
    var payload = buildPayload();

    if (!navigator.onLine) {
      enqueue(payload);
      showToast(
        "Saved offline",
        "Attendance will sync when internet returns.",
        "warning"
      );
      return;
    }

    postPayload(payload)
      .then(function (data) {
        removeQueuedDraft(payload.id);
        showToast("Success", data.message || "Attendance saved.", "success");
      })
      .catch(function () {
        enqueue(payload);
        showToast(
          "Saved offline",
          "The connection dropped, so attendance was queued.",
          "warning"
        );
      });
  };

  window.syncOfflineAttendance = function () {
    return syncQueuedAttendance(true);
  };

  window.clearOfflineAttendanceData = function () {
    queue = [];
    renderQueueStatus();
    return deleteNamespaceDrafts().catch(function () {
      // Best-effort privacy cleanup; expired drafts are purged during the next load.
    });
  };

  function initialise() {
    try {
      localStorage.removeItem("edumanage_offline_attendance_queue_v1");
    } catch (error) {
      // localStorage may be unavailable; IndexedDB remains the only active store.
    }

    attendanceData = clone(config.initialAttendance);
    attendanceData.__notes = clone(config.initialNotes);

    if (config.mode === "form") {
      collectFormState();
    }

    window.addEventListener("online", function () {
      renderQueueStatus();
      syncQueuedAttendance(true);
    });
    window.addEventListener("offline", renderQueueStatus);

    document.addEventListener("click", function (event) {
      if (event.target.closest("[data-offline-attendance-sync]")) {
        syncQueuedAttendance(true);
      }
    });

    var form = document.querySelector("[data-offline-attendance-form]");
    if (form) {
      form.addEventListener("change", collectFormState);
      form.addEventListener("input", collectFormState);
      form.addEventListener("submit", function (event) {
        collectFormState();

        if (!navigator.onLine) {
          event.preventDefault();
          enqueue(buildPayload());
          showToast(
            "Saved offline",
            "Attendance will sync when internet returns.",
            "warning"
          );
        }
      });
    }

    loadQueue()
      .then(function (drafts) {
        queue = drafts;
        hydrateFromCurrentDraft();
        updateMarkedCount();
        renderQueueStatus();

        if (navigator.onLine) {
          syncQueuedAttendance(false);
        }
      })
      .catch(function (error) {
        renderQueueStatus(error.message);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialise, { once: true });
  } else {
    initialise();
  }
})();
