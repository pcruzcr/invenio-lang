"""importar "ruta"; / import "path"; (INV-1420)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from inveniolang.core import CompileRequest, compile_pure
from inveniolang.errors import ErrorManager
from inveniolang.lexer import Lexer
from inveniolang.modulos import MAX_MODULOS, CargadorMemoria
from inveniolang.observability import PipelineMetrics
from inveniolang.parser import Parser

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _escribir(base, archivos):
    for nombre, texto in archivos.items():
        ruta = base / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
    return base


def _compilar(base, principal="main.inv", idioma=None):
    ruta = base / principal
    return compile_pure(CompileRequest(str(ruta), ruta.read_text(encoding="utf-8")), idioma=idioma)


UTIL = {
    "util/mates.inv": (
        "// módulo de prueba\n"
        "constante entero DOBLE = 2;\n"
        "entero duplicar(entero x) { retornar x * DOBLE; }\n"
        "entero dividir(entero a, entero b) { retornar a / b; }\n"
        "clase Contador {\n"
        "    privado entero n;\n"
        "    publico vacio inc() { este.n = este.n + 1; }\n"
        "    publico entero valor() { retornar este.n; }\n"
        "}\n"
        "enumeracion Color { ROJO, VERDE }\n"
        'void main() { imprimir("el main de un módulo no se importa"); }\n'
    ),
}


def test_importa_funciones_constantes_clases_y_enums(tmp_path):
    _escribir(
        tmp_path,
        dict(
            UTIL,
            **{
                "main.inv": (
                    'importar "util/mates";\n'
                    "void main() {\n"
                    "    imprimir(duplicar(21)); imprimir(DOBLE);\n"
                    "    Contador c = nuevo Contador(); c.inc(); c.inc(); imprimir(c.valor());\n"
                    "    imprimir(Color.VERDE);\n"
                    "}\n"
                )
            },
        ),
    )
    r = _compilar(tmp_path)
    assert r.ok, r.errores
    assert "".join(r.salida) == "42221"


def test_import_en_ingles_con_extension_y_diamante(tmp_path):
    _escribir(
        tmp_path,
        dict(
            UTIL,
            **{
                "a.inv": 'import "util/mates.inv";\nint f() { return duplicar(1); }\n',
                "b.inv": 'importar "util/mates";\nint g() { return duplicar(2); }\n',
                "main.inv": 'import "a"; import "b";\nvoid main() { print(f() + g()); }\n',
            },
        ),
    )
    r = _compilar(tmp_path)
    assert r.ok and r.salida == ("6",), r.errores


def test_modulo_no_encontrado_y_ruta_invalida(tmp_path):
    _escribir(
        tmp_path,
        {
            "main.inv": (
                'importar "nada";\nimportar "../fuera";\nimportar "/etc/x";\nvoid main() { }\n'
            )
        },
    )
    r = _compilar(tmp_path)
    assert not r.ok
    assert [e.split("]")[0] + "]" for e in r.errores] == [
        "[IL-MOD-001]",
        "[IL-MOD-002]",
        "[IL-MOD-002]",
    ]
    r_en = _compilar(tmp_path, idioma="en")
    assert "Module not found" in r_en.errores[0]


def test_extension_distinta_de_inv_rechazada(tmp_path):
    _escribir(tmp_path, {"datos.txt": "x", "main.inv": 'importar "datos.txt";\nvoid main() { }\n'})
    r = _compilar(tmp_path)
    assert "IL-MOD-002" in r.errores[0]


def test_enlace_simbolico_que_sale_de_la_carpeta(tmp_path):
    afuera = tmp_path / "afuera"
    proyecto = tmp_path / "proyecto"
    _escribir(afuera, {"secreto.inv": "entero s() { retornar 1; }\n"})
    _escribir(proyecto, {"main.inv": 'importar "enlace";\nvoid main() { }\n'})
    try:
        os.symlink(afuera / "secreto.inv", proyecto / "enlace.inv")
    except OSError:
        pytest.skip("el sistema no permite enlaces simbólicos")
    r = _compilar(proyecto)
    assert "IL-MOD-002" in r.errores[0]


def test_ciclo_de_importacion(tmp_path):
    _escribir(
        tmp_path,
        {
            "a.inv": 'importar "b";\nentero fa() { retornar 1; }\n',
            "b.inv": 'importar "a";\nentero fb() { retornar 2; }\n',
            "main.inv": 'importar "a";\nvoid main() { }\n',
        },
    )
    r = _compilar(tmp_path)
    assert len(r.errores) == 1 and "IL-MOD-003" in r.errores[0]
    assert "a.inv -> b.inv -> a.inv" in r.errores[0]


def test_importarse_a_si_mismo_es_un_ciclo(tmp_path):
    _escribir(tmp_path, {"main.inv": 'importar "main";\nvoid main() { }\n'})
    assert "IL-MOD-003" in _compilar(tmp_path).errores[0]


def test_conflicto_de_nombres(tmp_path):
    _escribir(
        tmp_path,
        dict(
            UTIL,
            **{
                "otro.inv": "entero duplicar(entero y) { retornar y; }\n",
                "main.inv": (
                    'importar "util/mates"; importar "otro";\n'
                    "entero dividir(entero a) { retornar a; }\nvoid main() { }\n"
                ),
            },
        ),
    )
    r = _compilar(tmp_path)
    assert all("IL-MOD-004" in e for e in r.errores) and len(r.errores) == 2
    assert any(e.startswith("[IL-MOD-004] otro.inv") for e in r.errores)
    assert any("main.inv:2" in e for e in r.errores)


def test_variable_global_no_importable(tmp_path):
    _escribir(
        tmp_path,
        {"m.inv": "entero contador = 0;\n", "main.inv": 'importar "m";\nvoid main() { }\n'},
    )
    r = _compilar(tmp_path)
    assert r.errores and "IL-MOD-005" in r.errores[0] and "m.inv:1" in r.errores[0]


def test_errores_del_modulo_con_su_propio_archivo(tmp_path):
    _escribir(
        tmp_path,
        {
            "sub/err.inv": 'entero g() { retornar "x"; }\n',
            "sint.inv": "entero h( { }\n",
            "main.inv": 'importar "sub/err";\nvoid main() { }\n',
            "main2.inv": 'importar "sint";\nvoid main() { }\n',
        },
    )
    r = _compilar(tmp_path)
    assert r.errores[0].startswith("[IL-TIPO-001] sub/err.inv:1:")
    r2 = _compilar(tmp_path, "main2.inv")
    assert r2.errores[0].startswith("[IL-SIN-") and "sint.inv:1" in r2.errores[0]


def test_un_modulo_no_ve_los_nombres_del_programa_que_lo_importa(tmp_path):
    _escribir(
        tmp_path,
        {
            "m.inv": "entero usa() { retornar secreto(); }\n",
            "main.inv": (
                'importar "m";\nentero secreto() { retornar 1; }\n'
                "void main() { imprimir(usa()); }\n"
            ),
        },
    )
    r = _compilar(tmp_path)
    assert not r.ok and "IL-SEM-003" in r.errores[0] and "m.inv" in r.errores[0]


def test_error_de_ejecucion_dentro_de_un_modulo_se_atribuye_al_modulo(tmp_path):
    _escribir(
        tmp_path,
        dict(
            UTIL,
            **{"main.inv": 'importar "util/mates";\nvoid main() { imprimir(dividir(1, 0)); }\n'},
        ),
    )
    r = _compilar(tmp_path)
    assert r.errores == ("[IL-EJE-006] util/mates.inv:4:49 — División por cero",)


def test_advertencias_del_modulo_no_se_repiten(tmp_path):
    _escribir(
        tmp_path,
        {
            "w.inv": "entero f() { entero x = 1; si (verdadero) { entero x = 2; } retornar x; }\n",
            "main.inv": 'importar "w";\nvoid main() { imprimir(f()); }\n',
        },
    )
    em = ErrorManager()
    ruta = tmp_path / "main.inv"
    ast, _ = Parser(Lexer(em), em).analizar(ruta.read_text(), "main.inv", ruta_fuente=str(ruta))
    from inveniolang.semantic import SemanticAnalyzer

    SemanticAnalyzer(em).analizar(ast)
    avisos = em.obtener_advertencias()
    assert len(avisos) == 1 and avisos[0].startswith("[IL-WARN-001] w.inv:1:")


def test_limite_de_modulos(tmp_path):
    archivos = {f"m{i}.inv": f'importar "m{i + 1}";\n' for i in range(MAX_MODULOS + 1)}
    archivos[f"m{MAX_MODULOS + 1}.inv"] = ""
    archivos["main.inv"] = 'importar "m0";\nvoid main() { }\n'
    _escribir(tmp_path, archivos)
    assert any("IL-MOD-007" in e for e in _compilar(tmp_path).errores)


def test_compile_pure_con_cargador_en_memoria_y_fase_medida():
    cargador = CargadorMemoria({"/virtual/lib.inv": "entero doble(entero x) { retornar 2 * x; }"})
    metricas = PipelineMetrics()
    req = CompileRequest("/virtual/main.inv", 'importar "lib"; void main() { imprimir(doble(4)); }')
    r = compile_pure(req, metricas, cargador=cargador)
    assert r.ok and r.salida == ("8",)
    assert "modulos" in [f["fase"] for f in metricas.to_dict()["fases"]]
    sin = compile_pure(
        CompileRequest("/virtual/main.inv", 'importar "otra"; void main() { }'), cargador=cargador
    )
    assert "IL-MOD-001" in sin.errores[0]


def test_programa_sin_importaciones_no_cambia():
    r = compile_pure(CompileRequest("x.inv", 'void main() { imprimir("hola"); }'))
    assert r.ok and r.salida == ("hola",)


def test_import_ya_no_es_identificador():
    r = compile_pure(CompileRequest("x.inv", "void main() { entero importar = 1; }"))
    assert not r.ok


def test_cli_run_ir_check_y_step_con_modulos(tmp_path):
    _escribir(
        tmp_path,
        {
            "lib/f.inv": (
                "constante entero BASE = 10;\nentero escalar(entero x) { retornar x * BASE; }\n"
            ),
            "p.inv": 'importar "lib/f";\nvoid main() { imprimir(escalar(4)); imprimir("\\n"); }\n',
        },
    )
    env = dict(os.environ, PYTHONPATH=RAIZ)
    for extra, esperado in (([], "40\n"), (["--run-ir"], "40\n"), (["--run-ir-opt"], "40\n")):
        r = subprocess.run(
            [sys.executable, "-m", "inveniolang.cli", str(tmp_path / "p.inv"), *extra],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=RAIZ,
            timeout=60,
        )
        assert r.stdout == esperado, (extra, r.stdout, r.stderr)
    r = subprocess.run(
        [sys.executable, "-m", "inveniolang.cli", str(tmp_path / "p.inv"), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=RAIZ,
        timeout=60,
    )
    assert "OK - 0" in r.stdout
