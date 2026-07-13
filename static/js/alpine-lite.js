(function () {
  "use strict";

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function evaluate(expression, state, element, event) {
    var refs = {};
    var root = element.closest("[data-alpine-lite-root]") || element;
    root.querySelectorAll("[x-ref]").forEach(function (ref) {
      refs[ref.getAttribute("x-ref")] = ref;
    });
    state.$refs = refs;
    state.$nextTick = function (callback) { window.setTimeout(callback, 0); };
    return Function("$data", "$event", "with($data){ return (" + expression + "); }")(state, event);
  }

  function run(expression, state, element, event) {
    var refs = {};
    var root = element.closest("[data-alpine-lite-root]") || element;
    root.querySelectorAll("[x-ref]").forEach(function (ref) {
      refs[ref.getAttribute("x-ref")] = ref;
    });
    state.$refs = refs;
    state.$nextTick = function (callback) { window.setTimeout(callback, 0); };
    return Function("$data", "$event", "with($data){ " + expression + "; }")(state, event);
  }

  function parseState(expression) {
    if (expression.indexOf("{") === 0) {
      return Function("return (" + expression + ");")();
    }
    return Function("with(window){ return (" + expression + "); }")();
  }

  function bind(root, state) {
    var bindings = [];

    function refresh() {
      bindings.forEach(function (binding) { binding(); });
    }

    var watchers = {};
    var proxy = new Proxy(state, {
      set: function (target, property, value) {
        target[property] = value;
        (watchers[property] || []).forEach(function (callback) { callback(value); });
        refresh();
        return true;
      }
    });
    proxy.$watch = function (property, callback) {
      watchers[property] = watchers[property] || [];
      watchers[property].push(callback);
    };

    root.setAttribute("data-alpine-lite-root", "true");

    Array.prototype.forEach.call(root.querySelectorAll("[x-text]"), function (element) {
      bindings.push(function () {
        element.textContent = evaluate(element.getAttribute("x-text"), proxy, element);
      });
    });

    var shown = root.hasAttribute("x-show") ? [root] : [];
    shown = shown.concat(Array.prototype.slice.call(root.querySelectorAll("[x-show]")));
    shown.forEach(function (element) {
      bindings.push(function () {
        element.hidden = !evaluate(element.getAttribute("x-show"), proxy, element);
      });
    });

    root.querySelectorAll("[\\:href]").forEach(function (element) {
      bindings.push(function () {
        element.setAttribute("href", evaluate(element.getAttribute(":href"), proxy, element));
      });
    });

    root.querySelectorAll("[\\:aria-expanded]").forEach(function (element) {
      bindings.push(function () {
        element.setAttribute("aria-expanded", String(evaluate(element.getAttribute(":aria-expanded"), proxy, element)));
      });
    });

    root.querySelectorAll("[\\:disabled]").forEach(function (element) {
      bindings.push(function () {
        element.disabled = Boolean(evaluate(element.getAttribute(":disabled"), proxy, element));
      });
    });

    root.querySelectorAll("[\\:class]").forEach(function (element) {
      var original = element.className;
      bindings.push(function () {
        var result = evaluate(element.getAttribute(":class"), proxy, element);
        element.className = original;
        if (result && typeof result === "object") {
          Object.keys(result).forEach(function (className) {
            element.classList.toggle(className, Boolean(result[className]));
          });
        }
      });
    });

    root.querySelectorAll("[\\@click], [x-on\\:click]").forEach(function (element) {
      var expression = element.getAttribute("@click") || element.getAttribute("x-on:click");
      element.addEventListener("click", function (event) {
        run(expression, proxy, element, event);
        refresh();
      });
    });

    root.querySelectorAll("[\\@submit], [x-on\\:submit]").forEach(function (element) {
      var expression = element.getAttribute("@submit") || element.getAttribute("x-on:submit");
      element.addEventListener("submit", function (event) {
        run(expression, proxy, element, event);
        refresh();
      });
    });

    root.querySelectorAll("[\\@click\\.away], [\\@click\\.outside]").forEach(function (element) {
      var expression = element.getAttribute("@click.away") || element.getAttribute("@click.outside");
      document.addEventListener("click", function (event) {
        if (!element.contains(event.target)) {
          run(expression, proxy, element, event);
          refresh();
        }
      });
    });

    if (root.hasAttribute("@keydown.escape.window")) {
      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
          run(root.getAttribute("@keydown.escape.window"), proxy, root, event);
          refresh();
        }
      });
    }

    if (root.hasAttribute("x-init")) {
      run(root.getAttribute("x-init"), proxy, root);
    }
    if (typeof proxy.init === "function") {
      proxy.init.call(proxy);
    }
    refresh();

    root.removeAttribute("x-cloak");
    root.querySelectorAll("[x-cloak]").forEach(function (element) {
      element.removeAttribute("x-cloak");
    });
  }

  ready(function () {
    document.querySelectorAll("[x-data]").forEach(function (root) {
      try {
        bind(root, parseState(root.getAttribute("x-data") || "{}"));
      } catch (error) {
        console.error("Alpine-lite initialization failed", error);
      }
    });
  });
})();
