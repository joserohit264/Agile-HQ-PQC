"""Mondrian multidimensional (K, L)-anonymization for EHR tables.

Strict top-down partitioning (LeFevre et al., 2006) extended with
distinct-L-diversity on the sensitive attribute.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class AnonResult:
    rows: list[dict]
    k: int
    l: int
    classes: int
    min_class_size: int
    avg_class_size: float
    info_loss: float          # Normalized Certainty Penalty in [0, 1]
    satisfied: bool
    suppressed: int


def _common_prefix(values: Sequence[str]) -> str:
    first = min(values); last = max(values)
    n = 0
    while n < min(len(first), len(last)) and first[n] == last[n]:
        n += 1
    return first[:n]


def _ok(part: list[dict], k: int, l: int, sens: str) -> bool:
    return len(part) >= k and len({r[sens] for r in part}) >= l


def mondrian_anonymize(records: list[dict], k: int, l: int,
                       numeric_qi: Sequence[str] = ("age",),
                       zip_qi: str | None = "zip", categorical_qi: Sequence[str] = ("sex",),
                       sensitive: str = "diagnosis") -> AnonResult:
    """Return a (k, l)-anonymized copy of ``records``."""
    if not records:
        return AnonResult([], k, l, 0, 0, 0.0, 0.0, True, 0)
    dims: list[tuple[str, str]] = [(q, "num") for q in numeric_qi]
    if zip_qi:
        dims.append((zip_qi, "zip"))
    dims += [(q, "cat") for q in categorical_qi]

    def key(r, d, kind):
        v = r[d]
        return int(v) if kind == "zip" else v

    # global spans for normalisation
    span = {}
    for d, kind in dims:
        if kind in ("num", "zip"):
            vals = [key(r, d, kind) for r in records]
            span[d] = max(vals) - min(vals) or 1
        else:
            span[d] = len({r[d] for r in records}) or 1

    def width(part, d, kind):
        if kind in ("num", "zip"):
            vals = [key(r, d, kind) for r in part]
            return (max(vals) - min(vals)) / span[d]
        return (len({r[d] for r in part}) - 1) / max(span[d] - 1, 1)

    # whole table must itself satisfy the constraints, otherwise suppress.
    if not _ok(records, k, l, sensitive):
        return AnonResult([], k, l, 0, 0, 0.0, 1.0, False, len(records))

    final: list[list[dict]] = []
    stack = [records]
    while stack:
        part = stack.pop()
        split = False
        for d, kind in sorted(dims, key=lambda dk: -width(part, *dk[::1])):
            if width(part, d, kind) == 0:
                continue
            if kind in ("num", "zip"):
                part_sorted = sorted(part, key=lambda r: key(r, d, kind))
                mid = len(part_sorted) // 2
                # keep equal values together (strict partitioning)
                pivot = key(part_sorted[mid], d, kind)
                left = [r for r in part_sorted if key(r, d, kind) < pivot]
                right = [r for r in part_sorted if key(r, d, kind) >= pivot]
                if not left or not right:
                    left = [r for r in part_sorted if key(r, d, kind) <= pivot]
                    right = [r for r in part_sorted if key(r, d, kind) > pivot]
            else:
                cats = sorted({r[d] for r in part})
                half = set(cats[: len(cats) // 2])
                left = [r for r in part if r[d] in half]
                right = [r for r in part if r[d] not in half]
            if left and right and _ok(left, k, l, sensitive) and _ok(right, k, l, sensitive):
                stack.extend([left, right])
                split = True
                break
        if not split:
            final.append(part)

    out, loss_total = [], 0.0
    for part in final:
        gen: dict[str, str] = {}
        ncp = 0.0
        for d, kind in dims:
            if kind == "num":
                vals = [r[d] for r in part]
                lo, hi = min(vals), max(vals)
                gen[d] = str(lo) if lo == hi else f"{lo}-{hi}"
            elif kind == "zip":
                zs = [str(r[d]) for r in part]
                p = _common_prefix(zs)
                gen[d] = p + "*" * (len(zs[0]) - len(p))
            else:
                cs = sorted({r[d] for r in part})
                gen[d] = cs[0] if len(cs) == 1 else "*"
            ncp += width(part, d, kind)
        loss_total += (ncp / len(dims)) * len(part)
        for r in part:
            row = {sensitive: r[sensitive]}
            row.update(gen)
            out.append(row)

    sizes = [len(p) for p in final]
    sat = all(_ok(p, k, l, sensitive) for p in final)
    return AnonResult(out, k, l, len(final), min(sizes), float(np.mean(sizes)),
                      loss_total / len(records), sat, 0)


def verify_k_l(rows: list[dict], k: int, l: int, qi: Sequence[str], sensitive: str) -> bool:
    """Independent check on a released table."""
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault(tuple(r[q] for q in qi), []).append(r[sensitive])
    return all(len(v) >= k and len(set(v)) >= l for v in groups.values())
