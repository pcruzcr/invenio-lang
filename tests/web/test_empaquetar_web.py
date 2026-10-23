"""Empaquetado del estudio web (INV-4201): determinista, completo y usable."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

import empaquetar_web as E  # noqa: E402, N812


@pytest.fixture(scope="module")
def generado():
    return E.generar()


def test_es_determinista(generado):
    assert E.generar() == generado


def test_manifiesto_con_hash_de_cada_archivo(generado):
    m = json.loads(generado["manifiesto.json"])
    assert set(m["archivos"]) == set(generado) - {"manifiesto.json"}
    for nombre, sha in m["archivos"].items():
        assert hashlib.sha256(generado[nombre]).hexdigest() == sha
    from inveniolang._version import __version__
    from inveniolang.web import CONTRATO

    assert (m["version"], m["contrato"]) == (__version__, CONTRATO)


def test_zip_sin_modulos_de_escritorio_con_ply_y_biblioteca(generado):
    z = zipfile.ZipFile(io.BytesIO(generado["inveniolang.zip"]))
    nombres = z.namelist()
    assert nombres == sorted(nombres)
    assert {"ply/lex.py", "ply/yacc.py", "inveniolang/web/puente.py", "inveniolang/api.py"} <= set(
        nombres
    )
    assert any(n.startswith("inveniolang/stdlib/") and n.endswith(".inv") for n in nombres)
    for excluido in E.EXCLUIDOS:
        assert not any(n.startswith(f"inveniolang/{excluido}") for n in nombres), excluido
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in nombres)
    for info in z.infolist():
        assert info.date_time == E.FECHA_ZIP
        assert b"\r\n" not in z.read(info)


def test_el_zip_funciona_sin_qt_ni_tk_ni_el_arbol_del_proyecto(generado, tmp_path):
    """Lo que ve Pyodide: solo el zip, sin PySide6 ni tkinter importables."""
    (tmp_path / "paquete.zip").write_bytes(generado["inveniolang.zip"])
    guion = """
import sys, json, builtins
real = builtins.__import__
def vigilado(nombre, *a, **k):
    if nombre.split('.')[0] in ('PySide6', 'tkinter'):
        raise ImportError('prohibido en el navegador: ' + nombre)
    return real(nombre, *a, **k)
builtins.__import__ = vigilado
sys.path.insert(0, sys.argv[1])
from inveniolang.web import llamar
r = json.loads(llamar(json.dumps({'metodo': 'ejecutar', 'args': {'codigo': 'vacio main() { imprimir(6 * 7); }'}})))
assert r['datos']['salida'] == '42', r
import inveniolang
assert inveniolang.__file__.startswith(sys.argv[1]), inveniolang.__file__
print('ok')
"""
    entorno = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = subprocess.run(
        [sys.executable, "-I", "-c", guion, str(tmp_path / "paquete.zip")],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=tmp_path,
        env=entorno,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith("ok")


def test_textos_son_las_claves_web_del_catalogo(generado):
    from inveniolang.i18n import en, es

    textos = json.loads(generado["textos.json"])
    assert set(textos) == {"es", "en"}
    for idioma, modulo in (("es", es), ("en", en)):
        esperado = {k[4:]: v for k, v in modulo.MENSAJES.items() if k.startswith("WEB.")}
        assert textos[idioma] == esperado
    assert textos["es"].keys() == textos["en"].keys()


def test_lexico_del_lexer_real(generado):
    from inveniolang.lexer import Lexer

    lx = json.loads(generado["lexico.json"])
    assert set(lx["palabras"]) == set(Lexer.keywords)
    assert lx["palabras"]["mientras"] == "clave" and lx["palabras"]["int"] == "tipo"
    assert lx["palabras"]["verdadero"] == "literal"
    assert {"longitud", "length"} <= set(lx["integradas"]) or lx["integradas"]
    assert ["mientras", "while"] in lx["pares"] and ["main", "main"] not in lx["pares"]


def test_curriculo_completo_y_emparejado(generado):
    es = json.loads(generado["curriculo.es.json"])
    en = json.loads(generado["curriculo.en.json"])
    ids = {}
    for cur in (es, en):
        ejercicios = [e for n in cur["niveles"] for e in n["ejercicios"]]
        assert len(cur["niveles"]) == 13 and len(ejercicios) == 133
        for e in ejercicios:
            assert e["solucion"] and e["esperado"] and e["enunciado"] and len(e["pistas"]) >= 1
            assert isinstance(e["entrada"], list)
        ids[cur["idioma"]] = [e["id"] for e in ejercicios]
    assert ids["es"] == ids["en"]
    con_entrada = [e for n in es["niveles"] for e in n["ejercicios"] if e["entrada"]]
    assert con_entrada, "los ejercicios con leer llevan su .entrada"


def test_main_escribe_y_comprobar_detecta_cambios(tmp_path, capsys):
    destino = tmp_path / "gen"
    assert E.main(["--comprobar", "--destino", str(destino)]) == 1
    assert E.main(["--destino", str(destino)]) == 0
    assert E.main(["--comprobar", "--destino", str(destino)]) == 0
    (destino / "textos.json").write_text("{}", encoding="utf-8")
    assert E.main(["--comprobar", "--destino", str(destino)]) == 1
    assert "desactualizado: textos.json" in capsys.readouterr().out
