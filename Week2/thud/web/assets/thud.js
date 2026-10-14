const SR = 32000, $ = id => document.getElementById(id);
const FEATURES = ["peak_hz", "centroid_hz", "rolloff_hz", "low_ratio", "decay_ms", "ring_ratio", "flatness"];
const LABELS = [null, "solid", "hollow"];
const st = { rows: 4, cols: 5, per: 2, tiles: [], cursor: 0, batches: [], backend: null, photos: [], truth: null };

const say = (t, err) => { $("status").textContent = t; $("status").className = err ? "err" : ""; };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const name = (r, c) => String.fromCharCode(65 + r) + (c + 1);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v | 0));

function reset() {
  st.rows = clamp($("rows").value, 1, 20); st.cols = clamp($("cols").value, 1, 20); st.per = +$("per").value;
  st.tiles = []; st.cursor = 0; st.batches = []; st.truth = null; st.backend = null;
  for (let r = 0; r < st.rows; r++) for (let c = 0; c < st.cols; c++)
    st.tiles.push({ r, c, taps: [], features: null, label: null, p_hollow: null, sus: null });
  $("result").innerHTML = '<p class="empty">No taps yet.</p>';
  render();
}

function mean(taps) {
  const f = {};
  for (const k of FEATURES) f[k] = taps.reduce((s, t) => s + t[k], 0) / taps.length;
  return f;
}

function addTaps(taps) {
  const before = st.tiles.map(t => t.taps.length);
  let placed = 0;
  for (const tap of taps) {
    const i = Math.floor(st.cursor / st.per);
    if (i >= st.tiles.length) break;
    st.tiles[i].taps.push(tap); st.cursor++; placed++;
  }
  for (const t of st.tiles) t.features = t.taps.length ? mean(t.taps) : null;
  st.batches.push({ before, cursor: st.cursor - placed });
  $("undo").disabled = false;
  return placed;
}

function undo() {
  const b = st.batches.pop(); if (!b) return;
  st.tiles.forEach((t, i) => {
    t.taps = t.taps.slice(0, b.before[i]);
    t.features = t.taps.length ? mean(t.taps) : null;
    if (!t.features) t.label = null;
  });
  st.cursor = b.cursor;
  $("undo").disabled = !st.batches.length;
  say("Removed the last recording.");
  scoreFloor();
}

function cls(t) {
  if (!t.features) return "";
  if (t.p_hollow != null) return t.p_hollow >= .5 ? "hollow" : t.p_hollow >= .3 ? "unsure" : "solid";
  return t.check ? "check" : "tapped";
}

function render() {
  const g = $("grid");
  g.style.setProperty("--cols", st.cols);
  const next = Math.floor(st.cursor / st.per);
  g.innerHTML = st.tiles.map((t, i) => {
    const p = t.p_hollow != null ? Math.round(t.p_hollow * 100) + "%" : "";
    const you = t.label ? `<span class="you">you: ${t.label}</span>` : "";
    const desc = `${name(t.r, t.c)}${t.features ? "" : ", not tapped"}${p ? `, ${p} likely hollow` : ""}${t.label ? `, confirmed ${t.label}` : ""}`;
    return `<button type="button" role="gridcell" class="tile ${cls(t)} ${i === next ? "next" : ""}" data-i="${i}" aria-label="${desc}">
      <span>${name(t.r, t.c)}</span><span class="p">${p}</span>${you}</button>`;
  }).join("");
  const tapped = st.tiles.filter(t => t.features);
  $("s-tapped").textContent = tapped.length;
  $("s-flagged").textContent = st.tiles.filter(t => t.p_hollow >= .5).length;
  $("s-confirmed").textContent = st.tiles.filter(t => t.label).length;
  $("write").disabled = !tapped.length;
}

$("grid").addEventListener("click", e => {
  const b = e.target.closest(".tile"); if (!b) return;
  const t = st.tiles[+b.dataset.i];
  if (!t.features) return say(`${name(t.r, t.c)} has no taps yet.`);
  t.label = LABELS[(LABELS.indexOf(t.label) + 1) % LABELS.length];
  scoreFloor();
});

async function scoreFloor() {
  const tapped = st.tiles.filter(t => t.features);
  st.tiles.forEach(t => { t.p_hollow = null; t.check = false; });
  if (!tapped.length) return render();
  const r = await fetch("api/score", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows: tapped.map(t => t.features), labels: tapped.map(t => t.label) }) });
  const j = await r.json();
  if (!r.ok) { render(); return say(j.error || "Scoring failed.", true); }
  tapped.forEach((t, i) => { t.sus = j.suspicion[i]; });
  const ranked = [...tapped].sort((a, b) => b.sus - a.sus);
  ranked.slice(0, Math.max(2, Math.ceil(tapped.length / 6))).forEach(t => { if (t.sus > 1.5) t.check = true; });
  if (/TabPFN/.test(j.note || "")) $("s-tabpfn").textContent = "unavailable";
  if (j.p_hollow) {
    st.backend = j.backend;
    $("s-tabpfn").textContent = j.backend === "local" ? "local" : "API";
    $("d-tabpfn").classList.add("on");
    tapped.forEach((t, i) => { t.p_hollow = j.p_hollow[i]; });
  }
  render();
  showResult(j, tapped);
}

function showResult(j, tapped) {
  const flagged = tapped.filter(t => t.p_hollow >= .5);
  let html;
  if (j.p_hollow) {
    html = `<strong>${flagged.length} of ${tapped.length} tiles likely hollow</strong>
      <p>TabPFN (${j.backend === "local" ? "running on this laptop" : "API, numbers only"}) learned this floor from your ${tapped.filter(t => t.label).length} confirmed tiles.</p>`;
    if (st.truth) {
      const right = tapped.filter(t => (t.p_hollow >= .5) === st.truth[st.tiles.indexOf(t)]).length;
      html += `<p>Demo floor: ${right} of ${tapped.length} tiles match the hidden answer.</p>`;
    }
  } else {
    const check = tapped.filter(t => t.check).map(t => name(t.r, t.c));
    const enough = ["solid", "hollow"].every(l => tapped.filter(t => t.label === l).length >= 2);
    html = `<strong>${tapped.length} tiles tapped</strong>
      <p>${check.length ? `These sound least like the rest of the floor: ${check.join(", ")}. Check them by hand first.` : "No tile stands out yet."}
      ${!enough ? "Mark at least two solid and two hollow tiles and TabPFN scores the rest." : /TabPFN/.test(j.note || "") ? "TabPFN is not set up on this machine. Install it or set TABPFN_TOKEN (see the README)." : esc(j.note || "")}</p>`;
  }
  $("result").innerHTML = html;
}

function drawWave(x, taps) {
  const cv = $("wave"), g = cv.getContext("2d"), W = cv.width, H = cv.height;
  g.fillStyle = "#0a1f4e"; g.fillRect(0, 0, W, H);
  const step = Math.max(1, Math.floor(x.length / W));
  let peak = 1e-6; for (let i = 0; i < x.length; i += 7) peak = Math.max(peak, Math.abs(x[i]));
  g.fillStyle = "#bfe4fa";
  for (let px = 0; px < W; px++) {
    let m = 0; for (let i = px * step; i < (px + 1) * step && i < x.length; i++) m = Math.max(m, Math.abs(x[i]));
    const h = (m / peak) * (H / 2 - 8);
    g.fillRect(px, H / 2 - h, 1, Math.max(1, 2 * h));
  }
  g.fillStyle = "#ffc42e";
  for (const t of taps) g.fillRect(Math.round(t.t * SR / step), 0, 3, 12);
}

async function analyse(samples) {
  if (samples.length < SR / 2) return say("That recording is too short. Record at least half a second.", true);
  say("Finding taps…");
  const r = await fetch("api/taps", { method: "POST", body: samples.buffer });
  const j = await r.json();
  if (!r.ok) return say(j.error, true);
  drawWave(samples, j.taps);
  if (!j.taps.length) return say("No taps found. Drop the coin closer to the microphone, in a quieter room.", true);
  const placed = addTaps(j.taps);
  const left = st.tiles.length * st.per - st.cursor;
  say(`Found ${j.taps.length} taps${placed < j.taps.length ? `, ${j.taps.length - placed} past the last tile were ignored` : ""}. ` +
      (left ? `${Math.ceil(left / st.per)} tiles left to tap.` : "Every tile is tapped."));
  await scoreFloor();
}

async function resample(buf) {
  const n = Math.round(buf.length * SR / buf.sampleRate);
  const ctx = new OfflineAudioContext(1, n, SR);
  const src = ctx.createBufferSource();
  src.buffer = buf; src.connect(ctx.destination); src.start();
  return (await ctx.startRendering()).getChannelData(0).slice(0, 300 * SR);
}

async function decode(bytes) {
  return resample(await new AudioContext().decodeAudioData(bytes));
}

let recorder = null;
$("rec").onclick = async () => {
  if (recorder) return recorder.stop();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    const parts = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = e => parts.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      recorder = null; $("rec").textContent = "Record taps";
      try { await analyse(await decode(await new Blob(parts).arrayBuffer())); }
      catch { say("Couldn't read that recording. Try uploading a file instead.", true); }
    };
    recorder.start();
    $("rec").textContent = "Stop and find taps";
    say("Recording. Tap the next row, then press stop.");
  } catch {
    say("No microphone access. On a phone, open this page over https, or upload a recording.", true);
  }
};

$("file").onchange = async e => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  try { say("Reading the file…"); await analyse(await decode(await f.arrayBuffer())); }
  catch { say("Couldn't read that file. Try a WAV, M4A, MP3 or a phone video.", true); }
};

$("demo").onclick = async () => {
  $("rows").value = 4; $("cols").value = 5; $("per").value = "1"; reset();
  say("Generating a demo floor…");
  const r = await fetch("api/demo");
  const truth = r.headers.get("X-Truth");
  const x = new Float32Array(await r.arrayBuffer());
  await analyse(x);
  st.truth = [...truth].map(c => c === "H");
  say($("status").textContent + " The demo hides which tiles are hollow. Mark two solid and two hollow from the yellow ones, and see how many TabPFN gets right.");
};

$("undo").onclick = undo;
for (const id of ["rows", "cols", "per"]) $(id).onchange = () => {
  if (st.cursor && !confirm("Changing the grid clears the taps you recorded. Continue?")) return;
  reset();
};

function shrink(file) {
  return new Promise((ok, bad) => {
    const img = new Image();
    img.onload = () => {
      const s = Math.min(1, 1024 / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(img.src);
      ok(c.toDataURL("image/jpeg", .85));
    };
    img.onerror = bad;
    img.src = URL.createObjectURL(file);
  });
}

$("photos").onchange = async e => {
  for (const f of [...e.target.files].slice(0, 6 - st.photos.length)) {
    try { st.photos.push(await shrink(f)); } catch { say(`Couldn't read ${f.name}.`, true); }
  }
  e.target.value = "";
  $("thumbs").innerHTML = st.photos.map((p, i) => `<img src="${p}" alt="Photo ${i + 1}">`).join("");
};

function md(s) {
  const out = []; let list = false;
  for (const raw of esc(s).split("\n")) {
    const line = raw.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    const li = line.match(/^\s*[-*]\s+(.*)/);
    if (li) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${li[1]}</li>`); continue; }
    if (list) { out.push("</ul>"); list = false; }
    const h = line.match(/^#{1,6}\s+(.*)/);
    if (h) out.push(`<h4>${h[1]}</h4>`);
    else if (line.trim()) out.push(`<p>${line}</p>`);
  }
  if (list) out.push("</ul>");
  return out.join("");
}

$("write").onclick = async () => {
  $("write").disabled = true;
  $("report").innerHTML = '<p class="empty" style="margin-top:12px">Gemma is writing. On a laptop CPU this takes a minute or two, longer with photos.</p>';
  const inspection = {
    site: $("site").value, room: $("room").value, rows: st.rows, cols: st.cols, backend: st.backend,
    tiles: st.tiles.map(t => ({ r: t.r, c: t.c, tapped: !!t.features, label: t.label, p_hollow: t.p_hollow, features: t.features })),
  };
  try {
    const r = await fetch("api/report", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inspection, photos: st.photos.map(p => p.split(",")[1]) }) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error);
    $("report").innerHTML = `<div class="report">${md(j.report)}</div>
      <p class="receipt">Written by ${esc(j.writer)}. Sealed as receipt <code>${j.receipt.hash}</code>
      <button class="btn dark" type="button" id="copy" style="margin-top:10px">Copy the receipt hash</button></p>`;
    $("copy").onclick = () => navigator.clipboard.writeText(j.receipt.hash).then(() => { $("copy").textContent = "Copied"; });
    ledger();
  } catch (err) {
    $("report").innerHTML = `<p class="empty" style="margin-top:12px;color:var(--hollow)">The report failed: ${esc(err.message || "server error")}.</p>`;
  }
  $("write").disabled = false;
};

async function status() {
  try {
    const j = await (await fetch("api/status")).json();
    $("s-gemma").textContent = j.gemma ? j.gemma_model : "not running";
    $("d-gemma").classList.toggle("on", j.gemma);
    $("s-tabpfn").textContent = j.tabpfn === "local" ? "local" : j.tabpfn === "api" ? "API" : "not run yet";
    $("d-tabpfn").classList.toggle("on", j.tabpfn === "local" || j.tabpfn === "api");
  } catch { $("s-gemma").textContent = "offline"; }
}

async function ledger() {
  try {
    const j = await (await fetch("api/ledger")).json();
    $("chain").textContent = j.ok ? `Chain intact: ${j.msg}` : `Chain broken: ${j.msg}`;
    $("chain").classList.toggle("bad", !j.ok);
    if (!j.entries.length) return;
    $("ledger").innerHTML = j.entries.slice(-10).reverse().map(e => `<article class="rcard">
      <div class="top"><span>${new Date(e.t * 1000).toLocaleString()}</span></div>
      <h3>${esc(e.room || "Unnamed room")}</h3>
      <p class="n">${e.flagged}<small>hollow of ${e.tapped} tapped</small></p>
      <code>${e.hash}</code></article>`).join("");
  } catch { $("chain").textContent = "Receipts unavailable: the local server is not running."; }
}

const io = "IntersectionObserver" in window && new IntersectionObserver(es => es.forEach(e => {
  if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
}), { threshold: .12 });
document.querySelectorAll(".rise").forEach(el => io ? io.observe(el) : el.classList.add("in"));

reset(); status(); ledger();
