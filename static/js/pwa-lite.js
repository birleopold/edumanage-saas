(function () {
  "use strict";

  var deferredInstallPrompt = null;

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
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
      '<p class="edu-install-prompt__text">Add this school system to your phone for faster access.</p>',
      '<span data-push-readiness></span>',
      '</div>',
      '<div class="edu-install-prompt__actions">',
      '<button type="button" data-pwa-install>Install</button>',
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
      if (dismissButton) {
        localStorage.setItem("edumanage_install_dismissed", "1");
        hideInstallPrompt();
      }
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
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/service-worker.js").catch(function () {
      // Keep silent: the app must continue working even if service worker registration fails.
    });
  }

  function updatePushReadiness() {
    var targets = document.querySelectorAll("[data-push-readiness]");
    if (!targets.length) return;
    var ready = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    targets.forEach(function (target) {
      target.classList.add("edu-push-ready-badge");
      target.innerHTML = ready
        ? '<i class="ph ph-bell-ringing" aria-hidden="true"></i><span>Push-ready browser</span>'
        : '<i class="ph ph-bell-slash" aria-hidden="true"></i><span>Push not supported here</span>';
    });
  }

  function init() {
    createOfflineBanner();
    createInstallPrompt();
    updateOfflineBanner();
    setupInstallPrompt();
    registerServiceWorker();
    updatePushReadiness();
    window.addEventListener("online", updateOfflineBanner);
    window.addEventListener("offline", updateOfflineBanner);
  }

  ready(init);
})();
