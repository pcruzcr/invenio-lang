"""Modelo JSON v1 del diagrama de flujo (INV-3000) y extracción código → modelo (INV-3001)."""

from __future__ import annotations

import json

import pytest
from comun import TODO, flujo

from inveniolang.flujo.modelo import TIPOS, a_dict, recorrer


@pytest.fixture(scope="module")
def modelo():
    return flujo.modelo_desde_codigo(TODO)


def test_representa_todas_las_construcciones_y_un_diagrama_por_subrutina(modelo):
    claves = [d.clave for d in modelo.diagramas()]
    assert claves == ["Contador.Contador", "Contador.sumar", "Contador.valor", "doble", "main"]
    tipos = {n.tipo for d in modelo.diagramas() for n in recorrer(d.cuerpo)}
    assert tipos == set(TIPOS)
    assert [d.tipo for d in modelo.diagramas()] == [
        "constructor",
        "metodo",
        "metodo",
        "funcion",
        "main",
    ]


def test_sino_si_se_aplana_en_ramas(modelo):
    para = next(n for n in modelo.diagrama().cuerpo if n.tipo == "para")
    si = para.cuerpo[0]
    assert [r.etiqueta for r in si.ramas] == ["i % 2 == 0", "i > 7"]
    assert si.alterno is not None and si.alterno[0].tipo == "llamada"


def test_ida_y_vuelta_json_exacta(modelo):
    texto = flujo.a_json(modelo)
    assert flujo.desde_json(texto) == modelo
    assert flujo.a_json(flujo.desde_json(texto)) == texto
    assert json.loads(texto)["formato"] == "inveniolang-flujo"
    assert json.loads(texto)["version"] == 1


def test_textos_conservan_el_codigo_del_estudiante():
    m = flujo.modelo_desde_codigo(
        'vacio main() { entero x = (1 + 2) * 3; // nota\n imprimir("a\\"b"); }'
    )
    cuerpo = m.diagrama().cuerpo
    assert cuerpo[0].texto == "entero x = (1 + 2) * 3"
    assert cuerpo[1].texto == '"a\\"b"'


def test_idioma_de_los_textos():
    m = flujo.modelo_desde_codigo("vacio main() { mientras (verdadero) { romper; } }", "en")
    assert m.idioma == "en"
    assert m.diagrama().firma == "void main()"
    assert m.diagrama().cuerpo[0].texto == "true"


def test_sobrecargas_tienen_claves_distintas():
    codigo = """
    clase A {
        publico entero f(entero x) { retornar x; }
        publico entero f(entero x, entero y) { retornar x + y; }
    }
    vacio main() { A a = nuevo A(); imprimir(a.f(1)); }
    """
    assert [d.clave for d in flujo.modelo_desde_codigo(codigo).diagramas()] == [
        "A.f",
        "A.f#2",
        "main",
    ]


def test_programa_invalido_lanza_error_con_diagnosticos():
    with pytest.raises(flujo.ErrorFlujo) as e:
        flujo.modelo_desde_codigo("vacio main() { entero x = ; }")
    assert e.value.diagnosticos
    assert "corrígelos" in e.value.texto("es") and "fix them" in e.value.texto("en")


@pytest.mark.parametrize(
    ("mutar", "fragmento_es", "fragmento_en"),
    [
        (lambda d: d.update(version=2), "versión 2", "version 2"),
        (lambda d: d.update(formato="otro"), "formato", "format"),
        (lambda d: d.update(extra=1), "claves desconocidas", "unknown keys"),
        (lambda d: d["elementos"][0].update(tipo="nada"), "no válido", "invalid value"),
        (
            lambda d: d["elementos"][-1]["diagrama"]["cuerpo"][1].update(id="n1"),
            "repetido",
            "repeated",
        ),
        (
            lambda d: d["elementos"][-1]["diagrama"]["cuerpo"][0].pop("texto"),
            "faltan",
            "missing",
        ),
    ],
)
def test_contrato_invalido_con_ruta_y_mensaje_bilingue(mutar, fragmento_es, fragmento_en):
    m = flujo.modelo_desde_codigo("vacio main() { entero x = 1; imprimir(x); }")
    d = a_dict(m)
    mutar(d)
    with pytest.raises(flujo.ErrorFlujo) as e:
        flujo.desde_dict(d)
    assert fragmento_es in e.value.texto("es") and "$" in e.value.texto("es")
    assert fragmento_en in e.value.texto("en")


def test_json_no_valido():
    with pytest.raises(flujo.ErrorFlujo):
        flujo.desde_json("{no es json")


def test_subrutina_desconocida(modelo):
    with pytest.raises(flujo.ErrorFlujo) as e:
        modelo.diagrama("nada")
    assert "main" in e.value.texto("en")
