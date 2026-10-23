"""INV-5006 / INV-5007: promoción de parámetros y recursión de procedimientos.

* Un argumento ``entero`` pasado a un parámetro ``real`` se promueve, como en
  una asignación. Antes ``real g(real x) { retornar x / 2; }`` con ``g(3)``
  daba 1.0 (división entera) en el intérprete y 1.5 en la máquina TAC.
* Un procedimiento recursivo sin caso base da IL-EJE-040, igual que una
  función. Antes escapaba un ``RecursionError`` de Python sin código ni línea.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import api  # noqa: E402

CLASE = """
clase Medidor {
    publico real escala;
    Medidor(real e) { este.escala = e; }
    publico real mitad(real x) { retornar x / 2; }
}
"""


@pytest.mark.parametrize(
    "programa",
    [
        "real g(real x) { retornar x / 2; }\nvacio main() { imprimir(g(3)); }",
        "vacio p(real x) { imprimir(x / 2); }\nvacio main() { p(3); }",
        CLASE + "vacio main() { Medidor m = nuevo Medidor(1); imprimir(m.mitad(3)); }",
        CLASE + "vacio main() { Medidor m = nuevo Medidor(3); imprimir(m.escala / 2); }",
        "vacio main() { funcion(real x) real f;"
        " f = funcion(real x) real { retornar x / 2; }; imprimir(f(3)); }",
    ],
    ids=["funcion", "procedimiento", "metodo", "constructor", "lambda"],
)
def test_entero_a_parametro_real_se_promueve(programa):
    r = api.ejecutar(programa)
    assert r.ok, r.errores
    assert r.salida == ("1.5",)


def test_el_entero_sigue_siendo_entero_en_parametro_entero():
    r = api.ejecutar("entero g(entero x) { retornar x / 2; }\nvacio main() { imprimir(g(3)); }")
    assert r.salida == ("1",)


def test_procedimiento_recursivo_sin_caso_base_da_il_eje_040():
    r = api.ejecutar("vacio p(entero n) { p(n + 1); }\nvacio main() { p(0); }")
    assert not r.ok
    assert len(r.errores) == 1 and "[IL-EJE-040]" in r.errores[0]
    assert ":1:" in r.errores[0]  # línea del procedimiento, no 0:0


def test_procedimiento_recursivo_con_caso_base_sigue_funcionando():
    r = api.ejecutar(
        "vacio cuenta(entero n) { si (n > 0) { imprimir(n); cuenta(n - 1); } }\n"
        "vacio main() { cuenta(3); }"
    )
    assert r.ok and "".join(r.salida) == "321"
