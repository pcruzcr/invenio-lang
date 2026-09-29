# analytics/predict.py — v10 predictiva abandono
from __future__ import annotations
from typing import Dict, Any, List
import time


def risk_score(intentos: int, errores_top: List, tiempo_prom: float) -> float:
    # simple: muchos intentos + top IL-SEM-003 + tiempo alto = riesgo (0-1)
    base = min(intentos / 10, 1.0)
    err = 0.3 if any("IL-SEM-003" in str(e) for e in errores_top) else 0
    t = min(tiempo_prom / 300, 0.3)
    return round(min(1.0, base * 0.5 + err + t), 2)


def predict(lms_dashboard: Dict[str, Any]) -> Dict[str, Any]:
    top = lms_dashboard.get("top_errores", [])
    total = lms_dashboard.get("total_intentos", 0)
    return {"risk": risk_score(total, top, 120), "accion": "tutoría" if total > 5 else "seguir", "ts": time.time()}
