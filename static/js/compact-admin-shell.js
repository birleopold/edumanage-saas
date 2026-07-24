(function () {
  "use strict";

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function compactRedesignedWorkspace() {
    if (!document.body.classList.contains("role-admin")) return;

    var workspace = document.querySelector("#main-content .edu-ops-page");
    if (!workspace) return;

    var inner = workspace.parentElement;
    var shell = inner && inner.parentElement;
    if (!inner || !shell) return;

    inner.classList.add("edu-content-shell__inner");
    shell.classList.add("edu-content-shell--flush");
  }

  ready(compactRedesignedWorkspace);
})();
