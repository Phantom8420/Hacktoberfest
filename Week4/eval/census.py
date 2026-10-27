"""The census: what Whisper hears in each kind of noise, with its guards off, across model sizes and seeds.
Resumable; writes eval/census.json, then prints the most common ghosts.

    python eval/census.py [sizes...]     # default: tiny base small, 7 noises x 5 seeds of 30 s each
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spiritbox import listen, noise  # noqa: E402
from spiritbox.ghosts import kind, norm  # noqa: E402

HERE = Path(__file__).parent
SEEDS = range(5)


def main(sizes):
    path = HERE / "census.json"
    out = json.loads(path.read_text()) if path.exists() else []
    done = {(r["model"], r["noise"], r["seed"]) for r in out}
    for size in sizes:
        for k in noise.KINDS:
            for seed in SEEDS:
                if (size, k, seed) in done:
                    continue
                segs = listen.retry(listen.summon, noise.make(k, 30, seed), size=size)
                for i, s in enumerate(segs):
                    s["kind"] = kind(s, segs[i - 1] if i else None) or "invented line"
                out.append({"model": size, "noise": k, "seed": seed, "lines": segs})
                print(f"{size:5} {k:7} {seed}  {[s['text'][:40] for s in segs][:3]}", flush=True)
                path.write_text(json.dumps(out, indent=1))
    summary(out)


def summary(out):
    words = collections.Counter(norm(s["text"]) or s["text"][:12] for r in out for s in r["lines"])  # norm drops non-Latin
    print("\nmost common ghosts:")
    for t, n in words.most_common(15):
        print(f"{n:4}  {t[:70]}")
    for size in dict.fromkeys(r["model"] for r in out):
        rs = [r for r in out if r["model"] == size]
        print(f"{size}: {sum(bool(r['lines']) for r in rs)}/{len(rs)} clips summoned something; languages",
              dict(collections.Counter(s["lang"] for r in rs for s in r["lines"][:1]).most_common(4)))


if __name__ == "__main__":
    main(sys.argv[1:] or ["tiny", "base", "small"])
