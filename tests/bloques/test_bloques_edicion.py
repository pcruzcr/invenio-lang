"""Edición pura de bloques y validación completa (INV-4008)."""

from __future__ import annotations

import copy

import pytest
from comun_bloques import TODO, bloques

from inveniolang import api
from inveniolang.bloques import edicion as E  # noqa: N812 - alias corto

PROGRAMA = """
vacio main() {
    entero n = 3;
    imprimir(n);
    n = n + 1;
}
"""


def _m():
    return bloques.bloques_desde_codigo(PROGRAMA)


def _cuerpo(m):
    return m.programa[0].listas["cuerpo"]


def test_construir_un_programa_desde_cero():
    m = E.nuevo_modelo("en")
    main = m.programa[0]
    assert bloques.codigo_desde_bloques(m) == "void main() {\n}\n"
    m = E.insertar(m, E.nuevo_bloque("declarar", "en", nombre="i"), E.Destino(main.id, "cuerpo"))
    decl = _cuerpo(m)[0]
    m = E.insertar(m, E.desde_paleta("numero", "en", valor="0"), E.Destino(decl.id, "valor"))
    m = E.insertar(m, E.nuevo_bloque("mientras"), E.Destino(main.id, "cuerpo"))
    ciclo = _cuerpo(m)[1]
    m = E.insertar(m, E.desde_paleta("menor"), E.Destino(ciclo.id, "condicion"))
    cond = _cuerpo(m)[1].huecos["condicion"]
    m = E.insertar(m, E.desde_paleta("variable", "en", nombre="i"), E.Destino(cond.id, "izquierda"))
    m = E.insertar(m, E.desde_paleta("numero", "en", valor="3"), E.Destino(cond.id, "derecha"))
    m = E.insertar(m, E.desde_paleta("imprimir"), E.Destino(ciclo.id, "cuerpo"))
    imp = _cuerpo(m)[1].listas["cuerpo"][0]
    m = E.insertar(m, E.desde_paleta("variable", "en", nombre="i"), E.Destino(imp.id, "valor"))
    m = E.insertar(m, E.desde_paleta("incrementar"), E.Destino(ciclo.id, "cuerpo"))
    inc = _cuerpo(m)[1].listas["cuerpo"][1]
    m = E.insertar(m, E.desde_paleta("variable", "en", nombre="i"), E.Destino(inc.id, "objetivo"))
    assert E.validar(m) == []
    codigo = bloques.codigo_desde_bloques(m)
    assert "while (i < 3) {" in codigo
    assert api.ejecutar(codigo).salida == ("0", "1", "2")


def test_operaciones_son_puras():
    m = _m()
    foto = bloques.a_dict(m)
    ident = _cuerpo(m)[1].id
    for op in (
        lambda x: E.eliminar(x, ident),
        lambda x: E.duplicar(x, ident),
        lambda x: E.mover(x, ident, E.Destino(x.programa[0].id, "cuerpo", 0)),
        lambda x: E.envolver(x, [ident], "si"),
        lambda x: E.editar(x, _cuerpo(x)[0].id, "nombre", "k"),
        lambda x: E.insertar(x, E.nuevo_bloque("romper"), E.Destino(x.programa[0].id, "cuerpo")),
    ):
        try:
            op(m)
        except bloques.ErrorBloques:
            pass
        assert bloques.a_dict(m) == foto


def test_mover_eliminar_duplicar():
    m = _m()
    main = m.programa[0].id
    imp, asig = _cuerpo(m)[1].id, _cuerpo(m)[2].id
    m2 = E.mover(m, asig, E.Destino(main, "cuerpo", 1))
    assert [b.id for b in _cuerpo(m2)][1:] == [asig, imp]
    m3 = E.duplicar(m2, imp)
    assert len(_cuerpo(m3)) == 4 and _cuerpo(m3)[3].id != imp
    assert bloques.codigo_desde_bloques(m3).count("imprimir(n);") == 2
    m4 = E.eliminar(m3, imp)
    assert imp not in {b.id for b in bloques.recorrer(m4.programa)}
    # Eliminar un valor deja su hueco vacío y la validación lo señala.
    valor = _cuerpo(m)[0].huecos["valor"].id
    m5 = E.eliminar(m, valor)
    assert [p.error.clave_mensaje for p in E.validar(m5)] == []  # declarar sin valor es válido
    m6 = E.eliminar(m, _cuerpo(m)[1].huecos["valor"].id)
    problemas = E.validar(m6)
    assert problemas and problemas[0].bloque == _cuerpo(m)[1].id
    with pytest.raises(bloques.ErrorBloques):
        bloques.codigo_desde_bloques(m6)


def test_no_dentro_de_si_mismo_y_saltos():
    m = bloques.bloques_desde_codigo(TODO)
    main = m.programa[-1]
    para = next(b for b in main.listas["cuerpo"] if b.tipo == "para")
    interior = para.listas["cuerpo"][0].id
    with pytest.raises(bloques.ErrorBloques) as e:
        E.mover(m, para.id, E.Destino(interior, "sino", 0))
    assert e.value.clave_mensaje == "BLQ.encaje.dentro_de_si"
    with pytest.raises(bloques.ErrorBloques) as e:
        E.insertar(m, E.nuevo_bloque("continuar"), E.Destino(main.id, "cuerpo", 0))
    assert e.value.clave_mensaje == "FLU.val.continuar_fuera"
    assert "loop" in e.value.texto("en")


def test_soltar_sobre_hueco_ocupado_como_blockly():
    m = _m()
    imp = _cuerpo(m)[1]
    m2 = E.insertar(m, E.desde_paleta("suma"), E.Destino(imp.id, "valor"))
    suma = _cuerpo(m2)[1].huecos["valor"]
    assert suma.tipo == "binaria" and suma.huecos["izquierda"].campos["nombre"] == "n"
    with pytest.raises(bloques.ErrorBloques) as e:
        E.insertar(m, E.desde_paleta("numero"), E.Destino(imp.id, "valor"))
    assert e.value.clave_mensaje == "BLQ.encaje.ocupado"


def test_envolver_y_editar():
    m = _m()
    ids = [b.id for b in _cuerpo(m)[1:]]
    m2 = E.envolver(m, ids, "si")
    si = _cuerpo(m2)[1]
    assert si.tipo == "si" and [b.id for b in si.listas["ramas"][0].listas["cuerpo"]] == ids
    with pytest.raises(bloques.ErrorBloques):
        E.envolver(m, [_cuerpo(m)[0].id, _cuerpo(m)[2].id], "mientras")
    with pytest.raises(bloques.ErrorBloques):
        E.envolver(m, ids, "imprimir")
    m3 = E.editar(m2, si.id, "tiene_sino", True)
    rama = si.listas["ramas"][0].id
    m3 = E.insertar(m3, E.desde_paleta("verdadero"), E.Destino(rama, "condicion"))
    assert "sino {" in bloques.codigo_desde_bloques(m3)
    m4 = E.insertar(m3, E.nuevo_bloque("imprimir"), E.Destino(si.id, "sino"))
    with pytest.raises(bloques.ErrorBloques) as e:
        E.editar(m4, si.id, "tiene_sino", False)
    assert e.value.clave_mensaje == "BLQ.val.parte_oculta"
    with pytest.raises(bloques.ErrorBloques):
        E.editar(m, _cuerpo(m)[0].id, "nombre", "1x")
    with pytest.raises(bloques.ErrorBloques):
        E.editar(m, _cuerpo(m)[0].id, "inexistente", "x")
    # Cambiar el operador no puede dejar un valor que ya no encaja donde está.
    m5 = E.insertar(m, E.nuevo_bloque("mientras"), E.Destino(m.programa[0].id, "cuerpo"))
    ciclo = _cuerpo(m5)[-1]
    m5 = E.insertar(m5, E.desde_paleta("menor"), E.Destino(ciclo.id, "condicion"))
    cond = _cuerpo(m5)[-1].huecos["condicion"]
    m5 = E.insertar(m5, E.desde_paleta("variable", "es", nombre="n"),
                    E.Destino(cond.id, "izquierda"))
    m5 = E.insertar(m5, E.desde_paleta("numero", "es", valor="9"), E.Destino(cond.id, "derecha"))
    assert E.validar(m5) == []
    with pytest.raises(bloques.ErrorBloques) as e:
        E.editar(m5, cond.id, "op", "+")
    assert e.value.clave_mensaje == "BLQ.encaje.tipo"


def test_validar_cuelga_diagnosticos_del_bloque():
    m = _m()
    m2 = E.editar(m, _cuerpo(m)[2].huecos["destino"].id, "nombre", "desconocida")
    problemas = E.validar(m2)
    assert len(problemas) == 1
    assert problemas[0].bloque == _cuerpo(m)[2].id
    assert "IL-" in problemas[0].texto("es")


def test_ids_nuevos_al_insertar_copias():
    m = _m()
    copia = copy.deepcopy(_cuerpo(m)[1])
    m2 = E.insertar(m, copia, E.Destino(m.programa[0].id, "cuerpo"))
    ids = [b.id for b in bloques.recorrer(m2.programa)]
    assert len(ids) == len(set(ids))


def test_codigo_con_lineas_de_instrucciones_y_definiciones():
    """INV-4005: cada bloque sabe su línea en el código generado (sincronía y depurador)."""
    from comun_bloques import COMPLETO

    m = bloques.bloques_desde_codigo(COMPLETO)
    codigo, lineas = bloques.codigo_con_lineas(m, "en")
    renglones = codigo.splitlines()
    for b in m.programa:
        assert renglones[lineas[b.id] - 1].strip(), b.tipo
    clase = next(b for b in m.programa if b.tipo == "clase" and b.campos["nombre"] == "Cuadrado")
    assert renglones[lineas[clase.id] - 1].startswith("class Cuadrado extends Base")
    for miembro in clase.listas["miembros"]:
        assert miembro.campos["nombre"] in renglones[lineas[miembro.id] - 1]
    main = m.programa[-1]
    for instr in main.listas["cuerpo"]:
        assert lineas[instr.id] > lineas[main.id]
