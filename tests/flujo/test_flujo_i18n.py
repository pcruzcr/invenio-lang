"""Todo texto de los diagramas sale del catálogo bilingüe (INV-3004, INV-3010)."""

from __future__ import annotations

import re

from comun import RAIZ

from inveniolang.flujo.edicion import CAMPOS
from inveniolang.flujo.modelo import TIPOS
from inveniolang.i18n import en, es

FUENTES = [
    *sorted((RAIZ / "inveniolang" / "flujo").glob("*.py")),
    RAIZ / "inveniolang" / "gui" / "panel_flujo.py",
    RAIZ / "inveniolang" / "cli.py",
    RAIZ / "inveniolang" / "gui_qt.py",
]


def test_claves_literales_existen_en_ambos_idiomas():
    usadas = set()
    for ruta in FUENTES:
        usadas |= set(
            re.findall(r'"((?:FLU|CLI\.d?flu)\.[a-z_.]+)"', ruta.read_text(encoding="utf-8"))
        )
    assert len(usadas) > 60
    assert usadas - set(es.MENSAJES) == set()
    assert usadas - set(en.MENSAJES) == set()


def test_claves_compuestas_existen():
    claves = [f"FLU.gui.tipo.{t}" for t in TIPOS]
    claves += [f"FLU.gui.campo.{c}" for campos in CAMPOS.values() for c in campos]
    claves += ["FLU.gui.campo.caso", "FLU.gui.campo.condicion"]
    claves += [
        f"FLU.sim.{s}"
        for s in ("terminal", "proceso", "decision", "datos", "predefinido", "conector")
    ]
    roles = list(TIPOS) + [
        "inicio",
        "fin",
        "captura",
        "inicio_para",
        "paso",
        "union",
        "destino",
        "caida",
    ]
    claves += [f"FLU.rol.{r}" for r in roles]
    claves += [f"FLU.val.no_es.{t}" for t in ("proceso", "declaracion", "llamada")]
    claves += [
        f"FLU.gui.parte.{p}" for p in ("cuerpo", "rama", "caso", "sino", "por_defecto", "captura")
    ]
    claves += [
        f"FLU.gui.{g}.{f}"
        for g in ("formato", "filtro")
        for f in ("json", "svg", "mermaid", "texto")
    ]
    faltan = [c for c in claves if c not in es.MENSAJES or c not in en.MENSAJES]
    assert faltan == []
