# backend/jit.py — v9 JIT stub (tracing)
from __future__ import annotations


class JITHotCounter:
    """Cuenta llamadas calientes para el JIT."""

    def __init__(self, threshold: int = 100):
        self.count: dict[str, int] = {}
        self.threshold = threshold

    def hit(self, func: str) -> bool:
        """Registra una llamada e indica si supera el umbral."""
        self.count[func] = self.count.get(func, 0) + 1
        return self.count[func] >= self.threshold

    def compile(self, func: str) -> str:
        """Compila la función caliente a nativo (demo)."""
        return f"JIT {func} @ {self.count[func]} hits → nativo"
