(function () {
  "use strict";

  var lastSidebarTrigger = null;
  var generatedId = 0;

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
      backdrop: document.getElementById("sidebar-backdrop"),
      toggles: document.querySelectorAll('button[onclick*="toggleSidebar"], [data-sidebar-toggle]')
    };
  }

  function sidebarIsOpen() {
    var elements = sidebarElements();
    return Boolean(elements.sidebar && !elements.sidebar.classList.contains("-translate-x-full"));
  }

  function focusableElements(container) {
    if (!container) return [];
    return Array.prototype.filter.call(container.querySelectorAll([
      "a[href]",
      "area[href]",
      "button:not([disabled])",
      "input:not([disabled]):not([type='hidden'])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "summary",
      "[tabindex]:not([tabindex='-1'])"
    ].join(",")), function (element) {
      return element.offsetParent !== null && element.getAttribute("aria-hidden") !== "true";
    });
  }

  function syncSidebarState() {
    var elements = sidebarElements();
    if (!elements.sidebar || !elements.backdrop) return;
    var open = sidebarIsOpen();
    elements.sidebar.setAttribute("aria-label", elements.sidebar.getAttribute("aria-label") || "Portal navigation");
    elements.sidebar.setAttribute("aria-hidden", String(isMobileShell() && !open));
    elements.sidebar.setAttribute("role", isMobileShell() ? "dialog" : "navigation");
    if (isMobileShell()) {
      elements.sidebar.setAttribute("aria-modal", String(open));
    } else {
      elements.sidebar.removeAttribute("aria-modal");
    }
    elements.backdrop.setAttribute("aria-hidden", "true");
    elements.toggles.forEach(function (button) {
      button.setAttribute("aria-controls", "sidebar");
      button.setAttribute("aria-expanded", String(open));
    });
    if (!isMobileShell()) {
      elements.backdrop.classList.add("hidden");
      document.body.style.overflow = "";
      return;
    }
    document.body.style.overflow = open ? "hidden" : "";
  }

  function closeSidebar(options) {
    var elements = sidebarElements();
    if (!elements.sidebar || !elements.backdrop || !isMobileShell()) return;
    elements.sidebar.classList.add("-translate-x-full");
    elements.backdrop.classList.add("hidden");
    document.body.style.overflow = "";
    syncSidebarState();
    if (!options || options.restoreFocus !== false) {
      if (lastSidebarTrigger && document.contains(lastSidebarTrigger)) {
        lastSidebarTrigger.focus({ preventScroll: true });
      }
      lastSidebarTrigger = null;
    }
  }

  function openSidebar(trigger) {
    var elements = sidebarElements();
    if (!elements.sidebar || !elements.backdrop || !isMobileShell()) return;
    lastSidebarTrigger = trigger && typeof trigger.focus === "function" ? trigger : document.activeElement;
    elements.sidebar.classList.remove("-translate-x-full");
    elements.backdrop.classList.remove("hidden");
    document.body.style.overflow = "hidden";
    syncSidebarState();
    window.requestAnimationFrame(function () {
      var focusables = focusableElements(elements.sidebar);
      (focusables[0] || elements.sidebar).focus({ preventScroll: true });
    });
  }

  function toggleSidebar(trigger) {
    if (sidebarIsOpen()) {
      closeSidebar();
    } else {
      openSidebar(trigger);
    }
  }

  function trapSidebarFocus(event) {
    if (event.key !== "Tab" || !isMobileShell() || !sidebarIsOpen()) return;
    var elements = sidebarElements();
    if (!elements.sidebar) return;
    var focusables = focusableElements(elements.sidebar);
    if (!focusables.length) {
      event.preventDefault();
      elements.sidebar.focus({ preventScroll: true });
      return;
    }
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (!elements.sidebar.contains(document.activeElement)) {
      event.preventDefault();
      first.focus({ preventScroll: true });
      return;
    }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus({ preventScroll: true });
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus({ preventScroll: true });
    }
  }

  function nextId(prefix) {
    generatedId += 1;
    return prefix + "-" + generatedId;
  }

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") return window.CSS.escape(value);
    return String(value).replace(/["\\]/g, "\\$&");
  }

  function normalizePath(pathname) {
    return (pathname || "").replace(/\/+$/, "") + "/";
  }

  function upgradeSidebarDestinations(sidebar) {
    if (!sidebar) return;
    if (!document.body.classList.contains("role-admin")) return;
    var destinationMap = {
      "/admin/finance/invoices/": "/admin/finance/",
      "/admin/coursework/materials/": "/admin/coursework/"
    };
    sidebar.querySelectorAll("nav a[href]").forEach(function (link) {
      var url;
      try {
        url = new URL(link.getAttribute("href"), window.location.origin);
      } catch (error) {
        return;
      }
      var normalized = normalizePath(url.pathname);
      if (destinationMap[normalized]) {
        link.href = destinationMap[normalized];
        link.dataset.eduDashboardLink = "true";
      }
    });
  }

  function markSidebarActive(sidebar) {
    if (!sidebar) return;
    var current = normalizePath(window.location.pathname);
    sidebar.querySelectorAll("nav a[href]").forEach(function (link) {
      var url;
      try {
        url = new URL(link.getAttribute("href"), window.location.origin);
      } catch (error) {
        return;
      }
      var target = normalizePath(url.pathname);
      if (target !== "/" && current.indexOf(target) === 0 && !link.classList.contains("nav-active")) {
        link.classList.add("edu-nav-current");
      }
    });
  }

  function enhanceSidebar() {
    var elements = sidebarElements();
    if (!elements.sidebar) return;
    elements.sidebar.classList.add("edu-sidebar-upgraded");
    elements.sidebar.setAttribute("tabindex", elements.sidebar.getAttribute("tabindex") || "-1");
    elements.sidebar.setAttribute("aria-label", elements.sidebar.getAttribute("aria-label") || "Portal navigation");
    upgradeSidebarDestinations(elements.sidebar);
    markSidebarActive(elements.sidebar);
    if (!window.toggleSidebar || !window.toggleSidebar.__eduManageEnhanced) {
      var enhancedToggle = function () {
        toggleSidebar(document.activeElement);
      };
      enhancedToggle.__eduManageEnhanced = true;
      window.toggleSidebar = enhancedToggle;
    }
    elements.sidebar.querySelectorAll("nav a[href]").forEach(function (link) {
      link.addEventListener("click", function () {
        if (isMobileShell()) closeSidebar();
      });
    });
    var active = elements.sidebar.querySelector(".nav-active, .bg-primary-50, .edu-nav-current");
    if (active) {
      active.setAttribute("aria-current", "page");
      window.requestAnimationFrame(function () {
        active.scrollIntoView({ block: "nearest", behavior: "auto" });
      });
    }
    window.addEventListener("resize", syncSidebarState, { passive: true });
    document.addEventListener("keydown", trapSidebarFocus);
    syncSidebarState();
  }

  function enhanceTables() {
    document.querySelectorAll("main table").forEach(function (table) {
      if (table.querySelector("caption") || table.hasAttribute("aria-label") || table.hasAttribute("aria-labelledby")) return;
      var container = table.closest("section, article, .bg-white, .rounded-xl, .rounded-2xl, .card, main");
      var heading = container ? container.querySelector("h1, h2, h3") : null;
      if (heading && heading.textContent.trim()) {
        if (!heading.id) heading.id = nextId("edu-table-heading");
        table.setAttribute("aria-labelledby", heading.id);
      } else {
        table.setAttribute("aria-label", "Data table");
      }
    });
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
    document.querySelectorAll("main input, main select, main textarea").forEach(function (field) {
      var type = (field.getAttribute("type") || "").toLowerCase();
      if (["hidden", "submit", "button", "reset", "file"].indexOf(type) !== -1) return;
      if (!field.id) field.id = nextId("edu-field");
      var hasAccessibleName = Boolean(
        field.getAttribute("aria-label") ||
        field.getAttribute("aria-labelledby") ||
        document.querySelector('label[for="' + cssEscape(field.id) + '"]') ||
        field.closest("label")
      );
      if (!hasAccessibleName) {
        var source = field.getAttribute("placeholder") || field.getAttribute("name") || field.id;
        field.setAttribute("aria-label", source.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim());
      }
    });
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

  function enhanceIcons() {
    document.querySelectorAll('i[class*="ph-"], i[class*=" ph"]').forEach(function (icon) {
      if (icon.hasAttribute("aria-hidden") || icon.getAttribute("role") === "img") return;
      var control = icon.closest("button, a");
      var controlText = control ? control.textContent.replace(/\s+/g, " ").trim() : "";
      var controlNamed = control && (control.getAttribute("aria-label") || control.getAttribute("aria-labelledby") || controlText);
      if (!control || controlNamed) {
        icon.setAttribute("aria-hidden", "true");
      }
    });
  }

  function roleLinks() {
    var body = document.body;
    if (body.classList.contains("role-admin")) {
      return [
        ["Command Dashboard", "/admin/", "ph-squares-four"],
        ["Admissions CRM", "/admin/admissions/", "ph-clipboard-text"],
        ["Coursework LMS", "/admin/coursework/", "ph-notebook"],
        ["Online Exams", "/admin/exams/", "ph-desktop"],
        ["Finance Billing", "/admin/finance/", "ph-wallet"],
        ["Accounting Books", "/admin/finance/books/", "ph-bank"],
        ["Payment Reconciliation", "/admin/finance/books/payments/", "ph-arrows-clockwise"],
        ["Messages Inbox", "/messages/", "ph-chats-circle"],
        ["Group Messaging", "/messages/bulk/", "ph-paper-plane-tilt"],
        ["Delivery Dashboard", "/message-ops/delivery/", "ph-broadcast"],
        ["Message Templates", "/message-ops/copy/", "ph-textbox"],
        ["Analytics Intelligence", "/admin/analytics/intelligence/", "ph-brain"],
        ["Reports", "/admin/reports/", "ph-chart-bar"],
        ["Integrations", "/admin/integrations/", "ph-plugs-connected"],
        ["Security Audit", "/admin/audit/", "ph-shield-check"],
        ["System Status", "/admin/system-status/", "ph-heartbeat"]
      ];
    }
    if (body.classList.contains("role-teacher")) {
      return [
        ["Teacher Dashboard", "/teacher/", "ph-squares-four"],
        ["Timetable", "/teacher/timetable/", "ph-calendar"],
        ["Coursework", "/teacher/coursework/", "ph-notebook"],
        ["Attendance", "/teacher/attendance/", "ph-calendar-check"],
        ["Assessments", "/teacher/assessments/", "ph-exam"],
        ["Online Exams", "/teacher/exams/", "ph-desktop"],
        ["Messages", "/messages/", "ph-chats-circle"],
        ["Parent Chat", "/messages/parent-teacher/", "ph-chat-teardrop-text"],
        ["Analytics", "/analytics-portal/teacher/", "ph-chart-line-up"],
        ["Documents", "/teacher/documents/", "ph-file-doc"]
      ];
    }
    if (body.classList.contains("role-parent")) {
      return [
        ["Parent Dashboard", "/parent/", "ph-squares-four"],
        ["Invoices & Pay", "/parent/finance/invoices/", "ph-wallet"],
        ["Results", "/parent/results/", "ph-chart-bar"],
        ["Exams", "/parent/exams/", "ph-file-text"],
        ["Coursework", "/parent/coursework/", "ph-notebook"],
        ["Attendance", "/parent/attendance/", "ph-calendar-check"],
        ["Messages", "/messages/", "ph-chats-circle"],
        ["Teacher Chat", "/messages/parent-teacher/", "ph-chat-teardrop-text"],
        ["Progress Trends", "/analytics-portal/parent/", "ph-chart-line-up"],
        ["Message Preferences", "/parent/account/message-preferences/", "ph-bell"],
        ["Transport", "/parent/transport/", "ph-bus"]
      ];
    }
    if (body.classList.contains("role-student")) {
      return [
        ["Student Dashboard", "/student/", "ph-squares-four"],
        ["Coursework", "/student/coursework/", "ph-notebook"],
        ["Online Exams", "/student/exams/", "ph-desktop"],
        ["Results", "/student/results/", "ph-chart-bar"],
        ["Timetable", "/student/timetable/", "ph-calendar"],
        ["Messages", "/messages/", "ph-chats-circle"],
        ["Progress Trends", "/analytics-portal/student/", "ph-chart-line-up"],
        ["Finance", "/student/finance/invoices/", "ph-wallet"],
        ["Transport", "/student/transport/", "ph-bus"],
        ["Documents", "/student/documents/", "ph-file-doc"]
      ];
    }
    return [];
  }

  function createQuickLauncher() {
    var links = roleLinks();
    if (!links.length || document.getElementById("edu-quick-launcher")) return;
    var launcher = document.createElement("section");
    launcher.id = "edu-quick-launcher";
    launcher.className = "edu-quick-launcher";
    launcher.setAttribute("aria-label", "Quick access menu");
    launcher.innerHTML = [
      '<button type="button" class="edu-quick-launcher__button" aria-expanded="false" aria-controls="edu-quick-launcher-panel">',
      '<i class="ph ph-lightning" aria-hidden="true"></i><span>Quick access</span>',
      '</button>',
      '<div id="edu-quick-launcher-panel" class="edu-quick-launcher__panel" hidden>',
      '<div class="edu-quick-launcher__head"><strong>Quick access</strong><span>Important workflows</span></div>',
      '<div class="edu-quick-launcher__grid"></div>',
      '</div>'
    ].join("");
    var grid = launcher.querySelector(".edu-quick-launcher__grid");
    links.forEach(function (item) {
      var link = document.createElement("a");
      link.href = item[1];
      link.className = "edu-quick-launcher__link";
      link.innerHTML = '<i class="ph ' + item[2] + '" aria-hidden="true"></i><span>' + item[0] + '</span>';
      grid.appendChild(link);
    });
    document.body.appendChild(launcher);
    var button = launcher.querySelector(".edu-quick-launcher__button");
    var panel = launcher.querySelector(".edu-quick-launcher__panel");
    function setOpen(open) {
      panel.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      launcher.classList.toggle("is-open", open);
    }
    button.addEventListener("click", function () { setOpen(panel.hidden); });
    document.addEventListener("click", function (event) {
      if (!launcher.contains(event.target)) setOpen(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(panel.hidden);
        button.focus();
      }
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
    if (main) {
      main.classList.add("page-fade-in");
      if (!main.hasAttribute("tabindex")) main.setAttribute("tabindex", "-1");
    }
    var pageHeader = document.querySelector("#main-content > div:first-child");
    if (pageHeader) {
      var title = pageHeader.querySelector("h1");
      var actions = pageHeader.querySelector("form, a, button");
      if (title && !title.textContent.trim() && !actions) pageHeader.hidden = true;
      if (title && title.textContent.trim() && main) {
        var shellTitle = title.textContent.trim().replace(/\s+/g, " ").toLowerCase();
        var duplicateTitle = Array.prototype.find.call(main.querySelectorAll("h1"), function (heading) {
          if (pageHeader.contains(heading)) return false;
          return heading.textContent.trim().replace(/\s+/g, " ").toLowerCase() === shellTitle;
        });
        if (duplicateTitle) {
          duplicateTitle.classList.add("edu-duplicate-page-title");
          duplicateTitle.setAttribute("aria-hidden", "true");
        }
      }
    }
    document.querySelectorAll('a[target="_blank"]').forEach(function (link) {
      if (!link.rel.includes("noopener")) link.rel = (link.rel + " noopener noreferrer").trim();
    });
  }

  ready(function () {
    enhanceSidebar();
    enhanceTables();
    enhanceForms();
    enhanceIcons();
    enhanceKeyboardNavigation();
    enhancePage();
    createQuickLauncher();
  });
})();
