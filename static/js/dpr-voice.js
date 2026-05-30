let mediaRecorder = null;
let audioChunks = [];
let activeField = null;
let activeMicBtn = null;
let isRecording = false;

const defaultPlaceholders = {
  progress_notes: "Describe today's site progress...",
  issues: "List any delays, constraints, or incidents...",
};

function getDprToast() {
  return window.showToast || function fallbackToast(message) { alert(message); };
}

async function startVoiceInput(fieldId, btnId) {
  if (isRecording) {
    stopRecording();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    activeField = document.getElementById(fieldId);
    activeMicBtn = document.getElementById(btnId);
    if (!activeField || !activeMicBtn) return;

    activeMicBtn.style.background = "#dc3545";
    activeMicBtn.innerHTML = '<i class="fa fa-stop" style="font-size:12px;"></i>';
    showRecordingIndicator(fieldId);

    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) audioChunks.push(event.data);
    };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      hideRecordingIndicator(fieldId);
      activeMicBtn.style.background = "#F59E0B";
      activeMicBtn.innerHTML = '<span class="spinner-border spinner-border-sm" style="width:14px;height:14px;"></span>';
      await transcribeAudio(fieldId);
      activeMicBtn.style.background = "#0B3C5D";
      activeMicBtn.innerHTML = '<i class="fa fa-microphone" style="font-size:14px;"></i>';
    };

    mediaRecorder.start();
    isRecording = true;
    window.setTimeout(() => {
      if (isRecording) stopRecording();
    }, 120000);
  } catch (err) {
    if (err.name === "NotAllowedError") {
      getDprToast()("Microphone access denied. Please allow microphone in browser.", "error");
    } else {
      getDprToast()("Could not access microphone.", "error");
    }
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
  }
}

function showRecordingIndicator(fieldId) {
  const field = document.getElementById(fieldId);
  if (!field) return;
  field.style.borderColor = "#dc3545";
  field.style.boxShadow = "0 0 0 3px rgba(220,53,69,0.15)";
  field.placeholder = "Recording... click stop when done";
}

function hideRecordingIndicator(fieldId) {
  const field = document.getElementById(fieldId);
  if (!field) return;
  field.style.borderColor = "";
  field.style.boxShadow = "";
  field.placeholder = "Transcribing your voice...";
}

async function transcribeAudio(fieldId) {
  const blob = new Blob(audioChunks, { type: "audio/webm" });
  const formData = new FormData();
  formData.append("audio", blob, "recording.webm");
  formData.append("field", fieldId);

  try {
    const response = await fetch("/api/dpr/transcribe-voice", { method: "POST", body: formData });
    const data = await response.json();
    if (data.success) {
      const field = document.getElementById(fieldId);
      if (!field) return;
      const existing = field.value.trim();
      field.value = existing ? `${existing}\n${data.text}` : data.text;
      field.placeholder = defaultPlaceholders[fieldId] || "";
      getDprToast()("Voice transcribed successfully!", "success");
      if (data.language) getDprToast()(`Detected: ${data.language}`, "info");
      field.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      getDprToast()(data.error || "Transcription failed", "error");
      const field = document.getElementById(fieldId);
      if (field) field.placeholder = "Transcription failed - try again";
    }
  } catch (_err) {
    getDprToast()("Upload failed. Try again.", "error");
  }
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && isRecording) stopRecording();
});

window.startVoiceInput = startVoiceInput;
window.stopRecording = stopRecording;
