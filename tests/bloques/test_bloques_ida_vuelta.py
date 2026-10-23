"""Garantía código → bloques → código (INV-4002, INV-4003, INV-4005).

Para TODOS los ejercicios de curriculum/es y curriculum/en: el programa
regenerado desde los bloques, en español y en inglés, compila y produce
exactamente la salida de su ``.expected`` con su ``.entrada``; el JSON v1
hace ida y vuelta exacta y los bloques son la misma estructura (mismos ids)
que el diagrama de flujo.
"""

from __future__ import annotations

import pytest
from comun_bloques import COMPLETO, CURRICULO, RAIZ, TODO, bloques, bloques_de, entrada_de

from inveniolang import api, flujo


def test_el_curriculo_esta_completo():
    assert len(CURRICULO) == 266
    assert len([p for p in CURRICULO if "es" in p.parts]) == 133


@pytest.mark.parametrize("inv", CURRICULO, ids=lambda p: f"{p.parent.parent.name}/{p.stem}")
def test_curriculo_misma_salida_en_ambos_idiomas(inv):
    esperado = inv.with_suffix(".expected").read_text(encoding="utf-8")
    modelo = bloques_de(inv)
    assert bloques.desde_json(bloques.a_json(modelo)) == modelo
    assert bloques.validar(modelo) == []
    for idioma in ("es", "en"):
        codigo = bloques.codigo_desde_bloques(modelo, idioma)
        r = api.ejecutar(codigo, ruta=inv.name, entrada=entrada_de(inv))
        assert r.ok, r.errores
        assert "".join(r.salida) == esperado, idioma


@pytest.mark.parametrize("inv", CURRICULO[::9], ids=lambda p: p.stem)
def test_bloques_y_flujo_son_el_mismo_arbol(inv):
    codigo = inv.read_text(encoding="utf-8")
    mf = flujo.modelo_desde_codigo(codigo, ruta=inv.name)
    mb = bloques.desde_flujo(mf)
    vuelta = bloques.a_flujo(mb)
    ids = [[n.id for n in flujo.modelo.recorrer(d.cuerpo)] for d in mf.diagramas()]
    assert ids == [[n.id for n in flujo.modelo.recorrer(d.cuerpo)] for d in vuelta.diagramas()]
    assert [d.clave for d in mf.diagramas()] == [d.clave for d in vuelta.diagramas()]
    # Punto fijo: el código de los bloques vuelve a dar los mismos bloques.
    texto = bloques.codigo_desde_bloques(mb)
    otra = bloques.bloques_desde_codigo(texto)
    assert bloques.codigo_desde_bloques(otra) == texto


@pytest.mark.parametrize("inv", CURRICULO[::11], ids=lambda p: p.stem)
def test_traducir_bloques_conserva_programa_e_ids(inv):
    modelo = bloques_de(inv)
    otro = "en" if modelo.idioma == "es" else "es"
    traducido = bloques.traducir_bloques(modelo, otro)
    assert traducido.idioma == otro
    assert [b.id for b in bloques.recorrer(traducido.programa) if b.id.startswith("n")] == [
        b.id for b in bloques.recorrer(modelo.programa) if b.id.startswith("n")
    ]
    assert bloques.codigo_desde_bloques(traducido) == bloques.codigo_desde_bloques(modelo, otro)


@pytest.mark.parametrize("programa", [TODO, COMPLETO], ids=["control", "completo"])
def test_programas_con_todo_el_lenguaje(programa):
    for entrada in (("0",), ("3",), ("9",)):
        original = api.ejecutar(programa, entrada=entrada)
        assert original.ok, original.errores
        modelo = bloques.bloques_desde_codigo(programa)
        for idioma in ("es", "en"):
            codigo = bloques.codigo_desde_bloques(modelo, idioma)
            assert api.ejecutar(codigo, entrada=entrada).salida == original.salida


def test_completo_usa_todos_los_tipos_de_bloque():
    """TODO + COMPLETO (+ ``importar``, probado aparte) cubren todo el catálogo."""
    tipos = {
        b.tipo
        for prog in (TODO, COMPLETO)
        for b in bloques.recorrer(bloques.bloques_desde_codigo(prog).programa)
    }
    assert set(bloques.TIPOS) - tipos == {"importar"}


def test_importar(tmp_path):
    (tmp_path / "util.inv").write_text("entero doble(entero x) {\n    retornar x * 2;\n}\n",
                                       encoding="utf-8")
    principal = tmp_path / "main.inv"
    principal.write_text('importar "util.inv";\nvacio main() {\n    imprimir(doble(4));\n}\n',
                         encoding="utf-8")
    modelo = bloques.bloques_desde_codigo(
        principal.read_text(encoding="utf-8"), ruta_fuente=str(principal)
    )
    assert modelo.programa[0].tipo == "importar"
    assert modelo.programa[0].campos["ruta"] == '"util.inv"'
    assert bloques.codigo_desde_bloques(modelo, "en").startswith('import "util.inv";')


@pytest.mark.parametrize(
    "programa", sorted((RAIZ / "pruebas").glob("*.inv"))[::4], ids=lambda p: p.stem
)
def test_programas_de_referencia(programa, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # alguno escribe archivos: cada corrida empieza igual
    codigo = programa.read_text(encoding="utf-8")
    if not api.compilar(codigo, ruta=str(programa)).ok:
        pytest.skip("programa con errores a propósito")
    original = api.ejecutar(codigo, ruta=str(programa))
    modelo = bloques.bloques_desde_codigo(codigo, ruta=str(programa),
                                          ruta_fuente=str(programa))
    for f in tmp_path.iterdir():
        f.unlink()
    regenerado = bloques.codigo_desde_bloques(modelo)
    r = api.ejecutar(regenerado, ruta=str(programa))
    assert r.salida == original.salida
