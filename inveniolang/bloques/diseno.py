"""Geometría del lienzo de bloques, sin Qt (INV-4011).

El lienzo de la GUI dibuja lo que calcula este módulo: cada bloque es una
``Caja`` con su forma y sus trozos (texto, campos, huecos) y, sobre todo,
cada sitio donde se puede soltar algo es una ``Zona`` con el ``Destino``
exacto de ``edicion``. Así:

* arrastrar con el ratón es buscar la zona bajo el puntero (``zona_en``);
* mover o insertar **con el teclado** es recorrer ``zonas`` en orden de
  lectura y elegir una con Intro: el mismo conjunto de destinos que con el
  ratón (nunca hay un sitio que sólo se alcance arrastrando);
* las pruebas comprueban la geometría (sin solapes, toda lista y todo hueco
  tienen su zona) sin abrir ninguna ventana.

El ancho de un texto lo mide la GUI (``medir``) para usar la fuente real;
por defecto se estima con un ancho fijo por carácter.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from .catalogo import TIPOS
from .modelo import Bloque, ModeloBloques
from .texto import Pieza, bocas, piezas, rotulo_boca, texto_campo

__all__ = ["ALTO", "Caja", "Diseno", "Trozo", "Zona", "disenar"]

ALTO = 26.0  # alto de una fila de texto
_PAD = 6.0
_SANGRIA = 22.0
_HUECO = 30.0  # ancho de un hueco vacío
_SEPARACION = 18.0  # entre definiciones del programa
_ZONA = 8.0  # alto de una zona de inserción en una pila


@dataclass
class Trozo:
    """Elemento dibujado de la cabecera: ``texto``, ``campo``, ``hueco`` vacío o ``mas``."""

    clase: str
    texto: str
    x: float
    y: float
    w: float
    h: float
    ref: str = ""  # nombre del campo/hueco/lista


@dataclass
class Caja:
    """Un bloque colocado en el lienzo."""

    id: str
    tipo: str
    forma: str
    categoria: str
    salida: str | None
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
    trozos: list[Trozo] = field(default_factory=list)
    hijas: list[Caja] = field(default_factory=list)
    alto_cabecera: float = ALTO
    rotulos: list[Trozo] = field(default_factory=list)  # rótulos de bocas


@dataclass
class Zona:
    """Sitio donde soltar: hueco o posición de lista (``padre`` None = programa)."""

    padre: str | None
    parte: str
    indice: int | None
    clase: str  # "hueco" o "lista"
    x: float
    y: float
    w: float
    h: float

    def contiene(self, px: float, py: float) -> bool:
        """¿El punto cae en la zona?"""
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h


@dataclass
class Diseno:
    """Resultado: cajas de primer nivel, todas las zonas y el tamaño total."""

    cajas: list[Caja]
    zonas: list[Zona]
    ancho: float
    alto: float

    def todas(self) -> Iterator[Caja]:
        """Todas las cajas en preorden (orden de lectura y de navegación con teclado)."""
        pila = list(reversed(self.cajas))
        while pila:
            c = pila.pop()
            yield c
            pila.extend(reversed(c.hijas))

    def caja(self, ident: str) -> Caja | None:
        """La caja del bloque ``ident``."""
        return next((c for c in self.todas() if c.id == ident), None)

    def caja_en(self, x: float, y: float) -> Caja | None:
        """La caja más interior bajo el punto."""
        elegida = None
        for c in self.todas():
            if c.x <= x <= c.x + c.w and c.y <= y <= c.y + c.h:
                elegida = c
        return elegida

    def zona_en(self, x: float, y: float) -> Zona | None:
        """La zona más pequeña que contiene el punto (la más precisa)."""
        candidatas = [z for z in self.zonas if z.contiene(x, y)]
        return min(candidatas, key=lambda z: z.w * z.h, default=None)


def _medir_defecto(texto: str) -> float:
    return 7.6 * len(texto)


class _Disenador:
    def __init__(self, idioma: str | None, medir: Callable[[str], float]):
        self.idioma = idioma
        self.medir = medir
        self.zonas: list[Zona] = []

    def caja(self, b: Bloque, x: float, y: float, rama_otra: bool = False) -> Caja:
        desc = TIPOS[b.tipo]
        c = Caja(b.id, b.tipo, desc.forma, desc.categoria, desc.salida, x, y)
        cx = x + _PAD
        alto = ALTO
        planas = _aplanar(piezas(b.tipo, self.idioma, rama_otra))
        # Primera pasada: las hijas en línea pueden ser más altas que la fila.
        for p in planas:
            if p.clase == "texto":
                texto = p.valor.strip()
                if texto:
                    w = self.medir(texto)
                    c.trozos.append(Trozo("texto", texto, cx, y, w, ALTO))
                    cx += w + 4
                continue
            nombre = p.valor
            if nombre in b.campos:
                texto = texto_campo(b, nombre, self.idioma) or "…"
                if isinstance(b.campos[nombre], bool):
                    marca = "☑" if b.campos[nombre] else "☐"
                    texto = f"{marca} {texto_campo_etiqueta(b, nombre, self.idioma)}"
                w = self.medir(texto) + 8
                c.trozos.append(Trozo("campo", texto, cx, y + 3, w, ALTO - 6, nombre))
                cx += w + 4
            elif nombre in b.huecos:
                hijo = b.huecos[nombre]
                if hijo is None:
                    c.trozos.append(Trozo("hueco", "", cx, y + 3, _HUECO, ALTO - 6, nombre))
                    self.zonas.append(
                        Zona(b.id, nombre, None, "hueco", cx, y + 3, _HUECO, ALTO - 6)
                    )
                    cx += _HUECO + 4
                else:
                    sub = self.caja(hijo, cx, y + 2)
                    c.hijas.append(sub)
                    self.zonas.append(Zona(b.id, nombre, None, "hueco", sub.x, sub.y, sub.w, sub.h))
                    cx += sub.w + 4
                    alto = max(alto, sub.h + 4)
            else:  # lista en línea (argumentos, valores, parámetros)
                cx = self._en_linea(b, nombre, c, cx, y)
                alto = max(alto, max((h.h + 4 for h in c.hijas), default=ALTO))
        c.alto_cabecera = alto
        ancho = cx - x + _PAD
        cy = y + alto
        for lista in bocas(b, self.idioma):
            rot = rotulo_boca(b, lista, self.idioma)
            if rot:
                w = self.medir(rot)
                c.rotulos.append(Trozo("texto", rot, x + _PAD, cy, w, ALTO, lista))
                ancho = max(ancho, w + 2 * _PAD)
                cy += ALTO
            cy, w = self._pila(b, lista, x + _SANGRIA, cy, c)
            ancho = max(ancho, w + _SANGRIA + _PAD)
        if c.forma in ("c", "definicion") or (
            c.forma in ("miembro", "parte", "valor") and bocas(b, self.idioma)
        ):
            cy += _PAD * 2  # brazo inferior de la «C»
        c.w = ancho
        c.h = cy - y
        return c

    def _en_linea(self, b: Bloque, nombre: str, c: Caja, cx: float, y: float) -> float:
        elementos = b.listas[nombre]
        for k, hijo in enumerate(elementos):
            self.zonas.append(Zona(b.id, nombre, k, "lista", cx, y + 3, 6, ALTO - 6))
            cx += 6
            sub = self.caja(hijo, cx, y + 2)
            c.hijas.append(sub)
            cx += sub.w
            if k < len(elementos) - 1:
                w = self.medir(",")
                c.trozos.append(Trozo("texto", ",", cx, y, w, ALTO))
                cx += w + 2
        w = self.medir("+") + 10
        c.trozos.append(Trozo("mas", "+", cx + 2, y + 3, w, ALTO - 6, nombre))
        self.zonas.append(Zona(b.id, nombre, len(elementos), "lista", cx + 2, y + 3, w, ALTO - 6))
        return cx + w + 6

    def _pila(self, b: Bloque, lista: str, x: float, y: float, c: Caja) -> tuple[float, float]:
        """Hijas apiladas; devuelve (y final, ancho máximo)."""
        elementos = b.listas[lista]
        padre = b.id
        ancho = 60.0
        if not elementos:
            self.zonas.append(Zona(padre, lista, 0, "lista", x, y, 120, ALTO))
            return y + ALTO, ancho
        for k, hijo in enumerate(elementos):
            self.zonas.append(Zona(padre, lista, k, "lista", x, y - _ZONA / 2, 160, _ZONA))
            sub = self.caja(hijo, x, y, rama_otra=(b.tipo == "si" and k > 0))
            c.hijas.append(sub)
            y += sub.h + 2
            ancho = max(ancho, sub.w)
        self.zonas.append(Zona(padre, lista, len(elementos), "lista", x, y - 1, 160, _ZONA))
        return y + _ZONA / 2, ancho


def texto_campo_etiqueta(b: Bloque, campo: str, idioma: str | None) -> str:
    """Rótulo de una bandera (``☑ con sino``): su nombre de parte."""
    from .. import i18n

    return i18n.t(f"BLQ.parte.{campo}", idioma)


def _aplanar(p: tuple[Pieza, ...]) -> list[Pieza]:
    """El lienzo muestra siempre los tramos opcionales (sus huecos se pueden rellenar)."""
    salida: list[Pieza] = []
    for x in p:
        if x.clase == "opcional":
            salida.extend(_aplanar(x.hijas))
        else:
            salida.append(x)
    return salida


def disenar(
    modelo: ModeloBloques,
    idioma: str | None = None,
    medir: Callable[[str], float] | None = None,
) -> Diseno:
    """Coloca el programa: definiciones apiladas con sus zonas de inserción."""
    d = _Disenador(idioma or modelo.idioma, medir or _medir_defecto)
    y = 10.0
    cajas: list[Caja] = []
    ancho = 0.0
    for k, b in enumerate(modelo.programa):
        d.zonas.append(
            Zona(None, "programa", k, "lista", 10, y - _SEPARACION / 2, 220, _SEPARACION / 2)
        )
        c = d.caja(b, 10, y)
        cajas.append(c)
        y += c.h + _SEPARACION
        ancho = max(ancho, c.w)
    d.zonas.append(Zona(None, "programa", len(modelo.programa), "lista", 10, y - 4, 220, ALTO))
    return Diseno(cajas, d.zonas, ancho + 40, y + ALTO + 20)
