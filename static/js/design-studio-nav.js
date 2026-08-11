(() => {
  "use strict";

  function operationsMenu(sidebar) {
    const headings = Array.from(sidebar.querySelectorAll("nav h3"));
    const heading = headings.find((item) => (item.textContent || "").trim().toLowerCase() === "operations");
    if (!heading) return null;
    const section = heading.closest("div");
    return section ? section.querySelector(".space-y-1") : null;
  }

  function addDesignStudioLink() {
    if (!document.body.classList.contains("role-admin")) return;
    const sidebar = document.getElementById("sidebar");
    if (!sidebar || sidebar.querySelector('a[href="/design-studio/"]')) return;

    const menu = operationsMenu(sidebar);
    if (!menu) return;

    const active = (window.location.pathname || "").startsWith("/design-studio/");
    const link = document.createElement("a");
    link.href = "/design-studio/";
    link.title = "Design Studio";
    link.className = "group flex items-center px-4 py-2.5 text-sm font-medium rounded-xl transition-all duration-200 " +
      (active ? "nav-active text-white" : "text-slate-700 nav-hover");
    if (active) link.setAttribute("aria-current", "page");
    link.innerHTML =
      '<i class="ph-fill ph-paint-brush-broad text-lg mr-3 transition-colors duration-200" ' +
      'style="color:' + (active ? 'white' : 'var(--org-primary)') + ';opacity:' + (active ? '1' : '0.5') + ';" aria-hidden="true"></i>' +
      '<span>Design Studio</span>';
    menu.appendChild(link);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addDesignStudioLink, { once: true });
  } else {
    addDesignStudioLink();
  }
})();
