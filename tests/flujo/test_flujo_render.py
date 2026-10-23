"""Exportaciones: SVG accesible (INV-3005), Mermaid (INV-3006) y texto (INV-3004)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from comun import TODO, flujo

from inveniolang.flujo.render_svg import PALETAS

NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def modelo():
    return flujo.modelo_desde_codigo(TODO)


def _contraste(a: str, b: str) -> float:
    def lum(h):
        c = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("tema", ["claro", "oscuro", "auto"])
def test_svg_valido_y_accesible(modelo, tema):
    svg = flujo.exportar(modelo, "svg", "main", tema=tema)
    raiz = ET.fromstring(svg)
    assert raiz.get("role") == "img"
    assert raiz.find(f"{NS}title").text == "Diagrama de flujo de main"
    desc = raiz.find(f"{NS}desc").text
    assert "Decisión" in desc and "Sigue en" in desc
    grupos = raiz.findall(f".//{NS}g[@data-simbolo]")
    assert grupos and all(g.find(f"{NS}title") is not None for g in grupos)
    # Cada símbolo tiene forma propia (no se distingue sólo por color).
    formas = {g.get("data-simbolo"): g[1].tag.replace(NS, "") for g in grupos}
    assert formas["decision"] == "polygon" and formas["conector"] == "circle"
    assert formas["terminal"] == "rect" and formas["datos"] == "polygon"
    assert ("prefers-color-scheme" in svg) == (tema == "auto")


def test_svg_determinista_y_de_todo_el_programa(modelo):
    assert flujo.exportar(modelo, "svg") == flujo.exportar(modelo, "svg")
    raiz = ET.fromstring(flujo.exportar(modelo, "svg"))
    titulos = [g.find(f"{NS}title").text for g in raiz.findall(f"{NS}g[@role='group']")]
    assert len(titulos) == len(modelo.diagramas())


def test_tema_invalido(modelo):
    with pytest.raises(ValueError):
        flujo.exportar(modelo, "svg", tema="rosa")


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
def test_contraste_del_texto(tema):
    p = PALETAS[tema]
    for fondo in ("fondo", "terminal", "proceso", "decision", "datos", "predefinido", "conector"):
        assert _contraste(p["texto"], p[fondo]) >= 7, fondo
    assert _contraste(p["flecha"], p["fondo"]) >= 4.5


def test_mermaid(modelo):
    mm = flujo.exportar(modelo, "mermaid", "main", "en")
    lineas = mm.splitlines()
    assert lineas[0] == "flowchart TD"
    assert lineas[1].startswith("    accTitle: Flowchart of main")
    assert lineas[2].startswith("    accDescr: ")
    assert '(["Start"])' in mm and '{"i #lt; n"}' in mm and "[/\"" in mm and '[["' in mm
    assert "-.->" in mm  # saltos punteados
    todos = flujo.exportar(modelo, "mermaid")
    assert todos.count("subgraph ") == len(modelo.diagramas())


def test_texto_accesible_bilingue(modelo):
    es = flujo.exportar(modelo, "texto", "main")
    en = flujo.exportar(modelo, "texto", "main", "en")
    assert es.startswith("Diagrama de flujo de main.") and en.startswith("Flowchart of main.")
    assert "Salta a" in es and "Jumps to" in en
    assert "«Sí» →" in es and "“Yes” →" in en
    assert "Vuelve a" in es
    numerados = [x for x in es.splitlines()[1:] if x]
    assert all(x.split(".")[0].isdigit() for x in numerados)


def test_formato_invalido(modelo):
    with pytest.raises(ValueError):
        flujo.exportar(modelo, "png")
