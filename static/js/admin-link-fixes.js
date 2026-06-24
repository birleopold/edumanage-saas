(function () {
  "use strict";

  var FEATURE_URLS = {
    ACADEMICS: ["/admin/academics/"],
    ADMISSIONS: ["/admin/admissions/"],
    ATTENDANCE: ["/admin/attendance/"],
    ASSESSMENTS: ["/admin/assessments/"],
    ANNOUNCEMENTS: ["/admin/announcements/"],
    COURSEWORK: ["/admin/coursework/"],
    FINANCE: ["/admin/finance/"],
    EXAMS: ["/admin/exams/"],
    REPORTS: ["/admin/reports/"],
    DOCUMENTS: ["/admin/documents/"],
    TIMETABLE: ["/admin/timetable/"],
    TRANSPORT: ["/admin/transport/"],
    LIBRARY: ["/admin/library/"],
    HOSTELS: ["/admin/hostels/"],
    INVENTORY: ["/admin/inventory/"],
    HR: ["/admin/hr/"],
    DISCIPLINE: ["/admin/discipline/"],
    MESSAGING: ["/messages/", "/message-ops/"],
    ANALYTICS: ["/admin/analytics/"],
    AUDIT: ["/admin/audit/"],
    INTEGRATIONS: ["/admin/integrations/"],
    MOBILE_API: ["/api/v1/mobile/"]
  };

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function flags() {
    var node = document.getElementById("edu-feature-flags");
    if (!node) return {};
    try {
      return JSON.parse(node.textContent || "{}");
    } catch (error) {
      return {};
    }
  }

  function isDisabled(value) {
    return value === false || value === "false" || value === "0" || value === 0;
  }

  function closestHideTarget(link) {
    return link.closest("[data-feature-card]") ||
      link.closest("a.group.rounded-2xl") ||
      link.closest("div[x-data]") ||
      link.closest("a.group.flex") ||
      link;
  }

  function hideFeatureLinks() {
    var currentFlags = flags();
    Object.keys(FEATURE_URLS).forEach(function (feature) {
      if (!isDisabled(currentFlags[feature])) return;
      FEATURE_URLS[feature].forEach(function (prefix) {
        document.querySelectorAll('a[href^="' + prefix + '"]').forEach(function (link) {
          var target = closestHideTarget(link);
          if (target) target.setAttribute("hidden", "hidden");
        });
      });
    });
  }

  function fixTransportScheduleLink() {
    var transportMenu = document.getElementById("admin-nav-submenu-transport");
    if (!transportMenu) return;
    var links = transportMenu.querySelectorAll("a");
    links.forEach(function (link) {
      var label = (link.textContent || "").trim().toLowerCase();
      if (label === "schedules" && link.getAttribute("href") === "/admin/exams/schedules/") {
        link.setAttribute("href", "/admin/transport/schedules/");
      }
    });
  }

  function init() {
    fixTransportScheduleLink();
    hideFeatureLinks();
  }

  ready(init);
})();
