(function () {
  "use strict";

  var ROLE_CONFIGS = [
    {
      bodyClass: "role-platform",
      pathPrefix: "/platform/",
      title: "Platform Owner Area"
    },
    {
      bodyClass: "role-admin",
      pathPrefix: "/admin/",
      title: "School Admin Area"
    },
    {
      bodyClass: "role-teacher",
      pathPrefix: "/teacher/",
      title: "Teacher Area"
    },
    {
      bodyClass: "role-student",
      pathPrefix: "/student/",
      title: "Student Area"
    },
    {
      bodyClass: "role-parent",
      pathPrefix: "/parent/",
      title: "Parent Area"
    }
  ];

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function detectRoleConfig() {
    var body = document.body;
    var path = window.location.pathname;
    for (var i = 0; i < ROLE_CONFIGS.length; i += 1) {
      var config = ROLE_CONFIGS[i];
      if (body.classList.contains(config.bodyClass) || path.indexOf(config.pathPrefix) === 0) {
        return config;
      }
    }
    return null;
  }

  function addCompactRoleBadge(config) {
    var target = document.querySelector(
      "aside .flex.flex-col.text-white, aside .flex.flex-col.overflow-hidden, aside .flex.flex-col"
    );
    if (!target || target.querySelector(".edu-role-scope-mini")) return;

    var badge = document.createElement("span");
    badge.className = "edu-role-scope-mini";
    badge.textContent = config.title;
    target.appendChild(badge);
  }

  function initRoleScopeClarity() {
    var config = detectRoleConfig();
    if (!config) return;

    /*
     * Role scope is shown as a compact sidebar label only. The previous
     * full-width banner repeated tenant information on every page and pushed
     * the actual task below the fold.
     */
    addCompactRoleBadge(config);
  }

  ready(initRoleScopeClarity);
})();
