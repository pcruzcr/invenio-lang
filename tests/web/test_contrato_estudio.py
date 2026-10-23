"""Contrato entre el estudio web y inveniolang.bloques (INV-4224, INV-4231)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from fixtures_estudio import DESTINO, generar

RAIZ = Path(__file__).resolve().parents[2]
TIENE_BLOQUES = importlib.util.find_spec("inveniolang.bloques") is not None
pytestmark = pytest.mark.skipif(
    not TIENE_BLOQUES,
    reason="inveniolang.bloques (equipo BLOQUES) se incorpora al fusionar f4_bloques",
)


def test_la_fixture_de_las_pruebas_de_node_es_la_vista_real_actual():
    assert (
        DESTINO.read_text(encoding="utf-8") == generar()
    ), "el contrato de bloques cambió: regenera con python tests/web/fixtures_estudio.py"


def test_envolver_en_ofrece_solo_contenedores_reales():
    from inveniolang import bloques

    html = (RAIZ / "web" / "estudio" / "index.html").read_text(encoding="utf-8")
    seleccion = re.search(r'<select id="sel-envolver">(.*?)</select>', html, re.S).group(1)
    tipos = re.findall(r'value="([a-z_]+)"', seleccion)
    assert tipos
    m = bloques.bloques_desde_codigo("vacio main() { entero x = 1; }")
    decl = m.programa[0].listas["cuerpo"][0].id
    for tipo in tipos:
        assert bloques.TIPOS[tipo].forma == "c"
        bloques.envolver(m, [decl], tipo)  # no lanza
