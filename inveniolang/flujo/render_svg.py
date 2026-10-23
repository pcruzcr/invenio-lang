"""SVG propio y accesible de un diagrama de flujo (INV-3005).

* **Accesible**: ``role="img"`` con ``<title>`` (nombre del diagrama) y
  ``<desc>`` (la descripción completa de :mod:`render_texto`); cada símbolo
  lleva su ``<title>`` («Decisión, línea 7: i < n»).
* **Sin depender sólo del color**: cada tipo de símbolo tiene su forma ISO
  5807 (óvalo, rectángulo, rombo, paralelogramo, rectángulo con barras,
  círculo); las salidas llevan su etiqueta escrita («Sí»/«No», el valor del
  caso) y los saltos una letra dentro del conector.
* **Temas**: ``claro``, ``oscuro`` o ``auto`` (sigue ``prefers-color-scheme``
  con CSS; los colores también van como atributos, así QtSvg, que ignora el
  CSS, dibuja el tema pedido). Texto ≥ 7:1 sobre su relleno en ambos temas.
* **Determinista**: el mismo diagrama produce el mismo texto byte a byte.
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape, quoteattr

from .. import i18n
from .esquema import ALTO_LINEA, MARGEN, R_UNION, Esquema, NodoEsquema, ancho_texto
from .render_texto import describir_esquema, nombre_rol

__all__ = ["PALETAS", "svg_esquema", "svg_varios"]

CLARO: dict[str, str] = {
    "fondo": "#ffffff",
    "texto": "#1f2328",
    "borde": "#24292f",
    "flecha": "#424a53",
    "terminal": "#ddf4ff",
    "proceso": "#f6f8fa",
    "decision": "#fff8c5",
    "datos": "#dafbe1",
    "predefinido": "#fbefff",
    "conector": "#ffffff",
}
OSCURO: dict[str, str] = {
    "fondo": "#0d1117",
    "texto": "#f0f6fc",
    "borde": "#c9d1d9",
    "flecha": "#c9d1d9",
    "terminal": "#0c2d6b",
    "proceso": "#161b22",
    "decision": "#3b2e00",
    "datos": "#033a16",
    "predefinido": "#3c1e70",
    "conector": "#0d1117",
}
PALETAS: dict[str, dict[str, str]] = {"claro": CLARO, "oscuro": OSCURO}
TEMAS = ("claro", "oscuro", "auto")

FUENTE = "ui-monospace, 'Cascadia Mono', Consolas, 'DejaVu Sans Mono', monospace"
T_TEXTO = 12
INCLINACION = 14.0  # desplazamiento del paralelogramo de datos
BARRA = 10.0  # barras laterales del proceso predefinido


def _n(x: float) -> str:
    """Número estable: un decimal como mucho, sin ``-0``."""
    r = round(float(x), 1)
    if r == int(r):
        return str(int(r)) if r != 0 else "0"
    return f"{r:.1f}"


def _css(prefijo: str) -> str:
    """Reglas por clase; en ``auto`` el modo oscuro entra por media query."""

    def reglas(paleta: dict[str, str]) -> str:
        partes = [
            f".{prefijo}f-{rol}{{fill:{color}}}.{prefijo}s-{rol}{{stroke:{color}}}"
            for rol, color in paleta.items()
        ]
        return "".join(partes)

    return (
        f"<style>{reglas(CLARO)}" f"@media (prefers-color-scheme: dark){{{reglas(OSCURO)}}}</style>"
    )


class _Lienzo:
    def __init__(self, paleta: dict[str, str], idioma: str, prefijo: str):
        self.p = paleta
        self.idioma = idioma
        self.pre = prefijo
        self.partes: list[str] = []

    def clases(self, *pares: tuple[str, str]) -> str:
        nombres = " ".join(f"{self.pre}{'f' if a == 'fill' else 's'}-{r}" for a, r in pares)
        colores = "".join(f' {a}="{self.p[r]}"' for a, r in pares)
        return f'{colores} class="{nombres}"'

    def texto(
        self, x: float, y: float, texto: str, ancla: str = "middle", negrita: bool = False
    ) -> None:
        peso = ' font-weight="bold"' if negrita else ""
        self.partes.append(
            f'<text x="{_n(x)}" y="{_n(y)}" text-anchor="{ancla}" font-size="{T_TEXTO}"'
            f'{peso}{self.clases(("fill", "texto"))}>{escape(texto)}</text>'
        )

    def nodo(self, n: NodoEsquema) -> None:
        donde = i18n.t("FLU.desc.linea", self.idioma, linea=n.linea) if n.linea and n.origen else ""
        titulo = f"{nombre_rol(n, self.idioma)}{donde}"
        if n.texto and n.rol not in ("romper", "continuar"):
            titulo += f": {n.texto}"
        if n.marca:
            titulo += " " + i18n.t("FLU.svg.conector", self.idioma, marca=n.marca)
        origen = f" data-nodo={quoteattr(n.origen)}" if n.origen else ""
        self.partes.append(
            f'<g data-simbolo="{n.simbolo}" data-rol="{n.rol}"{origen}'
            f' data-linea="{n.linea}"><title>{escape(titulo)}</title>'
        )
        trazo = self.clases(("fill", n.simbolo), ("stroke", "borde"))
        x, y, w, h = n.x, n.y, n.w, n.h
        if n.simbolo == "terminal":
            self.partes.append(
                f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}"'
                f' rx="{_n(h / 2)}" stroke-width="1.5"{trazo}/>'
            )
        elif n.simbolo == "decision":
            pts = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
            self._poligono(pts, trazo)
        elif n.simbolo == "datos":
            d = INCLINACION
            pts = [(x + d, y), (x + w, y), (x + w - d, y + h), (x, y + h)]
            self._poligono(pts, trazo)
        elif n.simbolo == "conector":
            r = w / 2
            relleno = self.clases(
                ("fill", "flecha" if n.rol == "union" else "conector"), ("stroke", "borde")
            )
            self.partes.append(
                f'<circle cx="{_n(x + r)}" cy="{_n(y + r)}" r="{_n(r)}"'
                f' stroke-width="1.5"{relleno}/>'
            )
        else:
            self.partes.append(
                f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}"'
                f' stroke-width="1.5"{trazo}/>'
            )
            if n.simbolo == "predefinido":
                for bx in (x + BARRA, x + w - BARRA):
                    self.partes.append(
                        f'<line x1="{_n(bx)}" y1="{_n(y)}" x2="{_n(bx)}" y2="{_n(y + h)}"'
                        f' stroke-width="1.5"{self.clases(("stroke", "borde"))}/>'
                    )
        if n.simbolo == "conector":
            if n.marca:
                self.texto(x + w / 2, y + h / 2 + 4, n.marca, negrita=True)
            if n.rol in ("romper", "continuar"):
                self.texto(x + w + 6, y + h / 2 + 4, n.texto, "start")
        else:
            cy = y + h / 2 - (len(n.lineas) - 1) * ALTO_LINEA / 2 + 4
            for k, linea in enumerate(n.lineas):
                self.texto(x + w / 2, cy + k * ALTO_LINEA, linea)
        self.partes.append("</g>")

    def _poligono(self, pts: list[tuple[float, float]], trazo: str) -> None:
        coords = " ".join(f"{_n(px)},{_n(py)}" for px, py in pts)
        self.partes.append(f'<polygon points="{coords}" stroke-width="1.5"{trazo}/>')

    def flecha(self, puntos: list[tuple[float, float]]) -> None:
        coords = " ".join(f"{_n(px)},{_n(py)}" for px, py in puntos)
        self.partes.append(
            f'<polyline points="{coords}" fill="none" stroke-width="1.5"'
            f'{self.clases(("stroke", "flecha"))}/>'
        )
        (x1, y1), (x2, y2) = puntos[-2], puntos[-1]
        angulo = math.atan2(y2 - y1, x2 - x1)
        tam = 8.0
        p2 = (x2 - tam * math.cos(angulo - math.pi / 7), y2 - tam * math.sin(angulo - math.pi / 7))
        p3 = (x2 - tam * math.cos(angulo + math.pi / 7), y2 - tam * math.sin(angulo + math.pi / 7))
        pts = " ".join(f"{_n(px)},{_n(py)}" for px, py in ((x2, y2), p2, p3))
        self.partes.append(f'<polygon points="{pts}"{self.clases(("fill", "flecha"))}/>')


def _cuerpo(esquema: Esquema, lz: _Lienzo) -> None:
    """Flechas (debajo), símbolos y etiquetas de las salidas."""
    for a in esquema.aristas:
        if not a.salto and len(a.puntos) >= 2:
            lz.flecha(a.puntos)
    for n in esquema.nodos:
        lz.nodo(n)
    for a in esquema.aristas:
        if a.etiqueta and a.pos_etiqueta is not None and not a.salto:
            x, y, ancla = a.pos_etiqueta
            lz.texto(x, y, a.etiqueta, ancla)


def _abrir(ancho: float, alto: float, titulo: str, desc: str, tema: str, prefijo: str) -> list[str]:
    paleta = PALETAS["claro" if tema == "auto" else tema]
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{_n(ancho)}"'
        f' height="{_n(alto)}" viewBox="0 0 {_n(ancho)} {_n(alto)}" role="img"'
        f' aria-labelledby="{prefijo}titulo {prefijo}desc" font-family="{FUENTE}">',
        f'<title id="{prefijo}titulo">{escape(titulo)}</title>',
        f'<desc id="{prefijo}desc">{escape(desc)}</desc>',
    ]
    if tema == "auto":
        partes.append(_css(prefijo))
    partes.append(
        f'<rect x="0" y="0" width="{_n(ancho)}" height="{_n(alto)}" fill="{paleta["fondo"]}"'
        f' class="{prefijo}f-fondo"/>'
    )
    return partes


def _validar_tema(tema: str) -> None:
    if tema not in TEMAS:
        raise ValueError(f"tema inválido {tema!r}; válidos: {', '.join(TEMAS)}")


def svg_esquema(esquema: Esquema, tema: str = "claro") -> str:
    """SVG completo de un diagrama, con ``<title>`` y ``<desc>`` accesibles."""
    _validar_tema(tema)
    prefijo = "flujo-"
    lz = _Lienzo(PALETAS["claro" if tema == "auto" else tema], esquema.idioma, prefijo)
    _cuerpo(esquema, lz)
    partes = _abrir(
        esquema.ancho, esquema.alto, esquema.titulo, describir_esquema(esquema), tema, prefijo
    )
    partes.extend(lz.partes)
    partes.append("</svg>")
    return "".join(partes)


def svg_varios(esquemas: list[Esquema], titulo: str, tema: str = "claro") -> str:
    """Varios diagramas (todas las subrutinas) en un solo SVG, uno bajo otro.

    Cada diagrama va en un grupo con su encabezado visible y su propio
    ``<title>``; la ``<desc>`` del documento reúne las descripciones de todos.
    """
    _validar_tema(tema)
    prefijo = "flujo-"
    idioma = esquemas[0].idioma if esquemas else "es"
    lz = _Lienzo(PALETAS["claro" if tema == "auto" else tema], idioma, prefijo)
    y = 0.0
    ancho = 0.0
    descripciones = []
    for e in esquemas:
        lz.partes.append(
            f'<g transform="translate(0,{_n(y)})" role="group" aria-label={quoteattr(e.titulo)}>'
            f"<title>{escape(e.titulo)}</title>"
        )
        lz.texto(MARGEN, MARGEN + 4, e.titulo, "start", negrita=True)
        lz.partes.append(f'<g transform="translate(0,{_n(ALTO_LINEA + 4)})">')
        _cuerpo(e, lz)
        lz.partes.append("</g></g>")
        y += e.alto + ALTO_LINEA + 4
        ancho = max(ancho, e.ancho, ancho_texto(e.titulo) + 2 * MARGEN)
        descripciones.append(describir_esquema(e))
    alto = max(y, 2 * MARGEN + 2 * R_UNION)
    partes = _abrir(ancho, alto, titulo, "\n\n".join(descripciones), tema, prefijo)
    partes.extend(lz.partes)
    partes.append("</svg>")
    return "".join(partes)
