"""Diagramas de flujo bidireccionales de InvenioLang (Fase 3, equipo FLUJO).

INV-3000..INV-3010: sustituye a ``flowchart.py`` (dibujo de un bloque, sin
modelo ni vuelta a código) y a ``flowchart_builder.py`` (edición parcial de
``main`` sobre el AST). Piezas:

* :mod:`.modelo` — contrato JSON v1 (árbol estructurado, un diagrama por
  subrutina, método y constructor).
* :mod:`.extraccion` — código → modelo; :mod:`.generacion` — modelo → código
  (es/en, con el formateador del proyecto).
* :mod:`.esquema` — símbolos ISO 5807 y geometría sin solapes;
  :mod:`.render_svg`, :mod:`.render_mermaid`, :mod:`.render_texto`.
* :mod:`.edicion` — operaciones estructuradas y validación bilingüe.

Documentación: ``docs/diagramas_de_flujo.md``.
"""

from __future__ import annotations

from .. import i18n
from .edicion import (
    CAMPOS,
    Problema,
    Ubicacion,
    agregar_rama,
    editar,
    eliminar,
    envolver_en_ciclo,
    envolver_en_si,
    insertar,
    mover,
    nuevo_modelo,
    nuevo_nodo,
    quitar_rama,
    validar,
    validar_fragmento,
)
from .esquema import Esquema, construir_esquema
from .extraccion import modelo_desde_codigo
from .generacion import codigo_desde_modelo, traducir_modelo
from .modelo import ErrorFlujo, ModeloFlujo, Nodo, a_json, desde_dict, desde_json
from .render_mermaid import mermaid_esquemas
from .render_svg import svg_esquema, svg_varios
from .render_texto import describir_esquema

__all__ = [
    "CAMPOS",
    "FORMATOS",
    "ErrorFlujo",
    "Esquema",
    "ModeloFlujo",
    "Nodo",
    "Problema",
    "Ubicacion",
    "a_json",
    "agregar_rama",
    "codigo_desde_modelo",
    "como_modelo",
    "desde_dict",
    "desde_json",
    "editar",
    "eliminar",
    "envolver_en_ciclo",
    "envolver_en_si",
    "esquemas",
    "exportar",
    "insertar",
    "modelo_desde_codigo",
    "mover",
    "nuevo_modelo",
    "nuevo_nodo",
    "quitar_rama",
    "traducir_modelo",
    "validar",
    "validar_fragmento",
]

FORMATOS = ("json", "svg", "mermaid", "texto")


def como_modelo(modelo: ModeloFlujo | dict | str) -> ModeloFlujo:
    """Acepta un ``ModeloFlujo``, su ``dict`` o su texto JSON."""
    if isinstance(modelo, ModeloFlujo):
        return modelo
    if isinstance(modelo, str):
        return desde_json(modelo)
    return desde_dict(modelo)


def esquemas(
    modelo: ModeloFlujo, subrutina: str | None = None, idioma: str | None = None
) -> list[Esquema]:
    """Esquemas dibujables: el de ``subrutina`` o, con ``None``, todos."""
    elegidos = [modelo.diagrama(subrutina)] if subrutina is not None else modelo.diagramas()
    if not elegidos:
        raise ErrorFlujo("FLU.error.sin_diagramas")
    return [construir_esquema(d, modelo.idioma, idioma) for d in elegidos]


def exportar(
    modelo: ModeloFlujo,
    formato: str = "json",
    subrutina: str | None = None,
    idioma: str | None = None,
    tema: str = "claro",
) -> str:
    """El modelo en ``formato`` (``json``, ``svg``, ``mermaid`` o ``texto``).

    ``subrutina`` (clave como ``main``, ``suma``, ``Pila.apilar``) elige un
    diagrama para svg/mermaid/texto; ``None`` incluye todos. El JSON es
    siempre el programa completo (es lo que permite volver a código), pero
    ``subrutina`` se valida igual. ``idioma`` es el de las etiquetas.
    """
    if formato not in FORMATOS:
        raise ValueError(f"formato inválido {formato!r}; válidos: {', '.join(FORMATOS)}")
    if formato == "json":
        if subrutina is not None:
            modelo.diagrama(subrutina)
        return a_json(modelo)
    lista = esquemas(modelo, subrutina, idioma)
    destino = lista[0].idioma
    titulo = lista[0].titulo if len(lista) == 1 else i18n.t("FLU.titulo_programa", destino)
    if formato == "svg":
        return svg_esquema(lista[0], tema) if len(lista) == 1 else svg_varios(lista, titulo, tema)
    texto = "\n\n".join(describir_esquema(e) for e in lista)
    if formato == "texto":
        return texto + "\n"
    return mermaid_esquemas(lista, titulo, texto)
