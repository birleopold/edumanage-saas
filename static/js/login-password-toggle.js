(() => {
  "use strict";

  function initialisePasswordToggle() {
    const password = document.querySelector("[data-login-password]");
    const toggle = document.querySelector("[data-password-visibility-toggle]");
    if (!password || !toggle) return;

    toggle.addEventListener("click", () => {
      const isVisible = password.type === "text";
      password.type = isVisible ? "password" : "text";
      toggle.setAttribute("aria-pressed", isVisible ? "false" : "true");
      toggle.setAttribute("aria-label", isVisible ? "Show password" : "Hide password");

      const icon = toggle.querySelector("i");
      if (icon) {
        icon.className = isVisible
          ? "ph ph-eye text-lg"
          : "ph ph-eye-slash text-lg";
      }
      password.focus({ preventScroll: true });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialisePasswordToggle, { once: true });
  } else {
    initialisePasswordToggle();
  }
})();
