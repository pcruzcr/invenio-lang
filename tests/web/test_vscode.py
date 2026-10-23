"""Extensión de VS Code (INV-4240, INV-4241): manifiesto, gramática y textos."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
EXT = RAIZ / "vscode-extension"
sys.path.insert(0, str(RAIZ / "scripts"))

import gramatica_vscode  # noqa: E402


def test_la_gramatica_versionada_es_la_que_genera_el_lexer():
    assert (
        gramatica_vscode.DESTINO.read_text(encoding="utf-8") == gramatica_vscode.texto()
    ), "regenera con: python scripts/gramatica_vscode.py"
    assert gramatica_vscode.main(["--comprobar"]) == 0


def test_toda_palabra_clave_del_lexer_tiene_ambito():
    from inveniolang.lexer import Lexer

    assert set(Lexer.keywords.values()) <= set(gramatica_vscode.AMBITOS)
    g = gramatica_vscode.gramatica()
    texto = json.dumps(g["repository"]["palabras"])
    for lexema in Lexer.keywords:
        assert re.search(rf"[|:]{re.escape(lexema)}[|)]", texto), lexema


def test_manifiesto_coherente_con_el_cliente_y_traducido():
    paquete = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
    assert paquete["main"] == "./extension.js" and (EXT / "extension.js").is_file()
    assert "vscode-languageclient" in paquete["dependencies"]
    gram = paquete["contributes"]["grammars"][0]
    assert (EXT / gram["path"]).is_file() and gram["scopeName"] == "source.inveniolang"
    assert (EXT / paquete["contributes"]["languages"][0]["configuration"]).is_file()
    cliente = (EXT / "extension.js").read_text(encoding="utf-8")
    comandos = [c["command"] for c in paquete["contributes"]["commands"]]
    for c in comandos:
        assert f'"{c}"' in cliente
    claves = set(re.findall(r'"%([a-zA-Z.]+)%"', json.dumps(paquete)))
    for nls in ("package.nls.json", "package.nls.es.json"):
        assert set(json.loads((EXT / nls).read_text(encoding="utf-8"))) == claves, nls
    usados = set(re.findall(r'vscode\.l10n\.t\(\s*"((?:[^"\\]|\\.)*)"', cliente))
    es = json.loads((EXT / "l10n" / "bundle.l10n.es.json").read_text(encoding="utf-8"))
    assert {json.loads(f'"{u}"') for u in usados} == set(es)
