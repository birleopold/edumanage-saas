(function () {
  "use strict";

  const SETUP_PATH = "/admin/school-setup/";
  const STRUCTURE_PATH = "/admin/academics/framework/";
  const CLASSES_PATH = "/admin/academics/class-groups/";
  const STEP_TITLES = {
    institution: "Institution profile and campuses",
    education_structure: "Education structure and curriculum",
    calendar: "Academic calendar",
    classes: "Classes, levels and streams",
    subjects: "Subjects, course units and pathways",
    assessment: "Assessment, grading and report rules",
    teaching: "Teachers and teaching assignments",
    learners: "Learners and go-live check",
    attendance: "Attendance",
    finance: "Fees and finance",
  };
  const CORE_STEP_ORDER = [
    "institution",
    "education_structure",
    "calendar",
    "classes",
    "subjects",
    "assessment",
    "teaching",
    "learners",
  ];

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

  function readJsonScript(id) {
    const node = document.getElementById(id);
    if (!node) return {};
    try {
      return JSON.parse(node.textContent || "{}");
    } catch (_error) {
      return {};
    }
  }

  function readQuickStartConfig() {
    return readJsonScript("school-setup-quickstart-config");
  }

  function readValidationConfig() {
    return readJsonScript("school-setup-validation-config");
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

    const icon = document.createElement("i");
    icon.className = `ph ${options.icon}`;
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);

    const label = document.createElement("span");
    label.textContent = options.label;
    button.appendChild(label);
    form.appendChild(button);

    if (options.confirmMessage) {
      form.addEventListener("submit", (event) => {
        if (!window.confirm(options.confirmMessage)) event.preventDefault();
      });
    }

    return form;
  }

  function noticeCard(options) {
    const box = document.createElement("div");
    box.className = "rounded-2xl border border-amber-200 bg-amber-50 p-5";

    const title = document.createElement("h4");
    title.className = "font-black text-amber-950";
    title.textContent = options.title;
    box.appendChild(title);

    const text = document.createElement("p");
    text.className = "mt-2 text-sm leading-6 text-amber-900";
    text.textContent = options.description;
    box.appendChild(text);

    if (options.href && options.label) {
      const link = document.createElement("a");
      link.href = options.href;
      link.className =
        "mt-4 inline-flex items-center gap-2 rounded-xl border border-amber-300 bg-white px-4 py-2.5 text-sm font-black text-amber-900 hover:bg-amber-100";
      link.textContent = options.label;
      box.appendChild(link);
    }

    return box;
  }

  function stageSelectionNotice() {
    return noticeCard({
      title: "Choose the school stages before creating secondary levels",
      description:
        "EduManage will not guess whether this institution offers O-Level, A-Level, Primary, or a combination. Enable the actual campus stages first; the standard-level quick start will then create only the matching P/S levels.",
      href: STRUCTURE_PATH,
      label: "Choose education stages",
    });
  }

  function addQuickStartActions() {
    if (currentPath() !== SETUP_PATH) return;
    if (document.getElementById("school-setup-safe-actions")) return;

    const csrfToken = getCookie("csrftoken");
    if (!csrfToken) return;

    const config = readQuickStartConfig();
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
          primary: !config.uganda_levels_available && !config.class_groups_available,
        },
        csrfToken
      )
    );

    if (config.uganda_levels_available) {
      const levelNames = Array.isArray(config.uganda_level_names)
        ? config.uganda_level_names.join(", ")
        : "the applicable standard levels";
      grid.appendChild(
        actionForm(
          {
            action: "bootstrap_uganda_levels",
            title: "Create missing Uganda standard levels",
            description: `Create only missing levels for the education stages already selected: ${levelNames}. Then synchronize the structure.`,
            safety:
              "Existing levels are kept exactly as they are. Inactive levels remain inactive. Subjects, classes, streams and dates are not auto-created.",
            label: "Create missing levels",
            icon: "ph-magic-wand",
            primary: true,
            confirmMessage: `Create only these missing standard levels where absent — ${levelNames} — and synchronize the education structure? Existing records will not be renamed, deleted or reactivated.`,
          },
          csrfToken
        )
      );
    } else if (config.uganda_stage_selection_required) {
      grid.appendChild(stageSelectionNotice());
    }

    if (config.class_groups_available) {
      const classLevels = Array.isArray(config.class_group_level_names)
        ? config.class_group_level_names.join(", ")
        : "the mapped in-scope levels";
      const campusName = config.class_group_campus_name || "the active campus";
      grid.appendChild(
        actionForm(
          {
            action: "bootstrap_class_groups",
            title: "Create missing class groups",
            description: `At ${campusName}, create one class group only for mapped active levels belonging to education stages enabled at this campus: ${classLevels}.`,
            safety:
              "Unmapped or out-of-stage levels are excluded. Existing or inactive class groups are preserved, same-name conflicts require review, and streams are not auto-created.",
            label: "Create missing classes",
            icon: "ph-users-three",
            primary: !config.uganda_levels_available,
            confirmMessage: `Create one missing class group per listed in-scope level at ${campusName}? Out-of-stage, unmapped, existing, inactive, conflicting and campus-less class groups will not be overwritten.`,
          },
          csrfToken
        )
      );
    } else if (config.class_group_reason === "multiple_campuses") {
      grid.appendChild(
        noticeCard({
          title: "Classes need campus-by-campus setup",
          description:
            config.class_group_message ||
            "This institution has multiple active campuses, so EduManage will not guess which levels belong at each campus.",
          href: CLASSES_PATH,
          label: "Manage classes",
        })
      );
    } else if (
      config.class_group_reason === "no_enabled_stages" ||
      config.class_group_reason === "no_mapped_levels"
    ) {
      grid.appendChild(
        noticeCard({
          title: "Synchronize education stages before creating classes",
          description:
            config.class_group_message ||
            "Class automation is available only after levels are mapped to education stages enabled for the campus.",
          href: STRUCTURE_PATH,
          label: "Review education structure",
        })
      );
    }

    section.appendChild(grid);

    const sections = container.querySelectorAll("section");
    const anchor = sections.length > 1 ? sections[1] : sections[0];
    if (anchor) anchor.insertAdjacentElement("afterend", section);
    else container.prepend(section);
  }

  function findingAction(finding, tone) {
    if (!finding.action_url) return null;
    const link = document.createElement("a");
    link.href = finding.action_url;
    link.textContent = finding.action_label || "Open settings";
    link.className =
      tone === "blocker"
        ? "mt-3 inline-flex rounded-lg bg-red-600 px-3 py-2 text-xs font-black text-white hover:bg-red-700"
        : "mt-3 inline-flex rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-black text-amber-900 hover:bg-amber-100";
    return link;
  }

  function findingBox(finding, tone) {
    const box = document.createElement("div");
    box.className =
      tone === "blocker"
        ? "rounded-xl border border-red-200 bg-red-50 p-4"
        : "rounded-xl border border-amber-200 bg-amber-50 p-4";

    const title = document.createElement("p");
    title.className =
      tone === "blocker" ? "text-sm font-black text-red-950" : "text-sm font-black text-amber-950";
    title.textContent = finding.title || (tone === "blocker" ? "Needs attention" : "Review this");
    box.appendChild(title);

    const message = document.createElement("p");
    message.className =
      tone === "blocker" ? "mt-1 text-sm leading-6 text-red-900" : "mt-1 text-sm leading-6 text-amber-900";
    message.textContent = finding.message || "";
    box.appendChild(message);

    const action = findingAction(finding, tone);
    if (action) box.appendChild(action);
    return box;
  }

  function firstCoreBlocker(config) {
    const steps = config.steps || {};
    for (const key of CORE_STEP_ORDER) {
      const blockers = Array.isArray(steps[key] && steps[key].blockers) ? steps[key].blockers : [];
      if (blockers.length) return { key, finding: blockers[0] };
    }
    return null;
  }

  function addValidationSummary(config, container) {
    if (document.getElementById("school-setup-validation-summary")) return;
    const coreBlockers = Number(config.core_blocker_count || 0);
    const allBlockers = Number(config.blocker_count || 0);
    const warnings = Number(config.warning_count || 0);
    const optionalBlockers = Math.max(0, allBlockers - coreBlockers);

    const section = document.createElement("section");
    section.id = "school-setup-validation-summary";
    section.className = coreBlockers
      ? "rounded-2xl border border-red-200 bg-red-50 p-6 shadow-sm"
      : "rounded-2xl border border-emerald-200 bg-emerald-50 p-6 shadow-sm";

    const eyebrow = document.createElement("p");
    eyebrow.className = coreBlockers
      ? "text-xs font-black uppercase tracking-wider text-red-700"
      : "text-xs font-black uppercase tracking-wider text-emerald-700";
    eyebrow.textContent = "Setup verification";
    section.appendChild(eyebrow);

    const heading = document.createElement("h3");
    heading.className = coreBlockers
      ? "mt-1 text-xl font-black text-red-950"
      : "mt-1 text-xl font-black text-emerald-950";
    heading.textContent = coreBlockers
      ? `${coreBlockers} core setup issue${coreBlockers === 1 ? "" : "s"} must be fixed`
      : "Core setup records pass the consistency checks";
    section.appendChild(heading);

    const description = document.createElement("p");
    description.className = coreBlockers
      ? "mt-2 max-w-4xl text-sm leading-6 text-red-900"
      : "mt-2 max-w-4xl text-sm leading-6 text-emerald-900";
    description.textContent = coreBlockers
      ? "EduManage now checks whether setup records agree with each other, not only whether they exist. Work from the first incomplete step downward; each issue below explains what to fix and why."
      : "No core contradiction was found. Amber review items are recommendations or conditions worth confirming; they do not automatically block go-live.";
    section.appendChild(description);

    const stats = document.createElement("div");
    stats.className = "mt-4 flex flex-wrap gap-2 text-xs font-black";
    const statRows = [
      [coreBlockers, "must fix", "bg-white text-red-800"],
      [warnings, "review", "bg-white text-amber-800"],
    ];
    if (optionalBlockers) statRows.push([optionalBlockers, "optional setup issue(s)", "bg-white text-slate-700"]);
    for (const [count, label, className] of statRows) {
      const pill = document.createElement("span");
      pill.className = `rounded-full px-3 py-1.5 ${className}`;
      pill.textContent = `${count} ${label}`;
      stats.appendChild(pill);
    }
    section.appendChild(stats);

    const first = firstCoreBlocker(config);
    if (first && first.finding && first.finding.action_url) {
      const start = document.createElement("a");
      start.href = first.finding.action_url;
      start.className =
        "mt-5 inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-black text-white hover:bg-red-700";
      start.textContent = `Start here: ${first.finding.action_label || STEP_TITLES[first.key] || "Fix first issue"}`;
      section.appendChild(start);
    }

    const hero = container.querySelector("section");
    if (hero) hero.insertAdjacentElement("afterend", section);
    else container.prepend(section);
  }

  function findStepCard(title) {
    const heading = Array.from(document.querySelectorAll("h4")).find(
      (node) => (node.textContent || "").trim() === title
    );
    if (!heading) return null;
    return heading.closest("li") || heading.closest(".rounded-2xl");
  }

  function addStepValidation(key, result) {
    const title = STEP_TITLES[key];
    if (!title || !result) return;
    const card = findStepCard(title);
    if (!card || card.querySelector(`[data-setup-validation="${key}"]`)) return;

    const blockers = Array.isArray(result.blockers) ? result.blockers : [];
    const warnings = Array.isArray(result.warnings) ? result.warnings : [];
    if (!blockers.length && !warnings.length) return;

    const panel = document.createElement("div");
    panel.dataset.setupValidation = key;
    panel.className = "mt-5 border-t border-slate-200 pt-4";

    if (blockers.length) {
      const label = document.createElement("p");
      label.className = "mb-2 text-xs font-black uppercase tracking-wider text-red-700";
      label.textContent = "Fix before this step is ready";
      panel.appendChild(label);

      const list = document.createElement("div");
      list.className = "space-y-2";
      blockers.forEach((finding) => list.appendChild(findingBox(finding, "blocker")));
      panel.appendChild(list);
      card.classList.add("ring-1", "ring-red-200");
    }

    if (warnings.length) {
      const details = document.createElement("details");
      details.className = blockers.length ? "mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4" : "rounded-xl border border-amber-200 bg-amber-50 p-4";
      const summary = document.createElement("summary");
      summary.className = "cursor-pointer text-sm font-black text-amber-950";
      summary.textContent = `${warnings.length} review item${warnings.length === 1 ? "" : "s"} — does not automatically block setup`;
      details.appendChild(summary);

      const list = document.createElement("div");
      list.className = "mt-3 space-y-2";
      warnings.forEach((finding) => list.appendChild(findingBox(finding, "warning")));
      details.appendChild(list);
      panel.appendChild(details);
    }

    card.appendChild(panel);
  }

  function addValidationPresentation() {
    if (currentPath() !== SETUP_PATH) return;
    const config = readValidationConfig();
    if (!config.steps) return;
    const main = document.getElementById("main-content") || document.querySelector("main");
    const container = main ? main.querySelector(".space-y-7") : null;
    if (!container) return;

    addValidationSummary(config, container);
    Object.entries(config.steps).forEach(([key, result]) => addStepValidation(key, result));
  }

  function enhanceSchoolSetup() {
    relabelSchoolSetup();
    addQuickStartActions();
    addValidationPresentation();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceSchoolSetup, { once: true });
  } else {
    enhanceSchoolSetup();
  }
})();
