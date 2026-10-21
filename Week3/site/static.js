"use strict";
// Stand-in for the local server on the static demo site. What Gemma saw in each sample room was
// recorded once by build_site.py and is replayed here; the planner and the time learning are
// ports of effort/plan.py and effort/learn.py and run in the browser. There is no model on this
// page, so it can't look at a new photo or judge an after photo.
(() => {
  const DATA = fetch("data.json").then((r) => r.json());
  const POWER = 0.7, PRIOR = 2, LIMIT = 16;
  const runs = {}, done = [];

  /* effort/plan.py */
  const score = (items) => {
    const z = {};
    for (const i of items) z[i.zone] = (z[i.zone] || 0) + i.mess;
    return Object.values(z).reduce((s, v) => s + v ** POWER, 0);
  };
  const cost = (i) => i.cost ?? i.est_seconds;
  const argmax = (xs, f) => xs.reduce((b, x) => (b === null || f(x) > f(b) ? x : b), null); // first max, like Python's max
  const ratio = (i) => score([i]) / Math.max(cost(i), 1);

  function greedy(items, budget) {
    let chosen = [], left = budget, pool = items.filter((i) => cost(i) <= budget);
    while (pool.length) {
      const base = score(chosen);
      const pick = argmax(pool, (i) => (score([...chosen, i]) - base) / Math.max(cost(i), 1));
      chosen.push(pick);
      left -= cost(pick);
      pool = pool.filter((i) => i !== pick && cost(i) <= left);
    }
    const single = argmax(items.filter((i) => cost(i) <= budget), (i) => score([i]));
    return single && score([single]) > score(chosen) ? [single] : chosen;
  }

  function best(items, budget) {
    if (items.length > LIMIT) return null;
    const fits = items.filter((i) => cost(i) <= budget);
    let top = [], topScore = 0;
    const walk = (k, start, combo, spent) => { // same order as itertools.combinations
      if (combo.length === k) {
        const s = score(combo);
        if (s > topScore) { top = [...combo]; topScore = s; }
        return;
      }
      for (let j = start; j < fits.length; j++) {
        if (spent + cost(fits[j]) > budget) continue;
        combo.push(fits[j]);
        walk(k, j + 1, combo, spent + cost(fits[j]));
        combo.pop();
      }
    };
    for (let k = 1; k <= fits.length; k++) walk(k, 0, [], 0);
    return top;
  }

  function order(moves) {
    const rank = {};
    for (const m of [...moves].sort((a, b) => ratio(b) - ratio(a))) if (!(m.zone in rank)) rank[m.zone] = Object.keys(rank).length;
    return [...moves].sort((a, b) => rank[a.zone] - rank[b.zone] || ratio(b) - ratio(a));
  }

  const round3 = (x) => Math.round(x * 1000) / 1000;
  function make(items, budget) {
    const moves = order(best(items, budget) ?? greedy(items, budget));
    return { budget, one: argmax(items.filter((i) => cost(i) <= budget), ratio), moves,
      seconds: moves.reduce((s, m) => s + cost(m), 0), score: round3(score(moves)), possible: round3(score(items)) };
  }

  /* effort/learn.py */
  function factors() {
    const r = {};
    for (const d of done) (r[d.move_to] ||= []).push(d.actual_seconds / d.est_seconds);
    return Object.fromEntries(Object.entries(r).map(([k, v]) => [k, (v.reduce((a, b) => a + b, 0) + PRIOR) / (v.length + PRIOR)]));
  }
  const apply = (items, f) => items.map((i) => ({ ...i, cost: Math.max(1, Math.round(i.est_seconds * (f[i.move_to] ?? 1))) }));

  const reply = (status, body) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function api(path, init) {
    const d = await DATA;
    if (path === "/api/see") {
      const s = d.samples.find((x) => init.body.name === x.file);
      if (!s) return reply(400, { error: "The online demo has no model, so it can only replay the sample rooms. Run it locally to use your own photo." });
      await wait(1600);
      const run = Math.random().toString(16).slice(2, 12);
      runs[run] = s.items;
      return reply(200, { run, items: s.items, seconds: s.seconds });
    }
    const b = JSON.parse(init.body || "{}");
    if (path === "/api/plan") {
      const f = factors(), gone = new Set(b.removed.map(Number));
      const items = apply(runs[b.run].filter((i) => !gone.has(i.id)), f);
      runs[b.run].costed = Object.fromEntries(items.map((i) => [i.id, i]));
      return reply(200, { ...make(items, Number(b.budget)), factors: f });
    }
    if (path === "/api/done") {
      const it = runs[b.run].costed[b.item];
      done.push({ move_to: it.move_to, est_seconds: it.est_seconds, actual_seconds: b.actual_seconds });
      return reply(200, { ok: true });
    }
    if (path.startsWith("/api/after")) {
      return reply(400, { error: "Judging an after photo needs Gemma, which this page doesn't have. Run it locally for that part." });
    }
    return reply(404, { error: "Not here." });
  }

  const real = window.fetch.bind(window);
  window.fetch = (url, init) => (String(url).startsWith("/api/") ? api(String(url), init || {}) : real(url, init));

  /* sample rooms instead of an upload */
  DATA.then((d) => {
    const pick = document.createElement("div");
    pick.className = "samples";
    pick.innerHTML = `<p class="hint">This online copy has no model in it, so pick a sample room: what Gemma 3 saw in it on a laptop CPU is replayed. <a href="https://github.com/Phantom8420/Hacktoberfest/tree/main/Week3">Run it locally</a> for your own room.</p>
      <div class="sample-row">${d.samples.map((s) => `<button type="button" class="sample" data-file="${s.file}">
        <img src="samples/${s.file}" alt="${s.title}" loading="lazy"><span>${s.title}</span></button>`).join("")}</div>`;
    const drop = document.getElementById("drop"), input = document.getElementById("photo"); // app.js listens on this input
    drop.replaceWith(pick);
    pick.id = "drop";
    input.hidden = true;
    pick.append(input);
    document.querySelector(".lede").textContent = "Show it your room, say how much energy you have left, and get the few moves worth the most tidiness. The real thing runs on your own computer; this copy replays it.";
    document.getElementById("wait-text").textContent = "Replaying what Gemma saw. On a laptop CPU this took a while; here it's instant-ish.";
    document.querySelector(".foot").innerHTML = d.samples.map((s) =>
      `<a href="${s.url}">${s.title}</a>: ${s.author}, ${s.license}`).join(" · ") + `. Model output from ${d.model}.`;
    pick.addEventListener("click", async (e) => {
      const b = e.target.closest(".sample");
      if (!b) return;
      const blob = await (await real(`samples/${b.dataset.file}`)).blob();
      const t = new DataTransfer();
      t.items.add(new File([blob], b.dataset.file, { type: blob.type }));
      document.getElementById("photo").files = t.files;
      document.getElementById("photo").dispatchEvent(new Event("change"));
    });
  });

  window.effortPlan = { make, greedy, best, score }; // for eval/static_parity.mjs
})();
