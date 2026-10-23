"""UML → esqueleto InvenioLang que compila (INV-3206) y ``api.codigo_desde_uml``."""

from __future__ import annotations

import pytest

from inveniolang import api, uml
from inveniolang.uml.modelo import Relacion

BIBLIOTECA = """
interface Prestable {
  + prestar(dias : entero) : logico
}
abstract class Recurso {
  # titulo : texto
  + codigo : texto = "R-1" {readOnly}
  + <<create>> Recurso(t : texto, anio : entero)
  + {abstract} describir() : texto
}
class Libro extends Recurso implements Prestable
class Socio {
  + Socio(nombre : texto)
}
class Biblioteca {
  + Biblioteca(s : Socio)
  + {static} crear() : Biblioteca
}
enum Estado {
  DISPONIBLE
  PRESTADO
}
class Caja<T> {
  - dato : T
  + obtener() : T
  + estado() : Estado
}
Biblioteca *-- Libro : principal
Biblioteca o-- Socio : socio
Biblioteca ..> Caja
"""


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_esqueleto_compila_y_completa_lo_que_falta(idioma):
    r = api.codigo_desde_uml(BIBLIOTECA, idioma)
    assert r.ok, r.errores
    codigo = r.salida[0]
    assert api.compilar(codigo).ok
    if idioma == "es":
        assert "abstracta clase Recurso {" in codigo
        assert "clase Libro hereda Recurso implementa Prestable {" in codigo
        assert 'padre("", 0);' in codigo  # el padre exige argumentos
        assert "Constructor añadido" in codigo
        assert "Exigido por Prestable" in codigo and "Exigido por Recurso" in codigo
        assert "publico texto titulo;" in codigo and "protegido (#)" in codigo
        assert '{readOnly}' in codigo and 'publico texto codigo = "R-1";' in codigo
        assert "este.principal = nuevo Libro();" in codigo
        assert "este.socio = s;" in codigo
        assert "Caja<entero> usaCaja;" in codigo
        assert "retornar Estado.DISPONIBLE;" in codigo
        assert "T valor;" in codigo and "retornar valor;" in codigo
        assert "// Por completar: implementa describir." in codigo
        assert codigo.rstrip().endswith("}") and "vacio main() {" in codigo
    else:
        assert "abstract class Recurso {" in codigo and "super(\"\", 0);" in codigo
        assert "this.principal = new Libro();" in codigo
        assert "// To complete: implement describir." in codigo
        assert "public static Biblioteca crear()" in codigo and "return null;" in codigo


def test_esqueleto_reproduce_el_diagrama():
    original = uml.leer_plantuml(BIBLIOTECA)
    codigo = api.codigo_desde_uml(original, "es").salida[0]
    vuelta = uml.desde_json(api.uml(codigo, formato="json").salida[0])
    for r in original.relaciones:
        assert r in vuelta.relaciones, r
    assert Relacion("composicion", "Biblioteca", "Libro", "principal", "0..1") in vuelta.relaciones


@pytest.mark.parametrize(
    ("diagrama", "es", "en"),
    [
        ("class A\nclass B {\n - hijos : A[]\n}", "arreglos de objetos", "arrays of objects"),
        ("class A\nclass B\nclass C\nC --|> A\nC --|> B", "herencia simple",
         "single inheritance"),
        ("interface I {\n - x : entero\n}", "no puede tener atributos", "cannot have attributes"),
        ("class A {\n - x : Fantasma\n}", "no es primitivo", "neither primitive"),
        ("class A {\n - mientras : entero\n}", "palabra reservada", "reserved word"),
        ("class A {\n + {abstract} f() : entero\n}", "no es una clase abstracta",
         "not an abstract class"),
        ("class A\nclass B\nA --|> B\nB --|> A", "forma un ciclo", "forms a cycle"),
        ("enum E {\n}", "al menos un valor", "at least one value"),
        ("class Caja<T>\nclass B\nB --|> Caja", "genérica", "generic"),
        ("class A {\n - v : vacio\n}", "solo puede ser el tipo de retorno", "return type"),
        ("class A {\n + f(x : entero, x : real) : vacio\n}", "dos veces", "twice"),
    ],
)
def test_lo_inexpresable_se_explica_en_ambos_idiomas(diagrama, es, en):
    r = api.codigo_desde_uml(diagrama, "es")
    assert not r.ok and not r.salida
    assert any(es in e for e in r.errores), r.errores
    r_en = api.codigo_desde_uml(diagrama, "en")
    assert any(en in e for e in r_en.errores), r_en.errores


def test_entradas_ilegibles():
    r = api.codigo_desde_uml('{"version": 1}', "en")
    assert not r.ok and "missing keys" in r.errores[0]
    r = api.codigo_desde_uml("class A {\n + x\n}", "es")
    assert not r.ok and r.errores[0].startswith("PlantUML, línea 2")
    assert not api.codigo_desde_uml(3.5).ok


def test_idioma_por_defecto_es_el_del_diagrama():
    codigo = api.codigo_desde_uml("class A {\n - n : int\n}").salida[0]
    assert "private int n;" in codigo
    m = uml.desde_json(api.uml("clase A { } vacio main() { }", formato="json").salida[0])
    assert "clase A {" in api.codigo_desde_uml(m).salida[0]


def test_generador_directo_lanza_modelo_no_generable():
    with pytest.raises(uml.ModeloNoGenerable) as e:
        uml.generar_codigo(uml.DiagramaClases())
    assert e.value.errores and "no classes" in e.value.errores[0].texto("en")
