"""Diagrama de objetos desde un paso de una traza de la Fase 2 (INV-3209, INV-3212)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest

from inveniolang import api
from inveniolang.visualizacion.modelo import a_json

NS = "{http://www.w3.org/2000/svg}"
LISTA = """
clase Nodo {
    publico entero valor;
    publico Nodo siguiente;
    Nodo(entero v) { este.valor = v; }
}
vacio main() {
    Nodo a = nuevo Nodo(1);
    Nodo b = nuevo Nodo(2);
    a.siguiente = b;
    b.siguiente = a;
    entero[3] numeros = {7, 8, 9};
    imprimir(a.valor);
}
"""


@pytest.fixture(scope="module")
def traza():
    t = api.trazar(LISTA)
    assert t.error is None
    return t


def _ultimo(traza):
    return len(traza.pasos) - 1


def test_texto_con_nombres_valores_y_enlaces(traza):
    texto = api.diagrama_objetos(traza, _ultimo(traza), formato="texto")
    assert "a : Nodo: valor = 1; siguiente = → b." in texto
    assert "b : Nodo: valor = 2; siguiente = → a." in texto
    assert "Enlaces: a.siguiente → b; b.siguiente → a." in texto
    en = api.diagrama_objetos(traza, _ultimo(traza), formato="texto", idioma="en")
    assert en.startswith("Object diagram of step") and "Links:" in en


def test_svg_accesible(traza):
    svg = api.diagrama_objetos(traza, _ultimo(traza))
    raiz = ET.fromstring(svg)
    assert raiz.get("role") == "img"
    assert raiz.find(NS + "title").text.startswith("Diagrama de objetos del paso")
    titulos = [t.text for t in raiz.iter(NS + "title")]
    assert "a.siguiente → b" in titulos and "b.siguiente → a" in titulos
    assert 'text-decoration="underline"' in svg  # notación UML de instancia
    assert svg == api.diagrama_objetos(traza, _ultimo(traza))
    assert "#0d1117" in api.diagrama_objetos(traza, _ultimo(traza), tema="oscuro")


def test_objeto_en_construccion_se_llama_este(traza):
    primero = next(i for i, p in enumerate(traza.pasos) if len(p.marcos) > 2)
    texto = api.diagrama_objetos(traza, primero, formato="texto")
    assert "este : Nodo" in texto


def test_arreglos_y_paso_sin_objetos():
    t = api.trazar("vacio main() { entero[2] v = {1, 2}; entero x = 3; }")
    assert "v : arreglo[2]: [0] = 1; [1] = 2." in api.diagrama_objetos(t, 1, formato="texto")
    vacio = api.diagrama_objetos("vacio main() { entero x = 3; }", 0, formato="texto")
    assert "No hay objetos" in vacio
    assert "No hay objetos" in api.diagrama_objetos("vacio main() { entero x = 3; }", 0)


def test_acepta_codigo_traza_y_dict(traza):
    paso = _ultimo(traza)
    como_dict = json.loads(a_json(traza))
    assert api.diagrama_objetos(como_dict, paso) == api.diagrama_objetos(traza, paso)
    assert api.diagrama_objetos(LISTA, paso) == api.diagrama_objetos(traza, paso)


def test_errores(traza):
    with pytest.raises(IndexError):
        api.diagrama_objetos(traza, len(traza.pasos))
    with pytest.raises(IndexError):
        api.diagrama_objetos(traza, -1)
    with pytest.raises(ValueError):
        api.diagrama_objetos(traza, 0, formato="png")
