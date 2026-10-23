"""INV-4406: acceso a miembro encadenado ``a.b.c`` (lectura, escritura y llamada).

Antes ``g.auto.motor.potencia`` era un error de sintaxis (IL-SIN-010): el
acceso a miembro era de un solo nivel y había que copiar cada eslabón en una
variable local. Ahora la gramática, el análisis semántico, el de tipos y el
intérprete lo admiten (spec: docs/InvenioLang_2.0_POO.md §14), sin conflictos
LALR nuevos, y el resto de herramientas (traductor es/en, formateador,
diagrama de flujo, trazador) lo conservan.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import api, flujo  # noqa: E402
from inveniolang.grammar_validator import validar_gramatica  # noqa: E402
from inveniolang.traductor import traducir  # noqa: E402

_spec = importlib.util.spec_from_file_location("conformidad", RAIZ / "pruebas" / "conformidad.py")
assert _spec is not None and _spec.loader is not None
conformidad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conformidad)

PROGRAMA = conformidad._cadena(
    "imprimir(g.auto.motor.potencia); imprimir(\" \");\n"
    "g.auto.motor.potencia += 5; imprimir(g.auto.motor.doble()); imprimir(\" \");\n"
    "g.tunear(); imprimir(g.auto.getMotor().potencia); imprimir(\" \");\n"
    "g.auto.km[2] = 4; imprimir(g.auto.km[2]);"
)


def test_grupo_de_conformidad_inveniolang11():
    res = conformidad.Resultados()
    conformidad.correr_inveniolang11(res, False)
    assert res.fallos == [] and res.ok == res.total == 17


def test_sin_conflictos_lalr_nuevos():
    informe = validar_gramatica()
    assert informe.ok and len(informe.shift_reduce) == 20 and not informe.reduce_reduce


def test_programa_encadenado_y_herramientas():
    r = api.ejecutar(PROGRAMA)
    assert r.ok, r.errores
    assert "".join(r.salida) == "100 210 115 4"
    ingles = traducir(PROGRAMA, "en")
    assert "g.auto.motor.potencia" in ingles and api.ejecutar(ingles).salida == r.salida
    formateado = api.formatear(PROGRAMA)
    assert formateado.ok and api.ejecutar(formateado.salida[0]).salida == r.salida
    modelo = flujo.modelo_desde_codigo(PROGRAMA)
    assert api.ejecutar(flujo.codigo_desde_modelo(modelo, "es")).salida == r.salida
    traza = api.trazar(PROGRAMA)
    assert traza.error is None and "".join(traza.salida) == "100 210 115 4"


def test_la_spec_documenta_el_acceso_encadenado():
    spec = (RAIZ / "docs" / "InvenioLang_2.0_POO.md").read_text(encoding="utf-8")
    assert "## 14. InvenioLang 11 — Acceso a miembro encadenado (INV-4406)" in spec
    assert "No se admite encadenar" not in spec
