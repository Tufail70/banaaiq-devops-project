(function () {
  const card = document.getElementById("project-health-card");
  if (!card) return;

  const healthUrl = card.dataset.healthUrl;
  const recalculateUrl = card.dataset.recalculateUrl;
  const recalculateBtn = document.getElementById("recalculate-health-btn");
  const circumference = 283;
  const colors = {
    green: "#28a745",
    amber: "#ffc107",
    red: "#dc3545",
  };

  function clampScore(value) {
    const score = Number(value);
    if (!Number.isFinite(score)) return 100;
    return Math.max(0, Math.min(100, Math.round(score)));
  }

  function normalizeStatus(status) {
    return ["green", "amber", "red"].includes(status) ? status : "green";
  }

  function formatLastCalculated(value) {
    if (!value) return "Last calculated not yet";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "Last calculated just now";
    return `Last calculated ${parsed.toLocaleString([], {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }

  function updateHealthCard(data) {
    if (!data) return;
    const score = clampScore(data.score);
    const status = normalizeStatus(data.status);
    const color = colors[status];
    const circle = card.querySelector("[data-health-score-root]");
    const arc = card.querySelector("[data-health-arc]");
    const text = card.querySelector("[data-health-score-value]");
    const summary = card.querySelector("[data-health-summary]");
    const last = card.querySelector("[data-health-last]");

    if (circle) {
      circle.classList.remove("health-green", "health-amber", "health-red");
      circle.classList.add(`health-${status}`);
    }
    if (arc) {
      arc.setAttribute("stroke", color);
      arc.setAttribute("stroke-dashoffset", (circumference - ((score / 100) * circumference)).toFixed(2));
    }
    if (text) {
      text.textContent = score;
      text.setAttribute("fill", color);
    }
    if (summary) {
      summary.textContent = data.summary || "All systems healthy.";
    }
    if (last) {
      last.textContent = formatLastCalculated(data.last_calculated);
    }

    const components = data.components || {};
    Object.keys(components).forEach((key) => {
      const node = card.querySelector(`[data-health-component="${key}"]`);
      if (node) node.textContent = components[key];
    });
  }

  async function refreshHealth() {
    if (!healthUrl) return;
    try {
      const response = await fetch(healthUrl);
      const data = await response.json();
      if (response.ok) updateHealthCard(data);
    } catch (_error) {
      // The next poll will try again.
    }
  }

  async function recalculateHealth() {
    if (!recalculateUrl || !recalculateBtn) return;
    const original = recalculateBtn.innerHTML;
    recalculateBtn.disabled = true;
    recalculateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Recalculating';
    try {
      const response = await fetch(recalculateUrl, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Health recalculation failed");
      updateHealthCard(data);
      if (window.showToast) window.showToast("Project health recalculated", "success");
    } catch (error) {
      if (window.showToast) window.showToast(error.message || "Health recalculation failed", "error");
    } finally {
      recalculateBtn.disabled = false;
      recalculateBtn.innerHTML = original;
    }
  }

  recalculateBtn?.addEventListener("click", recalculateHealth);
  refreshHealth();
  window.setInterval(refreshHealth, 60000);
})();
