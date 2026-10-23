"""Panel "Visualizador" de la GUI Qt y enganche con el trazador (INV-2231..INV-2233).

Se ejecuta con ``QT_QPA_PLATFORM=offscreen``; la configuración de QSettings
se aísla en un directorio temporal para no tocar la del usuario.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from vis_comun import FIXTURES, cargar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from inveniolang import i18n  # noqa: E402
from inveniolang import visualizacion as vis  # noqa: E402
from inveniolang.visualizacion import traza as traza_mod  # noqa: E402

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


def _esperar(condicion, segundos=20):
    limite = time.monotonic() + segundos
    while not condicion() and time.monotonic() < limite:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
    return condicion()


def test_panel_navega_con_teclado_y_raton_y_resalta_la_linea(ventana):
    t = cargar("arreglo_es")
    editor = ventana._tab_actual()
    editor.setPlainText(t["fuente"])
    ventana.mostrar_traza(t, editor)
    panel = ventana.panel_visualizador
    assert ventana.dock_visualizador.isVisible()
    assert panel.actual == 0 and editor.linea_traza == t["pasos"][0]["linea"]
    assert panel.contador.text() == "Paso 1 de 6"
    assert panel.lienzo.renderer().isValid()
    assert panel.descripcion.toPlainText() == vis.describir(t["pasos"][0], "es")

    QTest.keyClick(panel, Qt.Key.Key_Right)
    assert panel.actual == 1 and editor.linea_traza == t["pasos"][1]["linea"]
    QTest.keyClick(panel.btn_inicio, Qt.Key.Key_Right)  # atajo con el foco en un botón
    assert panel.actual == 2
    QTest.keyClick(panel.deslizador, Qt.Key.Key_End)
    assert panel.actual == 5 and editor.linea_traza == 12
    QTest.keyClick(panel, Qt.Key.Key_Left)
    assert panel.actual == 4
    QTest.keyClick(panel, Qt.Key.Key_Home)
    assert panel.actual == 0 and panel.deslizador.value() == 0

    QTest.mouseClick(panel.btn_siguiente, Qt.MouseButton.LeftButton)
    QTest.mouseClick(panel.btn_siguiente, Qt.MouseButton.LeftButton)
    assert panel.actual == 2
    QTest.mouseClick(panel.btn_fin, Qt.MouseButton.LeftButton)
    assert panel.actual == 5
    panel.deslizador.setValue(3)
    assert panel.actual == 3 and editor.linea_traza == t["pasos"][3]["linea"]
    # la línea resaltada lleva negrita además del fondo (no sólo color)
    sels = editor.extraSelections()
    assert any(
        s.format.fontWeight() >= 700 and s.cursor.blockNumber() == editor.linea_traza - 1
        for s in sels
    )


def test_reproduccion_automatica_y_espacio(ventana):
    panel = ventana.panel_visualizador
    ventana.mostrar_traza(cargar("recursion_en"))
    QTest.keyClick(panel, Qt.Key.Key_Space)
    assert panel.temporizador.isActive() and panel.btn_reproducir.isChecked()
    panel.temporizador.setInterval(5)
    assert _esperar(lambda: not panel.temporizador.isActive())
    assert panel.actual == panel.total() - 1  # se detiene al final
    QTest.keyClick(panel, Qt.Key.Key_Space)  # desde el final vuelve a empezar
    assert panel.actual == 0 and panel.temporizador.isActive()
    QTest.keyClick(panel, Qt.Key.Key_Space)
    assert not panel.temporizador.isActive()


def test_tema_de_la_ventana_llega_al_svg(ventana):
    panel = ventana.panel_visualizador
    ventana.mostrar_traza(cargar("pila_es"))
    ventana._aplicar_tema(True)
    assert panel.tema == "claro" and 'fill="#ffffff" class="f-fondo"' in panel.svg_actual()
    ventana._aplicar_tema(False)
    assert panel.tema == "oscuro" and 'fill="#0d1117" class="f-fondo"' in panel.svg_actual()


def test_abrir_json_y_exportar_html(ventana, tmp_path):
    panel = ventana.panel_visualizador
    assert not panel.btn_exportar.isEnabled()
    assert panel.abrir_json(str(FIXTURES / "grafo_en.json"))
    assert panel.total() == 2 and panel.btn_exportar.isEnabled()
    ruta = panel.exportar_html(str(tmp_path / "t.html"))
    html = open(ruta, encoding="utf-8").read()
    assert html == vis.traza_html(cargar("grafo_en"), panel.idioma)
    malo = tmp_path / "malo.json"
    malo.write_text('{"version": 7}', encoding="utf-8")
    assert not panel.abrir_json(str(malo))
    assert "no contiene una traza válida" in panel.descripcion.toPlainText()


def test_el_panel_traza_el_programa_real_y_navega(ventana):
    """INV-2008: "Trazar" usa visualizacion.traza.trazar real (sin dobles de prueba)."""
    codigo = (RAIZ / "curriculum" / "es" / "nivel05" / "01_burbuja.inv").read_text(encoding="utf-8")
    editor = ventana._tab_actual()
    editor.setPlainText(codigo)
    ventana.entry_input.setText("")
    assert ventana.trazar_programa() is True
    panel = ventana.panel_visualizador
    assert _esperar(lambda: panel.total() > 100, 60)
    ventana._hilo_traza.wait(10000)
    assert panel.traza["idioma"] == "es" and panel.traza["error"] is None
    primera = panel.traza["pasos"][0]["linea"]
    assert editor.linea_traza == primera
    panel.setFocus()
    for _ in range(10):
        QTest.keyClick(panel, Qt.Key.Key_Right)
    assert editor.linea_traza == panel.traza["pasos"][10]["linea"]
    assert "Paso 11" in panel.descripcion.toPlainText()
    QTest.keyClick(panel, Qt.Key.Key_End)
    ultimo = panel.traza["pasos"][-1]
    assert editor.linea_traza == ultimo["linea"]
    arreglos = [e for e in ultimo["estructuras"] if e["forma"] == "arreglo"]
    nodo = ultimo["monticulo"][arreglos[0]["raiz"]] if arreglos else None
    assert nodo is not None and [v["v"] for v in nodo["elementos"]] == [11, 12, 22, 25, 34, 64, 90]
    assert "<svg" in panel.svg_actual()


def test_ruta_del_editor_se_pasa_como_ruta_fuente(ventana, monkeypatch, tmp_path):
    """`importar` resuelve junto al archivo del editor y los errores citan su nombre."""
    (tmp_path / "util.inv").write_text(
        "entero doble(entero x) { retornar x * 2; }", encoding="utf-8"
    )
    llamadas = []
    original = traza_mod.trazar

    def espia(codigo, **kw):
        llamadas.append(kw)
        return original(codigo, **kw)

    monkeypatch.setattr(traza_mod, "trazar", espia)
    editor = ventana._tab_actual()
    editor.ruta = str(tmp_path / "main.inv")
    editor.setPlainText('importar "util";\nvacio main() { imprimir(doble(21)); }\n')
    assert ventana.trazar_programa() is True
    panel = ventana.panel_visualizador
    assert _esperar(lambda: panel.total() > 0, 30)
    ventana._hilo_traza.wait(10000)
    assert llamadas[0]["ruta"] == "main.inv" and llamadas[0]["ruta_fuente"] == editor.ruta
    assert panel.traza["salida"] == ["42"]


def test_error_del_trazador_se_muestra(ventana, monkeypatch):
    def trazar(codigo, **kw):
        raise RuntimeError("límite de tiempo")

    monkeypatch.setattr(traza_mod, "trazar", trazar)
    panel = ventana.panel_visualizador
    assert ventana.trazar_programa() is True
    assert _esperar(lambda: "límite de tiempo" in panel.descripcion.toPlainText())
    ventana._hilo_traza.wait(5000)
    assert panel.descripcion.toPlainText() == i18n.t(
        "VIS.gui.error_trazar", panel.idioma, error="límite de tiempo"
    )
