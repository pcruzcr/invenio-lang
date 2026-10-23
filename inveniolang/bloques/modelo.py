"""Modelo de bloques (contrato JSON, versión 1) — INV-4000.

Antes no existía ningún editor de bloques: el diagrama de flujo de la fase 3
guardaba cada caja como **texto** (``"i < n"``), así que no había forma de
arrastrar una expresión dentro de otra ni de comprobar al soltar que una
condición es lógica. Este módulo define el formato que comparten la
conversión código ⇄ bloques, la edición pura, la API, la CLI, la GUI Qt y
el estudio web (equipo WEB, que lee este contrato).

Decisiones:

* El programa de bloques es **el mismo árbol estructurado** que el diagrama
  de flujo (``inveniolang.flujo``): cada instrucción de bloques es un nodo
  del diagrama con el **mismo id** y el mismo anidamiento; lo que cambia es
  que cada texto se descompone en bloques de valor anidables. Por eso el
  diagrama de flujo se obtiene de los bloques (``conversion.a_flujo``) y al
  revés, y la generación de código reutiliza ``flujo.generacion``.
* Forma uniforme de todo bloque: ``id``, ``tipo``, ``linea``, ``campos``
  (datos atómicos), ``huecos`` (un bloque de valor o ``null``) y ``listas``
  (secuencias de bloques). Qué claves lleva cada tipo lo fija el catálogo
  (``catalogo.py``); un JSON con claves de más o de menos se rechaza con la
  ruta exacta del dato. Un hueco ``null`` es un hueco aún vacío (programa
  en construcción): el JSON lo admite y ``edicion.validar`` lo señala.
* Ida y vuelta exacta: ``desde_json(a_json(m)) == m``.

Forma JSON (detalle y catálogo en ``docs/bloques.md``)::

    {"formato": "inveniolang-bloques", "version": 1, "idioma": "es",
     "programa": [BLOQUE, ...]}
    BLOQUE = {"id": "n3", "tipo": "mientras", "linea": 7,
              "campos": {...}, "huecos": {"condicion": BLOQUE | null},
              "listas": {"cuerpo": [BLOQUE, ...]}}
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .. import i18n
from .catalogo import TIPOS, familia_de_lista

__all__ = [
    "FORMATO",
    "VERSION",
    "Bloque",
    "Etiqueta",
    "ErrorBloques",
    "ModeloBloques",
    "a_dict",
    "nombre_parte",
    "nombre_tipo",
    "a_json",
    "bloque_a_dict",
    "desde_dict",
    "desde_json",
    "recorrer",
]

FORMATO = "inveniolang-bloques"
VERSION = 1


class ErrorBloques(ValueError):
    """Error de bloques con mensaje bilingüe del catálogo ``BLQ.*``.

    ``args_mensaje`` puede contener otros ``ErrorBloques`` (o errores del
    diagrama de flujo) que se presentan en el mismo idioma; ``diagnosticos``
    lleva los del compilador si el programa no compila; ``bloque`` es el id
    del bloque culpable, si se conoce.
    """

    def __init__(
        self,
        clave_mensaje: str,
        /,
        diagnosticos: tuple[str, ...] = (),
        bloque: str | None = None,
        **args: Any,
    ):
        self.clave_mensaje = clave_mensaje
        self.args_mensaje = dict(args)
        self.diagnosticos = tuple(diagnosticos)
        self.bloque = bloque
        super().__init__(self.texto())

    def texto(self, idioma: str | None = None) -> str:
        """Mensaje en ``idioma`` (o en el idioma actual del proceso)."""
        args = {
            k: (v.texto(idioma) if hasattr(v, "texto") and callable(v.texto) else v)
            for k, v in self.args_mensaje.items()
        }
        return i18n.t(self.clave_mensaje, idioma, **args)


class Etiqueta:
    """Texto del catálogo que se presenta en el idioma de quien muestra el mensaje.

    Se pasa como argumento de un ``ErrorBloques`` (nombre de un tipo de
    bloque, de un hueco, de una familia de valor) para que el mensaje
    completo salga en un solo idioma.
    """

    def __init__(self, clave: str, **args: Any):
        self.clave = clave
        self.args = args

    def texto(self, idioma: str | None = None) -> str:
        """El texto en ``idioma``."""
        return i18n.t(self.clave, idioma, **self.args)


def nombre_tipo(tipo: str) -> Etiqueta:
    """Nombre traducible de un tipo de bloque."""
    return Etiqueta(f"BLQ.tipo.{tipo}")


def nombre_parte(parte: str) -> Etiqueta:
    """Nombre traducible de un hueco, lista o campo."""
    return Etiqueta(f"BLQ.parte.{parte}")


@dataclass
class Bloque:
    """Un bloque. Las claves válidas de ``campos``/``huecos``/``listas`` las da el catálogo."""

    id: str
    tipo: str
    linea: int = 0
    campos: dict[str, Any] = field(default_factory=dict)
    huecos: dict[str, Bloque | None] = field(default_factory=dict)
    listas: dict[str, list[Bloque]] = field(default_factory=dict)

    def hijos(self) -> Iterator[tuple[str, int | None, Bloque]]:
        """(nombre, posición, hijo): huecos ocupados (posición None) y elementos de listas."""
        for nombre, h in self.huecos.items():
            if h is not None:
                yield nombre, None, h
        for nombre, lista in self.listas.items():
            for k, b in enumerate(lista):
                yield nombre, k, b


@dataclass
class ModeloBloques:
    """Programa completo como bloques (contrato v1)."""

    idioma: str
    programa: list[Bloque] = field(default_factory=list)

    def buscar(self, ident: str) -> Bloque:
        """El bloque ``ident`` (``ErrorBloques`` si no existe)."""
        for b in recorrer(self.programa):
            if b.id == ident:
                return b
        raise ErrorBloques("BLQ.error.bloque_desconocido", id=ident)


def recorrer(bloques: list[Bloque]) -> Iterator[Bloque]:
    """Todos los bloques y sus descendientes, en preorden."""
    for b in bloques:
        yield b
        for _, _, h in b.hijos():
            yield from recorrer([h])


# ====================================================================== JSON


def bloque_a_dict(b: Bloque) -> dict[str, Any]:
    """Un bloque como ``dict`` JSON (claves en el orden del catálogo)."""
    desc = TIPOS[b.tipo]
    return {
        "id": b.id,
        "tipo": b.tipo,
        "linea": b.linea,
        "campos": {c.nombre: b.campos[c.nombre] for c in desc.campos},
        "huecos": {h.nombre: _hueco_a_dict(b.huecos[h.nombre]) for h in desc.huecos},
        "listas": {x.nombre: [bloque_a_dict(y) for y in b.listas[x.nombre]] for x in desc.listas},
    }


def _hueco_a_dict(b: Bloque | None) -> dict[str, Any] | None:
    return None if b is None else bloque_a_dict(b)


def a_dict(modelo: ModeloBloques) -> dict[str, Any]:
    """El modelo como ``dict`` JSON-serializable (contrato v1)."""
    return {
        "formato": FORMATO,
        "version": VERSION,
        "idioma": modelo.idioma,
        "programa": [bloque_a_dict(b) for b in modelo.programa],
    }


def a_json(modelo: ModeloBloques, sangria: int | None = 2) -> str:
    """El modelo como texto JSON (UTF-8 legible, claves en orden estable)."""
    return json.dumps(a_dict(modelo), ensure_ascii=False, indent=sangria)


class _Lector:
    """Convierte ``dict`` en bloques validando cada dato con su ruta."""

    def __init__(self) -> None:
        self.ids: set[str] = set()

    @staticmethod
    def falla(ruta: str, detalle: str, **args: Any) -> ErrorBloques:
        return ErrorBloques("BLQ.error.contrato", ruta=ruta, detalle=ErrorBloques(detalle, **args))

    def objeto(self, dato: Any, ruta: str, claves: tuple[str, ...]) -> dict[str, Any]:
        if not isinstance(dato, dict):
            raise self.falla(ruta, "BLQ.contrato.objeto")
        faltan = [c for c in claves if c not in dato]
        if faltan:
            raise self.falla(ruta, "BLQ.contrato.faltan", claves=", ".join(faltan))
        sobran = sorted(set(dato) - set(claves))
        if sobran:
            raise self.falla(ruta, "BLQ.contrato.sobran", claves=", ".join(sobran))
        return dato

    def bloque(self, dato: Any, ruta: str) -> Bloque:
        d = self.objeto(dato, ruta, ("id", "tipo", "linea", "campos", "huecos", "listas"))
        tipo = d["tipo"]
        if not isinstance(tipo, str) or tipo not in TIPOS:
            raise self.falla(f"{ruta}.tipo", "BLQ.contrato.tipo", valor=str(tipo))
        ident = d["id"]
        if not isinstance(ident, str) or not ident or ident in self.ids:
            raise self.falla(f"{ruta}.id", "BLQ.contrato.id_repetido", id=str(ident))
        self.ids.add(ident)
        linea = d["linea"]
        if not isinstance(linea, int) or isinstance(linea, bool) or linea < 0:
            raise self.falla(f"{ruta}.linea", "BLQ.contrato.entero")
        desc = TIPOS[tipo]
        b = Bloque(ident, tipo, linea)
        campos = self.objeto(d["campos"], f"{ruta}.campos", tuple(c.nombre for c in desc.campos))
        for c in desc.campos:
            valor = campos[c.nombre]
            if c.clase == "bandera":
                if not isinstance(valor, bool):
                    raise self.falla(f"{ruta}.campos.{c.nombre}", "BLQ.contrato.bandera")
            elif not isinstance(valor, str):
                raise self.falla(f"{ruta}.campos.{c.nombre}", "BLQ.contrato.texto")
            b.campos[c.nombre] = valor
        huecos = self.objeto(d["huecos"], f"{ruta}.huecos", tuple(h.nombre for h in desc.huecos))
        for h in desc.huecos:
            sub = huecos[h.nombre]
            rh = f"{ruta}.huecos.{h.nombre}"
            if sub is None:
                b.huecos[h.nombre] = None
                continue
            hijo = self.bloque(sub, rh)
            if TIPOS[hijo.tipo].forma != "valor":
                raise self.falla(rh, "BLQ.contrato.no_valor", tipo=hijo.tipo)
            b.huecos[h.nombre] = hijo
        listas = self.objeto(d["listas"], f"{ruta}.listas", tuple(x.nombre for x in desc.listas))
        for x in desc.listas:
            rl = f"{ruta}.listas.{x.nombre}"
            elementos = listas[x.nombre]
            if not isinstance(elementos, list):
                raise self.falla(rl, "BLQ.contrato.lista")
            hijos = [self.bloque(e, f"{rl}[{k}]") for k, e in enumerate(elementos)]
            for k, hijo in enumerate(hijos):
                if not familia_de_lista(x.acepta, hijo.tipo):
                    raise self.falla(
                        f"{rl}[{k}]", "BLQ.contrato.no_cabe", tipo=hijo.tipo, lista=x.nombre
                    )
            b.listas[x.nombre] = hijos
        return b


def desde_dict(dato: Any) -> ModeloBloques:
    """Reconstruye y valida un modelo; ``ErrorBloques`` con la ruta del dato inválido."""
    lector = _Lector()
    d = lector.objeto(dato, "$", ("formato", "version", "idioma", "programa"))
    if d["formato"] != FORMATO:
        raise lector.falla("$.formato", "BLQ.contrato.formato", formato=FORMATO)
    if d["version"] != VERSION:
        raise lector.falla("$.version", "BLQ.contrato.version", version=str(d["version"]))
    idioma = d["idioma"]
    if idioma not in i18n.IDIOMAS:
        raise lector.falla(
            "$.idioma", "BLQ.contrato.opcion", valor=str(idioma), validas=", ".join(i18n.IDIOMAS)
        )
    if not isinstance(d["programa"], list):
        raise lector.falla("$.programa", "BLQ.contrato.lista")
    programa = []
    for k, e in enumerate(d["programa"]):
        b = lector.bloque(e, f"$.programa[{k}]")
        if not familia_de_lista("definicion", b.tipo):
            raise lector.falla(
                f"$.programa[{k}]", "BLQ.contrato.no_cabe", tipo=b.tipo, lista="programa"
            )
        programa.append(b)
    return ModeloBloques(idioma, programa)


def desde_json(texto: str) -> ModeloBloques:
    """Lee un modelo desde texto JSON (``ErrorBloques`` si no es JSON o no cumple v1)."""
    try:
        dato = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorBloques("BLQ.error.json", detalle=str(e)) from e
    return desde_dict(dato)
