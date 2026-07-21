(function () {
  "use strict";

  const ROLE_ROUTES = [
    { bodyClass: "role-admin", href: "/admin/capabilities/", label: "Phase 1–9 Features" },
    { bodyClass: "role-teacher", href: "/teacher/capabilities/", label: "Integrated Features" },
    { bodyClass: "role-student", href: "/student/capabilities/", label: "My Learning Features" },
    { bodyClass: "role-parent", href: "/parent/capabilities/", label: "Children's Features" },
  ];

  function currentRoleRoute() {
    return ROLE_ROUTES.find((item) => document.body.classList.contains(item.bodyClass));
  }

  function buildLink(config) {
    const active = window.location.pathname === config.href;
    const link = document.createElement("a");
    link.href = config.href;
    link.className = "edu-phase-capability-link" + (active ? " edu-phase-capability-link--active" : "");
    link.setAttribute("aria-current", active ? "page" : "false");
    link.innerHTML = [
      '<span class="edu-phase-capability-link__icon"><i class="ph ph-circles-four" aria-hidden="true"></i></span>',
      '<span class="edu-phase-capability-link__copy">',
      '<strong>' + config.label + '</strong>',
      '<small>Role-aware access centre</small>',
      '</span>',
      '<i class="ph ph-arrow-right edu-phase-capability-link__arrow" aria-hidden="true"></i>',
    ].join("");
    return link;
  }

  function installNavigationLink() {
    const config = currentRoleRoute();
    if (!config || document.querySelector('[data-phase-capability-link="true"]')) return;

    const sidebar = document.querySelector("aside nav");
    if (!sidebar) return;

    const wrapper = document.createElement("div");
    wrapper.dataset.phaseCapabilityLink = "true";
    wrapper.className = "edu-phase-capability-link-wrap";
    wrapper.appendChild(buildLink(config));
    sidebar.insertBefore(wrapper, sidebar.firstChild);
  }

  document.addEventListener("DOMContentLoaded", installNavigationLink);
})();
