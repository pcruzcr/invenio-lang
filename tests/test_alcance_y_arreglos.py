"""Alcance léxico/de bloque, `+=` en `para` y arreglos dinámicos.

INV-1290: `para (...; i += 2)` asignaba en vez de sumar (ciclo infinito).
INV-1291: una declaración dentro de un bloque tapaba a la global homónima
          también después del bloque (intérprete y --run-ir).
INV-1292: alcance dinámico: una función veía las locales de quien la llama
          (y los tipos de variable eran un dict plano global).
INV-1440: atributos arreglo + `nuevo tipo[n]` (vector dinámico).
"""

from __future__ import annotations

import pytest

from inveniolang import ir
from inveniolang.core import CompileRequest, compile_pure
from inveniolang.errors import ErrorManager
from inveniolang.lexer import Lexer
from inveniolang.parser import Parser
from inveniolang.semantic import SemanticAnalyzer
from inveniolang.type_checker import TypeChecker


def _interprete(codigo):
    r = compile_pure(CompileRequest("t.inv", codigo))
    assert r.ok, r.errores
    return "".join(r.salida)


def _ir(codigo, optimizado=False):
    em = ErrorManager()
    ast, _ = Parser(Lexer(em), em).analizar(codigo, "t.inv")
    tabla = SemanticAnalyzer(em).analizar(ast)
    TypeChecker(em, tabla).verificar(ast)
    assert not em.hay_errores(), em.obtener_reportes()
    subrutinas, globales = ir.generar_programa(ast)
    if optimizado:
        globales, _ = ir.optimizar(globales)
        subrutinas, _ = ir.optimizar_programa(subrutinas)
    return "".join(ir.MaquinaTAC(subrutinas, globales).ejecutar())


def _ambos(codigo):
    salidas = {_interprete(codigo), _ir(codigo), _ir(codigo, optimizado=True)}
    assert len(salidas) == 1, salidas
    return salidas.pop()


def test_inv1290_asignacion_compuesta_en_la_actualizacion_del_para():
    codigo = """
    void main() {
        para (entero i = 0; i < 6; i += 2) { imprimir(i); }
        entero j;
        para (j = 10; j > 0; j -= 4) { imprimir(j); }
        entero[3] a = {1, 2, 3};
        para (entero k = 0; k < 3; k++) { a[k] *= 10; }
        imprimir(a[2]);
    }"""
    assert _ambos(codigo) == "024106230"


def test_inv1290_promocion_en_la_actualizacion_respeta_el_tipo_de_la_variable():
    codigo = """
    real f(real c) { retornar c; }
    void main() {
        para (entero c = 0; c <= 20; c = c + 10) { imprimir(c); imprimir(f(c)); imprimir(" "); }
    }"""
    assert _ambos(codigo) == "00.0 1010.0 2020.0 "


def test_inv1291_declaracion_en_bloque_no_tapa_a_la_global():
    codigo = """
    entero x = 100;
    vacio main() {
        si (verdadero) { entero x = 1; imprimir(x); }
        imprimir(x);
        mientras (x == 100) { entero x = 2; imprimir(x); romper; }
        para (entero x = 7; x < 8; x++) { imprimir(x); }
        imprimir(x);
    }"""
    assert _ambos(codigo) == "11002" + "7100"


def test_inv1291_variables_de_bloques_hermanos_independientes():
    codigo = """
    void main() {
        entero total = 0;
        para (entero i = 0; i < 3; i++) { entero t = i * 2; total += t; }
        para (entero i = 0; i < 2; i++) { entero t = 100; total += t; }
        imprimir(total);
    }"""
    assert _ambos(codigo) == "206"


def test_inv1292_alcance_lexico_no_dinamico():
    codigo = """
    entero g = 7;
    entero leer_g() { retornar g; }
    void main() {
        entero g = 99;
        imprimir(leer_g()); imprimir(g);
    }"""
    assert _ambos(codigo) == "799"


def test_inv1292_lambda_captura_su_ambito_lexico_y_no_el_del_que_la_invoca():
    codigo = """
    entero base = 1;
    funcion(entero x) entero g;
    entero aplicar() {
        entero n = 1000;
        retornar g(5);
    }
    void main() {
        entero n = 10;
        g = funcion(entero x) entero { retornar x + n + base; };
        imprimir(aplicar());
    }"""
    assert _interprete(codigo) == "16"


def test_inv1293_run_ir_promueve_argumentos_y_retornos_reales():
    codigo = """
    real g() { retornar 1; }
    real h(real a, entero b) { retornar a + b; }
    void main() { imprimir(g()); imprimir(" "); imprimir(h(2, 3)); }"""
    assert _ambos(codigo) == "1.0 5.0"


VECTOR = """
vacio copiar(entero[] origen, entero[] destino, entero n) {
    para (entero i = 0; i < n; i++) { destino[i] = origen[i]; }
}
clase Vec {
    privado entero[] datos;
    privado entero[] otro;
    privado real[] reales;
    privado entero n;
    Vec() { este.datos = nuevo entero[2]; este.reales = nuevo real[2]; }
    publico vacio agregar(entero v) {
        si (este.n == longitud_arreglo(este.datos)) {
            este.otro = nuevo entero[2 * este.n];
            copiar(este.datos, este.otro, este.n);
            este.datos = este.otro;
        }
        este.datos[este.n] = v;
        este.n = este.n + 1;
    }
    publico entero obtener(entero i) { retornar este.datos[i]; }
    publico entero capacidad() { retornar longitud_arreglo(este.datos); }
    publico real real0() { este.reales[0] = 3; este.reales[0] += 1; retornar este.reales[0]; }
}
"""


def test_inv1440_vector_dinamico_crece():
    codigo = VECTOR + """
    void main() {
        Vec v = nuevo Vec();
        para (entero i = 1; i <= 5; i++) { v.agregar(i * 10); }
        imprimir(v.obtener(4)); imprimir(" "); imprimir(v.capacidad());
        imprimir(" "); imprimir(v.real0());
    }"""
    assert _interprete(codigo) == "50 8 4.0"


@pytest.mark.parametrize(
    "cuerpo, codigo_error",
    [
        ("Vec v = nuevo Vec(); imprimir(v.obtener(9));", "IL-EJE-050"),
        ("entero n = -1; Caja c = nuevo Caja(); c.d = nuevo entero[n];", "IL-EJE-050"),
        ("Caja c = nuevo Caja(); imprimir(c.d[0]);", "IL-EJE-010"),
    ],
)
def test_inv1440_errores_de_ejecucion(cuerpo, codigo_error):
    codigo = VECTOR + "clase Caja { publico entero[] d; }\nvoid main() { " + cuerpo + " }"
    r = compile_pure(CompileRequest("t.inv", codigo))
    assert not r.ok and r.errores[0].startswith(f"[{codigo_error}]")


@pytest.mark.parametrize(
    "cuerpo, codigo_error",
    [
        ("Caja c = nuevo Caja(); imprimir(c.x[0]);", "IL-TIPO-023"),
        ('Caja c = nuevo Caja(); imprimir(c.d["a"]);', "IL-TIPO-021"),
        ('Caja c = nuevo Caja(); c.d = nuevo entero["a"];', "IL-TIPO-021"),
        ("Caja c = nuevo Caja(); c.d = nuevo texto[2];", "IL-TIPO-001"),
    ],
)
def test_inv1440_errores_estaticos(cuerpo, codigo_error):
    codigo = "clase Caja { publico entero x; publico entero[] d; }\nvoid main() { " + cuerpo + " }"
    r = compile_pure(CompileRequest("t.inv", codigo))
    assert not r.ok and r.errores[0].startswith(f"[{codigo_error}]"), r.errores
