"""Catálogo central de mensajes bilingüe (es/en) de InvenioLang.

INV-1400: antes cada diagnóstico era una cadena en español escrita en el
punto donde se detectaba (≈280 f-strings repartidas en lexer, parser,
semántico, tipos, intérprete, IR y built-ins), así que un estudiante que no
lee español no podía entender ningún error aunque el lenguaje ya aceptara
palabras clave en inglés. Ahora:

* cada mensaje tiene una **clave estable** (``"IL-SEM-003.funcion_no_encontrada"``)
  y una plantilla por idioma en ``es.py`` / ``en.py``;
* el código que detecta el error construye un :class:`Mensaje` diferido con
  :func:`M` (clave + argumentos) y **no** decide el idioma: lo decide quien
  presenta el diagnóstico (``ErrorManager(idioma=...)``, ``--idioma`` del
  CLI, ``compile_pure(..., idioma=...)`` o la variable ``INVENIO_IDIOMA``);
* cada idioma es una *Strategy* (:class:`CatalogoIdioma`) registrada en un
  *Registry* (:class:`RegistroIdiomas`): añadir un tercer idioma es registrar
  un diccionario más, sin tocar ningún analizador.

``tests/test_i18n.py`` comprueba que ningún idioma carece de una clave, que
los marcadores ``{...}`` coinciden entre idiomas y que toda clave usada en el
código existe en el catálogo.
"""

from __future__ import annotations

import os
import string
from collections.abc import Mapping
from typing import Any

from ..patterns import Strategy
from . import en as _en
from . import es as _es

IDIOMAS: tuple[str, ...] = ("es", "en")
IDIOMA_POR_DEFECTO = "es"
VARIABLE_ENTORNO = "INVENIO_IDIOMA"


def normalizar_idioma(valor: str | None, *, estricto: bool = True) -> str:
    """Reduce ``"en_US.UTF-8"``, ``"EN"`` o ``"es-CR"`` a ``"en"``/``"es"``.

    Con ``estricto=True`` un idioma no soportado es ``ValueError`` (lo que
    pide una API o un argumento explícito); con ``estricto=False`` se usa el
    idioma por defecto (lo razonable para una variable de entorno, que no
    debe tumbar el compilador por un valor heredado del sistema).
    """
    if valor is None or not str(valor).strip():
        if estricto:
            raise ValueError("idioma vacío")
        return IDIOMA_POR_DEFECTO
    base = str(valor).strip().lower().replace("-", "_").split(".")[0].split("_")[0]
    if base in IDIOMAS:
        return base
    if estricto:
        raise ValueError(f"idioma no soportado: {valor!r} (válidos: {', '.join(IDIOMAS)})")
    return IDIOMA_POR_DEFECTO


class CatalogoIdioma(Strategy):
    """Strategy de presentación: convierte (clave, argumentos) en texto."""

    def __init__(self, codigo: str, mensajes: Mapping[str, str]):
        self.codigo = codigo
        self.mensajes = dict(mensajes)

    def tiene(self, clave: str) -> bool:
        """Indica si el catálogo define la clave."""
        return clave in self.mensajes

    def execute(self, clave: str, *args: Any, **kwargs: Any) -> str:
        """Formatea la plantilla de ``clave`` con los argumentos con nombre."""
        return self.mensajes[clave].format_map(kwargs)


class RegistroIdiomas:
    """Registry de catálogos por código de idioma."""

    def __init__(self) -> None:
        self._catalogos: dict[str, CatalogoIdioma] = {}

    def registrar(self, catalogo: CatalogoIdioma) -> None:
        """Registra (o reemplaza) el catálogo de un idioma."""
        self._catalogos[catalogo.codigo] = catalogo

    def obtener(self, codigo: str) -> CatalogoIdioma:
        """Catálogo del idioma ``codigo`` (ya normalizado)."""
        return self._catalogos[codigo]

    def idiomas(self) -> tuple[str, ...]:
        """Códigos registrados, en orden de registro."""
        return tuple(self._catalogos)


REGISTRO = RegistroIdiomas()
REGISTRO.registrar(CatalogoIdioma("es", _es.MENSAJES))
REGISTRO.registrar(CatalogoIdioma("en", _en.MENSAJES))

# Idioma fijado explícitamente para todo el proceso (CLI con --idioma). None
# significa "consultar INVENIO_IDIOMA y, si no está, usar el español".
_idioma_proceso: str | None = None


def establecer_idioma(idioma: str | None) -> None:
    """Fija el idioma del proceso (``None`` vuelve a la variable de entorno)."""
    global _idioma_proceso
    _idioma_proceso = normalizar_idioma(idioma) if idioma is not None else None


def idioma_actual() -> str:
    """Idioma efectivo: el fijado con :func:`establecer_idioma` o el de entorno."""
    if _idioma_proceso is not None:
        return _idioma_proceso
    return normalizar_idioma(os.environ.get(VARIABLE_ENTORNO), estricto=False)


def t(clave: str, idioma: str | None = None, **args: Any) -> str:
    """Texto inmediato de ``clave`` en ``idioma`` (o en el idioma actual).

    Si un idioma careciera de la clave (no debería: lo impide la prueba de
    completitud) se usa el español antes que mostrar un hueco al estudiante.
    """
    codigo = normalizar_idioma(idioma) if idioma is not None else idioma_actual()
    catalogo = REGISTRO.obtener(codigo)
    if not catalogo.tiene(clave):
        catalogo = REGISTRO.obtener(IDIOMA_POR_DEFECTO)
    return catalogo.execute(clave, **args)


class Mensaje:
    """Mensaje diferido: clave del catálogo + argumentos, sin idioma fijado.

    Se convierte a texto lo más tarde posible (al registrarse en un
    ``ErrorManager`` o al mostrarse) para que el idioma lo elija quien
    presenta el error y no quien lo detecta.
    """

    __slots__ = ("clave", "args")

    def __init__(self, clave: str, args: Mapping[str, Any] | None = None):
        if clave not in _es.MENSAJES:
            raise KeyError(f"clave de mensaje desconocida: {clave!r}")
        self.clave = clave
        self.args = dict(args or {})

    def texto(self, idioma: str | None = None) -> str:
        """Representación en ``idioma`` (por defecto, el idioma actual)."""
        return t(self.clave, idioma, **self.args)

    def __str__(self) -> str:
        return self.texto()

    def __repr__(self) -> str:
        return f"Mensaje({self.clave!r}, {self.args!r})"

    def __eq__(self, otro: object) -> bool:
        if isinstance(otro, Mensaje):
            return self.clave == otro.clave and self.args == otro.args
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.clave)


def M(clave: str, **args: Any) -> Mensaje:  # noqa: N802 - nombre corto deliberado
    """Construye un :class:`Mensaje` diferido (forma corta usada por los analizadores)."""
    return Mensaje(clave, args)


def texto(mensaje: Any, idioma: str | None = None) -> str:
    """Texto de un ``Mensaje`` o de cualquier otro objeto (``str(obj)``)."""
    if isinstance(mensaje, Mensaje):
        return mensaje.texto(idioma)
    return str(mensaje)


def marcadores(plantilla: str) -> set[str]:
    """Nombres de los marcadores ``{nombre}`` de una plantilla (para pruebas)."""
    return {campo for _, campo, _, _ in string.Formatter().parse(plantilla) if campo}


__all__ = [
    "IDIOMAS",
    "IDIOMA_POR_DEFECTO",
    "VARIABLE_ENTORNO",
    "CatalogoIdioma",
    "M",
    "Mensaje",
    "REGISTRO",
    "RegistroIdiomas",
    "establecer_idioma",
    "idioma_actual",
    "marcadores",
    "normalizar_idioma",
    "t",
    "texto",
]
