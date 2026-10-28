const SR = 16000, SECONDS = 30;
const NAMES = { silence: "Silence", white: "White noise", pink: "Pink noise", brown: "Brown noise", hum: "Mains hum", fan: "Fan", rain: "Rain" };
const ABOUT = {
  silence: "Thirty seconds of zeros. Every model, every seed, wrote one word.",
  white: "Flat hiss across every frequency, like a radio between stations.",
  pink: "Hiss that falls off with pitch, closer to wind or surf.",
  brown: "Deep rumble, the sound inside a car on a motorway.",
  hum: "50 Hz and its harmonics, like an old amplifier or a fridge.",
  fan: "Brown rumble with a slow wobble.",
  rain: "Pink hiss with drops landing on it.",
};
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = s => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
// runs of Sinhala or Georgian letters are one glyph repeated; a short stretch shows it
const clip = (s, n = 64) => (n = /[^\p{Script=Latin}\p{N}\p{P}\p{S}\s]/u.test(s) ? Math.min(n, 28) : n, [...s].length > n ? [...s].slice(0, n).join("") + "…" : s);

// noise, made the way spiritbox/noise.py makes it (pink and brown by filter here, by FFT there)
function rand(seed) {
  let a = seed >>> 0 || 1;
  return () => { a ^= a << 13; a ^= a >>> 17; a ^= a << 5; return (a >>> 0) / 4294967296; };
}
function gauss(r) { return Math.sqrt(-2 * Math.log(r() || 1e-9)) * Math.cos(2 * Math.PI * r()); }
function peak(a, to) { let m = 0; for (const v of a) m = Math.max(m, Math.abs(v)); if (m) for (let i = 0; i < a.length; i++) a[i] *= to / m; return a; }
function makeNoise(kind, seed = Date.now()) {
  const n = SR * SECONDS, a = new Float32Array(n), r = rand(seed);
  if (kind === "white") for (let i = 0; i < n; i++) a[i] = 0.05 * gauss(r);
  if (kind === "pink" || kind === "rain") {  // Paul Kellet's pink filter
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < n; i++) {
      const w = gauss(r);
      b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759; b2 = 0.969 * b2 + w * 0.153852;
      b3 = 0.8665 * b3 + w * 0.3104856; b4 = 0.55 * b4 + w * 0.5329522; b5 = -0.7616 * b5 - w * 0.016898;
      a[i] = b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362; b6 = w * 0.115926;
    }
    peak(a, 0.3);
  }
  if (kind === "brown" || kind === "fan") {
    let x = 0;
    for (let i = 0; i < n; i++) { x = 0.998 * x + 0.02 * gauss(r); a[i] = x; }
    peak(a, 0.5);
    if (kind === "fan") for (let i = 0; i < n; i++) a[i] *= 0.6 + 0.2 * Math.sin(2 * Math.PI * 0.3 * i / SR);
  }
  if (kind === "hum") for (let i = 0; i < n; i++) {
    let s = 0; for (let k = 1; k < 6; k++) s += Math.sin(2 * Math.PI * 50 * k * i / SR) / k;
    a[i] = 0.1 * s + 0.01 * gauss(r);
  }
  if (kind === "rain") {
    for (let i = 0; i < n; i++) a[i] *= 0.4;
    for (let d = 0; d < SECONDS * 40; d++) {
      const at = Math.floor(r() * (n - 400)), g = 0.05 + 0.25 * r();
      for (let j = 0; j < 400; j++) a[at + j] += g * Math.exp(-j / 60) * gauss(r);
    }
    peak(a, 0.5);
  }
  return a;
}

function drawWave(canvas, a, color, from = 0) {
  const w = canvas.width = canvas.clientWidth * devicePixelRatio, h = canvas.height = canvas.clientHeight * devicePixelRatio;
  const g = canvas.getContext("2d"), cols = Math.floor(w / (2 * devicePixelRatio)), step = Math.floor(a.length / 8 / cols);
  g.clearRect(0, 0, w, h); g.fillStyle = color;
  for (let c = 0; c < cols; c++) {
    let m = 0; const s = from + c * step;
    for (let j = 0; j < step; j++) m = Math.max(m, Math.abs(a[(s + j) % a.length]));
    const bar = Math.max(1, Math.min(1, m * 1.6) * h * 0.9);
    g.fillRect(c * 2 * devicePixelRatio, (h - bar) / 2, devicePixelRatio, bar);
  }
}

// the live box
let data = null, asr = null, audio = null, playing = null;
const kindNow = () => document.querySelector("input[name=noise]:checked").value;

function showLaptop() {
  const k = kindNow(), lines = data?.census.noise[k]?.tiny || [];
  $("#laptop").innerHTML = "";
  if (!lines.length) return;
  $("#laptop").append("On a laptop, the same model in the same noise wrote ", el("q", null, clip(lines[0], 70)), ".");
}

function animateScope() {
  const c = $("#scope");
  let from = 0;
  const tick = () => {
    if (audio) drawWave(c, audio, "#8b93ff", from);
    from += SR / 20;
    if (playing && !reduced) requestAnimationFrame(tick);
  };
  tick();
}

async function summon() {
  const go = $("#go"), state = $("#state"), heard = $("#heard");
  const k = kindNow();
  audio = makeNoise(k);
  playing = true; animateScope();
  go.disabled = true; heard.innerHTML = "";
  state.className = "box-state on";
  try {
    if (!asr) {
      state.textContent = "Fetching Whisper tiny";
      const { pipeline } = await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.1");
      asr = await pipeline("automatic-speech-recognition", "onnx-community/whisper-tiny", {
        dtype: "q8", progress_callback: p => { if (p.status === "progress" && p.file?.endsWith(".onnx")) state.textContent = `Fetching Whisper tiny ${Math.round(p.progress)}%`; },
      });
    }
    state.textContent = `Listening to ${NAMES[k].toLowerCase()}`;
    const out = await asr(audio, { return_timestamps: true, chunk_length_s: 30 });
    const parts = (out.chunks?.length ? out.chunks.map(c => c.text) : [out.text]).map(t => t.trim()).filter(Boolean);
    if (!parts.length) heard.append(el("li", "quiet", "Nothing this time. Whisper tiny keeps quiet now and then; try again or pick another noise."));
    parts.forEach((t, i) => {
      const li = el("li", null, clip(t, 140)), why = ghostKind(t, parts[i - 1]);
      li.append(el("span", "why", why ? `The rules call this a ghost: ${why}.` : "Nothing in the rules catches this one."));
      heard.append(li);
    });
    state.textContent = `It heard ${parts.length} ${parts.length === 1 ? "line" : "lines"}`;
  } catch (e) {
    console.error(e);
    state.textContent = "Whisper could not load here";
    heard.append(el("li", "quiet", "This browser could not run the model. The laptop result below is what it says in this noise."));
  } finally {
    playing = false; go.disabled = false; go.textContent = "Summon again";
  }
}

// census reel
function buildReel() {
  const reel = $("#reel"), c = data.census;
  $("#census-sum").textContent = `${c.clips} clips of generated noise: seven kinds, five seeds, three model sizes. All ${c.spoke} wrote something, ${c.lines} lines between them.`;
  Object.entries(c.noise).forEach(([k, bySize], i) => {
    const p = el("article", "panel"); p.dataset.k = k;
    p.append(el("h3", null, NAMES[k] || k));
    const cv = el("canvas"); p.append(cv);
    const dl = el("dl");
    for (const size of ["tiny", "base", "small"]) {
      dl.append(el("dt", null, `Whisper ${size}`), el("dd", null, bySize[size]?.length ? clip(bySize[size][0], 80) : "Nothing"));
    }
    p.append(dl); reel.append(p);
    requestAnimationFrame(() => drawWave(cv, makeNoise(k, 7 + i), "#5d6470"));
  });
  const light = p => {
    reel.querySelectorAll(".panel").forEach(q => q.classList.toggle("lit", q === p));
    $("#reel-name").textContent = NAMES[p.dataset.k];
    $("#reel-line").textContent = ABOUT[p.dataset.k] || "";
  };
  light(reel.firstChild);
  reel.querySelectorAll(".panel").forEach(p => { p.tabIndex = 0; p.addEventListener("pointerenter", () => light(p)); p.addEventListener("focus", () => light(p)); });
}

function buildTop() {
  const ul = $("#top-rows");
  data.census.top.slice(0, 10).forEach(([t, n]) => {
    const li = el("li"); li.append(el("span", "t", clip(t, 44)), el("span", "n", n)); ul.append(li);
  });
}

function buildWitness() {
  const w = data.witness, tiles = $("#tiles");
  if (!w) { $("#witness-note").textContent = "The judges are still reading the meetings; their scores land here when they finish."; return; }
  const tile = (big, of, h, p) => { const t = el("div", "tile rise"); const b = el("p", "big", big); b.append(el("small", null, ` of ${of}`)); t.append(b, el("h3", null, h), el("p", null, p)); tiles.append(t); };
  const fa = n => `${n} real ${n === 1 ? "line" : "lines"} struck by mistake.`;
  tile(w.rules.caught, w.ghosts, "the rules", `Known sign-offs, loops, wrong language. ${fa(w.rules.false_alarms)}`);
  tile(w.doubt.caught, w.ghosts, "Whisper's own doubt", `Strike every line Whisper was unsure of. ${fa(w.doubt.false_alarms)}`);
  tile(w.first.caught, w.ghosts, "Gemma, first try", `Asked about all ${w.lines} lines, it suspected nearly every pause. ${fa(w.first.false_alarms)}`);
  tile(w.gemma.caught, w.ghosts, "Gemma, on the doubted lines", `It reads only the ${w.doubt.caught + w.doubt.false_alarms} lines Whisper doubted. ${fa(w.gemma.false_alarms)}`);
  tiles.lastChild.classList.add("best");
  $("#witness-note").textContent = `${w.lines} lines across Whisper tiny, base and small. Rules and Gemma together catch ${w.either.caught} of ${w.ghosts} for ${w.either.false_alarms} false alarms. The second prompt was written after seeing the first run's mistakes on these same meetings, so its score is optimistic, and ${w.ghosts} ghosts is a small test: a direction, not a benchmark.`;
}

function buildDoc() {
  const doc = $("#doc"), rows = data.meeting;
  if (!rows?.length) { doc.append(el("p", "empty", "The meeting transcript appears here once the judges finish.")); return; }
  for (const r of rows) {
    const ln = el("div", "ln");
    const m = Math.floor(r.start / 60), s = String(Math.floor(r.start % 60)).padStart(2, "0");
    const body = el("div"); body.append(el("span", "tx", r.text));
    if (r.rules === "ghost") { ln.classList.add("rules"); body.append(el("span", "tag r", `Rules: ${r.rules_kind}`)); }
    if (r.gemma === "ghost") { ln.classList.add("gemma"); body.append(el("span", "tag g", `Gemma: ${r.gemma_reason}`)); }
    if (r.truth === "ghost" && r.rules !== "ghost" && r.gemma !== "ghost") { ln.classList.add("missed"); body.append(el("span", "tag m", "Missed by both: nobody said this.")); }
    ln.append(el("span", "at", `${m}:${s}`), body); doc.append(ln);
  }
  const steps = document.querySelectorAll(".step");
  if (matchMedia("(max-width: 960px)").matches) { doc.dataset.state = 3; return; }
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return;
    steps.forEach(s => s.classList.toggle("on", s === e.target));
    doc.dataset.state = e.target.dataset.state;
  }), { rootMargin: "-45% 0px -45% 0px" });
  steps.forEach(s => io.observe(s));
  steps[0].classList.add("on");
}

function entrances() {
  const parts = document.querySelectorAll("main section:not(.hero) h2, main section:not(.hero) p, .pic, .rows li, .panel, .tile, .ln, pre");
  if (reduced || !("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.15 });
  parts.forEach(p => {
    if (p.closest(".step, .doc") && !p.matches(".ln")) return;
    const sibs = [...p.parentElement.children];
    p.classList.add("rise"); p.style.setProperty("--d", `${Math.min(sibs.indexOf(p), 6) * 75}ms`); io.observe(p);
  });
}

async function main() {
  audio = makeNoise("white", 1); animateScope();
  document.querySelectorAll("input[name=noise]").forEach(i => i.addEventListener("change", () => { audio = makeNoise(kindNow(), 1); animateScope(); showLaptop(); }));
  $("#go").addEventListener("click", summon);
  data = await (await fetch("data.json")).json();
  showLaptop(); buildReel(); buildTop(); buildWitness(); buildDoc(); entrances();
}
main();
