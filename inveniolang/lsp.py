"""Servidor LSP (Language Server Protocol) de InvenioLang sobre stdio.

Uso: ``python -m inveniolang.lsp`` (lo lanza el cliente del editor). Ofrece
diagnósticos ``[IL-XXX-NNN]`` con la sugerencia de ``error_explainer``,
hover sobre códigos de error y autocompletado de palabras clave y built-ins.

INV-1023: ``main()`` leía JSON línea a línea, pero el protocolo LSP enmarca
cada mensaje con ``Content-Length`` (ningún cliente real hablaba con él), y
solo atendía ``didOpen``; el despachador completo ``manejar_mensaje`` y el
lector con marcos ``leer_mensajes`` existían pero nada los usaba. Ahora el
servidor lee y escribe marcos LSP reales de forma incremental, despacha todos
los métodos y termina con ``exit``. El análisis pasa por la fachada del núcleo.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from typing import IO, Any

from .core import analizar_fuente
from .error_explainer import explicar, explicar_mensaje

__all__ = [
    "completion_for",
    "diagnostics_for",
    "hover_for",
    "leer_mensajes",
    "main",
    "manejar_mensaje",
]


def diagnostics_for(uri: str, text: str) -> list[dict[str, Any]]:
    """Diagnósticos LSP (errores y advertencias) del documento."""
    em = analizar_fuente(text, uri).errores
    diags = []
    for severidad, lista in ((1, em.errores), (2, em.warnings)):
        for e in lista:
            exp = explicar(e.codigo)
            linea, col = max(e.linea - 1, 0), max(e.columna - 1, 0)
            diags.append(
                {
                    "range": {
                        "start": {"line": linea, "character": col},
                        "end": {"line": linea, "character": col + 1},
                    },
                    "severity": severidad,
                    "code": e.codigo,
                    "source": "inveniolang",
                    "message": e.mensaje + (f"\n💡 {exp.fix}" if exp else ""),
                    "data": {"mensaje": e.mensaje},
                }
            )
    return diags


def hover_for(word: str) -> str:
    """Texto para hover LSP."""
    exp = explicar(word)
    if exp:
        return f"**{exp.codigo} {exp.titulo}**\n{exp.por_que}\n`{exp.ejemplo_bueno}`"
    return ""


def leer_mensajes(stream: IO[bytes]) -> Iterator[dict[str, Any]]:
    """Lee mensajes LSP enmarcados (``Content-Length``) de un flujo binario, uno a uno."""
    while True:
        largo = None
        while True:
            cabecera = stream.readline()
            if not cabecera:
                return  # fin del flujo
            cabecera = cabecera.strip()
            if not cabecera:
                break
            nombre, _, valor = cabecera.decode("ascii", "replace").partition(":")
            if nombre.strip().lower() == "content-length":
                largo = int(valor.strip())
        if largo is None:
            continue
        cuerpo = stream.read(largo)
        try:
            yield json.loads(cuerpo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue  # marco corrupto: se descarta y el servidor sigue


def _escribir(stream: IO[bytes], mensaje: dict[str, Any]) -> None:
    cuerpo = json.dumps(mensaje, ensure_ascii=False).encode("utf-8")
    stream.write(b"Content-Length: " + str(len(cuerpo)).encode() + b"\r\n\r\n" + cuerpo)
    stream.flush()


def completion_for(prefijo: str) -> list[dict[str, Any]]:
    """Autocompletado a partir de palabras clave y built-ins."""
    from . import builtins as _bi
    from .lexer import Lexer

    cands: set[str] = set(Lexer.keywords.keys()) | set(_bi.FUNCIONES_BUILT_IN.keys())
    pref = (prefijo or "").lower()
    return [{"label": c} for c in sorted(cands) if c.startswith(pref)][:50]


def _hover_en(texto: str, posicion: dict[str, Any]) -> str:
    """Texto de hover en ``posicion``.

    Si el cursor está sobre una línea con diagnóstico, su explicación completa
    (porqué, ejemplo malo/bueno y arreglo, en el idioma actual); si no, la del
    código IL-XXX-NNN bajo el cursor (p. ej. escrito en un comentario).
    """
    n = int(posicion.get("line", 0))
    for diag in diagnostics_for("<hover>", texto):
        inicio = diag["range"]["start"]
        if inicio["line"] == n:
            return explicar_mensaje(
                str(diag["code"]), diag["data"]["mensaje"], n + 1, inicio["character"] + 1
            )
    lineas = texto.splitlines()
    if not 0 <= n < len(lineas):
        return ""
    linea, col = lineas[n], int(posicion.get("character", 0))
    ini = fin = min(col, len(linea))
    while ini > 0 and (linea[ini - 1].isalnum() or linea[ini - 1] in "_-"):
        ini -= 1
    while fin < len(linea) and (linea[fin].isalnum() or linea[fin] in "_-"):
        fin += 1
    return hover_for(linea[ini:fin])


def _palabra_previa(texto: str, posicion: dict[str, Any]) -> str:
    """Identificador que el usuario está escribiendo justo antes del cursor."""
    lineas = texto.splitlines()
    n = int(posicion.get("line", 0))
    if not 0 <= n < len(lineas):
        return ""
    antes = lineas[n][: int(posicion.get("character", 0))]
    i = len(antes)
    while i > 0 and (antes[i - 1].isalnum() or antes[i - 1] == "_"):
        i -= 1
    return antes[i:]


def manejar_mensaje(msg: dict[str, Any], documentos: dict[str, str]) -> list[dict[str, Any]]:
    """Dispatcher puro y testeable. No hace IO."""
    metodo = msg.get("method", "")
    mid = msg.get("id")
    if metodo == "initialize":
        return [
            {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "capabilities": {
                        "textDocumentSync": 1,  # documento completo en cada cambio
                        "hoverProvider": True,
                        "completionProvider": {"triggerCharacters": []},
                    }
                },
            }
        ]
    if metodo == "shutdown":
        return [{"jsonrpc": "2.0", "id": mid, "result": None}]
    if metodo in ("textDocument/didOpen", "textDocument/didChange"):
        doc = msg.get("params", {}).get("textDocument", {})
        uri = msg.get("params", {}).get("uri") or doc.get("uri", "")
        cambios = msg.get("params", {}).get("contentChanges") or []
        texto = cambios[-1].get("text", "") if cambios else doc.get("text", "")
        if uri:
            documentos[uri] = texto
        diags = diagnostics_for(uri or "<memoria>", texto)
        return [
            {
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": diags},
            }
        ]
    if metodo == "textDocument/hover":
        pos = msg.get("params", {}).get("position", {})
        uri = msg.get("params", {}).get("textDocument", {}).get("uri", "")
        return [
            {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"contents": _hover_en(documentos.get(uri, ""), pos)},
            }
        ]
    if metodo == "textDocument/completion":
        params = msg.get("params", {})
        pref = str(params.get("prefijo", "") or "") or _palabra_previa(
            documentos.get(params.get("textDocument", {}).get("uri", ""), ""),
            params.get("position", {}),
        )
        return [{"jsonrpc": "2.0", "id": mid, "result": completion_for(pref)}]
    if mid is not None:
        return [
            {
                "jsonrpc": "2.0",
                "id": mid,
                "error": {"code": -32601, "message": "método no soportado"},
            }
        ]
    return []


def main(entrada: IO[bytes] | None = None, salida: IO[bytes] | None = None) -> int:
    """Bucle del servidor: lee marcos de ``entrada`` y responde en ``salida``."""
    entrada = entrada or sys.stdin.buffer
    salida = salida or sys.stdout.buffer
    documentos: dict[str, str] = {}
    for msg in leer_mensajes(entrada):
        if msg.get("method") == "exit":
            break
        for respuesta in manejar_mensaje(msg, documentos):
            _escribir(salida, respuesta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
