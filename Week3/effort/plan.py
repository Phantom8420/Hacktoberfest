"""Pick the moves worth the most tidiness for the seconds you have.

Tidiness isn't additive: the first thing cleared off a desk helps more than the fifth.
So a zone's value is (sum of its cleared mess) ** POWER, summed over zones. That is a
monotone submodular function, and for those, cost-benefit greedy plus "or just the single
best item, if that's better" is guaranteed at least (1 - 1/e) / 2 of the best possible plan.
Rooms of 16 items or fewer (most of them) are small enough to try every subset, so
make() uses that and only falls back to greedy above it.
"""
from itertools import combinations

POWER = 0.7  # a choice, not a measurement: how fast a zone's returns fall off


def score(items):
    zones = {}
    for it in items:
        zones[it["zone"]] = zones.get(it["zone"], 0) + it["mess"]
    return sum(v ** POWER for v in zones.values())


def cost(it):
    return it.get("cost", it["est_seconds"])  # cost = calibrated seconds once learn.py has data


def greedy(items, budget):
    chosen, left, pool = [], budget, [i for i in items if cost(i) <= budget]
    while pool:
        base = score(chosen)
        gain = lambda i: (score(chosen + [i]) - base) / max(cost(i), 1)
        pick = max(pool, key=gain)
        chosen.append(pick)
        left -= cost(pick)
        pool = [i for i in pool if i is not pick and cost(i) <= left]
    single = max((i for i in items if cost(i) <= budget), key=lambda i: score([i]), default=None)
    if single is not None and score([single]) > score(chosen):
        return [single]
    return chosen


def best(items, budget, limit=16):
    """Brute force; None when there are too many items to try every subset."""
    if len(items) > limit:
        return None
    fits = [i for i in items if cost(i) <= budget]
    top, top_score = [], 0.0
    for k in range(1, len(fits) + 1):
        for combo in combinations(fits, k):
            if sum(cost(i) for i in combo) <= budget and (s := score(combo)) > top_score:
                top, top_score = list(combo), s
    return top


def one_move(moves):
    """The move from the plan that helps most on its own, quicker one on a tie. Best value per second
    would be cheaper to compute but keeps picking five-second crumbs, like a mouse on a desk."""
    return max(moves, key=lambda m: (m["mess"], -cost(m)), default=None)


def order(moves):
    """Zone by zone so you don't walk back and forth; best value per second first within a zone."""
    zone_rank = {}
    for m in sorted(moves, key=lambda m: -score([m]) / max(cost(m), 1)):
        zone_rank.setdefault(m["zone"], len(zone_rank))
    return sorted(moves, key=lambda m: (zone_rank[m["zone"]], -score([m]) / max(cost(m), 1)))


def make(items, budget):
    chosen = best(items, budget)
    moves = order(greedy(items, budget) if chosen is None else chosen)
    return {"budget": budget, "one": one_move(moves), "moves": moves,
            "seconds": sum(cost(m) for m in moves), "score": round(score(moves), 3),
            "possible": round(score(items), 3)}
