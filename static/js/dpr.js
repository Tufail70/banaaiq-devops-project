(function () {
  const form = document.getElementById("dpr-form");
  if (!form) return;

  const reportDate = document.getElementById("reportDate");
  const project = document.getElementById("project");
  const zone = document.getElementById("zone");
  const weather = document.getElementById("weather");
  const notes = document.getElementById("progress_notes");
  const issues = document.getElementById("issues");
  const workerTableBody = document.getElementById("workers-tbody");
  const photos = document.getElementById("photos");
  const imagePreviewGrid = document.getElementById("imagePreviewGrid");
  const generateAiBtn = document.getElementById("generateAiBtn");
  const aiSummaryPanel = document.getElementById("aiSummaryPanel");
  const aiSummaryField = document.getElementById("aiSummaryField");
  const saveDraftBtn = document.getElementById("saveDraftBtn");
  const saveAsDraftField = document.getElementById("saveAsDraftField");

  const i18n = {
    analyzing: "BanaaIQ AI is analyzing your report...",
    summaryFailed: "AI summary failed.",
    serviceUnavailable: "AI service temporarily unavailable.",
    emptyHint: "Fill in the form and click Generate AI Summary",
  };

  function toast(message, level) {
    if (window.showToast) {
      window.showToast(message, level === "danger" ? "error" : level);
      return;
    }
    alert(message);
  }

  if (!reportDate.value) {
    reportDate.value = new Date().toISOString().slice(0, 10);
  }

  function truncateText(text, maxLength = 150) {
    if (!text) return "-";
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
  }

  function escapeAttribute(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function workerCount() {
    const rows = workerTableBody.querySelectorAll("tr");
    let count = 0;
    rows.forEach((row) => {
      const name = row.querySelector('input[name="worker_name[]"]');
      const present = row.querySelector('input[name="worker_present[]"]');
      if (name && name.value.trim() && present && present.checked) count += 1;
    });
    return count;
  }

  function syncWorkerPresentState(row) {
    const checkbox = row?.querySelector('input[name="worker_present[]"]');
    const hidden = row?.querySelector('input[name="worker_present_state[]"]');
    if (!checkbox || !hidden) return;
    hidden.value = checkbox.checked ? "1" : "0";
  }

  function updatePreview() {
    document.getElementById("previewDate").textContent = reportDate.value || "-";
    document.getElementById("previewProject").textContent = project.value || "-";
    document.getElementById("previewZone").textContent = zone.value || "-";
    document.getElementById("previewWeather").textContent = weather.value || "-";
    document.getElementById("previewWorkerCount").textContent = workerCount();
    document.getElementById("previewNotes").textContent = truncateText(notes.value);
    document.getElementById("previewIssues").textContent = truncateText(issues.value, 120);
  }

  window.addWorkerRowWithData = function addWorkerRowWithData(name = "", role = "", hours = 8, present = true) {
    const tr = document.createElement("tr");
    const safeName = escapeAttribute(name);
    const safeRole = escapeAttribute(role);
    const safeHours = Number.isFinite(Number(hours)) ? Number(hours) : 8;
    tr.innerHTML = `
      <td><input type="text" name="worker_name[]" class="form-control form-control-sm" value="${safeName}" placeholder="Worker name"></td>
      <td><input type="text" name="worker_role[]" class="form-control form-control-sm" value="${safeRole}" placeholder="Role"></td>
      <td><input type="number" name="worker_hours[]" class="form-control form-control-sm" value="${safeHours}" min="0" max="24" step="0.5"></td>
      <td class="text-center">
        <input type="hidden" name="worker_present_state[]" value="${present ? "1" : "0"}">
        <input type="checkbox" name="worker_present[]" value="1" class="worker-present" ${present ? "checked" : ""}>
      </td>
      <td><button type="button" class="btn btn-sm btn-outline-danger remove-worker" style="padding:2px 8px;"><i class="fa fa-times"></i></button></td>`;
    workerTableBody.appendChild(tr);
    syncWorkerPresentState(tr);
    updatePreview();
  };

  window.addWorkerRow = function addWorkerRow() {
    window.addWorkerRowWithData("", "", 8, true);
  };

  workerTableBody.addEventListener("click", (event) => {
    const button = event.target.closest(".remove-worker");
    if (!button) return;
    button.closest("tr")?.remove();
    updatePreview();
  });

  workerTableBody.addEventListener("change", (event) => {
    if (event.target.matches('input[name="worker_present[]"]')) {
      syncWorkerPresentState(event.target.closest("tr"));
      updatePreview();
    }
  });

  photos.addEventListener("change", () => {
    imagePreviewGrid.innerHTML = "";
    const selected = Array.from(photos.files || []).slice(0, 10);
    selected.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (loadEvent) => {
        const img = document.createElement("img");
        img.src = loadEvent.target.result;
        img.width = 72;
        img.height = 72;
        img.style.objectFit = "cover";
        img.className = "rounded border";
        imagePreviewGrid.appendChild(img);
      };
      reader.readAsDataURL(file);
    });
    document.getElementById("previewImageCount").textContent = selected.length;
  });

  async function generateAISummary() {
    const payload = {
      date: reportDate.value,
      project: project.value,
      zone: zone.value,
      weather: weather.value,
      notes: notes.value,
      issues: issues.value,
      worker_count: workerCount(),
    };
    const original = generateAiBtn.innerHTML;
    generateAiBtn.disabled = true;
    generateAiBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${i18n.analyzing}`;
    aiSummaryPanel.className = "small text-muted mb-2";
    aiSummaryPanel.textContent = i18n.analyzing;
    try {
      const res = await fetch("/api/dpr/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        aiSummaryField.value = data.summary;
        aiSummaryPanel.className = "small mb-2";
        aiSummaryPanel.textContent = data.summary;
      } else {
        aiSummaryPanel.className = "small text-danger mb-2";
        aiSummaryPanel.textContent = data.error || i18n.summaryFailed;
        toast(data.error || i18n.summaryFailed, "error");
      }
    } catch (_err) {
      aiSummaryPanel.className = "small text-danger mb-2";
      aiSummaryPanel.textContent = i18n.serviceUnavailable;
      toast(i18n.serviceUnavailable, "error");
    } finally {
      generateAiBtn.disabled = false;
      generateAiBtn.innerHTML = original;
    }
  }

  window.submitDPR = async function submitDPR() {
    const btn = document.getElementById("submitDprBtn");
    const formData = new FormData(form);
    const editId = document.getElementById("edit-dpr-id")?.value;
    const url = editId ? `/dashboard/dpr/${editId}/update` : form.action;
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
    try {
      const response = await fetch(url, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json();
	      if (data.success) {
	        toast(editId ? "DPR updated successfully!" : "DPR saved successfully!", "success");
	        if (data.boq_tracker_updated && data.boq_tracker_message) {
	          sessionStorage.setItem("boq_tracker_notice", data.boq_tracker_message);
	        }
	        window.setTimeout(() => { window.location.href = `/dashboard/dpr/${data.id}`; }, 900);
	      } else {
        toast(data.error || "Save failed", "error");
      }
    } catch (_err) {
      toast("Network error", "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = original;
      saveAsDraftField.value = "0";
    }
  };

  saveDraftBtn.addEventListener("click", async () => {
    saveAsDraftField.value = "1";
    await window.submitDPR();
  });

  form.addEventListener("submit", () => {
    if (!saveAsDraftField.value) saveAsDraftField.value = "0";
  });

  window.importWorkerExcel = async function importWorkerExcel(file) {
    if (!file) return;
    const status = document.getElementById("worker-import-status");
    if (status) status.style.display = "block";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/dpr/import-workers", { method: "POST", body: formData });
      const data = await response.json();
      if (data.success) {
        workerTableBody.innerHTML = "";
        data.workers.forEach((worker) => {
          window.addWorkerRowWithData(worker.name, worker.role, worker.hours, worker.present);
        });
        toast(`${data.count} workers imported!`, "success");
      } else {
        toast(data.error || "Import failed", "error");
      }
    } catch (_err) {
      toast("Upload failed. Try again.", "error");
    } finally {
      if (status) status.style.display = "none";
      const input = document.getElementById("worker-excel-input");
      if (input) input.value = "";
    }
  };

  ["input", "change", "keyup"].forEach((eventName) => {
    form.addEventListener(eventName, updatePreview);
  });

  generateAiBtn.addEventListener("click", generateAISummary);
  workerTableBody.querySelectorAll("tr").forEach(syncWorkerPresentState);
  updatePreview();
})();
