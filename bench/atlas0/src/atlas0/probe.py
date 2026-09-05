"""The class probe and the authority tables (design §6.2, §6.3).

``fit`` trains a multinomial logistic-regression probe on residual
vectors (standardised, L2-regularised, Adam, full batch — numpy, no
torch) and ``probe_layers`` runs one per layer, reporting train and
test accuracy against chance. Items are balanced across the three-way
class (dense / sparse / absent) before the split, so chance is 1/3
and a majority baseline is the same number; the split is by item, so
a name in the test set is never in the training set (§6.2: trained on
held-out items, tested on more held-out items).

``authority`` asks whether the probed class has any say over the act:
P(act | probed class), the mutual information between them, and the
same for the act against the output entropy (binned) — the null that
entropy moves while the act does not (§6.3). Everything is bits.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

CLASS3 = ("dense", "sparse", "absent")


def class3(item: dict) -> str | None:
    """The three-way class of an eval item; ``None`` for rows outside it (mid, module-infer)."""
    c = item["class"]
    if c == "dense-real":
        return "dense"
    if c == "sparse-real":
        return "sparse"
    if c.startswith("absent"):
        return "absent"
    return None


def balanced_indices(items: list[dict], seed: int, per_class: int | None = None) -> tuple[list[int], list[str]]:
    """Indices of a class-balanced subset of ``items`` (seeded), and their three-way labels."""
    rng = np.random.default_rng(seed)
    by: dict[str, list[int]] = {c: [] for c in CLASS3}
    for i, it in enumerate(items):
        c = class3(it)
        if c is not None:
            by[c].append(i)
    n = min(len(v) for v in by.values())
    if per_class is not None:
        n = min(n, per_class)
    idx: list[int] = []
    for c in CLASS3:
        chosen = rng.permutation(by[c])[:n]
        idx.extend(int(i) for i in chosen)
    order = rng.permutation(len(idx))
    idx = [idx[i] for i in order]
    return idx, [class3(items[i]) for i in idx]


@dataclass
class Probe:
    W: np.ndarray
    b: np.ndarray
    mu: np.ndarray
    sd: np.ndarray
    classes: tuple[str, ...]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        z = ((X - self.mu) / self.sd) @ self.W + self.b
        z -= z.max(1, keepdims=True)
        p = np.exp(z)
        return p / p.sum(1, keepdims=True)

    def predict(self, X: np.ndarray) -> list[str]:
        return [self.classes[i] for i in self.predict_proba(X).argmax(1)]


def fit(X: np.ndarray, y: list[str], classes: tuple[str, ...] = CLASS3, l2: float = 1e-2,
        iters: int = 300, lr: float = 0.05, seed: int = 0) -> Probe:
    X = np.asarray(X, np.float64)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xs = (X - mu) / sd
    n, d = Xs.shape
    K = len(classes)
    Y = np.zeros((n, K))
    for i, c in enumerate(y):
        Y[i, classes.index(c)] = 1.0
    rng = np.random.default_rng(seed)
    W = rng.normal(0, 0.01, (d, K))
    b = np.zeros(K)
    mW, vW, mb, vb = np.zeros_like(W), np.zeros_like(W), np.zeros_like(b), np.zeros_like(b)
    b1, b2, eps = 0.9, 0.999, 1e-8
    for t in range(1, iters + 1):
        z = Xs @ W + b
        z -= z.max(1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(1, keepdims=True)
        g = (p - Y) / n
        gW = Xs.T @ g + l2 * W
        gb = g.sum(0)
        mW = b1 * mW + (1 - b1) * gW
        vW = b2 * vW + (1 - b2) * gW ** 2
        mb = b1 * mb + (1 - b1) * gb
        vb = b2 * vb + (1 - b2) * gb ** 2
        W -= lr * (mW / (1 - b1 ** t)) / (np.sqrt(vW / (1 - b2 ** t)) + eps)
        b -= lr * (mb / (1 - b1 ** t)) / (np.sqrt(vb / (1 - b2 ** t)) + eps)
    return Probe(W, b, mu, sd, tuple(classes))


def accuracy(pred: list[str], y: list[str]) -> float:
    return sum(p == t for p, t in zip(pred, y)) / max(1, len(y))


def probe_layers(acts: np.ndarray, y: list[str], train_frac: float = 0.5, seed: int = 0,
                 classes: tuple[str, ...] = CLASS3) -> dict:
    """One probe per layer over ``acts`` ``(n, L, d)``; a seeded item split.

    Returns per-layer train/test accuracy, the chance level (the
    majority share of the test labels — 1/K when balanced), the best
    layer by test accuracy, and that layer's test predictions with the
    indices they belong to.
    """
    n, L, _ = acts.shape
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_tr = int(n * train_frac)
    tr, te = perm[:n_tr], perm[n_tr:]
    y_tr = [y[i] for i in tr]
    y_te = [y[i] for i in te]
    chance = max(Counter(y_te).values()) / max(1, len(y_te))
    layers = []
    best = None
    for l in range(L):
        p = fit(acts[tr, l], y_tr, classes, seed=seed)
        tr_acc = accuracy(p.predict(acts[tr, l]), y_tr)
        pred_te = p.predict(acts[te, l])
        te_acc = accuracy(pred_te, y_te)
        layers.append({"layer": l, "train": round(tr_acc, 4), "test": round(te_acc, 4)})
        if best is None or te_acc > best[0]:
            best = (te_acc, l, pred_te)
    return {
        "n_train": int(n_tr), "n_test": int(n - n_tr), "chance": round(chance, 4),
        "layers": layers, "best_layer": best[1], "best_test": round(best[0], 4),
        "test_indices": [int(i) for i in te], "test_predictions": best[2],
    }


def mutual_information(a: list, b: list) -> float:
    """MI in bits between two paired categorical sequences (plug-in estimate)."""
    n = len(a)
    if n == 0:
        return 0.0
    pa, pb, pab = Counter(a), Counter(b), Counter(zip(a, b))
    mi = 0.0
    for (x, y), c in pab.items():
        mi += c / n * math.log2((c / n) / ((pa[x] / n) * (pb[y] / n)))
    return max(0.0, mi)


def entropy_bins(entropies: list[float], k: int = 4) -> list[str]:
    """Quantile bins of the output entropies, as labels ``q0`` … ``q{k-1}``."""
    if not entropies:
        return []
    qs = np.quantile(entropies, [i / k for i in range(1, k)])
    return [f"q{int(np.searchsorted(qs, e, side='right'))}" for e in entropies]


def authority(true_cls: list[str], probed_cls: list[str], act_cols: list[str], entropies: list[float]) -> dict:
    """§6.3: does the probed class have authority over the act?

    ``act_cols`` are confusion-matrix columns per item (``atlas0.acts``).
    Reports P(act | probed class), MI(act; probed), MI(act; true class),
    MI(act; entropy quartile) and the mean entropy per true class.
    """
    table: dict[str, dict[str, float]] = {}
    for c in sorted(set(probed_cls)):
        rows = [a for p, a in zip(probed_cls, act_cols) if p == c]
        cnt = Counter(rows)
        table[c] = {a: round(cnt[a] / len(rows), 4) for a in sorted(cnt)}
    ent_by_cls: dict[str, float] = {}
    for c in sorted(set(true_cls)):
        es = [e for t, e in zip(true_cls, entropies) if t == c]
        ent_by_cls[c] = round(float(np.mean(es)), 4) if es else 0.0
    return {
        "p_act_given_probed": table,
        "mi_act_probed": round(mutual_information(act_cols, probed_cls), 4),
        "mi_act_true": round(mutual_information(act_cols, true_cls), 4),
        "mi_act_entropy": round(mutual_information(act_cols, entropy_bins(entropies)), 4),
        "mi_probed_true": round(mutual_information(probed_cls, true_cls), 4),
        "entropy_by_true_class": ent_by_cls,
        "n": len(act_cols),
    }
