(function () {
  "use strict";

  const ROLE_ROUTES = [
    { bodyClass: "role-admin", href: "/admin/capabilities/" },
    { bodyClass: "role-teacher", href: "/teacher/capabilities/" },
    { bodyClass: "role-student", href: "/student/capabilities/" },
    { bodyClass: "role-parent", href: "/parent/capabilities/" },
  ];

  function currentRoleRoute() {
    return ROLE_ROUTES.find(function (item) {
      return document.body.classList.contains(item.bodyClass);
    });
  }

  function buildLink(config) {
    const active = window.location.pathname === config.href;
    const link = document.createElement("a");
    link.href = config.href;
    link.className = "edu-phase-capability-link" + (active ? " edu-phase-capability-link--active" : "");
    link.setAttribute("aria-current", active ? "page" : "false");
    link.innerHTML = [
      '<span class="edu-phase-capability-link__icon"><i class="ph ph-squares-four" aria-hidden="true"></i></span>',
      '<span class="edu-phase-capability-link__copy"><strong>All tools</strong><small>Find any page</small></span>',
      '<i class="ph ph-arrow-right edu-phase-capability-link__arrow" aria-hidden="true"></i>',
    ].join("");
    return link;
  }

  function compactSidebar(sidebar, originalSections) {
    if (originalSections.length < 2 || sidebar.querySelector("[data-more-shortcuts]")) return;

    const details = document.createElement("details");
    details.dataset.moreShortcuts = "true";
    details.className = "edu-more-shortcuts";

    const summary = document.createElement("summary");
    summary.innerHTML = '<span><i class="ph ph-list" aria-hidden="true"></i> More shortcuts</span><i class="ph ph-caret-down edu-more-shortcuts__caret" aria-hidden="true"></i>';

    const content = document.createElement("div");
    content.className = "edu-more-shortcuts__content";

    originalSections.slice(1).forEach(function (section) {
      content.appendChild(section);
    });

    const hasActiveItem = Boolean(content.querySelector(".nav-active, [aria-current='page'], .bg-primary-50"));
    details.open = hasActiveItem;
    details.appendChild(summary);
    details.appendChild(content);
    sidebar.appendChild(details);
  }

  function installNavigationLink() {
    const config = currentRoleRoute();
    if (!config || document.querySelector('[data-tool-directory-link="true"]')) return;

    const sidebar = document.querySelector("aside nav");
    if (!sidebar) return;

    const originalSections = Array.from(sidebar.children).filter(function (item) {
      return item.tagName === "DIV";
    });

    const wrapper = document.createElement("div");
    wrapper.dataset.toolDirectoryLink = "true";
    wrapper.className = "edu-phase-capability-link-wrap";
    wrapper.appendChild(buildLink(config));
    sidebar.insertBefore(wrapper, sidebar.firstChild);

    compactSidebar(sidebar, originalSections);
  }

  document.addEventListener("DOMContentLoaded", installNavigationLink);
})();
