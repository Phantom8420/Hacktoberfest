"use strict";
const $ = (s) => document.querySelector(s);

const ICON = {
  mic: '<path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>',
  left: '<path d="m15 6-6 6 6 6"/>',
  right: '<path d="m9 6 6 6-6 6"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
};
const icon = (name) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICON[name]}</svg>`;
// a grease-pencil loop around the screen that answered you
const CIRCLE = '<svg class="circle" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">' +
  '<path pathLength="1" d="M9 34C14 10 72 1 92 22c11 12 8 52-12 66C58 101 18 98 7 74 0 58 4 38 22 22"/></svg>';

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

async function api(path, body, type) {
  const opt = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": type || "application/json" },
    body: type ? body : JSON.stringify(body),
  };
  const r = await fetch(path, opt);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
  return d;
}

const dayKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const clock = (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
function when(t) {
  const d = new Date(t * 1000), now = new Date();
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (dayKey(d) === dayKey(now)) return `Today ${clock(d)}`;
  const tm = new Date(now); tm.setDate(now.getDate() + 1);
  if (dayKey(d) === dayKey(y)) return `Yesterday ${clock(d)}`;
  if (dayKey(d) === dayKey(tm)) return `Tomorrow ${clock(d)}`;
  return `${d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" })} ${clock(d)}`;
}

let flashTimer;
function flash(msg) {
  const f = $("#flash");
  f.textContent = msg;
  f.classList.add("on");
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => f.classList.remove("on"), 3500);
}

/* status */
let status = {};
async function loadStatus() {
  try { status = await api("/api/status"); } catch { $("#state-text").textContent = "Déjà isn't running"; return; }
  document.body.classList.toggle("demo", !!status.public);
  $("#demo-note").hidden = !status.public;
  const s = status.public ? "sample screens" : status.state || "";
  $("#state").classList.toggle("rec", s === "recording");
  $("#state-text").textContent = {
    recording: "Recording", paused: "Paused", locked: "Screen locked", idle: "Idle", starting: "Starting",
    "screen hidden": "A protected window is in front", "not recording": "Not recording",
    "sample screens": "Demo",
  }[s] || s.charAt(0).toUpperCase() + s.slice(1);
  $("#counts").textContent = `${status.today} screens today, ${status.mb} MB kept`;
  const paused = status.settings.paused;
  $("#pause").textContent = paused ? "Resume" : "Pause";
  $("#pause").setAttribute("aria-pressed", String(paused));
  const hint = $("#hint");
  hint.replaceChildren();
  const keys = { P: "pause or resume", F: "forget the last 5 minutes" };
  for (const k of status.hotkeys || []) {
    const span = el("span");
    span.append(el("kbd", null, "Ctrl"), " ", el("kbd", null, "Alt"), " ", el("kbd", null, k), ` ${keys[k]}`);
    hint.append(span);
  }
}

$("#pause").onclick = async () => {
  await api("/api/settings", { paused: !status.settings.paused });
  await loadStatus();
  flash(status.settings.paused ? "Paused. Nothing is being recorded." : "Recording again.");
};
$("#forget").onclick = async () => {
  const d = await api("/api/forget", { minutes: 5 });
  flash(`Forgot ${d.deleted} screen${d.deleted === 1 ? "" : "s"} from the last 5 minutes.`);
  loadStatus(); loadDay();
};

/* ask */
const result = $("#result");
const EXAMPLES = [
  "What was that hotel I looked at yesterday?",
  "What error did I get this morning?",
  "Remind me to call the dentist tomorrow at 5",
  "Note that the spare key is with Sam",
];

function intro() {
  result.replaceChildren();
  result.append(el("h2", "answer quiet", "Ask about anything that was on your screen, or tell me something to keep."),
    el("p", "sub", "Answers come from screenshots on this computer and point to the one they came from. Say “remind me to…” or “note that…” to keep a reminder or a note."));
  const ex = el("div", "examples");
  for (const q of EXAMPLES) {
    const b = el("button", null, q);
    b.type = "button";
    b.onclick = () => { $("#q").value = q; submit(q); };
    ex.append(b);
  }
  result.append(ex);
}

function loading(text) {
  result.replaceChildren();
  result.className = "result loading";
  result.append(el("p", "asked", text), el("h2", "answer quiet", "Looking through your screens…"));
  const sk = el("div", "skel");
  for (let i = 0; i < 3; i++) sk.append(el("span"));
  result.append(sk);
}

function frameCard(h, cited) {
  const b = el("button", "frame" + (cited ? " cited" : ""));
  b.type = "button";
  const pic = el("span", "pic");
  const img = el("img");
  img.src = `/frames/${h.image}`;
  img.loading = "lazy";
  img.alt = `Your screen, ${when(h.t)}, ${h.app}`;
  pic.append(img);
  if (cited) pic.insertAdjacentHTML("beforeend", CIRCLE);
  b.append(pic, el("span", "when", when(h.t)), el("span", "where", h.title ? `${h.title}, ${h.app}` : h.app));
  if (h.snippet) b.append(el("span", "snip", h.snippet));
  b.onclick = () => openFrame(h.id);
  return b;
}

function render(d) {
  result.className = "result";
  result.replaceChildren();
  if (d.intent === "none") {
    result.append(el("h2", "answer quiet", "I didn't catch that."), el("p", "sub", "Try again a little closer to the mic, or type it."));
    return;
  }
  result.append(el("p", "asked", `“${d.text}”`));
  if (d.intent === "note") {
    const n = d.note;
    const head = n.kind === "reminder" ? `Reminder set for ${when(n.due)}.`
      : n.kind === "todo" ? "Added to your to-dos." : "Noted.";
    result.append(el("h2", "answer", head), el("p", "sub", n.text));
    if (status.public) result.append(el("p", "sub", "In this demo nothing is saved. On your own PC it would be."));
    loadNotes();
    return;
  }
  const hits = d.hits || [];
  if (d.answer) {
    result.append(el("h2", "answer", d.answer));
  } else if (hits.length) {
    result.append(el("h2", "answer quiet", "Here's the closest match on your screen."),
      el("p", "sub", status.gemma ? "I couldn't put it in one sentence I could check against the screen, so look for yourself."
        : "Start Ollama for one-line answers. The screens below are what matched."));
  } else {
    result.append(el("h2", "answer quiet", "Nothing on your screen matched that."),
      el("p", "sub", "Try a word you would have seen on it: a name, a site, a file, an error."));
  }
  if (hits.length) {
    const cited = d.cited ?? hits[0].id;
    const sheet = el("div", "sheet");
    for (const h of hits) sheet.append(frameCard(h, h.id === cited));
    result.append(el("h3", null, d.answer ? "Where it came from" : "Matching screens"), sheet);
  }
  if (d.notes && d.notes.length) {
    const ul = el("ul", "kept-list");
    for (const n of d.notes) ul.append(el("li", null, n.text));
    result.append(el("h3", null, "From your notes"), ul);
  }
}

async function submit(text) {
  text = text.trim();
  if (!text) return;
  const go = $("#ask-form .go");
  go.disabled = true;
  loading(`“${text}”`);
  try {
    render(await api("/api/ask", { text }));
  } catch (e) {
    result.className = "result";
    result.replaceChildren(el("h2", "answer quiet", "That didn't go through."), el("p", "sub", `${e.message}. Is Déjà still running?`));
  } finally {
    go.disabled = false;
  }
}
$("#ask-form").onsubmit = (e) => { e.preventDefault(); submit($("#q").value); };

/* voice */
const mic = $("#mic");
mic.innerHTML = icon("mic");
let rec = null, stopTimer;
mic.onclick = async () => {
  if (rec) { rec.stop(); return; }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    flash("Déjà can't use the microphone. Allow it in the browser's site settings.");
    return;
  }
  const chunks = [];
  rec = new MediaRecorder(stream);
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec.onstop = async () => {
    clearTimeout(stopTimer);
    stream.getTracks().forEach((t) => t.stop());
    const type = rec.mimeType || "audio/webm";
    rec = null;
    mic.setAttribute("aria-pressed", "false");
    mic.setAttribute("aria-label", "Speak");
    mic.innerHTML = icon("mic");
    loading("Listening back…");
    try {
      const d = await api("/api/voice", new Blob(chunks, { type }), type);
      $("#q").value = d.text || "";
      render(d);
    } catch (e) {
      result.className = "result";
      result.replaceChildren(el("h2", "answer quiet", "I couldn't hear that recording."), el("p", "sub", e.message));
    }
  };
  rec.start();
  mic.setAttribute("aria-pressed", "true");
  mic.setAttribute("aria-label", "Stop and send");
  mic.innerHTML = icon("stop");
  stopTimer = setTimeout(() => rec && rec.stop(), 30000);
};

/* notes */
async function loadNotes() {
  const { notes } = await api("/api/notes");
  const ul = $("#notes");
  ul.replaceChildren();
  if (!notes.length) {
    ul.append(el("li", "empty", "Say “remind me to…” or “note that…” and it lands here."));
    return;
  }
  const now = Date.now() / 1000;
  for (const n of notes) {
    const li = el("li", n.due && n.due <= now ? "late" : "");
    const box = el("input");
    box.type = "checkbox";
    box.id = `n${n.id}`;
    box.disabled = !!status.public;
    box.onchange = async () => { await api("/api/notes/done", { id: n.id, done: box.checked }); li.classList.toggle("done", box.checked); };
    const label = el("label");
    label.htmlFor = box.id;
    const kind = n.kind === "reminder" ? (n.due <= now ? `Due ${when(n.due)}` : when(n.due)) : n.kind === "todo" ? "To-do" : "Note";
    label.append(el("span", "txt", n.text), el("span", "due", kind));
    const del = el("button", "del");
    del.type = "button";
    del.setAttribute("aria-label", `Delete “${n.text}”`);
    del.innerHTML = icon("x");
    del.onclick = async () => { await api("/api/notes/delete", { id: n.id }); loadNotes(); };
    li.append(box, label, del);
    ul.append(li);
  }
}

/* day */
let day = new Date(), frames = [], shown = null;
const scrub = $("#scrub");
$("#day-prev").innerHTML = icon("left");
$("#day-next").innerHTML = icon("right");
$("#open-settings").innerHTML = icon("gear");

function minuteOf(t) { const d = new Date(t * 1000); return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60; }

async function loadDay(keep) {
  const key = dayKey(day), today = dayKey(new Date());
  $("#day-pick").value = key;
  $("#day-pick").max = today;
  $("#day-next").disabled = key >= today;
  const y = new Date(); y.setDate(y.getDate() - 1);
  $("#day-title").textContent = key === today ? "Today" : key === dayKey(y) ? "Yesterday"
    : day.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" });
  ({ frames } = await api(`/api/timeline?day=${key}&limit=400`));
  const svg = $("#ticks");
  svg.replaceChildren();
  for (const f of frames) {
    const x = minuteOf(f.t).toFixed(1);
    const l = document.createElementNS("http://www.w3.org/2000/svg", "line");
    l.setAttribute("x1", x); l.setAttribute("x2", x); l.setAttribute("y1", "6"); l.setAttribute("y2", "34");
    svg.append(l);
  }
  scrub.disabled = !frames.length;
  if (!frames.length) {
    shown = null;
    $("#preview-img").hidden = true;
    $("#preview-empty").hidden = false;
    $("#preview-cap").replaceChildren();
    $("#preview").disabled = true;
    return;
  }
  if (!(keep && shown)) scrub.value = Math.round(minuteOf(frames[frames.length - 1].t));
  shown = null;
  showAt(+scrub.value);
}

function showAt(minute) {
  let best = frames[0];
  for (const f of frames) if (Math.abs(minuteOf(f.t) - minute) < Math.abs(minuteOf(best.t) - minute)) best = f;
  if (shown === best) return;
  shown = best;
  const img = $("#preview-img");
  img.src = `/frames/${best.image}`;
  img.alt = `Your screen at ${clock(new Date(best.t * 1000))}, ${best.app}`;
  img.hidden = false;
  $("#preview-empty").hidden = true;
  $("#preview").disabled = false;
  const cap = $("#preview-cap");
  cap.replaceChildren(el("b", null, clock(new Date(best.t * 1000))), el("span", null, best.app), el("span", null, best.title));
}

scrub.oninput = () => frames.length && showAt(+scrub.value);
scrub.onchange = () => { if (shown) scrub.value = Math.round(minuteOf(shown.t)); };
$("#preview").onclick = () => shown && openFrame(shown.id);
$("#day-prev").onclick = () => { day.setDate(day.getDate() - 1); loadDay(); };
$("#day-next").onclick = () => { day.setDate(day.getDate() + 1); loadDay(); };
$("#day-pick").onchange = (e) => {
  if (!e.target.value) return;
  const [yy, mm, dd] = e.target.value.split("-").map(Number);
  day = new Date(yy, mm - 1, dd);
  loadDay();
};

/* frame viewer */
const viewer = $("#viewer");
let viewing = null;
async function openFrame(id) {
  let f;
  try { f = await api(`/api/frame?id=${id}`); } catch { flash("That screen has been forgotten."); return; }
  viewing = f;
  const img = $("#viewer-img");
  img.src = `/frames/${f.image}`;
  img.alt = `Your screen, ${when(f.t)}`;
  img.hidden = false;
  $("#viewer-title").textContent = f.title || f.app;
  $("#viewer-meta").textContent = `${when(f.t)}, ${f.app}`;
  $("#viewer-text").textContent = f.text || "No text was read on this screen.";
  viewer.showModal();
}
$("#viewer-close").onclick = () => viewer.close();
$("#viewer-forget").onclick = async () => {
  await api("/api/forget/frame", { id: viewing.id });
  viewer.close();
  flash("Forgotten. The screenshot and its text are deleted.");
  document.querySelectorAll(".frame").forEach((b) => b.querySelector(`img[src$="${viewing.image}"]`) && b.remove());
  loadDay(); loadStatus();
};
viewer.onclick = (e) => { if (e.target === viewer) viewer.close(); };

/* settings */
const settings = $("#settings");
$("#open-settings").onclick = async () => {
  await loadStatus();
  const s = status.settings;
  $("#excluded").value = s.excluded.join("\n");
  $("#interval").value = s.interval;
  $("#keep").value = s.keep_days;
  $("#models").textContent = `Speech: Whisper ${status.whisper_model}. Answers: ${status.gemma_model} through Ollama, ` +
    (status.gemma ? "ready." : "not running, so you get matching screens without a one-line answer.");
  settings.showModal();
};
$("#settings-close").onclick = () => settings.close();
settings.onclick = (e) => { if (e.target === settings) settings.close(); };
$("#settings-form").onsubmit = async (e) => {
  e.preventDefault();
  await api("/api/settings", {
    excluded: $("#excluded").value.split("\n"),
    interval: +$("#interval").value || 5,
    keep_days: +$("#keep").value || 30,
  });
  settings.close();
  flash("Settings saved.");
  loadStatus();
};
$("#forget-all").onclick = async () => {
  if (!confirm("Delete every screenshot and all the text Déjà has read? Notes and reminders stay.")) return;
  const d = await api("/api/forget", { all: true });
  settings.close();
  flash(`Forgot all ${d.deleted} screens.`);
  intro(); loadDay(); loadStatus();
};

intro();
loadStatus().then(loadNotes);
loadDay();
setInterval(loadStatus, 5000);
setInterval(loadNotes, 30000);
setInterval(() => { if (dayKey(day) === dayKey(new Date()) && !document.hidden) loadDay(true); }, 60000);
