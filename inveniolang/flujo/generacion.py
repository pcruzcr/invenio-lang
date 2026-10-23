"""Modelo de diagrama de flujo → código InvenioLang (INV-3002).

La generación escribe el programa en el idioma del modelo (los textos de las
cajas ya están en ese idioma) y, si se pide otro, lo pasa por el traductor
por tokens (``traductor.py``), que conserva exactamente el programa. Al final
se aplica el formateador del proyecto (``formatter.py``), así que el código
generado tiene la sangría canónica de cualquier otro archivo.

Además del texto se devuelve, para cada línea generada, a qué diagrama y a
qué nodo pertenece: la validación (``edicion.validar``) lo usa para colgar
cada diagnóstico del compilador de la caja que lo causó.
"""

from __future__ import annotations

import copy
from collections.abc import Callable

from ..formatter import formatear
from ..i18n import normalizar_idioma
from ..traductor import PALABRAS_CLAVE, traducir
from .modelo import ModeloFlujo, Nodo

__all__ = ["Generado", "codigo_desde_modelo", "generar", "traducir_modelo"]

_SANGRIA = "    "


class Generado:
    """Texto generado (en el idioma del modelo) y dueño de cada línea.

    ``duenos[k]`` es ``(clave del diagrama, id del nodo)`` de la línea
    ``k + 1``; ``(None, None)`` para líneas que no son de ningún diagrama.
    """

    def __init__(self) -> None:
        self.lineas: list[str] = []
        self.duenos: list[tuple[str | None, str | None]] = []
        # INV-4005: línea (1-based) donde empieza cada elemento del programa
        # y, tras el de una clase, cada uno de sus miembros, en orden. El
        # editor de bloques la usa para llevar el cursor del editor a la
        # definición (clase, atributo, subrutina) que el estudiante elige.
        self.inicios: list[int] = []

    @property
    def texto(self) -> str:
        """Programa completo con salto de línea final."""
        return "\n".join(self.lineas) + "\n"

    def linea(self, nivel: int, texto: str, clave: str | None, nodo: str | None) -> None:
        """Añade una línea sangrada con su dueño."""
        self.lineas.append(_SANGRIA * nivel + texto)
        self.duenos.append((clave, nodo))


class _Emisor:
    def __init__(self, idioma: str):
        self.k = 0 if normalizar_idioma(idioma) == "es" else 1
        self.g = Generado()
        self.clave: str | None = None

    def kw(self, tipo: str) -> str:
        return PALABRAS_CLAVE[tipo][self.k]

    def ln(self, nivel: int, texto: str, nodo: Nodo | None = None) -> None:
        self.g.linea(nivel, texto, self.clave, None if nodo is None else nodo.id)

    def secuencia(self, nodos: list[Nodo], nivel: int) -> None:
        for n in nodos:
            self.nodo(n, nivel)

    def nodo(self, n: Nodo, nivel: int) -> None:
        _EMISION[n.tipo](self, n, nivel)

    # ---- hojas

    def simple(self, n: Nodo, nivel: int) -> None:
        self.ln(nivel, f"{n.texto};", n)

    def leer(self, n: Nodo, nivel: int) -> None:
        self.ln(nivel, f"{self.kw('KW_READ')}({n.texto});", n)

    def escribir(self, n: Nodo, nivel: int) -> None:
        self.ln(nivel, f"{self.kw('KW_PRINT')}({n.texto});", n)

    def retornar(self, n: Nodo, nivel: int) -> None:
        kw = self.kw("KW_RETURN")
        self.ln(nivel, f"{kw} {n.texto};" if n.texto else f"{kw};", n)

    def romper(self, n: Nodo, nivel: int) -> None:
        self.ln(nivel, f"{self.kw('KW_BREAK')};", n)

    def continuar(self, n: Nodo, nivel: int) -> None:
        self.ln(nivel, f"{self.kw('KW_CONTINUE')};", n)

    # ---- compuestos

    def si(self, n: Nodo, nivel: int, desde: int = 0) -> None:
        # La cadena «sino si» se escribe anidada: el lenguaje exige llaves
        # tras `sino` (no hay `sino si` sin ellas).
        rama = n.ramas[desde]
        self.ln(nivel, f"{self.kw('KW_IF')} ({rama.etiqueta}) {{", n)
        self.secuencia(rama.cuerpo, nivel + 1)
        sino = self.kw("KW_ELSE")
        if desde + 1 < len(n.ramas):
            self.ln(nivel, f"}} {sino} {{", n)
            self.si(n, nivel + 1, desde + 1)
        elif n.alterno is not None:
            self.ln(nivel, f"}} {sino} {{", n)
            self.secuencia(n.alterno, nivel + 1)
        self.ln(nivel, "}", n)

    def casos(self, n: Nodo, nivel: int, palabra: str) -> None:
        self.ln(nivel, f"{self.kw(palabra)} ({n.texto}) {{", n)
        for rama in n.ramas:
            self.ln(nivel + 1, f"{self.kw('KW_CASE')} {rama.etiqueta}:", n)
            self.secuencia(rama.cuerpo, nivel + 2)
        if n.alterno is not None:
            self.ln(nivel + 1, f"{self.kw('KW_DEFAULT')}:", n)
            self.secuencia(n.alterno, nivel + 2)
        self.ln(nivel, "}", n)

    def segun(self, n: Nodo, nivel: int) -> None:
        self.casos(n, nivel, "KW_SWITCH")

    def coincidir(self, n: Nodo, nivel: int) -> None:
        self.casos(n, nivel, "KW_MATCH")

    def ciclo(self, n: Nodo, nivel: int, cabecera: str) -> None:
        self.ln(nivel, f"{cabecera} {{", n)
        self.secuencia(n.cuerpo, nivel + 1)
        self.ln(nivel, "}", n)

    def mientras(self, n: Nodo, nivel: int) -> None:
        self.ciclo(n, nivel, f"{self.kw('KW_WHILE')} ({n.texto})")

    def para(self, n: Nodo, nivel: int) -> None:
        self.ciclo(n, nivel, f"{self.kw('KW_FOR')} ({n.inicio}; {n.texto}; {n.paso})")

    def para_cada(self, n: Nodo, nivel: int) -> None:
        self.ciclo(n, nivel, f"{self.kw('KW_FOREACH')} ({n.variable} : {n.texto})")

    def hacer_mientras(self, n: Nodo, nivel: int) -> None:
        self.ln(nivel, f"{self.kw('KW_DO')} {{", n)
        self.secuencia(n.cuerpo, nivel + 1)
        self.ln(nivel, f"}} {self.kw('KW_WHILE')} ({n.texto});", n)

    def intentar(self, n: Nodo, nivel: int) -> None:
        self.ln(nivel, f"{self.kw('KW_TRY')} {{", n)
        self.secuencia(n.cuerpo, nivel + 1)
        self.ln(nivel, f"}} {self.kw('KW_CATCH')} ({n.variable}) {{", n)
        self.secuencia(n.alterno or [], nivel + 1)
        self.ln(nivel, "}", n)


_EMISION: dict[str, Callable[[_Emisor, Nodo, int], None]] = {
    "proceso": _Emisor.simple,
    "declaracion": _Emisor.simple,
    "llamada": _Emisor.simple,
    "leer": _Emisor.leer,
    "escribir": _Emisor.escribir,
    "retornar": _Emisor.retornar,
    "romper": _Emisor.romper,
    "continuar": _Emisor.continuar,
    "si": _Emisor.si,
    "segun": _Emisor.segun,
    "coincidir": _Emisor.coincidir,
    "mientras": _Emisor.mientras,
    "hacer_mientras": _Emisor.hacer_mientras,
    "para": _Emisor.para,
    "para_cada": _Emisor.para_cada,
    "intentar": _Emisor.intentar,
}


def generar(modelo: ModeloFlujo) -> Generado:
    """Programa en el idioma del modelo, línea a línea y con el dueño de cada una."""
    em = _Emisor(modelo.idioma)
    for k, el in enumerate(modelo.elementos):
        if k:
            em.ln(0, "")
        em.g.inicios.append(len(em.g.lineas) + 1)
        if el.tipo == "codigo":
            em.ln(0, el.texto)
            continue
        piezas = [(0, el)] if el.tipo == "subrutina" else [(1, m) for m in el.miembros]
        if el.tipo == "clase":
            em.ln(0, f"{el.texto} {{")
        for nivel, pieza in piezas:
            if el.tipo == "clase":
                em.g.inicios.append(len(em.g.lineas) + 1)
            if pieza.diagrama is None:
                em.ln(nivel, pieza.texto)
                continue
            d = pieza.diagrama
            em.clave = d.clave
            em.ln(nivel, f"{d.firma} {{")
            em.secuencia(d.cuerpo, nivel + 1)
            em.ln(nivel, "}")
            em.clave = None
        if el.tipo == "clase":
            em.ln(0, "}")
    return em.g


def codigo_desde_modelo(modelo: ModeloFlujo, idioma: str | None = None) -> str:
    """Código InvenioLang del modelo en ``idioma`` (``None``: el del modelo).

    Las líneas conservan su numeración al traducir y formatear: el traductor
    solo cambia palabras y el formateador solo la sangría.
    """
    texto = generar(modelo).texto
    destino = normalizar_idioma(idioma) if idioma is not None else modelo.idioma
    if destino != modelo.idioma:
        texto = traducir(texto, destino)
    return formatear(texto)


def _traducir_fragmento(texto: str, destino: str, captura: str | None) -> str:
    """Traduce un fragmento suelto.

    Traduce un fragmento suelto; dentro de un ``capturar (e)`` antepone ese contexto para que
    ``e.mensaje``/``e.codigo`` también se traduzcan.
    """
    if not texto:
        return texto
    if captura is None:
        return traducir(texto, destino)
    prefijo = f"capturar ({captura}) {{ "
    traducido = traducir(prefijo + texto, destino)
    return traducido[len(traducir(prefijo, destino)) :]


def _traducir_nodos(nodos: list[Nodo], destino: str, captura: str | None) -> None:
    for n in nodos:
        n.texto = _traducir_fragmento(n.texto, destino, captura)
        n.inicio = _traducir_fragmento(n.inicio, destino, captura)
        n.paso = _traducir_fragmento(n.paso, destino, captura)
        n.variable = _traducir_fragmento(n.variable, destino, captura)
        for rama in n.ramas:
            rama.etiqueta = _traducir_fragmento(rama.etiqueta, destino, captura)
        for parte, sec in n.secuencias():
            interior = n.variable if n.tipo == "intentar" and parte == "captura" else captura
            _traducir_nodos(sec, destino, interior)


def traducir_modelo(modelo: ModeloFlujo, idioma: str) -> ModeloFlujo:
    """Copia del modelo con todos sus textos en ``idioma`` (sin compilar nada).

    Sirve para cambiar el idioma de un diagrama que se está editando aunque
    todavía no compile; usa el mismo traductor por tokens que el código.
    """
    destino = normalizar_idioma(idioma)
    nuevo = copy.deepcopy(modelo)
    nuevo.idioma = destino
    for el in nuevo.elementos:
        el.texto = _traducir_fragmento(el.texto, destino, None)
        for pieza in [el, *el.miembros]:
            if pieza is not el:
                pieza.texto = _traducir_fragmento(pieza.texto, destino, None)
            if pieza.diagrama is not None:
                pieza.diagrama.firma = _traducir_fragmento(pieza.diagrama.firma, destino, None)
                _traducir_nodos(pieza.diagrama.cuerpo, destino, None)
    return nuevo
