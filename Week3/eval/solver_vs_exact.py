"""How good is greedy (the fallback above 16 items) against brute force (what the app uses up to 16)?
And how good is the obvious human rule, biggest mess first?

Two sets of rooms: the item lists Gemma actually produced in eval/stability.py (fixtures dropped, as the app does), and 1,000
random rooms (fixed seed). For each, budgets of 30 s, 90 s and 5 min.

    python eval/solver_vs_exact.py
"""
import json
import random
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from effort import plan, see  # noqa: E402

OUT = ROOT / "eval" / "results" / "solver.json"
BUDGETS = (30, 90, 300)


def naive(items, budget):
    """What a person might do: biggest mess first, until the time runs out."""
    chosen, left = [], budget
    for i in sorted(items, key=lambda i: -i["mess"]):
        if plan.cost(i) <= left:
            chosen.append(i)
            left -= plan.cost(i)
    return chosen


def compare(rooms):
    rows = []
    for items in rooms:
        items = items[:16]  # brute force limit
        for b in BUDGETS:
            best = plan.score(plan.best(items, b))
            if best == 0:
                continue
            g, n = plan.score(plan.greedy(items, b)), plan.score(naive(items, b))
            rows.append({"budget": b, "greedy": g / best, "naive": n / best})
    differ = [r for r in rows if r["greedy"] < 1 - 1e-9]
    return {"cases": len(rows), "greedy_not_optimal": len(differ),
            "greedy_worst": round(min(r["greedy"] for r in rows), 3),
            "greedy_median": round(median(r["greedy"] for r in rows), 3),
            "naive_worst": round(min(r["naive"] for r in rows), 3),
            "naive_median": round(median(r["naive"] for r in rows), 3),
            "naive_not_optimal": sum(r["naive"] < 1 - 1e-9 for r in rows),
            "ratios": [[r["budget"], round(r["greedy"], 4), round(r["naive"], 4)] for r in rows]}


def main():
    real = []
    stab = ROOT / "eval" / "results" / "stability.json"
    if stab.exists():
        looks = [look["items"] for s in json.loads(stab.read_text())["scenes"] for look in s["looks"]]
        real = [k for k in ([i for i in x if not see.fixture(i["what"], i["zone"], i["move_to"])] for x in looks) if k]
    rng = random.Random(2026)
    zones = ["bed", "floor", "desk", "chair", "shelf"]
    fake = [[{"id": i, "what": f"x{i}", "zone": rng.choice(zones), "move_to": "other",
              "est_seconds": rng.randint(3, 120), "mess": rng.randint(1, 5)}
             for i in range(rng.randint(3, 14))] for _ in range(1000)]
    out = {"power": plan.POWER, "budgets": BUDGETS, "real": compare(real) if real else None, "random": compare(fake)}
    OUT.write_text(json.dumps(out, indent=1))
    for k in ("real", "random"):
        if out[k]:
            print(k, {x: v for x, v in out[k].items() if x != "ratios"})
    print("saved", OUT)


if __name__ == "__main__":
    main()
