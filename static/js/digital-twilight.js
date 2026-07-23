(() => {
  "use strict";

  const STORAGE_KEY = "edumanage-admin-sidebar-collapsed";
  const DESKTOP_QUERY = "(min-width: 1024px)";
  const SEARCH_INPUT_ID = "global-q";

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

  function initialiseDigitalTwilight() {
    if (!document.body.classList.contains("role-admin")) return;

    const sidebar = document.getElementById("sidebar");
    if (sidebar) {
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
