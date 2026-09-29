# backend/jit.py — v9 JIT stub (tracing)
from __future__ import annotations
from typing import Dict


class JITHotCounter:
    def __init__(self, threshold: int = 100):
        self.count: Dict[str, int] = {}
        self.threshold = threshold

    def hit(self, func: str) -> bool:
        self.count[func] = self.count.get(func, 0) + 1
        return self.count[func] >= self.threshold

    def compile(self, func: str) -> str:
        return f"JIT {func} @ {self.count[func]} hits → nativo"
