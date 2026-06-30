const body = document.body;
const mainContainer = document.querySelector("#main-container");
const form = document.querySelector("#translate-form");
const startButton = document.querySelector("#start-button");
const exportButton = document.querySelector("#export-button");
const formMessage = document.querySelector("#form-message");
const progressPanel = document.querySelector("#progress-panel");
const statusTitle = document.querySelector("#status-title");
const statusPill = document.querySelector("#status-pill");
const systemState = document.querySelector("#system-state");
const progressFill = document.querySelector("#progress-fill");
const progressText = document.querySelector("#progress-text");
const progressCopy = document.querySelector("#progress-copy");
const stepIndicator = document.querySelector("#step-indicator");
const translationIdEl = document.querySelector("#translation-id");
const workDirEl = document.querySelector("#work-dir");
const logsOutput = document.querySelector("#logs-output");
const refreshLogsButton = document.querySelector("#refresh-logs");
const dropZone = document.querySelector("#drop-zone");
const videoFileInput = document.querySelector("#video-file");
const fileNameEl = document.querySelector("#file-name");
const themeToggle = document.querySelector("#theme-toggle");
const subtitleList = document.querySelector("#subtitle-list");
const previewVideo = document.querySelector("#preview-video");
const previewSubtitle = document.querySelector("#preview-subtitle");
const blurBox = document.querySelector("#blur-box");
const videoBg = document.querySelector("#video-bg");
const resizeHandle = document.querySelector("#resize-handle");
const previewBoxText = document.querySelector("#preview-box-text");
const stylePanel = document.querySelector("#panel-style-presets");
const overlayPanel = document.querySelector("#panel-overlay-presets");

const STORAGE_KEY = "autoTranslateVideo.preferences";
let pollTimer = null;
let currentTranslationId = null;
let selectedVideoFile = null;
let previewObjectUrl = null;
let selectedSubStyle = "white";
let selectedOverlayType = "default";
let isDraggingMask = false;
let isResizingMask = false;
let startY = 0;
let startTop = 0;
let startHeight = 0;

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
  if (saved.theme === "dark") {
    body.classList.add("dark");
    themeToggle.textContent = "Chế độ sáng";
  }
}

function savePreferences() {
  const data = Object.fromEntries(new FormData(form).entries());
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    targetLanguage: data.targetLanguage,
    sourceLang: data.sourceLang,
    bgmMode: data.bgmMode,
    targetVoice: data.targetVoice,
    theme: body.classList.contains("dark") ? "dark" : "light"
  }));
}

function setMessage(message, isError = false) {
  formMessage.textContent = message;
  formMessage.classList.toggle("error", isError);
}

function setSystemState(status) {
  const labelMap = {
    queued: "Đang chờ",
    running: "Đang chạy",
    translate_pending: "Chờ dịch",
    succeeded: "Hoàn tất",
    failed: "Bị lỗi",
    idle: "Chờ cấu hình"
  };
  systemState.textContent = labelMap[status] || "Chờ cấu hình";
  systemState.className = `state-pill ${status || "waiting"}`;
}

function setSelectedFile(file) {
  selectedVideoFile = file || null;
  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = null;
  }
  fileNameEl.textContent = selectedVideoFile
    ? `${selectedVideoFile.name} (${formatFileSize(selectedVideoFile.size)})`
    : "MP4, MOV, MKV, WEBM";
  dropZone.classList.toggle("has-file", Boolean(selectedVideoFile));
  if (selectedVideoFile) {
    previewObjectUrl = URL.createObjectURL(selectedVideoFile);
    previewVideo.src = previewObjectUrl;
    previewVideo.hidden = false;
    previewVideo.load();
    previewVideo.play().catch(() => {});
  } else {
    previewVideo.removeAttribute("src");
    previewVideo.hidden = true;
    previewVideo.load();
  }
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
    sub_style: selectedSubStyle,
    overlay_type: selectedOverlayType,
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
    sub_style: selectedSubStyle,
    overlay_type: selectedOverlayType,
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
  exportButton.disabled = true;
  setSystemState("queued");
  setMessage(selectedVideoFile ? "Đang upload video và đưa tác vụ vào hàng chờ..." : "Đang gửi tác vụ vào hàng chờ...");

  try {
    const translation = selectedVideoFile
      ? await startUploadTranslation()
      : await startJsonTranslation(payload);

    currentTranslationId = translation.translation_id;
    showProgress();
    updateProgress(translation);
    setMessage("Đã bắt đầu xử lý. Bạn theo dõi tiến trình ở phía dưới nhé.");
    startPolling();
  } catch (error) {
    setSystemState("failed");
    setMessage(`Chưa gửi được tác vụ: ${error.message}`, true);
  } finally {
    startButton.disabled = false;
    exportButton.disabled = false;
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
  const step = translation.current_step || "Chưa có tác vụ";

  setSystemState(status);
  statusTitle.textContent = `Hiện tại: ${step}`;
  statusPill.textContent = status;
  statusPill.className = `state-pill ${status}`;
  progressFill.style.width = `${percent}%`;
  progressText.textContent = `Tiến trình hệ thống: ${percent}%`;
  progressCopy.textContent = buildProgressCopy(translation);
  stepIndicator.textContent = stepLabel(percent);
  translationIdEl.textContent = translation.translation_id || "-";
  workDirEl.textContent = translation.work_dir || "-";

  if (translation.error) {
    setMessage(`Tác vụ lỗi ở ${translation.failed_step || "một bước chưa rõ"}: ${translation.error}`, true);
  }
}

function stepLabel(percent) {
  if (percent >= 96) return "8/8";
  if (percent >= 90) return "7/8";
  if (percent >= 78) return "6/8";
  if (percent >= 62) return "5/8";
  if (percent >= 45) return "4/8";
  if (percent >= 34) return "3/8";
  if (percent >= 18) return "2/8";
  if (percent >= 10) return "1/8";
  return "0/8";
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
  logsOutput.textContent = "Chưa có log.";
  progressFill.style.width = "0%";
  progressText.textContent = "Tiến trình hệ thống: 0%";
  stepIndicator.textContent = "0/8";
  statusTitle.textContent = "Hiện tại: Chưa có tác vụ";
  setSystemState("idle");
  setMessage("");
}

function selectSubtitleCard(card) {
  document.querySelectorAll(".subtitle-card").forEach((item) => item.classList.remove("active"));
  card.classList.add("active");
  const textarea = card.querySelector("textarea");
  previewSubtitle.textContent = textarea.value.trim() || card.dataset.previewText || "Phụ đề dịch sẽ nằm ở đây";
}

function switchPresetTab(tabType) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabType);
  });
  stylePanel.classList.toggle("hidden", tabType !== "style");
  overlayPanel.classList.toggle("hidden", tabType !== "overlay");
}

function selectStylePreset(button) {
  stylePanel.querySelectorAll(".preset-card").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  previewSubtitle.className = "preview-subtitle";
  const style = button.dataset.style;
  selectedSubStyle = style || "white";
  if (style === "yellow") previewSubtitle.classList.add("preset-yellow");
  if (style === "red") previewSubtitle.classList.add("preset-red");
  if (style === "cyan") previewSubtitle.classList.add("preset-cyan");
}

function selectOverlayPreset(button) {
  overlayPanel.querySelectorAll(".preset-card").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  blurBox.classList.remove("overlay-solid", "overlay-soft", "overlay-none");
  const overlay = button.dataset.overlay;
  selectedOverlayType = overlay || "default";
  if (overlay === "solid") blurBox.classList.add("overlay-solid");
  if (overlay === "soft") blurBox.classList.add("overlay-soft");
  if (overlay === "none") blurBox.classList.add("overlay-none");
  previewBoxText.textContent = button.textContent.trim();
}

function onMaskMove(event) {
  const deltaY = event.clientY - startY;
  const containerHeight = videoBg.offsetHeight;
  if (isDraggingMask) {
    let newTop = startTop + deltaY;
    newTop = Math.max(0, Math.min(containerHeight - blurBox.offsetHeight, newTop));
    blurBox.style.top = `${newTop}px`;
    blurBox.style.bottom = "auto";
  }
  if (isResizingMask) {
    let newHeight = startHeight - deltaY;
    let newTop = startTop + deltaY;
    if (newHeight > 28 && newTop > 0) {
      blurBox.style.height = `${newHeight}px`;
      blurBox.style.top = `${newTop}px`;
      blurBox.style.bottom = "auto";
    }
  }
}

function stopMaskInteraction() {
  isDraggingMask = false;
  isResizingMask = false;
  document.removeEventListener("mousemove", onMaskMove);
  document.removeEventListener("mouseup", stopMaskInteraction);
}

blurBox.addEventListener("mousedown", (event) => {
  if (event.target === resizeHandle) return;
  isDraggingMask = true;
  startY = event.clientY;
  startTop = blurBox.offsetTop;
  document.addEventListener("mousemove", onMaskMove);
  document.addEventListener("mouseup", stopMaskInteraction);
});

resizeHandle.addEventListener("mousedown", (event) => {
  event.stopPropagation();
  isResizingMask = true;
  startY = event.clientY;
  startTop = blurBox.offsetTop;
  startHeight = blurBox.offsetHeight;
  document.addEventListener("mousemove", onMaskMove);
  document.addEventListener("mouseup", stopMaskInteraction);
});

videoFileInput.addEventListener("change", () => setSelectedFile(videoFileInput.files[0]));

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragging");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("is-dragging"));

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
  const file = event.dataTransfer.files[0];
  if (file) {
    videoFileInput.files = event.dataTransfer.files;
    setSelectedFile(file);
  }
});

subtitleList.addEventListener("click", (event) => {
  const card = event.target.closest(".subtitle-card");
  if (card) selectSubtitleCard(card);
});

subtitleList.addEventListener("input", (event) => {
  if (event.target.matches("textarea")) {
    const card = event.target.closest(".subtitle-card");
    if (card && card.classList.contains("active")) {
      previewSubtitle.textContent = event.target.value.trim() || "Phụ đề dịch sẽ nằm ở đây";
    }
  }
});

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => switchPresetTab(button.dataset.tab));
});

stylePanel.addEventListener("click", (event) => {
  const button = event.target.closest(".preset-card");
  if (button) selectStylePreset(button);
});

overlayPanel.addEventListener("click", (event) => {
  const button = event.target.closest(".preset-card");
  if (button) selectOverlayPreset(button);
});

themeToggle.addEventListener("click", () => {
  body.classList.toggle("dark");
  themeToggle.textContent = body.classList.contains("dark") ? "Chế độ sáng" : "Chế độ tối";
  savePreferences();
});

document.querySelector("#load-video-button").addEventListener("click", () => {
  const input = document.querySelector("#video-url");
  input.focus();
  setMessage("Dán link hoặc chọn file xong bấm nút chạy pipeline nhé.");
});

form.addEventListener("submit", startTranslation);
refreshLogsButton.addEventListener("click", fetchLogs);
form.addEventListener("change", savePreferences);

loadPreferences();
setSystemState("idle");
