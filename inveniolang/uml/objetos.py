"""Diagrama de objetos UML a partir de un paso de una traza de la Fase 2.

INV-3209: el diagrama de clases muestra el *diseño*; el de objetos muestra
qué existe en memoria en un instante: cada instancia (``a : Auto``) con el
valor de sus campos y los enlaces entre ellas. Se construye desde un paso
del contrato JSON v1 de ``inveniolang.visualizacion`` (montículo con ids
estables y marcos con sus variables), así que sirve igual para una traza
recién calculada que para una guardada en disco.

Nombres: una instancia se llama como la variable que la referencia, buscando
del marco activo hacia ``main`` (si dos objetos distintos se llaman igual en
marcos diferentes, el segundo lleva la subrutina entre paréntesis); una instancia sin
variable es anónima y se nombra por su id (``#7 : Nodo``). ``este``/``this``
solo nombra a un objeto que ninguna otra variable referencia.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any
from xml.sax.saxutils import escape

from ..i18n import t
from ..visualizacion.render_svg import FUENTE, PALETAS, _n
from ..visualizacion.render_texto import es_ref, normalizar_paso, valor_texto
from .svg import ALTO_LINEA, MARGEN, RELLENO_X, SEP_COLUMNAS, T_MIEMBRO, T_NOTA, _Lienzo, _punta
from .svg import _ancho_texto as _ancho

__all__ = ["describir_objetos", "svg_objetos"]

MAX_INSTANCIAS = 60
MAX_ELEMENTOS = 12
MAX_ANCHO_FILA = 1200.0
SEP_NIVELES = 80.0
_RECEPTORES = frozenset({"este", "this"})


class _Instancia:
    """Objeto, arreglo o matriz del montículo con su texto ya calculado."""

    def __init__(self, nodo: Mapping[str, Any], nombre: str, idioma: str):
        self.id = int(nodo["id"])
        self.nodo = nodo
        self.nombre = nombre
        self.tipo = nodo["tipo"]
        n = len(nodo["elementos"])
        if self.tipo == "objeto":
            self.clase = str(nodo.get("clase") or "?")
        elif self.tipo == "matriz":
            cols = len(nodo["elementos"][0]) if n else 0
            self.clase = t("UML.obj.matriz", idioma, filas=n, columnas=cols)
        else:
            self.clase = t("UML.obj.arreglo", idioma, n=n)
        self.cabecera = f"{nombre} : {self.clase}"
        self.lineas: list[str] = []
        self.enlaces: list[tuple[str, int]] = []
        self.nivel = 0
        self.x = self.y = self.w = self.h = 0.0

    def calcular(self, nombres: Mapping[int, str], idioma: str) -> None:
        """Líneas de campos/celdas y enlaces salientes (necesita los nombres de todos)."""
        nodo = self.nodo
        if self.tipo == "objeto":
            for campo, valor in nodo["campos"].items():
                self.lineas.append(f"{campo} = {valor_texto(valor, idioma, nombres)}")
                if es_ref(valor):
                    self.enlaces.append((campo, int(valor["id"])))
        else:
            for i, elem in enumerate(nodo["elementos"]):
                if self.tipo == "matriz":
                    fila = ", ".join(valor_texto(v, idioma, nombres) for v in elem)
                    texto = f"[{i}] = {fila}"
                    for j, v in enumerate(elem):
                        if es_ref(v):
                            self.enlaces.append((f"[{i}][{j}]", int(v["id"])))
                else:
                    texto = f"[{i}] = {valor_texto(elem, idioma, nombres)}"
                    if es_ref(elem):
                        self.enlaces.append((f"[{i}]", int(elem["id"])))
                if i < MAX_ELEMENTOS:
                    self.lineas.append(texto)
            if len(nodo["elementos"]) > MAX_ELEMENTOS:
                resto = len(nodo["elementos"]) - MAX_ELEMENTOS
                self.lineas.append(t("UML.obj.mas", idioma, n=resto))
        if not self.lineas:
            self.lineas.append(t("UML.obj.sin_campos", idioma))
        textos = [self.cabecera] + self.lineas
        self.w = max(110.0, max(_ancho(x, T_MIEMBRO) for x in textos) + 2 * RELLENO_X)
        self.h = 12 + ALTO_LINEA + 8 + ALTO_LINEA * len(self.lineas) + 6

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def frase(self, idioma: str) -> str:
        return t("UML.obj.frase", idioma, cabecera=self.cabecera, campos="; ".join(self.lineas))


def _instancias(paso: Mapping[str, Any], idioma: str) -> tuple[list[_Instancia], int]:
    """Instancias en orden de recorrido (BFS desde las variables) y el total existente."""
    monticulo = paso["monticulo"]
    nombres: dict[int, str] = {}
    usados: set[str] = set()
    raices: list[int] = []
    # Primero las variables del programa y después `este`/`this`: un objeto en
    # construcción se reconoce mejor por la variable que lo recibirá.
    for receptor in (False, True):
        for marco in reversed(paso["marcos"]):
            for var, dato in marco["variables"].items():
                valor = dato.get("valor")
                if (var in _RECEPTORES) != receptor or not es_ref(valor):
                    continue
                ident = int(valor["id"])
                if ident not in monticulo:
                    continue
                raices.append(ident)
                if ident in nombres:
                    continue
                nombre = var if var not in usados else f"{var} ({marco['subrutina']})"
                usados.add(nombre)
                nombres[ident] = nombre
    niveles: dict[int, int] = {}
    orden: list[int] = []
    cola = [(r, 0) for r in raices]
    while cola:
        ident, nivel = cola.pop(0)
        if ident in niveles or ident not in monticulo:
            continue
        niveles[ident] = nivel
        orden.append(ident)
        nodo = monticulo[ident]
        hijos = list(nodo["campos"].values())
        for elem in nodo["elementos"]:
            hijos.extend(elem if isinstance(elem, list) else [elem])
        cola.extend((int(v["id"]), nivel + 1) for v in hijos if es_ref(v))
    resto = sorted(i for i in monticulo if i not in niveles)
    ultimo = max(niveles.values(), default=-1) + 1
    for ident in resto:
        niveles[ident] = ultimo
        orden.append(ident)
    total = len(orden)
    orden = orden[:MAX_INSTANCIAS]
    for ident in orden:
        nombres.setdefault(ident, f"#{ident}")
    instancias = []
    for ident in orden:
        inst = _Instancia(monticulo[ident], nombres[ident], idioma)
        inst.nivel = niveles[ident]
        instancias.append(inst)
    for inst in instancias:
        inst.calcular(nombres, idioma)
    return instancias, total


def describir_objetos(paso: Mapping[str, Any], idioma: str = "es") -> str:
    """Descripción textual del diagrama de objetos del paso (es/en)."""
    p = normalizar_paso(paso, idioma)
    instancias, total = _instancias(p, idioma)
    lineas = [t("UML.obj.resumen", idioma, n=p["n"], linea=p["linea"], total=total)]
    if not instancias:
        lineas.append(t("UML.obj.vacio", idioma))
    nombres = {i.id: i.nombre for i in instancias}
    for inst in instancias:
        lineas.append("- " + inst.frase(idioma))
    enlaces = [
        t("UML.obj.enlace", idioma, origen=inst.nombre, campo=campo, destino=nombres[destino])
        for inst in instancias
        for campo, destino in inst.enlaces
        if destino in nombres
    ]
    if enlaces:
        lineas.append(t("UML.obj.enlaces", idioma, lista="; ".join(enlaces)))
    if total > len(instancias):
        lineas.append(t("UML.obj.recortado", idioma, mostrados=len(instancias), total=total))
    return "\n".join(lineas)


def _colocar(instancias: list[_Instancia]) -> tuple[float, float]:
    filas: list[list[_Instancia]] = []
    for nivel in sorted({i.nivel for i in instancias}):
        actual: list[_Instancia] = []
        ancho = 0.0
        for inst in (i for i in instancias if i.nivel == nivel):
            if actual and ancho + SEP_COLUMNAS + inst.w > MAX_ANCHO_FILA:
                filas.append(actual)
                actual, ancho = [], 0.0
            ancho += (SEP_COLUMNAS if actual else 0) + inst.w
            actual.append(inst)
        filas.append(actual)
    anchos = [sum(i.w for i in f) + SEP_COLUMNAS * (len(f) - 1) for f in filas]
    total = max(anchos, default=0.0)
    y = MARGEN
    for fila, ancho in zip(filas, anchos, strict=True):
        x = MARGEN + (total - ancho) / 2
        for inst in fila:
            inst.x, inst.y = x, y
            x += inst.w + SEP_COLUMNAS
        y += max(i.h for i in fila) + SEP_NIVELES
    return total + 2 * MARGEN, y - SEP_NIVELES + MARGEN


def _borde(inst: _Instancia, hx: float, hy: float) -> tuple[float, float]:
    dx, dy = hx - inst.cx, hy - inst.cy
    if dx == 0 and dy == 0:
        return inst.cx, inst.y
    fx = (inst.w / 2) / abs(dx) if dx else math.inf
    fy = (inst.h / 2) / abs(dy) if dy else math.inf
    f = min(fx, fy)
    return inst.cx + dx * f, inst.cy + dy * f


def _enlace(lz: _Lienzo, a: _Instancia, b: _Instancia, campo: str, k: int, idioma: str) -> None:
    lz.grupo(t("UML.obj.enlace", idioma, origen=a.nombre, campo=campo, destino=b.nombre))
    if a is b:
        y1 = a.y + 12 + 22 * k
        x0, x1 = a.x + a.w, a.x + a.w + 24 + 10 * k
        lz.trazo([(x0, y1), (x1, y1), (x1, y1 + 18), (x0 + 12, y1 + 18)])
        _punta(lz, x0, y1 + 18, -1.0, 0.0, "abierta")
        lz.texto_uml(x1 + 4, y1 + 13, campo, tam=T_NOTA)
        lz.fin_grupo()
        return
    vx, vy = b.cx - a.cx, b.cy - a.cy
    largo = math.hypot(vx, vy) or 1.0
    d = (k + 1) // 2 * 14.0 * (1 if k % 2 else -1)
    px, py = -vy / largo * d, vx / largo * d
    ini = _borde(a, b.cx + px, b.cy + py)
    fin = _borde(b, a.cx + px, a.cy + py)
    ini, fin = (ini[0] + px, ini[1] + py), (fin[0] + px, fin[1] + py)
    largo = math.hypot(fin[0] - ini[0], fin[1] - ini[1]) or 1.0
    ux, uy = (fin[0] - ini[0]) / largo, (fin[1] - ini[1]) / largo
    lz.trazo([ini, fin])
    _punta(lz, fin[0], fin[1], ux, uy, "abierta")
    mx, my = (ini[0] + fin[0]) / 2, (ini[1] + fin[1]) / 2
    w = _ancho(campo, T_NOTA) + 8
    lz.rect(mx - w / 2, my - 11, w, 15, "fondo", None, radio=3)
    lz.texto_uml(mx, my, campo, tam=T_NOTA, ancla="middle")
    lz.fin_grupo()


def svg_objetos(paso: Mapping[str, Any], idioma: str = "es", *, tema: str = "claro") -> str:
    """SVG del diagrama de objetos del paso: instancias, valores y enlaces."""
    p = normalizar_paso(paso, idioma)
    paleta = PALETAS[tema]
    lz = _Lienzo(paleta, idioma)
    instancias, _total = _instancias(p, idioma)
    ancho, alto = _colocar(instancias)
    por_id = {i.id: i for i in instancias}
    cuenta: dict[tuple[int, int], int] = {}
    for inst in instancias:
        for campo, destino in inst.enlaces:
            if destino not in por_id:
                continue
            clave = (min(inst.id, destino), max(inst.id, destino))
            k = cuenta.get(clave, 0)
            cuenta[clave] = k + 1
            _enlace(lz, inst, por_id[destino], campo, k, idioma)
            if destino == inst.id:
                ancho = max(ancho, inst.x + inst.w + 60 + 10 * k + _ancho(campo, T_NOTA))
    for inst in instancias:
        lz.grupo(inst.frase(idioma))
        lz.rect(inst.x, inst.y, inst.w, inst.h, "panel", "panel_borde", 1.6, radio=3)
        lz.texto_uml(
            inst.cx,
            inst.y + 12 + ALTO_LINEA - 6,
            inst.cabecera,
            tam=T_MIEMBRO,
            ancla="middle",
            negrita=True,
            subrayado=True,
        )
        y = inst.y + 12 + ALTO_LINEA + 4
        lz.linea(inst.x, y, inst.x + inst.w, y, "panel_borde", 1.2)
        for linea in inst.lineas:
            y += ALTO_LINEA
            lz.texto_uml(inst.x + RELLENO_X, y - 5, linea)
        lz.fin_grupo()
    if not instancias:
        mensaje = t("UML.obj.vacio", idioma)
        lz.texto_uml(MARGEN, MARGEN + 16, mensaje, rol="texto_suave", mono=False)
        ancho, alto = max(360.0, _ancho(mensaje, T_MIEMBRO) + 2 * MARGEN), 64.0
    titulo = t("UML.obj.titulo", idioma, n=p["n"], linea=p["linea"])
    return "".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{_n(ancho)}"'
            f' height="{_n(alto)}" viewBox="0 0 {_n(ancho)} {_n(alto)}" role="img"'
            f' aria-labelledby="uml-obj-titulo uml-obj-desc" font-family="{FUENTE}"'
            f' data-paso="{p["n"]}">',
            f'<title id="uml-obj-titulo">{escape(titulo)}</title>',
            f'<desc id="uml-obj-desc">{escape(describir_objetos(p, idioma))}</desc>',
            f'<rect x="0" y="0" width="{_n(ancho)}" height="{_n(alto)}"'
            f' fill="{paleta["fondo"]}" class="f-fondo"/>',
            *lz.partes,
            "</svg>",
        ]
    )
