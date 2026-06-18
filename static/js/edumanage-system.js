(function () {
  "use strict";

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function isMobileShell() {
    return window.matchMedia("(max-width: 1023px)").matches;
  }

  function sidebarElements() {
    return {
      sidebar: document.getElementById("sidebar"),
      backdrop: document.getElementById("sidebar-backdrop")
    };
  }

  function sidebarIsOpen() {
    var elements = sidebarElements();
    return Boolean(elements.sidebar && !elements.sidebar.classList.contains("-translate-x-full"));
  }

  function closeSidebar() {
    var elements = sidebarElements();
    if (!elements.sidebar || !elements.backdrop || !isMobileShell()) return;
    elements.sidebar.classList.add("-translate-x-full");
    elements.backdrop.classList.add("hidden");
    document.body.style.overflow = "";
  }

  function syncSidebarState() {
    var elements = sidebarElements();
    if (!elements.sidebar || !elements.backdrop) return;

    if (!isMobileShell()) {
      elements.backdrop.classList.add("hidden");
      document.body.style.overflow = "";
      return;
    }

    document.body.style.overflow = sidebarIsOpen() ? "hidden" : "";
  }

  function enhanceSidebar() {
    var elements = sidebarElements();
    if (!elements.sidebar) return;

    elements.sidebar.setAttribute("aria-label", elements.sidebar.getAttribute("aria-label") || "Portal navigation");

    if (typeof window.toggleSidebar === "function" && !window.toggleSidebar.__eduManageEnhanced) {
      var originalToggle = window.toggleSidebar;
      var enhancedToggle = function () {
        originalToggle();
        window.requestAnimationFrame(syncSidebarState);
      };
      enhancedToggle.__eduManageEnhanced = true;
      window.toggleSidebar = enhancedToggle;
    }

    elements.sidebar.querySelectorAll("nav a[href]").forEach(function (link) {
      link.addEventListener("click", function () {
        if (isMobileShell()) closeSidebar();
      });
    });

    var active = elements.sidebar.querySelector(".nav-active, .bg-primary-50");
    if (active) {
      active.setAttribute("aria-current", "page");
      window.requestAnimationFrame(function () {
        active.scrollIntoView({ block: "nearest", behavior: "auto" });
      });
    }

    window.addEventListener("resize", syncSidebarState, { passive: true });
    syncSidebarState();
  }

  function enhanceTables() {
    document.querySelectorAll("main .overflow-x-auto").forEach(function (wrapper) {
      var table = wrapper.querySelector("table");
      if (!table) return;

      function updateOverflow() {
        wrapper.dataset.overflowing = String(wrapper.scrollWidth > wrapper.clientWidth + 2);
      }

      updateOverflow();
      window.addEventListener("resize", updateOverflow, { passive: true });
    });
  }

  function enhanceForms() {
    document.querySelectorAll("main form").forEach(function (form) {
      form.addEventListener("submit", function () {
        if (form.method.toLowerCase() === "get" || !form.checkValidity()) return;
        var submitters = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        submitters.forEach(function (button) {
          button.setAttribute("aria-busy", "true");
          button.classList.add("opacity-75", "cursor-wait");
        });
      });
    });
  }

  function enhanceKeyboardNavigation() {
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && sidebarIsOpen()) {
        closeSidebar();
        return;
      }

      var target = event.target;
      var typing = target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
      if (event.key === "/" && !typing && !event.ctrlKey && !event.metaKey && !event.altKey) {
        var search = document.querySelector('header input[type="search"]');
        if (search) {
          event.preventDefault();
          search.focus();
          search.select();
        }
      }
    });
  }

  function enhancePage() {
    var main = document.querySelector("main");
    if (main) main.classList.add("page-fade-in");

    var pageHeader = document.querySelector("#main-content > div:first-child");
    if (pageHeader) {
      var title = pageHeader.querySelector("h1");
      var actions = pageHeader.querySelector("form, a, button");
      if (title && !title.textContent.trim() && !actions) {
        pageHeader.hidden = true;
      }
    }

    document.querySelectorAll('a[target="_blank"]').forEach(function (link) {
      if (!link.rel.includes("noopener")) {
        link.rel = (link.rel + " noopener noreferrer").trim();
      }
    });
  }

  ready(function () {
    enhanceSidebar();
    enhanceTables();
    enhanceForms();
    enhanceKeyboardNavigation();
    enhancePage();
  });
})();
