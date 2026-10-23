"""Diagnósticos, mensajes de ejecución y CLI bilingües (INV-1400..INV-1403, INV-1410)."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys

import pytest

from inveniolang import builtins as bi
from inveniolang import i18n
from inveniolang.core import CompileRequest, compile_pure
from inveniolang.error_explainer import NIVELES, explicar, explicar_mensaje
from inveniolang.errors import ErrorManager
from inveniolang.i18n import en, es

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAQUETE = os.path.join(RAIZ, "inveniolang")
# Módulos cuyos textos para el estudiante salen del catálogo.
MODULOS_CATALOGADOS = [
    "lexer",
    "parser",
    "semantic",
    "type_checker",
    "interpreter",
    "ir",
    "builtins",
    "cli",
    "modulos",
    "error_explainer",
    "errors",
    "core/compiler",
]
METODOS_DIAGNOSTICO = {
    "error_lexico",
    "error_sintactico",
    "error_semantico",
    "error_tipo",
    "error_poo",
    "error_estructurado",
    "error_ejecucion",
    "advertencia",
    "RuntimeError_",
    "BuiltInError",
    "ErrorEjecucionTAC",
    "NoSoportadoIR",
    "NoSoportadoObjetivo",
}


def _arbol(nombre):
    with open(os.path.join(PAQUETE, nombre + ".py"), encoding="utf-8") as f:
        return ast.parse(f.read())


# ---------------------------------------------------------------- catálogo


def test_ningun_idioma_carece_de_una_clave():
    assert set(es.MENSAJES) == set(en.MENSAJES)
    for idioma in i18n.IDIOMAS:
        assert set(i18n.REGISTRO.obtener(idioma).mensajes) == set(es.MENSAJES)


def test_mismos_marcadores_en_ambos_idiomas():
    for clave, plantilla in es.MENSAJES.items():
        assert i18n.marcadores(plantilla) == i18n.marcadores(en.MENSAJES[clave]), clave


def test_toda_plantilla_se_puede_formatear():
    for clave, plantilla in es.MENSAJES.items():
        args = dict.fromkeys(i18n.marcadores(plantilla), 1)
        for idioma in i18n.IDIOMAS:
            assert isinstance(i18n.t(clave, idioma, **args), str)


def test_ninguna_traduccion_inglesa_quedo_en_espanol():
    sospechosas = re.compile(r"\b(no se|debe ser|fuera de rango|esperaba|encontró|está)\b")
    for clave, plantilla in en.MENSAJES.items():
        assert not sospechosas.search(plantilla), clave


def _claves_usadas():
    usadas = set()
    for nombre in MODULOS_CATALOGADOS:
        for nodo in ast.walk(_arbol(nombre)):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Name)
                and nodo.func.id in ("M", "t")
                and nodo.args
                and isinstance(nodo.args[0], ast.Constant)
            ):
                usadas.add(nodo.args[0].value)
    return usadas


def test_toda_clave_usada_en_el_codigo_existe():
    usadas = _claves_usadas()
    assert len(usadas) > 250
    assert usadas - set(es.MENSAJES) == set()


def test_ningun_diagnostico_se_escribe_como_texto_literal():
    """El mensaje de cada diagnóstico es un M(...) del catálogo, nunca un str."""
    culpables = []
    for nombre in MODULOS_CATALOGADOS:
        for nodo in ast.walk(_arbol(nombre)):
            if not isinstance(nodo, ast.Call):
                continue
            f = nodo.func
            nom = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if nom not in METODOS_DIAGNOSTICO:
                continue
            idx = 0 if nom.startswith("NoSoportado") else 1
            if len(nodo.args) > idx and isinstance(nodo.args[idx], (ast.Constant, ast.JoinedStr)):
                culpables.append(f"{nombre}:{nodo.lineno}")
    assert culpables == []


# ---------------------------------------------------------------- selección del idioma

PROGRAMA_ERROR = 'void main() { entero x = "hola"; }'


def test_compile_pure_con_idioma():
    r_es = compile_pure(CompileRequest("a.inv", PROGRAMA_ERROR))
    r_en = compile_pure(CompileRequest("a.inv", PROGRAMA_ERROR), idioma="en")
    assert "Tipo incompatible" in r_es.errores[0]
    assert "Incompatible type" in r_en.errores[0]
    assert r_es.errores[0].split(" — ")[0] == r_en.errores[0].split(" — ")[0]


def test_compile_pure_rechaza_un_idioma_desconocido():
    with pytest.raises(ValueError):
        compile_pure(CompileRequest("a.inv", PROGRAMA_ERROR), idioma="fr")


def test_variable_de_entorno(monkeypatch):
    monkeypatch.setenv(i18n.VARIABLE_ENTORNO, "en_US.UTF-8")
    assert i18n.idioma_actual() == "en"
    assert "Incompatible type" in compile_pure(CompileRequest("a.inv", PROGRAMA_ERROR)).errores[0]
    monkeypatch.setenv(i18n.VARIABLE_ENTORNO, "klingon")  # valor inválido: no tumba nada
    assert i18n.idioma_actual() == "es"


def test_mensaje_de_ejecucion_capturado_llega_al_programa_en_su_idioma():
    prog = (
        "void main() { intentar { entero x = 1 / 0; } "
        'capturar (e) { imprimir(e.codigo + " " + e.message); } }'
    )
    assert compile_pure(CompileRequest("a.inv", prog), idioma="en").salida == (
        "IL-EJE-006 Division by zero",
    )
    assert compile_pure(CompileRequest("a.inv", prog)).salida == ("IL-EJE-006 División por cero",)


def test_error_manager_conserva_la_clave_independiente_del_idioma():
    em = ErrorManager(idioma="en")
    em.error_semantico("IL-SEM-003", i18n.M("IL-SEM-003.funcion_no_encontrada", nombre="f"), 1, 1)
    err = em.errores[0]
    assert err.mensaje == 'Function not found: "f"'
    assert err.clave == "IL-SEM-003.funcion_no_encontrada" and err.args_mensaje == {"nombre": "f"}


def _cli(*args, env_extra=None, cwd=None):
    env = dict(os.environ, PYTHONPATH=RAIZ)
    env.pop(i18n.VARIABLE_ENTORNO, None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-m", "inveniolang.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=cwd or RAIZ,
        timeout=60,
    )


def test_cli_idioma_en(tmp_path):
    prog = tmp_path / "p.inv"
    prog.write_text(PROGRAMA_ERROR, encoding="utf-8")
    salida = _cli(str(prog), "--idioma", "en").stdout
    assert "=== TYPE ERRORS ===" in salida and "Incompatible type" in salida
    salida_es = _cli(str(prog)).stdout
    assert "=== ERRORES DE TIPOS ===" in salida_es


def test_cli_ayuda_y_variable_de_entorno():
    assert "Usage:" in _cli("--help", env_extra={i18n.VARIABLE_ENTORNO: "en"}).stdout
    assert "Uso:" in _cli("--help").stdout
    assert (
        "Check without running" in _cli("--idioma=en", "-h").stdout
        or "Usage" in _cli("--idioma=en", "-h").stdout
    )


def test_cli_rechaza_idioma_invalido(tmp_path):
    prog = tmp_path / "p.inv"
    prog.write_text("void main() { }", encoding="utf-8")
    r = _cli(str(prog), "--idioma", "fr")
    assert r.returncode != 0


def test_cli_step_con_errores_ya_no_se_cae(tmp_path):
    """INV-1430: --step con un error de tipos lanzaba AttributeError."""
    prog = tmp_path / "p.inv"
    prog.write_text(PROGRAMA_ERROR, encoding="utf-8")
    r = _cli(str(prog), "--step")
    assert "Traceback" not in r.stderr
    assert "IL-TIPO-001" in r.stdout and r.returncode == 1


# ---------------------------------------------------------------- explicador


def test_explicador_bilingue_con_ejemplos_en_el_idioma():
    exp_en = explicar("IL-SIN-030", "en")
    exp_es = explicar("IL-SIN-030", "es")
    assert exp_en.ejemplo_bueno.startswith("if (") and exp_es.ejemplo_bueno.startswith("si (")
    assert "Why:" in explicar_mensaje("IL-SIN-030", "x", 1, 1, "en")
    for codigo in NIVELES:
        for idioma in i18n.IDIOMAS:
            exp = explicar(codigo, idioma)
            assert exp.titulo and exp.fix


def test_explicador_familias_genericas():
    assert explicar("IL-MOD-999", "en").titulo == "Module error"
    assert explicar("XYZ") is None


# ---------------------------------------------------------------- built-ins


def test_todo_builtin_tiene_nombre_en_ambos_idiomas_y_una_sola_implementacion():
    for es_nombre, en_nombre, alias, func, _ret, _params in bi.BUILT_INS_BILINGUES:
        assert es_nombre != en_nombre
        for nombre in (es_nombre, en_nombre, *alias):
            assert bi.FUNCIONES_BUILT_IN[nombre][0] is func
            assert bi.PARES_BUILT_IN[nombre] == (es_nombre, en_nombre)
    assert set(bi.FUNCIONES_BUILT_IN) == set(bi.PARES_BUILT_IN)


def test_builtins_nuevos():
    prog = """
    void main() {
        entero[4] v = {1, 2, 3, 4};
        texto[2] w = {"a", "b"};
        imprimir(longitud_arreglo(v)); imprimir(array_length(w));
        imprimir(" "); imprimir(redondear(2.5)); imprimir(round(-2.5)); imprimir(redondear(2.4));
        imprimir(" "); imprimir(absoluto_real(-1.5)); imprimir(fabs(2.0));
    }"""
    assert "".join(compile_pure(CompileRequest("a.inv", prog)).salida) == "42 3-32 1.52.0"


def test_longitud_arreglo_rechaza_un_escalar():
    r = compile_pure(CompileRequest("a.inv", "void main() { imprimir(longitud_arreglo(3)); }"))
    assert not r.ok and "IL-SEM-081" in r.errores[0]


def test_lanzar_error_es_capturable():
    prog = """
    entero raiz_entera(entero x) {
        si (x < 0) { lanzar_error("negativo"); }
        retornar x;
    }
    void main() {
        intentar { imprimir(raiz_entera(-1)); }
        capturar (e) { imprimir(e.codigo + ":" + e.mensaje); }
        throw_error("fin");
    }"""
    r = compile_pure(CompileRequest("a.inv", prog))
    assert not r.ok and r.errores[0].endswith("— fin") and "IL-EJE-060" in r.errores[0]
    r2 = compile_pure(CompileRequest("a.inv", prog.replace('throw_error("fin");', "")))
    assert r2.salida == ("IL-EJE-060:negativo",)


def test_pasadas_de_optimizacion_con_nombre_traducido():
    from inveniolang import ir

    assert ir.nombre_pasada("plegado de constantes", "en") == "constant folding"
    assert ir.nombre_pasada("plegado de constantes", "es") == "plegado de constantes"
