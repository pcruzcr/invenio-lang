"""Reproductor HTML autónomo (INV-2220, INV-2241)."""

from __future__ import annotations

import base64
import gzip
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from vis_comun import NOMBRES, cargar

from inveniolang.visualizacion import describir, normalizar_traza, svg_paso, traza_html
from inveniolang.visualizacion.reproductor import empaquetar_svgs

AQUI = Path(__file__).parent


class _Recolector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.etiquetas = []

    def handle_starttag(self, tag, attrs):
        self.etiquetas.append((tag, dict(attrs)))


def _analizar(html):
    r = _Recolector()
    r.feed(html)
    return r.etiquetas


def _datos(html):
    crudo = re.search(
        r'<script type="application/json" id="vis-datos">(.*?)</script>', html, re.S
    ).group(1)
    return json.loads(crudo)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_html_autonomo_sin_urls_externas(nombre):
    html = traza_html(cargar(nombre))
    assert html == traza_html(cargar(nombre))  # determinista
    assert html.startswith("<!doctype html>")
    for patron in ("http://", "https://", "//cdn", "@import", "url(http"):
        assert patron not in html.lower(), patron
    for tag, attrs in _analizar(html):
        assert "src" not in attrs, tag
        if "href" in attrs:
            assert attrs["href"].startswith("#"), attrs
        assert tag not in ("link", "iframe", "img", "object", "embed")


@pytest.mark.parametrize("nombre", ["arreglo_es", "grafo_en"])
def test_html_accesible(nombre):
    t = normalizar_traza(cargar(nombre))
    html = traza_html(cargar(nombre))
    etiquetas = _analizar(html)
    raiz = etiquetas[0]
    assert raiz == ("html", {"lang": t["idioma"], "data-tema": "claro"})
    por_id = {a.get("id"): (tag, a) for tag, a in etiquetas if a.get("id")}
    assert por_id["descripcion"][1]["aria-live"] == "polite"
    assert any(a.get("role") == "toolbar" and a.get("aria-label") for _, a in etiquetas)
    for boton in ("btn-inicio", "btn-anterior", "btn-reproducir", "btn-siguiente", "btn-fin"):
        assert por_id[boton][1]["aria-label"]
    assert por_id["deslizador"][1]["aria-valuetext"]
    assert por_id["btn-tema"][1]["aria-pressed"] == "false"
    # código fuente: una <li> por línea, con id para resaltar la actual
    lineas = t["fuente"].rstrip("\n").split("\n")
    assert all(f"vis-l{i}" in por_id for i in range(1, len(lineas) + 1))
    # sin JavaScript también se puede leer todo: lista de descripciones
    for paso in t["pasos"]:
        assert describir(paso, t["idioma"]).replace('"', "&quot;") in html
    textos = (
        "Atajos" if t["idioma"] == "es" else "Shortcuts",
        "Inicio" if t["idioma"] == "es" else "Home",
    )
    assert all(x in html for x in textos)


def test_svgs_empaquetados_son_los_de_cada_paso():
    t = normalizar_traza(cargar("lista_enlazada_es"))
    datos = _datos(traza_html(t))
    unicos = json.loads(gzip.decompress(base64.b64decode(datos["svgs"])))
    for paso, meta in zip(t["pasos"], datos["pasos"], strict=True):
        esperado = svg_paso(paso, "es").replace(' xmlns="http://www.w3.org/2000/svg"', "", 1)
        assert unicos[meta["svg"]] == esperado
        assert meta["linea"] == paso["linea"]
        assert meta["descripcion"] == describir(paso, "es")
    assert datos["salida"] == ["6"] and [m["salida"] for m in datos["pasos"]] == [0, 0, 1]


def test_empaquetado_deduplica_y_es_determinista():
    blob, indices = empaquetar_svgs(["<a/>", "<b/>", "<a/>"])
    assert indices == [0, 1, 0]
    assert blob == empaquetar_svgs(["<a/>", "<b/>", "<a/>"])[0]


def test_idioma_explicito_y_avisos_de_error_y_truncado():
    t = cargar("error_es")
    html = traza_html(t)
    assert 'role="alert"' in html and "Índice fuera de rango" in html
    html_en = traza_html(t, idioma="en")
    assert 'lang="en"' in html_en and "The program ended with an error" in html_en
    t["truncada"] = True
    assert "límite de pasos" in traza_html(t)
    vacia = traza_html({"version": 1, "idioma": "en", "fuente": "", "pasos": []})
    assert "no steps" in vacia


def test_contenido_hostil_no_rompe_la_pagina():
    t = cargar("escalares_es")
    t["fuente"] = 'vacio main() { imprimir("</script><script>alert(1)</script>"); }\n'
    t["salida"] = ["</script><!--"]
    html = traza_html(t)
    assert html.count("<script") == 2  # sólo los dos propios
    assert "<!--" not in html.split("<script>")[0]


@pytest.mark.skipif(shutil.which("node") is None, reason="sin Node.js para ejecutar el JavaScript")
@pytest.mark.parametrize("nombre", ["arreglo_es", "recursion_en"])
def test_javascript_del_reproductor_funciona(nombre, tmp_path):
    """Ejecuta el JS real con un DOM mínimo: descompresión, teclado y botones."""
    t = normalizar_traza(cargar(nombre))
    pagina = tmp_path / "p.html"
    pagina.write_text(traza_html(t), encoding="utf-8")
    salida = subprocess.run(
        ["node", str(AQUI / "dom_minimo.js"), str(pagina)],
        capture_output=True,
        text=True,
        encoding="utf-8",  # Node escribe UTF-8; en Windows el valor por defecto es cp1252
        timeout=60,
        check=True,
    )
    r = json.loads(salida.stdout)
    n = len(t["pasos"])
    palabra = "Paso" if t["idioma"] == "es" else "Step"
    assert r["inicial"]["contador"] == f"{palabra} 1 {'de' if palabra == 'Paso' else 'of'} {n}"
    assert r["inicial"]["svg"] == "<svg" and r["inicial"]["paso_svg"] == str(t["pasos"][0]["n"])
    assert r["inicial"]["linea"] == f"vis-l{t['pasos'][0]['linea']}"
    assert r["inicial"]["marca"] == "▶" and r["inicial"]["aria_current"] == "step"
    assert (
        r["derecha"]["deslizador"] == "1"
        and r["derecha"]["linea"] == f"vis-l{t['pasos'][1]['linea']}"
    )
    assert r["derecha"]["descripcion"] == describir(t["pasos"][1], t["idioma"])
    assert r["fin"]["deslizador"] == str(n - 1) and r["fin"]["salida"] == "\n".join(t["salida"])
    assert r["izquierda"]["deslizador"] == str(n - 2)
    assert r["inicio"]["deslizador"] == "0" and r["boton_siguiente"]["deslizador"] == "1"
    assert r["espacio_prevenido"] and r["espacio"]["reproduciendo"] == "true"
    assert r["espacio2"]["reproduciendo"] == "false"
    assert r["flecha_en_select"] is False  # el <select> conserva sus flechas
    assert r["tema"] == "oscuro" and r["deslizador"]["deslizador"] == "0"
