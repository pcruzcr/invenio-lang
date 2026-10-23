"""Genera la gramática TextMate de InvenioLang para VS Code (INV-4240).

``vscode-extension/syntaxes/inveniolang.tmLanguage.json`` colorea los
programas en español y en inglés. Las palabras clave y las funciones
integradas NO se copian a mano: salen del lexer real (``Lexer.keywords``) y
de la tabla bilingüe de ``builtins.py``, agrupadas por el tipo de token. Así
una palabra clave nueva del lenguaje no puede quedar sin color: la prueba
``tests/web/test_vscode.py`` exige que el archivo versionado sea idéntico a
lo que genera este script.

Uso::

    python scripts/gramatica_vscode.py              # reescribe la gramática
    python scripts/gramatica_vscode.py --comprobar  # 1 si está desactualizada
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DESTINO = RAIZ / "vscode-extension" / "syntaxes" / "inveniolang.tmLanguage.json"

# Ámbito TextMate de cada tipo de token del lexer (los temas de VS Code
# colorean estos ámbitos estándar).
AMBITOS: dict[str, str] = {
    "KW_IF": "keyword.control",
    "KW_ELSE": "keyword.control",
    "KW_WHILE": "keyword.control",
    "KW_FOR": "keyword.control",
    "KW_FOREACH": "keyword.control",
    "KW_DO": "keyword.control",
    "KW_SWITCH": "keyword.control",
    "KW_CASE": "keyword.control",
    "KW_DEFAULT": "keyword.control",
    "KW_MATCH": "keyword.control",
    "KW_BREAK": "keyword.control",
    "KW_CONTINUE": "keyword.control",
    "KW_RETURN": "keyword.control",
    "KW_TRY": "keyword.control",
    "KW_CATCH": "keyword.control",
    "KW_IMPORT": "keyword.control.import",
    "KW_INT": "storage.type",
    "KW_FLOAT": "storage.type",
    "KW_STRING": "storage.type",
    "KW_BOOL": "storage.type",
    "KW_VOID": "storage.type",
    "KW_CLASS": "storage.type.class",
    "KW_INTERFACE": "storage.type.interface",
    "KW_ENUM": "storage.type.enum",
    "KW_FUNCION": "storage.type.function",
    "KW_CONSTRUCTOR": "storage.type.function",
    "KW_PUBLIC": "storage.modifier",
    "KW_PRIVATE": "storage.modifier",
    "KW_STATIC": "storage.modifier",
    "KW_ABSTRACT": "storage.modifier",
    "KW_CONST": "storage.modifier",
    "KW_EXTENDS": "storage.modifier.extends",
    "KW_IMPLEMENTS": "storage.modifier.implements",
    "KW_TRUE": "constant.language",
    "KW_FALSE": "constant.language",
    "KW_NULL": "constant.language",
    "KW_THIS": "variable.language",
    "KW_SUPER": "variable.language",
    "KW_NEW": "keyword.operator.new",
    "KW_PRINT": "support.function.io",
    "KW_READ": "support.function.io",
    "KW_MAIN": "entity.name.function.main",
}


def _alternativas(palabras: list[str]) -> str:
    return "|".join(sorted(palabras, key=lambda p: (-len(p), p)))


def gramatica() -> dict:
    """La gramática como ``dict`` (determinista)."""
    from inveniolang.builtins import PARES_BUILT_IN, PARES_ORDEN_SUPERIOR
    from inveniolang.lexer import Lexer

    por_ambito: dict[str, list[str]] = {}
    for lexema, token in Lexer.keywords.items():
        por_ambito.setdefault(AMBITOS[token], []).append(lexema)
    palabras = [
        {"name": f"{ambito}.inveniolang", "match": f"\\b(?:{_alternativas(lista)})\\b"}
        for ambito, lista in sorted(por_ambito.items())
    ]
    integradas = sorted(
        {n for par in (*PARES_BUILT_IN.values(), *PARES_ORDEN_SUPERIOR.values()) for n in par}
    )
    escape = {"name": "constant.character.escape.inveniolang", "match": "\\\\."}
    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "InvenioLang",
        "scopeName": "source.inveniolang",
        "fileTypes": ["inv"],
        "patterns": [
            {"include": "#comentarios"},
            {"include": "#textos"},
            {"include": "#numeros"},
            {"include": "#integradas"},
            {"include": "#palabras"},
            {"include": "#operadores"},
        ],
        "repository": {
            "comentarios": {
                "patterns": [
                    {"name": "comment.line.double-slash.inveniolang", "match": "//.*$"},
                    {"name": "comment.block.inveniolang", "begin": "/\\*", "end": "\\*/"},
                ]
            },
            "textos": {
                "patterns": [
                    {
                        "name": "string.quoted.double.inveniolang",
                        "begin": '"',
                        "end": '"|$',
                        "patterns": [escape],
                    },
                    {
                        "name": "string.quoted.single.inveniolang",
                        "begin": "'",
                        "end": "'|$",
                        "patterns": [escape],
                    },
                ]
            },
            "numeros": {
                "patterns": [
                    {
                        "name": "constant.numeric.inveniolang",
                        "match": "\\b\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b",
                    }
                ]
            },
            "integradas": {
                "patterns": [
                    {
                        "name": "support.function.builtin.inveniolang",
                        "match": f"\\b(?:{_alternativas(integradas)})\\b(?=\\s*\\()",
                    }
                ]
            },
            "palabras": {"patterns": palabras},
            "operadores": {
                "patterns": [
                    {
                        "name": "keyword.operator.inveniolang",
                        "match": "\\?\\.|\\?\\?|\\+\\+|--|[+\\-*/%]=|==|!=|<=|>=|&&|\\|\\||<<|>>|[-+*/%=<>!&|^~?:]",  # noqa: E501 - regex de TextMate
                    }
                ]
            },
        },
    }


def texto() -> str:
    """La gramática como texto JSON estable."""
    return json.dumps(gramatica(), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada; 0 si todo fue bien (o si está al día con --comprobar)."""
    p = argparse.ArgumentParser(description="Genera la gramática TextMate de InvenioLang.")
    p.add_argument("--comprobar", action="store_true", help="1 si el archivo está desactualizado")
    args = p.parse_args(argv)
    nuevo = texto()
    if args.comprobar:
        al_dia = DESTINO.is_file() and DESTINO.read_text(encoding="utf-8") == nuevo
        if not al_dia:
            print(f"desactualizada: {DESTINO}")
        return 0 if al_dia else 1
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(nuevo, encoding="utf-8")
    print(DESTINO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
