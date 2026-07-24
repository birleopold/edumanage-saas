(function () {
  "use strict";

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function initSidebar() {
    var sidebar = document.getElementById("platform-sidebar");
    var backdrop = document.getElementById("platform-sidebar-backdrop");
    var openButton = document.getElementById("platform-sidebar-open");
    var closeButton = document.getElementById("platform-sidebar-close");
    if (!sidebar || !backdrop || !openButton) return;

    function setOpen(open) {
      sidebar.classList.toggle("is-open", open);
      backdrop.classList.toggle("is-open", open);
      sidebar.setAttribute("aria-hidden", open ? "false" : window.innerWidth < 1024 ? "true" : "false");
      openButton.setAttribute("aria-expanded", open ? "true" : "false");
      document.body.style.overflow = open && window.innerWidth < 1024 ? "hidden" : "";
    }

    openButton.addEventListener("click", function () { setOpen(true); });
    backdrop.addEventListener("click", function () { setOpen(false); });
    if (closeButton) closeButton.addEventListener("click", function () { setOpen(false); });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth >= 1024) setOpen(false);
    });
  }

  function initCopyButtons() {
    document.querySelectorAll("[data-copy-value]").forEach(function (button) {
      button.addEventListener("click", function () {
        var value = button.getAttribute("data-copy-value") || "";
        if (!value || !navigator.clipboard) return;
        navigator.clipboard.writeText(value).then(function () {
          var original = button.textContent;
          button.textContent = "Copied";
          window.setTimeout(function () { button.textContent = original; }, 1400);
        });
      });
    });
  }

  ready(function () {
    initSidebar();
    initCopyButtons();
  });
})();
