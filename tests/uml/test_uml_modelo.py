"""Contrato JSON v1 del diagrama de clases y su normalización (INV-3200, INV-3201)."""

from __future__ import annotations

import json

import pytest

from inveniolang import uml
from inveniolang.uml.modelo import (
    Atributo,
    Clasificador,
    Constructor,
    DiagramaClases,
    ErrorUML,
    Literal,
    Metodo,
    Parametro,
    Relacion,
    ValorInicial,
)
from inveniolang.uml.reglas import normalizar

COMPLETO = DiagramaClases(
    (
        Clasificador("Color", "enumeracion", literales=(Literal("ROJO"), Literal("VERDE"))),
        Clasificador(
            "Forma",
            "enumeracion",
            literales=(Literal("Circulo", (Parametro("radio", "int"),)), Literal("Punto")),
        ),
        Clasificador("Volador", "interfaz", metodos=(Metodo("volar", "string", abstracto=True),)),
        Clasificador(
            "Figura",
            "abstracta",
            atributos=(
                Atributo("nombre", "string", "-", valor_inicial=ValorInicial("string", "x")),
            ),
            constructores=(Constructor("+", (Parametro("n", "string"),)),),
            metodos=(Metodo("area", "float", abstracto=True),),
        ),
        Clasificador(
            "Circulo",
            atributos=(
                Atributo("r", "float", "-", valor_inicial=ValorInicial("float", -2.5)),
                Atributo("cuenta", "int", "+", estatico=True, valor_inicial=ValorInicial("int", 0)),
                Atributo("color", "Color", "-"),
            ),
            metodos=(Metodo("area", "float", sobrescribe=True),),
        ),
        Clasificador(
            "Caja",
            parametros_tipo=("T",),
            atributos=(Atributo("v", "T", "-", valor_inicial=ValorInicial("null", None)),),
            metodos=(Metodo("obtener", "T"),),
            modulo="caja.inv",
        ),
    ),
    (
        Relacion("herencia", "Circulo", "Figura"),
        Relacion("realizacion", "Circulo", "Volador"),
        Relacion("asociacion", "Circulo", "Color", "color", "0..1"),
        Relacion("dependencia", "Caja", "Forma"),
    ),
    "es",
)


def test_ida_y_vuelta_json_exacta():
    texto = uml.a_json(COMPLETO)
    assert uml.desde_json(texto) == COMPLETO
    assert DiagramaClases.desde_dict(json.loads(texto)) == COMPLETO
    assert json.loads(texto)["version"] == 1 and json.loads(texto)["tipo"] == "diagrama_clases"


@pytest.mark.parametrize(
    ("mutar", "fragmento"),
    [
        (lambda d: d.update(version=2), "versión 2"),
        (lambda d: d.pop("relaciones"), "relaciones"),
        (lambda d: d["clasificadores"][0].update(tipo="registro"), "uml.clasificadores[0].tipo"),
        (
            lambda d: d["relaciones"].append(
                {
                    "tipo": "dependencia",
                    "origen": "Circulo",
                    "destino": "Nada",
                    "rol": None,
                    "multiplicidad": None,
                }
            ),
            "Nada",
        ),
        (lambda d: d["relaciones"][2].update(multiplicidad="7"), "multiplicidad"),
        (lambda d: d["relaciones"][0].update(rol="x"), "uml.relaciones[0]"),
        (lambda d: d["clasificadores"].append(d["clasificadores"][0]), "dos veces"),
        (lambda d: d["clasificadores"][3]["atributos"][0]["valor_inicial"].update(v=3), "literal"),
    ],
)
def test_json_invalido_explica_donde(mutar, fragmento):
    datos = COMPLETO.a_dict()
    mutar(datos)
    with pytest.raises(ErrorUML) as e:
        DiagramaClases.desde_dict(datos)
    assert fragmento in e.value.texto("es")
    assert "Invalid JSON diagram" in e.value.texto("en")


def test_json_mal_escrito():
    with pytest.raises(ErrorUML) as e:
        uml.desde_json("{no es json")
    assert "JSON" in e.value.texto("en")


def test_normalizar_completa_y_es_idempotente():
    a_medias = DiagramaClases(
        (
            Clasificador("Motor"),
            Clasificador("Volador", "interfaz", metodos=(Metodo("volar"),)),
            Clasificador(
                "Auto",
                atributos=(Atributo("ruedas", "Motor"),),
                metodos=(Metodo("volar"),),
            ),
        ),
        (
            Relacion("composicion", "Auto", "Motor", "motor", "0..*"),
            Relacion("dependencia", "Auto", "Motor"),
            Relacion("realizacion", "Auto", "Volador"),
            Relacion("realizacion", "Auto", "Volador"),
        ),
    )
    n = normalizar(a_medias)
    auto = n.clasificador("Auto")
    assert [a.nombre for a in auto.atributos] == ["ruedas", "motor"]
    assert auto.atributos[1].tipo == "Motor[]"
    assert Relacion("asociacion", "Auto", "Motor", "ruedas", "0..1") in n.relaciones
    assert all(r.tipo != "dependencia" for r in n.relaciones)  # ya hay una relación más fuerte
    assert sum(r.tipo == "realizacion" for r in n.relaciones) == 1
    assert n.clasificador("Volador").metodos[0].abstracto
    assert auto.metodos[0].sobrescribe
    assert normalizar(n) == n


def test_error_uml_bilingue_con_argumentos_traducidos():
    e = ErrorUML("UML.json.invalido", ruta="uml", motivo=uml.modelo.M("UML.json.lista"))
    assert e.texto("es").endswith("se esperaba una lista")
    assert e.texto("en").endswith("a list is required")


def test_cargar_diagrama_acepta_todas_las_formas():
    assert uml.cargar_diagrama(COMPLETO) is COMPLETO
    assert uml.cargar_diagrama(COMPLETO.a_dict()) == COMPLETO
    assert uml.cargar_diagrama(uml.a_json(COMPLETO).encode()) == COMPLETO
    assert uml.cargar_diagrama("class A\n").clasificador("A") is not None
    with pytest.raises(ErrorUML):
        uml.cargar_diagrama(42)


def test_exportar_rechaza_formato_desconocido():
    with pytest.raises(ValueError):
        uml.exportar(COMPLETO, "png")
