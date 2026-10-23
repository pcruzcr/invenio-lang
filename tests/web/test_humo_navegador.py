"""Prueba de humo del estudio en Chromium (INV-4230).

Sirve ``web/estudio`` en 127.0.0.1 con un paquete recién generado y recorre
la página con Playwright: ejecutar con entrada, errores explicados, ir a la
línea, traducir, diagrama de flujo, UML, paso a paso, bloques (teclado y
edición de un campo), currículo (solución y comprobación), tema oscuro,
idioma inglés y pestañas con flechas, sin un solo error en la consola.

* Siempre que haya Chromium y Playwright: con el **Pyodide simulado**
  (``pyodide_simulado/``), que reenvía cada llamada al puente real en CPython.
* Además, si hay una copia local de Pyodide (variable
  ``INVENIOLANG_PYODIDE_DIR`` o ``~/.cache/inveniolang/pyodide-0.29.3``):
  con el **Pyodide real**, ejecutando el compilador en WebAssembly.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "scripts"))

import empaquetar_web  # noqa: E402
from servidor_estudio import arrancar  # noqa: E402

NODE = shutil.which("node")
PLAYWRIGHT = Path(
    os.environ.get("INVENIOLANG_PLAYWRIGHT", "/opt/npm-tools/node_modules/playwright/index.mjs")
)
CHROMIUM = sorted(
    Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")).glob(
        "chromium-*/chrome-linux/chrome"
    )
)
PYODIDE = Path(
    os.environ.get("INVENIOLANG_PYODIDE_DIR", Path.home() / ".cache/inveniolang/pyodide-0.29.3")
)
TIENE_BLOQUES = importlib.util.find_spec("inveniolang.bloques") is not None

requiere_navegador = pytest.mark.skipif(
    NODE is None or not PLAYWRIGHT.exists() or not CHROMIUM,
    reason="sin Node.js, Playwright o Chromium (/opt/pw-browsers) para la prueba de humo",
)


@pytest.fixture(scope="module")
def generado(tmp_path_factory):
    destino = tmp_path_factory.mktemp("generado")
    empaquetar_web.escribir(destino, empaquetar_web.generar())
    return destino


def recorrer(generado: Path, pyodide: Path | None) -> None:
    servidor, base = arrancar(pyodide, generado)
    try:
        r = subprocess.run(
            [
                NODE,
                str(AQUI / "humo_navegador.mjs"),
                PLAYWRIGHT.as_uri(),
                str(CHROMIUM[-1]),
                f"{base}index.html?pyodide=/__pyodide/",
                "1" if TIENE_BLOQUES else "0",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
    finally:
        servidor.shutdown()
    resultado = (
        json.loads(r.stdout.strip().splitlines()[-1])
        if r.stdout.strip()
        else {"fallos": [r.stderr]}
    )
    assert r.returncode == 0 and resultado["fallos"] == [], resultado["fallos"]


@requiere_navegador
def test_humo_con_pyodide_simulado(generado):
    recorrer(generado, None)


@requiere_navegador
@pytest.mark.skipif(
    not (PYODIDE / "pyodide.mjs").exists(), reason=f"sin copia local de Pyodide en {PYODIDE}"
)
def test_humo_con_pyodide_real(generado):
    recorrer(generado, PYODIDE)
