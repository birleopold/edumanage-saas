(function () {
  "use strict";

  var QUEUE_KEY = "edumanage_offline_attendance_queue_v1";
  var config = window.OfflineAttendanceConfig || {};
  var attendanceData = {};

  function clone(value) {
    return JSON.parse(JSON.stringify(value || {}));
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function queueId(payload) {
    return "attendance:" + payload.offering_id + ":" + payload.date;
  }

  function loadQueue() {
    try {
      var raw = localStorage.getItem(QUEUE_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function saveQueue(queue) {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
    renderQueueStatus();
  }

  function queuedForCurrentPage() {
    if (!config.offeringId || !config.date) return null;
    var id = queueId({ offering_id: config.offeringId, date: config.date });
    return loadQueue().find(function (item) { return item.id === id; }) || null;
  }

  function buildPayload() {
    if (config.mode === "form") collectFormState();
    return {
      id: queueId({ offering_id: config.offeringId, date: config.date }),
      offering_id: config.offeringId,
      date: config.date,
      attendance: cleanAttendanceData(),
      notes: clone(noteData()),
      created_at: nowIso(),
      updated_at: nowIso()
    };
  }

  function noteData() {
    return attendanceData.__notes || {};
  }

  function setNoteData(notes) {
    attendanceData.__notes = notes || {};
  }

  function cleanAttendanceData() {
    var clean = {};
    Object.keys(attendanceData || {}).forEach(function (studentId) {
      if (studentId !== "__notes") clean[studentId] = attendanceData[studentId];
    });
    return clean;
  }

  function queuePayload(payload) {
    var queue = loadQueue();
    var existingIndex = queue.findIndex(function (item) { return item.id === payload.id; });
    if (existingIndex >= 0) {
      payload.created_at = queue[existingIndex].created_at || payload.created_at;
      queue[existingIndex] = payload;
    } else {
      queue.push(payload);
    }
    saveQueue(queue);
  }

  function removeQueued(id) {
    saveQueue(loadQueue().filter(function (item) { return item.id !== id; }));
  }

  function pendingCount() {
    return loadQueue().length;
  }

  function postPayload(payload) {
    return fetch(config.saveUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": config.csrfToken || ""
      },
      body: JSON.stringify(payload)
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok || !data.success) throw new Error(data.error || "Failed to save attendance.");
        return data;
      });
    });
  }

  function showToast(title, message, type) {
    if (typeof window.showToast === "function") window.showToast(title, message, type || "info");
    else alert((title || "Notice") + ": " + (message || ""));
  }

  function renderQueueStatus(errorMessage) {
    var panel = document.querySelector("[data-offline-attendance-status]");
    if (!panel) return;
    var count = pendingCount();
    var current = queuedForCurrentPage();
    var online = navigator.onLine;
    var label = panel.querySelector("[data-offline-attendance-label]");
    var detail = panel.querySelector("[data-offline-attendance-detail]");
    var syncButton = panel.querySelector("[data-offline-attendance-sync]");

    panel.classList.toggle("is-offline", !online);
    panel.classList.toggle("has-pending", count > 0);
    if (syncButton) syncButton.disabled = !online || count === 0;

    if (label) {
      label.textContent = !online ? "Offline attendance mode" : count ? "Attendance waiting to sync" : "Attendance sync ready";
    }
    if (!detail) return;
    if (errorMessage) detail.textContent = errorMessage;
    else if (!online && current) detail.textContent = "This class/date is saved on this device. It will sync automatically when internet returns.";
    else if (!online) detail.textContent = "Mark attendance as usual. Saving keeps it on this device until internet returns.";
    else if (count) detail.textContent = count + " saved attendance update" + (count === 1 ? "" : "s") + " pending sync.";
    else detail.textContent = "Online. Saves go directly to Django.";
  }

  function syncQueuedAttendance(options) {
    options = options || {};
    if (!navigator.onLine) {
      renderQueueStatus();
      return Promise.resolve({ synced: 0, pending: pendingCount() });
    }
    var queue = loadQueue();
    var synced = 0;
    var chain = Promise.resolve();
    queue.forEach(function (payload) {
      chain = chain.then(function () {
        return postPayload(payload).then(function () {
          removeQueued(payload.id);
          synced += 1;
        });
      });
    });
    return chain.then(function () {
      renderQueueStatus();
      if (synced && options.toast !== false) {
        showToast("Attendance synced", synced + " offline attendance save" + (synced === 1 ? "" : "s") + " synced.", "success");
      }
      return { synced: synced, pending: pendingCount() };
    }).catch(function (error) {
      renderQueueStatus(error.message);
      if (options.toast !== false) showToast("Sync paused", error.message || "Attendance will sync when the connection is stable.", "warning");
      return { synced: synced, pending: pendingCount(), error: error };
    });
  }

  function updateMarkedCount() {
    var target = document.getElementById("marked-count");
    if (target) target.textContent = Object.keys(cleanAttendanceData()).length;
  }

  function setButtonState(button, status) {
    var row = button.closest("[data-student-id]");
    if (!row) return;
    row.querySelectorAll(".status-btn").forEach(function (btn) {
      var btnStatus = btn.getAttribute("data-status");
      btn.classList.remove("bg-green-600", "bg-red-600", "bg-yellow-600", "bg-blue-600", "text-white", "border-green-600", "border-red-600", "border-yellow-600", "border-blue-600");
      btn.classList.add("bg-white", "text-slate-700", "border-slate-200");
      if (btnStatus === status) {
        btn.classList.remove("bg-white", "text-slate-700", "border-slate-200");
        if (status === "PRESENT") btn.classList.add("bg-green-600", "text-white", "border-green-600");
        if (status === "ABSENT") btn.classList.add("bg-red-600", "text-white", "border-red-600");
        if (status === "LATE") btn.classList.add("bg-yellow-600", "text-white", "border-yellow-600");
        if (status === "EXCUSED") btn.classList.add("bg-blue-600", "text-white", "border-blue-600");
      }
    });
  }

  function hydrateFromQueuedPayload() {
    var queued = queuedForCurrentPage();
    if (!queued || !queued.attendance) return;
    attendanceData = clone(queued.attendance);
    setNoteData(clone(queued.notes || {}));
    if (config.mode === "form") {
      hydrateFormState();
      return;
    }
    Object.keys(attendanceData).forEach(function (studentId) {
      var row = document.querySelector('[data-student-id="' + studentId + '"]');
      var button = row ? row.querySelector('[data-status="' + attendanceData[studentId] + '"]') : null;
      if (button) setButtonState(button, attendanceData[studentId]);
    });
  }

  function collectFormState() {
    var form = document.querySelector("[data-offline-attendance-form]");
    var attendance = {};
    var notes = {};
    if (!form) return;
    form.querySelectorAll('input[name="student_ids"]').forEach(function (input) {
      var studentId = input.value;
      var status = form.querySelector('[name="status_' + studentId + '"]');
      var note = form.querySelector('[name="note_' + studentId + '"]');
      attendance[studentId] = status ? status.value : "PRESENT";
      notes[studentId] = note ? note.value : "";
    });
    attendanceData = attendance;
    setNoteData(notes);
    updateMarkedCount();
  }

  function hydrateFormState() {
    var form = document.querySelector("[data-offline-attendance-form]");
    var notes = noteData();
    if (!form) return;
    Object.keys(attendanceData).forEach(function (studentId) {
      if (studentId === "__notes") return;
      var status = form.querySelector('[name="status_' + studentId + '"]');
      var note = form.querySelector('[name="note_' + studentId + '"]');
      if (status) status.value = attendanceData[studentId];
      if (note && Object.prototype.hasOwnProperty.call(notes, studentId)) note.value = notes[studentId] || "";
    });
  }

  window.markStudent = function (studentId, status, button) {
    attendanceData[studentId] = status;
    if (button) setButtonState(button, status);
    updateMarkedCount();
    if (!navigator.onLine) queuePayload(buildPayload());
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
      queuePayload(payload);
      showToast("Saved offline", "Attendance is stored on this device and will sync when internet returns.", "warning");
      renderQueueStatus();
      return;
    }
    postPayload(payload).then(function (data) {
      removeQueued(payload.id);
      showToast("Success", data.message || "Attendance saved.", "success");
      renderQueueStatus();
    }).catch(function () {
      queuePayload(payload);
      showToast("Saved offline", "The connection dropped, so attendance was queued for sync.", "warning");
      renderQueueStatus();
    });
  };

  window.syncOfflineAttendance = function () {
    return syncQueuedAttendance({ toast: true });
  };

  function init() {
    attendanceData = clone(config.initialAttendance || {});
    setNoteData(clone(config.initialNotes || {}));
    hydrateFromQueuedPayload();
    if (config.mode === "form") collectFormState();
    updateMarkedCount();
    renderQueueStatus();
    window.addEventListener("online", function () {
      renderQueueStatus();
      syncQueuedAttendance({ toast: true });
    });
    window.addEventListener("offline", renderQueueStatus);
    document.addEventListener("click", function (event) {
      if (event.target.closest("[data-offline-attendance-sync]")) syncQueuedAttendance({ toast: true });
    });
    var form = document.querySelector("[data-offline-attendance-form]");
    if (form) {
      form.addEventListener("change", collectFormState);
      form.addEventListener("input", collectFormState);
      form.addEventListener("submit", function (event) {
        collectFormState();
        if (!navigator.onLine) {
          event.preventDefault();
          queuePayload(buildPayload());
          showToast("Saved offline", "Attendance is stored on this device and will sync when internet returns.", "warning");
          renderQueueStatus();
        }
      });
    }
    if (navigator.onLine) syncQueuedAttendance({ toast: false });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
