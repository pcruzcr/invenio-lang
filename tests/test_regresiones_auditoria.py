# test_regresiones_auditoria.py — Regresiones de la auditoría 2026-10
#
# Cada prueba falla con el código anterior a la corrección que documenta y
# pasa con el actual. Se agrupan por componente.
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang import api, builtins, ir
from inveniolang.core import CompileRequest, compile_pure
from inveniolang.errors import ErrorManager
from inveniolang.lexer import Lexer
from inveniolang.parser import Parser
from inveniolang.semantic import SemanticAnalyzer
from inveniolang.type_checker import TypeChecker

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ast(codigo):
    em = ErrorManager()
    ast, _ = Parser(Lexer(em), em).analizar(codigo, "t.inv")
    assert ast is not None, [e.formato_oficial() for e in em.errores]
    tabla = SemanticAnalyzer(em).analizar(ast)
    TypeChecker(em, tabla).verificar(ast)
    assert not em.hay_errores(), [e.formato_oficial() for e in em.errores]
    return ast


def _correr_ir(codigo, optimizado=False):
    subrutinas, globales = ir.generar_programa(_ast(codigo))
    if optimizado:
        globales, _ = ir.optimizar(globales)
        subrutinas, _ = ir.optimizar_programa(subrutinas)
    return "".join(ir.MaquinaTAC(subrutinas, globales).ejecutar())


def _correr_arbol(codigo):
    r = api.ejecutar(codigo)
    assert r.ok, r.errores
    return "".join(r.salida)


def _paridad(codigo):
    """El intérprete de árbol, --run-ir y --run-ir-opt deben coincidir."""
    esperado = _correr_arbol(codigo)
    assert _correr_ir(codigo) == esperado
    assert _correr_ir(codigo, optimizado=True) == esperado
    return esperado


# ---------------------------------------------------------------- IR / TAC


def test_ir_operadores_bit_a_bit():
    """`&|^<<>>` no estaban en MaquinaTAC ("operación de IR no soportada")."""
    s = _paridad(
        "void main() { int a = 12; int b = 10;"
        ' imprimir(a & b); imprimir(" "); imprimir(a | b); imprimir(" ");'
        ' imprimir(a ^ b); imprimir(" "); imprimir(a << 2); imprimir(" "); imprimir(a >> 1); }'
    )
    assert s == "8 14 6 48 6"


def test_ir_complemento_bits_no_es_negacion_logica():
    """`~x` se traducía a `not` y daba `false` en vez de `-x-1`."""
    assert _paridad("void main() { int a = 5; imprimir(~a); }") == "-6"


def test_ir_variable_global_con_prefijo_t_sobrevive_optimizacion():
    """La DCE trataba `tam`/`total` como temporales y borraba su inicialización."""
    codigo = "int tam = 7; int total = 3;" " void main() { imprimir(tam + total); }"
    assert _paridad(codigo) == "10"


def test_ir_matriz_global_indexada_desde_funcion():
    """`_reiniciar` olvidaba las columnas de las matrices globales (usaba 10)."""
    codigo = (
        "int [4][3] m;"
        " void poner(int f, int c, int v) { m[f][c] = v; }"
        " void main() { poner(3, 2, 9); poner(1, 0, 4); imprimir(m[3][2] + m[1][0]); }"
    )
    assert _paridad(codigo) == "13"


def test_ir_matriz_con_dimension_constante_y_parametro():
    """Dimensiones con nombre y parámetros `int [][]` ya no asumen 10 columnas."""
    codigo = (
        "const int F = 2; const int C = 4;"
        " int suma(int [][] m, int f, int c) { int s = 0;"
        "  para (int i = 0; i < f; i++) { para (int j = 0; j < c; j++) { s = s + m[i][j]; } }"
        "  return s; }"
        " void main() { int [F][C] x;"
        "  para (int i = 0; i < F; i++) { para (int j = 0; j < C; j++) { x[i][j] = i * 10 + j; } }"
        "  imprimir(suma(x, F, C)); }"
    )
    assert _paridad(codigo) == "52"


def test_ir_variable_local_sombrea_global():
    """Una declaración local escribía sobre la global homónima."""
    codigo = (
        "int x = 1;" " void f() { int x = 50; x = x + 1; }" " void main() { f(); imprimir(x); }"
    )
    assert _paridad(codigo) == "1"


def test_ir_temporales_no_se_comparten_entre_llamadas_recursivas():
    """Los temporales de las globales quedaban en `globales` y las recursiones los pisaban."""
    codigo = (
        "int base = 1 + 1 + 1 + 1 + 1;"
        " int f(int n) { si (n <= 0) { return 0; } return (n * 1) + f(n - 1); }"
        " void main() { imprimir(f(base)); }"
    )
    assert _paridad(codigo) == "15"


def test_ir_plegado_no_propaga_global_a_traves_de_llamada():
    """Tras un `call`, una global pudo cambiar: no se puede seguir plegando su valor."""
    codigo = (
        "int g = 0;" " void inc() { g = g + 5; }" " void main() { g = 1; inc(); imprimir(g + 1); }"
    )
    assert _paridad(codigo) == "7"


def test_ir_recursion_de_cola_intercambio_de_parametros():
    """TCO copiaba los parámetros en secuencia: `f(b, a)` perdía el valor de `a`."""
    codigo = (
        "int f(int a, int b, int n) { si (n == 0) { return a * 10 + b; } return f(b, a, n - 1); }"
        " void main() { imprimir(f(1, 2, 1)); }"
    )
    assert _paridad(codigo) == "21"


@pytest.mark.parametrize("nombre", ["monticulo.inv", "arbol_b.inv", "bit_a_bit.inv", "trie.inv"])
def test_ir_programas_de_pruebas_paridad(nombre):
    """Programas reales que antes fallaban o divergían bajo --run-ir(-opt)."""
    with open(os.path.join(RAIZ, "pruebas", nombre), encoding="utf-8") as f:
        _paridad(f.read())


# ------------------------------------------------------- builtins / rutas


@pytest.mark.parametrize(
    "ruta",
    ["datos:oculto.txt", "CON.txt", "nul.log", "a*.txt", "x?.csv", "fin.txt.", "tab\t.txt"],
)
def test_builtins_rechaza_rutas_peligrosas(ruta):
    """Antes solo security.py (no usado en ejecución) rechazaba estos casos."""
    with pytest.raises(builtins.BuiltInError):
        builtins._validar_ruta(ruta)


def test_builtins_acepta_ruta_relativa_normal():
    """Una ruta relativa corriente sigue siendo válida."""
    assert builtins._validar_ruta("salida/notas.txt") == "salida/notas.txt"


# ------------------------------------------------------------- núcleo


def test_modo_tokens_no_exige_programa_valido():
    """Los tokens de un programa con error de tipos también se pueden ver."""
    r = compile_pure(CompileRequest("t.inv", 'void main() { int x = "a"; }', modo="tokens"))
    assert r.ok and r.salida


def test_modo_ast_no_ejecuta_el_programa():
    """El modo ast devuelve el árbol en vez de ejecutar."""
    r = compile_pure(CompileRequest("t.inv", "void main() { imprimir(42); }", modo="ast"))
    assert r.ok
    assert r.salida[0].startswith("Program(")


def test_modo_desconocido_se_rechaza():
    """Un modo desconocido ya no cae en la ejecución."""
    with pytest.raises(ValueError):
        CompileRequest("t.inv", "void main() { }", modo="ejecutar-todo")


def test_version_unica():
    """La versión sale de una sola fuente."""
    import inveniolang
    from inveniolang import sbom
    from inveniolang.cli import _VERSION
    from inveniolang.config import Config
    from inveniolang.core import COMPILER_VERSION

    v = inveniolang.__version__
    assert v == _VERSION == Config().compiler_version == COMPILER_VERSION
    assert sbom.generar_sbom()["version"] == v if hasattr(sbom, "generar_sbom") else True


def test_limites_vienen_de_config():
    """Los límites de ejecución salen de config.py."""
    from inveniolang import security
    from inveniolang.config import DEFAULT_CONFIG
    from inveniolang.interpreter import Interpreter

    assert security.MAX_RECURSION == DEFAULT_CONFIG.max_recursion == Interpreter.MAX_RECURSION
    assert builtins._MAX_ARCHIVO_BYTES == DEFAULT_CONFIG.max_archivo_builtin


def test_ssa_real_una_definicion_por_version_y_no_muta_el_tac():
    """INV-1016: SSA de verdad (φ con variables + renombrado), sin mutar el TAC.

    Antes `to_ssa` solo anteponía el texto "phi(a, b)" a los bloques con dos
    predecesores, sin variables ni versiones.
    """
    from inveniolang.core import analizar_fuente
    from inveniolang.ir_ssa import a_ssa

    codigo = (
        "int suma(int n) { int s = 0; int i = 0; "
        "mientras (i < n) { s = s + i; i = i + 1; } retornar s; } "
        "void main() { imprimir(suma(4)); }"
    )
    tac = ir.generar_programa(analizar_fuente(codigo).ast)[0]["suma"][1]
    antes = [repr(i) for i in tac]
    ssa = a_ssa(tac)
    assert [repr(i) for i in tac] == antes
    phis = {p.variable: p for b in ssa.phis.values() for p in b}
    assert set(phis) == {"s", "i"}
    assert sorted(phis["s"].argumentos.values()) == ["s_1", "s_3"]
    definidas = [ln.split(" = ")[0].strip() for b in ssa.instrs.values() for ln in b if " = " in ln]
    assert len(definidas) == len(set(definidas))


def test_plagio_archivos_vacios_no_son_identicos():
    """Dos entregas vacías no cuentan como plagio."""
    from inveniolang.plagiarism import plagiarism_score

    assert plagiarism_score("", "") == 0.0
    assert plagiarism_score("// solo comentario", "") == 0.0


def test_paquete_gui_no_arrastra_gui_qt():
    """INV-1005: `inveniolang.gui` solo expone temas y no importa la ventana Qt.

    Antes reexportaba MainWindow/CodeEditor desde gui_qt, que a su vez importa
    gui.theme: el ciclo dejaba los nombres en None según el orden de import.
    """
    import subprocess

    codigo = (
        "import sys, inveniolang.gui as g; "
        "assert g.TEMA_ALTO_CONTRASTE['fondo'] == '#000000'; "
        "print('inveniolang.gui_qt' in sys.modules)"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "False"


def test_audit_script_importable_sin_efectos():
    """_audit.py corría (y bloqueaba en input()) al importarse."""
    import importlib

    sys.path.insert(0, RAIZ)
    mod = importlib.import_module("_audit")
    assert callable(mod.main)
    assert mod.errores == []


# ------------------------------------------------- código objetivo (ISA)


@pytest.mark.parametrize("nombre", ["hanoi.inv", "bit_a_bit.inv", "funciones.inv", "ciclos.inv"])
@pytest.mark.parametrize("k", [None, 4])
def test_objetivo_paridad_con_tac(nombre, k):
    """`LOAD 1` buscaba una variable llamada 1; globales y parámetros mal asignados a registros."""
    with open(os.path.join(RAIZ, "pruebas", nombre), encoding="utf-8") as f:
        subrutinas, globales = ir.generar_programa(_ast(f.read()))
    entrada = ["5", "3", "2", "1", "4"]
    esperado = "".join(ir.MaquinaTAC(subrutinas, globales).ejecutar(entrada))
    objetivo, _ = ir.generar_objetivo_programa(subrutinas, k_registros=k)
    assert "".join(ir.MaquinaObjetivo(objetivo, globales).ejecutar(entrada)) == esperado


def test_metodo_sin_cuerpo_ni_abstracto_es_error_no_excepcion():
    """semantic.py caía con AttributeError al visitar un método sin cuerpo."""
    codigo = (
        "abstracta clase A { publico texto s(); }"
        ' clase B hereda A { publico texto s() { return "b"; } }'
        " void main() { }"
    )
    r = api.compilar(codigo)
    assert not r.ok
    assert any("IL-POO-022" in e for e in r.errores)
