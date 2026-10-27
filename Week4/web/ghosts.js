// The rules from spiritbox/ghosts.py, for the browser. transformers.js gives no no-speech or log-probability
// scores, so the "unsure audio" rule can't run here, and "wrong language" means letters outside the Latin script.
const PHRASES = ["thanks for watching", "thank you for watching", "subscribe", "like and subscribe", "see you next time",
  "see you in the next video", "subtitles by", "captions by", "transcribed by", "amara.org", "thank you.",
  "bye.", "you", "i'll see you", "please like", "next video"];

const norm = s => s.toLowerCase().replace(/[^a-z0-9.' ]/g, "").trim();

// Whisper's compression-ratio check, roughly: a line whose words are mostly repeats is a loop
const loops = t => { const w = t.split(/\s+/).filter(Boolean); return w.length >= 6 && new Set(w).size / w.length < 0.35; };

function ghostKind(text, prev) {
  const t = text.trim(), n = norm(t);
  if (/^[\[(♪*].*[\])♪*]$/u.test(t)) return "sound tag";  // taste-skill-ignore: Whisper writes the note, the page never shows it as UI
  if (PHRASES.includes(n) || PHRASES.some(p => p.length > 8 && n.includes(p))) return "sign-off";
  if (loops(t) || /(.{2,12})\1{4,}/u.test(t) || (prev && norm(prev) === n && n)) return "repetition loop";
  if (/[^\p{Script=Latin}\p{N}\p{P}\p{S}\s]/u.test(t)) return "wrong language";
  return null;
}

window.ghostKind = ghostKind;
