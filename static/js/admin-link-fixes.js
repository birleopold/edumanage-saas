(function () {
  "use strict";

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
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

  ready(fixTransportScheduleLink);
})();
