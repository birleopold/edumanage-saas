(function () {
  "use strict";

  const SETUP_PATH = "/admin/school-setup/";

  function currentPath() {
    try {
      return new URL(window.location.href).pathname;
    } catch (_error) {
      return window.location.pathname || "";
    }
  }

  function getCookie(name) {
    const prefix = `${name}=`;
    const rows = (document.cookie || "").split(";");
    for (const row of rows) {
      const value = row.trim();
      if (value.startsWith(prefix)) {
        return decodeURIComponent(value.slice(prefix.length));
      }
    }
    return "";
  }

  function relabelSchoolSetup() {
    const links = Array.from(document.querySelectorAll("a[href]"));
    const setupLink = links.find((link) => {
      try {
        return new URL(link.href, window.location.origin).pathname === SETUP_PATH;
      } catch (_error) {
        return false;
      }
    });

    if (!setupLink) return;

    const label = setupLink.querySelector("span");
    if (label) label.textContent = "School Setup";

    const icon = setupLink.querySelector("i");
    if (icon) {
      icon.classList.remove("ph-clipboard-text");
      icon.classList.add("ph-sliders-horizontal");
    }

    setupLink.setAttribute(
      "aria-label",
      "School Setup — guided institution, academic and operational configuration"
    );
  }

  function hiddenInput(name, value) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    return input;
  }

  function actionForm(options, csrfToken) {
    const form = document.createElement("form");
    form.method = "post";
    form.action = SETUP_PATH;
    form.className = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";
    form.appendChild(hiddenInput("csrfmiddlewaretoken", csrfToken));
    form.appendChild(hiddenInput("action", options.action));

    const title = document.createElement("h4");
    title.className = "font-black text-slate-950";
    title.textContent = options.title;
    form.appendChild(title);

    const text = document.createElement("p");
    text.className = "mt-2 text-sm leading-6 text-slate-600";
    text.textContent = options.description;
    form.appendChild(text);

    const safety = document.createElement("p");
    safety.className = "mt-3 text-xs font-bold text-slate-500";
    safety.textContent = options.safety;
    form.appendChild(safety);

    const button = document.createElement("button");
    button.type = "submit";
    button.className = options.primary
      ? "mt-4 inline-flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-black text-white hover:bg-primary-700"
      : "mt-4 inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-black text-slate-800 hover:border-primary-300 hover:text-primary-700";
    button.innerHTML = `<i class="ph ${options.icon}" aria-hidden="true"></i><span>${options.label}</span>`;
    form.appendChild(button);

    if (options.confirmMessage) {
      form.addEventListener("submit", (event) => {
        if (!window.confirm(options.confirmMessage)) event.preventDefault();
      });
    }

    return form;
  }

  function hasUgandaReference(container) {
    return Array.from(container.querySelectorAll("p")).some((node) =>
      (node.textContent || "").trim().toLowerCase().includes("uganda framework reference")
    );
  }

  function addQuickStartActions() {
    if (currentPath() !== SETUP_PATH) return;
    if (document.getElementById("school-setup-safe-actions")) return;

    const csrfToken = getCookie("csrftoken");
    if (!csrfToken) return;

    const main = document.getElementById("main-content") || document.querySelector("main");
    const container = main ? main.querySelector(".space-y-7") : null;
    if (!container) return;

    const section = document.createElement("section");
    section.id = "school-setup-safe-actions";
    section.className = "rounded-2xl border border-indigo-200 bg-indigo-50 p-6 shadow-sm";

    const eyebrow = document.createElement("p");
    eyebrow.className = "text-xs font-black uppercase tracking-wider text-indigo-700";
    eyebrow.textContent = "Safe quick actions";
    section.appendChild(eyebrow);

    const heading = document.createElement("h3");
    heading.className = "mt-1 text-xl font-black text-indigo-950";
    heading.textContent = "Let EduManage do the repetitive structure work";
    section.appendChild(heading);

    const intro = document.createElement("p");
    intro.className = "mt-2 max-w-4xl text-sm leading-6 text-indigo-900";
    intro.textContent =
      "These actions use the existing academic records. They do not delete classes, rename levels, replace manual mappings, or invent subjects, term dates or grading rules.";
    section.appendChild(intro);

    const grid = document.createElement("div");
    grid.className = "mt-5 grid gap-4 lg:grid-cols-2";

    grid.appendChild(
      actionForm(
        {
          action: "sync_education_structure",
          title: "Synchronize existing structure",
          description:
            "Map the levels you already created to education stages, enable matching campus stages and refresh curriculum links.",
          safety: "Manual administrator corrections are preserved.",
          label: "Synchronize structure",
          icon: "ph-arrows-clockwise",
          primary: !hasUgandaReference(container),
        },
        csrfToken
      )
    );

    if (hasUgandaReference(container)) {
      grid.appendChild(
        actionForm(
          {
            action: "bootstrap_uganda_levels",
            title: "Create missing Uganda standard levels",
            description:
              "For the selected Primary, Secondary or Mixed Uganda profile, create only the missing P1–P7 and/or S1–S6 levels that apply, then synchronize the structure.",
            safety:
              "Existing levels are kept exactly as they are. Inactive levels remain inactive. Subjects, classes, streams and dates are not auto-created.",
            label: "Create missing levels",
            icon: "ph-magic-wand",
            primary: true,
            confirmMessage:
              "Create only the missing standard P/S levels for this Uganda school profile and synchronize the education structure? Existing records will not be renamed, deleted or reactivated.",
          },
          csrfToken
        )
      );
    }

    section.appendChild(grid);

    const sections = container.querySelectorAll("section");
    const anchor = sections.length > 1 ? sections[1] : sections[0];
    if (anchor) anchor.insertAdjacentElement("afterend", section);
    else container.prepend(section);
  }

  function enhanceSchoolSetup() {
    relabelSchoolSetup();
    addQuickStartActions();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceSchoolSetup, { once: true });
  } else {
    enhanceSchoolSetup();
  }
})();
