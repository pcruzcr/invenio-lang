"""Contrato JSON de la traza (INV-2001): ida y vuelta exacta y validación.

Todas fallan contra el árbol anterior: ``inveniolang.visualizacion`` no existía.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang.visualizacion.modelo import (  # noqa: E402
    Acceso,
    Estructura,
    Marco,
    NodoMonticulo,
    Paso,
    Traza,
    Valor,
    VariableMarco,
    a_dict,
    a_json,
    desde_dict,
    desde_json,
)
from inveniolang.visualizacion.traza import trazar  # noqa: E402

PROGRAMA_RICO = """
clase Nodo {
    publico entero valor;
    publico Nodo siguiente;
    Nodo(entero v) { este.valor = v; }
}
vacio main() {
    entero [3] a = {3, 1, 2};
    real [2][2] m;
    m[0][1] = 1.5;
    real infinito = 1.0e308 * 10.0;
    texto s = "hola \\"mundo\\" ñ";
    logico b = verdadero;
    Nodo cabeza = nuevo Nodo(1);
    cabeza.siguiente = nuevo Nodo(2);
    a[0] = a[1] + a[2];
    imprimir(s);
}
"""


def test_ida_y_vuelta_exacta_de_una_traza_real():
    traza = trazar(PROGRAMA_RICO)
    assert traza.error is None and traza.pasos
    texto = a_json(traza)
    assert desde_json(texto) == traza
    # También desde el dict (lo que consumen los renderizadores).
    assert desde_dict(json.loads(texto)) == traza
    assert a_dict(desde_json(texto)) == json.loads(texto)


def test_forma_json_del_contrato():
    traza = trazar(PROGRAMA_RICO)
    datos = json.loads(a_json(traza))
    assert set(datos) == {"version", "idioma", "fuente", "pasos", "truncada", "error", "salida"}
    assert datos["version"] == 1 and datos["idioma"] == "es"
    ultimo = datos["pasos"][-1]
    assert set(ultimo) == {
        "n",
        "linea",
        "columna",
        "marcos",
        "monticulo",
        "accesos",
        "salida_nueva",
        "estructuras",
    }
    # Claves del montículo: texto con el id; el nodo repite su id entero.
    for clave, nodo in ultimo["monticulo"].items():
        assert clave == str(nodo["id"])
        assert nodo["tipo"] in ("arreglo", "matriz", "objeto")
    tipos = {n["tipo"] for n in ultimo["monticulo"].values()}
    assert tipos == {"arreglo", "matriz", "objeto"}
    matriz = next(n for n in ultimo["monticulo"].values() if n["tipo"] == "matriz")
    assert matriz["elementos"][0][1] == {"t": "escalar", "tipo": "float", "v": 1.5}
    variables = ultimo["marcos"][-1]["variables"]
    assert variables["b"] == {"tipo": "bool", "valor": {"t": "escalar", "tipo": "bool", "v": True}}
    assert variables["cabeza"]["valor"]["t"] == "ref"
    # JSON estándar: el infinito viaja como texto, nunca como Infinity.
    assert variables["infinito"]["valor"] == {"t": "escalar", "tipo": "float", "v": "inf"}
    assert "Infinity" not in a_json(traza)


def test_construccion_manual_y_valores_por_defecto():
    paso = Paso(
        1,
        4,
        5,
        (Marco("main", 4, {"x": VariableMarco("int", Valor.escalar("int", 7))}),),
        {1: NodoMonticulo(1, "arreglo", None, (Valor.escalar("int", 1),))},
        (Acceso("escribe", "a", 1, (0,), None),),
        ("hola",),
        (Estructura("arreglo", 1, "a", (1,)),),
    )
    traza = Traza("en", "void main() {}", (paso,), salida=("hola",))
    assert desde_json(a_json(traza, indent=2)) == traza
    assert traza.version == 1 and traza.error is None and not traza.truncada


@pytest.mark.parametrize(
    ("mutar", "mensaje"),
    [
        (lambda d: d.update(version=2), "versión"),
        (lambda d: d.update(idioma="fr"), "idioma"),
        (lambda d: d.pop("pasos"), "faltan"),
        (lambda d: d["pasos"][0]["estructuras"][0].update(forma="hexagono"), "forma"),
        (lambda d: d["pasos"][0]["accesos"][0].update(op="borra"), "operación"),
        (lambda d: d["pasos"][0]["monticulo"]["1"].update(id=9), "id"),
        (lambda d: d["pasos"][0]["marcos"][0].update(linea="4"), "entero"),
    ],
)
def test_desde_json_rechaza_lo_que_no_cumple_el_contrato(mutar, mensaje):
    paso = Paso(
        1,
        1,
        1,
        (Marco("main", 1),),
        {1: NodoMonticulo(1, "arreglo", None, ())},
        (Acceso("lee", "a", 1, (0,)),),
        (),
        (Estructura("arreglo", 1, "a", (1,)),),
    )
    datos = Traza("es", "", (paso,)).a_dict()
    mutar(datos)
    with pytest.raises(ValueError, match=mensaje):
        desde_json(json.dumps(datos))


def test_desde_json_rechaza_texto_que_no_es_json():
    with pytest.raises(ValueError, match="JSON"):
        desde_json("{no es json")
