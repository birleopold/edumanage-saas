(function () {
  "use strict";

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function initPasswordToggles() {
    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
      var targetId = button.getAttribute("data-password-toggle");
      var input = document.getElementById(targetId);
      if (!input) return;

      button.addEventListener("click", function () {
        var showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.setAttribute("aria-pressed", showing ? "false" : "true");
        button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
        var icon = button.querySelector("i");
        if (icon) {
          icon.className = showing ? "ph ph-eye" : "ph ph-eye-slash";
        }
      });
    });
  }

  function initDomainPreview() {
    var typeField = document.getElementById("id_type") || document.getElementById("id_domain_type");
    var domainField = document.getElementById("id_domain");
    var preview = document.querySelector("[data-domain-preview]");
    if (!typeField || !preview) return;

    function update() {
      var type = String(typeField.value || "CUSTOM").toUpperCase();
      var domain = domainField ? String(domainField.value || "").trim() : "";
      var example = type === "SUBDOMAIN" ? "school.edumanage.com" : "portal.school.ac.ug";
      var routing = type === "SUBDOMAIN"
        ? "Use a platform-controlled subdomain and point it to the EduManage host."
        : "Use the school's own domain and point its DNS records to EduManage.";
      preview.innerHTML = "<strong>" + (domain || example) + "</strong><span>" + routing + "</span>";
    }

    typeField.addEventListener("change", update);
    if (domainField) domainField.addEventListener("input", update);
    update();
  }

  function initPackageFeatures() {
    var packageField = document.getElementById("id_package");
    var featureContainer = document.getElementById("id_feature_flags");
    var note = document.querySelector("[data-package-note]");
    var configNode = document.getElementById("platform-package-presets");
    if (!packageField || !featureContainer || !configNode) return;

    var presets = {};
    try {
      presets = JSON.parse(configNode.textContent || "{}");
    } catch (error) {
      return;
    }

    var checkboxes = Array.prototype.slice.call(featureContainer.querySelectorAll("input[type='checkbox']"));

    function update() {
      var code = packageField.value || "standard";
      var preset = presets[code] || {};
      var isCustom = code === "custom";
      var enabled = new Set(preset.features || []);

      checkboxes.forEach(function (checkbox) {
        if (!isCustom) checkbox.checked = enabled.has(checkbox.value);
        checkbox.disabled = !isCustom;
      });

      featureContainer.classList.toggle("is-preset", !isCustom);
      if (note) {
        if (isCustom) {
          note.textContent = "Custom package: choose each module that should be enabled.";
        } else {
          note.textContent = (preset.label || code) + " preset: " + enabled.size + " modules will be enabled automatically.";
        }
      }
    }

    packageField.addEventListener("change", update);
    update();
  }

  function initSchemaSuggestion() {
    var nameField = document.getElementById("id_name");
    var schemaField = document.getElementById("id_schema_name");
    if (!nameField || !schemaField || schemaField.disabled) return;

    var manuallyEdited = Boolean(schemaField.value);
    schemaField.addEventListener("input", function () {
      manuallyEdited = Boolean(schemaField.value);
    });

    nameField.addEventListener("input", function () {
      if (manuallyEdited) return;
      var suggested = String(nameField.value || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .replace(/^[^a-z]+/, "")
        .slice(0, 63);
      schemaField.value = suggested;
    });
  }

  ready(function () {
    initPasswordToggles();
    initDomainPreview();
    initPackageFeatures();
    initSchemaSuggestion();
  });
})();
