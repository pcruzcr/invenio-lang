# studio/performance.py — v10 IDE all-in-one optimizado: eficiente, eficaz, ágil, seguro, estable
# Patrones: Strategy (cache), Observer (perf), Flyweight, Memento
from __future__ import annotations

import functools
import hashlib
import time
from collections.abc import Callable
from typing import Any


class PerfObserver:
    """Observador perf."""

    def __init__(self):
        self.metrics: dict[str, list] = {}

    def record(self, name: str, ms: float):
        """Registra la métrica."""
        self.metrics.setdefault(name, []).append(ms)

    def report(self) -> dict[str, float]:
        """Reporta el rendimiento."""
        return {k: sum(v) / len(v) for k, v in self.metrics.items()}


perf = PerfObserver()


def timed(name: str):
    """Mide la duración."""

    def deco(fn: Callable):
        """Decorador interno."""

        @functools.wraps(fn)
        def wrap(*a, **kw):
            """Envuelve con medición."""
            t0 = time.perf_counter()
            r = fn(*a, **kw)
            perf.record(name, (time.perf_counter() - t0) * 1000)
            return r

        return wrap

    return deco


class LRUCache:
    """Caché LRU."""

    def __init__(self, maxsize: int = 128):
        self.maxsize = maxsize
        self.cache: dict[str, Any] = {}
        self.order: list = []

    def get(self, key: str) -> Any | None:
        """Retorna la instancia compartida."""
        if key in self.cache:
            self.order.remove(key)
            self.order.append(key)
            return self.cache[key]
        return None

    def put(self, key: str, val: Any):
        """Guarda en caché."""
        if key in self.cache:
            self.order.remove(key)
        elif len(self.cache) >= self.maxsize:
            old = self.order.pop(0)
            self.cache.pop(old, None)
        self.cache[key] = val
        self.order.append(key)

    def clear(self):
        """Limpia el almacenamiento."""
        self.cache.clear()
        self.order.clear()


# Cache para lex/parse: evita re-tokenizar si código no cambió (hash)
lex_cache = LRUCache(64)
parse_cache = LRUCache(32)


def cached_lex(code: str, lexer_factory: Callable):
    """Lexer con caché."""
    h = hashlib.sha256(code.encode()).hexdigest()[:12]
    hit = lex_cache.get(h)
    if hit is not None:
        return hit
    res = lexer_factory()
    lex_cache.put(h, res)
    return res


# Estabilidad: circuit breaker para interpreter (evita colgar IDE)
class CircuitBreaker:
    """Corta rachas de fallos del intérprete."""

    def __init__(self, max_failures=3, reset_s=10):
        self.failures = 0
        self.last_fail = 0
        self.max_failures = max_failures
        self.reset_s = reset_s

    def call(self, fn: Callable, *a, **kw):
        """Ejecuta con caché."""
        if self.failures >= self.max_failures and time.time() - self.last_fail < self.reset_s:
            raise RuntimeError("Circuit open: demasiados fallos recientes")
        try:
            r = fn(*a, **kw)
            self.failures = 0
            return r
        except Exception:
            self.failures += 1
            self.last_fail = time.time()
            raise
