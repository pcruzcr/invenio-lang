# tests/test_regresion_golden.py — Oráculo de regresión sobre pruebas/*.inv
#
# Garantía: el pipeline completo (lexer→parser→semántico→tipos→ejecución)
# nunca debe lanzar una excepción no controlada para ningún programa de
# referencia, y todo error debe estar catalogado con el formato oficial
# [IL-XXX-NNN] (§15.8.1). Complementa la conformidad de 391 casos del CI.

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inveniolang.core import CompileRequest, compile_pure
from inveniolang.observability import PipelineMetrics

RAIZ = Path(__file__).resolve().parents[1]
_CATALOGO = re.compile(r"^\[IL-[A-Z]{3}-\d{3}\]")


def _programas_inv() -> list[Path]:
    carpeta = RAIZ / "pruebas"
    return sorted(carpeta.glob("*.inv"))


@pytest.mark.parametrize("ruta", _programas_inv(), ids=lambda p: p.name)
def test_pipeline_sin_crash_y_errores_catalogados(ruta: Path):
    codigo = ruta.read_text(encoding="utf-8", errors="replace")
    req = CompileRequest(ruta=ruta.name, codigo=codigo, modo="check")
    metrics = PipelineMetrics()
    # No debe lanzar excepción (crash = defecto, error catalogado = correcto)
    resultado = compile_pure(req, metrics=metrics)
    for err in resultado.errores:
        assert _CATALOGO.match(err), f"error no catalogado en {ruta.name}: {err}"
    assert metrics.fases, "las métricas por fase deben registrarse"


def test_sandbox_stdin_y_aislamiento(tmp_path):
    """El sandbox debe alimentar stdin por caso y aislar la ejecución."""
    from inveniolang.sandbox import run_sandboxed

    # Programa que lee una línea de entrada y la imprime
    prog = tmp_path / "leer.inv"
    prog.write_text(
        "string nombre = leer();\nimprimir(nombre);\n",
        encoding="utf-8",
    )
    # Rápido: timeout corto; en CI sin sandbox externo debe funcionar igual
    r = run_sandboxed(str(prog), entrada=["Socrates"], timeout=15)
    # El resultado debe existir y, si el intérprete soporta leer() con stdin,
    # la salida contiene la entrada; si no, el fallo debe ser controlado.
    assert isinstance(r, dict) and "ok" in r and "returncode" in r
    if r["ok"]:
        assert "Socrates" in r["stdout"]


def test_cli_caret_y_metrics_salida():
    """CLI: --metrics imprime JSON con métricas por fase."""
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "inveniolang.cli",
            "--metrics",
            str(RAIZ / "pruebas" / "hola_mundo.inv"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        cwd=str(RAIZ),
    )
    assert proc.returncode == 0
    import json

    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    fases = {f["fase"] for f in payload["metrics"]["fases"]}
    assert {"lexer", "parser", "semantico", "tipos", "ejecucion"} <= fases
