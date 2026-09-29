# ir_ssa.py — v5 SSA + dominadores (extraído de ir/ssa.py, movido por conflicto ir.py)
from __future__ import annotations
from typing import Dict, Set
from .cfg import BloqueCFG


def compute_dominators(cfg: Dict[str, BloqueCFG], entry: str) -> Dict[str, Set[str]]:
    dom: Dict[str, Set[str]] = {bid: set(cfg.keys()) for bid in cfg}
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


def to_ssa(cfg: Dict[str, BloqueCFG]) -> Dict[str, BloqueCFG]:
    for blk in cfg.values():
        if len(blk.predecesores) > 1:
            blk.instrs.insert(0, "phi")
    return cfg
