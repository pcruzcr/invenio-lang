"""Código → modelo UML y ``api.uml`` en todos sus formatos (INV-3202, INV-3212)."""

from __future__ import annotations

from pathlib import Path

import pytest

from inveniolang import api, uml
from inveniolang.config import DEFAULT_CONFIG
from inveniolang.uml.modelo import Relacion, ValorInicial

RAIZ = Path(__file__).resolve().parents[2]

PROGRAMA = """
enumeracion Color { ROJO, VERDE }
enumeracion Forma { Circulo(entero radio), Punto }
interfaz Volador { publico abstracto texto volar(); }
abstracta clase Vehiculo {
    privado texto marca = "sin marca";
    Vehiculo(texto m) { este.marca = m; }
    publico abstracto entero ruedas();
}
clase Motor {
    publico entero hp = -3;
    publico estatico real factor = 1.5;
    publico logico listo = verdadero;
    Motor(entero p) { este.hp = p; }
}
clase Piloto { }
clase Hangar { publico estatico entero total() { retornar 0; } }
clase Caja<T> {
    privado T dato;
    publico T obtener() { retornar este.dato; }
}
clase Avion hereda Vehiculo implementa Volador {
    privado Motor motor;
    privado Piloto piloto;
    privado Color color;
    privado Avion escolta = nulo;
    Avion(Piloto p) {
        padre("Avion");
        este.motor = nuevo Motor(500);
        este.piloto = p;
    }
    publico entero ruedas() { retornar 3; }
    publico texto volar() {
        Caja<entero> c = nuevo Caja<entero>();
        entero n = Hangar.total();
        Forma f = nuevo Circulo(2);
        retornar "alto";
    }
}
vacio main() { }
"""


@pytest.fixture(scope="module")
def modelo():
    r = api.uml(PROGRAMA, formato="json")
    assert r.ok, r.errores
    return uml.desde_json(r.salida[0])


def test_clasificadores_y_miembros(modelo):
    tipos = {c.nombre: c.tipo for c in modelo.clasificadores}
    assert tipos == {
        "Color": "enumeracion", "Forma": "enumeracion", "Volador": "interfaz",
        "Vehiculo": "abstracta", "Motor": "clase", "Piloto": "clase", "Hangar": "clase",
        "Caja": "clase", "Avion": "clase",
    }
    # El genérico se muestra como plantilla, no expandido a Caja<entero>.
    assert modelo.clasificador("Caja").parametros_tipo == ("T",)
    forma = modelo.clasificador("Forma")
    assert forma.literales[0].parametros[0].tipo == "int"
    motor = modelo.clasificador("Motor")
    assert [a.valor_inicial for a in motor.atributos] == [
        ValorInicial("int", -3), ValorInicial("float", 1.5), ValorInicial("bool", True)
    ]
    assert motor.atributos[1].estatico and motor.atributos[0].visibilidad == "+"
    vehiculo = modelo.clasificador("Vehiculo")
    assert vehiculo.atributos[0].visibilidad == "-" and vehiculo.metodos[0].abstracto
    avion = modelo.clasificador("Avion")
    assert [m.sobrescribe for m in avion.metodos] == [True, True]
    assert modelo.clasificador("Hangar").metodos[0].estatico
    assert modelo.idioma == "es"


def test_relaciones_con_su_criterio(modelo):
    rels = set(modelo.relaciones)
    assert Relacion("herencia", "Avion", "Vehiculo") in rels
    assert Relacion("realizacion", "Avion", "Volador") in rels
    # creado con nuevo en el constructor → composición
    assert Relacion("composicion", "Avion", "Motor", "motor", "0..1") in rels
    # recibido como parámetro → agregación
    assert Relacion("agregacion", "Avion", "Piloto", "piloto", "0..1") in rels
    assert Relacion("asociacion", "Avion", "Color", "color", "0..1") in rels
    assert Relacion("asociacion", "Avion", "Avion", "escolta", "0..1") in rels
    # uso en cuerpos: genérico, acceso estático y variante de tipo suma
    for destino in ("Caja", "Hangar", "Forma"):
        assert Relacion("dependencia", "Avion", destino) in rels
    # la agregación ya cubre a Piloto (parámetro del constructor): sin dependencia extra
    assert Relacion("dependencia", "Avion", "Piloto") not in rels


def test_composicion_por_inicializacion_y_dependencia_por_firma():
    codigo = """
    clase Parte { }
    clase Otra { }
    clase Todo {
        privado Parte p = nuevo Parte();
        publico vacio usar(Otra o) { }
    }
    void main() { }
    """
    m = uml.desde_json(api.uml(codigo, formato="json").salida[0])
    assert Relacion("composicion", "Todo", "Parte", "p", "0..1") in m.relaciones
    assert Relacion("dependencia", "Todo", "Otra") in m.relaciones


def test_programa_en_ingles_y_modulos_importados():
    codigo = 'import "structures/stack";\nclass User { private Stack s; }\nvoid main() { }\n'
    r = api.uml(codigo, "prog.inv", formato="json", ruta_fuente=str(RAIZ / "prog.inv"))
    assert r.ok, r.errores
    m = uml.desde_json(r.salida[0])
    assert m.idioma == "en"
    pila = m.clasificador("Stack")
    assert pila is not None and pila.modulo is not None and "stack" in pila.modulo
    assert m.clasificador("User").modulo is None
    assert "+ push(v : int) : void" in api.uml(codigo, formato="plantuml",
                                               ruta_fuente=str(RAIZ / "p.inv")).salida[0]


def test_modulos_en_memoria():
    r = api.uml('importar "util.inv";\nvacio main() { }', "m.inv", formato="texto",
                modulos={"util.inv": "clase Util { }"})
    assert r.ok and "Util" in r.salida[0]


def test_programa_invalido_devuelve_diagnosticos_en_su_idioma():
    r = api.uml("clase A hereda B { } vacio main() { }", idioma="en")
    assert not r.ok and r.errores and not r.salida
    assert "B" in r.errores[0]


def test_firma_compatible_y_formatos():
    codigo = (RAIZ / "pruebas" / "arbol_binario.inv").read_text(encoding="utf-8")
    plant = api.uml(codigo, "arbol.inv", "plantuml", DEFAULT_CONFIG).salida[0]
    assert plant.startswith("@startuml") and "class Nodo" in plant
    assert api.uml(codigo, formato="mermaid").salida[0].startswith("classDiagram")
    svg = api.uml(codigo, formato="svg", tema="oscuro").salida[0]
    assert svg.startswith("<svg") and "#0d1117" in svg
    assert "Nodo" in api.uml(codigo, formato="texto", idioma="en").salida[0]
    for malo in ("png", "dot", ""):
        with pytest.raises(ValueError):
            api.uml(codigo, formato=malo)


def test_sin_clases():
    r = api.uml("vacio main() { }", formato="texto")
    assert r.ok and "no declara clases" in r.salida[0]
    assert api.uml("void main() { }", formato="texto", idioma="en").salida[0].startswith(
        "The program declares no classes"
    )
