"""Dibujo SVG de un paso de una Traza (equipo VISTA).

INV-2210: ``svg_paso(paso, idioma)`` devuelve un SVG autónomo con un panel
por estructura viva (arreglo, matriz, pila, cola, lista enlazada, lista
doble, árbol binario, grafo, objeto), la pila de llamadas, las variables de
la subrutina activa, la salida nueva y una leyenda. Decisiones:

* **Determinista**: mismo paso → mismo texto SVG, byte a byte (sin azar, sin
  ``id()`` de Python, sin orden de conjuntos; los números se redondean igual
  siempre). El reproductor HTML y las pruebas dependen de ello.
* **Accesible**: ``role="img"`` + ``<title>``/``<desc>`` (la descripción es la
  de :func:`render_texto.describir`), un ``<title>`` por panel y por celda, y
  los resaltados de lectura/escritura **no dependen sólo del color**: cada
  uno combina borde (discontinuo / grueso), patrón (puntos / rayas) y una
  marca con letra (L/E, R/W).
* **Temas**: la paleta clara y la oscura cumplen WCAG AAA en texto (≥ 7:1) y
  AA en elementos gráficos (≥ 3:1); lo comprueba ``tests/visualizacion``.
  Cada color lleva además una clase ``f-<rol>``/``s-<rol>`` para que el
  reproductor HTML cambie de tema con CSS sin volver a dibujar.
* **Sin dependencias**: sólo cadenas; QtSvg, navegadores y ``xml.etree`` lo
  leen igual (flechas como polígonos, no ``<marker>``).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any
from xml.sax.saxutils import escape

from .. import i18n
from . import render_texto as rt

CLARO: dict[str, str] = {
    "fondo": "#ffffff",
    "panel": "#f6f8fa",
    "panel_borde": "#6e7781",
    "texto": "#1f2328",
    "texto_suave": "#424a53",
    "celda": "#ffffff",
    "celda_borde": "#57606a",
    "lee_fondo": "#ddf4ff",
    "lee_borde": "#0550ae",
    "escribe_fondo": "#fff1e5",
    "escribe_borde": "#953800",
    "acento": "#5a2d9c",
    "arista": "#424a53",
    "activo_fondo": "#fff8c5",
    "activo_borde": "#7d4e00",
}
OSCURO: dict[str, str] = {
    "fondo": "#0d1117",
    "panel": "#161b22",
    "panel_borde": "#8b949e",
    "texto": "#f0f6fc",
    "texto_suave": "#c9d1d9",
    "celda": "#0d1117",
    "celda_borde": "#8b949e",
    "lee_fondo": "#0c2d6b",
    "lee_borde": "#79c0ff",
    "escribe_fondo": "#5a1e02",
    "escribe_borde": "#ffa657",
    "acento": "#d2a8ff",
    "arista": "#c9d1d9",
    "activo_fondo": "#3b2e00",
    "activo_borde": "#e3b341",
}
PALETAS: dict[str, dict[str, str]] = {"claro": CLARO, "oscuro": OSCURO}

FUENTE = "system-ui, 'Segoe UI', Roboto, 'Noto Sans', 'DejaVu Sans', sans-serif"
FUENTE_MONO = "ui-monospace, 'Cascadia Mono', Consolas, 'DejaVu Sans Mono', monospace"
T_VALOR = 14  # px: valores en celdas (legible a un metro de un proyector)
T_ETIQUETA = 12
T_TITULO = 14
MARGEN = 16
SEPARACION = 16
CABECERA = 34
RELLENO = 14

# Límites de dibujo: por encima, el panel se recorta y lo dice ("Se muestran
# X de Y"); la descripción textual sigue contando la estructura completa.
MAX_CELDAS = 256
POR_FILA = 16
MAX_FILAS_MATRIZ = 24
MAX_PILA = 40
MAX_LISTA = 24
MAX_NIVELES_ARBOL = 10
MAX_VERTICES = 40
MAX_MARCOS = 24
MAX_SALIDA = 10

# Campos del contenedor que apuntan a cada extremo (tope, frente, final…).
CAMPOS_TOPE = frozenset({"cima", "tope", "top"})
CAMPOS_FRENTE = frozenset({"frente", "front", "cabeza", "head", "primero", "first", "inicio"})
CAMPOS_FINAL = frozenset(
    {"final", "fin", "rear", "back", "cola", "tail", "ultimo", "último", "last"}
)
CAMPOS_SIG = frozenset({"siguiente", "sig", "next", "abajo", "below", "debajo"})
CAMPOS_ANT = frozenset({"anterior", "ant", "prev", "previous", "previo"})


def _n(x: float) -> str:
    """Número estable para el SVG: 1 decimal como mucho, sin ``-0``."""
    r = round(float(x), 1)
    if r == int(r):
        return str(int(r)) if r != 0 else "0"
    return f"{r:.1f}"


def _ancho(texto: str, tam: float, mono: bool = True) -> float:
    return len(texto) * tam * (0.6 if mono else 0.56)


def _recortar(texto: str, ancho: float, tam: float = T_VALOR) -> str:
    cabe = max(1, int(ancho / (tam * 0.6)))
    return texto if len(texto) <= cabe else texto[: max(1, cabe - 1)] + "…"


def combinar(a: str | None, b: str | None) -> str | None:
    """Une dos estados de acceso (``lee`` + ``escribe`` → ``ambos``)."""
    if a is None or a == b:
        return b if a is None else a
    if b is None:
        return a
    return "ambos"


class Lienzo:
    """Acumula elementos SVG con la paleta del tema (patrón Builder)."""

    def __init__(self, paleta: Mapping[str, str], idioma: str):
        self.p = paleta
        self.idioma = idioma
        self.partes: list[str] = []

    def _color(self, attr: str, rol: str | None) -> tuple[str, str]:
        if rol is None:
            return f' {attr}="none"', ""
        return f' {attr}="{self.p[rol]}"', ("f-" if attr == "fill" else "s-") + rol

    def _clase(self, *clases: str) -> str:
        c = " ".join(x for x in clases if x)
        return f' class="{c}"' if c else ""

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        relleno: str | None,
        borde: str | None = None,
        grosor: float = 1.5,
        guiones: str | None = None,
        radio: float = 4,
        patron: str | None = None,
    ) -> None:
        """Rectángulo con relleno/borde de la paleta (o un patrón ``url(#…)``)."""
        if patron is not None:
            fill, cf = f' fill="url(#{patron})"', ""
        else:
            fill, cf = self._color("fill", relleno)
        stroke, cs = self._color("stroke", borde)
        extra = f' stroke-width="{_n(grosor)}"' if borde else ""
        if guiones and borde:
            extra += f' stroke-dasharray="{guiones}"'
        self.partes.append(
            f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" rx="{_n(radio)}"'
            f"{fill}{stroke}{extra}{self._clase(cf, cs)}/>"
        )

    def texto(
        self,
        x: float,
        y: float,
        contenido: str,
        rol: str = "texto",
        tam: float = T_VALOR,
        ancla: str = "middle",
        mono: bool = True,
        negrita: bool = False,
    ) -> None:
        """Texto con la fuente monoespaciada (valores) o la de interfaz."""
        fam = "m" if mono else "s"
        peso = ' font-weight="700"' if negrita else ""
        fill, cf = self._color("fill", rol)
        self.partes.append(
            f'<text x="{_n(x)}" y="{_n(y)}" font-size="{_n(tam)}" text-anchor="{ancla}"'
            f' font-family="{FUENTE_MONO if fam == "m" else FUENTE}"{peso}{fill}{self._clase(cf)}>'
            f"{escape(contenido)}</text>"
        )

    def linea(
        self, x1: float, y1: float, x2: float, y2: float, rol: str = "arista", grosor: float = 1.5
    ) -> None:
        """Segmento recto."""
        stroke, cs = self._color("stroke", rol)
        self.partes.append(
            f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}"{stroke}'
            f' stroke-width="{_n(grosor)}"{self._clase(cs)}/>'
        )

    def flecha(
        self, x1: float, y1: float, x2: float, y2: float, rol: str = "arista", punta: float = 9
    ) -> None:
        """Segmento con punta triangular dibujada como polígono."""
        largo = math.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / largo, (y2 - y1) / largo
        bx, by = x2 - ux * punta, y2 - uy * punta
        self.linea(x1, y1, bx, by, rol)
        px, py = -uy * punta * 0.45, ux * punta * 0.45
        fill, cf = self._color("fill", rol)
        puntos = f"{_n(x2)},{_n(y2)} {_n(bx + px)},{_n(by + py)} {_n(bx - px)},{_n(by - py)}"
        self.partes.append(f'<polygon points="{puntos}"{fill}{self._clase(cf)}/>')

    def circulo(
        self,
        cx: float,
        cy: float,
        r: float,
        relleno: str | None,
        borde: str | None,
        grosor: float = 1.5,
        guiones: str | None = None,
    ) -> None:
        """Círculo (vértices de grafo, anillo de visitado)."""
        fill, cf = self._color("fill", relleno)
        stroke, cs = self._color("stroke", borde)
        extra = f' stroke-width="{_n(grosor)}"' if borde else ""
        if guiones and borde:
            extra += f' stroke-dasharray="{guiones}"'
        self.partes.append(
            f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}"'
            f"{fill}{stroke}{extra}{self._clase(cf, cs)}/>"
        )

    def grupo(self, titulo: str, x: float = 0, y: float = 0) -> None:
        """Abre un ``<g>`` con nombre accesible y ``<title>``."""
        mov = f' transform="translate({_n(x)},{_n(y)})"' if x or y else ""
        self.partes.append(
            f'<g role="group" aria-label="{escape(titulo, {chr(34): "&quot;"})}"{mov}>'
        )
        self.partes.append(f"<title>{escape(titulo)}</title>")

    def fin_grupo(self) -> None:
        """Cierra el último ``<g>``."""
        self.partes.append("</g>")

    def estilo_estado(self, estado: str | None) -> tuple[str, str, float, str | None, str | None]:
        """(relleno, borde, grosor, guiones, patrón) de una celda según su acceso."""
        if estado == "lee":
            return "lee_fondo", "lee_borde", 2.0, "5 3", "vis-pat-lee"
        if estado in ("escribe", "ambos"):
            return "escribe_fondo", "escribe_borde", 3.0, None, "vis-pat-escribe"
        return "celda", "celda_borde", 1.5, None, None

    def palabra_estado(self, estado: str | None) -> str:
        """Texto del estado para los ``<title>`` (no sólo color: también se dice)."""
        if estado is None:
            return ""
        partes = []
        if estado in ("lee", "ambos"):
            partes.append(i18n.t("VIS.svg.leido", self.idioma))
        if estado in ("escribe", "ambos"):
            partes.append(i18n.t("VIS.svg.escrito", self.idioma))
        return " — " + "; ".join(partes)

    def celda(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        contenido: str,
        estado: str | None,
        titulo: str,
        radio: float = 4,
        marca_fuera: bool = False,
    ) -> None:
        """Celda con valor; si se accedió, borde + patrón + marca con letra.

        ``marca_fuera`` coloca la insignia sobre la esquina (nodos redondos de
        árbol, donde dentro taparía el valor).
        """
        self.grupo(titulo + self.palabra_estado(estado), x, y)
        relleno, borde, grosor, guiones, patron = self.estilo_estado(estado)
        self.rect(0, 0, w, h, relleno, borde, grosor, guiones, radio)
        base = h / 2 + T_VALOR * 0.35
        if patron is not None:
            self.rect(grosor, h - 7 - grosor / 2, w - 2 * grosor, 6, None, patron=patron, radio=0)
            base -= 3
        # con insignia dentro, el valor se corre a la izquierda para no taparse
        dentro = estado is not None and not marca_fuera
        self.texto(
            w / 2 - (8 if dentro else 0), base, _recortar(contenido, w - (26 if dentro else 10))
        )
        if estado is not None:
            self.marca(w + (8 if marca_fuera else 0), estado, -12 if marca_fuera else 2)
        self.fin_grupo()

    def marca(self, w: float, estado: str, y: float = 2) -> None:
        """Insignia con letra en la esquina (L/E o R/W; ambas si lee y escribe)."""
        letras = []
        if estado in ("lee", "ambos"):
            letras.append(i18n.t("VIS.svg.marca_lee", self.idioma))
        if estado in ("escribe", "ambos"):
            letras.append(i18n.t("VIS.svg.marca_escribe", self.idioma))
        texto = "".join(letras)
        ancho = 8 + 7 * len(texto)
        rol = "lee_borde" if estado == "lee" else "escribe_borde"
        self.rect(w - ancho - 2, y, ancho, 14, rol, radio=3)
        self.texto(w - ancho / 2 - 2, y + 11, texto, "fondo", 10, mono=False, negrita=True)

    def etiqueta(self, x: float, y: float, contenido: str, estado: str | None = None) -> float:
        """Rótulo tipo "tope", "frente", "raíz"; devuelve su ancho."""
        if estado is not None:
            # la letra (L/E, R/W) hace que el resaltado no dependa sólo del color
            letras = []
            if estado in ("lee", "ambos"):
                letras.append(i18n.t("VIS.svg.marca_lee", self.idioma))
            if estado in ("escribe", "ambos"):
                letras.append(i18n.t("VIS.svg.marca_escribe", self.idioma))
            contenido = f"{contenido} · {''.join(letras)}"
        w = _ancho(contenido, T_ETIQUETA, mono=False) + 14
        relleno, borde, grosor, guiones, _ = self.estilo_estado(estado)
        self.rect(
            x, y, w, 20, relleno, "acento" if estado is None else borde, grosor, guiones, radio=10
        )
        self.texto(
            x + w / 2,
            y + 14,
            contenido,
            "acento" if estado is None else "texto",
            T_ETIQUETA,
            mono=False,
            negrita=True,
        )
        return w


class Panel:
    """Fragmento ya dibujado en coordenadas locales, con su tamaño."""

    def __init__(self, ancho: float, alto: float, partes: list[str]):
        self.ancho = ancho
        self.alto = alto
        self.partes = partes


def _panel(lz: Lienzo, titulo: str, ancho: float, alto_cuerpo: float, cuerpo: list[str]) -> Panel:
    """Envuelve el cuerpo con fondo, borde y cabecera del panel."""
    ancho = max(ancho, _ancho(titulo, T_TITULO, mono=False) + 2 * RELLENO)
    alto = CABECERA + alto_cuerpo + RELLENO
    marco = Lienzo(lz.p, lz.idioma)
    marco.grupo(titulo)
    marco.rect(0, 0, ancho, alto, "panel", "panel_borde", 1, radio=8)
    marco.texto(RELLENO, 23, titulo, "texto", T_TITULO, ancla="start", mono=False, negrita=True)
    marco.partes.append(f'<g transform="translate({RELLENO},{CABECERA})">')
    marco.partes.extend(cuerpo)
    marco.partes.append("</g>")
    marco.fin_grupo()
    return Panel(ancho, alto, marco.partes)


def _ancho_celda(textos: Sequence[str], minimo: float = 44, maximo: float = 140) -> float:
    largo = max((len(t) for t in textos), default=1)
    return min(maximo, max(minimo, largo * T_VALOR * 0.6 + 18))


def _nota_recorte(lz: Lienzo, y: float, mostrados: int, total: int) -> float:
    if mostrados >= total:
        return y
    lz.texto(
        0,
        y + 16,
        i18n.t("VIS.svg.recortado", lz.idioma, mostrados=mostrados, total=total),
        "texto_suave",
        T_ETIQUETA,
        "start",
        mono=False,
    )
    return y + 24


# ----------------------------------------------------------------- formas


class Contexto:
    """Lo que todos los paneles necesitan del paso, calculado una sola vez."""

    def __init__(self, paso: Mapping[str, Any], idioma: str, paleta: Mapping[str, str]):
        self.paso = paso
        self.idioma = idioma
        self.paleta = paleta
        self.estados = rt.estado_accesos(paso)
        self.nombres = rt.nombres_de_nodos(paso, idioma)

    def vt(self, valor: Any) -> str:
        """Texto de un valor con nombres legibles para las referencias."""
        return rt.valor_texto(valor, self.idioma, self.nombres)

    def lienzo(self) -> Lienzo:
        """Lienzo nuevo con la paleta e idioma del paso."""
        return Lienzo(self.paleta, self.idioma)

    def estado_nodo(self, nodo: int | None, excluir: frozenset[str] = frozenset()) -> str | None:
        """Estado de un nodo por los accesos a sus campos (salvo ``excluir``)."""
        if nodo is None:
            return None
        estado = None
        for clave, valor in self.estados.items():
            if clave[0] == "campo" and clave[1] == nodo and clave[2].lower() not in excluir:
                estado = combinar(estado, valor)
            elif clave[0] == "celda" and clave[1] == nodo:
                estado = combinar(estado, valor)
        return estado

    def estado_campos(self, nodo: int, campos: frozenset[str]) -> str | None:
        """Estado de los campos ``campos`` de ``nodo``."""
        estado = None
        for clave, valor in self.estados.items():
            if clave[0] == "campo" and clave[1] == nodo and clave[2].lower() in campos:
                estado = combinar(estado, valor)
        return estado


def _titulo_panel(est: Mapping[str, Any], idioma: str) -> str:
    forma = i18n.t(f"VIS.forma.{est['forma']}", idioma)
    return i18n.t(
        "VIS.svg.panel", idioma, etiqueta=est["etiqueta"] or f"#{est['raiz']}", forma=forma
    )


def panel_arreglo(est: Mapping[str, Any], ctx: Contexto) -> Panel:
    """Celdas con índice debajo, en filas de ``POR_FILA``."""
    lz = ctx.lienzo()
    nodo = ctx.paso["monticulo"].get(est["raiz"])
    elementos = list(nodo["elementos"]) if nodo else []
    textos = [ctx.vt(v) for v in elementos[:MAX_CELDAS]]
    w, h = _ancho_celda(textos), 40.0
    etq = est["etiqueta"] or f"#{est['raiz']}"
    for i, texto in enumerate(textos):
        fila, col = divmod(i, POR_FILA)
        x, y = col * (w + 4), fila * (h + 26)
        estado = ctx.estados.get(("celda", est["raiz"], i))
        lz.celda(x, y, w, h, texto, estado, f"{etq}[{i}] = {texto}")
        lz.texto(x + w / 2, y + h + 16, str(i), "texto_suave", T_ETIQUETA)
    filas = max(1, math.ceil(len(textos) / POR_FILA))
    if not textos:
        lz.celda(
            0,
            0,
            120,
            h,
            i18n.t("VIS.svg.vacia", ctx.idioma),
            None,
            i18n.t("VIS.svg.vacia", ctx.idioma),
        )
    alto = _nota_recorte(lz, filas * (h + 26) - 4, len(textos), len(elementos))
    ancho = min(len(textos), POR_FILA) * (w + 4) + 2 * RELLENO
    return _panel(lz, _titulo_panel(est, ctx.idioma), max(ancho, 150), alto, lz.partes)


def panel_matriz(est: Mapping[str, Any], ctx: Contexto) -> Panel:
    """Rejilla con índices de fila a la izquierda y de columna arriba."""
    lz = ctx.lienzo()
    filas, ids_fila = rt.filas_matriz(est, ctx.paso)
    por_id = {i: fila_id for fila_id, i in ids_fila.items()}
    vista = [f[:MAX_FILAS_MATRIZ] for f in filas[:MAX_FILAS_MATRIZ]]
    textos = [[ctx.vt(v) for v in fila] for fila in vista]
    w, h = _ancho_celda([t for fila in textos for t in fila]), 36.0
    columnas = max((len(f) for f in textos), default=0)
    izq, arriba = 30.0, 20.0
    etq = est["etiqueta"] or f"#{est['raiz']}"
    for j in range(columnas):
        lz.texto(izq + j * (w + 4) + w / 2, 13, str(j), "texto_suave", T_ETIQUETA)
    for i, fila in enumerate(textos):
        y = arriba + i * (h + 4)
        lz.texto(izq - 10, y + h / 2 + 4, str(i), "texto_suave", T_ETIQUETA, "end")
        for j, texto in enumerate(fila):
            estado = combinar(
                ctx.estados.get(("celda", est["raiz"], i, j)),
                ctx.estados.get(("celda", por_id[i], j)) if i in por_id else None,
            )
            lz.celda(izq + j * (w + 4), y, w, h, texto, estado, f"{etq}[{i}][{j}] = {texto}")
    alto = arriba + len(textos) * (h + 4)
    total = sum(len(f) for f in filas)
    alto = _nota_recorte(lz, alto, sum(len(f) for f in textos), total)
    return _panel(
        lz, _titulo_panel(est, ctx.idioma), izq + columnas * (w + 4) + 2 * RELLENO, alto, lz.partes
    )


def _estado_extremo(ctx: Contexto, est: Mapping[str, Any], campos: frozenset[str]) -> str | None:
    return ctx.estado_campos(est["raiz"], campos)


def _estados_secuencia(
    est: Mapping[str, Any], ctx: Contexto, elems: Sequence[tuple[int | None, Any]]
) -> list[str | None]:
    """Estado de cada elemento: por su nodo o, si vive en un arreglo, por su celda."""
    estados: list[str | None] = []
    # INV-4400: el elemento k (desde la cima) de una pila sobre arreglo es la
    # celda cima - k; antes se contaba desde el final de lo que se dibujaba,
    # lo que fallaba si la pila no llenaba el arreglo o se recortaba la vista.
    cima = rt.indice_cima(est, ctx.paso) if est["forma"] == "pila" else 0
    for k, (nodo, _) in enumerate(elems):
        if nodo is not None:
            estados.append(ctx.estado_nodo(nodo, CAMPOS_SIG | CAMPOS_ANT))
        else:
            indice = cima - k if est["forma"] == "pila" else k
            estados.append(ctx.estados.get(("celda", est["raiz"], indice)))
    return estados


def panel_pila(est: Mapping[str, Any], ctx: Contexto) -> Panel:
    """Pila vertical: el tope arriba, la base abajo."""
    lz = ctx.lienzo()
    elems = rt.secuencia(est, ctx.paso)
    vista = elems[:MAX_PILA]
    textos = [ctx.vt(v) for _, v in vista]
    estados = _estados_secuencia(est, ctx, vista)
    w, h = _ancho_celda(textos, 72, 180), 36.0
    col = 74.0
    if not vista:
        lz.rect(col, 0, w, h, "celda", "celda_borde", 1.5, "4 4")
        lz.texto(
            col + w / 2,
            h / 2 + 5,
            i18n.t("VIS.svg.vacia", ctx.idioma),
            "texto_suave",
            T_ETIQUETA,
            mono=False,
        )
    for k, texto in enumerate(textos):
        y = k * (h + 4)
        lz.celda(col, y, w, h, texto, estados[k], f"{k}: {texto}")
    if vista:
        lz.etiqueta(
            0, 8, i18n.t("VIS.svg.tope", ctx.idioma), _estado_extremo(ctx, est, CAMPOS_TOPE)
        )
        if len(vista) > 1:
            lz.etiqueta(0, (len(vista) - 1) * (h + 4) + 8, i18n.t("VIS.svg.base", ctx.idioma))
    alto = max(1, len(vista)) * (h + 4)
    alto = _nota_recorte(lz, alto, len(vista), len(elems))
    return _panel(lz, _titulo_panel(est, ctx.idioma), col + w + 2 * RELLENO, alto, lz.partes)


def panel_cola(est: Mapping[str, Any], ctx: Contexto) -> Panel:
    """Cola horizontal: frente a la izquierda, final a la derecha."""
    lz = ctx.lienzo()
    elems = rt.secuencia(est, ctx.paso)
    vista = elems[:MAX_LISTA]
    textos = [ctx.vt(v) for _, v in vista]
    estados = _estados_secuencia(est, ctx, vista)
    w, h = _ancho_celda(textos), 40.0
    y0 = 30.0
    if not vista:
        lz.rect(0, y0, 120, h, "celda", "celda_borde", 1.5, "4 4")
        lz.texto(
            60,
            y0 + h / 2 + 5,
            i18n.t("VIS.svg.vacia", ctx.idioma),
            "texto_suave",
            T_ETIQUETA,
            mono=False,
        )
    for k, texto in enumerate(textos):
        lz.celda(k * (w + 6), y0, w, h, texto, estados[k], f"{k}: {texto}")
    if vista:
        frente = i18n.t("VIS.svg.frente", ctx.idioma)
        final = i18n.t("VIS.svg.final", ctx.idioma)
        if len(vista) == 1:
            lz.etiqueta(
                0,
                0,
                f"{frente} · {final}",
                combinar(
                    _estado_extremo(ctx, est, CAMPOS_FRENTE),
                    _estado_extremo(ctx, est, CAMPOS_FINAL),
                ),
            )
        else:
            lz.etiqueta(0, 0, frente, _estado_extremo(ctx, est, CAMPOS_FRENTE))
            ancho_final = _ancho(final, T_ETIQUETA, mono=False) + 14
            lz.etiqueta(
                (len(vista) - 1) * (w + 6) + w - ancho_final,
                0,
                final,
                _estado_extremo(ctx, est, CAMPOS_FINAL),
            )
    alto = _nota_recorte(lz, y0 + h, len(vista), len(elems))
    ancho = max(1, len(vista)) * (w + 6) + 2 * RELLENO
    return _panel(lz, _titulo_panel(est, ctx.idioma), max(ancho, 200), alto, lz.partes)


def _caja_nulo(lz: Lienzo, x: float, y: float, h: float) -> float:
    nulo = i18n.t("VIS.valor.nulo", lz.idioma)
    w = _ancho(nulo, T_ETIQUETA) + 16
    lz.rect(x, y + 6, w, h - 12, None, "celda_borde", 1.5, "4 3")
    lz.texto(x + w / 2, y + h / 2 + 4, nulo, "texto_suave", T_ETIQUETA)
    return w


def panel_lista(est: Mapping[str, Any], ctx: Contexto) -> Panel:
    """Lista simple ``[valor|•]→`` o doble ``[•|valor|•]⇄`` terminada en nulo."""
    lz = ctx.lienzo()
    doble = est["forma"] == "lista_doble"
    elems = rt.secuencia(est, ctx.paso)
    vista = elems[:MAX_LISTA]
    textos = [ctx.vt(v) for _, v in vista]
    wv, h, ptr, hueco = _ancho_celda(textos, 44, 120), 40.0, 22.0, 40.0
    w = wv + ptr * (2 if doble else 1)
    y0 = 30.0
    x0 = 0.0
    if doble and vista:
        x0 = _caja_nulo(lz, 0, y0, h) + hueco
    for k, (nodo, _) in enumerate(vista):
        x = x0 + k * (w + hueco)
        titulo = f"{k}: {textos[k]}"
        estado_valor = ctx.estado_nodo(nodo, CAMPOS_SIG | CAMPOS_ANT)
        izq = ptr if doble else 0.0
        if doble:
            _puntero(lz, ctx, x, y0, ptr, h, nodo, CAMPOS_ANT, titulo)
        lz.celda(x + izq, y0, wv, h, textos[k], estado_valor, titulo, radio=0)
        _puntero(lz, ctx, x + izq + wv, y0, ptr, h, nodo, CAMPOS_SIG, titulo)
        siguiente_x = x + w + hueco
        if k + 1 < len(vista):
            lz.flecha(
                x + w - ptr / 2,
                y0 + (13 if doble else h / 2),
                siguiente_x,
                y0 + (13 if doble else h / 2),
            )
            if doble:
                lz.flecha(siguiente_x + ptr / 2, y0 + 27, x + w, y0 + 27)
    if vista:
        fin_x = x0 + len(vista) * (w + hueco)
        lz.flecha(
            fin_x - hueco - ptr / 2,
            y0 + (13 if doble else h / 2),
            fin_x,
            y0 + (13 if doble else h / 2),
        )
        w_nulo = _caja_nulo(lz, fin_x, y0, h)
        if doble:
            lz.flecha(x0 + ptr / 2, y0 + 27, x0 - hueco, y0 + 27)
        lz.etiqueta(
            x0, 0, i18n.t("VIS.svg.cabeza", ctx.idioma), _estado_extremo(ctx, est, CAMPOS_FRENTE)
        )
        if doble and len(vista) > 1:
            final = i18n.t("VIS.svg.cola_lista", ctx.idioma)
            ancho_final = _ancho(final, T_ETIQUETA, mono=False) + 14
            lz.etiqueta(
                x0 + (len(vista) - 1) * (w + hueco) + w - ancho_final,
                0,
                final,
                _estado_extremo(ctx, est, CAMPOS_FINAL),
            )
        ancho = fin_x + w_nulo
    else:
        ancho = _caja_nulo(lz, 0, y0, h) + 20
        lz.etiqueta(
            0, 0, i18n.t("VIS.svg.cabeza", ctx.idioma), _estado_extremo(ctx, est, CAMPOS_FRENTE)
        )
    alto = _nota_recorte(lz, y0 + h, len(vista), len(elems))
    return _panel(lz, _titulo_panel(est, ctx.idioma), ancho + 2 * RELLENO, alto, lz.partes)


def _puntero(
    lz: Lienzo,
    ctx: Contexto,
    x: float,
    y: float,
    w: float,
    h: float,
    nodo: int | None,
    campos: frozenset[str],
    titulo: str,
) -> None:
    """Compartimento de enlace con su punto; se resalta si se tocó ese campo."""
    estado = ctx.estado_campos(nodo, campos) if nodo is not None else None
    relleno, borde, grosor, guiones, _ = lz.estilo_estado(estado)
    lz.grupo(titulo + lz.palabra_estado(estado), x, y)
    lz.rect(0, 0, w, h, relleno, borde, grosor, guiones, radio=0)
    lz.circulo(w / 2, h / 2, 3.5, "arista", None)
    lz.fin_grupo()


def disposicion_arbol(
    raiz: int | None, hijos: Mapping[int, Mapping[str, int]], max_niveles: int = MAX_NIVELES_ARBOL
) -> dict[int, tuple[float, int]]:
    """Posición ``(x, nivel)`` de cada nodo: Reingold–Tilford simplificado.

    Cada subárbol se resume en su contorno izquierdo y derecho por nivel;
    dos hermanos se separan lo justo para que, en todos los niveles comunes,
    haya al menos una unidad entre ellos. Un hijo único se desplaza media
    unidad hacia su lado, para que izquierdo y derecho se distingan sin
    color. Iterativo (no recursivo): un árbol degenerado de miles de nodos
    no agota la pila de Python. Las ``x`` quedan en unidades ≥ 0.
    """
    if raiz is None:
        return {}
    orden: list[tuple[int, int]] = []
    pila, vistos = [(raiz, 0)], {raiz}
    while pila:
        n, nivel = pila.pop()
        orden.append((n, nivel))
        if nivel + 1 >= max_niveles:
            continue
        for lado in ("izq", "der"):
            h = hijos.get(n, {}).get(lado)
            if h is not None and h not in vistos:
                vistos.add(h)
                pila.append((h, nivel + 1))
    incluidos = {n for n, _ in orden}
    contorno: dict[int, tuple[list[float], list[float]]] = {}
    desplaz: dict[int, float] = {}
    for n, _ in reversed(orden):
        hi = hijos.get(n, {}).get("izq")
        hd = hijos.get(n, {}).get("der")
        hi = hi if hi in incluidos and hi in contorno else None
        hd = hd if hd in incluidos and hd in contorno else None
        if hi is not None and hd is not None:
            li, ri = contorno[hi]
            ld, rd = contorno[hd]
            sep = max(ri[k] - ld[k] for k in range(min(len(ri), len(ld)))) + 1.0
            desplaz[hi], desplaz[hd] = -sep / 2, sep / 2
        elif hi is not None:
            desplaz[hi] = -0.5
        elif hd is not None:
            desplaz[hd] = 0.5
        izq, der = [0.0], [0.0]
        for h in (hi, hd):
            if h is None:
                continue
            hl, hr = contorno[h]
            for k in range(len(hl)):
                if k + 1 < len(izq):
                    izq[k + 1] = min(izq[k + 1], hl[k] + desplaz[h])
                    der[k + 1] = max(der[k + 1], hr[k] + desplaz[h])
                else:
                    izq.append(hl[k] + desplaz[h])
                    der.append(hr[k] + desplaz[h])
        contorno[n] = (izq, der)
    pos: dict[int, tuple[float, int]] = {raiz: (0.0, 0)}
    for n, nivel in orden:
        x = pos[n][0]
        for lado in ("izq", "der"):
            h = hijos.get(n, {}).get(lado)
            if h is not None and h in desplaz and h not in pos:
                pos[h] = (x + desplaz[h], nivel + 1)
    minimo = min(x for x, _ in pos.values())
    return {n: (x - minimo, nivel) for n, (x, nivel) in pos.items()}


def panel_arbol(est: Mapping[str, Any], ctx: Contexto) -> Panel:
    """Árbol por niveles, sin solapes (ver :func:`disposicion_arbol`)."""
    lz = ctx.lienzo()
    raiz, hijos = rt.arbol(est, ctx.paso)
    pos = disposicion_arbol(raiz, hijos)
    monticulo = ctx.paso["monticulo"]
    textos = {n: ctx.vt(rt.valor_de_nodo(monticulo.get(n))) for n in pos}
    w = _ancho_celda(list(textos.values()), 40, 110)
    h, unidad, nivel_alto, y0 = 34.0, w + 14, 64.0, 28.0
    if raiz is None:
        lz.rect(0, y0, 120, h, "celda", "celda_borde", 1.5, "4 4")
        lz.texto(
            60,
            y0 + h / 2 + 5,
            i18n.t("VIS.svg.vacia", ctx.idioma),
            "texto_suave",
            T_ETIQUETA,
            mono=False,
        )
        return _panel(lz, _titulo_panel(est, ctx.idioma), 150, y0 + h, lz.partes)

    def centro(n: int) -> tuple[float, float]:
        x, nivel = pos[n]
        return x * unidad + w / 2, y0 + nivel * nivel_alto

    for n in sorted(pos, key=lambda k: (pos[k][1], pos[k][0])):
        for lado in ("izq", "der"):
            hijo = hijos.get(n, {}).get(lado)
            if hijo in pos:
                (x1, y1), (x2, y2) = centro(n), centro(hijo)
                lz.linea(x1, y1 + h, x2, y2)
    for n in sorted(pos, key=lambda k: (pos[k][1], pos[k][0])):
        cx, y = centro(n)
        estado = ctx.estado_nodo(n)
        lz.celda(cx - w / 2, y, w, h, textos[n], estado, textos[n], radio=h / 2, marca_fuera=True)
    cx, _ = centro(raiz)
    rotulo = i18n.t("VIS.svg.raiz", ctx.idioma)
    lz.etiqueta(cx - (_ancho(rotulo, T_ETIQUETA, mono=False) + 14) / 2, 0, rotulo)
    niveles = max(nivel for _, nivel in pos.values()) + 1
    ancho = (max(x for x, _ in pos.values())) * unidad + w
    alto = y0 + (niveles - 1) * nivel_alto + h
    total = sum(len(nv) for nv in rt.niveles_arbol(raiz, hijos))
    alto = _nota_recorte(lz, alto, len(pos), total)
    return _panel(lz, _titulo_panel(est, ctx.idioma), ancho + 2 * RELLENO, alto, lz.partes)


def disposicion_circular(n: int, radio: float) -> list[tuple[float, float]]:
    """Posiciones en círculo (sentido horario desde arriba): determinista."""
    if n == 1:
        return [(radio, radio)]
    return [
        (
            radio + radio * math.cos(-math.pi / 2 + 2 * math.pi * k / n),
            radio + radio * math.sin(-math.pi / 2 + 2 * math.pi * k / n),
        )
        for k in range(n)
    ]


def panel_grafo(est: Mapping[str, Any], ctx: Contexto) -> Panel:
    """Grafo en disposición circular; pesos en píldoras sobre cada arista."""
    lz = ctx.lienzo()
    vertices, aristas = rt.grafo(est, ctx.paso)
    vista = vertices[:MAX_VERTICES]
    rv = 22.0
    radio = max(70.0, len(vista) * 20.0)
    margen = rv + 26
    crudas = disposicion_circular(len(vista), radio)
    arriba = min((y for _, y in crudas), default=0.0)
    pos = {v: (x + margen, y - arriba + margen) for v, (x, y) in zip(vista, crudas, strict=True)}
    indices = rt.grafo_por_indices(est, ctx.paso) is not None
    rot = {v: rt.etiqueta_vertice(v, ctx.paso, ctx.idioma, indices) for v in vista}
    pares = {(u, v) for u, v, _, _ in aristas}
    pildoras: list[tuple[float, float, str]] = []
    for u, v, peso, dirigida in aristas:
        if u not in pos or v not in pos:
            continue
        (x1, y1), (x2, y2) = pos[u], pos[v]
        if u == v:
            lz.circulo(x1, y1 - rv - 10, 11, None, "arista")
            if peso:
                pildoras.append((x1, y1 - rv - 30, peso))
            continue
        d = math.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / d, (y2 - y1) / d
        desplazo = 6.0 if dirigida and (v, u) in pares else 0.0
        px, py = -uy * desplazo, ux * desplazo
        a = (x1 + ux * rv + px, y1 + uy * rv + py)
        b = (x2 - ux * rv + px, y2 - uy * rv + py)
        if dirigida:
            lz.flecha(a[0], a[1], b[0], b[1])
        else:
            lz.linea(a[0], a[1], b[0], b[1])
        if peso:
            pildoras.append(((a[0] + b[0]) / 2 + px * 2, (a[1] + b[1]) / 2 + py * 2, peso))
    for x, y, peso in pildoras:
        ancho = _ancho(peso, T_ETIQUETA) + 12
        lz.rect(x - ancho / 2, y - 10, ancho, 20, "celda", "arista", 1, radio=10)
        lz.texto(x, y + 4, peso, "texto", T_ETIQUETA)
    for v in vista:
        x, y = pos[v]
        estado = None if indices else ctx.estado_nodo(v)
        relleno, borde, grosor, guiones, _ = lz.estilo_estado(estado)
        vis = rt.visitado(v, ctx.paso, indices)
        extra = (" — " + i18n.t("VIS.svg.visitado", ctx.idioma)) if vis else ""
        lz.grupo(rot[v] + extra + lz.palabra_estado(estado))
        if vis:
            lz.circulo(x, y, rv + 5, None, "acento", 2)
        lz.circulo(x, y, rv, relleno, borde, grosor, guiones)
        lz.texto(x, y + 5, _recortar(rot[v], 2 * rv - 6))
        if estado is not None:
            lz.partes.append(f'<g transform="translate({_n(x - rv - 4)},{_n(y - rv - 12)})">')
            lz.marca(2 * rv + 8, estado)
            lz.partes.append("</g>")
        if vis:
            lz.texto(
                x - rv - 3, y - rv + 6, "✓", "acento", T_TITULO, "end", mono=False, negrita=True
            )
        lz.fin_grupo()
    lado = 2 * radio + 2 * margen if len(vista) > 1 else 2 * margen
    alto = max((y for _, y in pos.values()), default=0.0) + margen
    alto = _nota_recorte(lz, alto, len(vista), len(vertices))
    return _panel(lz, _titulo_panel(est, ctx.idioma), lado + 2 * RELLENO, alto, lz.partes)


def panel_objeto(est: Mapping[str, Any], ctx: Contexto) -> Panel:
    """Objeto como tabla campo | valor."""
    lz = ctx.lienzo()
    nodo = ctx.paso["monticulo"].get(est["raiz"]) or {"campos": {}, "clase": None}
    filas = [(k, ctx.vt(v)) for k, v in nodo["campos"].items()]
    wn = max([_ancho(k, T_VALOR) for k, _ in filas] + [40]) + 16
    wv = _ancho_celda([v for _, v in filas], 60, 220)
    for i, (campo, texto) in enumerate(filas):
        y = i * 30
        lz.texto(wn - 10, y + 19, campo, "texto_suave", T_VALOR, "end")
        estado = ctx.estados.get(("campo", est["raiz"], campo))
        lz.celda(wn, y, wv, 28, texto, estado, f"{campo} = {texto}")
    titulo = _titulo_panel(est, ctx.idioma) + (f" ({nodo['clase']})" if nodo.get("clase") else "")
    return _panel(lz, titulo, wn + wv + 2 * RELLENO, max(1, len(filas)) * 30, lz.partes)


def panel_pila_llamadas(ctx: Contexto) -> Panel | None:
    """Marcos del tope (arriba, resaltado como activo) a la base."""
    marcos = ctx.paso["marcos"]
    if not marcos:
        return None
    lz = ctx.lienzo()
    idioma = ctx.idioma
    orden = list(reversed(marcos))
    if len(orden) > MAX_MARCOS:
        orden = orden[: MAX_MARCOS - 4] + [None] + orden[-3:]  # type: ignore[list-item]
    lineas = []
    for m in orden:
        if m is None:
            lineas.append(("⋮", "", None))
            continue
        cab = i18n.t("VIS.desc.marco", idioma, subrutina=m["subrutina"], linea=m["linea"])
        valores = [
            f"{k} = {ctx.vt(v.get('valor'))}"
            for k, v in m["variables"].items()
            if not rt.es_ref(v.get("valor"))
        ]
        lineas.append((cab, rt.unir(valores, idioma, 6), m))
    w = max(
        220.0, max(max(_ancho(c, T_VALOR, False), _ancho(e, T_ETIQUETA)) for c, e, _ in lineas) + 90
    )
    y = 0.0
    for k, (cab, escalares, m) in enumerate(lineas):
        if m is None:
            lz.texto(w / 2, y + 16, cab, "texto_suave", T_TITULO)
            y += 26
            continue
        alto = 46 if escalares else 30
        activo = k == 0
        lz.grupo(
            cab
            + (" — " + i18n.t("VIS.svg.activo", idioma) if activo else "")
            + (f": {escalares}" if escalares else ""),
            0,
            y,
        )
        if activo:
            lz.rect(0, 0, w, alto, "activo_fondo", "activo_borde", 3)
            etq = i18n.t("VIS.svg.activo", idioma)
            ancho_etq = _ancho(etq, T_ETIQUETA, False) + 12
            lz.rect(w - ancho_etq - 6, 6, ancho_etq, 18, "activo_borde", radio=9)
            lz.texto(w - ancho_etq / 2 - 6, 19, etq, "fondo", T_ETIQUETA, mono=False, negrita=True)
        else:
            lz.rect(0, 0, w, alto, "celda", "celda_borde", 1.5)
        lz.texto(
            10,
            20,
            ("▶ " if activo else "") + cab,
            "texto",
            T_VALOR,
            "start",
            mono=False,
            negrita=activo,
        )
        if escalares:
            lz.texto(
                10, 38, _recortar(escalares, w - 20, T_ETIQUETA), "texto_suave", T_ETIQUETA, "start"
            )
        lz.fin_grupo()
        y += alto + 6
    return _panel(lz, i18n.t("VIS.svg.pila_llamadas", idioma), w + 2 * RELLENO, y - 6, lz.partes)


def panel_variables(ctx: Contexto) -> Panel | None:
    """Variables de la subrutina activa con nombre, tipo y valor."""
    marcos = ctx.paso["marcos"]
    if not marcos or not marcos[-1]["variables"]:
        return None
    lz = ctx.lienzo()
    tope = marcos[-1]
    filas = [
        (
            k,
            str(v.get("tipo", "")),
            rt.valor_variable(k, v.get("valor"), ctx.paso, ctx.idioma, ctx.nombres),
        )
        for k, v in tope["variables"].items()
    ]
    wn = max(_ancho(k, T_VALOR) for k, _, _ in filas) + 12
    wt = max(_ancho(t, T_ETIQUETA) for _, t, _ in filas) + 16
    wv = _ancho_celda([v for _, _, v in filas], 60, 240)
    for i, (nombre, tipo, valor) in enumerate(filas):
        y = i * 32
        lz.texto(0, y + 20, nombre, "texto", T_VALOR, "start")
        lz.texto(wn, y + 20, tipo, "texto_suave", T_ETIQUETA, "start")
        estado = ctx.estados.get(("var", nombre))
        lz.celda(wn + wt, y, wv, 28, valor, estado, f"{nombre} ({tipo}) = {valor}")
    titulo = i18n.t("VIS.svg.variables", ctx.idioma, subrutina=tope["subrutina"])
    return _panel(lz, titulo, wn + wt + wv + 2 * RELLENO, len(filas) * 32 - 4, lz.partes)


def panel_salida(ctx: Contexto) -> Panel | None:
    """Líneas impresas en este paso."""
    lineas = ctx.paso["salida_nueva"]
    if not lineas:
        return None
    lz = ctx.lienzo()
    vista = lineas[:MAX_SALIDA]
    for i, linea in enumerate(vista):
        lz.texto(0, i * 22 + 16, "› " + _recortar(linea, 600), "texto", T_VALOR, "start")
    ancho = max(_ancho("› " + _recortar(x, 600), T_VALOR) for x in vista)
    alto = _nota_recorte(lz, len(vista) * 22, len(vista), len(lineas))
    return _panel(lz, i18n.t("VIS.svg.salida", ctx.idioma), ancho + 2 * RELLENO, alto, lz.partes)


def panel_leyenda(ctx: Contexto) -> Panel | None:
    """Explica los dos resaltados con muestras (sólo si hubo accesos)."""
    if not ctx.paso["accesos"]:
        return None
    lz = ctx.lienzo()
    muestras = [
        ("lee", i18n.t("VIS.svg.leido", ctx.idioma)),
        ("escribe", i18n.t("VIS.svg.escrito", ctx.idioma)),
    ]
    ancho = 0.0
    for i, (estado, texto) in enumerate(muestras):
        y = i * 44
        lz.celda(0, y, 56, 38, "x", estado, texto)
        lz.texto(68, y + 24, texto, "texto", T_ETIQUETA + 1, "start", mono=False)
        ancho = max(ancho, 68 + _ancho(texto, T_ETIQUETA + 1, False))
    return _panel(lz, i18n.t("VIS.svg.leyenda", ctx.idioma), ancho + 2 * RELLENO, 82, lz.partes)


_PANELES = {
    "arreglo": panel_arreglo,
    "matriz": panel_matriz,
    "pila": panel_pila,
    "cola": panel_cola,
    "lista_enlazada": panel_lista,
    "lista_doble": panel_lista,
    "arbol_binario": panel_arbol,
    "grafo": panel_grafo,
    "objeto": panel_objeto,
}


def _patrones(p: Mapping[str, str]) -> str:
    return (
        "<defs>"
        '<pattern id="vis-pat-lee" width="6" height="6" patternUnits="userSpaceOnUse">'
        f'<circle cx="3" cy="3" r="1.4" fill="{p["lee_borde"]}" class="f-lee_borde"/></pattern>'
        '<pattern id="vis-pat-escribe" width="6" height="6" patternUnits="userSpaceOnUse"'
        ' patternTransform="rotate(45)">'
        f'<rect x="0" y="0" width="2.5" height="6" fill="{p["escribe_borde"]}"'
        ' class="f-escribe_borde"/></pattern>'
        "</defs>"
    )


def svg_paso(paso: Mapping[str, Any], idioma: str = "es", *, tema: str = "claro") -> str:
    """SVG completo de un paso, con ``<title>`` y ``<desc>`` accesibles."""
    idioma = i18n.normalizar_idioma(idioma)
    paleta = PALETAS[tema]
    p = rt.normalizar_paso(paso, idioma)
    ctx = Contexto(p, idioma, paleta)
    paneles: list[Panel] = [_PANELES[e["forma"]](e, ctx) for e in p["estructuras"]]
    if not p["estructuras"]:
        lz = ctx.lienzo()
        texto = i18n.t("VIS.svg.sin_estructuras", idioma)
        lz.texto(0, 16, texto, "texto_suave", T_VALOR, "start", mono=False)
        paneles.append(
            _panel(
                lz,
                i18n.t("VIS.ui.estructuras", idioma),
                _ancho(texto, T_VALOR, False) + 2 * RELLENO,
                22,
                lz.partes,
            )
        )
    for extra in (
        panel_pila_llamadas(ctx),
        panel_variables(ctx),
        panel_salida(ctx),
        panel_leyenda(ctx),
    ):
        if extra is not None:
            paneles.append(extra)
    ancho = max(360.0, max(pn.ancho for pn in paneles) + 2 * MARGEN)
    alto = MARGEN + sum(pn.alto + SEPARACION for pn in paneles) - SEPARACION + MARGEN
    titulo = i18n.t("VIS.svg.titulo", idioma, n=p["n"], linea=p["linea"])
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1"'
        f' width="{_n(ancho)}" height="{_n(alto)}"'
        f' viewBox="0 0 {_n(ancho)} {_n(alto)}" role="img" aria-labelledby="vis-titulo vis-desc"'
        f' font-family="{FUENTE}" data-paso="{p["n"]}" data-linea="{p["linea"]}">',
        f'<title id="vis-titulo">{escape(titulo)}</title>',
        f'<desc id="vis-desc">{escape(rt.describir(p, idioma))}</desc>',
        _patrones(paleta),
        f'<rect x="0" y="0" width="{_n(ancho)}" height="{_n(alto)}"'
        f' fill="{paleta["fondo"]}" class="f-fondo"/>',
    ]
    y = float(MARGEN)
    for pn in paneles:
        partes.append(f'<g transform="translate({MARGEN},{_n(y)})">')
        partes.extend(pn.partes)
        partes.append("</g>")
        y += pn.alto + SEPARACION
    partes.append("</svg>")
    return "".join(partes)


def css_tema(selector: str, tema: str) -> str:
    """Reglas CSS que repintan un SVG ya dibujado con la paleta ``tema``.

    Las clases ``f-<rol>``/``s-<rol>`` que emite :class:`Lienzo` permiten al
    reproductor HTML pasar de claro a oscuro sin recalcular ningún SVG.
    """
    paleta = PALETAS[tema]
    reglas = []
    for rol, color in paleta.items():
        reglas.append(f"{selector} .f-{rol}{{fill:{color}}}")
        reglas.append(f"{selector} .s-{rol}{{stroke:{color}}}")
    return "\n".join(reglas)


__all__ = [
    "CLARO",
    "OSCURO",
    "PALETAS",
    "css_tema",
    "disposicion_arbol",
    "disposicion_circular",
    "svg_paso",
]
