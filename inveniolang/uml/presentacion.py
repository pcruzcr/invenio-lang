"""Cómo se escribe cada pieza del modelo en español o en inglés.

INV-3203: el modelo guarda los tipos en forma canónica (``int``, ``bool``…);
el estudiante debe verlos con las palabras de su idioma (``entero``,
``logico`` / ``int``, ``bool``), las mismas que escribe en el código. Las
palabras salen de la tabla bilingüe del traductor (``traductor.PALABRAS_CLAVE``)
para que diagrama, código generado y traductor nunca discrepen.
"""

from __future__ import annotations

import json

from ..traductor import PALABRAS_CLAVE
from .modelo import ValorInicial

__all__ = ["literal_codigo", "palabra", "tipo_visible"]

_TOKEN_TIPO = {
    "int": "KW_INT",
    "float": "KW_FLOAT",
    "string": "KW_STRING",
    "bool": "KW_BOOL",
    "void": "KW_VOID",
}


def palabra(token: str, idioma: str) -> str:
    """Palabra clave del token ``token`` (``KW_CLASS``…) en ``idioma``."""
    es, en = PALABRAS_CLAVE[token]
    return en if idioma == "en" else es


def tipo_visible(tipo: str, idioma: str) -> str:
    """``int[]`` → ``entero[]`` en español; los nombres de clase no cambian."""
    dims = tipo.count("[]")
    base = tipo.replace("[]", "")
    token = _TOKEN_TIPO.get(base)
    return (palabra(token, idioma) if token else base) + "[]" * dims


def _real(v: float) -> str:
    """Real con la forma que acepta el léxico (``d.d`` con exponente opcional)."""
    texto = repr(float(v))
    if "e" in texto and "." not in texto.split("e")[0]:
        mantisa, exponente = texto.split("e")
        texto = f"{mantisa}.0e{exponente}"
    return texto


def _texto(v: str) -> str:
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}
    return '"' + "".join(escapes.get(c, c) for c in v) + '"'


def literal_codigo(valor: ValorInicial, idioma: str) -> str:
    """El literal tal como se escribe en InvenioLang (``verdadero``, ``-2.5``, ``"hola"``)."""
    if valor.tipo == "null":
        return palabra("KW_NULL", idioma)
    if valor.tipo == "bool":
        return palabra("KW_TRUE" if valor.v else "KW_FALSE", idioma)
    if valor.tipo == "string":
        return _texto(str(valor.v))
    if valor.tipo == "float":
        return _real(float(valor.v or 0.0))
    return json.dumps(valor.v)
