"""Diagramas UML bidireccionales: código ⇄ diagrama de clases, y diagrama de objetos.

INV-3210: sustituye al antiguo ``uml.py`` (51 líneas que solo escribían
PlantUML/Mermaid mínimos desde el AST). Piezas:

* :mod:`.modelo` — contrato JSON v1 del diagrama de clases (ida y vuelta exacta);
* :mod:`.desde_codigo` — programa (es/en) → modelo, con todas las relaciones;
* :mod:`.plantuml` — subconjunto documentado de PlantUML → modelo;
* :mod:`.exportar` — modelo → PlantUML / Mermaid ``classDiagram``;
* :mod:`.svg` y :mod:`.texto` — dibujo SVG accesible y descripción en frases;
* :mod:`.generador` — modelo → esqueleto InvenioLang que compila (es/en);
* :mod:`.objetos` — diagrama de objetos de un paso de una traza de la Fase 2.

La fachada pública está en ``inveniolang.api`` (``uml``, ``codigo_desde_uml``,
``diagrama_objetos``); ver ``docs/uml.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .desde_codigo import modelo_desde_ast
from .exportar import a_mermaid, a_plantuml
from .generador import ModeloNoGenerable, generar_codigo
from .modelo import DiagramaClases, ErrorUML, a_json, desde_json
from .objetos import describir_objetos, svg_objetos
from .plantuml import leer_plantuml
from .svg import svg_clases
from .texto import describir

__all__ = [
    "FORMATOS",
    "DiagramaClases",
    "ErrorUML",
    "ModeloNoGenerable",
    "a_json",
    "cargar_diagrama",
    "describir_objetos",
    "desde_json",
    "exportar",
    "generar_codigo",
    "leer_plantuml",
    "modelo_desde_ast",
    "svg_objetos",
]

FORMATOS = ("plantuml", "mermaid", "svg", "json", "texto")


def exportar(
    modelo: DiagramaClases, formato: str, idioma: str | None = None, tema: str = "claro"
) -> str:
    """El diagrama en ``formato`` (uno de :data:`FORMATOS`)."""
    if formato == "plantuml":
        return a_plantuml(modelo, idioma)
    if formato == "mermaid":
        return a_mermaid(modelo, idioma)
    if formato == "svg":
        return svg_clases(modelo, idioma, tema=tema)
    if formato == "json":
        return a_json(modelo)
    if formato == "texto":
        return describir(modelo, idioma)
    raise ValueError(f"formato UML inválido {formato!r}; válidos: {', '.join(FORMATOS)}")


def cargar_diagrama(fuente: Any, idioma: str = "es") -> DiagramaClases:
    """Acepta un :class:`DiagramaClases`, su ``dict``, su JSON o texto PlantUML.

    Un texto que empieza por ``{`` se lee como JSON; cualquier otro, como
    PlantUML (``idioma`` solo decide el idioma del modelo si el PlantUML no
    lo delata). :class:`ErrorUML` si no se puede leer.
    """
    if isinstance(fuente, DiagramaClases):
        return fuente
    if isinstance(fuente, Mapping):
        return DiagramaClases.desde_dict(dict(fuente))
    if isinstance(fuente, (bytes, bytearray)):
        fuente = fuente.decode("utf-8")
    if not isinstance(fuente, str):
        raise ErrorUML("UML.error.fuente", tipo=type(fuente).__name__)
    if fuente.lstrip().startswith("{"):
        return desde_json(fuente)
    return leer_plantuml(fuente, idioma)
