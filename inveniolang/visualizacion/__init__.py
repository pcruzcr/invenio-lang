"""Visualización paso a paso de estructuras y algoritmos (Fase 2).

Parte TRAZA (INV-2000..):

* :mod:`.modelo` — contrato JSON de la traza (dataclasses inmutables);
* :mod:`.traza` — ejecuta un programa y produce su :class:`~.modelo.Traza`;
* :mod:`.clasificador` — reconoce pilas, colas, listas, árboles y grafos.

INV-2230: punto de entrada de la parte VISTA. Consume Trazas del contrato
JSON de la Fase 2 (``dict``, texto JSON u objeto ``Traza``) y produce:

* :func:`describir` — descripción accesible de un paso (es/en);
* :func:`svg_paso` / :func:`traza_svg` — dibujo SVG de un paso;
* :func:`html_traza` / :func:`traza_html` — reproductor HTML autónomo.

INV-2008: al integrar las dos partes, ``cargar_trazador`` y
``TrazadorNoDisponible`` (que cubrían la ausencia de ``traza.py`` mientras
los equipos trabajaban por separado) se retiraron: el trazador ya forma parte
del paquete y ese camino no podía ejecutarse nunca.
"""

from __future__ import annotations

from typing import Any

from .. import i18n
from .modelo import Traza, a_json, desde_json
from .render_svg import svg_paso
from .render_texto import TrazaInvalida, describir, normalizar_traza
from .reproductor import html_traza
from .traza import trazar


def traza_html(traza: Any, idioma: str | None = None) -> str:
    """HTML autónomo del reproductor para una Traza (dict, JSON u objeto)."""
    return html_traza(traza, idioma)


def traza_svg(traza: Any, n_paso: int, idioma: str | None = None, tema: str = "claro") -> str:
    """SVG del paso ``n_paso`` (posición 0..N-1 en ``pasos``) de una Traza."""
    t = normalizar_traza(traza)
    idi = i18n.normalizar_idioma(idioma) if idioma is not None else t["idioma"]
    total = len(t["pasos"])
    if not 0 <= n_paso < total:
        raise IndexError(i18n.t("VIS.error.paso_fuera", idi, n=n_paso, total=total))
    return svg_paso(t["pasos"][n_paso], idi, tema=tema)


__all__ = [
    "Traza",
    "TrazaInvalida",
    "a_json",
    "describir",
    "desde_json",
    "html_traza",
    "normalizar_traza",
    "svg_paso",
    "traza_html",
    "traza_svg",
    "trazar",
]
