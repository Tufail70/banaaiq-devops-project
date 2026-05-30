let primaryLang = null
let outputLang = null
let isSetupDone = false
let selectedAudioFile = null
let processingInterval = null

function showToast(message, type) {
  const klass = type === "error" ? "danger" : (type === "warning" ? "warning" : (type || "success"))
  let c = document.getElementById("translator-toast-wrap")
  if (!c) {
    c = document.createElement("div")
    c.id = "translator-toast-wrap"
    c.className = "toast-container position-fixed top-0 end-0 p-3"
    c.style.zIndex = "2200"
    document.body.appendChild(c)
  }
  const t = document.createElement("div")
  t.className = `toast align-items-center text-bg-${klass} border-0`
  t.innerHTML = `<div class="d-flex"><div class="toast-body">${escapeHtml(message)}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`
  c.appendChild(t)
  const bs = new bootstrap.Toast(t, { delay: 2200 })
  bs.show()
  t.addEventListener("hidden.bs.toast", () => t.remove())
}

function selectPrimaryLang(lang) {
  primaryLang = lang
  document.querySelectorAll(".lang-card").forEach((c) => c.classList.remove("selected"))
  document.querySelector(`.lang-card[data-lang="${lang}"]`)?.classList.add("selected")
  outputLang = lang === "English" ? "Arabic" : "English"
  const out = document.getElementById("output-lang-select")
  if (out) out.value = outputLang
  updateTextareaPlaceholder()
  checkSetupComplete()
}

function onOutputLangChange() {
  outputLang = document.getElementById("output-lang-select")?.value || null
  checkSetupComplete()
}

function checkSetupComplete() {
  isSetupDone = primaryLang !== null && outputLang !== null
  const hasAudio = selectedAudioFile !== null
  const hasText = (document.getElementById("text-input")?.value.trim().length || 0) > 2
  const v = document.getElementById("btn-translate-voice")
  const t = document.getElementById("btn-translate-text")
  if (v) v.disabled = !(isSetupDone && hasAudio)
  if (t) t.disabled = !(isSetupDone && hasText)
  const ok = document.getElementById("setup-complete-indicator")
  if (ok) ok.style.display = isSetupDone ? "block" : "none"
}

function updateTextareaPlaceholder() {
  const textarea = document.getElementById("text-input")
  if (!textarea) return
  if (primaryLang === "Arabic") {
    textarea.placeholder = "الصق أو اكتب الرسالة للترجمة..."
    textarea.setAttribute("dir", "rtl")
  } else {
    textarea.placeholder = "Paste or type the message to translate..."
    textarea.setAttribute("dir", "ltr")
  }
}

function switchTab(tab) {
  document.getElementById("tab-voice").style.display = tab === "voice" ? "block" : "none"
  document.getElementById("tab-text").style.display = tab === "text" ? "block" : "none"
  document.querySelectorAll(".input-tab-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tab))
  hideResults()
}

function handleAudioFileSelect(event) {
  const file = event?.target?.files?.[0] || event
  if (!file) return
  const ext = file.name.split(".").pop().toLowerCase()
  const allowed = ["mp3", "wav", "m4a", "ogg", "webm", "mp4"]
  if (!allowed.includes(ext)) {
    showToast("Only audio files supported: MP3, WAV, M4A", "error")
    return
  }
  if (file.size > 25 * 1024 * 1024) {
    showToast("File too large. Maximum 25MB.", "error")
    return
  }
  selectedAudioFile = file
  document.getElementById("audio-drop-zone").style.display = "none"
  const infoCard = document.getElementById("audio-file-info")
  infoCard.style.display = "block"
  infoCard.querySelector(".audio-filename").textContent = file.name
  infoCard.querySelector(".audio-filesize").textContent = formatFileSize(file.size)
  const player = document.getElementById("audio-preview-player")
  player.src = URL.createObjectURL(file)
  player.style.display = "block"
  checkSetupComplete()
}

function removeAudioFile() {
  selectedAudioFile = null
  document.getElementById("audio-drop-zone").style.display = "block"
  document.getElementById("audio-file-info").style.display = "none"
  document.getElementById("audio-preview-player").style.display = "none"
  document.getElementById("audio-file-input").value = ""
  document.getElementById("btn-translate-voice").disabled = true
}

async function translateVoice() {
  if (!selectedAudioFile || !isSetupDone) return
  const btn = document.getElementById("btn-translate-voice")
  btn.disabled = true
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Processing...`
  hideResults()
  showProcessingSteps()
  const formData = new FormData()
  formData.append("audio", selectedAudioFile)
  formData.append("primary_lang", primaryLang)
  formData.append("output_lang", outputLang)
  try {
    const response = await fetch("/api/translator/voice", { method: "POST", body: formData })
    const data = await response.json()
    hideProcessingSteps()
    if (data.success) {
      displayResults(data)
      updateCallsCounter(data.calls_remaining, data.ai_limit, data.ai_unlimited)
      showToast("Voice message translated!", "success")
    } else {
      showToast(data.error || "Translation failed", "error")
    }
  } catch (_err) {
    hideProcessingSteps()
    showToast("Network error. Try again.", "error")
  } finally {
    btn.disabled = false
    btn.innerHTML = `<i class="fas fa-robot me-2"></i>Transcribe & Translate Voice`
  }
}

async function translateText() {
  const text = document.getElementById("text-input")?.value.trim()
  if (!text || !isSetupDone) return
  const btn = document.getElementById("btn-translate-text")
  btn.disabled = true
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Translating...`
  hideResults()
  try {
    const response = await fetch("/api/translator/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, primary_lang: primaryLang, output_lang: outputLang }),
    })
    const data = await response.json()
    if (data.success) {
      displayResults(data)
      updateCallsCounter(data.calls_remaining, data.ai_limit, data.ai_unlimited)
      showToast("Text translated!", "success")
    } else {
      showToast(data.error || "Translation failed", "error")
    }
  } catch (_err) {
    showToast("Network error. Try again.", "error")
  } finally {
    btn.disabled = false
    btn.innerHTML = `<i class="fas fa-language me-2"></i>Translate & Analyze`
  }
}

function displayResults(data) {
  document.getElementById("result-original-text").textContent = data.original_text || ""
  document.getElementById("detected-lang-badge").textContent = "Detected: " + (data.detected_language || "Unknown")
  document.getElementById("input-type-badge").textContent = data.input_type === "voice" ? "Voice input" : "Text input"
  document.getElementById("translated-to-badge").textContent = "Translated to: " + outputLang

  const translationBox = document.getElementById("result-translation")
  translationBox.textContent = data.translation || ""
  translationBox.setAttribute("dir", outputLang === "Arabic" ? "rtl" : "ltr")
  if (outputLang === "Arabic") {
    translationBox.style.fontFamily = "'Cairo', sans-serif"
    translationBox.style.fontSize = "1.05rem"
  } else {
    translationBox.style.fontFamily = ""
    translationBox.style.fontSize = ""
  }

  document.getElementById("result-summary").textContent = data.summary || ""
  const actionBox = document.getElementById("key-action-box")
  const actionText = (data.key_action || "").trim()
  if (actionText && actionText.toLowerCase() !== "none") {
    actionBox.style.display = "block"
    document.getElementById("key-action-text").textContent = actionText
  } else {
    actionBox.style.display = "none"
  }

  const repliesContainer = document.getElementById("replies-container")
  repliesContainer.innerHTML = ""
  const toneColors = { formal: "primary", brief: "secondary", clarification: "warning", general: "secondary" }
  ;(data.suggested_replies || []).forEach((reply) => {
    const kind = reply.type || reply.tone || "general"
    const color = toneColors[kind] || "secondary"
    const left = color === "primary" ? "#0B3C5D" : (color === "warning" ? "#fd7e14" : "#6c757d")
    const textEn = reply.text_en || ""
    const textAr = reply.text_ar || ""
    const enJson = JSON.stringify(textEn)
    const arJson = JSON.stringify(textAr)
    repliesContainer.innerHTML += `
      <div class="reply-card p-3 mb-2 border rounded" style="border-left:3px solid ${left} !important;">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <span class="badge bg-${color}">${reply.label || "Reply"}</span>
        </div>

        <div class="reply-english mb-2">
          <small class="text-muted">English</small>
          <p class="mb-1" dir="ltr">${escapeHtml(textEn)}</p>
          <button class="btn btn-sm btn-outline-secondary" onclick='copyReplyText(${enJson}, this)'>Copy EN</button>
        </div>

        <div class="reply-arabic mb-2" dir="rtl" style="font-family:'Cairo',sans-serif;">
          <small class="text-muted">Arabic</small>
          <p class="mb-1">${escapeHtml(textAr)}</p>
          <button class="btn btn-sm btn-outline-secondary" onclick='copyReplyText(${arJson}, this)'>Copy AR</button>
        </div>

        <button class="btn btn-sm btn-outline-primary" onclick='openEditModal(${enJson}, ${arJson})'>Edit &amp; Copy</button>
      </div>
    `
  })

  const panel = document.getElementById("results-panel")
  panel.style.display = "block"
  panel.scrollIntoView({ behavior: "smooth", block: "start" })
}

function showProcessingSteps() {
  const container = document.getElementById("processing-steps")
  container.style.display = "block"
  const steps = container.querySelectorAll(".proc-step")
  let current = 0
  processingInterval = setInterval(() => {
    if (current > 0 && current <= steps.length) {
      steps[current - 1].querySelector(".proc-spinner")?.classList.add("d-none")
      steps[current - 1].querySelector(".proc-check")?.classList.remove("d-none")
      steps[current - 1].style.color = "#28a745"
    }
    if (current < steps.length) {
      steps[current].querySelector(".proc-spinner")?.classList.remove("d-none")
    }
    current += 1
  }, 1600)
}

function hideProcessingSteps() {
  if (processingInterval) clearInterval(processingInterval)
  processingInterval = null
  document.getElementById("processing-steps").style.display = "none"
}

function copyReplyText(text, btn) {
  navigator.clipboard.writeText(text || "").then(() => {
    const original = btn.innerHTML
    btn.innerHTML = "Copied"
    btn.classList.add("btn-success")
    btn.classList.remove("btn-outline-secondary")
    setTimeout(() => {
      btn.innerHTML = original
      btn.classList.remove("btn-success")
      btn.classList.add("btn-outline-secondary")
    }, 1600)
  })
}

function openEditModal(textEn, textAr) {
  const en = document.getElementById("edit-reply-textarea-en")
  const ar = document.getElementById("edit-reply-textarea-ar")
  if (en) en.value = textEn || ""
  if (ar) ar.value = textAr || ""
  new bootstrap.Modal(document.getElementById("edit-reply-modal")).show()
}

function copyEditedReply(lang) {
  const id = lang === "ar" ? "edit-reply-textarea-ar" : "edit-reply-textarea-en"
  const text = document.getElementById(id)?.value || ""
  navigator.clipboard.writeText(text).then(() => showToast("Modified reply copied!", "success"))
}

function escapeHtml(value) {
  return (value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;")
}


function copyText(elementId) {
  const text = document.getElementById(elementId)?.textContent
  if (!text) return
  navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard!", "success"))
}

function copyPhrase(text) {
  navigator.clipboard.writeText(text).then(() => showToast("Phrase copied!", "success"))
}

function copyAllResults() {
  const original = document.getElementById("result-original-text")?.textContent || ""
  const translation = document.getElementById("result-translation")?.textContent || ""
  const summary = document.getElementById("result-summary")?.textContent || ""
  const keyAction = document.getElementById("key-action-text")?.textContent || ""
  const all = `Original:\n${original}\n\nTranslation:\n${translation}\n\nSummary:\n${summary}\n\nKey Action:\n${keyAction}`
  navigator.clipboard.writeText(all).then(() => showToast("All results copied!", "success"))
}

function hideResults() {
  document.getElementById("results-panel").style.display = "none"
}

function updateCallsCounter(remaining, limit, unlimited) {
  const counter = document.getElementById("ai-calls-counter")
  if (!counter) return
  if (unlimited || limit === null) {
    counter.textContent = "AI Queries: Unlimited"
    counter.style.color = ""
    return
  }
  if (!limit) {
    counter.textContent = "AI Queries: Start a free trial"
    counter.style.color = "#dc3545"
    return
  }
  const used = Math.max(Number(limit) - Number(remaining ?? limit), 0)
  counter.textContent = `AI Queries: ${used}/${limit}`
  if (remaining <= 5) counter.style.color = "#dc3545"
  else if (remaining <= 10) counter.style.color = "#fd7e14"
  else counter.style.color = ""
  if (remaining === 0) showToast("Monthly AI limit reached. Upgrade your plan for more queries.", "warning")
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B"
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
  return (bytes / (1024 * 1024)).toFixed(1) + " MB"
}

document.getElementById("text-input")?.addEventListener("input", function () {
  const count = this.value.length
  const counter = document.getElementById("char-counter")
  counter.textContent = count + " / 3000"
  counter.style.color = count > 2800 ? "#dc3545" : "#6c757d"
  checkSetupComplete()
})

document.getElementById("audio-file-input")?.addEventListener("change", handleAudioFileSelect)

const dropZone = document.getElementById("audio-drop-zone")
dropZone?.addEventListener("dragover", (e) => {
  e.preventDefault()
  dropZone.style.borderColor = "#0B3C5D"
  dropZone.style.background = "#f0f4ff"
})
dropZone?.addEventListener("dragleave", () => {
  dropZone.style.borderColor = "#F59E0B"
  dropZone.style.background = "#fafafa"
})
dropZone?.addEventListener("drop", (e) => {
  e.preventDefault()
  dropZone.style.borderColor = "#F59E0B"
  dropZone.style.background = "#fafafa"
  handleAudioFileSelect(e.dataTransfer.files[0])
})
dropZone?.addEventListener("click", () => document.getElementById("audio-file-input")?.click())

document.getElementById("phrase-search")?.addEventListener("keyup", function () {
  const search = this.value.toLowerCase()
  document.querySelectorAll("#phrase-table tbody tr").forEach((row) => {
    row.style.display = row.textContent.toLowerCase().includes(search) ? "" : "none"
  })
})

document.querySelectorAll(".category-badge").forEach((badge) => {
  badge.addEventListener("click", function () {
    document.querySelectorAll(".category-badge").forEach((b) => b.classList.remove("active"))
    this.classList.add("active")
    const cat = this.dataset.category
    document.querySelectorAll("#phrase-table tbody tr").forEach((row) => {
      row.style.display = cat === "All" || row.dataset.category === cat ? "" : "none"
    })
  })
})
