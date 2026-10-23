"""INV-4402: diagrama de objetos accesible desde la CLI y desde el Visualizador Qt.

Hasta ahora ``api.diagrama_objetos`` (Fase 3) solo se podía usar desde
Python: ni ``inveniolang trazar`` ni el panel Visualizador lo ofrecían.
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import api, cli, uml  # noqa: E402

COMPOSICION = RAIZ / "curriculum" / "es" / "nivel08" / "06_composicion.inv"
NS = "{http://www.w3.org/2000/svg}"


def _cli(monkeypatch, capsys, *args: str) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["inveniolang", *args])
    rc = cli.main()
    return rc, capsys.readouterr().out


def test_trazar_objetos_svg(monkeypatch, capsys, tmp_path):
    destino = tmp_path / "obj.svg"
    rc, out = _cli(monkeypatch, capsys, "trazar", str(COMPOSICION), "--objetos", "5", str(destino))
    assert rc == 0, out
    assert "Diagrama de objetos del paso 5" in out
    svg = destino.read_text(encoding="utf-8")
    assert ET.fromstring(svg).tag == NS + "svg"
    codigo = COMPOSICION.read_text(encoding="utf-8")
    traza = api.trazar(codigo, COMPOSICION.name, ruta_fuente=str(COMPOSICION))
    assert svg == api.diagrama_objetos(traza, 4, formato="svg", idioma="es")
    assert "=== TRAZA" not in out  # es una exportación: no se imprime el texto


def test_trazar_objects_texto_en_ingles(monkeypatch, capsys, tmp_path):
    destino = tmp_path / "obj.txt"
    rc, out = _cli(
        monkeypatch, capsys, "trace", str(COMPOSICION), "--objects", "3", str(destino),
        "--idioma", "en",
    )
    assert rc == 0, out
    assert "Object diagram of step 3" in out
    assert destino.read_text(encoding="utf-8").startswith("Object diagram of step 3")


@pytest.mark.parametrize("n", ["0", "x", "99999"])
def test_trazar_objetos_paso_fuera_de_rango(monkeypatch, capsys, tmp_path, n):
    rc, out = _cli(
        monkeypatch, capsys, "trazar", str(COMPOSICION), "--objetos", n, str(tmp_path / "o.svg")
    )
    assert rc == 2 and "--objetos:" in out
    assert not (tmp_path / "o.svg").exists()


# ----------------------------------------------------------------- GUI

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")  # noqa: N806 - nombre del módulo Qt
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_visualizador_alterna_al_diagrama_de_objetos(app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from inveniolang.gui_qt import PanelVisualizador

    panel = PanelVisualizador(idioma="es")
    assert not panel.btn_objetos.isEnabled()  # sin traza no hay nada que alternar
    codigo = COMPOSICION.read_text(encoding="utf-8")
    panel.cargar_traza(api.trazar(codigo, COMPOSICION.name).a_dict())
    panel.ir(4)
    paso = panel.traza["pasos"][4]
    assert panel.btn_objetos.isEnabled() and not panel.vista_objetos()

    QTest.keyClick(panel, Qt.Key.Key_O)  # teclado
    assert panel.vista_objetos() and panel.actual == 4
    assert panel.svg_actual() == uml.svg_objetos(paso, "es", tema=panel.tema)
    assert panel.descripcion.toPlainText().startswith(uml.describir_objetos(paso, "es"))
    assert panel.lienzo.renderer().isValid()

    QTest.keyClick(panel, Qt.Key.Key_Right)  # navegar conserva la vista
    assert panel.actual == 5 and panel.vista_objetos()
    assert panel.svg_actual() == uml.svg_objetos(panel.traza["pasos"][5], "es", tema=panel.tema)

    QTest.mouseClick(panel.btn_objetos, Qt.MouseButton.LeftButton)  # ratón
    assert not panel.vista_objetos()
    assert "Diagrama de objetos" not in panel.svg_actual()
    panel.deleteLater()
