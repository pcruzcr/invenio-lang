"""Presupuestos de tiempo por fase y alertas sobre ``PipelineMetrics``.

INV-1026: la CLI (``--metrics``) adjunta estas alertas a las métricas; antes
solo las usaban las pruebas. Se eliminaron ``max_salida_chars`` (nadie lo
comprobaba) y ``dentro_de_presupuesto`` (sin llamadores).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Budget:
    """Presupuesto de tiempo para pipeline y fases."""

    max_total_ms: float = 5000.0
    max_fase_ms: float = 2000.0


@dataclass(frozen=True)
class Alerta:
    """Alerta monitorizable con nivel y contexto."""

    nivel: str  # INFO|WARN|CRIT
    mensaje: str
    fase: str = ""
    ms: float = 0.0


def evaluar_metricas(metrics: Any, budget: Budget | None = None) -> list[Alerta]:
    """Evalúa PipelineMetrics contra un presupuesto y retorna alertas."""
    budget = budget or Budget()
    alertas: list[Alerta] = []
    total = 0.0
    try:
        fases = metrics.to_dict().get("fases", [])
        total = float(metrics.to_dict().get("total_ms", 0.0))
    except Exception:
        return [Alerta(nivel="CRIT", mensaje="métricas ilegibles")]
    for f in fases:
        ms = float(f.get("ms", 0.0) or 0.0)
        fase = str(f.get("fase", "?"))
        if ms > budget.max_fase_ms:
            alertas.append(Alerta(nivel="WARN", mensaje=f"fase lenta: {fase}", fase=fase, ms=ms))
        if f.get("error"):
            alertas.append(Alerta(nivel="CRIT", mensaje=f"error en fase {fase}", fase=fase, ms=ms))
    if total > budget.max_total_ms:
        alertas.append(Alerta(nivel="CRIT", mensaje="presupuesto total excedido", ms=total))
    if not alertas:
        alertas.append(Alerta(nivel="INFO", mensaje="dentro de presupuesto", ms=total))
    return alertas
