"""Lector del subconjunto documentado de PlantUML (INV-3205)."""

from __future__ import annotations

import pytest

from inveniolang import uml
from inveniolang.uml.modelo import ErrorUML, Relacion, ValorInicial

DIAGRAMA = """
@startuml
' Comentario de una línea
/' comentario
   de bloque '/
skinparam classAttributeIconSize 0
title Biblioteca
interface Prestable {
  + prestar(dias : entero) : logico
}
abstract class Recurso {
  # titulo : texto
  - {static} total : entero = 0
  + codigo : texto = "R-1" {readOnly}
  + <<create>> Recurso(t : texto)
  + {abstract} describir() : texto
}
class Libro extends Recurso implements Prestable {
  -- datos --
  - paginas : entero
  + Libro(t : texto, p : entero)
  + prestar(dias : entero) : logico
  + describir() : texto
}
class Revista {
  int numero
  String describir()
  void archivar(int caja, boolean urgente)
}
enum Estado {
  DISPONIBLE, PRESTADO
  PERDIDO(multa : real)
}
class Caja<T> {
  - dato : T
  + obtener() : T
}
class Socio
note "Una nota" as N1
note top of Libro
  texto libre
end note
Biblioteca *-- "0..*" Libro : libros
Biblioteca o-- Socio
Socio "0..1" --> Revista : favorita
Recurso <-- Socio
Libro ..> Estado
Revista --|> Recurso
@enduml
"""


@pytest.fixture(scope="module")
def modelo():
    return uml.leer_plantuml(DIAGRAMA)


def test_clasificadores(modelo):
    tipos = {c.nombre: c.tipo for c in modelo.clasificadores}
    assert tipos["Prestable"] == "interfaz" and tipos["Recurso"] == "abstracta"
    assert tipos["Estado"] == "enumeracion" and tipos["Biblioteca"] == "clase"
    assert modelo.clasificador("Caja").parametros_tipo == ("T",)
    assert [x.nombre for x in modelo.clasificador("Estado").literales] == [
        "DISPONIBLE", "PRESTADO", "PERDIDO"
    ]
    assert modelo.clasificador("Estado").literales[2].parametros[0].tipo == "float"
    assert modelo.idioma == "es"


def test_miembros(modelo):
    recurso = modelo.clasificador("Recurso")
    titulo, total, codigo = recurso.atributos
    assert (titulo.visibilidad, titulo.tipo) == ("#", "string")
    assert total.estatico and total.valor_inicial == ValorInicial("int", 0)
    assert codigo.constante and codigo.valor_inicial == ValorInicial("string", "R-1")
    assert recurso.constructores[0].parametros[0].tipo == "string"
    assert recurso.metodos[0].abstracto
    libro = modelo.clasificador("Libro")
    assert len(libro.constructores) == 1 and libro.metodos[0].sobrescribe
    revista = modelo.clasificador("Revista")
    assert revista.atributos[0].tipo == "int" and revista.atributos[0].visibilidad == "-"
    assert revista.metodos[0].retorno == "string"
    assert [p.tipo for p in revista.metodos[1].parametros] == ["int", "bool"]
    assert modelo.clasificador("Prestable").metodos[0].abstracto


def test_relaciones(modelo):
    rels = set(modelo.relaciones)
    assert Relacion("herencia", "Libro", "Recurso") in rels
    assert Relacion("herencia", "Revista", "Recurso") in rels
    assert Relacion("realizacion", "Libro", "Prestable") in rels
    assert Relacion("composicion", "Biblioteca", "Libro", "libros", "0..*") in rels
    # sin rol, el rol es el nombre de la clase destino en minúscula inicial
    assert Relacion("agregacion", "Biblioteca", "Socio", "socio", "0..1") in rels
    assert Relacion("asociacion", "Socio", "Revista", "favorita", "0..1") in rels
    assert Relacion("asociacion", "Socio", "Recurso", "recurso", "0..1") in rels
    assert Relacion("dependencia", "Libro", "Estado") in rels
    # una relación estructural crea el atributo que le falta
    biblioteca = modelo.clasificador("Biblioteca")
    assert [(a.nombre, a.tipo) for a in biblioteca.atributos] == [
        ("libros", "Libro[]"), ("socio", "Socio")
    ]


def test_una_clase_gana_al_alias_de_tipo():
    m = uml.leer_plantuml("class Texto\nclass Doc {\n - t : Texto\n - s : texto\n}\n")
    assert [a.tipo for a in m.clasificador("Doc").atributos] == ["Texto", "string"]


def test_idioma_deducido_de_los_tipos():
    assert uml.leer_plantuml("class A {\n - n : int\n}").idioma == "en"
    assert uml.leer_plantuml("class A {\n - n : entero\n}", "en").idioma == "es"
    assert uml.leer_plantuml("class A", "en").idioma == "en"


@pytest.mark.parametrize(
    ("texto", "linea", "es", "en"),
    [
        ("class A {\n  + x\n}", 2, "no se entiende el atributo", "cannot understand"),
        ("class A {\n  - n : entero = cosa\n}", 2, "valor inicial no admitido",
         "unsupported initial value"),
        ("class A {\n  - n : entero\n", 1, "falta la llave", "closing"),
        ("class A\nclass A", 2, "se declara dos veces", "declared twice"),
        ("A <<-->> B", 1, "flecha no admitida", "unsupported arrow"),
        ("class A\npackage algo {", 2, "no se entiende", "cannot understand"),
        ("class A\nA *-- B : 1x", 2, "debe ser un identificador", "must be an identifier"),
        ("class A {\n  - n : ent-ero\n}", 2, "tipo inválido", "invalid type"),
    ],
)
def test_errores_con_linea_y_bilingues(texto, linea, es, en):
    with pytest.raises(ErrorUML) as e:
        uml.leer_plantuml(texto)
    assert e.value.texto("es").startswith(f"PlantUML, línea {linea}:")
    assert es in e.value.texto("es")
    assert e.value.texto("en").startswith(f"PlantUML, line {linea}:")
    assert en in e.value.texto("en")


def test_texto_sin_clases():
    with pytest.raises(ErrorUML) as e:
        uml.leer_plantuml("@startuml\n@enduml\n")
    assert "no class" in e.value.texto("en")
