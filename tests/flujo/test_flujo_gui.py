"""Panel «Diagrama de flujo» de la GUI Qt sobre el modelo nuevo (INV-3010)."""

from __future__ import annotations

import os

import pytest
from comun import RAIZ, flujo

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QSettings  # noqa: E402

from inveniolang import api  # noqa: E402

BURBUJA = RAIZ / "curriculum" / "es" / "nivel05" / "01_burbuja.inv"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("qs"))
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


def test_panel_elige_subrutina_y_regenera_codigo_en_ingles(ventana):
    ventana._tab_actual().setPlainText(BURBUJA.read_text(encoding="utf-8"))
    ventana.generar_diagrama()
    panel = ventana.panel_flujo
    assert ventana.dock_diagrama.isVisible()
    claves = [panel.combo.itemData(i) for i in range(panel.combo.count())]
    assert claves == ["imprimirArreglo", "intercambiar", "main"] and panel.clave == "main"
    panel.combo.setCurrentIndex(claves.index("intercambiar"))
    assert panel.arbol.topLevelItem(0).childCount() == 3
    assert panel._esquema is not None and panel.escena.items()
    panel.combo_idioma.setCurrentText("en")
    assert panel.modelo.idioma == "en"
    pestanas = ventana.editor_tabs.count()
    codigo = panel.generar_codigo()
    assert ventana.editor_tabs.count() == pestanas + 1
    assert "for (" in codigo
    esperado = BURBUJA.with_suffix(".expected").read_text(encoding="utf-8")
    assert "".join(api.ejecutar(codigo).salida) == esperado


def test_panel_edita_valida_deshace_y_resalta(ventana, tmp_path, monkeypatch):
    from inveniolang.gui import panel_flujo

    avisos = []
    monkeypatch.setattr(panel_flujo.QMessageBox, "warning", lambda *a: avisos.append(a[2]))
    panel = ventana.panel_flujo
    ventana.abrir_constructor_diagrama()
    assert panel.modelo is not None and panel.clave == "main"
    assert panel.insertar_tipo("declaracion", {"texto": "entero s = 0"})
    assert panel.insertar_tipo("escribir", {"texto": "s"})
    assert not panel.insertar_tipo("proceso", {"texto": "s = = 1"})  # rechazado, con aviso
    assert avisos and "«texto»" in avisos[0]
    item = panel.arbol.topLevelItem(0).child(1)
    panel.arbol.setCurrentItem(item)
    item.setSelected(True)
    assert panel.envolver("mientras", {"condicion": "s < 3"})
    cuerpo = panel.modelo.diagrama().cuerpo
    assert [n.tipo for n in cuerpo] == ["declaracion", "mientras"]
    assert panel.lista_problemas.count() == 0
    panel.deshacer()
    assert [n.tipo for n in panel.modelo.diagrama().cuerpo] == ["declaracion", "escribir"]
    assert panel.desplazar(panel.modelo.diagrama().cuerpo[1].id, -1)
    assert panel.modelo.diagrama().cuerpo[0].tipo == "escribir"
    assert panel.lista_problemas.count() > 0  # usa s antes de declararla
    destino = tmp_path / "d.json"
    assert panel.exportar("json", str(destino))
    assert flujo.desde_json(destino.read_text(encoding="utf-8")) == panel.modelo
    for formato in ("svg", "mermaid", "texto"):
        assert panel.exportar(formato, str(tmp_path / f"d.{formato}"))
    panel.cargar_codigo("vacio main() {\n entero x = 1;\n imprimir(x);\n}\n")
    panel.resaltar("main", 3)
    assert panel._resaltado is not None
    ventana._quitar_resaltado_diagrama()
    assert panel._resaltado is None
    assert not panel.cargar_codigo("vacio main() { x = 1; }")
    assert panel.lista_problemas.count() >= 2
