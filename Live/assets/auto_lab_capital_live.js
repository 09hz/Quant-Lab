/*
v22.2.6.1 AI Auto Lab capital panel safe browser updater

Research/simulation only. This script only updates display text.
It does not place orders, connect to brokers, or change backend run parameters.

This version uses event delegation and one-shot startup timers only.
*/
(function () {
  "use strict";

  const IDS = {
    initial: "main-autolab-initial-cash",
    target: "main-autolab-target-cash",
    exposure: "main-autolab-cash-exposure",
    sizing: "main-autolab-sizing-mode",
    summary: "main-autolab-capital-summary"
  };

  let lastHtml = "";

  function byId(id) {
    return document.getElementById(id);
  }

  function parseNumber(id, fallback) {
    const el = byId(id);
    if (!el) return fallback;

    let raw = "";
    if (typeof el.value !== "undefined") {
      raw = String(el.value);
    } else {
      raw = String(el.textContent || "");
    }

    raw = raw.replace(/[$,%\s,]/g, "");
    const n = parseFloat(raw);
    return Number.isFinite(n) ? n : fallback;
  }

  function money(value) {
    return "$" + Number(value).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (ch) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      }[ch];
    });
  }

  function readSizingMode() {
    const root = byId(IDS.sizing);
    if (!root) return "percent_cash_exposure";

    const hiddenInput = root.querySelector("input");
    if (hiddenInput && hiddenInput.value) return hiddenInput.value;

    const label = root.querySelector(".Select-value-label");
    if (label && label.textContent.trim()) {
      const txt = label.textContent.trim();
      if (/fixed/i.test(txt)) return "fixed_quantity";
      if (/affordable/i.test(txt)) return "max_affordable_shares";
      if (/percent/i.test(txt)) return "percent_cash_exposure";
      return txt;
    }

    const text = (root.textContent || "").trim();
    if (/fixed/i.test(text)) return "fixed_quantity";
    if (/affordable/i.test(text)) return "max_affordable_shares";
    if (/percent/i.test(text)) return "percent_cash_exposure";
    return "percent_cash_exposure";
  }

  function computeHtml() {
    const initial = Math.max(1, parseNumber(IDS.initial, 12000));
    const target = Math.max(1, parseNumber(IDS.target, 24000));
    const exposure = Math.min(100, Math.max(1, parseNumber(IDS.exposure, 95)));
    const sizing = readSizingMode();
    const targetReturn = initial > 0 ? ((target / initial) - 1.0) * 100.0 : 0.0;

    return [
      "<h4>Simulated capital assumptions</h4>",
      "<ul>",
      "<li>Starting cash: <code>" + money(initial) + "</code></li>",
      "<li>Target cash: <code>" + money(target) + "</code></li>",
      "<li>Target return needed: <code>" + targetReturn.toFixed(2) + "%</code></li>",
      "<li>Cash exposure: <code>" + exposure.toFixed(2) + "%</code></li>",
      "<li>Sizing mode: <code>" + escapeHtml(sizing) + "</code></li>",
      "</ul>",
      "<strong>Research/simulation only. These are not real account balances.</strong>"
    ].join("");
  }

  function render() {
    const summary = byId(IDS.summary);
    if (!summary) return false;

    const nextHtml = computeHtml();

    if (nextHtml !== lastHtml && summary.innerHTML !== nextHtml) {
      summary.innerHTML = nextHtml;
      lastHtml = nextHtml;
    }

    return true;
  }

  function scheduleRender() {
    window.requestAnimationFrame(function () {
      render();
      window.setTimeout(render, 75);
      window.setTimeout(render, 250);
    });
  }

  function eventLooksRelevant(event) {
    const target = event.target;
    if (!target) return false;

    const id = target.id || "";
    if (
      id === IDS.initial ||
      id === IDS.target ||
      id === IDS.exposure ||
      id === IDS.sizing
    ) {
      return true;
    }

    const closest = target.closest ? target.closest("#" + IDS.sizing) : null;
    return Boolean(closest);
  }

  function start() {
    ["input", "change", "keyup", "blur", "click"].forEach(function (eventName) {
      document.addEventListener(
        eventName,
        function (event) {
          if (eventLooksRelevant(event) || eventName === "click") {
            scheduleRender();
          }
        },
        true
      );
    });

    [0, 100, 300, 700, 1200, 2000].forEach(function (ms) {
      window.setTimeout(render, ms);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }

  window.autolabCapitalSummaryRender = render;
})();
