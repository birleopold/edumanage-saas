(function () {
  "use strict";

  function relabelSchoolSetup() {
    const links = Array.from(document.querySelectorAll('a[href]'));
    const setupLink = links.find((link) => {
      try {
        return new URL(link.href, window.location.origin).pathname === "/admin/school-setup/";
      } catch (_error) {
        return false;
      }
    });

    if (!setupLink) return;

    const label = setupLink.querySelector("span");
    if (label) label.textContent = "School Setup";

    const icon = setupLink.querySelector("i");
    if (icon) {
      icon.classList.remove("ph-clipboard-text");
      icon.classList.add("ph-sliders-horizontal");
    }

    setupLink.setAttribute(
      "aria-label",
      "School Setup — guided institution, academic and operational configuration"
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", relabelSchoolSetup, { once: true });
  } else {
    relabelSchoolSetup();
  }
})();
