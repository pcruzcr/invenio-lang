"""API (INV-3008), CLI (INV-3009) y retirada de flowchart*.py (INV-3011)."""

from __future__ import annotations

import importlib
import json
import sys

import pytest
from comun import RAIZ, TODO, flujo

from inveniolang import api, cli

BURBUJA = RAIZ / "curriculum" / "es" / "nivel05" / "01_burbuja.inv"


def test_api_diagrama_flujo_formatos():
    codigo = BURBUJA.read_text(encoding="utf-8")
    modelo = json.loads(api.diagrama_flujo(codigo))
    assert modelo["formato"] == "inveniolang-flujo" and modelo["idioma"] == "es"
    assert api.diagrama_flujo(codigo, "intercambiar", "svg").startswith("<svg")
    assert api.diagrama_flujo(codigo, "main", "mermaid", "en").startswith("flowchart TD")
    assert api.diagrama_flujo(codigo, "intercambiar", "texto", "en").startswith(
        "Flowchart of intercambiar."
    )
    with pytest.raises(flujo.ErrorFlujo):
        api.diagrama_flujo(codigo, "no_existe")
    with pytest.raises(ValueError):
        api.diagrama_flujo(codigo, formato="gif")
    with pytest.raises(flujo.ErrorFlujo) as e:
        api.diagrama_flujo("vacio main() { x = 1; }")
    assert any("IL-" in d for d in e.value.diagnosticos)


def test_api_codigo_desde_flujo_acepta_json_dict_y_modelo():
    texto = api.diagrama_flujo(TODO)
    modelo = flujo.desde_json(texto)
    en = api.codigo_desde_flujo(texto, "en")
    assert (
        en
        == api.codigo_desde_flujo(json.loads(texto), "en")
        == api.codigo_desde_flujo(modelo, "en")
    )
    assert "while" in en and api.compilar(en).ok
    assert "mientras" in api.codigo_desde_flujo(modelo)


def test_api_modulos_en_memoria():
    codigo = 'importar "util.inv";\nvacio main() { imprimir(doble(2)); }'
    util = "entero doble(entero x) { retornar x * 2; }"
    m = flujo.desde_json(api.diagrama_flujo(codigo, modulos={"util.inv": util}))
    assert m.elementos[0].texto == 'importar "util.inv";'
    assert [d.clave for d in m.diagramas()] == ["main"]


def _cli(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["inveniolang", *argv])
    rc = cli.main()
    return rc, capsys.readouterr().out


def test_cli_flujo_y_desde_flujo(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    rc, out = _cli(
        monkeypatch, capsys, "flujo", str(BURBUJA), "--subrutina", "intercambiar", "--idioma", "en"
    )
    assert rc == 0 and out.startswith("Flowchart of intercambiar.")
    rc, _ = _cli(
        monkeypatch,
        capsys,
        "flujo",
        str(BURBUJA),
        "--json",
        "d.json",
        "--svg",
        "d.svg",
        "--mermaid",
        "d.mmd",
        "--tema",
        "auto",
    )
    assert rc == 0 and (tmp_path / "d.svg").read_text(encoding="utf-8").startswith("<svg")
    assert (tmp_path / "d.mmd").read_text(encoding="utf-8").startswith("flowchart TD")
    rc, _ = _cli(monkeypatch, capsys, "desde-flujo", "d.json", "--idioma", "en", "-o", "salida.inv")
    assert rc == 0
    codigo = (tmp_path / "salida.inv").read_text(encoding="utf-8")
    esperado = BURBUJA.with_suffix(".expected").read_text(encoding="utf-8")
    assert "".join(api.ejecutar(codigo).salida) == esperado
    rc, out = _cli(monkeypatch, capsys, "desde-flujo", "d.json")
    assert rc == 0 and "vacio main()" in out


def test_cli_errores(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "malo.inv").write_text("vacio main() { x = 1; }", encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, "flujo", "malo.inv")
    assert rc == 1 and "IL-" in out
    rc, out = _cli(
        monkeypatch, capsys, "flujo", str(BURBUJA), "--subrutina", "nada", "--idioma", "en"
    )
    assert rc == 1 and "There is no subroutine" in out
    modelo = flujo.modelo_desde_codigo("vacio main() { entero x = 1; }")
    modelo = flujo.editar(modelo, "main", "n1", "texto", 'entero x = "uno"')
    (tmp_path / "d.json").write_text(flujo.a_json(modelo), encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, "desde-flujo", "d.json", "-o", "x.inv")
    assert rc == 1 and "[main · n1]" in out and not (tmp_path / "x.inv").exists()
    (tmp_path / "roto.json").write_text("{}", encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, "desde-flujo", "roto.json", "--idioma", "es")
    assert rc == 1 and "faltan" in out


@pytest.mark.parametrize("modulo", ["inveniolang.flowchart", "inveniolang.flowchart_builder"])
def test_modulos_anteriores_retirados(modulo):
    # INV-3011: sustituidos por inveniolang.flujo; no deben quedar como código muerto.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(modulo)
