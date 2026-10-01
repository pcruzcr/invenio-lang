# ir_ssa.py — v5 SSA + dominadores (extraído de ir/ssa.py, movido por conflicto ir.py)
from __future__ import annotations

from .cfg import BloqueCFG


def compute_dominators(cfg: dict[str, BloqueCFG], entry: str) -> dict[str, set[str]]:
    """Calcula dominadores del CFG."""
    dom: dict[str, set[str]] = {bid: set(cfg.keys()) for bid in cfg}
    dom[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for bid in cfg:
            if bid == entry:
                continue
            preds = cfg[bid].predecesores
            if not preds:
                continue
            new = set.intersection(*(dom[p] for p in preds)) | {bid}
            if new != dom[bid]:
                dom[bid] = new
                changed = True
    return dom


def to_ssa(cfg: dict[str, BloqueCFG]) -> dict[str, BloqueCFG]:
    """Convierte a SSA."""
    for blk in cfg.values():
        if len(blk.predecesores) > 1:
            blk.instrs.insert(0, "phi")
    return cfg
