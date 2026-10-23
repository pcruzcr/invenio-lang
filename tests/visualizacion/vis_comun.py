"""Utilidades comunes de las pruebas del visualizador (INV-2240).

No se llama conftest.py: tests/ no es un paquete y dos conftest sin
__init__ chocarían por nombre de módulo.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
NOMBRES = sorted(p.stem for p in FIXTURES.glob("*.json"))


def cargar(nombre: str) -> dict:
    """Traza de ejemplo construida a mano según el contrato JSON de la Fase 2."""
    return json.loads((FIXTURES / f"{nombre}.json").read_text(encoding="utf-8"))


