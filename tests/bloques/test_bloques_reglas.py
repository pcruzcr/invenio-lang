"""Encaje tipado al soltar (INV-4006): mismo veredicto que el compilador real."""

from __future__ import annotations

import pytest
from comun_bloques import bloques

from inveniolang import api
from inveniolang.bloques import edicion as E  # noqa: N812 - alias corto
from inveniolang.bloques import reglas

BASE = """
clase Punto {
    publico entero x;
}

real media(entero a, entero b) {
    retornar (a + b) / 2.0;
}

vacio main() {
    entero n = 1;
    real r = 2.5;
    texto s = "hola";
    logico ok = verdadero;
    entero[3] v = {1, 2, 3};
    Punto p = nuevo Punto();
    entero total = 0;
    texto saludo = "";
    imprimir(n);
}
"""


def _base():
    return bloques.bloques_desde_codigo(BASE)


def _main(m):
    return m.programa[-1]


def _decl(m, nombre):
    return next(b for b in _main(m).listas["cuerpo"] if b.campos.get("nombre") == nombre)


def _expr(texto):
    from inveniolang.bloques.lector import Ids, Lector

    return Lector("es", Ids()).texto_expresion(texto)


def _codigo_con(m, destino_id, hueco, texto):
    """Código del programa con ``texto`` escrito a mano en el hueco (sin pasar por reglas)."""
    import copy

    m = copy.deepcopy(m)
    m.buscar(destino_id).huecos[hueco] = _expr(texto)
    return bloques.codigo_desde_bloques(m)


@pytest.mark.parametrize(
    "decl, valor, familia",
    [
        ("n", '"x"', "texto"),  # entero <- texto
        ("n", "2.5", "real"),  # entero <- real (no hay conversión implícita)
        ("s", "nulo", "nulo"),  # texto <- nulo
        ("ok", "1", "entero"),  # logico <- entero
        ("n", "n < 2", "logico"),
        ("saludo", "s + s", None),  # válido: texto + texto
        ("r", "n", None),  # válido: entero se promueve a real
        ("p", "nulo", None),  # válido: objeto <- nulo
        ("total", "v[1] * 2", None),
        ("r", "media(1, 2)", None),
    ],
)
def test_declaracion_rechaza_lo_mismo_que_el_compilador(decl, valor, familia):
    m = _base()
    d = _decl(m, decl)
    motivo = bloques.motivo_rechazo(m, _expr(valor), d, bloques.Ranura("hueco", "valor"))
    compila = api.compilar(_codigo_con(m, d.id, "valor", valor)).ok
    assert (motivo is None) == compila, (motivo and motivo.texto(), compila)
    if familia is not None:
        assert motivo is not None and motivo.clave_mensaje == "BLQ.encaje.tipo"
        assert motivo.args_mensaje["recibido"].clave == f"BLQ.familia.{familia}"


@pytest.mark.parametrize(
    "texto, valido",
    [
        ("n < 3", True),
        ("ok && n > 0", True),
        ("n", False),
        ('"si"', False),
        ("n + 1", False),
        ("!ok", True),
        ("v[0] == 1", True),
    ],
)
def test_condicion_debe_ser_logica(texto, valido):
    m = _base()
    m = E.insertar(m, E.nuevo_bloque("mientras"), E.Destino(_main(m).id, "cuerpo"))
    mientras = _main(m).listas["cuerpo"][-1]
    motivo = bloques.motivo_rechazo(m, _expr(texto), mientras, bloques.Ranura("hueco", "condicion"))
    assert (motivo is None) == valido
    import copy

    m2 = copy.deepcopy(m)
    m2.buscar(mientras.id).huecos["condicion"] = _expr(texto)
    assert api.compilar(bloques.codigo_desde_bloques(m2)).ok == valido


@pytest.mark.parametrize(
    "izq, op, der, valido",
    [
        ("n", "+", "1", True),
        ("s", "+", "s", True),
        ("s", "+", "n", False),
        ("n", "%", "2", True),
        ("r", "%", "2", False),
        ("ok", "<", "ok", False),
        ("s", "<", "s", False),
        ("n", "&&", "ok", False),
        ("n", "==", '"a"', False),
        ("n", "==", "r", True),
    ],
)
def test_operandos(izq, op, der, valido):
    import copy

    m = _base()
    imp = _main(m).listas["cuerpo"][-1]
    binaria = E.nuevo_bloque("binaria", "es", op=op)
    m = E.eliminar(m, imp.huecos["valor"].id)
    m = E.insertar(m, binaria, E.Destino(imp.id, "valor"))
    m = copy.deepcopy(m)
    b = _main(m).listas["cuerpo"][-1].huecos["valor"]
    b.huecos["izquierda"] = _expr(izq)
    for x in bloques.recorrer([b.huecos["izquierda"]]):
        x.id = "izq" + x.id
    b.huecos["derecha"] = _expr(der)
    for x in bloques.recorrer([b.huecos["derecha"]]):
        x.id = "der" + x.id
    problemas = reglas.problemas_de_tipos(m)
    assert (problemas == []) == valido, [p.texto() for p in problemas]
    assert api.compilar(bloques.codigo_desde_bloques(m)).ok == valido


def test_formas_y_familias_de_lista():
    m = _base()
    main = _main(m)
    casos = [
        (
            E.nuevo_bloque("numero", "es", valor="1"),
            main,
            ("lista", "cuerpo"),
            "BLQ.encaje.lista.instruccion",
        ),
        (E.nuevo_bloque("romper"), main, ("lista", "parametros"), "BLQ.encaje.lista.parametro"),
        (
            E.nuevo_bloque("imprimir"),
            main.listas["cuerpo"][0],
            ("hueco", "valor"),
            "BLQ.encaje.no_valor",
        ),
        (
            E.nuevo_bloque("numero", "es", valor="1"),
            main.listas["cuerpo"][-1],
            ("hueco", "valor"),
            None,
        ),
        (E.nuevo_bloque("atributo"), main, ("lista", "cuerpo"), "BLQ.encaje.lista.instruccion"),
        (E.nuevo_bloque("imprimir"), None, ("lista", "programa"), "BLQ.encaje.solo_dentro"),
        (
            E.nuevo_bloque("numero", "es", valor="1"),
            m.programa[0],
            ("lista", "miembros"),
            "BLQ.encaje.lista.miembro",
        ),
    ]
    for bloque, padre, (clase, nombre), clave in casos:
        motivo = bloques.motivo_rechazo(m, bloque, padre, bloques.Ranura(clase, nombre, 0))
        assert (motivo.clave_mensaje if motivo else None) == clave, (bloque.tipo, nombre)
        if motivo is not None:
            assert motivo.texto("es") != motivo.texto("en")


def test_huecos_con_forma():
    m = _base()
    m = E.insertar(m, E.nuevo_bloque("asignar"), E.Destino(_main(m).id, "cuerpo"))
    asignar = _main(m).listas["cuerpo"][-1]
    for texto, clave in (
        ("n", None),
        ("v[0]", None),
        ("p.x", None),
        ("n + 1", "BLQ.encaje.hueco.asignable"),
        ("3", "BLQ.encaje.hueco.asignable"),
    ):
        motivo = bloques.motivo_rechazo(
            m, _expr(texto), asignar, bloques.Ranura("hueco", "destino")
        )
        assert (motivo.clave_mensaje if motivo else None) == clave
    m = E.insertar(m, E.nuevo_bloque("llamar"), E.Destino(_main(m).id, "cuerpo"))
    llamar = _main(m).listas["cuerpo"][-1]
    assert bloques.motivo_rechazo(m, _expr("n"), llamar, bloques.Ranura("hueco", "llamada"))
    assert (
        bloques.motivo_rechazo(m, _expr("media(1, 2)"), llamar, bloques.Ranura("hueco", "llamada"))
        is None
    )


def test_lista_con_maximo():
    m = _base()
    m = E.insertar(m, E.nuevo_bloque("para"), E.Destino(_main(m).id, "cuerpo"))
    para = _main(m).listas["cuerpo"][-1]
    m = E.insertar(m, E.nuevo_bloque("declarar", "es", nombre="i"), E.Destino(para.id, "inicio"))
    with pytest.raises(bloques.ErrorBloques) as e:
        E.insertar(m, E.nuevo_bloque("declarar", "es", nombre="j"), E.Destino(para.id, "inicio"))
    assert e.value.clave_mensaje == "BLQ.encaje.lleno"
    with pytest.raises(bloques.ErrorBloques) as e:
        E.insertar(m, E.nuevo_bloque("imprimir"), E.Destino(para.id, "paso"))
    assert e.value.clave_mensaje == "BLQ.encaje.lista.paso_para"


def test_campos_validados_con_el_lexer():
    with pytest.raises(bloques.ErrorBloques):
        E.nuevo_bloque("variable", "es", nombre="2x")
    with pytest.raises(bloques.ErrorBloques):
        E.nuevo_bloque("variable", "es", nombre="mientras")
    with pytest.raises(bloques.ErrorBloques):
        E.nuevo_bloque("declarar", "es", tipo="entero entero", nombre="x")
    with pytest.raises(bloques.ErrorBloques):
        E.nuevo_bloque("numero", "es", valor="1a")
    with pytest.raises(bloques.ErrorBloques):
        E.nuevo_bloque("binaria", "es", op="**")
    assert (
        E.nuevo_bloque("declarar", "en", tipo="Pila<int>", nombre="p").campos["tipo"] == "Pila<int>"
    )
    assert E.nuevo_bloque("parametro", "es", tipo="real[][]", nombre="m")
    assert E.nuevo_bloque("caso", "es", valor="-3").campos["valor"] == "-3"
    assert E.nuevo_bloque("declarar", "en").campos["tipo"] == "int"
