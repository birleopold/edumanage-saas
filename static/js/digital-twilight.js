(() => {
  "use strict";

  const STORAGE_KEY = "edumanage-admin-sidebar-collapsed";
  const DESKTOP_QUERY = "(min-width: 1024px)";
  const SEARCH_INPUT_ID = "global-q";

  const ATTENDANCE_MENU_ITEMS = [
    ["/admin/attendance/", "Overview", "ph-gauge"],
    ["/admin/attendance/devices/", "Devices", "ph-fingerprint"],
    ["/admin/attendance/devices/add/", "Add / Connect Device", "ph-plus-circle"],
    ["/admin/attendance/daily/", "Daily Register", "ph-calendar-check"],
    ["/admin/attendance/events/", "Raw Events", "ph-waveform"],
    ["/admin/attendance/policies/", "Policies", "ph-sliders-horizontal"],
    ["/admin/attendance/import/", "Import", "ph-upload-simple"],
    ["/admin/attendance/integration-guide/", "Setup Instructions", "ph-book-open-text"],
    ["/admin/attendance/sessions/", "Class Attendance", "ph-chalkboard-teacher"]
  ];

  function isEditableTarget(target) {
    if (!target) return false;
    const tagName = target.tagName ? target.tagName.toLowerCase() : "";
    return target.isContentEditable || ["input", "textarea", "select"].includes(tagName);
  }

  function readStoredPreference() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === "true";
    } catch (_error) {
      return false;
    }
  }

  function storePreference(collapsed) {
    try {
      window.localStorage.setItem(STORAGE_KEY, collapsed ? "true" : "false");
    } catch (_error) {
      // Storage can be unavailable in private browsing or locked-down devices.
    }
  }

  function setAccessibleNavigationState(sidebar) {
    sidebar.querySelectorAll("nav div[id*='submenu'] a.text-white").forEach((link) => {
      link.classList.add("nav-active");
      link.style.setProperty("color", "#ffffff", "important");
    });

    sidebar.querySelectorAll("a.nav-active, a.bg-primary-50").forEach((link) => {
      link.setAttribute("aria-current", "page");
    });

    sidebar.querySelectorAll("nav a, nav button").forEach((item) => {
      const labelNode = item.querySelector("span");
      const label = labelNode ? labelNode.textContent.trim() : item.textContent.trim();
      if (label && !item.hasAttribute("title")) item.setAttribute("title", label);
    });
  }

  function createCollapseButton(sidebar) {
    const existing = sidebar.querySelector(".edu-sidebar-collapse");
    if (existing) return existing;

    const header = sidebar.firstElementChild;
    if (!header) return null;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "edu-sidebar-collapse";
    button.setAttribute("aria-controls", "sidebar");
    button.innerHTML = '<i class="ph ph-caret-double-left" aria-hidden="true"></i><span class="sr-only">Collapse navigation</span>';
    header.appendChild(button);
    return button;
  }

  function setupDesktopCollapse(sidebar) {
    const media = window.matchMedia(DESKTOP_QUERY);
    const button = createCollapseButton(sidebar);
    if (!button) return;

    let preferredCollapsed = readStoredPreference();

    const applyState = (collapsed, persist = false) => {
      preferredCollapsed = Boolean(collapsed);
      const effectiveCollapsed = media.matches && preferredCollapsed;
      document.body.classList.toggle("edu-sidebar-collapsed", effectiveCollapsed);
      button.setAttribute("aria-expanded", effectiveCollapsed ? "false" : "true");
      button.setAttribute("aria-label", effectiveCollapsed ? "Expand navigation" : "Collapse navigation");
      button.title = effectiveCollapsed ? "Expand navigation" : "Collapse navigation";

      const icon = button.querySelector("i");
      if (icon) {
        icon.className = effectiveCollapsed
          ? "ph ph-caret-double-right"
          : "ph ph-caret-double-left";
      }

      if (persist) storePreference(preferredCollapsed);
    };

    button.addEventListener("click", () => {
      applyState(!document.body.classList.contains("edu-sidebar-collapsed"), true);
    });

    const onViewportChange = () => applyState(preferredCollapsed, false);
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onViewportChange);
    } else if (typeof media.addListener === "function") {
      media.addListener(onViewportChange);
    }

    applyState(preferredCollapsed, false);
  }

  function setupSearchShortcut() {
    const input = document.getElementById(SEARCH_INPUT_ID);
    if (!input) return;

    const form = input.closest("form");
    if (form && !form.querySelector(".edu-search-shortcut")) {
      const hint = document.createElement("kbd");
      hint.className = "edu-search-shortcut";
      hint.textContent = navigator.platform && navigator.platform.toLowerCase().includes("mac") ? "⌘ K" : "Ctrl K";
      hint.setAttribute("aria-hidden", "true");
      form.appendChild(hint);
    }

    document.addEventListener("keydown", (event) => {
      const commandK = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k";
      const slash = event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey;
      if ((!commandK && !slash) || isEditableTarget(event.target)) return;

      event.preventDefault();
      input.focus();
      input.select();
    });
  }

  function improveDashboardSemantics() {
    document.querySelectorAll(".edu-kpi-card").forEach((card) => {
      card.setAttribute("role", "group");
    });

    document.querySelectorAll(".edu-priority-item, .edu-module-card, .edu-operation-card").forEach((link) => {
      if (link.tagName.toLowerCase() === "a" && !link.getAttribute("aria-label")) {
        const heading = link.querySelector("h4, strong");
        if (heading) link.setAttribute("aria-label", heading.textContent.trim());
      }
    });
  }

  function attendanceItemActive(href, currentPath) {
    if (href === "/admin/attendance/") return currentPath === href;
    return currentPath === href || currentPath.startsWith(href);
  }

  function setupAttendanceDropdown(sidebar) {
    if (!sidebar || sidebar.querySelector("[data-admin-attendance-menu]")) return;

    const sourceLink = Array.from(sidebar.querySelectorAll("nav a")).find((link) => {
      return link.getAttribute("href") === "/admin/attendance/sessions/" &&
        (link.textContent || "").trim() === "Attendance";
    });
    if (!sourceLink || sourceLink.hidden || sourceLink.hasAttribute("hidden")) return;

    const currentPath = window.location.pathname || "";
    const attendanceActive = currentPath.startsWith("/admin/attendance/");

    const wrapper = document.createElement("div");
    wrapper.dataset.adminAttendanceMenu = "true";
    wrapper.className = "relative";

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.id = "admin-nav-trigger-attendance";
    trigger.setAttribute("aria-controls", "admin-nav-submenu-attendance");
    trigger.setAttribute("aria-expanded", attendanceActive ? "true" : "false");
    trigger.className = "group w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium rounded-xl transition-all duration-200 " +
      (attendanceActive ? "nav-active text-white" : "text-slate-700 nav-hover");
    trigger.innerHTML =
      '<div class="flex items-center"><i class="ph-fill ph-calendar-check text-lg mr-3" aria-hidden="true"></i><span>Attendance</span></div>' +
      '<i class="ph ph-caret-down text-sm transition-transform duration-200' + (attendanceActive ? " rotate-180" : "") + '" aria-hidden="true"></i>';

    const submenu = document.createElement("div");
    submenu.id = "admin-nav-submenu-attendance";
    submenu.setAttribute("role", "group");
    submenu.setAttribute("aria-label", "Attendance");
    submenu.className = "ml-4 mt-1 space-y-1 border-l-2 pl-3";
    submenu.style.borderColor = "color-mix(in srgb, var(--org-primary) 20%, transparent)";
    submenu.hidden = !attendanceActive;

    ATTENDANCE_MENU_ITEMS.forEach(([href, label, icon]) => {
      const link = document.createElement("a");
      link.href = href;
      link.className = "block px-3 py-2 text-sm rounded-lg transition-colors text-slate-600 hover:bg-slate-100";
      link.innerHTML = '<i class="ph ' + icon + ' mr-2" aria-hidden="true"></i>' + label;
      if (attendanceItemActive(href, currentPath)) {
        link.classList.add("nav-active", "text-white", "font-semibold");
        link.classList.remove("text-slate-600");
        link.setAttribute("aria-current", "page");
      }
      submenu.appendChild(link);
    });

    trigger.addEventListener("click", () => {
      const opening = submenu.hidden;
      submenu.hidden = !opening;
      trigger.setAttribute("aria-expanded", opening ? "true" : "false");
      const caret = trigger.querySelector(".ph-caret-down");
      if (caret) caret.classList.toggle("rotate-180", opening);
    });

    wrapper.appendChild(trigger);
    wrapper.appendChild(submenu);
    sourceLink.replaceWith(wrapper);
  }

  function initialiseDigitalTwilight() {
    if (!document.body.classList.contains("role-admin")) return;

    const sidebar = document.getElementById("sidebar");
    if (sidebar) {
      setupAttendanceDropdown(sidebar);
      setAccessibleNavigationState(sidebar);
      setupDesktopCollapse(sidebar);
    }

    setupSearchShortcut();
    improveDashboardSemantics();
    document.documentElement.dataset.digitalTwilightReady = "true";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialiseDigitalTwilight, { once: true });
  } else {
    initialiseDigitalTwilight();
  }
})();
