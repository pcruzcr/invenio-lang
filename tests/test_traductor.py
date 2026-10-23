"""Traductor de código fuente es <-> en por tokens (INV-1404).

Ida y vuelta sobre TODOS los programas de pruebas/ (y los ejemplos del
currículo): traducir a inglés y volver a español da el mismo programa
(misma secuencia de tokens, mismos comentarios/literales/formato) y la misma
salida; además la vuelta es un punto fijo.
"""

from __future__ import annotations

import glob
import os
import random
import subprocess
import sys
import tempfile

import pytest

from inveniolang.core import CompileRequest, compile_pure
from inveniolang.traductor import tokens_con_posicion, traducir

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRAMAS = sorted(
    glob.glob(os.path.join(RAIZ, "pruebas", "*.inv"))
    + glob.glob(os.path.join(RAIZ, "curriculum", "*", "*.inv"))
)


def _esqueleto(codigo):
    """Texto con cada lexema traducible sustituido por un marcador."""
    tokens, _ = tokens_con_posicion(codigo)
    partes, cursor = [], 0
    for tok in tokens:
        if tok.lexema:
            partes += [codigo[cursor : tok.pos], "\x00"]
            cursor = tok.pos + len(tok.lexema)
    partes.append(codigo[cursor:])
    return "".join(partes)


def _tipos(codigo):
    return [t.tipo for t in tokens_con_posicion(codigo)[0]]


def _ejecutar(codigo, entrada):
    # Cada ejecución en una carpeta vacía propia (archivo_io.inv escribe
    # archivos relativos) y con azar/random deterministas.
    previa = os.getcwd()
    with tempfile.TemporaryDirectory() as carpeta:
        os.chdir(carpeta)
        random.seed(1234)
        try:
            r = compile_pure(CompileRequest("prog.inv", codigo, entrada=entrada))
        finally:
            os.chdir(previa)
    codigos = tuple(e.split("]")[0] for e in r.errores)
    return r.ok, r.salida, codigos


def _entrada_de(ruta):
    # Los ejemplos del currículo con lectura traen su entrada en .input
    previa = ruta[:-4] + ".input"
    if os.path.exists(previa):
        return tuple(open(previa, encoding="utf-8").read().split())
    return ("5", "3", "hola", "2.5", "verdadero") * 4


@pytest.mark.parametrize("ruta", PROGRAMAS, ids=os.path.basename)
def test_ida_y_vuelta(ruta):
    original = open(ruta, encoding="utf-8").read()
    en = traducir(original, "en")
    es = traducir(en, "es")
    # Mismo programa: misma secuencia de tokens y el mismo texto fuera de
    # los lexemas traducidos (comentarios, literales, espacios, saltos).
    assert _tipos(en) == _tipos(original) == _tipos(es)
    assert _esqueleto(en) == _esqueleto(original) == _esqueleto(es)
    # Punto fijo: volver a traducir no cambia nada.
    assert traducir(es, "en") == en and traducir(en, "es") == es
    assert traducir(en, "en") == en and traducir(es, "es") == es
    # Misma salida (o los mismos códigos de error).
    entrada = _entrada_de(ruta)
    assert _ejecutar(en, entrada) == _ejecutar(original, entrada) == _ejecutar(es, entrada)


def test_el_ingles_no_contiene_palabras_clave_en_espanol():
    original = open(os.path.join(RAIZ, "pruebas", "poo_completo.inv"), encoding="utf-8").read()
    en = traducir(original, "en")
    palabras = {t.lexema for t in tokens_con_posicion(en)[0] if t.tipo.startswith("KW_")}
    assert palabras.isdisjoint({"clase", "publico", "retornar", "imprimir", "nuevo", "abstracta"})
    assert "abstract class Figura" in en and "public abstract float area()" in en
    es = traducir(en, "es")
    assert "abstracta clase Figura" in es and "publico abstracto real area()" in es


def test_conserva_comentarios_textos_y_formato():
    codigo = (
        "// si mientras para: comentario\n"
        "void main() {\n"
        '    /* imprimir\n  si */\timprimir("si y mientras");   // fin\n'
        '    entero n = longitud_texto("para");\n'
        "}\n"
    )
    en = traducir(codigo, "en")
    assert en == (
        "// si mientras para: comentario\n"
        "void main() {\n"
        '    /* imprimir\n  si */\tprint("si y mientras");   // fin\n'
        '    int n = text_length("para");\n'
        "}\n"
    )


def test_metodos_del_estudiante_con_nombre_de_builtin_no_se_tocan():
    codigo = (
        'clase A { publico texto trim() { retornar recortar(" a "); } }\n'
        'void main() { A a = nuevo A(); imprimir(a.trim()); imprimir(trim(" b ")); }\n'
    )
    en = traducir(codigo, "en")
    assert 'public string trim() { return trim(" a "); }' in en
    assert 'print(a.trim()); print(trim(" b "));' in en
    assert traducir(en, "es").count("recortar(") == 2
    assert _ejecutar(en, ()) == _ejecutar(codigo, ())


def test_campos_de_la_excepcion_solo_dentro_del_capturar():
    codigo = (
        "clase Aviso { publico texto mensaje; }\n"
        "void main() {\n"
        '    Aviso e = nuevo Aviso(); e.mensaje = "x";\n'
        "    intentar { entero z = 1 / 0; } capturar (e) { imprimir(e.mensaje); }\n"
        "    imprimir(e.mensaje);\n"
        "}\n"
    )
    en = traducir(codigo, "en")
    assert "catch (e) { print(e.message); }" in en
    assert en.count("e.mensaje") == 2  # el campo del objeto del estudiante
    assert _ejecutar(en, ()) == _ejecutar(codigo, ())


def test_cli_traducir(tmp_path):
    origen = tmp_path / "hola.inv"
    origen.write_text('// saludo\nvoid main() { imprimir("hola"); }\n', encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=RAIZ)
    r = subprocess.run(
        [sys.executable, "-m", "inveniolang.cli", "traducir", str(origen), "--a", "en"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )
    assert r.returncode == 0 and r.stdout == '// saludo\nvoid main() { print("hola"); }\n'
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "inveniolang.cli",
            "traducir",
            str(origen),
            "--a",
            "en",
            "--salida",
            "hola_en.inv",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=tmp_path,
        timeout=60,
    )
    assert r.returncode == 0 and (tmp_path / "hola_en.inv").read_text().startswith("// saludo")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "inveniolang.cli",
            "traducir",
            str(origen),
            "--a",
            "en",
            "--salida",
            "../fuera.inv",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=tmp_path,
        timeout=60,
    )
    assert r.returncode == 1 and not (tmp_path.parent / "fuera.inv").exists()


def test_cli_traducir_reporta_errores_lexicos(tmp_path):
    origen = tmp_path / "malo.inv"
    origen.write_text("void main() { entero x = 1 @ 2; }\n", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=RAIZ)
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "inveniolang.cli",
            "traducir",
            str(origen),
            "--a",
            "en",
            "--idioma",
            "en",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )
    assert r.returncode == 1 and "IL-LEX-002" in r.stdout and "LEXICAL ERRORS" in r.stdout
