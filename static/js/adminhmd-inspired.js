(() => {
  "use strict";

  const STORAGE_KEY = "edumanage-admin-theme";
  const DARK_CLASS = "edu-theme-dark";

  function readPreference() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) || "system";
    } catch (_error) {
      return "system";
    }
  }

  function writePreference(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (_error) {
      // Storage may be blocked by the browser. The current page still updates.
    }
  }

  function systemPrefersDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function effectiveDark(preference) {
    if (preference === "dark") return true;
    if (preference === "light") return false;
    return systemPrefersDark();
  }

  function updateThemeButton(button, isDark) {
    if (!button) return;
    button.setAttribute("aria-pressed", isDark ? "true" : "false");
    button.setAttribute("aria-label", isDark ? "Use light appearance" : "Use dark appearance");
    button.title = isDark ? "Use light appearance" : "Use dark appearance";
    const icon = button.querySelector("i");
    if (icon) icon.className = isDark ? "ph ph-sun" : "ph ph-moon";
  }

  function applyTheme(preference, button) {
    const dark = effectiveDark(preference);
    document.body.classList.toggle(DARK_CLASS, dark);
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
    document.documentElement.dataset.eduTheme = dark ? "dark" : "light";
    updateThemeButton(button, dark);
  }

  function createThemeButton() {
    const header = document.querySelector("body.role-admin > div.flex-1 > header");
    if (!header) return null;

    const actions = header.querySelector(":scope > div:last-child");
    if (!actions) return null;

    const existing = actions.querySelector(".edu-theme-toggle");
    if (existing) return existing;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "edu-theme-toggle";
    button.innerHTML = '<i class="ph ph-moon" aria-hidden="true"></i>';

    const notifications = actions.querySelector("[x-data]");
    if (notifications) {
      actions.insertBefore(button, notifications);
    } else {
      actions.prepend(button);
    }
    return button;
  }

  function setupThemeSwitch() {
    const button = createThemeButton();
    if (!button) return;

    let preference = readPreference();
    applyTheme(preference, button);

    button.addEventListener("click", () => {
      const darkNow = document.body.classList.contains(DARK_CLASS);
      preference = darkNow ? "light" : "dark";
      writePreference(preference);
      applyTheme(preference, button);
    });

    if (window.matchMedia) {
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      const followSystem = () => {
        if (readPreference() === "system") applyTheme("system", button);
      };
      if (typeof media.addEventListener === "function") {
        media.addEventListener("change", followSystem);
      } else if (typeof media.addListener === "function") {
        media.addListener(followSystem);
      }
    }
  }

  function labelResponsiveTables() {
    document.querySelectorAll("table.edu-data-table").forEach((table) => {
      const labels = Array.from(table.querySelectorAll("thead th")).map((cell) => cell.textContent.trim());
      table.querySelectorAll("tbody tr").forEach((row) => {
        Array.from(row.children).forEach((cell, index) => {
          if (labels[index]) cell.dataset.label = labels[index];
        });
      });
    });
  }

  function announceFilterCount() {
    const resultCount = document.querySelector("[data-user-result-count]");
    if (!resultCount) return;
    resultCount.setAttribute("role", "status");
    resultCount.setAttribute("aria-live", "polite");
  }

  function initialise() {
    if (!document.body.classList.contains("role-admin")) return;
    setupThemeSwitch();
    labelResponsiveTables();
    announceFilterCount();
    document.documentElement.dataset.adminHmdPatternsReady = "true";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialise, { once: true });
  } else {
    initialise();
  }
})();
