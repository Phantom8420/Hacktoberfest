"""Two ways to rank tiles.

suspicion(): no labels yet. How far each tile sits from this floor's median,
in robust z units. Used to pick which tiles the inspector should check first.

classify(): once a few tiles are confirmed solid or hollow, TabPFN learns this
floor from them in context (no training run) and scores every other tile.
"""
import os

import numpy as np

from .taps import FEATURES

MIN_PER_CLASS = 2


def matrix(rows):
    X = np.array([[r[k] for k in FEATURES] for r in rows], dtype="float64")
    # frequencies and ratios span decades; logs keep one feature from dominating the distance
    return np.log1p(np.clip(X, 0, None))


def suspicion(rows):
    if not rows:
        return []
    X = matrix(rows)
    med = np.median(X, 0)
    mad = np.median(np.abs(X - med), 0) * 1.4826 + 1e-6
    z = np.abs(X - med) / mad
    return [round(float(v), 3) for v in np.sqrt((z ** 2).mean(1))]


_backend = None  # "local" or "api" once one has worked


def _local():
    from tabpfn import TabPFNClassifier
    return TabPFNClassifier(device="cpu", n_estimators=4)


def _api():
    token = os.environ.get("TABPFN_TOKEN")
    if not token:
        raise RuntimeError("TabPFN not available: install tabpfn locally or set TABPFN_TOKEN for the API")
    import tabpfn_client
    tabpfn_client.set_access_token(token)
    return tabpfn_client.TabPFNClassifier()


def _fit_predict(X, idx, y):
    """Local TabPFN first (only numbers, nothing leaves the machine), the API if
    local weights can't load. THUD_TABPFN=local|api pins one."""
    global _backend
    want = _backend or os.environ.get("THUD_TABPFN", "auto")
    order = ["local", "api"] if want == "auto" else [want]
    err = None
    for name in order:
        try:
            clf = _local() if name == "local" else _api()
            clf.fit(X[idx], y)
            _backend = name
            return name, clf.predict_proba(X)[:, list(clf.classes_).index(1)]
        except Exception as e:  # missing package, gated weights, no token
            err = e
    raise RuntimeError(f"TabPFN unavailable: {err}")


def classify(rows, labels):
    """labels: list aligned with rows, each 'solid', 'hollow' or None.
    Returns (backend, [P(hollow)] for every row)."""
    idx = [i for i, l in enumerate(labels) if l in ("solid", "hollow")]
    y = np.array([labels[i] == "hollow" for i in idx], dtype=int)
    if y.sum() < MIN_PER_CLASS or (len(y) - y.sum()) < MIN_PER_CLASS:
        raise ValueError(f"confirm at least {MIN_PER_CLASS} solid and {MIN_PER_CLASS} hollow tiles first")
    name, proba = _fit_predict(matrix(rows), idx, y)
    return name, [round(float(p), 4) for p in proba]
