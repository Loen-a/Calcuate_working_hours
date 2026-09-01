"use strict";

(() => {
  const table = document.querySelector("#prediction-table");
  const toggle = document.querySelector("#toggle-other-days");

  if (table && toggle) {
    toggle.addEventListener("click", () => {
      const expanded = table.classList.toggle("show-all");
      toggle.setAttribute("aria-expanded", String(expanded));
      toggle.textContent = expanded ? "收起其他工作日" : "显示其他工作日";
    });
  }

  const focus = document.querySelector("#selected-forecast");
  const previewUrl = focus?.dataset.previewUrl;
  if (!previewUrl) {
    return;
  }

  const timers = new WeakMap();
  const controllers = new WeakMap();

  const selectedElements = {
    balance: document.querySelector("#selected-balance"),
    copy: document.querySelector("#selected-preview-copy"),
    reason: document.querySelector("#selected-reason"),
    required: document.querySelector("#selected-required"),
    status: document.querySelector("#selected-preview-status"),
  };

  function setSelectedEmpty() {
    selectedElements.status.textContent = "等待上班时间";
    selectedElements.copy.textContent = "填写上班时间，即可看到当天最早下班时间。";
  }

  function setSelectedUnavailable() {
    selectedElements.status.textContent = "非工作日";
    selectedElements.copy.textContent = "当前日期不是工作日；可在高级设置中添加调休上班标记。";
    selectedElements.balance.textContent = "-";
    selectedElements.required.textContent = "-";
    selectedElements.reason.textContent = "-";
  }

  function setSelectedPreview(data) {
    selectedElements.status.textContent = "即时预览";
    selectedElements.copy.textContent = `按 ${data.required_label}有效工时计算，已计入启用的非工作时间。`;
    selectedElements.balance.textContent = data.balance_label;
    selectedElements.required.textContent = data.required_label;
    selectedElements.reason.textContent = data.reason_label;
  }

  async function refreshPreview(input) {
    const target = document.getElementById(input.dataset.previewTarget);
    if (!target) {
      return;
    }

    const selectedScope = input.dataset.previewScope === "selected";
    const startTime = input.value;
    if (!startTime) {
      target.textContent = selectedScope ? "--:--" : "-";
      if (selectedScope) {
        setSelectedEmpty();
      }
      return;
    }

    controllers.get(input)?.abort();
    const controller = new AbortController();
    controllers.set(input, controller);

    const url = new URL(previewUrl, window.location.href);
    url.searchParams.set("work_date", input.dataset.workDate);
    url.searchParams.set("start_time", startTime);
    target.setAttribute("aria-busy", "true");

    try {
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error("Preview request failed");
      }

      const data = await response.json();
      if (!data.available) {
        target.textContent = selectedScope ? "--:--" : "-";
        if (selectedScope) {
          setSelectedUnavailable();
        }
        return;
      }

      target.textContent = data.suggested_end_label;
      if (selectedScope) {
        setSelectedPreview(data);
      }
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      target.textContent = selectedScope ? "--:--" : "-";
      if (selectedScope) {
        selectedElements.status.textContent = "预览暂不可用";
        selectedElements.copy.textContent = "可直接保存记录，页面会按同一规则重新计算。";
      }
    } finally {
      if (controllers.get(input) === controller) {
        target.removeAttribute("aria-busy");
      }
    }
  }

  document.querySelectorAll("[data-preview-start]").forEach((input) => {
    input.addEventListener("input", () => {
      window.clearTimeout(timers.get(input));
      timers.set(input, window.setTimeout(() => refreshPreview(input), 160));
    });
    input.addEventListener("change", () => {
      window.clearTimeout(timers.get(input));
      refreshPreview(input);
    });
  });
})();
