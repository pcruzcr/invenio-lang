"""Biblioteca estándar educativa en InvenioLang (INV-1430).

Cada módulo de inveniolang/stdlib se ejercita desde un programa de
tests/stdlib/programas/ con su salida esperada. La versión inglesa de cada
módulo debe ser el mismo programa con nombres traducidos: se comprueba
token a token y ejecutando los mismos programas traducidos al inglés contra
ella.
"""

from __future__ import annotations

import os
import sys

import pytest

from inveniolang.core import CompileRequest, compile_pure
from inveniolang.modulos import RAIZ_STDLIB
from inveniolang.traductor import tokens_con_posicion, traducir

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "stdlib"))
from glosario import IDENTIFICADORES, RUTAS  # noqa: E402

DIR_PROGRAMAS = os.path.join(os.path.dirname(__file__), "stdlib", "programas")
PROGRAMAS = sorted(f[:-4] for f in os.listdir(DIR_PROGRAMAS) if f.endswith(".inv"))
MODULOS = sorted(k for k in RUTAS if "/" in k)


def _ejecutar(ruta, codigo):
    r = compile_pure(CompileRequest(ruta=ruta, codigo=codigo))
    assert r.ok, r.errores
    return "".join(r.salida)


def _a_ingles_con_glosario(codigo):
    """Palabras clave con traductor.py + identificadores y rutas con el glosario."""
    traducido = traducir(codigo, "en")
    tokens, em = tokens_con_posicion(traducido)
    assert not em.hay_errores()
    partes, cursor = [], 0
    for tok in tokens:
        if tok.tipo == "IDENTIFICADOR" and tok.lexema in IDENTIFICADORES:
            partes += [traducido[cursor : tok.pos], IDENTIFICADORES[tok.lexema]]
            cursor = tok.pos + len(tok.lexema)
    partes.append(traducido[cursor:])
    resultado = "".join(partes)
    for es, en in RUTAS.items():
        resultado = resultado.replace(f'"{es}"', f'"{en}"')
    return resultado


def _firma(codigo):
    """Tipos de token + lexemas de identificadores/números; sin textos ni comentarios."""
    em_tokens, em = tokens_con_posicion(codigo)
    assert not em.hay_errores()
    firma = []
    for tok in em_tokens:
        firma.append((tok.tipo, tok.lexema if tok.tipo == "IDENTIFICADOR" else ""))
    return firma


@pytest.mark.parametrize("nombre", PROGRAMAS)
def test_programa_que_usa_la_biblioteca_en_espanol(nombre):
    ruta = os.path.join(DIR_PROGRAMAS, nombre + ".inv")
    esperado = open(os.path.join(DIR_PROGRAMAS, nombre + ".salida"), encoding="utf-8").read()
    assert _ejecutar(ruta, open(ruta, encoding="utf-8").read()) == esperado


@pytest.mark.parametrize("nombre", PROGRAMAS)
def test_mismo_programa_en_ingles_contra_la_biblioteca_inglesa(nombre):
    ruta = os.path.join(DIR_PROGRAMAS, nombre + ".inv")
    esperado = open(os.path.join(DIR_PROGRAMAS, nombre + ".salida"), encoding="utf-8").read()
    en = _a_ingles_con_glosario(open(ruta, encoding="utf-8").read())
    assert 'import "structures/' in en or 'import "algorithms/' in en
    assert _ejecutar(ruta, en) == esperado


@pytest.mark.parametrize("modulo", MODULOS)
def test_version_inglesa_es_el_mismo_programa(modulo):
    es = open(os.path.join(RAIZ_STDLIB, modulo + ".inv"), encoding="utf-8").read()
    en = open(os.path.join(RAIZ_STDLIB, RUTAS[modulo] + ".inv"), encoding="utf-8").read()
    assert _firma(_a_ingles_con_glosario(es)) == _firma(en)


@pytest.mark.parametrize("modulo", MODULOS + [RUTAS[m] for m in MODULOS])
def test_modulo_importable_sin_errores_ni_advertencias(modulo, tmp_path):
    from inveniolang.errors import ErrorManager
    from inveniolang.lexer import Lexer
    from inveniolang.parser import Parser

    principal = tmp_path / "p.inv"
    principal.write_text(f'importar "{modulo}";\nvoid main() {{ }}\n', encoding="utf-8")
    em = ErrorManager()
    ast, _ = Parser(Lexer(em), em).analizar(principal.read_text(), str(principal))
    assert ast is not None and not em.errores and not em.warnings, em.obtener_reportes()


def test_ordenamientos_y_busquedas_tambien_corren_en_el_codigo_intermedio():
    """--run-ir: el enlace de módulos ocurre antes de generar el TAC."""
    from inveniolang import ir
    from inveniolang.errors import ErrorManager
    from inveniolang.lexer import Lexer
    from inveniolang.parser import Parser
    from inveniolang.semantic import SemanticAnalyzer
    from inveniolang.type_checker import TypeChecker

    ruta = os.path.join(DIR_PROGRAMAS, "algoritmos.inv")
    codigo = open(ruta, encoding="utf-8").read()
    em = ErrorManager()
    ast, _ = Parser(Lexer(em), em).analizar(codigo, "algoritmos.inv", ruta_fuente=ruta)
    tabla = SemanticAnalyzer(em).analizar(ast)
    TypeChecker(em, tabla).verificar(ast)
    assert not em.hay_errores()
    subrutinas, globales = ir.generar_programa(ast)
    salida = "".join(ir.MaquinaTAC(subrutinas, globales).ejecutar())
    esperado = open(os.path.join(DIR_PROGRAMAS, "algoritmos.salida"), encoding="utf-8").read()
    assert salida == esperado
