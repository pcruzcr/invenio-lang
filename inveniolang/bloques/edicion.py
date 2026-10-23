"""Edición pura de bloques y validación completa (INV-4008).

Operaciones del editor de arrastrar y soltar (Qt y web): **insertar**,
**mover**, **eliminar**, **duplicar**, **envolver** y **editar** un campo.
Todas son puras: reciben un modelo y devuelven uno nuevo (la GUI guarda los
anteriores para deshacer/rehacer) y, si la operación no es válida, lanzan
``ErrorBloques`` con el motivo bilingüe (``reglas.motivo_rechazo``: qué
familia de bloque cabe ahí, qué tipo de valor espera el hueco…). Es la misma
filosofía que la edición del diagrama de flujo (``flujo/edicion.py``), de la
que se reutilizan las reglas de ``romper``/``continuar``, sus mensajes y la
validación con el compilador real.

Un destino es una posición de una lista (``Destino(padre, "cuerpo", 2)``)
o un hueco (``Destino(padre, "condicion")``); ``padre=None`` es la lista
``programa``. Soltar un valor en un hueco ocupado hace lo que Blockly: si el
bloque nuevo tiene un hueco libre compatible, el que había pasa a ese hueco
(soltar «+» sobre ``x`` da ``x + _``); si no, se rechaza.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from .. import flujo
from ..i18n import normalizar_idioma
from ..traductor import PALABRAS_CLAVE
from .catalogo import PALETA, TIPOS
from .conversion import a_flujo, claves_de_diagramas
from .lector import Ids
from .lector import nuevo_bloque as _crear
from .modelo import Bloque, ErrorBloques, ModeloBloques, nombre_parte, nombre_tipo, recorrer
from .reglas import (
    Contexto,
    Ranura,
    error_campo,
    faltantes,
    motivo_rechazo,
    problemas_de_tipos,
    saltos_fuera_de_lugar,
)

__all__ = [
    "Destino",
    "Problema",
    "desde_paleta",
    "donde_esta",
    "duplicar",
    "editar",
    "eliminar",
    "envolver",
    "insertar",
    "mover",
    "nuevo_bloque",
    "nuevo_modelo",
    "validar",
]


@dataclass(frozen=True)
class Destino:
    """Sitio donde soltar: lista ``parte`` (en ``indice``; ``None`` al final) o hueco ``parte``."""

    padre: str | None = None
    parte: str = "programa"
    indice: int | None = None


@dataclass(frozen=True)
class Problema:
    """Un problema del programa de bloques: bloque culpable (si se sabe) y mensaje."""

    bloque: str | None
    error: Any  # ErrorBloques o ErrorFlujo: ambos ofrecen texto(idioma)

    def texto(self, idioma: str | None = None) -> str:
        """Mensaje en ``idioma``."""
        return self.error.texto(idioma)


# ====================================================================== creación


_DEFECTO_KW = {es: tipo for tipo, (es, _en) in PALABRAS_CLAVE.items()}


def nuevo_bloque(tipo: str, idioma: str = "es", /, **campos: Any) -> Bloque:
    """Bloque nuevo (sin id: lo asigna ``insertar``) con sus campos validados.

    Los campos que no se dan toman el valor por defecto del catálogo (los
    tipos por defecto se escriben en ``idioma``). Un ``si`` nace con su
    primera rama y una ``enumeracion`` con un valor, como exige el catálogo.
    """
    if tipo not in TIPOS:
        raise ErrorBloques("BLQ.edicion.tipo", tipo=tipo)
    desc = TIPOS[tipo]
    idioma = normalizar_idioma(idioma)
    b = _crear(Ids(), tipo)
    b.id = ""
    for c in desc.campos:
        if c.clase in ("tipo", "tipo_retorno") and c.defecto in _DEFECTO_KW:
            b.campos[c.nombre] = PALABRAS_CLAVE[_DEFECTO_KW[c.defecto]][0 if idioma == "es" else 1]
    for nombre, valor in campos.items():
        campo = desc.campo(nombre)
        if campo is None:
            raise ErrorBloques("BLQ.edicion.campo", campo=nombre, tipo=nombre_tipo(tipo))
        err = error_campo(campo, valor)
        if err is not None:
            raise ErrorBloques("BLQ.val.en_campo", campo=nombre_parte(nombre), detalle=err)
        b.campos[nombre] = valor
    if tipo == "si":
        b.listas["ramas"].append(nuevo_bloque("rama_si", idioma))
    if tipo == "enumeracion":
        b.listas["miembros"].append(nuevo_bloque("miembro_enum", idioma))
    if tipo == "fila":
        b.listas["valores"].append(nuevo_bloque("numero", idioma))
    return b


def desde_paleta(clave: str, idioma: str = "es", /, **campos: Any) -> Bloque:
    """Bloque de la entrada ``clave`` de la paleta (con sus campos preestablecidos)."""
    entrada = next((e for e in PALETA if e.clave == clave), None)
    if entrada is None:
        raise ErrorBloques("BLQ.edicion.tipo", tipo=clave)
    return nuevo_bloque(entrada.tipo, idioma, **{**dict(entrada.campos), **campos})


def nuevo_modelo(idioma: str = "es") -> ModeloBloques:
    """Programa con sólo ``main`` vacío (punto de partida del editor)."""
    idioma = normalizar_idioma(idioma)
    main = nuevo_bloque("subrutina", idioma, nombre="main")
    main.id = "b1"
    return ModeloBloques(idioma, [main])


# ====================================================================== búsqueda


def _ids(modelo: ModeloBloques) -> set[str]:
    return {b.id for b in recorrer(modelo.programa)}


def _asignar_ids(modelo: ModeloBloques, bloque: Bloque) -> None:
    ids = Ids(_ids(modelo))
    for b in recorrer([bloque]):
        if not b.id or b.id in ids.usados:
            b.id = ids.nuevo()
        else:
            ids.usados.add(b.id)


def donde_esta(modelo: ModeloBloques, ident: str) -> tuple[Bloque | None, Ranura]:
    """(padre, ranura) del bloque ``ident``; padre ``None`` = lista ``programa``."""
    for pos, b in enumerate(modelo.programa):
        if b.id == ident:
            return None, Ranura("lista", "programa", pos)
    for padre in recorrer(modelo.programa):
        for nombre, k, h in padre.hijos():
            if h.id == ident:
                return padre, Ranura("hueco" if k is None else "lista", nombre, k)
    raise ErrorBloques("BLQ.error.bloque_desconocido", id=ident)


def _lista(modelo: ModeloBloques, padre: Bloque | None, parte: str) -> list[Bloque]:
    if padre is None:
        if parte != "programa":
            raise ErrorBloques("BLQ.error.parte", parte=nombre_parte(parte), tipo="programa")
        return modelo.programa
    if parte not in padre.listas:
        raise ErrorBloques(
            "BLQ.error.parte", parte=nombre_parte(parte), tipo=nombre_tipo(padre.tipo)
        )
    return padre.listas[parte]


def _quitar(modelo: ModeloBloques, ident: str) -> Bloque:
    padre, ranura = donde_esta(modelo, ident)
    if ranura.clase == "hueco":
        assert padre is not None
        hijo = padre.huecos[ranura.nombre]
        assert hijo is not None
        padre.huecos[ranura.nombre] = None
        return hijo
    assert ranura.indice is not None
    return _lista(modelo, padre, ranura.nombre).pop(ranura.indice)


def _hueco_libre(ctx: Contexto, nuevo: Bloque, viejo: Bloque) -> str | None:
    """Primer hueco vacío de ``nuevo`` donde ``viejo`` encaja."""
    for h in TIPOS[nuevo.tipo].huecos:
        if (
            nuevo.huecos[h.nombre] is None
            and motivo_rechazo(ctx, viejo, nuevo, Ranura("hueco", h.nombre)) is None
        ):
            return h.nombre
    return None


def _colocar(modelo: ModeloBloques, bloque: Bloque, destino: Destino) -> None:
    """Pone ``bloque`` (ya fuera del modelo, con ids únicos) en ``destino``."""
    padre = None if destino.padre is None else modelo.buscar(destino.padre)
    if padre is not None and destino.parte in padre.huecos:
        ctx = Contexto(modelo)
        err = motivo_rechazo(ctx, bloque, padre, Ranura("hueco", destino.parte))
        if err is not None:
            raise err
        viejo = padre.huecos[destino.parte]
        padre.huecos[destino.parte] = bloque
        if viejo is not None:
            hueco = _hueco_libre(Contexto(modelo), bloque, viejo)
            if hueco is None:
                raise ErrorBloques("BLQ.encaje.ocupado", hueco=nombre_parte(destino.parte))
            bloque.huecos[hueco] = viejo
        return
    lista = _lista(modelo, padre, destino.parte)
    indice = len(lista) if destino.indice is None else destino.indice
    if not 0 <= indice <= len(lista):
        raise ErrorBloques("BLQ.edicion.indice", indice=indice, total=len(lista))
    err = motivo_rechazo(Contexto(modelo), bloque, padre, Ranura("lista", destino.parte, indice))
    if err is not None:
        raise err
    lista.insert(indice, bloque)


def _sin_saltos_nuevos(antes: ModeloBloques, despues: ModeloBloques) -> None:
    """Rechaza la operación si deja un ``romper``/``continuar`` nuevo fuera de lugar."""
    previos = {e.bloque for e in saltos_fuera_de_lugar(antes)}
    for err in saltos_fuera_de_lugar(despues):
        if err.bloque not in previos:
            raise err


# ====================================================================== operaciones


def insertar(modelo: ModeloBloques, bloque: Bloque, destino: Destino) -> ModeloBloques:
    """Inserta ``bloque`` (y su contenido) en ``destino``; los ids repetidos se renuevan."""
    nuevo = copy.deepcopy(modelo)
    bloque = copy.deepcopy(bloque)
    _asignar_ids(nuevo, bloque)
    _colocar(nuevo, bloque, destino)
    _sin_saltos_nuevos(modelo, nuevo)
    return nuevo


def mover(modelo: ModeloBloques, ident: str, destino: Destino) -> ModeloBloques:
    """Lleva el bloque ``ident`` a ``destino`` (nunca dentro de sí mismo).

    En una lista, ``destino.indice`` cuenta ya sin el bloque movido.
    """
    nuevo = copy.deepcopy(modelo)
    bloque = nuevo.buscar(ident)
    if destino.padre is not None and any(b.id == destino.padre for b in recorrer([bloque])):
        raise ErrorBloques("BLQ.encaje.dentro_de_si")
    _quitar(nuevo, ident)
    _colocar(nuevo, bloque, destino)
    _sin_saltos_nuevos(modelo, nuevo)
    return nuevo


def eliminar(modelo: ModeloBloques, ident: str) -> ModeloBloques:
    """Quita el bloque ``ident`` con todo su contenido (un hueco queda vacío)."""
    nuevo = copy.deepcopy(modelo)
    _quitar(nuevo, ident)
    return nuevo


def duplicar(modelo: ModeloBloques, ident: str) -> ModeloBloques:
    """Copia el bloque (con ids nuevos) justo después de él en su lista."""
    padre, ranura = donde_esta(modelo, ident)
    if ranura.clase != "lista":
        raise ErrorBloques("BLQ.edicion.no_en_lista", operacion=_op("duplicar"))
    copia = copy.deepcopy(modelo.buscar(ident))
    for b in recorrer([copia]):
        b.id = ""
    assert ranura.indice is not None
    destino = Destino(None if padre is None else padre.id, ranura.nombre, ranura.indice + 1)
    return insertar(modelo, copia, destino)


def _op(nombre: str) -> Any:
    from .modelo import Etiqueta

    return Etiqueta(f"BLQ.edicion.op.{nombre}")


def envolver(modelo: ModeloBloques, ids: list[str], tipo: str, /, **campos: Any) -> ModeloBloques:
    """Mete los bloques consecutivos ``ids`` en el cuerpo de un bloque nuevo ``tipo``.

    ``tipo`` es un contenedor de instrucciones (``si``, ``mientras``,
    ``para``…); en un ``si`` van a su primera rama. Los huecos del nuevo
    contenedor quedan vacíos para que el estudiante los rellene.
    """
    if not ids:
        raise ErrorBloques("BLQ.edicion.no_consecutivos")
    padre, ranura = donde_esta(modelo, ids[0])
    if ranura.clase != "lista":
        raise ErrorBloques("BLQ.edicion.no_en_lista", operacion=_op("envolver"))
    lista = _lista(modelo, padre, ranura.nombre)
    posicion = {b.id: k for k, b in enumerate(lista)}
    if len(set(ids)) != len(ids) or any(i not in posicion for i in ids):
        raise ErrorBloques("BLQ.edicion.no_consecutivos")
    ks = sorted(posicion[i] for i in ids)
    if ks != list(range(ks[0], ks[0] + len(ks))):
        raise ErrorBloques("BLQ.edicion.no_consecutivos")
    contenedor = nuevo_bloque(tipo, modelo.idioma, **campos)
    cuerpo = contenedor.listas["ramas"][0] if tipo == "si" else contenedor
    if "cuerpo" not in cuerpo.listas or TIPOS[tipo].forma != "c":
        raise ErrorBloques("BLQ.edicion.no_contenedor", tipo=nombre_tipo(tipo))
    nuevo = copy.deepcopy(modelo)
    _asignar_ids(nuevo, contenedor)
    npadre = None if padre is None else nuevo.buscar(padre.id)
    nlista = _lista(nuevo, npadre, ranura.nombre)
    destino = Destino(None if padre is None else padre.id, ranura.nombre, ks[0])
    interior = nlista[ks[0] : ks[-1] + 1]
    del nlista[ks[0] : ks[-1] + 1]
    _colocar(nuevo, contenedor, destino)
    (contenedor.listas["ramas"][0] if tipo == "si" else contenedor).listas["cuerpo"].extend(
        interior
    )
    _sin_saltos_nuevos(modelo, nuevo)
    return nuevo


def editar(modelo: ModeloBloques, ident: str, campo: str, valor: Any) -> ModeloBloques:
    """Cambia un campo del bloque (validado con el lexer real o sus opciones).

    Desactivar una bandera que esconde bloques (``tiene_sino`` con un
    ``sino`` lleno) se rechaza: el estudiante debe vaciar antes esa parte.
    También se rechaza un cambio que haga que el bloque deje de encajar
    donde está (por ejemplo, cambiar ``+`` por ``<`` dentro de un hueco
    numérico).
    """
    nuevo = copy.deepcopy(modelo)
    b = nuevo.buscar(ident)
    desc = TIPOS[b.tipo].campo(campo)
    if desc is None:
        raise ErrorBloques("BLQ.edicion.campo", campo=campo, tipo=nombre_tipo(b.tipo))
    if isinstance(valor, str) and desc.clase != "texto":
        valor = valor.strip()
    err = error_campo(desc, valor)
    if err is not None:
        raise ErrorBloques("BLQ.val.en_campo", bloque=ident, campo=nombre_parte(campo), detalle=err)
    b.campos[campo] = valor
    for e in faltantes(nuevo):
        if e.bloque == ident and e.clave_mensaje == "BLQ.val.parte_oculta":
            raise e
    padre, ranura = donde_esta(nuevo, ident)
    if padre is not None:
        err = motivo_rechazo(nuevo, b, padre, ranura)
        if err is not None:
            raise err
    return nuevo


# ====================================================================== validación


def _todos(modelo: ModeloBloques) -> Iterator[Problema]:
    for e in faltantes(modelo):
        yield Problema(e.bloque, e)
    for e in saltos_fuera_de_lugar(modelo):
        yield Problema(e.bloque, e)
    for e in problemas_de_tipos(modelo):
        yield Problema(e.bloque, e)


def validar(modelo: ModeloBloques) -> list[Problema]:
    """Todos los problemas: estructura, campos, tipos y, si todo eso está bien, compilación.

    Los diagnósticos del compilador se cuelgan del bloque de instrucción
    que generó la línea (mismo id que el nodo del diagrama de flujo) o, si
    no es de ninguna instrucción, de la subrutina o el método.
    """
    problemas = list(_todos(modelo))
    if problemas:
        return problemas
    mf = a_flujo(modelo)
    claves = claves_de_diagramas(modelo)
    for p in flujo.validar(mf):
        if p.nodo is not None:
            problemas.append(Problema(p.nodo, p.error))
        else:
            problemas.append(Problema(claves.get(p.clave or ""), p.error))
    return problemas
