(function () {
  "use strict";

  var MODULES = [
    {
      prefixes: ["/admin/academics/"],
      title: "Academics navigation",
      description: "Move quickly between academic setup, records and reports.",
      actions: [
        ["Add New", "/admin/academics/courses/create/", "ph-plus-circle", "primary"],
        ["View All", "/admin/academics/courses/", "ph-list-bullets", "secondary"],
        ["Settings", "/admin/academics/", "ph-sliders", "secondary"],
        ["Reports", "/admin/reports/academic-performance/", "ph-chart-line-up", "secondary"],
        ["Back to Dashboard", "/admin/", "ph-arrow-left", "ghost"]
      ]
    },
    {
      prefixes: ["/admin/admissions/"],
      title: "Admissions navigation",
      description: "Access applications, leads, forms, pipeline and reports from one place.",
      actions: [
        ["Add New", "/admin/admissions/create/", "ph-plus-circle", "primary"],
        ["View All", "/admin/admissions/", "ph-list-bullets", "secondary"],
        ["Settings", "/admin/admissions/forms/", "ph-sliders", "secondary"],
        ["Reports", "/admin/admissions/pipeline/", "ph-chart-line-up", "secondary"],
        ["Back to Dashboard", "/admin/", "ph-arrow-left", "ghost"]
      ]
    },
    {
      prefixes: ["/admin/finance/"],
      title: "Finance navigation",
      description: "Jump to invoices, fee settings, finance reports and the dashboard.",
      actions: [
        ["Add New", "/admin/finance/invoices/create/", "ph-plus-circle", "primary"],
        ["View All", "/admin/finance/invoices/", "ph-list-bullets", "secondary"],
        ["Settings", "/admin/finance/fee-items/", "ph-sliders", "secondary"],
        ["Reports", "/admin/reports/finance/", "ph-chart-line-up", "secondary"],
        ["Back to Dashboard", "/admin/", "ph-arrow-left", "ghost"]
      ]
    },
    {
      prefixes: ["/admin/hr/"],
      title: "HR navigation",
      description: "Manage staff, departments, positions, payroll and reports.",
      actions: [
        ["Add New", "/admin/hr/staff/create/", "ph-plus-circle", "primary"],
        ["View All", "/admin/hr/", "ph-list-bullets", "secondary"],
        ["Settings", "/admin/hr/departments/", "ph-sliders", "secondary"],
        ["Reports", "/admin/reports/", "ph-chart-line-up", "secondary"],
        ["Back to Dashboard", "/admin/", "ph-arrow-left", "ghost"]
      ]
    },
    {
      prefixes: ["/admin/analytics/"],
      title: "Analytics navigation",
      description: "Open dashboards, records, charts and academic reports fast.",
      actions: [
        ["Add New", "/admin/analytics/records/", "ph-plus-circle", "primary"],
        ["View All", "/admin/analytics/", "ph-list-bullets", "secondary"],
        ["Settings", "/admin/analytics/records/", "ph-sliders", "secondary"],
        ["Reports", "/admin/reports/academic-performance/", "ph-chart-line-up", "secondary"],
        ["Back to Dashboard", "/admin/", "ph-arrow-left", "ghost"]
      ]
    },
    {
      prefixes: ["/admin/settings/"],
      title: "Organization settings navigation",
      description: "Manage profile, campuses, feature flags and reports.",
      actions: [
        ["Add New", "/admin/settings/campuses/create/", "ph-plus-circle", "primary"],
        ["View All", "/admin/settings/campuses/", "ph-list-bullets", "secondary"],
        ["Settings", "/admin/settings/", "ph-sliders", "secondary"],
        ["Reports", "/admin/reports/", "ph-chart-line-up", "secondary"],
        ["Back to Dashboard", "/admin/", "ph-arrow-left", "ghost"]
      ]
    },
    {
      prefixes: ["/admin/enterprise/"],
      title: "Platform controls navigation",
      description: "Open enterprise controls, settings, reports and the dashboard.",
      actions: [
        ["Add New", "/admin/enterprise/permissions/", "ph-plus-circle", "primary"],
        ["View All", "/admin/enterprise/", "ph-list-bullets", "secondary"],
        ["Settings", "/admin/enterprise/org-settings/", "ph-sliders", "secondary"],
        ["Reports", "/admin/enterprise/analytics/", "ph-chart-line-up", "secondary"],
        ["Back to Dashboard", "/admin/", "ph-arrow-left", "ghost"]
      ]
    },
    {
      prefixes: ["/platform/"],
      title: "Platform navigation",
      description: "Manage SaaS tenants, domains, onboarding and platform records.",
      actions: [
        ["Add New", "/platform/tenants/create/", "ph-plus-circle", "primary"],
        ["View All", "/platform/tenants/", "ph-list-bullets", "secondary"],
        ["Settings", "/dj-admin/", "ph-sliders", "secondary"],
        ["Reports", "/platform/", "ph-chart-line-up", "secondary"],
        ["Back to Dashboard", "/platform/", "ph-arrow-left", "ghost"]
      ]
    }
  ];

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function currentModule() {
    var path = window.location.pathname;
    for (var i = 0; i < MODULES.length; i += 1) {
      var module = MODULES[i];
      for (var j = 0; j < module.prefixes.length; j += 1) {
        if (path.indexOf(module.prefixes[j]) === 0) return module;
      }
    }
    return null;
  }

  function actionHtml(action) {
    var label = action[0];
    var url = action[1];
    var icon = action[2];
    var style = action[3] || "secondary";
    return [
      '<a class="edu-module-actions__button edu-module-actions__button--' + style + '" href="' + url + '">',
      '<i class="ph ' + icon + '" aria-hidden="true"></i>',
      '<span>' + label + '</span>',
      '</a>'
    ].join("");
  }

  function buildStrip(module) {
    var section = document.createElement("section");
    section.id = "edu-module-actions";
    section.className = "edu-module-actions";
    section.setAttribute("aria-label", module.title);
    section.innerHTML = [
      '<div class="edu-module-actions__copy">',
      '<p class="edu-module-actions__eyebrow">Module shortcuts</p>',
      '<h2>' + module.title + '</h2>',
      '<p>' + module.description + '</p>',
      '</div>',
      '<div class="edu-module-actions__buttons">',
      module.actions.map(actionHtml).join(""),
      '</div>'
    ].join("");
    return section;
  }

  function insertStrip(strip) {
    var adminHeader = document.querySelector("#main-content > div:first-child");
    if (adminHeader && adminHeader.parentNode) {
      adminHeader.parentNode.insertBefore(strip, adminHeader.nextSibling);
      return true;
    }

    var platformContent = document.querySelector("main section.px-5, main section.lg\\:px-8, main section");
    if (platformContent) {
      platformContent.insertBefore(strip, platformContent.firstChild);
      return true;
    }
    return false;
  }

  function initModuleActions() {
    if (document.getElementById("edu-module-actions")) return;
    var module = currentModule();
    if (!module) return;
    insertStrip(buildStrip(module));
  }

  ready(initModuleActions);
})();
