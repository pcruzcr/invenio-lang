"""API (INV-4009) y CLI ``bloques`` / ``desde-bloques`` (INV-4010)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from comun_bloques import RAIZ, TODO, bloques

from inveniolang import api, flujo

EJERCICIO = RAIZ / "curriculum" / "es" / "nivel03" / "12_funciones_como_valores.inv"


def test_api_bloques_y_vuelta():
    texto_json = api.bloques(TODO)
    modelo = bloques.desde_json(texto_json)
    en = api.codigo_desde_bloques(texto_json, "en")
    assert en == api.codigo_desde_bloques(json.loads(texto_json), "en")
    assert en == api.codigo_desde_bloques(modelo, "en")
    assert "while (n > 0)" in en
    assert api.bloques(TODO, "texto", idioma="en").startswith("enumeration Forma")
    assert set(api.catalogo_bloques("en")["tipos"]) == set(bloques.TIPOS)
    with pytest.raises(ValueError):
        api.bloques(TODO, "svg")
    with pytest.raises(flujo.ErrorFlujo) as e:
        api.bloques("vacio main() { x = 1; }")
    assert e.value.diagnosticos
    with pytest.raises(bloques.ErrorBloques):
        api.codigo_desde_bloques('{"formato": "x"}')


def _cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "inveniolang.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd or RAIZ,
        timeout=300,
    )


def test_cli_ida_y_vuelta(tmp_path):
    destino = tmp_path / "b.json"
    catalogo = tmp_path / "c.json"
    r = _cli("bloques", str(EJERCICIO), "--json", str(destino), "--catalogo", str(catalogo))
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(catalogo.read_text(encoding="utf-8"))["formato"] == (
        "inveniolang-bloques-catalogo"
    )
    programa = tmp_path / "p.inv"
    r = _cli("desde-bloques", str(destino), "--idioma", "en", "-o", str(programa))
    assert r.returncode == 0 and "Program written" in r.stdout
    esperado = EJERCICIO.with_suffix(".expected").read_text(encoding="utf-8")
    assert "".join(api.ejecutar(programa.read_text(encoding="utf-8")).salida) == esperado
    r = _cli("blocks", str(EJERCICIO), "--idioma", "en")
    assert r.returncode == 0 and "define int sumar" in r.stdout


def test_cli_errores(tmp_path):
    malo = tmp_path / "malo.inv"
    malo.write_text("vacio main() { x = 1; }\n", encoding="utf-8")
    r = _cli("bloques", str(malo))
    assert r.returncode == 1 and "IL-" in r.stdout
    modelo = bloques.bloques_desde_codigo("vacio main() {\n    imprimir(1);\n}\n")
    modelo.programa[0].listas["cuerpo"][0].huecos["valor"] = None
    incompleto = tmp_path / "i.json"
    incompleto.write_text(bloques.a_json(modelo), encoding="utf-8")
    r = _cli("desde-bloques", str(incompleto), "--idioma", "en")
    assert r.returncode == 1 and "missing" in r.stdout
    roto = tmp_path / "r.json"
    roto.write_text("{", encoding="utf-8")
    assert _cli("desde-bloques", str(roto)).returncode == 1
    assert _cli("desde-bloques", str(tmp_path / "no.json")).returncode == 1
