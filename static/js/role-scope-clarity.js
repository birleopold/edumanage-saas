(function () {
  "use strict";

  var ROLE_CONFIGS = [
    {
      bodyClass: "role-platform",
      pathPrefix: "/platform/",
      title: "Platform Owner Area",
      label: "All-school SaaS control",
      icon: "ph-buildings",
      description: "Manage every school tenant, domain, onboarding status and platform-level operation from one protected console.",
      scope: ["All schools", "Tenant domains", "Platform setup", "SaaS operations"],
      guardrail: "This area is not a school portal. It controls the full EduManage SaaS environment."
    },
    {
      bodyClass: "role-admin",
      pathPrefix: "/admin/",
      title: "School Admin Area",
      label: "One-school management",
      icon: "ph-shield-check",
      description: "Manage this school tenant only: learners, teachers, finance, academics, settings and reports for the current school.",
      scope: ["This school only", "School records", "Fees and reports", "School settings"],
      guardrail: "Data here belongs to the current tenant/school, not to other schools on the platform."
    },
    {
      bodyClass: "role-teacher",
      pathPrefix: "/teacher/",
      title: "Teacher Area",
      label: "Teaching workspace",
      icon: "ph-chalkboard-teacher",
      description: "Focus on daily teaching work: timetable, attendance, coursework, assessments, exams and learner support.",
      scope: ["Assigned classes", "Teaching tasks", "Marks and attendance", "Parent communication"],
      guardrail: "Teachers work with assigned teaching records, not platform or whole-school administration."
    },
    {
      bodyClass: "role-student",
      pathPrefix: "/student/",
      title: "Student Area",
      label: "Learning and results",
      icon: "ph-student",
      description: "Access learning materials, coursework, timetable, exams, results, announcements and personal school records.",
      scope: ["My learning", "My results", "My timetable", "My notices"],
      guardrail: "Students see their own learning records, not other learners or administration tools."
    },
    {
      bodyClass: "role-parent",
      pathPrefix: "/parent/",
      title: "Parent Area",
      label: "Child monitoring and payments",
      icon: "ph-users-three",
      description: "Monitor linked children, results, attendance, discipline, announcements, coursework, fees and payments.",
      scope: ["Linked children", "Payments", "Results", "School communication"],
      guardrail: "Parents see only their linked child records and payment information."
    }
  ];

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
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

  function scopePills(items) {
    return items
      .map(function (item) {
        return '<span class="edu-role-scope__pill">' + escapeHtml(item) + '</span>';
      })
      .join("");
  }

  function buildBanner(config) {
    var section = document.createElement("section");
    section.id = "edu-role-scope-banner";
    section.className = "edu-role-scope edu-role-scope--" + config.bodyClass.replace("role-", "");
    section.setAttribute("aria-label", config.title + " scope notice");
    section.innerHTML = [
      '<div class="edu-role-scope__icon"><i class="ph ' + escapeHtml(config.icon) + '" aria-hidden="true"></i></div>',
      '<div class="edu-role-scope__content">',
      '<p class="edu-role-scope__eyebrow">' + escapeHtml(config.label) + '</p>',
      '<h2>' + escapeHtml(config.title) + '</h2>',
      '<p class="edu-role-scope__description">' + escapeHtml(config.description) + '</p>',
      '<div class="edu-role-scope__pills">' + scopePills(config.scope) + '</div>',
      '</div>',
      '<div class="edu-role-scope__guardrail"><i class="ph ph-lock-key" aria-hidden="true"></i><span>' + escapeHtml(config.guardrail) + '</span></div>'
    ].join("");
    return section;
  }

  function insertBanner(banner) {
    var mainContent = document.getElementById("main-content");
    if (mainContent) {
      var titleContext = mainContent.querySelector(":scope > .mb-6");
      if (titleContext && titleContext.parentNode) {
        titleContext.parentNode.insertBefore(banner, titleContext.nextSibling);
        return true;
      }
      mainContent.insertBefore(banner, mainContent.firstChild);
      return true;
    }

    var platformSection = document.querySelector("main section.px-5, main section.lg\\:px-8, main section");
    if (platformSection) {
      platformSection.insertBefore(banner, platformSection.firstChild);
      return true;
    }
    return false;
  }

  function addCompactRoleBadge(config) {
    var target = document.querySelector("aside .flex.flex-col.text-white, aside .flex.flex-col.overflow-hidden, aside .flex.flex-col");
    if (!target || target.querySelector(".edu-role-scope-mini")) return;
    var badge = document.createElement("span");
    badge.className = "edu-role-scope-mini";
    badge.textContent = config.title;
    target.appendChild(badge);
  }

  function initRoleScopeClarity() {
    if (document.getElementById("edu-role-scope-banner")) return;
    var config = detectRoleConfig();
    if (!config) return;
    addCompactRoleBadge(config);
    insertBanner(buildBanner(config));
  }

  ready(initRoleScopeClarity);
})();
