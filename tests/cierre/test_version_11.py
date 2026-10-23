"""INV-4408: versión 11.0.0 en la fuente única y en todo lo que la cita.

Antes `main.py --version` imprimía "10.0.0" escrito a mano (no leía
`_version.py`), y SBOM, pyproject, la puerta de release y los documentos de
release repetían la cadena: una subida de versión olvidada en uno de ellos
dejaba artefactos contradictorios.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import __version__  # noqa: E402
from inveniolang.config import Config  # noqa: E402
from inveniolang.core import COMPILER_VERSION  # noqa: E402
from inveniolang.sbom import generar_sbom  # noqa: E402

VERSION = "11.0.0"


def test_fuente_unica_y_derivados():
    assert __version__ == COMPILER_VERSION == Config().compiler_version == VERSION


def test_main_version_lee_la_fuente_unica():
    r = subprocess.run(
        [sys.executable, "main.py", "--version"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.stdout.strip() == f"InvenioLang {VERSION}"


def test_pyproject_y_sbom_al_dia():
    assert f'version = "{VERSION}"' in (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    sbom = json.loads((RAIZ / "SBOM.json").read_text(encoding="utf-8"))
    assert sbom["version"] == VERSION
    # Las huellas del SBOM corresponden a los ficheros actuales (se regeneró).
    assert sbom["ficheros_clave"] == generar_sbom(str(RAIZ))["ficheros_clave"]


def test_documentos_de_release():
    release = (RAIZ / "docs" / "RELEASE.md").read_text(encoding="utf-8")
    assert f"# Release {VERSION}" in release and f"v{VERSION}" in release
    assert "10.0.0" not in release
    verificador = (RAIZ / "scripts" / "verify_release.py").read_text(encoding="utf-8")
    assert f'"{VERSION}"' in verificador
