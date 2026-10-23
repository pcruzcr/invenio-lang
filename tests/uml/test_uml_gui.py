"""Panel "Diagrama UML" de la GUI Qt (INV-3214).

Se ejecuta con ``QT_QPA_PLATFORM=offscreen``; QSettings se aísla en un
directorio temporal para no tocar la configuración del usuario.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QSettings  # noqa: E402

from inveniolang import api, uml  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path_factory.mktemp("qsettings")),
    )
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def ventana(app):
    from inveniolang.gui_qt import MainWindow

    w = MainWindow()
    w.show()
    yield w
    for i in range(w.editor_tabs.count()):
        w.editor_tabs.widget(i).modificado = False
    w.close()
    w.deleteLater()


def test_diagrama_del_editor(ventana):
    editor = ventana._tab_actual()
    editor.setPlainText((RAIZ / "curriculum/es/nivel08/06_composicion.inv").read_text("utf-8"))
    assert ventana.generar_uml()
    panel = ventana.panel_uml
    assert ventana.dock_uml.isVisible()
    assert panel.modelo.clasificador("Auto") is not None
    assert panel.svg_actual().startswith("<svg") and panel.lienzo.renderer().isValid()
    assert "Auto se compone de Motor" in panel.descripcion.toPlainText()
    assert panel.editor_puml.toPlainText().startswith("@startuml")
    assert panel.btn_exportar.isEnabled()


def test_errores_del_programa(ventana):
    ventana._tab_actual().setPlainText("clase A hereda Nadie { } vacio main() { }")
    assert not ventana.generar_uml()
    assert "Nadie" in ventana.panel_uml.descripcion.toPlainText()


def test_exportar_por_extension(ventana, tmp_path):
    ventana._tab_actual().setPlainText("clase A { publico entero x; } vacio main() { }")
    assert ventana.generar_uml()
    panel = ventana.panel_uml
    for nombre, inicio in (("d.svg", "<svg"), ("d.puml", "@startuml"), ("d.mmd", "classDiagram"),
                           ("d.txt", "Diagrama de clases")):
        assert panel.exportar(str(tmp_path / nombre)) == str(tmp_path / nombre)
        assert (tmp_path / nombre).read_text("utf-8").startswith(inicio)
    panel.exportar(str(tmp_path / "d.json"))
    assert uml.desde_json((tmp_path / "d.json").read_text("utf-8")) == panel.modelo


def test_generar_esqueleto_abre_pestana(ventana, tmp_path):
    panel = ventana.panel_uml
    puml = tmp_path / "d.puml"
    puml.write_text("class Motor {\n + arrancar() : void\n}\n", encoding="utf-8")
    assert panel.abrir(str(puml))
    assert panel.modelo.clasificador("Motor") is not None
    panel.combo_idioma.setCurrentText("en")
    antes = ventana.editor_tabs.count()
    codigo = panel.generar_esqueleto()
    assert codigo is not None and "class Motor {" in codigo and api.compilar(codigo).ok
    assert ventana.editor_tabs.count() == antes + 1
    assert ventana._tab_actual().toPlainText() == codigo
    panel.editor_puml.setPlainText("class A {\n - hijos : A[]\n}\n")
    assert panel.generar_esqueleto() is None
    assert "arreglos de objetos" in panel.descripcion.toPlainText()


def test_abrir_archivo_ilegible_y_tema(ventana, tmp_path):
    panel = ventana.panel_uml
    malo = tmp_path / "m.puml"
    malo.write_text("class A {\n + x\n}\n", encoding="utf-8")
    assert not panel.abrir(str(malo)) and "línea 2" in panel.descripcion.toPlainText()
    assert not panel.abrir(str(tmp_path / "no.puml"))
    ventana._tab_actual().setPlainText("clase A { } vacio main() { }")
    ventana.generar_uml()
    ventana._aplicar_tema(True)
    assert "#ffffff" in panel.svg_actual()
    ventana._aplicar_tema(False)
    assert "#0d1117" in panel.svg_actual()
