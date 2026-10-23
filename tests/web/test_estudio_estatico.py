"""Comprobaciones estáticas del estudio web: textos, accesibilidad y contraste (INV-4203, INV-4220)."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from contraste import fallos, temas

from inveniolang.i18n import en, es

RAIZ = Path(__file__).resolve().parents[2]
ESTUDIO = RAIZ / "web" / "estudio"
HTML = (ESTUDIO / "index.html").read_text(encoding="utf-8")
JS = {p.name: p.read_text(encoding="utf-8") for p in sorted((ESTUDIO / "js").glob("*.js"))}
CSS = (ESTUDIO / "estilos.css").read_text(encoding="utf-8")
WEB = {k[4:] for k in es.MENSAJES if k.startswith("WEB.")}

# Claves que el código compone a partir de un valor (estado del motor, motivo de error, idioma).
ESTADOS_MOTOR = ("cargando", "listo", "ocupado", "sin_red", "sin_paquete", "error")
MOTIVOS = ("tiempo", "detenido", "no_listo", "peticion", "interno", "recursion", "sin_bloques")
DINAMICAS = (
    {f"motor.{e}" for e in ESTADOS_MOTOR}
    | {f"motor.corto.{e}" for e in ESTADOS_MOTOR}
    | {f"motor.error.{m}" for m in MOTIVOS}
    | {"idioma.es", "idioma.en"}
    | {"tecla.intro", "tecla.espacio", "tecla.supr"}
)


class Arbol(HTMLParser):
    """Recoge elementos con sus atributos y el texto directo de cada uno."""

    def __init__(self) -> None:
        super().__init__()
        self.elementos: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag, attrs):
        """Registra cada etiqueta de apertura con sus atributos."""
        self.elementos.append((tag, {k: v or "" for k, v in attrs}))


def elementos():
    a = Arbol()
    a.feed(HTML)
    return a.elementos


def claves_usadas() -> set[str]:
    usadas = set(re.findall(r'data-t(?:-[a-z-]+)?="([^"]+)"', HTML))
    for fuente in JS.values():
        usadas |= {
            m
            for m in re.findall(r'"([a-z_]+(?:\.[a-z_0-9]+)+)"', fuente)
            if m.split(".")[0] in {k.split(".")[0] for k in WEB}
        }
    return usadas | DINAMICAS


def test_toda_clave_usada_existe_en_ambos_idiomas():
    faltan = claves_usadas() - WEB
    assert faltan == set()
    assert {k for k in en.MENSAJES if k.startswith("WEB.")} == {f"WEB.{k}" for k in WEB}


def test_ninguna_clave_web_sobra():
    assert WEB - claves_usadas() == set()


def test_los_estados_y_motivos_del_motor_coinciden_con_el_codigo():
    for e in ESTADOS_MOTOR:
        assert f'"{e}"' in JS["estado.js"] or e in JS["estado.js"]
    for m in ("tiempo", "detenido", "no_listo", "interno"):
        assert f'"{m}"' in JS["motor.js"]
    puente = (RAIZ / "inveniolang" / "web" / "puente.py").read_text(encoding="utf-8")
    for m in ("peticion", "interno", "recursion", "sin_bloques"):
        assert f'"tipo": "{m}"' in puente


def test_ids_que_usa_el_codigo_existen_en_la_pagina():
    ids = {a["id"] for _, a in elementos() if "id" in a}
    usados = set()
    for fuente in JS.values():
        usados |= set(re.findall(r'\$\("([a-z0-9-]+)"\)', fuente))
    assert usados - ids == set()
    for _, a in elementos():
        for attr in ("aria-controls", "aria-labelledby", "aria-describedby", "for"):
            for ref in a.get(attr, "").split():
                assert ref in ids, f"{attr}={ref}"


def test_ids_unicos():
    ids = [a["id"] for _, a in elementos() if "id" in a]
    assert len(ids) == len(set(ids))


# Botones cuyo texto pone el código (depende del idioma del programa o de la pregunta).
TEXTO_DINAMICO = {
    "btn-traducir": "btn-traducir-texto",
    "dialogo-confirmar-si": "dialogo-confirmar-si",
}


def test_todo_control_tiene_nombre_accesible():
    """Botones con texto del catálogo (data-t) o aria-label; campos con su etiqueta."""
    for boton in re.findall(r"<button\b[^>]*>.*?</button>", HTML, re.S):
        ident = re.search(r'id="([^"]+)"', boton)
        if ident and ident.group(1) in TEXTO_DINAMICO:
            assert f'$("{TEXTO_DINAMICO[ident.group(1)]}").textContent' in JS["app.js"]
            continue
        assert "data-t" in boton, boton
    etiquetas = {a.get("for") for t, a in elementos() if t == "label"}
    # Campos envueltos en su <label> (etiqueta implícita).
    envueltos = set(re.findall(r'<label[^>]*>(?:(?!</label>).)*?id="([^"]+)"', HTML, re.S))
    for t, a in elementos():
        if t in ("input", "select", "textarea") and a.get("type") not in ("radio", "file"):
            ident = a.get("id")
            assert ident in etiquetas or ident in envueltos or a.get("data-t-aria-label"), a


def test_estructura_accesible_de_la_pagina():
    assert re.search(r'<html lang="es"', HTML)
    assert 'class="saltar" href="#codigo"' in HTML
    assert (
        'role="tablist"' in HTML and HTML.count('role="tab"') == HTML.count('role="tabpanel"') == 6
    )
    assert 'aria-live="polite"' in HTML and 'aria-live="assertive"' in HTML
    assert 'role="tree"' in HTML
    assert "<main" in HTML and "<header" in HTML and "<noscript>" in HTML
    assert 'sandbox="allow-scripts"' in HTML, "el reproductor incrustado va aislado"


def test_css_movimiento_reducido_foco_visible_y_contraste_forzado():
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert ":focus-visible" in CSS and "outline: 3px" in CSS
    assert "@media (forced-colors: active)" in CSS
    assert "min-height: 2.25rem" in CSS, "objetivos táctiles amplios (WCAG 2.5.8)"


@pytest.mark.parametrize("tema", ["claro", "oscuro", "sistema_oscuro"])
def test_contraste_aaa_del_texto_y_3_a_1_de_los_controles(tema):
    assert fallos(temas()[tema]) == []


def test_el_tema_del_sistema_es_identico_al_oscuro():
    t = temas()
    assert t["sistema_oscuro"] == t["oscuro"]


def test_sin_recursos_externos_salvo_pyodide_oficial():
    externos = set(re.findall(r"https?://[^\s\"'`)]+", HTML + "".join(JS.values()) + CSS))
    externos -= {"http://www.w3.org/2000/svg"}
    assert externos == {"https://cdn.jsdelivr.net/pyodide/v0.29.3/full/"}


def test_sin_innerhtml_con_datos_sin_escapar():
    """Cada innerHTML se construye con escaparHTML o con marcado fijo."""
    for nombre, fuente in JS.items():
        for linea in fuente.splitlines():
            if ".innerHTML =" in linea and "resaltarHTML" not in linea:
                assert nombre in ("vista_bloques.js", "editor.js", "app.js"), nombre
    assert "${e(" in JS["vista_bloques.js"]
