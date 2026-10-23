"""Rótulos de los bloques y descripción textual accesible (INV-4007).

Cada tipo de bloque tiene una **plantilla** bilingüe en el catálogo i18n
(``BLQ.plantilla.<tipo>``), por ejemplo ``"mientras {condicion}"``:

* ``{nombre}`` es un campo, un hueco o una lista «en línea» (argumentos,
  valores de ``imprimir``, parámetros) del bloque;
* ``<? … ?>`` es un tramo opcional: en el texto se omite si todo lo que
  nombra está vacío (``declarar entero x<? = {valor}?>``), mientras que el lienzo lo
  muestra siempre para que el hueco se pueda rellenar.

Las listas que no aparecen en la plantilla son **bocas** (pilas de
instrucciones, ramas, casos, miembros) y se dibujan debajo de la cabecera.
Este módulo produce el texto que muestran el lienzo, la paleta, los
lectores de pantalla (``describir``) y los anuncios del editor por teclado:
el estudiante que no ve el lienzo recibe exactamente la misma información.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import i18n
from .catalogo import TIPOS
from .escritor import Escritor
from .modelo import Bloque, ModeloBloques

__all__ = [
    "Pieza",
    "bocas",
    "describir",
    "piezas",
    "rotulo",
    "rotulo_boca",
    "texto_campo",
    "texto_ranura",
]


@dataclass(frozen=True)
class Pieza:
    """Trozo de plantilla: ``texto`` literal, ``ref`` a una parte o tramo ``opcional``."""

    clase: str
    valor: str = ""
    hijas: tuple[Pieza, ...] = ()


def _analizar(plantilla: str) -> tuple[Pieza, ...]:
    salida: list[Pieza] = []
    i = 0
    while i < len(plantilla):
        if plantilla.startswith("<?", i):
            fin = plantilla.index("?>", i)
            salida.append(Pieza("opcional", hijas=_analizar(plantilla[i + 2 : fin])))
            i = fin + 2
        elif plantilla[i] == "{":
            fin = plantilla.index("}", i)
            salida.append(Pieza("ref", plantilla[i + 1 : fin]))
            i = fin + 1
        else:
            j = i
            while j < len(plantilla) and plantilla[j] != "{" and not plantilla.startswith("<?", j):
                j += 1
            salida.append(Pieza("texto", plantilla[i:j]))
            i = j
    return tuple(salida)


def piezas(tipo: str, idioma: str | None = None, rama_otra: bool = False) -> tuple[Pieza, ...]:
    """Plantilla analizada del tipo (``rama_otra``: rama «sino si» de un ``si``)."""
    clave = "BLQ.plantilla.rama_si.otra" if rama_otra else f"BLQ.plantilla.{tipo}"
    codigo = i18n.normalizar_idioma(idioma) if idioma is not None else i18n.idioma_actual()
    # La plantilla se lee sin formatear: sus {marcadores} los rellena _render.
    return _analizar(i18n.REGISTRO.obtener(codigo).mensajes[clave])


def _refs(p: tuple[Pieza, ...]) -> set[str]:
    salida: set[str] = set()
    for x in p:
        if x.clase == "ref":
            salida.add(x.valor)
        elif x.clase == "opcional":
            salida |= _refs(x.hijas)
    return salida


def bocas(b: Bloque, idioma: str | None = None) -> list[str]:
    """Listas del bloque que se dibujan como bocas (no están en la plantilla).

    Se omiten las que una bandera desactiva (``sino`` sin ``tiene_sino``…).
    """
    en_linea = _refs(piezas(b.tipo, idioma))
    ocultas = {
        "sino": "tiene_sino",
        "por_defecto": "tiene_defecto",
        "cuerpo": "con_cuerpo",
    }
    return [
        x.nombre
        for x in TIPOS[b.tipo].listas
        if x.nombre not in en_linea
        and not (
            x.nombre in ocultas
            and ocultas[x.nombre] in b.campos
            and not b.campos[ocultas[x.nombre]]
        )
    ]


def texto_campo(b: Bloque, campo: str, idioma: str | None = None) -> str:
    """Valor de un campo tal como se lee (banderas y opciones traducidas)."""
    valor = b.campos[campo]
    if isinstance(valor, bool):
        if campo == "seguro":
            return "?." if valor else "."
        if campo == "con_parametros":
            return ""
        if campo == "con_cuerpo":
            return "" if valor else i18n.t("BLQ.bandera.con_cuerpo.no", idioma)
        return i18n.t(f"BLQ.bandera.{campo}", idioma) if valor else ""
    if campo in ("visibilidad", "modificador", "posicion", "estilo") or (
        b.tipo == "logico" and campo == "valor"
    ):
        return i18n.t(f"BLQ.valor.{valor}", idioma) if valor else ""
    return str(valor)


def texto_ranura(b: Bloque, nombre: str, idioma: str | None = None) -> str:
    """Texto de un campo, hueco o lista en línea del bloque."""
    esc = Escritor(i18n.normalizar_idioma(idioma) if idioma else i18n.idioma_actual())
    if nombre in b.campos:
        return texto_campo(b, nombre, idioma)
    if nombre in b.huecos:
        h = b.huecos[nombre]
        return "" if h is None else esc.expresion(h)
    lista = b.listas.get(nombre, [])
    if lista and lista[0].tipo == "parametro":
        return esc.parametros(lista)
    if lista and lista[0].tipo == "fila":
        return ", ".join(
            "{" + ", ".join(esc.expresion(v) for v in f.listas["valores"]) + "}" for f in lista
        )
    return ", ".join(esc.expresion(x) for x in lista)


def _vacia(b: Bloque, nombre: str) -> bool:
    if nombre in b.campos:
        v = b.campos[nombre]
        return v is False or v == ""
    if nombre in b.huecos:
        return b.huecos[nombre] is None
    return not b.listas.get(nombre)


def _render(b: Bloque, p: tuple[Pieza, ...], idioma: str | None) -> str:
    partes: list[str] = []
    for x in p:
        if x.clase == "texto":
            partes.append(x.valor)
        elif x.clase == "ref":
            partes.append(texto_ranura(b, x.valor, idioma))
        elif not all(_vacia(b, r) for r in _refs(x.hijas)):
            partes.append(_render(b, x.hijas, idioma))
    return "".join(partes)


def rotulo(b: Bloque, idioma: str | None = None, rama_otra: bool = False) -> str:
    """Texto de una línea del bloque (``rama_otra``: rama «sino si»)."""
    texto = _render(b, piezas(b.tipo, idioma, rama_otra), idioma)
    return " ".join(texto.split())


def _describir(b: Bloque, nivel: int, idioma: str | None, lineas: list[str], otra: bool) -> None:
    lineas.append("  " * nivel + rotulo(b, idioma, otra))
    for lista in bocas(b, idioma):
        etiqueta = rotulo_boca(b, lista, idioma)
        interior = nivel + 1
        if etiqueta:
            lineas.append("  " * interior + etiqueta)
            interior += 1
        for k, hijo in enumerate(b.listas[lista]):
            _describir(hijo, interior, idioma, lineas, b.tipo == "si" and k > 0)


def rotulo_boca(b: Bloque, lista: str, idioma: str | None = None) -> str:
    """Rótulo de una boca (``sino``, ``capturar (e)``…) o ``""`` si no lleva."""
    clave = f"BLQ.boca.{b.tipo}.{lista}"
    if not i18n.REGISTRO.obtener(i18n.IDIOMA_POR_DEFECTO).tiene(clave):
        return ""
    return i18n.t(clave, idioma, **{k: texto_campo(b, k, idioma) for k in b.campos})


def describir(modelo: ModeloBloques, idioma: str | None = None) -> str:
    """Programa de bloques como texto sangrado (una línea por bloque de instrucción).

    Es la alternativa textual del lienzo (lectores de pantalla, CLI
    ``bloques --texto``): cada línea es el rótulo del bloque con sus valores
    escritos como expresiones.
    """
    lineas: list[str] = []
    for b in modelo.programa:
        _describir(b, 0, idioma, lineas, False)
    return "\n".join(lineas) + "\n"
