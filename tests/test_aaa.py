# test_aaa.py — Puerta AAA+: contrato, config, robustez, determinismo
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang import api
from inveniolang.ast_validator import validar_ast
from inveniolang.config import Config
from inveniolang.core import CompileRequest, compile_pure
from inveniolang.errors import ErrorManager
from inveniolang.lexer import Lexer
from inveniolang.parser import Parser
from inveniolang.symbol_table import SymbolTable


def test_version_unica():
    """Versión única gobernable en config y API."""
    assert Config().compiler_version == "10.0.0"
    r = api.compilar("void main() { }")
    assert r.version == "10.0.0"
    assert r.ok


def test_api_determinista():
    """Misma entrada produce misma salida, distinto run_id."""
    cod = "void main() { imprimir(2+3*4); }"
    a = api.ejecutar(cod)
    b = api.ejecutar(cod)
    assert a.salida == b.salida == ("14",)
    assert a.ok and b.ok
    assert a.run_id != b.run_id  # trazable, salida determinista


def test_config_entorno():
    """Overrides INVE_* para orquestación."""
    os.environ["INVE_MAX_ITERS"] = "123"
    try:
        assert Config.desde_entorno().max_iteraciones == 123
    finally:
        del os.environ["INVE_MAX_ITERS"]


def test_ambito_balanceado():
    """Contextmanager garantiza entrar/salir ámbito."""
    t = SymbolTable()
    n0 = t.profundidad_ambito()
    with t.ambito():
        assert t.profundidad_ambito() == n0 + 1
    assert t.profundidad_ambito() == n0


def test_validador_detecta_ciclo():
    """Validador auditable detecta herencia circular."""
    em = ErrorManager()
    lx = Lexer(em)
    p = Parser(lx, em)
    cod = "clase A hereda B { } clase B hereda A { } void main() { }"
    ast, _ = p.analizar(cod, "t.inv")
    assert ast is not None
    msgs = validar_ast(ast)
    assert any("Ciclo" in m for m in msgs)


def test_error_formato_oficial():
    """Error léxico conserva código oficial IL-LEX-002."""
    r = api.ejecutar("void main() { int x = 5 @ 3; }")
    assert not r.ok
    assert any("IL-LEX-002" in e for e in r.errores)


def test_core_modos():
    """Modos check/tokens del contrato core."""
    base = CompileRequest(ruta="t.inv", codigo="void main() { }", modo="check")
    assert compile_pure(base).ok
    toks = compile_pure(CompileRequest(ruta="t.inv", codigo="void main() { }", modo="tokens"))
    assert toks.ok and len(toks.salida) > 0


def test_for_accion_incdec():
    """Acción ++/-- del for ejecuta sin NameError (rama IncDecNode eliminada)."""
    r = api.ejecutar("void main() { int s = 0; para (int i = 0; i < 3; i++) { s = s + 1; } imprimir(s); }")
    assert r.ok and "".join(r.salida) == "3"
    r2 = api.ejecutar("void main() { int s = 0; para (int i = 3; i > 0; i--) { s = s + 1; } imprimir(s); }")
    assert r2.ok and "".join(r2.salida) == "3"
