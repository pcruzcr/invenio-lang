"""Garantía de ida y vuelta código → diagrama → código (INV-3001, INV-3002).

Para TODOS los ejercicios de curriculum/es y curriculum/en: el programa
regenerado desde el diagrama, en español y en inglés, compila y produce
exactamente la salida esperada (``.expected``) con su ``.entrada``.
"""

from __future__ import annotations

import pytest
from comun import CURRICULO, RAIZ, TODO, entrada_de, flujo, modelo_de

from inveniolang import api
from inveniolang.flujo.modelo import a_dict


def _sin_lineas(d):
    if isinstance(d, dict):
        return {k: _sin_lineas(v) for k, v in d.items() if k != "linea"}
    if isinstance(d, list):
        return [_sin_lineas(x) for x in d]
    return d


def test_el_curriculo_esta_completo():
    assert len([p for p in CURRICULO if "/es/" in str(p)]) == len(
        [p for p in CURRICULO if "/en/" in str(p)]
    )
    assert len(CURRICULO) >= 250


@pytest.mark.parametrize("inv", CURRICULO, ids=lambda p: f"{p.parent.parent.name}/{p.stem}")
def test_curriculo_misma_salida_en_ambos_idiomas(inv):
    esperado = inv.with_suffix(".expected").read_text(encoding="utf-8")
    modelo = modelo_de(inv)
    for idioma in ("es", "en"):
        codigo = flujo.codigo_desde_modelo(modelo, idioma)
        r = api.ejecutar(codigo, ruta=inv.name, entrada=entrada_de(inv))
        assert r.ok, r.errores
        assert "".join(r.salida) == esperado, idioma


@pytest.mark.parametrize("inv", CURRICULO[::7], ids=lambda p: p.stem)
def test_punto_fijo_y_traduccion_del_modelo(inv):
    modelo = modelo_de(inv)
    for idioma in ("es", "en"):
        codigo = flujo.codigo_desde_modelo(modelo, idioma)
        otra = flujo.modelo_desde_codigo(codigo, idioma)
        assert flujo.codigo_desde_modelo(otra, idioma) == codigo
        assert _sin_lineas(a_dict(otra)) == _sin_lineas(
            a_dict(flujo.traducir_modelo(modelo, idioma))
        )


def test_programa_con_todas_las_construcciones():
    for entrada in (("0",), ("3",), ("9",)):
        original = api.ejecutar(TODO, entrada=entrada)
        for idioma in ("es", "en"):
            codigo = flujo.codigo_desde_modelo(flujo.modelo_desde_codigo(TODO), idioma)
            assert api.ejecutar(codigo, entrada=entrada).salida == original.salida


def test_codigo_generado_usa_el_formateador():
    from inveniolang.formatter import formatear

    codigo = flujo.codigo_desde_modelo(flujo.modelo_desde_codigo(TODO), "en")
    assert formatear(codigo) == codigo
    assert "while (n > 0) {" in codigo and "mientras" not in codigo


@pytest.mark.parametrize(
    "programa", sorted((RAIZ / "pruebas").glob("*.inv"))[::3], ids=lambda p: p.stem
)
def test_programas_de_referencia(programa, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # alguno escribe archivos: cada corrida empieza igual
    codigo = programa.read_text(encoding="utf-8")
    if not api.compilar(codigo, ruta=str(programa)).ok:
        pytest.skip("programa con errores a propósito")
    original = api.ejecutar(codigo, ruta=str(programa))
    modelo = flujo.modelo_desde_codigo(codigo, ruta=str(programa), ruta_fuente=str(programa))
    for f in tmp_path.iterdir():
        f.unlink()
    regenerado = api.ejecutar(flujo.codigo_desde_modelo(modelo, "en"), ruta=str(programa))
    assert regenerado.salida == original.salida
