const form = document.querySelector("#translate-form");
const startButton = document.querySelector("#start-button");
const resetButton = document.querySelector("#reset-button");
const formMessage = document.querySelector("#form-message");
const emptyState = document.querySelector("#empty-state");
const progressPanel = document.querySelector("#progress-panel");
const statusTitle = document.querySelector("#status-title");
const statusPill = document.querySelector("#status-pill");
const progressFill = document.querySelector("#progress-fill");
const progressCopy = document.querySelector("#progress-copy");
const translationIdEl = document.querySelector("#translation-id");
const workDirEl = document.querySelector("#work-dir");
const logsOutput = document.querySelector("#logs-output");
const refreshLogsButton = document.querySelector("#refresh-logs");
const dropZone = document.querySelector("#drop-zone");
const videoFileInput = document.querySelector("#video-file");
const fileNameEl = document.querySelector("#file-name");

const STORAGE_KEY = "autoTranslateVideo.preferences";
let pollTimer = null;
let currentTranslationId = null;
let selectedVideoFile = null;

const friendlyCopy = {
  queued: "Đã nhận tác vụ, đang xếp hàng xử lý...",
  running: "Đang xử lý video. Tiến trình sẽ cập nhật theo từng bước.",
  translate_pending: "Đã bóc băng xong. Bạn cần tạo file dịch hoặc thêm GOOGLE_API_KEY rồi resume.",
  succeeded: "Xong rồi. Video/audio đã được xuất vào work dir.",
  failed: "Có lỗi rồi. Log bên dưới đã rút gọn để bạn thấy lỗi nằm ở bước nào."
};

function loadPreferences() {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  for (const [name, value] of Object.entries(saved)) {
    const input = form.elements[name];
    if (input && value) input.value = value;
  }
}

function savePreferences() {
  const data = Object.fromEntries(new FormData(form).entries());
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    targetLanguage: data.targetLanguage,
    sourceLang: data.sourceLang,
    bgmMode: data.bgmMode,
    targetVoice: data.targetVoice
  }));
}

function setMessage(message, isError = false) {
  formMessage.textContent = message;
  formMessage.classList.toggle("error", isError);
}

function setSelectedFile(file) {
  selectedVideoFile = file || null;
  fileNameEl.textContent = selectedVideoFile
    ? `${selectedVideoFile.name} (${formatFileSize(selectedVideoFile.size)})`
    : "Hỗ trợ mp4, mov, mkv, webm...";
  dropZone.classList.toggle("has-file", Boolean(selectedVideoFile));
}

function formatFileSize(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function buildJsonPayload() {
  const data = Object.fromEntries(new FormData(form).entries());
  const payload = {
    target_language: data.targetLanguage,
    source_lang: data.sourceLang,
    bgm_mode: data.bgmMode,
    target_voice: data.targetVoice,
    skip_video: false
  };

  if (data.videoUrl.trim()) payload.video_url = data.videoUrl.trim();
  if (data.resumeDir.trim()) payload.resume_dir = data.resumeDir.trim();
  return payload;
}

function buildUploadUrl() {
  const data = Object.fromEntries(new FormData(form).entries());
  const params = new URLSearchParams({
    filename: selectedVideoFile.name,
    target_language: data.targetLanguage,
    source_lang: data.sourceLang,
    bgm_mode: data.bgmMode,
    target_voice: data.targetVoice,
    skip_video: "false"
  });

  if (data.resumeDir.trim()) params.set("resume_dir", data.resumeDir.trim());
  return `/api/translate/upload?${params.toString()}`;
}

async function startTranslation(event) {
  event.preventDefault();
  savePreferences();

  const payload = buildJsonPayload();
  if (!payload.video_url && !payload.resume_dir && !selectedVideoFile) {
    setMessage("Bạn cần dán link video, thả file video hoặc điền resume folder trước nhé.", true);
    return;
  }

  startButton.disabled = true;
  setMessage(selectedVideoFile ? "Đang upload video và đưa tác vụ vào hàng chờ..." : "Đang gửi tác vụ vào hàng chờ...");

  try {
    const translation = selectedVideoFile
      ? await startUploadTranslation()
      : await startJsonTranslation(payload);

    currentTranslationId = translation.translation_id;
    showProgress();
    updateProgress(translation);
    setMessage("Đã bắt đầu xử lý. Bạn theo dõi tiến trình bên phải nhé.");
    startPolling();
  } catch (error) {
    setMessage(`Chưa gửi được tác vụ: ${error.message}`, true);
  } finally {
    startButton.disabled = false;
  }
}

async function startJsonTranslation(payload) {
  const response = await fetch("/api/translate", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(await readError(response) || "API chưa nhận tác vụ được.");
  return response.json();
}

async function startUploadTranslation() {
  const response = await fetch(buildUploadUrl(), {
    method: "POST",
    headers: {"Content-Type": selectedVideoFile.type || "application/octet-stream"},
    body: selectedVideoFile
  });
  if (!response.ok) throw new Error(await readError(response) || "Upload video chưa thành công.");
  return response.json();
}

async function readError(response) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    return JSON.stringify(data.detail || data);
  } catch {
    return response.statusText;
  }
}

function showProgress() {
  emptyState.classList.add("hidden");
  progressPanel.classList.remove("hidden");
}

function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(fetchStatus, 2500);
  fetchLogs();
}

async function fetchStatus() {
  if (!currentTranslationId) return;
  try {
    const response = await fetch(`/api/translate/${currentTranslationId}`);
    if (!response.ok) throw new Error("Không đọc được tiến trình.");
    const translation = await response.json();
    updateProgress(translation);
    if (["succeeded", "failed", "translate_pending"].includes(translation.status)) {
      clearInterval(pollTimer);
    }
    fetchLogs();
  } catch (error) {
    setMessage(`Tạm thời chưa cập nhật được tiến trình: ${error.message}`, true);
  }
}

async function fetchLogs() {
  if (!currentTranslationId) return;
  try {
    const response = await fetch(`/api/translate/${currentTranslationId}/logs?tail=40`);
    if (!response.ok) return;
    const data = await response.json();
    logsOutput.textContent = data.logs.length ? data.logs.join("\n") : "Chưa có log.";
    logsOutput.scrollTop = logsOutput.scrollHeight;
  } catch {
    logsOutput.textContent = "Chưa tải được log, thử lại sau một nhịp nhé.";
  }
}

function updateProgress(translation) {
  const status = translation.status || "queued";
  const percent = Math.max(0, Math.min(100, translation.progress_percent || 0));
  const step = translation.current_step || "Đang chuẩn bị...";

  statusTitle.textContent = step;
  statusPill.textContent = status;
  statusPill.className = `status-pill ${status}`;
  progressFill.style.width = `${percent}%`;
  progressCopy.textContent = buildProgressCopy(translation);
  translationIdEl.textContent = translation.translation_id || "-";
  workDirEl.textContent = translation.work_dir || "-";

  if (translation.error) {
    setMessage(`Tác vụ lỗi ở ${translation.failed_step || "một bước chưa rõ"}: ${translation.error}`, true);
  }
}

function buildProgressCopy(translation) {
  const step = translation.current_step || "";
  if (translation.status === "running" && step) {
    if (step.includes("Bước 1")) return "Đang lấy video hoặc đọc file upload.";
    if (step.includes("Bước 2.5")) return "Đang xử lý nhạc nền và vocal.";
    if (step.includes("Bước 3")) return "Đang bóc băng bằng Azure Speech.";
    if (step.includes("Bước 4")) return "Đang dịch transcript bằng Gemini hoặc kiểm tra file dịch.";
    if (step.includes("Bước 5")) return "Đang tạo giọng đọc, bước này có thể lâu hơn một chút.";
    if (step.includes("Bước 6")) return "Đang khớp timeline và mix âm thanh.";
    if (step.includes("Bước 7")) return "Đang ghép audio vào video.";
  }
  return friendlyCopy[translation.status] || "Đang cập nhật tiến trình...";
}

function resetUi() {
  clearInterval(pollTimer);
  currentTranslationId = null;
  form.reset();
  setSelectedFile(null);
  loadPreferences();
  progressPanel.classList.add("hidden");
  emptyState.classList.remove("hidden");
  logsOutput.textContent = "Chưa có log.";
  setMessage("");
}

videoFileInput.addEventListener("change", () => {
  setSelectedFile(videoFileInput.files[0]);
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragging");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("is-dragging");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
  const file = event.dataTransfer.files[0];
  if (file) {
    videoFileInput.files = event.dataTransfer.files;
    setSelectedFile(file);
  }
});

form.addEventListener("submit", startTranslation);
resetButton.addEventListener("click", resetUi);
refreshLogsButton.addEventListener("click", fetchLogs);
form.addEventListener("change", savePreferences);

loadPreferences();
