# observability.py — Capa de observabilidad para InvenioLang
#
# Proporciona (nivel senior):
#   1. Logging estructurado JSON (machine-parseable, listo para ELK/Loki).
#   2. Correlación por run-id (trazabilidad end-to-end de una compilación).
#   3. Métricas por fase del pipeline (lexer→parser→semántico→tipos→run).
#   4. Decorador @traced para funciones críticas (timing + contexto).
#
# Patrones aplicados:
#   - Observer (MetricsObserver extiende patterns.Observer → eventos ErrorManager).
#   - Singleton-lite (configure_observability es idempotente).
#   - Facade (PipelineMetrics.mide agrupa logging+timing+métricas).
#
# Diseño: cero dependencias externas; logging a stderr por defecto para no
# contaminar la salida estándar del compilador (contrato §7 E/S).

from __future__ import annotations
import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional

from .patterns import Observer

__all__ = [
    "configure_observability",
    "get_logger",
    "new_run_id",
    "set_current_run",
    "get_current_run",
    "traced",
    "PipelineMetrics",
    "MetricsObserver",
    "emit_structured",
]

_LOG = logging.getLogger("inveniolang")
_configured = False

_RESERVED = frozenset(
    {
        "levelname",
        "name",
        "message",
        "asctime",
        "msg",
        "args",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "pathname",
        "module",
        "filename",
        "levelno",
    }
)


class JsonFormatter(logging.Formatter):
    """Formatea registros como una línea JSON (parseable por ELK/Loki)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": round(record.created, 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = repr(value)
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_observability(level: int = logging.INFO, json_output: bool = True, stream: Any = None) -> logging.Logger:
    """Idempotente: configura el handler del paquete una única vez."""
    global _configured
    if _configured:
        return _LOG
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter() if json_output else logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    _LOG.addHandler(handler)
    _LOG.setLevel(level)
    _LOG.propagate = False  # nunca invadir el root del host
    _configured = True
    return _LOG


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Logger hijo de 'inveniolang'. Configura bajo demanda."""
    if not _configured:
        configure_observability()
    return _LOG.getChild(name) if name else _LOG


def emit_structured(level: int, event: str, **fields: Any) -> None:
    """Emitir un evento estructurado con nombre explícito (recomendado)."""
    get_logger().log(level, event, extra={"event": event, **fields})


# ————— Correlación por run-id —————
_current_run: Dict[str, Any] = {}


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def set_current_run(run_id: str, **context: Any) -> None:
    _current_run["run_id"] = run_id
    _current_run.update(context)


def get_current_run() -> Dict[str, Any]:
    return dict(_current_run)


# ————— Métricas de pipeline (trazabilidad por fase) —————
class PipelineMetrics:
    """Registra duración y resultado por fase: lexer, parser, semantico,
    tipos, ejecucion. Serializable a dict/JSON para CI y panel docente."""

    def __init__(self) -> None:
        self.fases: list[Dict[str, Any]] = []

    @contextmanager
    def mide(self, fase: str, **meta: Any) -> Iterator[Dict[str, Any]]:
        entrada = {"fase": fase, "inicio": time.perf_counter(), **meta}
        self.fases.append(entrada)
        try:
            yield entrada
        except Exception as exc:
            entrada["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            entrada["ms"] = round((time.perf_counter() - entrada.pop("inicio")) * 1000, 2)
            get_logger("metrics").info(
                "fase_completada", extra={"fase": entrada["fase"], "ms": entrada["ms"], "error": entrada.get("error")}
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fases": [{k: v for k, v in f.items() if k != "inicio"} for f in self.fases],
            "total_ms": self.total_ms(),
        }

    def total_ms(self) -> float:
        return round(sum(f.get("ms", 0.0) for f in self.fases), 2)


# ————— Decorador de trazado —————
def traced(fase: Optional[str] = None) -> Callable:
    """Decorador: loguea duración en ms; en fallo registra tipo de error."""

    def deco(fn: Callable) -> Callable:
        nombre = fase or fn.__qualname__
        log = get_logger("trace")

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                resultado = fn(*args, **kwargs)
                log.debug("%s ok", nombre, extra={"ms": round((time.perf_counter() - t0) * 1000, 2)})
                return resultado
            except Exception as exc:
                log.error(
                    "%s fallo: %s",
                    nombre,
                    exc,
                    extra={"ms": round((time.perf_counter() - t0) * 1000, 2), "error_type": type(exc).__name__},
                )
                raise

        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper

    return deco


# ————— Observer de métricas (se conecta a ErrorManager) —————
class MetricsObserver(Observer):
    """Suscribir a ErrorManager para llevar contadores de errores/warnings
    sin acoplar el compilador a la capa de observabilidad (Observer)."""

    def __init__(self) -> None:
        self.errores = 0
        self.advertencias = 0
        self.por_codigo: Dict[str, int] = {}

    def update(self, event: str, data: Any) -> None:
        if event in ("error", "error_ejecucion") and data is not None:
            self.errores += 1
            codigo = getattr(data, "codigo", "?")
            self.por_codigo[codigo] = self.por_codigo.get(codigo, 0) + 1
        elif event == "advertencia" and data is not None:
            self.advertencias += 1
            codigo = getattr(data, "codigo", "?")
            self.por_codigo[codigo] = self.por_codigo.get(codigo, 0) + 1
