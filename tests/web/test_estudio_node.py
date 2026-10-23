"""Pruebas de JavaScript con ``node --test`` (INV-4232).

La lógica pura del estudio (estado, i18n, almacenamiento, currículo,
resaltado, motor y bloques) y la gramática y el cliente de la extensión de
VS Code se prueban en Node; esta prueba las lanza para que la batería de
pytest las incluya.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="sin Node.js para ejecutar las pruebas de JavaScript")
@pytest.mark.parametrize(
    "carpeta", [RAIZ / "web" / "estudio" / "pruebas", RAIZ / "vscode-extension" / "pruebas"]
)
def test_node_test(carpeta):
    pruebas = sorted(str(p) for p in carpeta.glob("*.test.mjs"))
    assert pruebas, carpeta
    # La prueba del servidor LSP lo lanza con este mismo intérprete.
    entorno = {**os.environ, "INVENIOLANG_PYTHON": sys.executable}
    r = subprocess.run(
        # TAP explícito: desde Node 20 el reportero por defecto es "spec" (ℹ fail 0).
        [NODE, "--test", "--test-reporter=tap", *pruebas],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        cwd=carpeta,
        env=entorno,
    )
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
    assert "# fail 0" in r.stdout
