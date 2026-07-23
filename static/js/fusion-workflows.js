(() => {
  "use strict";

  const CONFIG = {
    student: [
      {
        key: "identity",
        label: "Student identity",
        description: "Names, date of birth and contact details",
        heading: "Who is the learner?",
        help: "Enter the learner’s official identity exactly as it appears on school or government records.",
        fields: ["first_name", "last_name", "date_of_birth", "email"],
      },
      {
        key: "placement",
        label: "School placement",
        description: "Campus, class and student numbers",
        heading: "Where does the learner belong?",
        help: "Choose the correct campus and stream, then confirm the school and government learner identifiers.",
        fields: ["campus", "stream", "student_id", "learner_id"],
      },
      {
        key: "background",
        label: "Background",
        description: "Location and identification records",
        heading: "Complete supporting information",
        help: "Add location and identification details when they are available. Optional fields may be completed later.",
        fields: ["district", "subcounty", "parish", "nin"],
      },
      {
        key: "access",
        label: "Portal access",
        description: "Status and secure account delivery",
        heading: "Choose account and access settings",
        help: "Decide whether the learner is active and whether a secure portal account should be created and delivered.",
        fields: ["is_active", "create_user", "send_email"],
      },
    ],
    teacher: [
      {
        key: "identity",
        label: "Teacher identity",
        description: "Staff number, names and contacts",
        heading: "Who is the staff member?",
        help: "Enter the teacher’s official staff identity and reliable contact information.",
        fields: ["staff_id", "first_name", "last_name", "phone", "email"],
      },
      {
        key: "assignment",
        label: "School assignment",
        description: "Campus and employment status",
        heading: "Where is the teacher assigned?",
        help: "Confirm the teacher’s campus and whether the staff record should be active immediately.",
        fields: ["campus", "is_active"],
      },
      {
        key: "access",
        label: "Portal access",
        description: "Account creation and invitation",
        heading: "Prepare secure teacher access",
        help: "Create a teacher portal account and choose whether to deliver the setup link by email.",
        fields: ["create_user", "send_email"],
      },
    ],
  };

  function createElement(tag, className, html) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (html !== undefined) element.innerHTML = html;
    return element;
  }

  function fieldContainer(shell, name) {
    return shell.querySelector(`[data-field-name="${CSS.escape(name)}"]`);
  }

  function hasFieldError(container) {
    return container && container.dataset.fieldError === "true";
  }

  function makeStepper(steps) {
    const stepper = createElement("div", "edu-guided-stepper");
    stepper.style.setProperty("--guided-step-count", String(steps.length));
    stepper.setAttribute("role", "tablist");
    stepper.setAttribute("aria-label", "Record setup steps");

    steps.forEach((step, index) => {
      const button = createElement(
        "button",
        "edu-guided-step",
        `<span class="edu-guided-step__number">${index + 1}</span><span><strong>${step.label}</strong><span>${step.description}</span></span>`,
      );
      button.type = "button";
      button.id = `edu-guided-tab-${step.key}`;
      button.setAttribute("role", "tab");
      button.setAttribute("aria-controls", `edu-guided-panel-${step.key}`);
      button.setAttribute("aria-selected", index === 0 ? "true" : "false");
      button.tabIndex = index === 0 ? 0 : -1;
      if (index === 0) button.setAttribute("aria-current", "step");
      step.button = button;
      stepper.appendChild(button);
    });

    return stepper;
  }

  function makeProgress() {
    const wrapper = createElement("div", "edu-guided-progress");
    const message = createElement("p", "", '<strong>Step 1</strong> of 1');
    message.setAttribute("role", "status");
    message.setAttribute("aria-live", "polite");
    const track = createElement("span", "edu-guided-progress__track", '<span class="edu-guided-progress__fill"></span>');
    track.setAttribute("aria-hidden", "true");
    wrapper.append(message, track);
    return { wrapper, message, track };
  }

  function makePanel(step, index, shell) {
    const panel = createElement("section", "edu-guided-panel");
    panel.id = `edu-guided-panel-${step.key}`;
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", `edu-guided-tab-${step.key}`);
    panel.tabIndex = 0;
    if (index !== 0) panel.hidden = true;

    const heading = createElement(
      "div",
      "edu-guided-panel__heading",
      `<h3>${step.heading}</h3><p>${step.help}</p>`,
    );
    const fields = createElement("div", "edu-guided-panel__fields");

    step.fields.forEach((fieldName) => {
      const container = fieldContainer(shell, fieldName);
      if (!container) return;
      const type = container.dataset.fieldType || "";
      if (["checkbox", "file", "textarea"].includes(type)) container.dataset.wide = "true";
      fields.appendChild(container);
    });

    panel.append(heading, fields);
    step.panel = panel;
    step.hasErrors = Array.from(fields.children).some(hasFieldError);
    return panel;
  }

  function makeNavigation(form, originalActions) {
    const navigation = createElement("div", "edu-guided-navigation");
    const back = createElement("button", "edu-guided-back", '<i class="ph ph-arrow-left" aria-hidden="true"></i> Previous');
    back.type = "button";
    const right = createElement("div", "edu-guided-navigation__right");
    const next = createElement("button", "edu-guided-next", 'Continue <i class="ph ph-arrow-right" aria-hidden="true"></i>');
    next.type = "button";

    const cancel = originalActions ? originalActions.querySelector(".edu-form-cancel") : null;
    const submit = originalActions ? originalActions.querySelector(".edu-form-submit") : null;
    if (cancel) right.appendChild(cancel.cloneNode(true));
    right.appendChild(next);
    if (submit) {
      const submitClone = submit.cloneNode(true);
      submitClone.classList.add("edu-guided-submit");
      submitClone.hidden = true;
      right.appendChild(submitClone);
    }

    navigation.append(back, right);
    form.appendChild(navigation);
    return { navigation, back, next, submit: right.querySelector(".edu-guided-submit") };
  }

  function validateCurrentStep(step) {
    const fields = step.panel.querySelectorAll("input, select, textarea");
    for (const field of fields) {
      if (!field.checkValidity()) {
        field.reportValidity();
        field.focus();
        return false;
      }
    }
    return true;
  }

  function setupAccessDependencies(shell) {
    const createUser = shell.querySelector('[name="create_user"]');
    const sendEmail = shell.querySelector('[name="send_email"]');
    if (!createUser || !sendEmail) return;

    const sendContainer = sendEmail.closest("[data-field-name]");
    const note = createElement(
      "p",
      "edu-field-dependency-note",
      "Email delivery is available only when a portal account is being created.",
    );
    if (sendContainer) sendContainer.appendChild(note);

    const update = () => {
      const accountEnabled = createUser.checked;
      sendEmail.disabled = !accountEnabled;
      if (!accountEnabled) sendEmail.checked = false;
      if (sendContainer) sendContainer.setAttribute("aria-disabled", accountEnabled ? "false" : "true");
      note.classList.toggle("is-visible", !accountEnabled);
    };

    createUser.addEventListener("change", update);
    update();
  }

  function enhanceGuidedForm(shell) {
    const kind = shell.dataset.guidedForm;
    const configured = CONFIG[kind];
    if (!configured || shell.classList.contains("is-enhanced")) return;

    const form = shell.querySelector("form");
    const originalGrid = form ? form.querySelector(":scope > .grid") : null;
    const originalActions = form ? form.querySelector(":scope > .edu-form-actions") : null;
    if (!form || !originalGrid) return;

    const steps = configured
      .map((step) => ({ ...step, fields: [...step.fields] }))
      .filter((step) => step.fields.some((name) => fieldContainer(shell, name)));
    if (!steps.length) return;

    const stepper = makeStepper(steps);
    const progress = makeProgress();
    const panels = createElement("div", "edu-guided-panels");
    steps.forEach((step, index) => panels.appendChild(makePanel(step, index, shell)));

    const ungrouped = Array.from(originalGrid.querySelectorAll(":scope > [data-field-name]"));
    if (ungrouped.length) {
      const finalStep = steps[steps.length - 1];
      ungrouped.forEach((container) => finalStep.panel.querySelector(".edu-guided-panel__fields").appendChild(container));
    }

    form.insertBefore(stepper, originalGrid);
    form.insertBefore(progress.wrapper, originalGrid);
    form.insertBefore(panels, originalGrid);
    const controls = makeNavigation(form, originalActions);

    let currentIndex = Math.max(0, steps.findIndex((step) => step.hasErrors));
    if (currentIndex < 0) currentIndex = 0;

    const showStep = (index, focusPanel = false) => {
      currentIndex = Math.max(0, Math.min(index, steps.length - 1));
      steps.forEach((step, stepIndex) => {
        const active = stepIndex === currentIndex;
        const complete = stepIndex < currentIndex;
        step.panel.hidden = !active;
        step.button.setAttribute("aria-selected", active ? "true" : "false");
        step.button.setAttribute("aria-current", active ? "step" : "false");
        step.button.tabIndex = active ? 0 : -1;
        step.button.classList.toggle("is-complete", complete);
        const number = step.button.querySelector(".edu-guided-step__number");
        if (number) number.innerHTML = complete ? '<i class="ph ph-check" aria-hidden="true"></i>' : String(stepIndex + 1);
      });

      controls.back.disabled = currentIndex === 0;
      controls.next.hidden = currentIndex === steps.length - 1;
      if (controls.submit) controls.submit.hidden = currentIndex !== steps.length - 1;
      progress.message.innerHTML = `<strong>Step ${currentIndex + 1}</strong> of ${steps.length} · ${steps[currentIndex].label}`;
      progress.track.style.setProperty("--guided-progress", `${((currentIndex + 1) / steps.length) * 100}%`);
      const fill = progress.track.querySelector(".edu-guided-progress__fill");
      if (fill) fill.style.setProperty("--guided-progress", `${((currentIndex + 1) / steps.length) * 100}%`);
      if (focusPanel) steps[currentIndex].panel.focus({ preventScroll: true });
    };

    steps.forEach((step, index) => {
      step.button.addEventListener("click", () => {
        if (index > currentIndex && !validateCurrentStep(steps[currentIndex])) return;
        showStep(index, true);
      });
      step.button.addEventListener("keydown", (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let target = currentIndex;
        if (event.key === "ArrowLeft") target = Math.max(0, currentIndex - 1);
        if (event.key === "ArrowRight") target = Math.min(steps.length - 1, currentIndex + 1);
        if (event.key === "Home") target = 0;
        if (event.key === "End") target = steps.length - 1;
        showStep(target, false);
        steps[target].button.focus();
      });
    });

    controls.back.addEventListener("click", () => showStep(currentIndex - 1, true));
    controls.next.addEventListener("click", () => {
      if (validateCurrentStep(steps[currentIndex])) showStep(currentIndex + 1, true);
    });

    form.addEventListener("submit", (event) => {
      for (let index = 0; index < steps.length; index += 1) {
        if (!validateCurrentStep(steps[index])) {
          event.preventDefault();
          showStep(index, true);
          return;
        }
      }
    });

    shell.classList.add("is-enhanced");
    setupAccessDependencies(shell);
    showStep(currentIndex, false);
  }

  function labelRegistryTables() {
    document.querySelectorAll("table.edu-registry-table").forEach((table) => {
      const headings = Array.from(table.querySelectorAll("thead th")).map((cell) => cell.textContent.trim());
      table.querySelectorAll("tbody tr").forEach((row) => {
        Array.from(row.children).forEach((cell, index) => {
          if (headings[index]) cell.dataset.label = headings[index];
        });
      });
    });
  }

  function initialise() {
    document.querySelectorAll("[data-guided-form]").forEach(enhanceGuidedForm);
    labelRegistryTables();
    document.documentElement.dataset.fusionWorkflowsReady = "true";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialise, { once: true });
  } else {
    initialise();
  }
})();
