const $ = (id) => document.getElementById(id);
const state = { run: null, items: [], removed: new Set(), plan: null, timer: null, done: new Set() };

const icon = (name) => `<svg class="ic" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function secs(n) {
  n = Math.round(n);
  if (n < 120) return `${n} seconds`;
  const m = Math.floor(n / 60), s = n % 60;
  return s ? `${m} min ${s} s` : `${m} minutes`;
}

// slider position -> seconds, on a log scale from 10 s to 10 min, rounded to numbers people say
function budget() {
  const raw = 10 * Math.pow(60, $("budget").value / 100);
  const step = raw < 60 ? 5 : raw < 180 ? 10 : 30;
  return Math.round(raw / step) * step;
}
function mood(s) {
  return s <= 30 ? "barely alive" : s <= 120 ? "some" : s <= 300 ? "a little" : "suspiciously motivated";
}
function showBudget() {
  const s = budget();
  $("budget-secs").textContent = secs(s);
  $("budget-mood").textContent = mood(s);
}

async function api(path, body, type = "application/json") {
  const res = await fetch(path, {
    method: "POST", headers: { "Content-Type": type },
    body: type === "application/json" ? JSON.stringify(body) : body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Something went wrong (${res.status}).`);
  return data;
}

// /api/see answers in NDJSON: {"item": ...} per item as Gemma writes it, then the whole answer
async function see(file, onItem) {
  const res = await fetch("/api/see", { method: "POST", headers: { "Content-Type": file.type || "image/jpeg" }, body: file });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Something went wrong (${res.status}).`);
  }
  const reader = res.body.getReader(), dec = new TextDecoder();
  let buf = "", out = null;
  for (let done = false; !done;) {
    const r = await reader.read();
    done = r.done;
    buf += dec.decode(r.value, { stream: !done });
    const lines = buf.split("\n");
    buf = lines.pop();
    for (const line of lines.filter((l) => l.trim()).map((l) => JSON.parse(l))) {
      if (line.error) throw new Error(line.error);
      line.item ? onItem(line.item) : (out = line);
    }
  }
  if (!out) throw new Error("Gemma stopped before finishing. Try the photo again.");
  return out;
}

function clock(el) {
  const t0 = performance.now();
  const id = setInterval(() => { el.textContent = `${Math.round((performance.now() - t0) / 1000)} s`; }, 500);
  el.textContent = "0 s";
  return () => clearInterval(id);
}

function show(id) {
  $(id).hidden = false;
}

/* 1. before photo -> items */
$("photo").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  $("preview-img").src = URL.createObjectURL(file);
  $("preview").hidden = false;
  $("snap-error").hidden = true;
  $("drop").classList.add("busy");
  ["check", "energy", "move", "after"].forEach((id) => ($(id).hidden = true));
  $("wait").hidden = false;
  const stop = clock($("wait-clock"));
  Object.assign(state, { run: null, items: [], removed: new Set(), plan: null, done: new Set() });
  $("chips").innerHTML = "";
  $("go").disabled = true;
  try {
    const out = await see(file, (item) => { // chips and the slider while Gemma is still writing
      state.items.push(item);
      if (state.items.length === 1) { show("check"); show("energy"); }
      $("chips").insertAdjacentHTML("beforeend", chip(item));
    });
    Object.assign(state, { run: out.run, items: out.items });
    renderChips();
    show("check");
    show("energy");
    $("go").disabled = false;
    $("go").focus();
  } catch (err) {
    ["check", "energy"].forEach((id) => ($(id).hidden = true)); // half a list with no run to plan
    $("snap-error").textContent = err.message;
    $("snap-error").hidden = false;
  } finally {
    stop();
    $("wait").hidden = true;
    $("drop").classList.remove("busy");
    e.target.value = "";
  }
});

/* 2. untick what isn't there */
function renderChips() {
  const ul = $("chips");
  if (!state.items.length) {
    ul.innerHTML = `<li class="hint">Gemma found nothing to move. Either the room is tidy or the photo is too dark; try one with more light.</li>`;
    return;
  }
  ul.innerHTML = state.items.map(chip).join("");
}
const chip = (i) => `
    <li><button class="chip" type="button" data-id="${i.id}" aria-pressed="${state.removed.has(i.id)}"
      aria-label="${esc(i.what)} on ${esc(i.zone)}; tap if it isn't really there">
      ${esc(i.what)} <small>${esc(i.zone)} · ~${i.est_seconds}s</small>${icon("x")}</button></li>`;
$("chips").addEventListener("click", (e) => {
  const b = e.target.closest(".chip");
  if (!b) return;
  const id = Number(b.dataset.id);
  const off = !state.removed.has(id);
  off ? state.removed.add(id) : state.removed.delete(id);
  b.setAttribute("aria-pressed", String(off));
});

/* 3. energy -> plan */
$("budget").addEventListener("input", showBudget);
$("go").addEventListener("click", async () => {
  $("go").disabled = true;
  try {
    state.plan = await api("/api/plan", { run: state.run, budget: budget(), removed: [...state.removed] });
    state.done = new Set();
    renderPlan();
    show("move");
    show("after");
    $("one").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    alertIn("snap-error", err.message);
  } finally {
    $("go").disabled = false;
  }
});

function alertIn(id, msg) {
  $(id).textContent = msg;
  $(id).hidden = false;
}

function renderPlan() {
  const p = state.plan, one = p.one;
  const card = $("one");
  card.classList.toggle("empty", !one);
  if (!one) {
    card.innerHTML = `<p class="label">Your one move</p><h3>Nothing fits in ${secs(p.budget)}.</h3>
      <p class="rest">Which is a perfectly good answer. Lie down, or nudge the slider.</p>`;
  } else {
    card.innerHTML = `
      <p class="label">Your one move</p>
      <h3>${esc(cap(one.what))}</h3>
      <p class="route"><span>from the ${esc(one.zone)}</span> ${icon("arrow")} <span>${esc(one.move_to)}</span></p>
      <p class="cost">about ${secs(one.cost)}</p>
      <div class="row">${timerButton(one, true)}</div>
      <p class="rest">That's it. If you still have energy afterwards, the full plan is below.</p>`;
    card.style.animation = "none"; card.offsetHeight; card.style.animation = "";
  }
  const share = p.possible ? Math.round((100 * p.score) / p.possible) : 0;
  $("plan-sum").innerHTML = p.moves.length
    ? `<span><b>${p.moves.length}</b> move${p.moves.length > 1 ? "s" : ""}</span><span><b>${secs(p.seconds)}</b></span>
       <span><b>${share}%</b> of the tidiness on offer</span>`
    : "<span>empty</span>";
  $("moves").innerHTML = p.moves.map((m) => `
    <li data-id="${m.id}"><span class="what">${esc(cap(m.what))}</span>
      <span class="meta">${esc(m.zone)} → ${esc(m.move_to)} · ~${secs(m.cost)}</span>${timerButton(m)}</li>`).join("");
  calibLine(one, p.factors);
}

function timerButton(m, big) {
  const ring = `<div class="ring" data-ring="${m.id}" data-cost="${m.cost}"><svg viewBox="0 0 64 64" aria-hidden="true">
      <circle class="track" cx="32" cy="32" r="28" pathLength="100"/><circle class="fill" cx="32" cy="32" r="28" pathLength="100"/></svg>
      <span class="timer" data-clock="${m.id}">${secs(m.cost).replace(" seconds", " s")}</span></div>`;
  return `${big ? ring : ""}<button type="button" class="${big ? "primary" : "mini"}" data-timer="${m.id}">${icon("play")}<span>Start</span></button>`;
}

function calibLine(one, f) {
  const el = $("calib");
  const k = one && f[one.move_to];
  el.hidden = !k || Math.abs(k - 1) < 0.1;
  if (!el.hidden) {
    el.innerHTML = `You take <b>${k.toFixed(1)}×</b> Gemma's guess for <b>${esc(one.move_to)}</b> moves, so this one is planned at ${secs(one.cost)}, not ${secs(one.est_seconds)}.`;
  }
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/* 4. timers: one running at a time; Done logs the real seconds */
document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-timer]");
  if (!b || b.disabled) return;
  const id = Number(b.dataset.timer);
  const t = state.timer;
  if (t && t.id === id) {
    t.stop();
    const actual = (performance.now() - t.t0) / 1000;
    state.timer = null;
    markDone(id, actual);
    try { await api("/api/done", { run: state.run, item: id, actual_seconds: actual }); }
    catch (err) { alertIn("after-error", `Couldn't save that time: ${err.message}`); }
    return;
  }
  if (t) return; // finish the running move first
  const clocks = [...document.querySelectorAll(`[data-clock="${id}"]`)];
  const buttons = [...document.querySelectorAll(`[data-timer="${id}"]`)];
  const t0 = performance.now();
  const ring = document.querySelector(`[data-ring="${id}"]`);
  const tick = () => {
    const el = (performance.now() - t0) / 1000, s = `${Math.round(el)} s`;
    if (ring) { // counts down the planned seconds; running over is allowed, it just says so
      const left = Math.round(ring.dataset.cost - el);
      ring.style.setProperty("--p", Math.min(el / ring.dataset.cost, 1) * 100);
      ring.classList.toggle("over", left < 0);
      clocks.forEach((c) => { c.textContent = left >= 0 ? `${left} s left` : `${-left} s over`; });
    } else clocks.forEach((c) => (c.textContent = s));
    clocks.forEach((c) => c.classList.add("on"));
    buttons.forEach((x) => { if (x.classList.contains("mini")) x.querySelector("span").textContent = s; });
  };
  const iv = setInterval(tick, 250);
  state.timer = { id, t0, stop: () => clearInterval(iv) };
  buttons.forEach((x) => { x.classList.add("on"); x.querySelector("use").setAttribute("href", "#i-check"); x.querySelector("span").textContent = "Done"; });
  tick();
  buttons.filter((x) => x.classList.contains("primary")).forEach((x) => (x.querySelector("span").textContent = "Done"));
});

function markDone(id, actual) {
  state.done.add(id);
  document.querySelectorAll(`[data-timer="${id}"]`).forEach((x) => {
    x.disabled = true;
    x.classList.remove("on");
    x.querySelector("span").textContent = `Done in ${Math.round(actual)} s`;
  });
  document.querySelectorAll(`[data-clock="${id}"], [data-ring="${id}"]`).forEach((c) => c.remove());
  document.querySelector(`#moves li[data-id="${id}"]`)?.classList.add("done");
}

/* 5. after photo -> verdict */
$("photo-after").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  $("after-error").hidden = true;
  $("verdict").hidden = true;
  $("wait-after").hidden = false;
  const stop = clock($("after-clock"));
  try {
    const v = await api(`/api/after?run=${encodeURIComponent(state.run)}`, file, file.type || "image/jpeg");
    renderVerdict(v);
    $("again").hidden = false;
  } catch (err) {
    alertIn("after-error", err.message);
  } finally {
    stop();
    $("wait-after").hidden = true;
    e.target.value = "";
  }
});

function renderVerdict(v) {
  const spent = state.plan.moves.filter((m) => state.done.has(m.id)).length;
  const heads = {
    tidier: "Tidier. Officially.",
    messier: "Somehow, messier.",
    same: "Gemma sees no difference.",
    unclear: "Gemma can't make up its mind.",
  };
  const body = {
    tidier: `Clearly enough that it said so with the photos either way round (margin ${v.margin} of 3).`,
    messier: "Both ways round. Perhaps the light changed, or something got knocked over.",
    same: "From this angle the change is too small to see. Bold strategy; the sloth approves.",
    unclear: "It picked a different photo when the order swapped, so neither answer counts.",
  };
  const extra = v.mess_removed != null
    ? ` ${v.gone.length} item${v.gone.length === 1 ? "" : "s"} gone, about ${Math.round(v.mess_removed * 100)}% of the mess, after ${spent} move${spent === 1 ? "" : "s"}.`
    : "";
  $("verdict").innerHTML = `<h3>${heads[v.verdict] || "Done."}</h3><p>${body[v.verdict] || ""}${extra}</p>`;
  $("verdict").hidden = false;
}

$("again").addEventListener("click", () => {
  ["check", "energy", "move", "after"].forEach((id) => ($(id).hidden = true));
  $("preview").hidden = true;
  $("verdict").hidden = true;
  $("again").hidden = true;
  window.scrollTo({ top: 0, behavior: "smooth" });
  $("photo").focus();
});

showBudget();
