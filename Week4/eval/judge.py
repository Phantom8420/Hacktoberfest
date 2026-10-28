"""Who catches the ghosts better: the rules (spiritbox/ghosts.py) or Gemma (spiritbox/witness.py)?
Scores both on eval/transcripts.json and writes eval/judge.json. Gemma's answers are cached, so it resumes.

    python eval/judge.py
"""
import json
import os
import sys
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spiritbox import ghosts, listen, witness  # noqa: E402

HERE = Path(__file__).parent
# SPIRITBOX_SET=holdout: a second set of meetings, made and scored only after the prompt was settled
SET = "_" + os.environ["SPIRITBOX_SET"] if os.environ.get("SPIRITBOX_SET") else ""


def score(rows, key):
    """'unsure' counts as not flagged: a line the judge wouldn't strike stays in the transcript."""
    tp = sum(r["truth"] == "ghost" and r[key] == "ghost" for r in rows)
    fp = sum(r["truth"] == "real" and r[key] == "ghost" for r in rows)
    fn = sum(r["truth"] == "ghost" and r[key] != "ghost" for r in rows)
    p, rc = tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0
    return {"caught": tp, "missed": fn, "false_alarms": fp, "precision": round(p, 2), "recall": round(rc, 2),
            "f1": round(2 * p * rc / (p + rc), 2) if p + rc else 0,
            "unsure": sum(r[key] == "unsure" for r in rows)}


def main():
    rows = json.loads((HERE / f"transcripts{SET}.json").read_text())
    cache_path = HERE / "witness_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    out = []
    for (size, meeting), g in groupby(rows, key=lambda r: (r["model"], r["meeting"])):
        g = list(g)
        for i, r in enumerate(ghosts.flag(g)):
            k = f"{witness.MODEL}|questions|{size}{SET}|{meeting}|{i}"  # "questions": the third prompt; earlier prompts are kept in the cache
            if not witness.suspect(r):
                w = witness.CLEAR
            elif k in cache:
                w = cache[k]
            else:
                w = cache[k] = listen.retry(witness.judge, g, i)
                cache_path.write_text(json.dumps(cache, indent=1))
            out.append(dict(r, rules=r["verdict"], rules_kind=r["kind"], gemma=w["verdict"], gemma_kind=w.get("kind"),
                            gemma_reason=w.get("reason")))
        print(size, meeting, "judged", flush=True)
    report = {"lines": len(out), "ghosts": sum(r["truth"] == "ghost" for r in out),
              "rules": score(out, "rules"), "gemma": score(out, "gemma")}
    for r in out:
        r["doubt"] = "ghost" if witness.suspect(r) else "real"
    report["doubt"] = score(out, "doubt")  # Whisper's doubt alone, every suspect struck
    for r in out:
        r["both"] = "ghost" if "ghost" in (r["rules"], r["gemma"]) else "real"
    report["either"] = score(out, "both")
    report["rows"] = [{k: r[k] for k in ("model", "meeting", "start", "text", "truth", "rules", "rules_kind",
                                         "gemma", "gemma_kind", "gemma_reason")} for r in out]
    (HERE / f"judge{SET}.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1))
    for r in report["rows"]:
        if r["truth"] != r["gemma"] or r["rules"] != r["gemma"]:
            print(f"{r['truth']:5} rules {r['rules']:5} gemma {r['gemma']:6} {r['text'][:60]!r}  {r['gemma_reason'][:90]}")


if __name__ == "__main__":
    main()
