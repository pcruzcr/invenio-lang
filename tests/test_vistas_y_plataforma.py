"""Vistas didácticas sobre TODOS los programas de referencia y piezas de plataforma (INV-1032).

Recorrer los 70+ programas de ``pruebas/`` garantiza que diagramas de flujo,
vista Rosetta y UML no revientan con ninguna construcción del lenguaje.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from inveniolang import api, flujo, sandbox, sbom  # noqa: E402
from inveniolang.core import analizar_fuente  # noqa: E402
from inveniolang.patterns import Caretaker, Memento, RegistryFactory, StrategyContext  # noqa: E402

PROGRAMAS = sorted((RAIZ / "pruebas").glob("*.inv"))


@pytest.mark.parametrize("programa", PROGRAMAS, ids=lambda p: p.stem)
def test_vistas_de_cada_programa(programa):
    """Diagrama de flujo de cada subrutina + Rosetta en los 5 lenguajes + UML."""
    codigo = programa.read_text(encoding="utf-8")
    analisis = analizar_fuente(codigo, programa.name)
    assert analisis.ok, analisis.errores.obtener_reportes()
    # INV-3003: flowchart.py se sustituyó por inveniolang.flujo (un esquema
    # por subrutina, método y constructor).
    modelo = flujo.modelo_desde_codigo(codigo, ruta=programa.name, ruta_fuente=str(programa))
    for esquema in flujo.esquemas(modelo):
        assert esquema.nodos and esquema.ancho > 0
    for lenguaje in ("python", "c", "java", "csharp", "pascal"):
        assert api.ver_como(lenguaje, codigo).ok
    if analisis.ast.clases:
        assert "@startuml" in api.uml(codigo).salida[0]


def test_sbom_cli(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sbom", "--check"])
    assert sbom.main() == 0
    assert json.loads(capsys.readouterr().out)["producto"] == "inveniolang"
    monkeypatch.setattr(sys, "argv", ["sbom"])
    assert sbom.main() == 0


def test_sandbox_timeout_y_comando_inexistente(tmp_path):
    lazo = tmp_path / "lazo.inv"
    lazo.write_text("void main() { mientras (verdadero) { } }", encoding="utf-8")
    r = sandbox.run_sandboxed(str(lazo), timeout=1)
    assert not r["ok"]
    roto = sandbox.ResourceSandbox().execute([str(tmp_path / "no-existe")])
    assert not roto["ok"] and roto["returncode"] == 1


def test_patrones_minimos():
    ctx = StrategyContext()
    with pytest.raises(ValueError):
        ctx.execute()
    with pytest.raises(KeyError):
        ctx.execute_named("nada")
    fab = RegistryFactory()
    with pytest.raises(ValueError):
        fab.create("x")
    guardian = Caretaker(max_mementos=1)
    guardian.save(Memento(1))
    guardian.save(Memento(2))
    assert len(guardian._mementos) == 1 and guardian._mementos[0].get_state() == 2
