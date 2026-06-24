(function () {
  "use strict";

  var NAVS = [
    {
      match: "/platform/",
      items: [
        ["Home", "/platform/", "ph-gauge"],
        ["Schools", "/platform/tenants/", "ph-buildings"],
        ["Plans", "/platform/subscriptions/", "ph-credit-card"],
        ["Ready", "/platform/deployment-readiness/", "ph-rocket-launch"],
        ["Activity", "/platform/activity/", "ph-clock-counter-clockwise"]
      ]
    },
    {
      match: "/admin/",
      items: [
        ["Home", "/admin/", "ph-house"],
        ["Students", "/admin/students/", "ph-student"],
        ["Fees", "/admin/finance/", "ph-wallet"],
        ["Reports", "/admin/reports/advanced/", "ph-chart-line-up"],
        ["More", "/admin/settings/", "ph-dots-three-circle"]
      ]
    },
    {
      match: "/teacher/",
      items: [
        ["Home", "/teacher/", "ph-house"],
        ["Attendance", "/teacher/attendance/", "ph-calendar-check"],
        ["Marks", "/teacher/assessments/", "ph-exam"],
        ["Work", "/teacher/coursework/", "ph-notebook"],
        ["Search", "/teacher/search/", "ph-magnifying-glass"]
      ]
    },
    {
      match: "/student/",
      items: [
        ["Home", "/student/", "ph-house"],
        ["Results", "/student/results/", "ph-chart-bar"],
        ["Fees", "/student/finance/", "ph-wallet"],
        ["Work", "/student/coursework/", "ph-books"],
        ["Search", "/student/search/", "ph-magnifying-glass"]
      ]
    },
    {
      match: "/parent/",
      items: [
        ["Home", "/parent/", "ph-house"],
        ["Results", "/parent/results/", "ph-chart-bar"],
        ["Fees", "/parent/finance/", "ph-wallet"],
        ["Attend", "/parent/attendance/", "ph-calendar-check"],
        ["Children", "/parent/students/", "ph-users-three"]
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

  function safeHref(value) {
    var url;
    try {
      url = new URL(value, window.location.origin);
    } catch (error) {
      return "#";
    }
    if (url.origin !== window.location.origin) return "#";
    return url.pathname + url.search + url.hash;
  }

  function activeNav() {
    var path = window.location.pathname;
    for (var i = 0; i < NAVS.length; i += 1) {
      if (path.indexOf(NAVS[i].match) === 0) return NAVS[i];
    }
    return null;
  }

  function buildItem(item) {
    var path = window.location.pathname;
    var href = safeHref(item[1]);
    var active = path === href || (href !== "/" && path.indexOf(href) === 0);
    return [
      '<a href="' + href + '" class="' + (active ? 'is-active' : '') + '">',
      '<i class="ph ' + item[2] + '" aria-hidden="true"></i>',
      '<span>' + item[0] + '</span>',
      '</a>'
    ].join("");
  }

  function initMobileBottomNav() {
    if (document.querySelector(".edu-mobile-bottom-nav")) return;
    var nav = activeNav();
    if (!nav) return;
    var section = document.createElement("nav");
    section.className = "edu-mobile-bottom-nav";
    section.setAttribute("aria-label", "Mobile navigation");
    section.innerHTML = nav.items.map(buildItem).join("");
    document.body.appendChild(section);
  }

  ready(initMobileBottomNav);
})();