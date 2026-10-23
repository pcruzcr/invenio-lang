"""Edición estructurada del diagrama y validación bilingüe (INV-3007)."""

from __future__ import annotations

import pytest
from comun import flujo

from inveniolang import api

U = flujo.Ubicacion


def _agregar(m, tipo, ubicacion=None, **campos):
    return flujo.insertar(m, "main", ubicacion or U(), flujo.nuevo_nodo(tipo, **campos))


def _programa_base():
    m = _agregar(flujo.nuevo_modelo("es"), "declaracion", texto="entero s = 0;")
    m = _agregar(m, "proceso", texto="s = s + i")
    m = _agregar(m, "escribir", texto="s")
    return m


def _ids(m):
    return [n.id for n in m.diagrama().cuerpo]


def test_operaciones_construyen_un_programa_que_corre():
    m = _programa_base()
    original = m
    m = flujo.envolver_en_ciclo(
        m, "main", [_ids(m)[1]], "para", inicio="entero i = 1", condicion="i <= 4", paso="i++"
    )
    assert _ids(original) == ["n1", "n2", "n3"]  # las operaciones no mutan
    assert flujo.validar(m) == []
    for idioma in ("es", "en"):
        assert api.ejecutar(flujo.codigo_desde_modelo(m, idioma)).salida == ("10",)


def test_envolver_en_si_mover_y_eliminar():
    m = _programa_base()
    m = flujo.envolver_en_si(m, "main", ["n2"], "s == 0")
    si = m.diagrama().cuerpo[1]
    assert si.tipo == "si" and si.ramas[0].cuerpo[0].id == "n2"
    m = flujo.mover(m, "main", "n3", U(si.id, "rama:0", 0))
    assert [n.id for n in m.diagrama().cuerpo[1].ramas[0].cuerpo] == ["n3", "n2"]
    m = flujo.eliminar(m, "main", si.id)
    assert _ids(m) == ["n1"]


def test_ramas_sino_si_casos_y_por_defecto():
    m = _agregar(flujo.nuevo_modelo("en"), "declaracion", texto="int x = 2")
    m = _agregar(m, "si", condicion="x == 1")
    si = _ids(m)[-1]
    m = flujo.agregar_rama(m, "main", si, "rama", "x == 2")
    m = flujo.agregar_rama(m, "main", si, "sino")
    m = _agregar(m, "escribir", U(si, "rama:1"), texto='"two"')
    m = _agregar(m, "escribir", U(si, "sino"), texto='"other"')
    m = _agregar(m, "segun", expresion="x")
    seg = _ids(m)[-1]
    m = flujo.agregar_rama(m, "main", seg, "caso", "2")
    m = flujo.agregar_rama(m, "main", seg, "por_defecto")
    m = _agregar(m, "escribir", U(seg, "caso:0"), texto="20")
    m = _agregar(m, "romper", U(seg, "caso:0"))
    m = _agregar(m, "escribir", U(seg, "por_defecto"), texto="0")
    assert flujo.validar(m) == []
    assert api.ejecutar(flujo.codigo_desde_modelo(m, "es")).salida == ("two", "20")
    m = flujo.quitar_rama(m, "main", si, "rama:0")
    m = flujo.editar(m, "main", si, "rama:0", "x != 2")
    assert api.ejecutar(flujo.codigo_desde_modelo(m)).salida == ("other", "20")
    with pytest.raises(flujo.ErrorFlujo):
        flujo.agregar_rama(m, "main", seg, "por_defecto")


@pytest.mark.parametrize(
    ("operacion", "es", "en"),
    [
        (lambda m: _agregar(m, "romper"), "romper", "break"),
        (lambda m: _agregar(m, "continuar"), "continuar", "continue"),
        (lambda m: flujo.eliminar(m, "main", "n99"), "n99", "n99"),
        (
            lambda m: flujo.envolver_en_si(m, "main", ["n1", "n3"], "x"),
            "consecutivos",
            "consecutive",
        ),
        (lambda m: _agregar(m, "proceso", texto="imprimir(1)"), "proceso", "process"),
        (
            lambda m: _agregar(m, "proceso", texto="x = 1; } vacio f() { y = 2"),
            "una instrucción",
            "one statement",
        ),
        (lambda m: _agregar(m, "si", condicion=""), "vacío", "empty"),
        (lambda m: flujo.editar(m, "main", "n1", "condicion", "x"), "condicion", "condicion"),
        (lambda m: _agregar(m, "escribir", U("n1", "cuerpo"), texto="1"), "cuerpo", "cuerpo"),
        (lambda m: flujo.envolver_en_ciclo(m, "main", ["n1"], "si", condicion="x"), "si", "si"),
    ],
)
def test_operaciones_invalidas_con_mensaje_bilingue(operacion, es, en):
    with pytest.raises(flujo.ErrorFlujo) as e:
        operacion(_programa_base())
    assert es in e.value.texto("es") and en in e.value.texto("en")


def test_no_se_mueve_un_nodo_dentro_de_si_mismo():
    m = _programa_base()
    m = flujo.envolver_en_ciclo(m, "main", ["n2"], "mientras", condicion="s < 3")
    ciclo = _ids(m)[1]
    with pytest.raises(flujo.ErrorFlujo) as e:
        flujo.mover(m, "main", ciclo, U(ciclo, "cuerpo", 0))
    assert "dentro de sí" in e.value.texto("es")
    # Sacar el romper del ciclo dejaría un salto inválido.
    m = _agregar(m, "romper", U(ciclo, "cuerpo"))
    romper = m.diagrama().cuerpo[1].cuerpo[-1].id
    with pytest.raises(flujo.ErrorFlujo):
        flujo.mover(m, "main", romper, U())


def test_validar_cuelga_el_error_del_compilador_del_nodo():
    m = flujo.editar(_programa_base(), "main", "n1", "texto", 'texto s = "a"')
    problemas = flujo.validar(m)
    assert problemas and problemas[0].clave == "main" and problemas[0].nodo == "n2"
    assert "IL-" in problemas[0].texto("en")


def test_validar_fragmento_por_campo():
    assert flujo.validar_fragmento("para", "condicion", "i < 3") == []
    assert flujo.validar_fragmento("leer", "texto", "n + 1")
    assert flujo.validar_fragmento("retornar", "texto", "") == []
    assert flujo.validar_fragmento("coincidir", "caso", "Circulo(r)") == []
    assert flujo.validar_fragmento("intentar", "variable", "e") == []
