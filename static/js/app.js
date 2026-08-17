/* Kotak Assist — customer support client */

const STORAGE_TOKEN = "kmpl_session_token";
const STORAGE_CUSTOMER = "kmpl_customer";
const AGENT_LABEL = "Support";

const loginView = document.getElementById("loginView");
const appView = document.getElementById("appView");
const loginForm = document.getElementById("loginForm");
const guestForm = document.getElementById("guestForm");
const loginError = document.getElementById("loginError");
const guestError = document.getElementById("guestError");
const loginBtn = document.getElementById("loginBtn");
const guestBtn = document.getElementById("guestBtn");
const showGuestBtn = document.getElementById("showGuestBtn");
const showLoginBtn = document.getElementById("showLoginBtn");
const authFlip = document.getElementById("authFlip");
const logoutBtn = document.getElementById("logoutBtn");
const userNameEl = document.getElementById("userName");
const guestBadge = document.getElementById("guestBadge");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const muteBtn = document.getElementById("muteBtn");
const statusPill = document.getElementById("statusPill");
const hint = document.getElementById("hint");
const orb = document.getElementById("orb");
const voiceCanvas = document.getElementById("voiceCanvas");
const transcriptEl = document.getElementById("transcript");

let pc = null;
let dc = null;
let localStream = null;
let audioEl = null;
let eventSocket = null;
let muted = false;
let activeResponseId = null;
let greetingSent = false;
let callStartedAt = null;
let callActive = false;
let vizMode = "idle";
let audioCtx = null;
let micAnalyser = null;
let remoteAnalyser = null;
let vizRaf = 0;
let vizLevel = 0;
const seenEventIds = new Set();
const handledCallIds = new Set();
const pendingToolCalls = new Map();
const conversationLog = [];

function getToken() {
  return sessionStorage.getItem(STORAGE_TOKEN) || "";
}

function getCustomer() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_CUSTOMER) || "null");
  } catch {
    return null;
  }
}

function setSession(token, customer) {
  sessionStorage.setItem(STORAGE_TOKEN, token);
  sessionStorage.setItem(STORAGE_CUSTOMER, JSON.stringify(customer));
}

function clearSession() {
  sessionStorage.removeItem(STORAGE_TOKEN);
  sessionStorage.removeItem(STORAGE_CUSTOMER);
}

function showLogin() {
  loginView.classList.remove("hidden");
  appView.classList.add("hidden");
  authFlip?.classList.remove("is-guest");
}

function showApp() {
  loginView.classList.add("hidden");
  appView.classList.remove("hidden");
  const customer = getCustomer();
  if (customer) {
    userNameEl.textContent = customer.full_name || customer.customer_id;
    guestBadge.classList.toggle("hidden", !customer.is_guest);
  }
  if (!vizRaf) drawVoiceViz();
}

function setStatus(text, kind = "idle") {
  statusPill.textContent = text;
  statusPill.className = `status-pill ${kind}`;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function addBubble(role, text) {
  if (!text || !String(text).trim()) return;
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  const who = role === "user" ? "You" : AGENT_LABEL;
  div.innerHTML = `<span class="who">${escapeHtml(who)}</span>${escapeHtml(String(text))}`;
  transcriptEl.appendChild(div);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
  conversationLog.push({ role, text: String(text).trim() });
}

function toolState(responseId) {
  if (!pendingToolCalls.has(responseId)) {
    pendingToolCalls.set(responseId, {
      expected: new Set(),
      completed: new Set(),
      knownAll: false,
      responseRequested: false,
    });
  }
  return pendingToolCalls.get(responseId);
}

function maybeContinueAfterTools(responseId) {
  const state = pendingToolCalls.get(responseId);
  if (!state || state.responseRequested || !state.knownAll) return;
  if (state.expected.size === 0) return;
  if (![...state.expected].every((id) => state.completed.has(id))) return;
  if (!dc || dc.readyState !== "open") return;
  state.responseRequested = true;
  dc.send(JSON.stringify({ type: "response.create" }));
}

async function executeTool(name, args) {
  const res = await fetch("/api/tools/execute", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": getToken(),
    },
    body: JSON.stringify({
      name,
      arguments: args || {},
      session_token: getToken(),
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Tool failed: ${name}`);
  }
  const data = await res.json();
  return data.output;
}

async function handleFunctionCall(item, responseId) {
  if (!item?.call_id || handledCallIds.has(item.call_id)) return;
  handledCallIds.add(item.call_id);

  const name = item.name;
  let args = {};
  try {
    args = item.arguments ? JSON.parse(item.arguments) : {};
  } catch {
    args = {};
  }

  const rid = responseId || activeResponseId || "unknown";
  const state = toolState(rid);
  state.expected.add(item.call_id);

  let output;
  try {
    output = await executeTool(name, args);
  } catch (err) {
    output = JSON.stringify({ error: String(err.message || err) });
    console.error("Tool error", name, err);
  }

  if (dc && dc.readyState === "open") {
    dc.send(
      JSON.stringify({
        type: "conversation.item.create",
        item: {
          type: "function_call_output",
          call_id: item.call_id,
          output: typeof output === "string" ? output : JSON.stringify(output),
        },
      }),
    );
  }

  state.completed.add(item.call_id);
  maybeContinueAfterTools(rid);
}

function sendOpeningGreeting() {
  if (greetingSent || !dc || dc.readyState !== "open") return;
  greetingSent = true;
  const customer = getCustomer();
  const name = customer?.full_name?.split(" ")[0] || "";
  const guest = Boolean(customer?.is_guest);
  const greet = guest
    ? name
      ? `Say exactly this once, then stop and wait: Hello ${name}, this is Kotak customer support. I can help with KMPL products and policies. How can I help you today?`
      : "Say exactly this once, then stop and wait: Hello, this is Kotak customer support. I can help with KMPL products and policies. How can I help you today?"
    : name
      ? `Say exactly this once, then stop and wait: Hello ${name}, this is Kotak customer support. How can I help you today?`
      : "Say exactly this once, then stop and wait: Hello, this is Kotak customer support. How can I help you today?";
  dc.send(
    JSON.stringify({
      type: "response.create",
      response: { instructions: greet },
    }),
  );
}

function onServerEvent(event) {
  const type = event.type;
  if (event.event_id) {
    if (seenEventIds.has(event.event_id)) return;
    seenEventIds.add(event.event_id);
  }

  if (type === "session.created" || type === "session.updated") {
    setStatus("Connected", "live");
    setVizMode("listening");
    hint.textContent = "Connected. Speak naturally — support will respond when you finish.";
    sendOpeningGreeting();
  }

  if (type === "input_audio_buffer.speech_started") {
    setStatus("Listening…", "live");
    setVizMode("listening");
  }

  if (type === "input_audio_buffer.speech_stopped") {
    setStatus("Thinking…", "live");
  }

  if (type === "response.created") {
    activeResponseId = event.response?.id || null;
    greetingSent = true;
  }

  if (type === "output_audio_buffer.started" || type === "response.output_audio.delta") {
    setStatus("Speaking…", "live");
    setVizMode("speaking");
  }

  if (type === "output_audio_buffer.stopped" || type === "response.done") {
    setVizMode("listening");
    setStatus("Listening…", "live");
  }

  if (type === "conversation.item.input_audio_transcription.completed") {
    addBubble("user", event.transcript || "");
  }

  if (type === "response.output_audio_transcript.delta") {
    const responseId = event.response_id || activeResponseId || "current";
    let bubble = transcriptEl.querySelector(`.bubble.assistant[data-response-id="${responseId}"]`);
    if (!bubble) {
      bubble = document.createElement("div");
      bubble.className = "bubble assistant";
      bubble.dataset.responseId = responseId;
      bubble.dataset.streaming = "1";
      bubble.innerHTML = `<span class="who">${escapeHtml(AGENT_LABEL)}</span>`;
      transcriptEl.appendChild(bubble);
    }
    bubble.appendChild(document.createTextNode(event.delta || ""));
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  if (type === "response.output_audio_transcript.done") {
    const responseId = event.response_id || activeResponseId;
    const bubble = responseId
      ? transcriptEl.querySelector(`.bubble.assistant[data-response-id="${responseId}"]`)
      : transcriptEl.querySelector(".bubble.assistant:last-of-type");
    if (bubble) {
      bubble.dataset.streaming = "0";
      const text = bubble.textContent.replace(AGENT_LABEL, "").trim();
      if (text) conversationLog.push({ role: "assistant", text });
    }
  }

  if (type === "response.function_call_arguments.done") {
    handleFunctionCall(
      {
        name: event.name,
        arguments: event.arguments,
        call_id: event.call_id,
      },
      event.response_id || activeResponseId,
    );
  }

  if (type === "response.done" && event.response?.output) {
    const rid = event.response.id || activeResponseId;
    const calls = event.response.output.filter((item) => item.type === "function_call" && item.call_id);
    if (calls.length) {
      const state = toolState(rid);
      for (const item of calls) {
        state.expected.add(item.call_id);
        handleFunctionCall(item, rid);
      }
      state.knownAll = true;
      maybeContinueAfterTools(rid);
    }
  }

  if (type === "error") {
    console.error("Realtime error", event);
    setStatus("Error", "error");
  }
}

async function startCall() {
  if (!getToken()) {
    showLogin();
    return;
  }

  startBtn.disabled = true;
  setStatus("Connecting…", "idle");
  hint.textContent = "Requesting microphone and opening secure voice session…";

  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("This browser does not support microphone access. Try Chrome or Edge.");
  }

  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (err) {
    throw new Error(
      err?.name === "NotAllowedError"
        ? "Microphone access denied. Allow mic permission in your browser and try again."
        : `Microphone error: ${err.message || err}`,
    );
  }

  connectEventSocket();

  audioEl = document.createElement("audio");
  audioEl.autoplay = true;
  audioEl.playsInline = true;
  document.body.appendChild(audioEl);

  pc = new RTCPeerConnection();
  pc.ontrack = (e) => {
    audioEl.srcObject = e.streams[0];
    attachRemoteAnalyser(e.streams[0]);
  };

  startVoiceViz(localStream);
  setVizMode("listening");

  for (const track of localStream.getTracks()) {
    pc.addTrack(track, localStream);
  }

  dc = pc.createDataChannel("oai-events");
  dc.addEventListener("open", sendOpeningGreeting);
  dc.addEventListener("message", (e) => {
    try {
      onServerEvent(JSON.parse(e.data));
    } catch (err) {
      console.warn("Bad event", err);
    }
  });

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const sdpResponse = await fetch("/session", {
    method: "POST",
    body: offer.sdp,
    headers: {
      "Content-Type": "application/sdp",
      "X-Session-Token": getToken(),
    },
  });

  if (!sdpResponse.ok) {
    let errText = await sdpResponse.text();
    try {
      const parsed = JSON.parse(errText);
      errText = parsed.detail || errText;
    } catch (_) {
      /* keep raw text */
    }
    if (sdpResponse.status === 401) {
      clearSession();
      showLogin();
      throw new Error("Session expired. Please log in again.");
    }
    throw new Error(errText || "Failed to create realtime session");
  }

  const answerSdp = await sdpResponse.text();
  await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

  callStartedAt = Date.now();
  callActive = true;
  stopBtn.disabled = false;
  muteBtn.disabled = false;
  setStatus("Live", "live");
  const guest = Boolean(getCustomer()?.is_guest);
  hint.textContent = guest
    ? "You are live as a guest. Ask about KMPL products, policies, or applying for a loan. Account balances are not available."
    : "You are live. Describe your issue and we will help you from here.";
}

async function endCallOnServer() {
  const token = getToken();
  if (!token) return;
  try {
    await fetch("/api/call/end", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_token: token,
        transcript: conversationLog,
        resolved: true,
      }),
    });
  } catch (err) {
    console.warn("Failed to log support ticket", err);
  }
}

async function stopCall() {
  if (callActive) {
    await endCallOnServer();
  }

  callActive = false;
  cleanupLocalCall();
  callStartedAt = null;
  startBtn.disabled = false;
  setStatus("Idle", "idle");
  setVizMode("idle");
  hint.textContent = "Call ended. Click Start Call to begin again.";
}

function toggleMute() {
  if (!localStream) return;
  muted = !muted;
  localStream.getAudioTracks().forEach((t) => {
    t.enabled = !muted;
  });
  muteBtn.textContent = muted ? "Unmute Mic" : "Mute Mic";
  setStatus(muted ? "Muted" : "Listening…", "live");
}

function connectEventSocket() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  eventSocket = new WebSocket(`${proto}://${location.host}/ws/events`);
  eventSocket.addEventListener("open", () => {
    eventSocket.send(JSON.stringify({ type: "client_status", status: "ui_ready" }));
  });
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.classList.add("hidden");
  loginBtn.disabled = true;

  const login = document.getElementById("loginInput").value.trim();
  const password = document.getElementById("passwordInput").value;

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || "Login failed");
    }
    setSession(data.session_token, data.customer);
    transcriptEl.innerHTML = "";
    conversationLog.length = 0;
    showApp();
  } catch (err) {
    loginError.textContent = err.message || "Login failed";
    loginError.classList.remove("hidden");
  } finally {
    loginBtn.disabled = false;
  }
});

showGuestBtn.addEventListener("click", () => {
  loginError.classList.add("hidden");
  guestError.classList.add("hidden");
  authFlip.classList.add("is-guest");
  setTimeout(() => document.getElementById("guestName")?.focus(), 350);
});

showLoginBtn.addEventListener("click", () => {
  loginError.classList.add("hidden");
  guestError.classList.add("hidden");
  authFlip.classList.remove("is-guest");
  setTimeout(() => document.getElementById("loginInput")?.focus(), 350);
});

guestForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  guestError.classList.add("hidden");
  guestBtn.disabled = true;

  const full_name = document.getElementById("guestName").value.trim();
  const phone = document.getElementById("guestPhone").value.trim();
  const email = document.getElementById("guestEmail").value.trim();

  try {
    const res = await fetch("/api/guest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name, phone, email }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || "Could not continue as guest");
    }
    setSession(data.session_token, data.customer);
    transcriptEl.innerHTML = "";
    conversationLog.length = 0;
    hint.textContent =
      "Guest mode: ask about KMPL products and policies. Account information is not available.";
    showApp();
  } catch (err) {
    guestError.textContent = err.message || "Guest login failed";
    guestError.classList.remove("hidden");
  } finally {
    guestBtn.disabled = false;
  }
});

logoutBtn.addEventListener("click", async () => {
  await stopCall();
  try {
    await fetch("/api/logout", {
      method: "POST",
      headers: { "X-Session-Token": getToken() },
    });
  } catch (_) {}
  clearSession();
  showLogin();
});

startBtn.addEventListener("click", () => {
  startCall().catch((err) => {
    console.error(err);
    setStatus("Error", "error");
    hint.textContent = err.message || "Could not start call.";
    cleanupLocalCall();
    startBtn.disabled = false;
  });
});

function cleanupLocalCall() {
  try {
    dc?.close();
  } catch (_) {}
  try {
    pc?.getSenders().forEach((s) => s.track && s.track.stop());
    pc?.close();
  } catch (_) {}
  localStream?.getTracks().forEach((t) => t.stop());
  if (audioEl) {
    audioEl.srcObject = null;
    audioEl.remove();
    audioEl = null;
  }
  try {
    eventSocket?.close();
  } catch (_) {}

  pc = null;
  dc = null;
  localStream = null;
  eventSocket = null;
  greetingSent = false;
  activeResponseId = null;
  seenEventIds.clear();
  handledCallIds.clear();
  pendingToolCalls.clear();
  muted = false;
  muteBtn.textContent = "Mute Mic";
  stopBtn.disabled = true;
  muteBtn.disabled = true;
  stopVoiceViz();
  if (!callActive) {
    setStatus("Idle", "idle");
  }
}

stopBtn.addEventListener("click", () => stopCall());
muteBtn.addEventListener("click", toggleMute);

// Boot
if (getToken() && getCustomer()) {
  showApp();
} else {
  showLogin();
}

function setVizMode(mode) {
  vizMode = mode;
  orb.classList.toggle("listening", mode === "listening");
  orb.classList.toggle("speaking", mode === "speaking");
}

function analyserLevel(analyser) {
  if (!analyser) return 0;
  const freq = new Uint8Array(analyser.frequencyBinCount);
  const time = new Uint8Array(analyser.fftSize);
  analyser.getByteFrequencyData(freq);
  analyser.getByteTimeDomainData(time);
  let energy = 0;
  const usable = Math.floor(freq.length * 0.55);
  for (let i = 1; i < usable; i++) energy += freq[i];
  energy = energy / (usable * 255);
  let rms = 0;
  for (let i = 0; i < time.length; i++) {
    const v = (time[i] - 128) / 128;
    rms += v * v;
  }
  rms = Math.sqrt(rms / time.length);
  return Math.min(1, energy * 1.35 + rms * 2.1);
}

function startVoiceViz(micStream) {
  try {
    audioCtx?.close();
  } catch (_) {}
  audioCtx = new AudioContext();
  micAnalyser = audioCtx.createAnalyser();
  micAnalyser.fftSize = 512;
  micAnalyser.smoothingTimeConstant = 0.72;
  audioCtx.createMediaStreamSource(micStream).connect(micAnalyser);
  remoteAnalyser = null;
  if (audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
  if (!vizRaf) drawVoiceViz();
}

function attachRemoteAnalyser(stream) {
  if (!audioCtx || !stream) return;
  remoteAnalyser = audioCtx.createAnalyser();
  remoteAnalyser.fftSize = 512;
  remoteAnalyser.smoothingTimeConstant = 0.68;
  audioCtx.createMediaStreamSource(stream).connect(remoteAnalyser);
}

function stopVoiceViz() {
  try {
    audioCtx?.close();
  } catch (_) {}
  audioCtx = null;
  micAnalyser = null;
  remoteAnalyser = null;
  vizLevel = 0;
  vizMode = "idle";
  if (!vizRaf) drawVoiceViz();
}

function drawVoiceViz() {
  const canvas = voiceCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const size = Math.floor(canvas.clientWidth * dpr) || 420;
  if (canvas.width !== size) {
    canvas.width = size;
    canvas.height = size;
  }

  const speaking = vizMode === "speaking";
  const live = vizMode === "listening" || speaking;
  const source = speaking && remoteAnalyser ? remoteAnalyser : micAnalyser;
  const target = live ? analyserLevel(source) : 0.06 + Math.sin(Date.now() / 900) * 0.025;
  vizLevel += (target - vizLevel) * (speaking ? 0.28 : 0.18);

  const cx = size / 2;
  const cy = size / 2;
  ctx.clearRect(0, 0, size, size);

  const rings = 3;
  for (let r = rings; r >= 1; r--) {
    const radius = size * (0.18 + r * 0.1 + vizLevel * 0.08 * r);
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = speaking
      ? `rgba(237, 28, 36, ${0.08 + vizLevel * 0.12})`
      : `rgba(0, 51, 102, ${0.07 + vizLevel * 0.1})`;
    ctx.lineWidth = 2 * dpr;
    ctx.stroke();
  }

  const analyser = source;
  const bins = analyser ? analyser.frequencyBinCount : 64;
  const freq = new Uint8Array(bins);
  if (analyser) analyser.getByteFrequencyData(freq);
  const bars = 56;
  const inner = size * (0.2 + vizLevel * 0.04);
  const maxLen = size * (0.16 + vizLevel * 0.22);

  for (let i = 0; i < bars; i++) {
    const idx = Math.floor((i / bars) * bins * 0.62) + 2;
    const raw = analyser ? freq[idx] / 255 : 0.18;
    const h = Math.max(0.08, raw) * maxLen * (0.45 + vizLevel);
    const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
    const x1 = cx + Math.cos(angle) * inner;
    const y1 = cy + Math.sin(angle) * inner;
    const x2 = cx + Math.cos(angle) * (inner + h);
    const y2 = cy + Math.sin(angle) * (inner + h);
    const grad = ctx.createLinearGradient(x1, y1, x2, y2);
    if (speaking) {
      grad.addColorStop(0, "rgba(0, 51, 102, 0.35)");
      grad.addColorStop(1, "rgba(237, 28, 36, 0.95)");
    } else {
      grad.addColorStop(0, "rgba(0, 51, 102, 0.25)");
      grad.addColorStop(1, "rgba(0, 51, 102, 0.85)");
    }
    ctx.strokeStyle = grad;
    ctx.lineWidth = Math.max(2, size * 0.007);
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  const core = size * (0.13 + vizLevel * 0.03);
  const glow = ctx.createRadialGradient(cx, cy, core * 0.2, cx, cy, core * 1.6);
  glow.addColorStop(0, speaking ? "rgba(237, 28, 36, 0.22)" : "rgba(0, 51, 102, 0.16)");
  glow.addColorStop(1, "rgba(255, 255, 255, 0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(cx, cy, core * 1.6, 0, Math.PI * 2);
  ctx.fill();

  vizRaf = requestAnimationFrame(drawVoiceViz);
}

fetch("/health").catch(() => {});
