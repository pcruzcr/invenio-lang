"""Contrato JSON v1 de bloques (INV-4000) y catálogo accesible (INV-4001, INV-4004)."""

from __future__ import annotations

import copy
import json

import pytest
from comun_bloques import COMPLETO, bloques

from inveniolang import i18n
from inveniolang.bloques import catalogo
from inveniolang.bloques.texto import piezas


def _modelo():
    return bloques.bloques_desde_codigo(COMPLETO)


def test_ida_y_vuelta_exacta_y_forma_uniforme():
    m = _modelo()
    d = bloques.a_dict(m)
    assert d["formato"] == "inveniolang-bloques" and d["version"] == 1
    assert bloques.desde_dict(json.loads(bloques.a_json(m))) == m
    for b in bloques.recorrer(m.programa):
        bd = bloques.modelo.bloque_a_dict(b)
        assert list(bd) == ["id", "tipo", "linea", "campos", "huecos", "listas"]
        desc = catalogo.TIPOS[b.tipo]
        assert list(bd["campos"]) == [c.nombre for c in desc.campos]
        assert list(bd["huecos"]) == [h.nombre for h in desc.huecos]
        assert list(bd["listas"]) == [x.nombre for x in desc.listas]
    ids = [b.id for b in bloques.recorrer(m.programa)]
    assert len(ids) == len(set(ids))


def _sin_hijos(b):
    return {**copy.deepcopy(b), "id": "zz2", "huecos": {"destino": None, "valor": None}}


def _primero(d, tipo):
    pila = list(d["programa"])
    while pila:
        b = pila.pop(0)
        if b["tipo"] == tipo:
            return b
        pila.extend(h for h in b["huecos"].values() if h)
        for lista in b["listas"].values():
            pila.extend(lista)
    raise AssertionError(tipo)


@pytest.mark.parametrize(
    "romper, ruta, fragmento",
    [
        (lambda d: d.update(formato="otro"), "$.formato", "inveniolang-bloques"),
        (lambda d: d.update(version=2), "$.version", "2"),
        (lambda d: d.update(idioma="fr"), "$.idioma", "fr"),
        (lambda d: d.pop("programa"), "$", "programa"),
        (lambda d: d["programa"][0].update(tipo="nada"), "$.programa[0].tipo", "nada"),
        (lambda d: d["programa"][0].update(extra=1), "$.programa[0]", "extra"),
        (lambda d: d["programa"][1].update(id=d["programa"][0]["id"]), "$.programa[1].id", ""),
        (lambda d: d["programa"][0].update(linea=-1), "$.programa[0].linea", ""),
        (lambda d: _primero(d, "declarar")["campos"].update(constante="si"), "constante", ""),
        (lambda d: _primero(d, "binaria")["campos"].update(op=3), "campos.op", ""),
        (
            lambda d: _primero(d, "mientras")["huecos"].update(condicion=_primero(d, "romper")),
            "huecos.condicion",
            "romper",
        ),
        (
            lambda d: _primero(d, "si")["listas"]["sino"].append(
                {**copy.deepcopy(_primero(d, "numero")), "id": "zz1"}
            ),
            "listas.sino[",
            "numero",
        ),
        (
            lambda d: d["programa"].append(_sin_hijos(_primero(d, "asignar"))),
            "$.programa[",
            "asignar",
        ),
    ],
)
def test_contrato_rechaza_con_ruta(romper, ruta, fragmento):
    from comun_bloques import TODO

    d = bloques.a_dict(bloques.bloques_desde_codigo(COMPLETO if "declarar" in ruta else TODO))
    if "constante" in ruta or "campos.op" in ruta:
        d = bloques.a_dict(_modelo())
    romper(d)
    with pytest.raises(bloques.ErrorBloques) as e:
        bloques.desde_dict(d)
    assert ruta in str(e.value)
    assert fragmento in str(e.value)
    assert e.value.texto("en").startswith("Invalid blocks at")


def test_json_invalido():
    with pytest.raises(bloques.ErrorBloques) as e:
        bloques.desde_json("{no es json")
    assert "JSON" in e.value.texto("en")


def test_catalogo_completo_y_bilingue():
    for idioma in i18n.IDIOMAS:
        cat = bloques.catalogo_dict(idioma)
        json.dumps(cat)
        assert set(cat["tipos"]) == set(catalogo.TIPOS)
        for tipo, desc in cat["tipos"].items():
            assert desc["nombre"] and desc["plantilla"] is not None
            refs = {p.valor for p in _refs(piezas(tipo, idioma))}
            nombres = {c["nombre"] for c in desc["campos"]} | {h["nombre"] for h in desc["huecos"]}
            nombres |= {x["nombre"] for x in desc["listas"]}
            assert refs <= nombres, (tipo, refs - nombres)
            # Todo hueco y todo campo se ve en el bloque (los campos de estilo,
            # sólo en el formulario de edición).
            assert {h["nombre"] for h in desc["huecos"]} <= refs, tipo
        for entrada in cat["paleta"]:
            assert entrada["nombre"]
            bloques.desde_paleta(entrada["clave"], idioma)
    es, en = bloques.catalogo_dict("es"), bloques.catalogo_dict("en")
    assert es["tipos"]["mientras"]["plantilla"] != en["tipos"]["mientras"]["plantilla"]


def _refs(p):
    for x in p:
        if x.clase == "ref":
            yield x
        elif x.clase == "opcional":
            yield from _refs(x.hijas)


def test_paleta_cubre_todos_los_tipos():
    assert {e.tipo for e in catalogo.PALETA} == set(catalogo.TIPOS)
    for t in catalogo.TIPOS.values():
        assert t.forma in catalogo.FORMAS and t.categoria in catalogo.CATEGORIAS
        assert all(h.acepta in catalogo.ACEPTA_HUECO for h in t.huecos)
        assert all(x.acepta in catalogo.ACEPTA_LISTA for x in t.listas)


def test_colores_accesibles_y_nunca_solo_color():
    """INV-4004: texto ≥ 7:1 sobre su relleno, borde ≥ 3:1 sobre el lienzo, icono propio."""
    iconos = set()
    for cat in catalogo.CATEGORIAS.values():
        for tema in ("claro", "oscuro"):
            relleno, texto, borde = getattr(cat, tema)
            assert catalogo.contraste(relleno, texto) >= 7, (cat.nombre, tema)
            assert catalogo.contraste(borde, catalogo.FONDO_LIENZO[tema]) >= 3, (cat.nombre, tema)
        iconos.add(cat.icono)
    assert len(iconos) == len(catalogo.CATEGORIAS)
    # La forma distingue además instrucciones, contenedores, valores y definiciones.
    assert {t.forma for t in catalogo.TIPOS.values()} == set(catalogo.FORMAS)
