"""Dibujo SVG de cada paso (INV-2210)."""

from __future__ import annotations

import itertools
import random
import xml.etree.ElementTree as ET

import pytest
from vis_comun import NOMBRES, cargar

from inveniolang.accessibility import contraste_ratio
from inveniolang.visualizacion import describir, normalizar_traza, svg_paso, traza_svg
from inveniolang.visualizacion import render_svg as rs
from inveniolang.visualizacion import render_texto as rt

NS = "{http://www.w3.org/2000/svg}"


def _raiz(svg: str) -> ET.Element:
    return ET.fromstring(svg)


@pytest.mark.parametrize("nombre", NOMBRES)
@pytest.mark.parametrize("tema", ["claro", "oscuro"])
def test_svg_bien_formado_accesible_y_determinista(nombre, tema):
    t = normalizar_traza(cargar(nombre))
    for paso in t["pasos"]:
        svg = svg_paso(paso, t["idioma"], tema=tema)
        assert svg == svg_paso(paso, t["idioma"], tema=tema)  # determinista
        raiz = _raiz(svg)
        assert raiz.tag == NS + "svg" and raiz.get("role") == "img"
        assert raiz.get("aria-labelledby") == "vis-titulo vis-desc"
        titulo, desc = raiz.find(NS + "title"), raiz.find(NS + "desc")
        assert titulo is not None and str(paso["n"]) in titulo.text
        assert desc is not None and desc.text == describir(paso, t["idioma"])
        # cada panel es un grupo con nombre accesible y su propio <title>
        for g in raiz.iter(NS + "g"):
            if g.get("role") == "group":
                assert g.get("aria-label") and g.find(NS + "title").text == g.get("aria-label")


def _etiquetas(svg: str) -> list[str]:
    return [g.get("aria-label") for g in _raiz(svg).iter(NS + "g") if g.get("role") == "group"]


PANELES = {
    "arreglo_es": "a · Arreglo",
    "arreglo_en": "a · Array",
    "matriz_es": "m · Matriz",
    "matriz_en": "m · Matrix",
    "pila_es": "p · Pila",
    "pila_en": "s · Stack",
    "cola_es": "c · Cola",
    "cola_en": "q · Queue",
    "lista_enlazada_es": "l · Lista enlazada",
    "lista_enlazada_en": "l · Linked list",
    "lista_doble_es": "d · Lista doble",
    "lista_doble_en": "d · Doubly linked list",
    "arbol_es": "t · Árbol binario",
    "arbol_en": "t · Binary tree",
    "grafo_es": "g · Grafo",
    "grafo_en": "g · Graph",
    "recursion_es": "Pila de llamadas",
    "recursion_en": "Call stack",
    "escalares_es": "Variables de main",
    "escalares_en": "Variables of main",
}


@pytest.mark.parametrize("nombre", sorted(PANELES))
def test_cada_forma_tiene_su_panel(nombre):
    t = normalizar_traza(cargar(nombre))
    svg = svg_paso(t["pasos"][-1], t["idioma"])
    assert PANELES[nombre] in _etiquetas(svg)


def test_celdas_del_arreglo_con_valor_e_indice():
    t = normalizar_traza(cargar("arreglo_es"))
    etiquetas = _etiquetas(svg_paso(t["pasos"][-1], "es"))
    for i, v in enumerate([1, 2, 4, 5]):
        assert any(e.startswith(f"a[{i}] = {v}") for e in etiquetas)


def test_resaltado_no_depende_solo_del_color():
    """Lectura y escritura: borde distinto + patrón + letra + texto en <title>."""
    t = normalizar_traza(cargar("arreglo_es"))
    svg = svg_paso(t["pasos"][3], "es")  # lee a[1], escribe a[0]
    etq = _etiquetas(svg)
    assert any(e.startswith("a[0] = 1 — escrito en este paso") for e in etq)
    assert any(e.startswith("a[1] = 1 — leído en este paso") for e in etq)
    raiz = _raiz(svg)
    rects = list(raiz.iter(NS + "rect"))
    assert any(r.get("fill") == "url(#vis-pat-escribe)" for r in rects)
    assert any(r.get("fill") == "url(#vis-pat-lee)" for r in rects)
    assert any(r.get("stroke-dasharray") == "5 3" for r in rects)  # lectura: discontinuo
    assert any(r.get("stroke-width") == "3" for r in rects)  # escritura: grueso
    textos = [x.text for x in raiz.iter(NS + "text")]
    assert "E" in textos and "L" in textos
    en = [x.text for x in _raiz(svg_paso(t["pasos"][3], "en")).iter(NS + "text")]
    assert "W" in en and "R" in en


def test_variable_escalar_escrita_se_marca():
    t = normalizar_traza(cargar("escalares_en"))
    etq = _etiquetas(svg_paso(t["pasos"][0], "en"))
    assert any(e.startswith("age (int) = 15 — written at this step") for e in etq)


def test_la_pila_de_llamadas_muestra_el_marco_activo_arriba():
    t = normalizar_traza(cargar("recursion_es"))
    etq = [e for e in _etiquetas(svg_paso(t["pasos"][3], "es")) if "(línea" in e]
    assert etq[0] == "factorial (línea 3) — activo: n = 1"
    assert etq[-1] == "main (línea 9)"
    assert len(etq) == 4


def test_texto_del_svg_sigue_el_idioma():
    paso = normalizar_traza(cargar("cola_es"))["pasos"][0]
    es = [x.text for x in _raiz(svg_paso(paso, "es")).iter(NS + "text")]
    en = [x.text for x in _raiz(svg_paso(paso, "en")).iter(NS + "text")]
    # el rótulo "final" se escribió en este paso: lleva la letra de escritura
    assert "frente" in es and "final · E" in es
    assert "front" in en and "rear · W" in en


def _contraste(paleta, a, b):
    return contraste_ratio(paleta[a], paleta[b])


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
def test_paleta_aaa_en_texto_y_aa_en_graficos(tema):
    p = rs.PALETAS[tema]
    fondos_texto = ["fondo", "panel", "celda", "lee_fondo", "escribe_fondo", "activo_fondo"]
    for texto, fondo in itertools.product(["texto", "texto_suave"], fondos_texto):
        assert _contraste(p, texto, fondo) >= 7, (texto, fondo)
    for fondo in ("fondo", "panel", "celda"):
        assert _contraste(p, "acento", fondo) >= 7, fondo
    # letras de las insignias (texto "fondo" sobre el color del borde)
    for insignia in ("lee_borde", "escribe_borde", "activo_borde"):
        assert _contraste(p, "fondo", insignia) >= 7, insignia
    for grafico in (
        "celda_borde",
        "lee_borde",
        "escribe_borde",
        "arista",
        "panel_borde",
        "activo_borde",
    ):
        assert _contraste(p, grafico, "panel") >= 3, grafico
        assert _contraste(p, grafico, "fondo") >= 3, grafico


def test_temas_misma_estructura_distinto_color():
    paso = normalizar_traza(cargar("grafo_en"))["pasos"][0]
    claro, oscuro = svg_paso(paso, "en", tema="claro"), svg_paso(paso, "en", tema="oscuro")
    assert claro != oscuro
    assert claro.replace(rs.CLARO["fondo"], "").count("<") == oscuro.count("<")


def test_css_del_tema_cubre_todas_las_clases_usadas():
    paso = normalizar_traza(cargar("lista_doble_es"))["pasos"][1]
    svg = svg_paso(paso, "es")
    css = rs.css_tema("#x", "oscuro")
    usadas = {c for el in _raiz(svg).iter() for c in (el.get("class") or "").split()}
    assert usadas and all(f".{c}{{" in css for c in usadas)


# ----------------------------------------------------------------- árbol


def _bst(claves):
    hijos, raiz = {}, None
    for c in claves:
        if raiz is None:
            raiz = c
            continue
        p = raiz
        while True:
            lado = "izq" if c < p else "der"
            if lado not in hijos.get(p, {}):
                hijos.setdefault(p, {})[lado] = c
                break
            p = hijos[p][lado]
    return raiz, hijos


def _sin_solapes(pos, hijos):
    por_nivel = {}
    for _n, (x, nivel) in pos.items():
        por_nivel.setdefault(nivel, []).append(x)
    for xs in por_nivel.values():
        xs.sort()
        assert all(b - a >= 1 - 1e-9 for a, b in zip(xs, xs[1:], strict=False)), xs
    for p, hs in hijos.items():
        if p not in pos:
            continue
        if "izq" in hs and hs["izq"] in pos:
            assert pos[hs["izq"]][0] < pos[p][0]
        if "der" in hs and hs["der"] in pos:
            assert pos[hs["der"]][0] > pos[p][0]


@pytest.mark.parametrize("semilla", range(40))
def test_disposicion_del_arbol_sin_solapes(semilla):
    claves = random.Random(semilla).sample(range(1000), 60)
    raiz, hijos = _bst(claves)
    pos = rs.disposicion_arbol(raiz, hijos, max_niveles=100)
    assert len(pos) == 60
    _sin_solapes(pos, hijos)
    assert min(x for x, _ in pos.values()) == 0


def test_arbol_degenerado_profundo_no_agota_la_pila():
    raiz, hijos = _bst(range(3000))
    pos = rs.disposicion_arbol(raiz, hijos, max_niveles=5000)
    assert len(pos) == 3000
    _sin_solapes(pos, hijos)
    # recortado al dibujar: sólo MAX_NIVELES_ARBOL niveles
    assert len(rs.disposicion_arbol(raiz, hijos)) == rs.MAX_NIVELES_ARBOL


def test_arbol_dibujado_sin_solapes_de_cajas():
    t = normalizar_traza(cargar("arbol_en"))
    raiz = _raiz(svg_paso(t["pasos"][-1], "en"))
    nodos = [
        g
        for g in raiz.iter(NS + "g")
        if g.get("role") == "group" and g.get("transform") and g.get("aria-label", "")[:2].isdigit()
    ]
    cajas = []
    for g in nodos:
        x, y = (float(v) for v in g.get("transform")[10:-1].split(","))
        r = g.find(NS + "rect")
        cajas.append((x, y, float(r.get("width")), float(r.get("height"))))
    assert len(cajas) >= 8
    for a, b in itertools.combinations(cajas, 2):
        separadas = (
            a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]
        )
        assert separadas, (a, b)


# ----------------------------------------------------------------- grafo


def test_disposicion_circular_determinista():
    a = rs.disposicion_circular(6, 100)
    assert a == rs.disposicion_circular(6, 100)
    assert a[0] == pytest.approx((100, 0))  # el primer vértice arriba
    for x, y in a:
        assert (x - 100) ** 2 + (y - 100) ** 2 == pytest.approx(100**2)


def test_grafo_con_pesos_y_dirigido_o_no():
    es = normalizar_traza(cargar("grafo_es"))["pasos"][0]
    raiz = _raiz(svg_paso(es, "es"))
    textos = [x.text for x in raiz.iter(NS + "text")]
    for peso in ("4", "1", "2", "5", "3"):
        assert peso in textos
    assert len(list(raiz.iter(NS + "polygon"))) == 6  # 6 aristas dirigidas → 6 puntas
    en = normalizar_traza(cargar("grafo_en"))["pasos"][0]
    assert not list(_raiz(svg_paso(en, "en")).iter(NS + "polygon"))  # no dirigido
    vertices, aristas = rt.grafo(en["estructuras"][0], en)
    assert len(vertices) == 4 and len(aristas) == 4 and not any(a[3] for a in aristas)
    assert any("visited" in e for e in _etiquetas(svg_paso(en, "en")))


# ----------------------------------------------------------------- límites


def test_estructura_grande_se_recorta_y_lo_dice():
    elementos = [{"t": "escalar", "tipo": "entero", "v": i} for i in range(400)]
    paso = {
        "monticulo": {"1": {"tipo": "arreglo", "elementos": elementos}},
        "estructuras": [{"forma": "arreglo", "raiz": 1, "etiqueta": "big", "nodos": [1]}],
    }
    svg = svg_paso(paso, "es")
    assert f"Se muestran {rs.MAX_CELDAS} de 400." in svg
    assert "big[255]" in svg and "big[256]" not in svg


def test_traza_svg_por_indice_y_fuera_de_rango():
    t = cargar("pila_en")
    assert traza_svg(t, 0) == svg_paso(t["pasos"][0], "en")
    assert "<desc" in traza_svg(t, 3, idioma="es", tema="oscuro")
    with pytest.raises(IndexError, match="4"):
        traza_svg(t, 4)


def test_valores_con_caracteres_especiales_se_escapan():
    paso = {
        "marcos": [
            {
                "subrutina": "main",
                "linea": 1,
                "variables": {
                    "s": {
                        "tipo": "texto",
                        "valor": {"t": "escalar", "tipo": "texto", "v": '<b>&"x"</b>'},
                    }
                },
            }
        ],
        "salida_nueva": ["</svg><script>"],
    }
    svg = svg_paso(paso, "es")
    _raiz(svg)
    assert "<script>" not in svg and "<b>" not in svg
