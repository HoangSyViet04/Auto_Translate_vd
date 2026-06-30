const body = document.body;
const form = document.querySelector("#translate-form");
const startButton = document.querySelector("#start-button");
const formMessage = document.querySelector("#form-message");
const progressPanel = document.querySelector("#progress-panel");
const statusTitle = document.querySelector("#status-title");
const systemState = document.querySelector("#system-state");
const progressFill = document.querySelector("#progress-fill");
const progressText = document.querySelector("#progress-text");
const stepIndicator = document.querySelector("#step-indicator");
const logsOutput = document.querySelector("#logs-output");
const dropZone = document.querySelector("#drop-zone");
const videoFileInput = document.querySelector("#video-file");
const fileNameEl = document.querySelector("#file-name");
const themeToggle = document.querySelector("#theme-toggle");
const themeIcon = document.querySelector("#theme-icon");
const subtitleList = document.querySelector("#subtitle-list");
const previewVideo = document.querySelector("#preview-video");
const previewSubtitle = document.querySelector("#preview-subtitle");
const blurBox = document.querySelector("#blur-box");
const videoBg = document.querySelector("#video-bg");
const resizeHandle = document.querySelector("#resize-handle");
const previewBoxText = document.querySelector("#preview-box-text");
const stylePanel = document.querySelector("#panel-style-presets");
const overlayPanel = document.querySelector("#panel-overlay-presets");
const overlayWidthInput = document.querySelector("#overlay-width");
const overlayHeightInput = document.querySelector("#overlay-height");
const overlayBlurInput = document.querySelector("#overlay-blur");

const STORAGE_KEY = "autoTranslateVideo.preferences";
let pollTimer = null;
let currentTranslationId = null;
let selectedVideoFile = null;
let previewObjectUrl = null;
let selectedSubStyle = "white";
let selectedOverlayType = "blur";
let isDraggingMask = false;
let isResizingMask = false;
let activePointerId = null;
let startX = 0;
let startY = 0;
let startLeft = 0;
let startTop = 0;
let startHeight = 0;

const friendlyCopy = {
  queued: "Đã nhận tác vụ, đang xếp hàng xử lý...",
  running: "Đang xử lý video. Tiến trình sẽ cập nhật theo từng bước.",
  translate_pending: "Đã bóc băng xong. Bạn cần tạo file dịch hoặc thêm GOOGLE_API_KEY rồi resume.",
  succeeded: "Xong rồi. Video/audio đã được xuất vào work dir.",
  failed: "Có lỗi rồi. Log bên dưới đã rút gọn để bạn thấy lỗi nằm ở bước nào."
};

function normalizeStepLabel(step) {
  return String(step || "")
    .replaceAll("BÆ°á»›c", "Bước")
    .replaceAll("Äang", "Đang")
    .replaceAll("TÃ¡ch Ã¢m thanh", "Tách âm thanh")
    .replaceAll("TÃ¡c vá»¥", "Tác vụ")
    .replaceAll("bá»‹ lá»—i", "bị lỗi");
}

function readPreferences() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function setThemeIcon() {
  themeIcon.textContent = body.classList.contains("dark") ? "☀" : "☾";
}

function loadPreferences() {
  const saved = readPreferences();
  for (const [name, value] of Object.entries(saved)) {
    const input = form.elements[name];
    if (input && value) input.value = value;
  }
  body.classList.toggle("dark", saved.theme === "dark");
  setThemeIcon();
}

function savePreferences() {
  const data = Object.fromEntries(new FormData(form).entries());
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    targetLanguage: data.targetLanguage,
    sourceLang: data.sourceLang,
    asrProvider: data.asrProvider,
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

function getOverlayGeometry() {
  const container = videoBg.getBoundingClientRect();
  const box = blurBox.getBoundingClientRect();
  if (!container.width || !container.height) {
    return {overlay_x: 0.09, overlay_y: 0.78, overlay_w: 0.82, overlay_h: 0.1};
  }
  return {
    overlay_x: clamp((box.left - container.left) / container.width, 0, 0.98),
    overlay_y: clamp((box.top - container.top) / container.height, 0, 0.98),
    overlay_w: clamp(box.width / container.width, 0.05, 1),
    overlay_h: clamp(box.height / container.height, 0.03, 1)
  };
}

function buildOverlayPayload() {
  return {
    overlay_type: selectedOverlayType,
    overlay_blur: Number(overlayBlurInput.value || 14),
    ...getOverlayGeometry()
  };
}

function buildJsonPayload() {
  const data = Object.fromEntries(new FormData(form).entries());
  const payload = {
    target_language: data.targetLanguage,
    source_lang: data.sourceLang,
    asr_provider: data.asrProvider,
    bgm_mode: data.bgmMode,
    target_voice: data.targetVoice,
    sub_style: selectedSubStyle,
    skip_video: false,
    ...buildOverlayPayload()
  };

  if (data.videoUrl.trim()) payload.video_url = data.videoUrl.trim();
  if (data.resumeDir.trim()) payload.resume_dir = data.resumeDir.trim();
  return payload;
}

function buildUploadUrl() {
  const data = Object.fromEntries(new FormData(form).entries());
  const overlay = buildOverlayPayload();
  const params = new URLSearchParams({
    filename: selectedVideoFile.name,
    target_language: data.targetLanguage,
    source_lang: data.sourceLang,
    asr_provider: data.asrProvider,
    bgm_mode: data.bgmMode,
    target_voice: data.targetVoice,
    sub_style: selectedSubStyle,
    overlay_type: overlay.overlay_type,
    overlay_x: overlay.overlay_x.toFixed(4),
    overlay_y: overlay.overlay_y.toFixed(4),
    overlay_w: overlay.overlay_w.toFixed(4),
    overlay_h: overlay.overlay_h.toFixed(4),
    overlay_blur: String(overlay.overlay_blur),
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
    setMessage("Bạn cần dán link video, thả file video hoặc điền resume folder trước.", true);
    return;
  }

  startButton.disabled = true;
  setSystemState("queued");
  setMessage(selectedVideoFile ? "Đang upload video và đưa tác vụ vào hàng chờ..." : "Đang gửi tác vụ vào hàng chờ...");

  try {
    const translation = selectedVideoFile
      ? await startUploadTranslation()
      : await startJsonTranslation(payload);

    currentTranslationId = translation.translation_id;
    showProgress();
    updateProgress(translation);
    setMessage("Đã bắt đầu xử lý. Bạn có thể theo dõi tiến trình ở thanh bên dưới.");
    startPolling();
  } catch (error) {
    setSystemState("failed");
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
    logsOutput.textContent = "Chưa tải được log, thử lại sau một nhịp.";
  }
}

function updateProgress(translation) {
  const status = translation.status || "queued";
  const percent = Math.max(0, Math.min(100, translation.progress_percent || 0));
  const step = normalizeStepLabel(translation.current_step || "Chưa có tác vụ");

  setSystemState(status);
  statusTitle.textContent = `Hiện tại: ${step}`;
  progressFill.style.width = `${percent}%`;
  progressText.textContent = `Tiến trình hệ thống: ${percent}%`;
  stepIndicator.textContent = stepLabel(percent);
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
  const step = normalizeStepLabel(translation.current_step || "");
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
  if (style !== "white") previewSubtitle.classList.add(`preset-${style}`);
}

function selectOverlayPreset(button) {
  overlayPanel.querySelectorAll(".preset-card").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  blurBox.classList.remove("overlay-blur", "overlay-solid", "overlay-soft", "overlay-none");
  const overlay = button.dataset.overlay;
  selectedOverlayType = overlay || "blur";
  if (selectedOverlayType === "blur") blurBox.classList.add("overlay-blur");
  if (selectedOverlayType === "solid") blurBox.classList.add("overlay-solid");
  if (selectedOverlayType === "soft") blurBox.classList.add("overlay-soft");
  if (selectedOverlayType === "none") blurBox.classList.add("overlay-none");
  previewBoxText.textContent = button.textContent.trim();
}

function applyOverlaySliders() {
  const width = Number(overlayWidthInput.value || 82);
  const height = Number(overlayHeightInput.value || 10);
  const blur = Number(overlayBlurInput.value || 14);
  const currentLeft = parseFloat(blurBox.style.left || "9") || 9;
  const left = clamp(currentLeft, 0, 100 - width);

  blurBox.style.width = `${width}%`;
  blurBox.style.height = `${height}%`;
  blurBox.style.left = `${left}%`;
  blurBox.style.right = "auto";
  blurBox.style.setProperty("--mask-blur", `${blur}px`);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function syncOverlaySliders() {
  const geometry = getOverlayGeometry();
  overlayWidthInput.value = Math.round(geometry.overlay_w * 100);
  overlayHeightInput.value = Math.round(geometry.overlay_h * 100);
}

function startMaskDrag(event) {
  if (event.target === resizeHandle) return;
  event.preventDefault();
  isDraggingMask = true;
  isResizingMask = false;
  activePointerId = event.pointerId;
  startX = event.clientX;
  startY = event.clientY;
  startLeft = blurBox.offsetLeft;
  startTop = blurBox.offsetTop;
  blurBox.setPointerCapture?.(event.pointerId);
}

function startMaskResize(event) {
  event.preventDefault();
  event.stopPropagation();
  isDraggingMask = false;
  isResizingMask = true;
  activePointerId = event.pointerId;
  startX = event.clientX;
  startY = event.clientY;
  startLeft = blurBox.offsetLeft;
  startTop = blurBox.offsetTop;
  startHeight = blurBox.offsetHeight;
  blurBox.setPointerCapture?.(event.pointerId);
}

function onMaskMove(event) {
  if (activePointerId !== null && event.pointerId !== activePointerId) return;
  if (!isDraggingMask && !isResizingMask) return;

  const deltaY = event.clientY - startY;
  const deltaX = event.clientX - startX;
  const containerHeight = videoBg.offsetHeight;
  const containerWidth = videoBg.offsetWidth;
  const minHeight = Math.max(28, containerHeight * 0.04);

  if (isDraggingMask) {
    const maxTop = Math.max(0, containerHeight - blurBox.offsetHeight);
    const maxLeft = Math.max(0, containerWidth - blurBox.offsetWidth);
    const newTop = Math.max(0, Math.min(maxTop, startTop + deltaY));
    const newLeft = Math.max(0, Math.min(maxLeft, startLeft + deltaX));
    blurBox.style.top = `${newTop}px`;
    blurBox.style.left = `${(newLeft / containerWidth) * 100}%`;
    blurBox.style.bottom = "auto";
    blurBox.style.right = "auto";
  }

  if (isResizingMask) {
    const newTop = Math.max(0, startTop + deltaY);
    const newHeight = Math.max(minHeight, startHeight - deltaY);
    if (newTop + newHeight <= containerHeight) {
      blurBox.style.height = `${newHeight}px`;
      blurBox.style.top = `${newTop}px`;
      blurBox.style.bottom = "auto";
      overlayHeightInput.value = Math.round((newHeight / containerHeight) * 100);
    }
  }

  if (isResizingMask) {
    const left = (blurBox.offsetLeft / containerWidth) * 100;
    blurBox.style.left = `${clamp(left, 0, 100)}%`;
    blurBox.style.right = "auto";
  }
}

function stopMaskInteraction(event) {
  if (activePointerId !== null && event.pointerId !== activePointerId) return;
  blurBox.releasePointerCapture?.(event.pointerId);
  isDraggingMask = false;
  isResizingMask = false;
  activePointerId = null;
  syncOverlaySliders();
}

blurBox.addEventListener("pointerdown", startMaskDrag);
blurBox.addEventListener("pointermove", onMaskMove);
blurBox.addEventListener("pointerup", stopMaskInteraction);
blurBox.addEventListener("pointercancel", stopMaskInteraction);
resizeHandle.addEventListener("pointerdown", startMaskResize);

overlayWidthInput.addEventListener("input", applyOverlaySliders);
overlayHeightInput.addEventListener("input", applyOverlaySliders);
overlayBlurInput.addEventListener("input", applyOverlaySliders);

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
  setThemeIcon();
  savePreferences();
});

document.querySelector("#load-video-button").addEventListener("click", () => {
  const input = document.querySelector("#video-url");
  input.focus();
  setMessage("Dán link xong bấm Bắt đầu pipeline để tạo tác vụ.");
});

form.addEventListener("submit", startTranslation);
form.addEventListener("change", savePreferences);

loadPreferences();
applyOverlaySliders();
setSystemState("idle");
