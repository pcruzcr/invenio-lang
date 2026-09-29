# lsp.py — H3.8 Language Server Protocol para InvenioLang
# Reusa lexer.py:9, semantic.py:44, error_explainer.py. Patrones: Facade + Strategy + Observer
# Minimal LSP: textDocument/didOpen → diagnostics, hover, completion.
from __future__ import annotations

import json
import sys
from typing import Any

from .error_explainer import explicar
from .errors import ErrorManager
from .lexer import Lexer
from .parser import Parser
from .semantic import SemanticAnalyzer
from .type_checker import TypeChecker


def diagnostics_for(uri: str, text: str) -> list[dict[str, Any]]:
    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(text, uri)
    if not em.hay_errores():
        p = Parser(lx, em)
        ast, _ = p.analizar(text, uri)
        if ast and not em.hay_errores():
            sem = SemanticAnalyzer(em)
            tabla = sem.analizar(ast)
            if not em.hay_errores():
                TypeChecker(em, tabla).verificar(ast)
    diags = []
    for e in em.errores:
        exp = explicar(e.codigo)
        msg = e.mensaje + (f"\n💡 {exp.fix}" if exp else "")
        diags.append(
            {
                "range": {
                    "start": {"line": e.linea - 1, "character": e.columna - 1},
                    "end": {"line": e.linea - 1, "character": e.columna + 5},
                },
                "severity": 1,
                "code": e.codigo,
                "source": "inveniolang",
                "message": msg,
            }
        )
    return diags


def hover_for(word: str) -> str:
    exp = explicar(word)
    if exp:
        return f"**{exp.codigo} {exp.titulo}**\n{exp.por_que}\n`{exp.ejemplo_bueno}`"
    return ""


# CLI para VS Code extension (stdio JSON-RPC minimal)
def main():
    print(
        "InvenioLang LSP — stdin JSON-RPC (hover/diagnostics). Requiere cliente VS Code.",
        file=sys.stderr,
    )
    for line in sys.stdin:
        try:
            msg = json.loads(line)
            if msg.get("method") == "textDocument/didOpen":
                uri = msg["params"]["textDocument"]["uri"]
                text = msg["params"]["textDocument"]["text"]
                diags = diagnostics_for(uri, text)
                resp = {
                    "jsonrpc": "2.0",
                    "method": "textDocument/publishDiagnostics",
                    "params": {"uri": uri, "diagnostics": diags},
                }
                print(json.dumps(resp))
                sys.stdout.flush()
        except Exception:
            continue


# ---- LSP interoperable: framing Content-Length + dispatcher puro ----
def leer_mensajes(stream) -> Any:
    """Lee mensajes LSP con framing o línea JSON. Generador testeable."""
    buf = b""
    datos = stream.read() if hasattr(stream, "read") else stream
    if isinstance(datos, str):
        datos = datos.encode("utf-8")
    buf += datos or b""
    while buf:
        if buf.startswith(b"Content-Length:"):
            try:
                head, _, resto = buf.partition(b"\r\n\r\n")
                largo = int(head.decode("utf-8").split(":")[1].strip().split(";")[0])
            except Exception:
                return
            if len(resto) < largo:
                return
            cuerpo = resto[:largo]
            buf = resto[largo:]
            try:
                yield json.loads(cuerpo.decode("utf-8"))
            except Exception:
                continue
        else:
            linea, sep, resto = buf.partition(b"\n")
            buf = resto if sep else b""
            linea = linea.strip()
            if not linea:
                continue
            try:
                yield json.loads(linea.decode("utf-8"))
            except Exception:
                continue


def completion_for(prefijo: str) -> list[dict[str, Any]]:
    """Autocompletado localizable a partir de keywords + builtins."""
    try:
        from . import builtins as _bi
        from .lexer import Lexer as _Lx
    except Exception:
        return []
    cands: set[str] = set(_Lx.keywords.keys())
    try:
        cands.update(_bi.FUNCIONES_BUILT_IN.keys())
    except Exception:
        pass
    pref = (prefijo or "").lower()
    return [{"label": c} for c in sorted(cands) if c.startswith(pref)][:50]


def manejar_mensaje(msg: dict[str, Any], documentos: dict[str, str]) -> list[dict[str, Any]]:
    """Dispatcher puro y testeable. No hace IO."""
    metodo = msg.get("method", "")
    mid = msg.get("id")
    if metodo == "initialize":
        return [
            {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"capabilities": {"hoverProvider": True}},
            }
        ]
    if metodo == "shutdown":
        return [{"jsonrpc": "2.0", "id": mid, "result": None}]
    if metodo in ("textDocument/didOpen", "textDocument/didChange"):
        doc = msg.get("params", {}).get("textDocument", {})
        uri = msg.get("params", {}).get("uri") or doc.get("uri", "")
        texto = doc.get("text", "") or msg.get("params", {}).get("text", "")
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
        texto = documentos.get(uri, "")
        try:
            linea = texto.splitlines()[int(pos.get("line", 0))]
            palabra = "".join(c if (c.isalnum() or c == "_") else " " for c in linea)
            toks = [t for t in palabra.split() if t]
            col = int(pos.get("character", 0))
            acc = 0
            objetivo = toks[0] if toks else ""
            for t in toks:
                acc += len(t) + 1
                if col < acc:
                    objetivo = t
                    break
        except Exception:
            objetivo = ""
        return [
            {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"contents": hover_for(objetivo)},
            }
        ]
    if metodo == "textDocument/completion":
        pref = ""
        try:
            pref = str(msg.get("params", {}).get("prefijo", "") or "")
        except Exception:
            pref = ""
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


if __name__ == "__main__":
    main()
