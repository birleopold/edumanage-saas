(() => {
  "use strict";

  const DESKTOP_MEDIA = "(min-width: 1024px)";
  const FOCUSABLE_SELECTOR = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled]):not([type='hidden'])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  let mediaQuery = null;
  let lastOpener = null;

  function shellElements() {
    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");
    const controls = Array.from(document.querySelectorAll("[aria-controls='sidebar']"));
    return { sidebar, backdrop, controls };
  }

  function isDesktop() {
    return Boolean(mediaQuery && mediaQuery.matches);
  }

  function isMobileOpen(sidebar) {
    return !isDesktop() && sidebar.getAttribute("aria-hidden") === "false";
  }

  function visibleFocusable(container) {
    return Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR)).filter((element) => {
      if (element.hasAttribute("hidden")) return false;
      const style = window.getComputedStyle(element);
      return style.display !== "none" && style.visibility !== "hidden";
    });
  }

  function updateControls(controls, sidebar, open) {
    controls.forEach((control) => {
      control.setAttribute("aria-expanded", open ? "true" : "false");
      const insideSidebar = sidebar.contains(control);
      if (!insideSidebar) {
        control.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
      }
    });
  }

  function setSidebarState(open, { focusSidebar = false, restoreFocus = false } = {}) {
    const { sidebar, backdrop, controls } = shellElements();
    if (!sidebar || !backdrop) return;

    const effectiveOpen = isDesktop() || Boolean(open);
    sidebar.classList.toggle("-translate-x-full", !effectiveOpen);
    sidebar.setAttribute("aria-hidden", effectiveOpen ? "false" : "true");
    sidebar.toggleAttribute("inert", !effectiveOpen);
    sidebar.dataset.portalOpen = effectiveOpen ? "true" : "false";

    backdrop.classList.toggle("hidden", !effectiveOpen || isDesktop());
    backdrop.dataset.portalOpen = effectiveOpen && !isDesktop() ? "true" : "false";
    updateControls(controls, sidebar, effectiveOpen);

    if (focusSidebar && effectiveOpen && !isDesktop()) {
      window.requestAnimationFrame(() => {
        const [first] = visibleFocusable(sidebar);
        if (first) first.focus();
      });
    }

    if (restoreFocus && lastOpener && document.contains(lastOpener)) {
      window.requestAnimationFrame(() => lastOpener.focus());
    }
  }

  function toggleSidebar(forceOpen) {
    const { sidebar } = shellElements();
    if (!sidebar || isDesktop()) {
      setSidebarState(true);
      return;
    }

    const currentlyOpen = isMobileOpen(sidebar);
    const shouldOpen = typeof forceOpen === "boolean" ? forceOpen : !currentlyOpen;
    if (shouldOpen) {
      const active = document.activeElement;
      if (active && active.getAttribute && active.getAttribute("aria-controls") === "sidebar") {
        lastOpener = active;
      }
    }
    setSidebarState(shouldOpen, {
      focusSidebar: shouldOpen,
      restoreFocus: !shouldOpen,
    });
  }

  function trapSidebarFocus(event) {
    const { sidebar } = shellElements();
    if (!sidebar || event.key !== "Tab" || !isMobileOpen(sidebar)) return;

    const focusable = visibleFocusable(sidebar);
    if (!focusable.length) {
      event.preventDefault();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function initialisePortalShell() {
    const { sidebar, backdrop } = shellElements();
    if (!sidebar || !backdrop) return;

    mediaQuery = window.matchMedia(DESKTOP_MEDIA);
    setSidebarState(isDesktop());

    const onViewportChange = () => {
      lastOpener = null;
      setSidebarState(isDesktop());
    };
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", onViewportChange);
    } else if (typeof mediaQuery.addListener === "function") {
      mediaQuery.addListener(onViewportChange);
    }

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isMobileOpen(sidebar)) {
        event.preventDefault();
        toggleSidebar(false);
        return;
      }
      trapSidebarFocus(event);
    });

    sidebar.addEventListener("click", (event) => {
      const link = event.target.closest("a[href]");
      if (link && !isDesktop()) toggleSidebar(false);
    });

    document.documentElement.dataset.portalShellReady = "true";
  }

  window.toggleSidebar = toggleSidebar;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialisePortalShell, { once: true });
  } else {
    initialisePortalShell();
  }
})();
