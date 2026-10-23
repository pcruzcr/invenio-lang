"""Diagrama de clases en SVG propio: jerárquico, determinista y accesible.

INV-3208: antes solo había texto PlantUML/Mermaid, que el estudiante debía
pegar en una herramienta externa (con red) para ver el dibujo. Este
renderizador no depende de nada:

* **Disposición jerárquica por herencia**: cada clasificador va en la fila
  ``1 + máxima fila de sus supertipos`` (padres e interfaces arriba, como en
  los libros); dentro de la fila se ordena por el baricentro de sus
  supertipos para acortar las flechas; una fila demasiado ancha se parte.
  Las cajas nunca se solapan (las pruebas lo comprueban) y el resultado es
  el mismo byte a byte para el mismo modelo.
* **Notación UML estándar**: triángulo hueco (herencia; discontinua para la
  realización), rombo lleno (composición) o hueco (agregación), flecha
  abierta (asociación; discontinua para la dependencia), rol y
  multiplicidad junto al extremo. Los tipos de relación se distinguen por
  forma y trazo, nunca solo por color, y una leyenda los nombra.
* **Accesible**: ``role="img"`` con ``<title>``/``<desc>`` (la descripción
  de :mod:`.texto`), un grupo con nombre y ``<title>`` por clasificador, por
  miembro y por relación.
* **Temas**: reutiliza la paleta clara/oscura de la Fase 2
  (``visualizacion.render_svg.PALETAS``, contraste AAA en texto) y sus
  clases ``f-``/``s-``, así que el CSS del reproductor también lo repinta.
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

from ..i18n import t
from ..visualizacion.render_svg import FUENTE, FUENTE_MONO, PALETAS, Lienzo, _n
from .modelo import Atributo, Clasificador, DiagramaClases, Literal, Relacion
from .presentacion import literal_codigo, tipo_visible
from .texto import (
    describir,
    frase_atributo,
    frase_clasificador,
    frase_constructor,
    frase_metodo,
    frase_relacion,
    resumen,
)

__all__ = ["svg_clases"]

T_MIEMBRO = 13.0
T_NOMBRE = 15.0
T_NOTA = 11.5
ALTO_LINEA = 19.0
RELLENO_X = 10.0
MARGEN = 24.0
SEP_COLUMNAS = 56.0
SEP_FILAS = 96.0
MAX_ANCHO_FILA = 1280.0
ANCHO_MIN_CAJA = 120.0


def _ancho_texto(texto: str, tam: float) -> float:
    return len(texto) * tam * 0.6


class _Lienzo(Lienzo):
    """Lienzo de la Fase 2 con las primitivas que la notación UML necesita."""

    def trazo(self, puntos: list[tuple[float, float]], guiones: bool = False) -> None:
        """Polilínea del color de las aristas (discontinua para realización/dependencia)."""
        stroke, cs = self._color("stroke", "arista")
        dash = ' stroke-dasharray="7 5"' if guiones else ""
        pts = " ".join(f"{_n(x)},{_n(y)}" for x, y in puntos)
        self.partes.append(
            f'<polyline points="{pts}" fill="none"{stroke} stroke-width="1.6"{dash}'
            f"{self._clase(cs)}/>"
        )

    def poligono(self, puntos: list[tuple[float, float]], lleno: bool) -> None:
        """Punta de flecha o rombo: lleno con el color de la arista o hueco (color de fondo)."""
        fill, cf = self._color("fill", "arista" if lleno else "fondo")
        stroke, cs = self._color("stroke", "arista")
        pts = " ".join(f"{_n(x)},{_n(y)}" for x, y in puntos)
        self.partes.append(
            f'<polygon points="{pts}"{fill}{stroke} stroke-width="1.6"{self._clase(cf, cs)}/>'
        )

    def texto_uml(
        self,
        x: float,
        y: float,
        contenido: str,
        titulo: str | None = None,
        *,
        tam: float = T_MIEMBRO,
        rol: str = "texto",
        ancla: str = "start",
        negrita: bool = False,
        cursiva: bool = False,
        subrayado: bool = False,
        mono: bool = True,
    ) -> None:
        """Texto con los estilos de UML (cursiva = abstracto, subrayado = estático)."""
        fill, cf = self._color("fill", rol)
        estilo = ""
        if negrita:
            estilo += ' font-weight="700"'
        if cursiva:
            estilo += ' font-style="italic"'
        if subrayado:
            estilo += ' text-decoration="underline"'
        fam = FUENTE_MONO if mono else FUENTE
        hijo = f"<title>{escape(titulo)}</title>" if titulo else ""
        self.partes.append(
            f'<text x="{_n(x)}" y="{_n(y)}" font-size="{_n(tam)}" text-anchor="{ancla}"'
            f' font-family="{fam}"{estilo}{fill}{self._clase(cf)}>{hijo}{escape(contenido)}</text>'
        )


class _Linea:
    """Una línea de texto de una caja con su estilo y su ``<title>``."""

    def __init__(self, texto: str, titulo: str, *, cursiva: bool = False, subrayado: bool = False):
        self.texto = texto
        self.titulo = titulo
        self.cursiva = cursiva
        self.subrayado = subrayado


class _Caja:
    """Caja de un clasificador: cabecera y compartimentos ya escritos en texto."""

    def __init__(self, modelo: DiagramaClases, c: Clasificador, idioma: str):
        self.c = c
        self.titulo = frase_clasificador(modelo, c, idioma)
        self.estereotipo = (
            None if c.tipo == "clase" else "«" + t(f"UML.svg.estereotipo.{c.tipo}", idioma) + "»"
        )
        genericos = f"<{', '.join(c.parametros_tipo)}>" if c.parametros_tipo else ""
        self.nombre = c.nombre + genericos
        self.modulo = t("UML.svg.modulo", idioma, modulo=c.modulo) if c.modulo else None
        self.compartimentos: list[list[_Linea]] = []
        if c.tipo == "enumeracion":
            self.compartimentos.append(
                [_Linea(self._literal(x, idioma), x.nombre) for x in c.literales]
            )
        else:
            self.compartimentos.append(
                [
                    _Linea(
                        self._atributo(a, idioma),
                        frase_atributo(a, idioma),
                        subrayado=a.estatico,
                    )
                    for a in c.atributos
                ]
            )
            operaciones = [
                _Linea(
                    f"{k.visibilidad} «create» {c.nombre}({self._params(k.parametros, idioma)})",
                    frase_constructor(k, c.nombre, idioma),
                )
                for k in c.constructores
            ]
            marca_abstracto = " {" + t("UML.txt.abstracto", idioma) + "}"
            for x in c.metodos:
                texto = (
                    f"{x.visibilidad} {x.nombre}({self._params(x.parametros, idioma)})"
                    f" : {tipo_visible(x.retorno, idioma)}"
                )
                if x.abstracto and c.tipo != "interfaz":
                    texto += marca_abstracto
                operaciones.append(
                    _Linea(
                        texto,
                        frase_metodo(x, idioma),
                        cursiva=x.abstracto,
                        subrayado=x.estatico,
                    )
                )
            self.compartimentos.append(operaciones)
        cabecera = [self.nombre] + [x for x in (self.estereotipo, self.modulo) if x]
        anchos = [_ancho_texto(x, T_NOMBRE) for x in cabecera]
        anchos += [_ancho_texto(x.texto, T_MIEMBRO) for comp in self.compartimentos for x in comp]
        self.w = max(ANCHO_MIN_CAJA, max(anchos) + 2 * RELLENO_X)
        self.alto_cabecera = 10 + ALTO_LINEA * len(cabecera) + 4
        self.h = self.alto_cabecera + sum(
            max(1, len(comp)) * ALTO_LINEA + 8 for comp in self.compartimentos
        )
        self.x = 0.0
        self.y = 0.0
        # Espacio a la derecha para los lazos de las relaciones consigo misma.
        lazos = [r for r in modelo.relaciones if r.origen == r.destino == c.nombre]
        self.extra = 0.0
        if lazos:
            rotulos = max(_ancho_texto(f"{r.rol} {r.multiplicidad}", T_NOTA) for r in lazos)
            self.extra = 40 + 30 * (len(lazos) - 1) + rotulos

    @property
    def ocupa(self) -> float:
        """Ancho que ocupa en su fila (caja más lazos)."""
        return self.w + self.extra

    @staticmethod
    def _params(params: tuple, idioma: str) -> str:
        return ", ".join(f"{p.nombre} : {tipo_visible(p.tipo, idioma)}" for p in params)

    def _literal(self, x: Literal, idioma: str) -> str:
        return f"{x.nombre}({self._params(x.parametros, idioma)})" if x.parametros else x.nombre

    def _atributo(self, a: Atributo, idioma: str) -> str:
        texto = f"{a.visibilidad} {a.nombre} : {tipo_visible(a.tipo, idioma)}"
        if a.valor_inicial is not None:
            texto += " = " + literal_codigo(a.valor_inicial, idioma)
        if a.constante:
            texto += " {readOnly}"
        return texto

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def dibujar(self, lz: _Lienzo) -> None:
        lz.grupo(self.titulo)
        lz.rect(self.x, self.y, self.w, self.h, "panel", "panel_borde", 1.6, radio=3)
        y = self.y + 10
        if self.estereotipo:
            y += ALTO_LINEA
            lz.texto_uml(
                self.cx,
                y - 5,
                self.estereotipo,
                tam=T_NOTA,
                rol="texto_suave",
                ancla="middle",
                mono=False,
            )
        y += ALTO_LINEA
        lz.texto_uml(
            self.cx,
            y - 4,
            self.nombre,
            tam=T_NOMBRE,
            ancla="middle",
            negrita=True,
            cursiva=self.c.tipo == "abstracta",
            mono=False,
        )
        if self.modulo:
            y += ALTO_LINEA
            lz.texto_uml(
                self.cx,
                y - 5,
                self.modulo,
                tam=T_NOTA,
                rol="texto_suave",
                ancla="middle",
                mono=False,
            )
        y = self.y + self.alto_cabecera
        for comp in self.compartimentos:
            lz.linea(self.x, y, self.x + self.w, y, "panel_borde", 1.2)
            y += 4
            for linea in comp:
                y += ALTO_LINEA
                lz.texto_uml(
                    self.x + RELLENO_X,
                    y - 5,
                    linea.texto,
                    linea.titulo,
                    cursiva=linea.cursiva,
                    subrayado=linea.subrayado,
                )
            if not comp:
                y += ALTO_LINEA
            y += 4
        lz.fin_grupo()


# ----------------------------------------------------------------- disposición


def _filas(modelo: DiagramaClases, cajas: dict[str, _Caja]) -> list[list[_Caja]]:
    """Capas por herencia/realización, ordenadas por baricentro y partidas si no caben."""
    supers = {
        c.nombre: [s for s in [modelo.padre(c.nombre), *modelo.interfaces(c.nombre)] if s in cajas]
        for c in modelo.clasificadores
    }
    capa: dict[str, int] = {}

    def nivel(nombre: str, pila: tuple[str, ...] = ()) -> int:
        if nombre in capa:
            return capa[nombre]
        if nombre in pila:  # un ciclo (diagrama mal formado) no debe colgar el dibujo
            return 0
        sups = [s for s in supers.get(nombre, []) if s]
        capa[nombre] = 0 if not sups else 1 + max(nivel(s, pila + (nombre,)) for s in sups)
        return capa[nombre]

    orden = [c.nombre for c in modelo.clasificadores]
    for nombre in orden:
        nivel(nombre)
    capas: list[list[str]] = [[] for _ in range(max(capa.values(), default=-1) + 1)]
    for nombre in orden:
        capas[capa[nombre]].append(nombre)
    posicion: dict[str, float] = {}
    for i, fila in enumerate(capas):
        if i > 0:

            def baricentro(n: str) -> float:
                ss = [posicion[s] for s in supers[n] if s in posicion]
                return sum(ss) / len(ss) if ss else float("inf")

            fila.sort(key=lambda n: (baricentro(n), orden.index(n)))
        for j, nombre in enumerate(fila):
            posicion[nombre] = j
    filas: list[list[_Caja]] = []
    for fila in capas:
        actual: list[_Caja] = []
        ancho = 0.0
        for nombre in fila:
            caja = cajas[nombre]
            if actual and ancho + SEP_COLUMNAS + caja.ocupa > MAX_ANCHO_FILA:
                filas.append(actual)
                actual, ancho = [], 0.0
            ancho += (SEP_COLUMNAS if actual else 0) + caja.ocupa
            actual.append(caja)
        if actual:
            filas.append(actual)
    return filas


def _colocar(filas: list[list[_Caja]]) -> tuple[float, float]:
    """Asigna x/y a cada caja (filas centradas); devuelve el tamaño ocupado."""
    anchos = [sum(c.ocupa for c in f) + SEP_COLUMNAS * (len(f) - 1) for f in filas]
    total = max(anchos, default=0.0)
    y = MARGEN
    for fila, ancho in zip(filas, anchos, strict=True):
        x = MARGEN + (total - ancho) / 2
        alto = max(c.h for c in fila)
        for caja in fila:
            caja.x, caja.y = x, y
            x += caja.ocupa + SEP_COLUMNAS
        y += alto + SEP_FILAS
    return total + 2 * MARGEN, y - SEP_FILAS + MARGEN


# ----------------------------------------------------------------- relaciones


def _borde(caja: _Caja, hacia_x: float, hacia_y: float) -> tuple[float, float]:
    """Punto del borde de ``caja`` en la recta de su centro hacia (hacia_x, hacia_y)."""
    dx, dy = hacia_x - caja.cx, hacia_y - caja.cy
    if dx == 0 and dy == 0:
        return caja.cx, caja.y
    fx = (caja.w / 2) / abs(dx) if dx else math.inf
    fy = (caja.h / 2) / abs(dy) if dy else math.inf
    f = min(fx, fy)
    return caja.cx + dx * f, caja.cy + dy * f


def _punta(
    lz: _Lienzo, x: float, y: float, ux: float, uy: float, forma: str
) -> tuple[float, float]:
    """Dibuja la decoración en (x, y) mirando hacia (ux, uy); devuelve dónde empieza la línea."""
    px, py = -uy, ux
    if forma == "triangulo":
        bx, by = x - ux * 15, y - uy * 15
        lz.poligono([(x, y), (bx + px * 8, by + py * 8), (bx - px * 8, by - py * 8)], False)
        return bx, by
    if forma in ("rombo_lleno", "rombo_hueco"):
        mx, my = x - ux * 10, y - uy * 10
        fx, fy = x - ux * 20, y - uy * 20
        lz.poligono(
            [(x, y), (mx + px * 6, my + py * 6), (fx, fy), (mx - px * 6, my - py * 6)],
            forma == "rombo_lleno",
        )
        return fx, fy
    # flecha abierta (asociación navegable, dependencia)
    bx, by = x - ux * 12, y - uy * 12
    lz.trazo([(bx + px * 6, by + py * 6), (x, y), (bx - px * 6, by - py * 6)])
    return x, y


def _etiqueta(lz: _Lienzo, x: float, y: float, texto: str) -> None:
    """Rol y multiplicidad con fondo, para leerse aunque cruce una línea o una caja.

    Se dibujan al final, encima de todo.
    """
    w = _ancho_texto(texto, T_NOTA) + 8
    lz.rect(x - w / 2, y - 12, w, 16, "fondo", None, radio=3)
    lz.texto_uml(x, y, texto, tam=T_NOTA, rol="texto", ancla="middle")


def _dibujar_relacion(
    lz: _Lienzo,
    r: Relacion,
    cajas: dict[str, _Caja],
    desplazamiento: float,
    idioma: str,
    entrada: dict[str, list[Relacion]],
    etiquetas: list[tuple[float, float, str]],
) -> None:
    origen, destino = cajas[r.origen], cajas[r.destino]
    lz.grupo(frase_relacion(r, idioma))
    guiones = r.tipo in ("realizacion", "dependencia")
    etiqueta = f"{r.rol} {r.multiplicidad}" if r.rol else None
    if r.origen == r.destino:
        k = desplazamiento
        y1 = origen.y + 14 + k
        y2 = y1 + 26
        x0 = origen.x + origen.w
        x1 = x0 + 26 + k
        inicio = (x0, y1)
        if r.tipo in ("composicion", "agregacion"):
            forma = "rombo_lleno" if r.tipo == "composicion" else "rombo_hueco"
            inicio = _punta(lz, x0, y1, -1.0, 0.0, forma)
        lz.trazo([inicio, (x1, y1), (x1, y2), (x0 + 12, y2)], guiones)
        _punta(lz, x0, y2, -1.0, 0.0, "abierta")
        if etiqueta:
            etiquetas.append((x1 + 6 + _ancho_texto(etiqueta, T_NOTA) / 2, y2 + 4, etiqueta))
        lz.fin_grupo()
        return
    if r.tipo in ("herencia", "realizacion"):
        hermanos = entrada[r.destino]
        i = hermanos.index(r)
        paso = min(18.0, (destino.w - 20) / max(1, len(hermanos)))
        dx = (i - (len(hermanos) - 1) / 2) * paso
        fin = (destino.cx + dx, destino.y + destino.h)
        ini = _borde(origen, *fin)
        largo = math.hypot(fin[0] - ini[0], fin[1] - ini[1]) or 1.0
        ux, uy = (fin[0] - ini[0]) / largo, (fin[1] - ini[1]) / largo
        base = _punta(lz, fin[0], fin[1], ux, uy, "triangulo")
        lz.trazo([ini, base], guiones)
        lz.fin_grupo()
        return
    # Paralelas entre el mismo par: se separan perpendicularmente.
    vx, vy = destino.cx - origen.cx, destino.cy - origen.cy
    largo = math.hypot(vx, vy) or 1.0
    px, py = -vy / largo * desplazamiento, vx / largo * desplazamiento
    ini = _borde(origen, destino.cx + px, destino.cy + py)
    fin = _borde(destino, origen.cx + px, origen.cy + py)
    ini = (ini[0] + px, ini[1] + py)
    fin = (fin[0] + px, fin[1] + py)
    largo = math.hypot(fin[0] - ini[0], fin[1] - ini[1]) or 1.0
    ux, uy = (fin[0] - ini[0]) / largo, (fin[1] - ini[1]) / largo
    if r.tipo in ("composicion", "agregacion"):
        forma = "rombo_lleno" if r.tipo == "composicion" else "rombo_hueco"
        ini = _punta(lz, ini[0], ini[1], -ux, -uy, forma)
    lz.trazo([ini, fin], guiones)
    _punta(lz, fin[0], fin[1], ux, uy, "abierta")
    if etiqueta:
        # Cada paralela lleva su rótulo a otra distancia y de su propio lado.
        lado = -1.0 if desplazamiento < 0 else 1.0
        dist = 44 + abs(desplazamiento) * 1.5
        ex = fin[0] - ux * dist - uy * 12 * lado
        ey = fin[1] - uy * dist + ux * 12 * lado + 4
        etiquetas.append((ex, ey, etiqueta))
    lz.fin_grupo()


def _leyenda(lz: _Lienzo, x: float, y: float, tipos: list[str], idioma: str) -> float:
    """Una muestra de cada tipo de relación presente, con su nombre; devuelve el alto."""
    if not tipos:
        return 0.0
    lz.grupo(t("UML.svg.leyenda", idioma))
    lz.texto_uml(
        x,
        y + 14,
        t("UML.svg.leyenda", idioma),
        tam=T_NOTA,
        rol="texto_suave",
        mono=False,
        negrita=True,
    )
    cx = x
    yy = y + 36
    for tipo in tipos:
        nombre = t(f"UML.svg.rel.{tipo}", idioma)
        guiones = tipo in ("realizacion", "dependencia")
        if tipo in ("herencia", "realizacion"):
            base = _punta(lz, cx + 46, yy - 4, 1.0, 0.0, "triangulo")
            lz.trazo([(cx, yy - 4), base], guiones)
        else:
            inicio: tuple[float, float] = (cx, yy - 4)
            if tipo in ("composicion", "agregacion"):
                forma = "rombo_lleno" if tipo == "composicion" else "rombo_hueco"
                inicio = _punta(lz, cx, yy - 4, -1.0, 0.0, forma)
            lz.trazo([inicio, (cx + 46, yy - 4)], guiones)
            _punta(lz, cx + 46, yy - 4, 1.0, 0.0, "abierta")
        lz.texto_uml(cx + 54, yy, nombre, tam=T_NOTA, mono=False)
        cx += 54 + _ancho_texto(nombre, T_NOTA) + 28
    lz.fin_grupo()
    return 48.0


def svg_clases(modelo: DiagramaClases, idioma: str | None = None, *, tema: str = "claro") -> str:
    """SVG autónomo del diagrama de clases (``tema``: ``claro`` u ``oscuro``)."""
    idi = idioma or modelo.idioma
    paleta = PALETAS[tema]
    lz = _Lienzo(paleta, idi)
    cajas = {c.nombre: _Caja(modelo, c, idi) for c in modelo.clasificadores}
    filas = _filas(modelo, cajas)
    ancho, alto = _colocar(filas)
    entrada: dict[str, list[Relacion]] = {}
    for r in modelo.relaciones:
        if r.tipo in ("herencia", "realizacion"):
            entrada.setdefault(r.destino, []).append(r)
    pares: dict[tuple[str, ...], int] = {}
    etiquetas: list[tuple[float, float, str]] = []
    for r in modelo.relaciones:
        clave = tuple(sorted((r.origen, r.destino)))
        if r.tipo in ("herencia", "realizacion"):
            desplazamiento = 0.0
        else:
            k = pares.get(clave, 0)
            pares[clave] = k + 1
            desplazamiento = (
                30.0 * k if r.origen == r.destino else ((k + 1) // 2 * 16.0 * (1 if k % 2 else -1))
            )
        _dibujar_relacion(lz, r, cajas, desplazamiento, idi, entrada, etiquetas)
    for caja in cajas.values():
        caja.dibujar(lz)
    for x, y, texto in etiquetas:
        _etiqueta(lz, x, y, texto)
    if not modelo.clasificadores:
        mensaje = t("UML.txt.vacio", idi)
        lz.texto_uml(MARGEN, MARGEN + 16, mensaje, rol="texto_suave", mono=False)
        ancho, alto = max(360.0, _ancho_texto(mensaje, T_MIEMBRO) + 2 * MARGEN), 64.0
    tipos = [
        x
        for x in (
            "herencia",
            "realizacion",
            "composicion",
            "agregacion",
            "asociacion",
            "dependencia",
        )
        if any(r.tipo == x for r in modelo.relaciones)
    ]
    alto_leyenda = _leyenda(lz, MARGEN, alto - MARGEN + 8, tipos, idi)
    alto += alto_leyenda
    ancho_leyenda = 2 * MARGEN + sum(
        82 + _ancho_texto(t(f"UML.svg.rel.{x}", idi), T_NOTA) for x in tipos
    )
    ancho = max(ancho, ancho_leyenda)
    titulo = t("UML.svg.titulo", idi, resumen=resumen(modelo, idi))
    return "".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{_n(ancho)}"'
            f' height="{_n(alto)}" viewBox="0 0 {_n(ancho)} {_n(alto)}" role="img"'
            f' aria-labelledby="uml-titulo uml-desc" font-family="{FUENTE}">',
            f'<title id="uml-titulo">{escape(titulo)}</title>',
            f'<desc id="uml-desc">{escape(describir(modelo, idi))}</desc>',
            f'<rect x="0" y="0" width="{_n(ancho)}" height="{_n(alto)}"'
            f' fill="{paleta["fondo"]}" class="f-fondo"/>',
            *lz.partes,
            "</svg>",
        ]
    )
