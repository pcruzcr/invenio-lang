"""Editor de bloques de InvenioLang (Fase 4, equipo BLOQUES).

INV-4000..INV-4012: programación por bloques estilo Scratch/Blockly sobre el
**mismo árbol estructurado** que el diagrama de flujo (``inveniolang.flujo``):
cada instrucción de bloques es un nodo del diagrama con el mismo id, y la
vuelta a código usa la generación de ``flujo``.

* :mod:`.catalogo` — tipos de bloque, formas, huecos tipados, categorías
  accesibles y paleta (``catalogo_dict`` lo publica en JSON para la web).
* :mod:`.modelo` — contrato JSON v1 con ida y vuelta exacta.
* :mod:`.lector` / :mod:`.escritor` — textos InvenioLang ⇄ bloques.
* :mod:`.conversion` — código ⇄ bloques ⇄ diagrama de flujo, es/en.
* :mod:`.reglas` — encaje al soltar: familias, huecos tipados, inferencia.
* :mod:`.edicion` — operaciones puras y validación con el compilador real.
* :mod:`.texto` — rótulos y descripción accesible.
* :mod:`.diseno` — geometría del lienzo (zonas de soltar), sin Qt.

Documentación: ``docs/bloques.md``.
"""

from __future__ import annotations

from .catalogo import PALETA, TIPOS, catalogo_dict
from .conversion import (
    a_flujo,
    bloques_desde_codigo,
    codigo_con_lineas,
    codigo_desde_bloques,
    desde_flujo,
    traducir_bloques,
)
from .edicion import (
    Destino,
    Problema,
    desde_paleta,
    donde_esta,
    duplicar,
    editar,
    eliminar,
    envolver,
    insertar,
    mover,
    nuevo_bloque,
    nuevo_modelo,
    validar,
)
from .modelo import (
    Bloque,
    ErrorBloques,
    ModeloBloques,
    a_dict,
    a_json,
    desde_dict,
    desde_json,
    recorrer,
)
from .reglas import Ranura, motivo_rechazo
from .texto import describir, rotulo

__all__ = [
    "PALETA",
    "TIPOS",
    "Bloque",
    "Destino",
    "ErrorBloques",
    "ModeloBloques",
    "Problema",
    "Ranura",
    "a_dict",
    "a_flujo",
    "a_json",
    "bloques_desde_codigo",
    "catalogo_dict",
    "codigo_con_lineas",
    "codigo_desde_bloques",
    "como_modelo",
    "describir",
    "desde_dict",
    "desde_flujo",
    "desde_json",
    "desde_paleta",
    "donde_esta",
    "duplicar",
    "editar",
    "eliminar",
    "envolver",
    "insertar",
    "motivo_rechazo",
    "mover",
    "nuevo_bloque",
    "nuevo_modelo",
    "recorrer",
    "rotulo",
    "traducir_bloques",
    "validar",
]


def como_modelo(modelo: ModeloBloques | dict | str) -> ModeloBloques:
    """Acepta un ``ModeloBloques``, su ``dict`` o su texto JSON."""
    if isinstance(modelo, ModeloBloques):
        return modelo
    if isinstance(modelo, str):
        return desde_json(modelo)
    return desde_dict(modelo)
