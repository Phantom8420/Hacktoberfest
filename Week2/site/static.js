"use strict";
// Stand-in for the local server on the static demo site: answers /api/* from data.json in the
// browser. Search and time parsing are ports of deja/ask.py, deja/when.py and the note rule in
// deja/voice.py; one-line answers exist only for the questions build_site.py asked Gemma.
(() => {
  const DATA = fetch("data.json").then((r) => r.json()).then((d) => {
    const now = Date.now() / 1000;
    for (const f of d.frames) f.t = now - f.ago;
    for (const n of d.notes) n.due = n.due_in == null ? null : now + n.due_in;
    return d;
  });

  const STOP = new Set(`a about after again all am an and any are as at be been before being but by can could did do does
doing find for from get got had has have how i i'd i'm if in into is it it's its just let like look looked
looking me my of on one or please remember saw say see seen show some something tell that the then there these
thing this those to up us was we were what what's when where which while who why will with you your deja
yesterday today tonight earlier ago last week morning afternoon evening night open opened`.split(/\s+/));
  const KEEP = /^(?:(?:hey |ok |okay )?deja[,.]? )?(remind me(?: to)?|remember(?: that| to)?|note(?: that|:)?|make a note(?: that)?|add|to ?do:?|don'?t (?:let me )?forget(?: to)?|i (?:need|have|want) to|save)\b[,:]?\s*/i;
  const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  const PARTS = { morning: [6, 12], afternoon: [12, 18], evening: [18, 24], night: [18, 28] };
  const UNITS = { minute: 60, hour: 3600, day: 86400, week: 604800 };
  const WORDS = { a: 1, an: 1, one: 1, two: 2, three: 3, four: 4, five: 5, ten: 10, few: 3, couple: 2 };
  const NUM = "(\\d+|an?|one|two|three|four|five|ten|few|couple)";

  const num = (s) => (/^\d+$/.test(s) ? +s : WORDS[s] || 1);
  const cut = (text, m) => (text.slice(0, m.index) + " " + text.slice(m.index + m[0].length)).replace(/\s{2,}/g, " ").trim();
  const midnight = (s) => { const d = new Date(s * 1000); d.setHours(0, 0, 0, 0); return d / 1000; };
  const weekday = (s) => (new Date(s * 1000).getDay() + 6) % 7; // Monday = 0, as in Python
  const window_ = (day, part) => { const [lo, hi] = PARTS[part] || [0, 24]; return [day + lo * 3600, day + hi * 3600]; };

  function past(text, now) {
    const today = midnight(now), t = text.toLowerCase();
    let m = new RegExp(`\\b${NUM}(?: of)? (minute|hour|day|week)s? ago\\b`).exec(t);
    if (m) {
      const n = num(m[1]), unit = UNITS[m[2]];
      if (m[2] === "day" || m[2] === "week") return [today - n * unit, today - n * unit + unit, cut(text, m)];
      return [now - n * unit - unit, now - n * unit + unit, cut(text, m)];
    }
    if ((m = /\blast night\b/.exec(t))) return [...window_(today - 86400, "night"), cut(text, m)];
    if ((m = /\b(today|yesterday)(?: (morning|afternoon|evening))?\b|\bthis (morning|afternoon|evening)\b/.exec(t)))
      return [...window_(m[1] === "yesterday" ? today - 86400 : today, m[2] || m[3]), cut(text, m)];
    if ((m = /\btonight\b|\bearlier\b/.exec(t))) return [today, now, cut(text, m)];
    if ((m = new RegExp(`\\b(?:(last|this past|on|this) )?(${DAYS.join("|")})(?: (morning|afternoon|evening|night))?\\b`).exec(t))) {
      let back = (weekday(now) - DAYS.indexOf(m[2]) + 7) % 7;
      if (back === 0 && (m[1] === "last" || m[1] === "this past")) back = 7;
      return [...window_(today - back * 86400, m[3]), cut(text, m)];
    }
    if ((m = /\b(last|this) week\b/.exec(t))) {
      const monday = today - weekday(now) * 86400;
      return m[1] === "this" ? [monday, now, cut(text, m)] : [monday - 7 * 86400, monday, cut(text, m)];
    }
    return [null, null, text];
  }

  function due(text, now) {
    const today = midnight(now), t = text.toLowerCase();
    let m = new RegExp(`\\bin ${NUM}(?: of)? (minute|hour|day|week)s?\\b`).exec(t);
    if (m) return [now + num(m[1]) * UNITS[m[2]], cut(text, m)];
    let day = null, hour = null, rest = text;
    m = new RegExp(`\\b(tomorrow|tonight|this (?:morning|afternoon|evening)|next week|(?:on |next |this )?(?:${DAYS.join("|")}))\\b`).exec(t);
    if (m) {
      const w = m[1];
      if (w === "tomorrow") [day, hour] = [today + 86400, 9];
      else if (w === "tonight") [day, hour] = [today, 20];
      else if (w.startsWith("this ") && PARTS[w.split(" ")[1]]) [day, hour] = [today, { morning: 9, afternoon: 15, evening: 18 }[w.split(" ")[1]]];
      else if (w === "next week") [day, hour] = [today + (7 - weekday(now)) * 86400, 9];
      else [day, hour] = [today + (((DAYS.indexOf(w.split(" ").pop()) - weekday(now) + 7) % 7) || 7) * 86400, 9];
      rest = cut(rest, { index: m.index, 0: m[0] });
    }
    m = /\b(?:at|by) (\d{1,2})(?:[:.](\d{2}))? ?(am|pm|a\.m\.|p\.m\.)?\b/.exec(rest.toLowerCase());
    if (m) {
      let h = +m[1];
      const mins = +(m[2] || 0), ampm = (m[3] || "").replace(/\./g, "");
      if (ampm === "pm" && h < 12) h += 12;
      else if (ampm === "am" && h === 12) h = 0;
      else if (!ampm && h < 8) h += 12; // "at 5" means 5 pm
      if (h > 23 || mins > 59) return [day == null ? null : day + hour * 3600, rest];
      rest = cut(rest, m);
      if (day == null) day = now < today + h * 3600 + mins * 60 ? today : today + 86400;
      return [day + h * 3600 + mins * 60, rest];
    }
    return [day == null ? null : day + hour * 3600, rest];
  }

  function terms(q) {
    return (q.toLowerCase().match(/[a-z0-9][a-z0-9'+#.-]*/g) || [])
      .map((w) => [w, w.replace(/^[.']+|[.']+$/g, "")])
      .filter(([w, s]) => !STOP.has(s) && (w.length > 1 || /^\d+$/.test(w))).map(([, s]) => s);
  }
  const parts = (words) => [...new Set(words.flatMap((w) => w.toLowerCase().split(/[^\w]+/)).filter((p) => p.length >= 3))];
  function snippet(text, words, n) {
    const lines = (text || "").split("\n").filter((l) => l.trim());
    const hits = lines.filter((l) => words.some((w) => l.toLowerCase().includes(w)));
    return (hits.length ? hits : lines).slice(0, n).join("\n").slice(0, 700);
  }
  // shortcut: counts matching substrings instead of bm25 ranking; fine for a handful of sample screens
  function search(d, words, start, end) {
    const ps = parts(words), inWin = d.frames.filter((f) => f.t >= (start || 0) && f.t < (end || 9e12));
    if (!ps.length) return inWin.slice(0, 8);
    return inWin.map((f) => [ps.filter((p) => `${f.app} ${f.title} ${f.text}`.toLowerCase().includes(p)).length, f])
      .filter(([s]) => s).sort((a, b) => b[0] - a[0] || b[1].t - a[1].t).slice(0, 8).map(([, f]) => f);
  }

  function handle(d, text) {
    const now = Date.now() / 1000, m = KEEP.exec(text.trim());
    if (m) {
      const verb = m[1].toLowerCase();
      let kind = verb.startsWith("remind") ? "reminder"
        : verb.endsWith(" to") || /^(add|to|don|i )/.test(verb) ? "todo" : "note";
      let body = text.trim().slice(m[0].length).trim().replace(/\.+$/, "");
      body = body.charAt(0).toUpperCase() + body.slice(1);
      if (body) {
        const [at, rest] = due(body, now);
        if (kind === "reminder" && at == null) kind = "todo";
        return { text, intent: "note", note: { id: null, text: rest || body, kind, due: at } };
      }
    }
    const byId = (id) => d.frames.find((f) => f.id === id);
    const [start, end, rest] = past(text, now), words = terms(rest);
    // same keywords as a question build_site.py asked, so "flight gate?" finds "What was my flight gate?"
    const known = words.length ? d.answers[[...words].sort().join(" ")] : null;
    const hits = known ? known.hits.map(byId) : search(d, words, start, end);
    const ps = parts(words);
    return {
      text, intent: "ask", answer: known ? known.answer : null, cited: known ? known.cited : null,
      hits: hits.map((f) => ({ ...f, text: undefined, snippet: snippet(f.text, words, 4) })),
      notes: ps.length ? d.notes.filter((n) => ps.some((p) => n.text.toLowerCase().includes(p))) : [],
    };
  }

  function get(d, url) {
    const q = url.searchParams;
    if (url.pathname === "/api/status") {
      const today = midnight(Date.now() / 1000);
      return { frames: d.frames.length, today: d.frames.filter((f) => f.t >= today).length, mb: d.mb,
        state: "sample screens", public: true, static: true, gemma: true, hotkeys: [],
        gemma_model: d.gemma_model, whisper_model: "base.en",
        settings: { paused: false, excluded: [], interval: 5, keep_days: 30 } };
    }
    if (url.pathname === "/api/timeline") {
      const [y, mo, dd] = q.get("day").split("-").map(Number), start = new Date(y, mo - 1, dd) / 1000;
      return { day: q.get("day"), frames: d.frames.filter((f) => f.t >= start && f.t < start + 86400).sort((a, b) => a.t - b.t) };
    }
    if (url.pathname === "/api/frame") return d.frames.find((f) => f.id === +q.get("id"));
    if (url.pathname === "/api/notes") return { notes: d.notes };
  }

  const real = window.fetch.bind(window);
  window.fetch = async (input, opt = {}) => {
    const url = new URL(input, location.href);
    if (!url.pathname.startsWith("/api/")) return real(input, opt);
    const d = await DATA;
    const json = (code, body) => new Response(JSON.stringify(body), { status: code, headers: { "Content-Type": "application/json" } });
    if (!opt.method || opt.method === "GET") {
      const body = get(d, url);
      return body ? json(200, body) : json(404, { error: "not found" });
    }
    if (url.pathname === "/api/ask") return json(200, handle(d, String(JSON.parse(opt.body).text).trim().slice(0, 500)));
    return json(403, { error: "this is a read-only demo" });
  };
})();
