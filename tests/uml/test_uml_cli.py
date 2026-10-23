"""CLI: ``--uml svg|json|texto`` y ``inveniolang desde-uml`` (INV-3213)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from inveniolang import api, cli, i18n, uml

RAIZ = Path(__file__).resolve().parents[2]
COMPOSICION = RAIZ / "curriculum" / "es" / "nivel08" / "06_composicion.inv"


@pytest.fixture(autouse=True)
def _idioma_limpio():
    yield
    i18n.establecer_idioma(None)


def _cli(monkeypatch, capsys, *args: str) -> tuple[int, str]:
    i18n.establecer_idioma(None)  # cada invocación es un proceso nuevo
    monkeypatch.setattr(sys, "argv", ["inveniolang", *args])
    rc = cli.main()
    return rc, capsys.readouterr().out


@pytest.mark.parametrize(
    ("formato", "inicio"),
    [
        ("plantuml", "@startuml"),
        ("mermaid", "classDiagram"),
        ("svg", "<svg"),
        ("json", "{"),
        ("texto", "Diagrama de clases: 2 clases; 1 relación."),
    ],
)
def test_uml_en_cada_formato(monkeypatch, capsys, formato, inicio):
    rc, out = _cli(monkeypatch, capsys, str(COMPOSICION), "--uml", formato)
    assert rc == 0 and out.startswith(inicio)


def test_uml_texto_en_ingles_y_con_importar(monkeypatch, capsys):
    rc, out = _cli(monkeypatch, capsys, str(COMPOSICION), "--uml", "texto", "--idioma", "en")
    assert rc == 0 and out.startswith("Class diagram: 2 classes; 1 relationship.")
    # `importar` se resuelve junto al archivo, no junto al directorio de trabajo
    pila = RAIZ / "tests" / "stdlib" / "programas" / "pila.inv"
    rc, out = _cli(monkeypatch, capsys, str(pila), "--uml", "json")
    assert rc == 0 and uml.desde_json(out).clasificador("Pila") is not None


def test_uml_programa_invalido(monkeypatch, capsys, tmp_path):
    malo = tmp_path / "malo.inv"
    malo.write_text("clase A hereda Nadie { } vacio main() { }", encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, str(malo), "--uml", "svg")
    assert rc == 1 and "Nadie" in out


def test_desde_uml_puml_a_stdout_y_a_archivo(monkeypatch, capsys, tmp_path):
    puml = tmp_path / "d.puml"
    puml.write_text(
        "class Motor {\n - hp : int\n}\nclass Car\nCar *-- Motor : engine\n", encoding="utf-8"
    )
    rc, out = _cli(monkeypatch, capsys, "desde-uml", str(puml))
    assert rc == 0 and "class Car {" in out and "this.engine = new Motor();" not in out
    assert "private Motor engine = new Motor();" in out
    destino = tmp_path / "car.inv"
    rc, out = _cli(monkeypatch, capsys, "from-uml", str(puml), "--idioma", "es", "-o", str(destino))
    assert rc == 0 and "Esqueleto escrito en" in out
    codigo = destino.read_text(encoding="utf-8")
    assert "clase Car {" in codigo and api.compilar(codigo).ok


def test_desde_uml_json(monkeypatch, capsys, tmp_path):
    diagrama = tmp_path / "d.json"
    diagrama.write_text(
        api.uml(COMPOSICION.read_text(encoding="utf-8"), formato="json").salida[0], encoding="utf-8"
    )
    rc, out = _cli(monkeypatch, capsys, "desde-uml", str(diagrama), "--idioma", "en")
    assert rc == 0 and "class Car" not in out and "class Auto {" in out
    assert json.loads(diagrama.read_text(encoding="utf-8"))["version"] == 1


def test_desde_uml_errores(monkeypatch, capsys, tmp_path):
    rc, out = _cli(monkeypatch, capsys, "desde-uml", str(tmp_path / "no_existe.puml"))
    assert rc == 1 and "No se pudo leer el diagrama" in out
    malo = tmp_path / "m.puml"
    malo.write_text("class A {\n - hijos : A[]\n}\n", encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, "desde-uml", str(malo), "--idioma", "en")
    assert rc == 1 and "cannot be turned into InvenioLang code" in out
    assert "arrays of objects" in out
    bueno = tmp_path / "b.puml"
    bueno.write_text("class A\n", encoding="utf-8")
    rc, out = _cli(
        monkeypatch, capsys, "desde-uml", str(bueno), "-o", str(tmp_path / "x" / "y.inv")
    )
    assert rc == 1 and "No se pudo escribir" in out


def test_ayuda_menciona_los_formatos(monkeypatch, capsys):
    rc, out = _cli(monkeypatch, capsys, "--help")
    assert rc == 0 and "desde-uml" in out and "svg" in out
