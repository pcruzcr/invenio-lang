"""Geometría del lienzo (INV-4011) y descripción accesible (INV-4007)."""

from __future__ import annotations

import pytest
from comun_bloques import COMPLETO, CURRICULO, TODO, bloques, bloques_de

from inveniolang.bloques import diseno, edicion, texto


def _solapan(a, b):
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


@pytest.mark.parametrize("programa", [TODO, COMPLETO], ids=["control", "completo"])
def test_cada_hueco_y_cada_lista_tiene_zona(programa):
    m = bloques.bloques_desde_codigo(programa)
    d = diseno.disenar(m)
    zonas = {(z.padre, z.parte, z.indice) for z in d.zonas}
    for b in bloques.recorrer(m.programa):
        for h in b.huecos:
            assert (b.id, h, None) in zonas, (b.tipo, h)
        for nombre in texto.bocas(b):
            for k in range(len(b.listas[nombre]) + 1):
                assert (b.id, nombre, k) in zonas, (b.tipo, nombre, k)
    for k in range(len(m.programa) + 1):
        assert (None, "programa", k) in zonas
    # El orden de navegación con teclado recorre todos los bloques.
    assert sorted(c.id for c in d.todas()) == sorted(b.id for b in bloques.recorrer(m.programa))


@pytest.mark.parametrize("inv", CURRICULO[::17], ids=lambda p: p.stem)
def test_hermanas_no_se_solapan_y_quedan_dentro(inv):
    d = diseno.disenar(bloques_de(inv))
    for padre in [diseno.Caja("raiz", "", "", "valores", None, 0, 0, d.ancho, d.alto,
                              hijas=d.cajas), *d.todas()]:
        for i, a in enumerate(padre.hijas):
            assert padre.x <= a.x and a.x + a.w <= padre.x + padre.w + 0.01, padre.tipo
            for b in padre.hijas[i + 1:]:
                assert not _solapan(a, b), (padre.tipo, a.tipo, b.tipo)


def test_zona_y_caja_bajo_el_puntero():
    m = edicion.nuevo_modelo()
    d = diseno.disenar(m)
    main = d.cajas[0]
    zona = d.zona_en(main.x + 30, main.y + diseno.ALTO + 5)
    assert zona is not None and (zona.padre, zona.parte, zona.indice) == (main.id, "cuerpo", 0)
    assert d.caja_en(main.x + 3, main.y + 12).id == main.id


def test_describir_es_en():
    m = bloques.bloques_desde_codigo(TODO)
    es = texto.describir(m, "es")
    en = texto.describir(m, "en")
    assert "  mientras n > 0" in es and "  while n > 0" in en
    assert "sino si i > 7 entonces" in es and "else if i > 7 then" in en
    assert "capturar (e)" in es and "catch (e)" in en
    assert len(es.splitlines()) == len(en.splitlines())


def test_rotulo_omite_tramos_opcionales_vacios():
    b = edicion.nuevo_bloque("declarar", "es", nombre="x")
    assert texto.rotulo(b, "es") == "declarar entero x"
    b.huecos["valor"] = edicion.nuevo_bloque("numero", "es", valor="4")
    assert texto.rotulo(b, "en") == "declare entero x = 4"
