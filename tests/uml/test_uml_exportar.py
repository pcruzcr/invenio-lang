"""PlantUML, Mermaid, SVG accesible y descripción textual (INV-3204, INV-3207, INV-3208)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from inveniolang import api, uml
from inveniolang.uml.modelo import Clasificador, DiagramaClases, Relacion
from inveniolang.visualizacion.render_svg import CLARO, OSCURO

RAIZ = Path(__file__).resolve().parents[2]
NS = "{http://www.w3.org/2000/svg}"


def _modelo(ruta: str) -> uml.DiagramaClases:
    codigo = (RAIZ / ruta).read_text(encoding="utf-8")
    r = api.uml(codigo, formato="json", ruta_fuente=str(RAIZ / ruta))
    assert r.ok, r.errores
    return uml.desde_json(r.salida[0])


@pytest.fixture(scope="module")
def decorator():
    return _modelo("curriculum/es/nivel09/11_patron_decorator.inv")


@pytest.fixture(scope="module")
def grafo():
    return _modelo("tests/stdlib/programas/grafo.inv")


def test_plantuml_completo(decorator):
    texto = uml.exportar(decorator, "plantuml")
    assert texto.startswith("@startuml") and texto.rstrip().endswith("@enduml")
    assert "abstract class Texto {" in texto
    assert "  + {abstract} renderizar() : texto" in texto
    assert "  + <<create>> Negrita(t : Texto)" in texto
    assert "Texto <|-- Negrita" in texto
    assert 'Negrita o-- "0..1" Texto : envuelto' in texto
    ingles = uml.exportar(decorator, "plantuml", "en")
    assert "renderizar() : string" in ingles


def test_mermaid_completo(decorator):
    texto = uml.exportar(decorator, "mermaid")
    assert texto.startswith("classDiagram")
    assert "<<abstract>>" in texto and "+renderizar() texto*" in texto
    assert '  Negrita o-- "0..1" Texto : envuelto' in texto
    m = DiagramaClases(
        (Clasificador("Caja", parametros_tipo=("T",)), Clasificador("I", "interfaz")), ()
    )
    assert "class Caja~T~" in uml.exportar(m, "mermaid")
    assert "<<interface>>" in uml.exportar(m, "mermaid")


def _cajas(svg: str):
    raiz = ET.fromstring(svg)
    cajas = []
    for g in raiz.iter(NS + "g"):
        rect = g.find(NS + "rect")
        titulo = g.find(NS + "title")
        if rect is not None and titulo is not None and rect.get("class", "").startswith("f-panel"):
            cajas.append(
                (titulo.text, *(float(rect.get(k)) for k in ("x", "y", "width", "height")))
            )
    return raiz, cajas


@pytest.mark.parametrize("ruta", [
    "curriculum/es/nivel09/11_patron_decorator.inv",
    "curriculum/en/level09/04_interfaces.inv",
    "tests/stdlib/programas/grafo.inv",
    "curriculum/es/nivel11/08_arbol_avl.inv",
])
def test_svg_accesible_sin_solapes_y_determinista(ruta):
    modelo = _modelo(ruta)
    svg = uml.exportar(modelo, "svg")
    assert svg == uml.exportar(modelo, "svg")
    raiz, cajas = _cajas(svg)
    assert raiz.get("role") == "img"
    assert raiz.find(NS + "title").text and raiz.find(NS + "desc").text == uml.exportar(
        modelo, "texto"
    )
    assert len(cajas) == len(modelo.clasificadores)
    ancho, alto = float(raiz.get("width")), float(raiz.get("height"))
    for i, (_, x, y, w, h) in enumerate(cajas):
        assert x >= 0 and y >= 0 and x + w <= ancho and y + h <= alto
        for _, x2, y2, w2, h2 in cajas[i + 1:]:
            assert x + w <= x2 or x2 + w2 <= x or y + h <= y2 or y2 + h2 <= y
    # cada relación es un grupo con nombre (no solo un trazo de color)
    titulos = {t.text for t in raiz.iter(NS + "title")}
    for r in modelo.relaciones:
        assert uml.texto.frase_relacion(r, modelo.idioma) in titulos


def test_svg_jerarquico_padres_arriba(decorator):
    _, cajas = _cajas(uml.exportar(decorator, "svg"))
    y = {titulo.split(".")[0].split()[-1]: yy for titulo, _, yy, _, _ in cajas}
    assert y["Texto"] < y["Negrita"] == y["Subrayado"] == y["TextoSimple"]


def test_svg_temas_y_notacion(decorator):
    claro = uml.exportar(decorator, "svg", tema="claro")
    oscuro = uml.exportar(decorator, "svg", tema="oscuro")
    assert CLARO["fondo"] in claro and OSCURO["fondo"] in oscuro
    assert "f-fondo" in claro  # clases de tema: el CSS del reproductor lo repinta
    assert 'font-style="italic"' in claro  # el nombre de la clase abstracta
    assert "«abstracta»" in claro and "{abstracto}" in claro
    assert "Leyenda" in claro and "herencia" in claro and "agregación" in claro
    assert "Legend" in uml.exportar(decorator, "svg", "en")


def test_svg_estatico_subrayado_y_dependencia_discontinua(grafo):
    m = DiagramaClases(
        (Clasificador("A"), Clasificador("B")), (Relacion("dependencia", "A", "B"),)
    )
    svg = uml.exportar(m, "svg")
    assert 'stroke-dasharray="7 5"' in svg
    estatico = api.uml(
        "clase A { publico estatico entero n = 0; } vacio main() { }", formato="svg"
    ).salida[0]
    assert 'text-decoration="underline"' in estatico


def test_svg_vacio():
    svg = uml.exportar(DiagramaClases(), "svg")
    assert "no declara clases" in svg and ET.fromstring(svg) is not None


def test_texto_es_y_en(decorator):
    es = uml.exportar(decorator, "texto")
    assert es.startswith("Diagrama de clases: 3 clases, 1 clase abstracta; 5 relaciones.")
    assert "Clase abstracta Texto." in es
    assert "renderizar(): texto (público, abstracto)" in es
    assert "Negrita agrega Texto mediante el atributo envuelto" in es
    assert "cero o uno" in es
    en = uml.exportar(decorator, "texto", "en")
    assert en.startswith("Class diagram: 3 classes, 1 abstract class; 5 relationships.")
    assert "Negrita aggregates Texto through attribute envuelto" in en
    assert "renderizar(): string (public, overrides)" in en
