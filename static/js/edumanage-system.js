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
    if (main) main.classList.add("page-fade-in");
    var pageHeader = document.querySelector("#main-content > div:first-child");
    if (pageHeader) {
      var title = pageHeader.querySelector("h1");
      var actions = pageHeader.querySelector("form, a, button");
      if (title && !title.textContent.trim() && !actions) pageHeader.hidden = true;
    }
    document.querySelectorAll('a[target="_blank"]').forEach(function (link) {
      if (!link.rel.includes("noopener")) link.rel = (link.rel + " noopener noreferrer").trim();
    });
  }

  ready(function () {
    enhanceSidebar();
    enhanceTables();
    enhanceForms();
    enhanceKeyboardNavigation();
    enhancePage();
    createQuickLauncher();
  });
})();
