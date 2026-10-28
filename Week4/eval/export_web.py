"""Pack the census and the witness results into web/data.json for the demo page.

    python eval/export_web.py
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spiritbox.ghosts import norm  # noqa: E402

HERE = Path(__file__).parent
SIZES = ("tiny", "base", "small")
SHOWN = "base", "2_fan"  # the meeting the page walks through: two echoes and a plain ghost-free stretch


def main():
    census = json.loads((HERE / "census.json").read_text(encoding="utf8"))
    lines = [(r["model"], s) for r in census for s in r["lines"]]
    top = collections.Counter(norm(s["text"]) or s["text"][:24] for _, s in lines)
    first = {}  # the exact wording of each ghost, as Whisper wrote it the first time
    for _, s in lines:
        first.setdefault(norm(s["text"]) or s["text"][:24], s["text"])
    out = {
        "census": {"clips": len(census), "spoke": sum(bool(r["lines"]) for r in census), "lines": len(lines),
                   "languages": collections.Counter(s["lang"] for _, s in lines).most_common(8),
                   "top": [[first[t][:90], n] for t, n in top.most_common(16)],
                   "noise": {k: {size: [s["text"][:120] for r in census if r["noise"] == k and r["model"] == size
                                        and r["seed"] == 0 for s in r["lines"]][:4] for size in SIZES}
                             for k in dict.fromkeys(r["noise"] for r in census)}},
    }
    judge = HERE / "judge.json"
    if judge.exists():
        j = json.loads(judge.read_text(encoding="utf8"))
        out["witness"] = {k: j[k] for k in ("lines", "ghosts", "rules", "doubt", "gemma", "either")}
        out["witness"]["first"] = json.loads((HERE / "judge_first_prompt.json").read_text(encoding="utf8"))["gemma"]
        out["meeting"] = [{k: r[k] for k in ("start", "text", "truth", "rules", "rules_kind", "gemma", "gemma_kind",
                                             "gemma_reason")} for r in j["rows"] if (r["model"], r["meeting"]) == SHOWN]
    path = HERE.parent / "web" / "data.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
    print("wrote", path, path.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
