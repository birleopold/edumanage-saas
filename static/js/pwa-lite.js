(function () {
  "use strict";

  var deferredInstallPrompt = null;
  var readiness = null;

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function csrfToken() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var rawData = window.atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
    return outputArray;
  }

  function createOfflineBanner() {
    if (document.querySelector(".edu-offline-banner")) return;
    var banner = document.createElement("div");
    banner.className = "edu-offline-banner";
    banner.setAttribute("role", "status");
    banner.innerHTML = '<i class="ph ph-wifi-slash" aria-hidden="true"></i><span>You are offline. Reconnect to load school records safely.</span>';
    document.body.appendChild(banner);
  }

  function updateOfflineBanner() {
    var banner = document.querySelector(".edu-offline-banner");
    if (!banner) return;
    banner.classList.toggle("is-visible", !navigator.onLine);
  }

  function createInstallPrompt() {
    if (document.querySelector(".edu-install-prompt")) return;
    var prompt = document.createElement("div");
    prompt.className = "edu-install-prompt";
    prompt.innerHTML = [
      '<div>',
      '<p class="edu-install-prompt__title">Install EduManage</p>',
      '<p class="edu-install-prompt__text">Add this school system to your phone and enable school alerts.</p>',
      '<span data-push-readiness></span>',
      '</div>',
      '<div class="edu-install-prompt__actions">',
      '<button type="button" data-pwa-install>Install</button>',
      '<button type="button" data-push-enable>Alerts</button>',
      '<button type="button" data-pwa-dismiss>Later</button>',
      '</div>'
    ].join("");
    document.body.appendChild(prompt);
  }

  function showInstallPrompt() {
    var prompt = document.querySelector(".edu-install-prompt");
    if (!prompt || localStorage.getItem("edumanage_install_dismissed") === "1") return;
    prompt.classList.add("is-visible");
  }

  function hideInstallPrompt() {
    var prompt = document.querySelector(".edu-install-prompt");
    if (prompt) prompt.classList.remove("is-visible");
  }

  function setupInstallPrompt() {
    window.addEventListener("beforeinstallprompt", function (event) {
      event.preventDefault();
      deferredInstallPrompt = event;
      showInstallPrompt();
    });

    document.addEventListener("click", function (event) {
      var installButton = event.target.closest("[data-pwa-install]");
      var dismissButton = event.target.closest("[data-pwa-dismiss]");
      var pushButton = event.target.closest("[data-push-enable]");
      if (dismissButton) {
        localStorage.setItem("edumanage_install_dismissed", "1");
        hideInstallPrompt();
      }
      if (pushButton) enablePushNotifications();
      if (!installButton) return;
      if (!deferredInstallPrompt) {
        alert("Use your browser menu and choose Add to Home Screen / Install app.");
        return;
      }
      deferredInstallPrompt.prompt();
      deferredInstallPrompt.userChoice.finally(function () {
        deferredInstallPrompt = null;
        hideInstallPrompt();
      });
    });
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return Promise.resolve(null);
    return navigator.serviceWorker.register("/service-worker.js").catch(function () {
      return null;
    });
  }

  function updatePushReadiness() {
    var targets = document.querySelectorAll("[data-push-readiness]");
    if (!targets.length) return;
    var ready = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    var configured = readiness && readiness.vapid_public_key_configured;
    var stored = readiness && readiness.active_subscriptions > 0;
    targets.forEach(function (target) {
      target.classList.add("edu-push-ready-badge");
      if (!ready) {
        target.innerHTML = '<i class="ph ph-bell-slash" aria-hidden="true"></i><span>Push not supported here</span>';
      } else if (!configured) {
        target.innerHTML = '<i class="ph ph-bell-ringing" aria-hidden="true"></i><span>Push storage ready</span>';
      } else if (stored) {
        target.innerHTML = '<i class="ph ph-check-circle" aria-hidden="true"></i><span>Alerts enabled</span>';
      } else {
        target.innerHTML = '<i class="ph ph-bell-ringing" aria-hidden="true"></i><span>Push ready</span>';
      }
    });
  }

  function loadReadiness() {
    return fetch("/pwa/push-readiness/", { credentials: "same-origin" })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) { readiness = data || readiness; updatePushReadiness(); return readiness; })
      .catch(function () { updatePushReadiness(); return readiness; });
  }

  function enablePushNotifications() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      alert("This browser does not support push notifications.");
      return;
    }
    loadReadiness().then(function (data) {
      if (!data || !data.vapid_public_key) {
        alert("Push notification storage is ready. Add VAPID keys on the server to enable delivery.");
        return;
      }
      return Notification.requestPermission().then(function (permission) {
        if (permission !== "granted") return;
        return navigator.serviceWorker.ready.then(function (registration) {
          return registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(data.vapid_public_key)
          });
        }).then(function (subscription) {
          return fetch(data.subscribe_url || "/pwa/push-subscribe/", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
            body: JSON.stringify(subscription)
          });
        }).then(function (response) {
          if (!response.ok) {
            return response.json().catch(function () { return {}; }).then(function (payload) {
              throw new Error(payload.error || "Could not save this browser for alerts.");
            });
          }
          return loadReadiness();
        }).catch(function (error) {
          alert(error.message || "Could not enable alerts for this browser.");
        });
      });
    });
  }

  function init() {
    createOfflineBanner();
    createInstallPrompt();
    updateOfflineBanner();
    setupInstallPrompt();
    registerServiceWorker().then(loadReadiness);
    window.addEventListener("online", updateOfflineBanner);
    window.addEventListener("offline", updateOfflineBanner);
  }

  ready(init);
})();
