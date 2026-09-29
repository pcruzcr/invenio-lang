# tests/test_auditoria.py — Suite de verificación para las mejoras de auditoría
# Ejecutar: python -m pytest tests/ -q   (desde la raíz del repo)
import io
import json
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inveniolang.security import validar_ruta_relativa, validar_tamano_contenido, auditar_seguridad
from inveniolang.observability import (PipelineMetrics, MetricsObserver, get_logger,
                                       configure_observability, JsonFormatter,
                                       new_run_id, set_current_run, get_current_run)
from inveniolang.toolchain import pkg as pkg_mod
from inveniolang.core import CompileRequest, compile_pure


# ————— security.py —————
@pytest.mark.parametrize("ruta", [
    "../etc/passwd", "a/../b", "/absoluta", "C:/Windows", "C:\\Windows",
    "\\\\servidor\\compartido", "//servidor/share", "malware.exe",
    "CON", "nul.txt", "COM1.txt", "x\\x00y", "con .txt".replace(" ", ""),
    "a.".rstrip(".") and "ok.inv",
])
def test_rutas_bloqueadas_o_validas(ruta):
    """Rutas peligrosas → ValueError; 'ok.inv' estilo es aceptable en otros tests."""
    try:
        validar_ruta_relativa(ruta)
    except ValueError:
        return
    # Si no lanzó, debe ser una ruta razonablemente segura
    assert ".." not in ruta.split("/") and ruta == "ok.inv"

@pytest.mark.parametrize("ruta", [
    "../etc/passwd", "C:/Windows", "\\\\srv\\share", "//srv/share",
    "malware.exe", "CON", "NUL.dat", "COM1", "a..b/../../x.txt",
    "trick.txt.", "wild*.txt",
])
def test_rutas_peligrosas_rechazadas(ruta):
    with pytest.raises(ValueError):
        validar_ruta_relativa(ruta)

def test_ruta_valida():
    assert validar_ruta_relativa("datos/archivo.txt") == "datos/archivo.txt"

def test_tamano_contenido():
    with pytest.raises(ValueError):
        validar_tamano_contenido("x" * 200_001)

def test_auditar_seguridad_ok():
    hallazgos = auditar_seguridad()
    assert hallazgos and hallazgos[0][0] == "OK"


# ————— observability.py —————
def test_logger_json_estructurado():
    stream = io.StringIO()
    configure_observability(level=logging.INFO, stream=stream)
    log = get_logger("test")
    log.info("evento_prueba", extra={"event": "prueba", "valor": 42})
    lineas = stream.getvalue().strip().splitlines()
    payload = json.loads(lineas[-1])
    assert payload["msg"] == "evento_prueba"
    assert payload["valor"] == 42
    assert payload["level"] == "INFO"

def test_pipeline_metrics_mide_fases():
    m = PipelineMetrics()
    with m.mide("lexer"):
        pass
    with m.mide("parser"):
        pass
    d = m.to_dict()
    assert [f["fase"] for f in d["fases"]] == ["lexer", "parser"]
    assert d["total_ms"] >= 0

def test_pipeline_metrics_captura_error():
    m = PipelineMetrics()
    with pytest.raises(RuntimeError):
        with m.mide("fase_x"):
            raise RuntimeError("boom")
    assert "RuntimeError" in m.fases[0]["error"]

def test_metrics_observer_cuenta_errores():
    from inveniolang.errors import ErrorManager
    em = ErrorManager()
    obs = MetricsObserver()
    em.attach(obs)
    em.error_lexico("IL-LEX-001", "m", 1, 1)
    em.advertencia("IL-WARN-001", "w", 1, 1)
    assert obs.errores == 1 and obs.advertencias == 1
    assert obs.por_codigo["IL-LEX-001"] == 1

def test_run_id_correlacion():
    rid = new_run_id()
    set_current_run(rid, ruta="t.inv")
    cur = get_current_run()
    assert cur["run_id"] == rid and cur["ruta"] == "t.inv"


# ————— toolchain/pkg.py —————
def test_pkg_json_corrupto_no_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("invenio.json").write_text("{json roto", encoding="utf-8")
    assert pkg_mod.resolve_deps() == []
    assert pkg_mod.pkg_hash()  # hash calculable de todos modos

def test_pkg_init_valida_nombre(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        pkg_mod.init_pkg("../malicioso")
    with pytest.raises(ValueError):
        pkg_mod.init_pkg("app", version="no-soy-semver")
    pkg_mod.init_pkg("app_valido")
    assert Path("invenio.json").exists()

def test_pkg_escritura_atomica_add_dep(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pkg_mod.init_pkg("app")
    deps = pkg_mod.add_dep("lib1.inv")
    assert "lib1.inv" in deps
    assert "lib1.inv" in pkg_mod.resolve_deps()
    assert not Path("invenio.json.tmp").exists()  # tmp renombrado


# ————— core/compiler.py con métricas —————
def test_compile_pure_con_metricas():
    m = PipelineMetrics()
    req = CompileRequest(ruta="t.inv",
                         codigo="void main() { imprimir(5); }")
    r = compile_pure(req, metrics=m)
    assert r.ok, r.errores
    assert "5" in "".join(r.salida)
    d = m.to_dict()
    assert {f["fase"] for f in d["fases"]} >= {"lexer", "parser", "semantico", "tipos", "ejecucion"}

def test_compile_pure_sin_metricas_igual():
    req = CompileRequest(ruta="t.inv",
                         codigo="void main() { imprimir(5); }")
    r = compile_pure(req)
    assert r.ok and "5" in "".join(r.salida)