"""Esquema dibujable de un diagrama: símbolos ISO 5807, flechas y posiciones (INV-3003).

Un único recorrido del árbol estructurado produce a la vez el **grafo**
(símbolos y flechas, con su etiqueta) y su **geometría**. SVG, Mermaid, la
descripción accesible y la GUI consumen este mismo esquema, así que nunca
discrepan entre sí.

Garantía de dibujo sin solapes, por construcción:

* cada construcción ocupa un rectángulo propio; una secuencia los apila en
  vertical y las ramas de una decisión van en **columnas disjuntas**;
* las flechas de vuelta de un ciclo bajan por debajo del cuerpo y suben por
  un **carril izquierdo** reservado; la salida «no» baja por un **carril
  derecho**; las ramas se reúnen por debajo de todas las columnas en un
  conector de unión;
* los saltos (``romper``, ``continuar`` y la caída de un ``caso`` al
  siguiente) no se dibujan como líneas que crucen el diagrama: se dibujan
  con **pares de conectores** con la misma letra, como manda ISO 5807
  (conector de salida → conector de entrada).

``tests/flujo`` comprueba sobre todo el currículo que ningún par de símbolos
se solapa y que toda flecha dibujada empieza y termina en sus símbolos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import i18n
from ..traductor import PALABRAS_CLAVE
from .modelo import Diagrama, Nodo

__all__ = ["Arista", "Esquema", "NodoEsquema", "construir_esquema"]

Punto = tuple[float, float]

ANCHO_CAR = 7.2  # px por carácter, fuente monoespaciada de 12 px
ALTO_LINEA = 16.0
MAX_CARACTERES = 34
RELLENO_X = 12.0
RELLENO_Y = 8.0
SEP_V = 30.0  # separación vertical entre símbolos
SEP_H = 28.0  # separación entre columnas
CARRIL = 24.0  # carril de la flecha de vuelta de un ciclo
MARGEN = 16.0
R_UNION = 6.0  # radio del conector de unión
R_SALTO = 12.0  # radio de un conector con letra
LADO_MIN = 18.0  # tramo mínimo horizontal al salir por un vértice


@dataclass
class NodoEsquema:
    """Símbolo dibujado; ``x``/``y`` es la esquina superior izquierda."""

    id: str
    simbolo: str
    texto: str
    lineas: list[str]
    origen: str | None
    linea: int
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    rol: str = ""
    marca: str = ""

    @property
    def cx(self) -> float:
        """Centro horizontal."""
        return self.x + self.w / 2


@dataclass
class Arista:
    """Flecha ``desde`` → ``hasta``. Un salto.

    Flecha ``desde`` → ``hasta``. Un salto (``salto=True``) no tiene puntos: se dibuja con el par de
    conectores que comparten ``marca``.
    """

    desde: str
    hasta: str
    etiqueta: str = ""
    puntos: list[Punto] = field(default_factory=list)
    salto: bool = False
    pos_etiqueta: tuple[float, float, str] | None = None


@dataclass
class Esquema:
    """Grafo con geometría de un diagrama."""

    clave: str
    titulo: str
    idioma: str
    nodos: list[NodoEsquema]
    aristas: list[Arista]
    ancho: float
    alto: float

    def nodo(self, ident: str) -> NodoEsquema:
        """Nodo por id."""
        return next(n for n in self.nodos if n.id == ident)


@dataclass
class _Salida:
    """Flecha pendiente.

    Flecha pendiente: sale de ``desde`` con ``etiqueta`` por ``ruta``; el último punto está en el
    borde inferior de la construcción.
    """

    desde: str
    etiqueta: str
    ruta: list[Punto]
    pos_etiqueta: tuple[float, float, str] | None = None


class _Geo:
    """Construcción ya dispuesta en coordenadas locales (entrada arriba en ``cx``)."""

    def __init__(self) -> None:
        self.nodos: list[NodoEsquema] = []
        self.aristas: list[Arista] = []
        self.ancho = 0.0
        self.alto = 0.0
        self.cx = 0.0
        self.entrada = ""
        self.salida: _Salida | None = None

    def mover(self, dx: float, dy: float) -> None:
        if not dx and not dy:
            return
        for n in self.nodos:
            n.x += dx
            n.y += dy
        for a in self.aristas:
            a.puntos = [(x + dx, y + dy) for x, y in a.puntos]
            if a.pos_etiqueta is not None:
                px, py, ancla = a.pos_etiqueta
                a.pos_etiqueta = (px + dx, py + dy, ancla)
        if self.salida is not None:
            s = self.salida
            s.ruta = [(x + dx, y + dy) for x, y in s.ruta]
            if s.pos_etiqueta is not None:
                px, py, ancla = s.pos_etiqueta
                s.pos_etiqueta = (px + dx, py + dy, ancla)

    def absorber(self, otro: _Geo, dx: float, dy: float) -> None:
        otro.mover(dx, dy)
        self.nodos.extend(otro.nodos)
        self.aristas.extend(otro.aristas)


def _extension(g: _Geo) -> float:
    """Borde derecho real de todo lo dibujado en ``g``.

    Borde derecho real de todo lo dibujado en ``g`` (símbolos, palabras al lado de un conector,
    flechas y etiquetas).
    """
    derecha = 0.0
    for n in g.nodos:
        extra = 6 + ancho_texto(n.texto) if n.rol in ("romper", "continuar") else 0.0
        derecha = max(derecha, n.x + n.w + extra)
    rutas = [a.puntos for a in g.aristas] + ([g.salida.ruta] if g.salida else [])
    for ruta in rutas:
        for x, _ in ruta:
            derecha = max(derecha, x + 2)
    etiquetas = [(a.etiqueta, a.pos_etiqueta) for a in g.aristas]
    if g.salida is not None:
        etiquetas.append((g.salida.etiqueta, g.salida.pos_etiqueta))
    for texto, pos in etiquetas:
        if pos is not None and pos[2] == "start":
            derecha = max(derecha, pos[0] + ancho_texto(texto) + 2)
    return derecha


def _limpiar(puntos: list[Punto]) -> list[Punto]:
    """Quita puntos repetidos y los intermedios alineados."""
    salida: list[Punto] = []
    for p in puntos:
        p = (round(p[0], 2), round(p[1], 2))
        if salida and salida[-1] == p:
            continue
        if len(salida) >= 2:
            a, b = salida[-2], salida[-1]
            if (a[0] == b[0] == p[0]) or (a[1] == b[1] == p[1]):
                salida[-1] = p
                continue
        salida.append(p)
    return salida


def _envolver(texto: str) -> list[str]:
    """Parte ``texto`` en líneas de hasta ``MAX_CARACTERES`` (por espacios)."""
    if not texto:
        return []
    lineas: list[str] = []
    actual = ""
    for palabra in texto.split(" "):
        while len(palabra) > MAX_CARACTERES:
            if actual:
                lineas.append(actual)
                actual = ""
            lineas.append(palabra[:MAX_CARACTERES])
            palabra = palabra[MAX_CARACTERES:]
        candidato = f"{actual} {palabra}" if actual else palabra
        if len(candidato) <= MAX_CARACTERES:
            actual = candidato
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def ancho_texto(texto: str) -> float:
    """Ancho estimado de ``texto`` en la fuente monoespaciada del diagrama."""
    return len(texto) * ANCHO_CAR


def _medidas(simbolo: str, lineas: list[str]) -> tuple[float, float]:
    tw = max((ancho_texto(x) for x in lineas), default=0.0)
    th = len(lineas) * ALTO_LINEA
    if simbolo == "decision":
        w = max(120.0, tw * 1.5 + 32)
        return w, max(56.0, th / (1 - tw / w) + 14)
    if simbolo == "conector":
        return 2 * R_SALTO, 2 * R_SALTO
    h = th + 2 * RELLENO_Y
    extra = {"predefinido": 20.0, "datos": 28.0, "terminal": h}.get(simbolo, 0.0)
    return max(110.0, tw + 2 * RELLENO_X + extra), h


class _Disposicion:
    """Recorre un diagrama y produce el esquema (patrón Builder)."""

    def __init__(self, idioma: str, idioma_codigo: str):
        self.idioma = idioma
        self.k = 0 if idioma_codigo == "es" else 1
        self._n = 0
        self.saltos: list[Arista] = []
        # Pila de destinos de salto: (lista de `romper`, lista de `continuar`);
        # None en una posición = esa construcción no captura ese salto.
        self.pila: list[tuple[list[str] | None, list[str] | None]] = []

    def t(self, clave: str, **args: str) -> str:
        return i18n.t(clave, self.idioma, **args)

    def kw(self, tipo: str) -> str:
        return PALABRAS_CLAVE[tipo][self.k]

    # ------------------------------------------------------------ símbolos

    def simbolo(
        self, simbolo: str, texto: str, origen: str | None, linea: int, rol: str = ""
    ) -> NodoEsquema:
        self._n += 1
        lineas = _envolver(texto) if simbolo != "conector" else []
        w, h = _medidas(simbolo, lineas)
        if simbolo == "conector" and rol == "union":
            w = h = 2 * R_UNION
        return NodoEsquema(f"s{self._n}", simbolo, texto, lineas, origen, linea, 0, 0, w, h, rol)

    def hoja(self, nodo: NodoEsquema, cae: bool = True) -> _Geo:
        g = _Geo()
        g.nodos.append(nodo)
        g.ancho, g.alto, g.cx = nodo.w, nodo.h, nodo.w / 2
        g.entrada = nodo.id
        if nodo.simbolo == "conector" and nodo.rol in ("romper", "continuar"):
            # La palabra va a la derecha del círculo: se reserva su ancho.
            g.ancho = nodo.w + 6 + ancho_texto(nodo.texto)
        if cae:
            g.salida = _Salida(nodo.id, "", [(g.cx, nodo.h)])
        return g

    def conectar(self, salida: _Salida, destino: str, puntos: list[Punto]) -> Arista:
        a = Arista(
            salida.desde,
            destino,
            salida.etiqueta,
            _limpiar(salida.ruta + puntos),
            pos_etiqueta=salida.pos_etiqueta,
        )
        return a

    def salto(self, desde: str, hasta: str) -> None:
        self.saltos.append(Arista(desde, hasta, salto=True))

    # ------------------------------------------------------------ secuencias

    def secuencia_geos(self, geos: list[_Geo]) -> _Geo | None:
        if not geos:
            return None
        g = _Geo()
        g.cx = max(x.cx for x in geos)
        y = 0.0
        anterior: _Salida | None = None
        for k, x in enumerate(geos):
            if k:
                y += SEP_V
            dx = g.cx - x.cx
            entrada_y = y
            g.absorber(x, dx, y)
            if anterior is not None:
                ultimo = anterior.ruta[-1]
                medio = entrada_y - SEP_V / 2
                g.aristas.append(
                    self.conectar(
                        anterior, x.entrada, [(ultimo[0], medio), (g.cx, medio), (g.cx, entrada_y)]
                    )
                )
            g.ancho = max(g.ancho, dx + x.ancho)
            y += x.alto
            anterior = x.salida
        g.alto = y
        g.entrada = geos[0].entrada
        g.salida = geos[-1].salida
        return g

    def secuencia(self, nodos: list[Nodo]) -> _Geo | None:
        return self.secuencia_geos([self.construccion(n) for n in nodos])

    def construccion(self, n: Nodo) -> _Geo:
        if n.tipo == "si":
            return self.si(n, 0)
        if n.tipo in ("segun", "coincidir"):
            return self.casos(n)
        if n.tipo in ("mientras", "para", "para_cada"):
            return self.ciclo(n)
        if n.tipo == "hacer_mientras":
            return self.hacer(n)
        if n.tipo == "intentar":
            return self.intentar(n)
        return self.instruccion(n)

    def instruccion(self, n: Nodo) -> _Geo:
        if n.tipo in ("romper", "continuar"):
            palabra = self.kw("KW_BREAK" if n.tipo == "romper" else "KW_CONTINUE")
            nodo = self.simbolo("conector", palabra, n.id, n.linea, rol=n.tipo)
            destinos = next(
                (d for d in reversed(self.pila) if d[0 if n.tipo == "romper" else 1] is not None),
                None,
            )
            if destinos is not None:
                lista = destinos[0 if n.tipo == "romper" else 1]
                assert lista is not None
                lista.append(nodo.id)
            return self.hoja(nodo, cae=False)
        if n.tipo == "retornar":
            texto = f"{self.kw('KW_RETURN')} {n.texto}".strip()
            return self.hoja(self.simbolo("terminal", texto, n.id, n.linea, "retornar"), cae=False)
        if n.tipo == "leer":
            texto = f"{self.kw('KW_READ')} {n.texto}"
        elif n.tipo == "escribir":
            texto = f"{self.kw('KW_PRINT')} {n.texto}"
        else:
            texto = n.texto
        simbolo = {"leer": "datos", "escribir": "datos", "llamada": "predefinido"}
        return self.hoja(self.simbolo(simbolo.get(n.tipo, "proceso"), texto, n.id, n.linea, n.tipo))

    # ------------------------------------------------------------ unión

    def reunir(
        self, g: _Geo, salidas: list[_Salida], cx: float, y_fin: float, destino: NodoEsquema | None
    ) -> None:
        """Lleva ``salidas``.

        Lleva ``salidas`` (que acaban a la altura ``y_fin`` o más arriba) a un punto común bajo la
        construcción y deja en ``g`` la salida resultante.
        """
        y_union = y_fin + SEP_V / 2
        if destino is None and len(salidas) <= 1:
            if salidas:
                s = salidas[0]
                x0 = s.ruta[-1][0]
                s.ruta = _limpiar(s.ruta + [(x0, y_union), (cx, y_union)])
                g.salida = s
            g.alto = y_union
            return
        nodo = destino or self.simbolo("conector", "", None, 0, rol="union")
        nodo.x, nodo.y = cx - nodo.w / 2, y_union - nodo.h / 2
        g.nodos.append(nodo)
        for s in salidas:
            x0 = s.ruta[-1][0]
            lado = nodo.x if x0 < cx else nodo.x + nodo.w if x0 > cx else None
            if lado is None:
                pts = [(cx, nodo.y)]
            else:
                pts = [(x0, y_union), (lado, y_union)]
            g.aristas.append(self.conectar(s, nodo.id, pts))
        g.alto = nodo.y + nodo.h
        g.salida = _Salida(nodo.id, "", [(cx, g.alto)])

    # ------------------------------------------------------------ decisiones

    def columnas(
        self, columnas: list[tuple[_Geo | None, float]], ancho_min: float
    ) -> tuple[list[float], list[float], float]:
        """Posición x (izquierda) y centro de cada columna, y ancho total.

        Cada columna tiene un ancho mínimo (su etiqueta); una columna vacía es
        un carril de ancho mínimo por el que la flecha baja recta.
        """
        izq: list[float] = []
        centros: list[float] = []
        x = 0.0
        for geo, minimo in columnas:
            w = max(minimo, geo.ancho if geo is not None else 0.0, 40.0)
            izq.append(x)
            centro = x + (geo.cx + (w - geo.ancho) / 2 if geo is not None else w / 2)
            centros.append(centro)
            x += w + SEP_H
        total = max(x - SEP_H, ancho_min)
        return izq, centros, total

    def si(self, n: Nodo, desde: int) -> _Geo:
        rama = n.ramas[desde]
        d = self.simbolo("decision", rama.etiqueta, n.id, n.linea, "si")
        izquierda = self.secuencia(rama.cuerpo)
        if desde + 1 < len(n.ramas):
            derecha: _Geo | None = self.si(n, desde + 1)
        else:
            derecha = self.secuencia(n.alterno) if n.alterno is not None else None
        return self.dos_caminos(d, izquierda, derecha, self.t("FLU.lbl.si"), self.t("FLU.lbl.no"))

    def dos_caminos(
        self,
        d: NodoEsquema,
        izquierda: _Geo | None,
        derecha: _Geo | None,
        etq_izq: str,
        etq_der: str,
    ) -> _Geo:
        """Decisión (o ``intentar``) con un camino por cada lado, en columnas."""
        g = _Geo()
        li, ld = ancho_texto(etq_izq) + 8, ancho_texto(etq_der) + 8
        _, (ci, cd), _ = self.columnas([(izquierda, li), (derecha, ld)], 0)
        separacion = d.w + 2 * max(LADO_MIN, li, ld)
        if cd - ci < separacion:
            empuje = separacion - (cd - ci)
            cd += empuje
        cx = (ci + cd) / 2
        d.x, d.y = cx - d.w / 2, 0.0
        g.nodos.append(d)
        y0 = d.h + SEP_V
        medio = d.h / 2
        salidas: list[_Salida] = []
        y_fin = y0
        for geo, centro, etiqueta, lado in (
            (izquierda, ci, etq_izq, d.x),
            (derecha, cd, etq_der, d.x + d.w),
        ):
            ancla = "end" if lado == d.x else "start"
            pos = (lado + (-4 if ancla == "end" else 4), medio - 5, ancla)
            if geo is None:
                salidas.append(_Salida(d.id, etiqueta, [(lado, medio), (centro, medio)], pos))
                continue
            g.absorber(geo, centro - geo.cx, y0)
            g.aristas.append(
                Arista(
                    d.id,
                    geo.entrada,
                    etiqueta,
                    _limpiar([(lado, medio), (centro, medio), (centro, y0)]),
                    pos_etiqueta=pos,
                )
            )
            y_fin = max(y_fin, y0 + geo.alto)
            if geo.salida is not None:
                salidas.append(geo.salida)
        g.cx = cx
        g.entrada = d.id
        self.reunir(g, salidas, cx, y_fin, None)
        g.ancho = max(_extension(g), cd + 20)
        return g

    def casos(self, n: Nodo) -> _Geo:
        """``segun``/``coincidir``: una columna por caso bajo un bus horizontal.

        En ``segun`` un caso que no termina en ``romper`` cae al siguiente:
        se dibuja con un par de conectores (salida al pie de su columna,
        entrada en la cabeza de la siguiente).
        """
        g = _Geo()
        d = self.simbolo("decision", n.texto, n.id, n.linea, n.tipo)
        es_segun = n.tipo == "segun"
        rompe: list[str] = []
        self.pila.append((rompe if es_segun else None, None))
        cuerpos = [x.cuerpo for x in n.ramas]
        etiquetas = [x.etiqueta for x in n.ramas]
        if n.alterno is not None:
            cuerpos.append(n.alterno)
            etiquetas.append(self.kw("KW_DEFAULT"))
        por_columna: list[list[_Geo]] = []
        entradas: dict[int, NodoEsquema] = {}
        for k, cuerpo in enumerate(cuerpos):
            partes = [self.construccion(x) for x in cuerpo]
            cae = not partes or partes[-1].salida is not None
            if es_segun and k + 1 < len(cuerpos) and cae:
                fuente = self.simbolo("conector", "", None, 0, rol="caida")
                destino = self.simbolo("conector", "", None, 0, rol="destino")
                entradas[k + 1] = destino
                partes.append(self.hoja(fuente, cae=False))
                self.salto(fuente.id, destino.id)
            por_columna.append(partes)
        self.pila.pop()
        columnas: list[_Geo | None] = []
        for k, partes in enumerate(por_columna):
            if k in entradas:
                partes.insert(0, self.hoja(entradas[k]))
            columnas.append(self.secuencia_geos(partes))
        ninguno = es_segun and n.alterno is None
        etq_cols = etiquetas + ([self.t("FLU.lbl.ninguno")] if ninguno else [])
        if ninguno:
            columnas.append(None)
        especificacion = [(c, ancho_texto(e) + 12) for c, e in zip(columnas, etq_cols, strict=True)]
        if not especificacion:
            especificacion = [(None, ancho_texto(self.t("FLU.lbl.ninguno")) + 12)]
            etq_cols = [self.t("FLU.lbl.ninguno")]
            columnas = [None]
        _, centros, total = self.columnas(especificacion, 0)
        cx = (centros[0] + centros[-1]) / 2
        desplaza = max(0.0, d.w / 2 - cx)
        cx += desplaza
        d.x, d.y = cx - d.w / 2, 0.0
        g.nodos.append(d)
        y_bus = d.h + SEP_V / 2
        y0 = d.h + SEP_V + ALTO_LINEA
        salidas: list[_Salida] = []
        y_fin = y0
        for col, centro, etiqueta in zip(columnas, centros, etq_cols, strict=True):
            centro += desplaza
            pos = (centro + 4, y0 - 6, "start")
            ruta = [(cx, d.h), (cx, y_bus), (centro, y_bus)]
            if col is None:
                salidas.append(_Salida(d.id, etiqueta, ruta + [(centro, y0)], pos))
                continue
            g.absorber(col, centro - col.cx, y0)
            g.aristas.append(
                Arista(
                    d.id, col.entrada, etiqueta, _limpiar(ruta + [(centro, y0)]), pos_etiqueta=pos
                )
            )
            y_fin = max(y_fin, y0 + col.alto)
            if col.salida is not None:
                salidas.append(col.salida)
        g.cx = cx
        g.entrada = d.id
        destino_rompe = None
        if rompe:
            destino_rompe = self.simbolo("conector", "", None, 0, rol="destino")
            for r in rompe:
                self.salto(r, destino_rompe.id)
        self.reunir(g, salidas, cx, y_fin, destino_rompe)
        g.ancho = max(_extension(g), total + desplaza)
        return g

    def intentar(self, n: Nodo) -> _Geo:
        t = self.simbolo("proceso", self.kw("KW_TRY"), n.id, n.linea, "intentar")
        cuerpo = self.secuencia(n.cuerpo)
        captura = self.simbolo(
            "proceso", f"{self.kw('KW_CATCH')} ({n.variable})", n.id, n.linea, rol="captura"
        )
        derecha = self.secuencia_geos(
            [self.hoja(captura)] + [self.construccion(x) for x in n.alterno or []]
        )
        return self.dos_caminos(
            t, cuerpo, derecha, self.t("FLU.lbl.sin_error"), self.t("FLU.lbl.error")
        )

    # ------------------------------------------------------------ ciclos

    def ciclo(self, n: Nodo) -> _Geo:
        """``mientras``, ``para`` y ``para_cada``: condición arriba, cuerpo, vuelta."""
        g = _Geo()
        rompe: list[str] = []
        sigue: list[str] = []
        if n.tipo == "para_cada":
            texto = self.t("FLU.texto.para_cada", variable=n.variable, coleccion=n.texto)
            etq_si, etq_no = self.t("FLU.lbl.siguiente"), self.t("FLU.lbl.agotado")
        else:
            texto = n.texto or self.kw("KW_TRUE")
            etq_si, etq_no = self.t("FLU.lbl.si"), self.t("FLU.lbl.no")
        inicio = (
            self.simbolo("proceso", n.inicio, n.id, n.linea, rol="inicio_para")
            if n.tipo == "para" and n.inicio
            else None
        )
        d = self.simbolo("decision", texto, n.id, n.linea, n.tipo)
        self.pila.append((rompe, sigue))
        partes = [self.construccion(x) for x in n.cuerpo]
        self.pila.pop()
        cola: list[_Geo] = []
        if sigue:
            destino_sigue = self.simbolo("conector", "", None, 0, rol="destino")
            for s in sigue:
                self.salto(s, destino_sigue.id)
            cola.append(self.hoja(destino_sigue))
        if n.tipo == "para" and n.paso:
            cola.append(self.hoja(self.simbolo("proceso", n.paso, n.id, n.linea, rol="paso")))
        cuerpo = self.secuencia_geos(partes + cola)
        y_d = 0.0
        if inicio is not None:
            y_d = inicio.h + SEP_V
        carril_der = max(CARRIL, ancho_texto(etq_no) + 16)
        mitad = max(d.w / 2, inicio.w / 2 if inicio else 0.0, cuerpo.cx if cuerpo else 0.0)
        cx = CARRIL + mitad
        if inicio is not None:
            inicio.x, inicio.y = cx - inicio.w / 2, 0.0
            g.nodos.append(inicio)
        d.x, d.y = cx - d.w / 2, y_d
        g.nodos.append(d)
        if inicio is not None:
            g.aristas.append(Arista(inicio.id, d.id, "", [(cx, inicio.h), (cx, y_d)]))
        y0 = y_d + d.h + SEP_V
        derecha = d.x + d.w
        medio = y_d + d.h / 2
        pos_si = (cx + 4, y_d + d.h + 12, "start")
        if cuerpo is not None:
            g.absorber(cuerpo, cx - cuerpo.cx, y0)
            g.aristas.append(
                Arista(
                    d.id, cuerpo.entrada, etq_si, [(cx, y_d + d.h), (cx, y0)], pos_etiqueta=pos_si
                )
            )
            derecha = max(derecha, cx - cuerpo.cx + cuerpo.ancho)
            y_vuelta = y0 + cuerpo.alto + SEP_V / 2
            vuelta = cuerpo.salida
        else:
            y_vuelta = y_d + d.h + SEP_V / 2
            vuelta = _Salida(d.id, etq_si, [(cx, y_d + d.h)], pos_si)
        if vuelta is not None:
            x0 = vuelta.ruta[-1][0]
            g.aristas.append(
                self.conectar(
                    vuelta,
                    d.id,
                    [(x0, y_vuelta), (CARRIL / 2, y_vuelta), (CARRIL / 2, medio), (d.x, medio)],
                )
            )
        x_der = derecha + carril_der - 8
        y_salida = y_vuelta + SEP_V / 2
        no = _Salida(
            d.id,
            etq_no,
            [(d.x + d.w, medio), (x_der, medio), (x_der, y_salida), (cx, y_salida)],
            (d.x + d.w + 4, medio - 5, "start"),
        )
        g.cx = cx
        g.entrada = inicio.id if inicio is not None else d.id
        self.cerrar(g, no, rompe, cx, y_salida, lateral=True)
        g.ancho = max(_extension(g), derecha + carril_der)
        return g

    def cerrar(
        self, g: _Geo, no: _Salida, rompe: list[str], cx: float, y_salida: float, lateral: bool
    ) -> None:
        """Salida del ciclo: directa, o por un conector con letra si hay ``romper``.

        ``lateral``: la flecha «no» llega por el carril derecho (``mientras``,
        ``para``, ``para_cada``) y entra al conector por su lado derecho; si no,
        baja recta (``hacer … mientras``) y entra por arriba.
        """
        if not rompe:
            g.salida = no
            g.alto = y_salida
            return
        destino = self.simbolo("conector", "", None, 0, rol="destino")
        for r in rompe:
            self.salto(r, destino.id)
        destino.x, destino.y = cx - destino.w / 2, y_salida
        if lateral:
            no.ruta[-1] = (destino.x + destino.w, y_salida + destino.h / 2)
            no.ruta[-2] = (no.ruta[-2][0], y_salida + destino.h / 2)
        g.nodos.append(destino)
        g.aristas.append(
            Arista(
                no.desde, destino.id, no.etiqueta, _limpiar(no.ruta), pos_etiqueta=no.pos_etiqueta
            )
        )
        g.alto = destino.y + destino.h
        g.salida = _Salida(destino.id, "", [(cx, g.alto)])

    def hacer(self, n: Nodo) -> _Geo:
        """``hacer … mientras``: unión arriba, cuerpo, condición abajo y vuelta."""
        g = _Geo()
        rompe: list[str] = []
        sigue: list[str] = []
        union = self.simbolo("conector", "", None, 0, rol="union")
        d = self.simbolo("decision", n.texto, n.id, n.linea, "hacer_mientras")
        self.pila.append((rompe, sigue))
        partes = [self.construccion(x) for x in n.cuerpo]
        self.pila.pop()
        if sigue:
            destino_sigue = self.simbolo("conector", "", None, 0, rol="destino")
            for s in sigue:
                self.salto(s, destino_sigue.id)
            partes.append(self.hoja(destino_sigue))
        cuerpo = self.secuencia_geos(partes)
        etq_si, etq_no = self.t("FLU.lbl.si"), self.t("FLU.lbl.no")
        mitad = max(d.w / 2 + ancho_texto(etq_si), cuerpo.cx if cuerpo else 0.0)
        cx = CARRIL + mitad
        union.x, union.y = cx - union.w / 2, 0.0
        g.nodos.append(union)
        y = union.h + SEP_V
        derecha = cx + d.w / 2
        if cuerpo is not None:
            g.absorber(cuerpo, cx - cuerpo.cx, y)
            g.aristas.append(Arista(union.id, cuerpo.entrada, "", [(cx, union.h), (cx, y)]))
            derecha = max(derecha, cx - cuerpo.cx + cuerpo.ancho)
            y += cuerpo.alto + SEP_V
            if cuerpo.salida is not None:
                x0 = cuerpo.salida.ruta[-1][0]
                g.aristas.append(
                    self.conectar(
                        cuerpo.salida, d.id, [(x0, y - SEP_V / 2), (cx, y - SEP_V / 2), (cx, y)]
                    )
                )
        else:
            g.aristas.append(Arista(union.id, d.id, "", [(cx, union.h), (cx, y)]))
        d.x, d.y = cx - d.w / 2, y
        g.nodos.append(d)
        medio = y + d.h / 2
        g.aristas.append(
            Arista(
                d.id,
                union.id,
                etq_si,
                [
                    (d.x, medio),
                    (CARRIL / 2, medio),
                    (CARRIL / 2, union.h / 2),
                    (union.x, union.h / 2),
                ],
                pos_etiqueta=(d.x - 4, medio - 5, "end"),
            )
        )
        y_salida = y + d.h + SEP_V / 2
        no = _Salida(d.id, etq_no, [(cx, y + d.h), (cx, y_salida)], (cx + 4, y + d.h + 12, "start"))
        g.cx = cx
        g.entrada = union.id
        self.cerrar(g, no, rompe, cx, y_salida, lateral=False)
        g.ancho = max(_extension(g), derecha + CARRIL)
        return g

    # ------------------------------------------------------------ diagrama

    def diagrama(self, diag: Diagrama) -> tuple[list[NodoEsquema], list[Arista], float, float]:
        if diag.tipo == "main":
            texto_inicio = self.t("FLU.inicio_main")
        else:
            texto_inicio = self.t("FLU.inicio", firma=diag.firma)
        inicio = self.hoja(self.simbolo("terminal", texto_inicio, None, diag.linea, "inicio"))
        cuerpo = [self.construccion(x) for x in diag.cuerpo]
        cae = not cuerpo or cuerpo[-1].salida is not None
        partes = [inicio, *cuerpo]
        if cae:
            fin = self.simbolo("terminal", self.t("FLU.fin"), None, 0, "fin")
            partes.append(self.hoja(fin, cae=False))
        g = self.secuencia_geos(partes)
        assert g is not None
        g.mover(MARGEN, MARGEN)
        aristas = g.aristas + self.saltos
        _asignar_marcas(g.nodos, aristas)
        return g.nodos, aristas, g.ancho + 2 * MARGEN, g.alto + 2 * MARGEN


def _letra(k: int) -> str:
    """0 → A, 25 → Z, 26 → AA… (identificadores de conectores)."""
    letras = ""
    k += 1
    while k:
        k, r = divmod(k - 1, 26)
        letras = chr(65 + r) + letras
    return letras


def _asignar_marcas(nodos: list[NodoEsquema], aristas: list[Arista]) -> None:
    """Cada conector de destino recibe una letra.

    Cada conector de destino recibe una letra (en orden de lectura) y cada conector de origen de un
    salto muestra la letra de su destino.
    """
    destinos = sorted(
        (n for n in nodos if n.rol == "destino"), key=lambda n: (round(n.y, 1), round(n.x, 1))
    )
    letras = {n.id: _letra(k) for k, n in enumerate(destinos)}
    por_id = {n.id: n for n in nodos}
    for n in destinos:
        n.marca = letras[n.id]
    for a in aristas:
        if a.salto:
            por_id[a.desde].marca = letras[a.hasta]


def construir_esquema(diagrama: Diagrama, idioma_modelo: str, idioma: str | None = None) -> Esquema:
    """Esquema dibujable de ``diagrama``.

    ``idioma_modelo`` es el de los textos del diagrama (palabras clave que se
    muestran en las cajas); ``idioma`` el de las etiquetas («Sí»/«Yes»,
    «Inicio»/«Start»); por defecto el mismo.
    """
    destino = i18n.normalizar_idioma(idioma) if idioma is not None else idioma_modelo
    disp = _Disposicion(destino, idioma_modelo)
    nodos, aristas, ancho, alto = disp.diagrama(diagrama)
    titulo = i18n.t("FLU.titulo", destino, nombre=diagrama.clave)
    return Esquema(diagrama.clave, titulo, destino, nodos, aristas, ancho, alto)
