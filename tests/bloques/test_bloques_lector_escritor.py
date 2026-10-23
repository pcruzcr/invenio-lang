"""Textos ⇄ bloques de valor (INV-4002, INV-4003): precedencia, literales y es/en."""

from __future__ import annotations

import pytest
from comun_bloques import bloques
from hypothesis import given, settings
from hypothesis import strategies as st

from inveniolang.bloques.catalogo import OPS_BINARIOS, OPS_UNARIOS
from inveniolang.bloques.escritor import Escritor
from inveniolang.bloques.lector import Ids, Lector
from inveniolang.flujo.extraccion import nodos_de_bloque


def _leer(texto, idioma="es"):
    return Lector(idioma, Ids()).texto_expresion(texto)


def _forma(b):
    """Estructura sin ids ni líneas."""
    if b is None:
        return None
    return (
        b.tipo,
        tuple(sorted(b.campos.items())),
        tuple((k, _forma(v)) for k, v in b.huecos.items()),
        tuple((k, tuple(_forma(x) for x in v)) for k, v in b.listas.items()),
    )


def _nuevo(tipo, **campos):
    return bloques.nuevo_bloque(tipo, "es", **campos)


hojas = st.one_of(
    st.sampled_from(["0", "7", "2.5", "10.25"]).map(lambda v: _nuevo("numero", valor=v)),
    st.sampled_from(["a", "b", "total"]).map(lambda v: _nuevo("variable", nombre=v)),
    st.sampled_from(['"x"', '"a\\nb"', "'c'"]).map(lambda v: _nuevo("texto", valor=v)),
    st.sampled_from(["verdadero", "falso"]).map(lambda v: _nuevo("logico", valor=v)),
    st.just(None).map(lambda _: _nuevo("nulo")),
)


def _binaria(op, i, d):
    b = _nuevo("binaria", op=op)
    b.huecos.update(izquierda=i, derecha=d)
    return b


def _unaria(op, v):
    b = _nuevo("unaria", op=op)
    b.huecos["valor"] = v
    return b


def _ternaria(c, v, f):
    b = _nuevo("ternaria")
    b.huecos.update(condicion=c, si_verdadero=v, si_falso=f)
    return b


def _indice(c, p):
    b = _nuevo("indice")
    b.huecos.update(coleccion=c, posicion=p)
    return b


def _metodo(o, args):
    b = _nuevo("llamada_metodo", nombre="m")
    b.huecos["objeto"] = o
    b.listas["argumentos"] = args
    return b


def _llamada(args):
    b = _nuevo("llamada", nombre="f")
    b.listas["argumentos"] = args
    return b


def _inc(pos, o):
    b = _nuevo("incremento", op="++", posicion=pos)
    b.huecos["objetivo"] = o
    return b


expresiones = st.recursive(
    hojas,
    lambda h: st.one_of(
        st.builds(_binaria, st.sampled_from(OPS_BINARIOS), h, h),
        st.builds(_unaria, st.sampled_from(OPS_UNARIOS), h),
        st.builds(_ternaria, h, h, h),
        st.builds(_indice, h, h),
        st.builds(_metodo, h, st.lists(h, max_size=2)),
        st.builds(_llamada, st.lists(h, max_size=3)),
        st.builds(_inc, st.sampled_from(["prefijo", "sufijo"]), h),
    ),
    max_leaves=12,
)


@settings(max_examples=300, deadline=None)
@given(expresiones)
def test_escribir_y_leer_conserva_el_arbol(b):
    """Los paréntesis que pone el escritor reproducen exactamente el anidamiento."""
    for idioma in ("es", "en"):
        texto = Escritor(idioma).expresion(b)
        assert _forma(_leer(texto, idioma)) == _forma(b), texto


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("(a + b) * c", "(a + b) * c"),
        ("a - (b - c)", "a - (b - c)"),
        ("(a - b) - c", "a - b - c"),
        ("a ?? (b ?? c)", "a ?? b ?? c"),
        ("(a ?? b) ?? c", "(a ?? b) ?? c"),
        ("- -a", "-(-a)"),
        ("-(--a)", "-(--a)"),
        ("(a ? b : c) ? d : e", "(a ? b : c) ? d : e"),
        ("((x))", "x"),
        ("1.50 + 0", "1.50 + 0"),
        ('"a\\"b"', '"a\\"b"'),
        ("este.x?.y(1)[2]", "este.x?.y(1)[2]"),
        ("nuevo Caja<entero>(1, 2)", "nuevo Caja<entero>(1, 2)"),
    ],
)
def test_parentesis_minimos_y_literales_tal_cual(texto, esperado):
    assert Escritor("es").expresion(_leer(texto)) == esperado


def test_palabras_clave_en_el_idioma_del_escritor():
    b = _leer("nuevo Pila(verdadero, nulo, este.x)")
    assert Escritor("en").expresion(b) == "new Pila(true, null, this.x)"
    assert b.listas["argumentos"][0].campos["valor"] == "verdadero"  # neutral
    assert _leer("true", "en").campos["valor"] == "verdadero"


def test_lambda_con_cuerpo_de_instrucciones():
    b = _leer("funcion(entero x) logico { si (x > 0) { retornar verdadero; } retornar falso; }")
    assert b.tipo == "lambda" and [x.tipo for x in b.listas["cuerpo"]] == ["si", "retornar"]
    assert Escritor("en").expresion(b) == (
        "function(entero x) logico { if (x > 0) { return true; } return false; }"
    )


def test_texto_mal_formado_explica_donde():
    with pytest.raises(bloques.ErrorBloques) as e:
        _leer("a + * b")
    assert "*" in e.value.texto("es") and "near" in e.value.texto("en")


def test_nodos_de_bloque_sin_contexto_semantico():
    """INV-4002: el cuerpo de una lambda se diagrama aunque use variables de fuera."""
    nodos = nodos_de_bloque("total = total + x; retornar total;", "es")
    assert [n.tipo for n in nodos] == ["proceso", "retornar"]
