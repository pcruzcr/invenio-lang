"""Descripción textual accesible del diagrama de clases (es/en).

INV-3207: un diagrama es una imagen; un estudiante que usa lector de
pantalla (o que imprime en texto plano) necesita la misma información en
frases: qué clasificadores hay, sus miembros con visibilidad y
modificadores dichos con palabras (no con ``+``/``-`` ni cursivas) y cada
relación explicada. El SVG usa estas mismas frases en sus ``<title>`` y
``<desc>``; la CLI (``--uml texto``) y la GUI las muestran tal cual.
"""

from __future__ import annotations

from ..i18n import t
from .modelo import Atributo, Clasificador, Constructor, DiagramaClases, Metodo, Relacion
from .presentacion import literal_codigo, tipo_visible

__all__ = ["describir", "frase_clasificador", "frase_relacion"]

_ORDEN_TIPOS = ("clase", "abstracta", "interfaz", "enumeracion")


def _firma(nombre: str, params: tuple, idioma: str) -> str:
    return f"{nombre}({', '.join(f'{p.nombre}: {tipo_visible(p.tipo, idioma)}' for p in params)})"


def _visibilidad(v: str, idioma: str) -> str:
    return t({"+": "UML.txt.publico", "-": "UML.txt.privado", "#": "UML.txt.protegido"}[v], idioma)


def frase_atributo(a: Atributo, idioma: str) -> str:
    """``motor (público, Motor)`` con los modificadores en palabras."""
    rasgos = [_visibilidad(a.visibilidad, idioma)]
    if a.estatico:
        rasgos.append(t("UML.txt.estatico", idioma))
    if a.constante:
        rasgos.append(t("UML.txt.constante", idioma))
    rasgos.append(tipo_visible(a.tipo, idioma))
    if a.valor_inicial is not None:
        valor = literal_codigo(a.valor_inicial, idioma)
        rasgos.append(t("UML.txt.valor_inicial", idioma, valor=valor))
    return f"{a.nombre} ({', '.join(rasgos)})"


def frase_constructor(c: Constructor, clase: str, idioma: str) -> str:
    """``Auto(m: texto) (público)``."""
    return f"{_firma(clase, c.parametros, idioma)} ({_visibilidad(c.visibilidad, idioma)})"


def frase_metodo(x: Metodo, idioma: str) -> str:
    """``area(): real (público, abstracto)``."""
    rasgos = [_visibilidad(x.visibilidad, idioma)]
    if x.estatico:
        rasgos.append(t("UML.txt.estatico", idioma))
    if x.abstracto:
        rasgos.append(t("UML.txt.abstracto", idioma))
    if x.sobrescribe:
        rasgos.append(t("UML.txt.sobrescribe", idioma))
    retorno = tipo_visible(x.retorno, idioma)
    return f"{_firma(x.nombre, x.parametros, idioma)}: {retorno} ({', '.join(rasgos)})"


def frase_clasificador(modelo: DiagramaClases, c: Clasificador, idioma: str) -> str:
    """Párrafo de un clasificador: tipo, nombre, origen, supertipos y miembros."""
    partes = [t(f"UML.txt.tipo.{c.tipo}", idioma, nombre=c.nombre)]
    if c.parametros_tipo:
        partes.append(t("UML.txt.generico", idioma, parametros=", ".join(c.parametros_tipo)))
    if c.modulo:
        partes.append(t("UML.txt.modulo", idioma, modulo=c.modulo))
    padre = modelo.padre(c.nombre)
    if padre:
        partes.append(t("UML.txt.hereda", idioma, padre=padre))
    interfaces = modelo.interfaces(c.nombre)
    if interfaces:
        partes.append(t("UML.txt.implementa", idioma, interfaces=", ".join(interfaces)))
    sep = t("UML.txt.sep", idioma)
    if c.literales:
        valores = sep.join(
            _firma(x.nombre, x.parametros, idioma) if x.parametros else x.nombre
            for x in c.literales
        )
        partes.append(t("UML.txt.valores", idioma, lista=valores))
    if c.atributos:
        lista = sep.join(frase_atributo(a, idioma) for a in c.atributos)
        partes.append(t("UML.txt.atributos", idioma, lista=lista))
    if c.constructores:
        lista = sep.join(frase_constructor(k, c.nombre, idioma) for k in c.constructores)
        partes.append(t("UML.txt.constructores", idioma, lista=lista))
    if c.metodos:
        lista = "; ".join(frase_metodo(x, idioma) for x in c.metodos)
        partes.append(t("UML.txt.metodos", idioma, lista=lista))
    if c.tipo != "enumeracion" and not (c.atributos or c.constructores or c.metodos):
        partes.append(t("UML.txt.sin_miembros", idioma))
    return " ".join(partes)


def frase_relacion(r: Relacion, idioma: str) -> str:
    """Una relación en palabras (también es el ``<title>`` de su línea en el SVG)."""
    mult = ""
    if r.multiplicidad is not None:
        clave = "UML.txt.mult.varios" if r.multiplicidad == "0..*" else "UML.txt.mult.uno"
        mult = t(clave, idioma, multiplicidad=r.multiplicidad)
    return t(
        f"UML.txt.rel.{r.tipo}",
        idioma,
        origen=r.origen,
        destino=r.destino,
        rol=r.rol or "",
        multiplicidad=mult,
    )


def resumen(modelo: DiagramaClases, idioma: str) -> str:
    """Primera frase: cuántos clasificadores de cada tipo y cuántas relaciones."""
    if not modelo.clasificadores:
        return t("UML.txt.vacio", idioma)
    cuentas = []
    for tipo in _ORDEN_TIPOS:
        n = sum(1 for c in modelo.clasificadores if c.tipo == tipo)
        if n:
            sufijo = "1" if n == 1 else "n"
            cuentas.append(t(f"UML.txt.cuenta.{tipo}.{sufijo}", idioma, n=n))
    n = len(modelo.relaciones)
    relaciones = t(f"UML.txt.cuenta.relacion.{'1' if n == 1 else 'n'}", idioma, n=n)
    return t(
        "UML.txt.resumen",
        idioma,
        cuentas=t("UML.txt.sep", idioma).join(cuentas),
        relaciones=relaciones,
    )


def describir(modelo: DiagramaClases, idioma: str | None = None) -> str:
    """Descripción completa, una línea por clasificador y por relación."""
    idi = idioma or modelo.idioma
    lineas = [resumen(modelo, idi)]
    for c in modelo.clasificadores:
        lineas.append("- " + frase_clasificador(modelo, c, idi))
    if modelo.clasificadores:
        lineas.append(
            t("UML.txt.relaciones", idi) if modelo.relaciones else t("UML.txt.sin_relaciones", idi)
        )
        lineas.extend("- " + frase_relacion(r, idi) for r in modelo.relaciones)
    return "\n".join(lineas)
