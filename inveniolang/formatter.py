"""Formateador de fuentes InvenioLang: sangría canónica sin tocar los tokens.

INV-1009: la versión anterior (``toolchain/formatter.py``) reescribía el texto
con expresiones regulares sobre TODO el fuente, incluidos literales y
comentarios: ``imprimir("a=b")`` se convertía en ``imprimir("a = b")`` (cambia
la salida del programa) y nadie la invocaba. Esta versión solo reorganiza el
espacio en blanco *entre* líneas:

* sangría de 4 espacios por nivel de llaves (las llaves dentro de cadenas y
  comentarios no cuentan; una línea que empieza con ``}`` baja un nivel);
* sin espacios al final de línea, como mucho una línea en blanco seguida y un
  único salto de línea final;
* el interior de un comentario ``/* ... */`` multilínea se respeta tal cual.

Como no altera ningún token, el programa formateado es léxicamente idéntico al
original (las pruebas lo comprueban sobre todos los ``pruebas/*.inv``) y
``formatear(formatear(x)) == formatear(x)``.
"""

from __future__ import annotations

__all__ = ["formatear"]

_SANGRIA = "    "


def _balance(linea: str, en_bloque: bool) -> tuple[int, bool]:
    """Variación de profundidad de llaves en ``linea`` y si termina dentro de ``/* */``."""
    delta = 0
    i = 0
    comilla = ""
    while i < len(linea):
        c = linea[i]
        if en_bloque:
            if linea.startswith("*/", i):
                en_bloque = False
                i += 1
        elif comilla:
            if c == "\\":
                i += 1
            elif c == comilla:
                comilla = ""
        elif linea.startswith("//", i):
            break
        elif linea.startswith("/*", i):
            en_bloque = True
            i += 1
        elif c in "\"'":
            comilla = c
        elif c == "{":
            delta += 1
        elif c == "}":
            delta -= 1
        i += 1
    return delta, en_bloque


def formatear(codigo: str) -> str:
    """Devuelve ``codigo`` con sangría canónica; nunca modifica tokens."""
    salida: list[str] = []
    profundidad = 0
    en_bloque = False
    blancos = 0
    for cruda in codigo.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if en_bloque:
            # Interior de un comentario de bloque: se conserva literal.
            salida.append(cruda.rstrip())
            delta, en_bloque = _balance(cruda, True)
            profundidad = max(0, profundidad + delta)
            continue
        linea = cruda.strip()
        if not linea:
            blancos += 1
            continue
        if salida and blancos:
            salida.append("")
        blancos = 0
        cierres = len(linea) - len(linea.lstrip("}"))
        nivel = max(0, profundidad - cierres)
        salida.append(_SANGRIA * nivel + linea)
        delta, en_bloque = _balance(linea, False)
        profundidad = max(0, profundidad + delta)
    return "\n".join(salida) + "\n" if salida else ""
