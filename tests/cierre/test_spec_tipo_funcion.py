"""INV-4407: errata del tipo función en docs/InvenioLang_2.0_POO.md §12.5.

El ejemplo de la especificación declaraba ``funcion(entero, entero) entero
operar;``, que el parser rechaza (IL-SIN-010): el tipo función usa
``lista_params`` y cada parámetro lleva nombre. La prueba compila y ejecuta
literalmente el bloque de código de §12.5/12.6.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import api  # noqa: E402


def _bloque_12_5() -> str:
    spec = (RAIZ / "docs" / "InvenioLang_2.0_POO.md").read_text(encoding="utf-8")
    seccion = spec.split("### 12.5/12.6", 1)[1].split("### 12.7", 1)[0]
    m = re.search(r"```\r?\n(.*?)```", seccion, re.S)
    assert m is not None
    return m.group(1)


def test_el_ejemplo_de_la_spec_compila_y_da_7():
    r = api.ejecutar("vacio main() {\n" + _bloque_12_5() + "}\n")
    assert r.ok, r.errores
    assert "".join(r.salida) == "7"


def test_nombres_de_parametro_no_forman_parte_del_tipo():
    codigo = (
        "vacio main() {\n"
        "    funcion(entero a, entero b) entero f;\n"
        "    f = funcion(entero x, entero y) entero { retornar x * y; };\n"
        "    funcion(entero p, entero q) entero g = f;\n"
        "    imprimir(g(6, 7));\n}\n"
    )
    r = api.ejecutar(codigo)
    assert r.ok and "".join(r.salida) == "42"
