"""How long things take *you*, learned from the timer.

Per destination (bin, laundry, ...) keep actual/estimated. Two imaginary moves at exactly
1.0 are mixed in, so one odd move can't swing the plan: (sum of ratios + 2) / (n + 2).
"""
PRIOR = 2


def factors(done):
    """done: [{"move_to", "est_seconds", "actual_seconds"}] -> {move_to: factor}"""
    ratios = {}
    for d in done:
        if d.get("actual_seconds") and d.get("est_seconds"):
            ratios.setdefault(d["move_to"], []).append(d["actual_seconds"] / d["est_seconds"])
    return {k: (sum(r) + PRIOR) / (len(r) + PRIOR) for k, r in ratios.items()}


def apply(items, f):
    """Items with a calibrated `cost` in seconds (Gemma's guess times your factor)."""
    return [{**i, "cost": max(1, round(i["est_seconds"] * f.get(i["move_to"], 1.0)))} for i in items]
