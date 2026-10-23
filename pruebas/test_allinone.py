"""Herramientas didácticas a través de la fachada ``inveniolang.api``.

INV-1008/1012/1013: esta suite probaba ``transpiler`` (emisores que escribían
``pass  # Assignment``), ``visual.trees``, ``studio``, ``types.gradual``,
``analytics.predict`` y ``toolchain``, módulos eliminados. Ahora cubre las
herramientas que quedan, por la API pública.
"""

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from inveniolang import api  # noqa: E402
from inveniolang.plagiarism import cluster  # noqa: E402

SUMA = "int suma(int a, int b) { retornar a + b; } void main() { imprimir(suma(1, 2)); }"


def test_ver_como_cinco_lenguajes():
    """La vista Rosetta traduce de verdad cuerpo y llamadas."""
    for objetivo in ("python", "c", "java", "csharp", "pascal"):
        r = api.ver_como(objetivo, SUMA)
        assert r.ok, objetivo
        assert "suma" in r.salida[0] and "a + b" in r.salida[0], objetivo


def test_uml_desde_programa_real():
    """PlantUML y Mermaid salen de las clases del AST."""
    codigo = (RAIZ / "pruebas" / "arbol_binario.inv").read_text(encoding="utf-8")
    plant = api.uml(codigo).salida[0]
    assert plant.startswith("@startuml") and "class Nodo" in plant
    assert "classDiagram" in api.uml(codigo, formato="mermaid").salida[0]


def test_ssa_de_un_ciclo_tiene_phi():
    """Un ciclo que actualiza su contador produce una φ en la cabecera."""
    r = api.ssa((RAIZ / "pruebas" / "ciclos.inv").read_text(encoding="utf-8"))
    assert r.ok and "φ(" in r.salida[0]


def test_complejidad_y_efectos():
    """Informes reales por subrutina."""
    codigo = (RAIZ / "pruebas" / "mergesort.inv").read_text(encoding="utf-8")
    assert "mergesort: O(n log n)" in api.complejidad(codigo).salida[0]
    assert "main: escribe en pantalla" in api.efectos(codigo).salida[0]


def test_plagio_agrupa_entregas_renombradas():
    """Renombrar variables no oculta una copia; un programa distinto queda fuera."""
    grupos = cluster(
        [
            "void main(){ int x=1; imprimir(x); }",
            "void main(){ int y=1; imprimir(y); }",
            "int f(int n){ retornar n*n; } void main(){ imprimir(f(9)); }",
        ]
    )
    assert grupos == [{0, 1}]
