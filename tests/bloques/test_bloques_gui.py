"""Panel «Bloques» de la GUI Qt (INV-4012): arrastrar y soltar, teclado y sincronía."""

from __future__ import annotations

import os

import pytest
from comun_bloques import TODO, bloques

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QDragMoveEvent, QDropEvent  # noqa: E402

from inveniolang.gui.panel_bloques import (  # noqa: E402
    PanelBloques,
    mime_bloque,
    mime_paleta,
)

SENCILLO = "vacio main() {\n    entero x = 1;\n    imprimir(x);\n}\n"
_NADA = Qt.KeyboardModifier.NoModifier


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("qs"))
    )
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(app):
    p = PanelBloques()
    p.resize(1200, 800)
    p.show()
    yield p
    p.close()
    p.deleteLater()


def _zona(panel, padre, parte, indice=None):
    return next(
        z for z in panel.diseno.zonas
        if z.padre == padre and z.parte == parte and (indice is None or z.indice == indice)
    )


def _soltar_con_raton(panel, datos, zona):
    """Simula el final de un arrastre real: dragMove + drop sobre el centro de la zona.

    ``datos`` debe seguir referenciado mientras duran los eventos (lo es: es
    un parámetro de esta función).
    """
    punto = panel.lienzo.mapFromScene(QPointF(zona.x + zona.w / 2, zona.y + zona.h / 2))
    acciones = Qt.DropAction.MoveAction | Qt.DropAction.CopyAction
    mover = QDragMoveEvent(QPoint(punto), acciones, datos, Qt.MouseButton.LeftButton, _NADA)
    panel.lienzo.dragMoveEvent(mover)
    aceptado_al_mover = mover.isAccepted()
    soltar = QDropEvent(QPointF(punto), acciones, datos, Qt.MouseButton.LeftButton, _NADA)
    panel.lienzo.dropEvent(soltar)
    return aceptado_al_mover, soltar.isAccepted()


def test_arrastrar_desde_la_paleta_y_entre_huecos(panel):
    generado = []
    panel.codigo_generado.connect(generado.append)
    assert panel.cargar_codigo(SENCILLO)
    main = panel.modelo.programa[0]
    # Los datos del arrastre los produce la propia paleta (como al arrastrar con el ratón).
    item = next(
        panel.paleta.topLevelItem(i).child(j)
        for i in range(panel.paleta.topLevelItemCount())
        for j in range(panel.paleta.topLevelItem(i).childCount())
        if panel.paleta.topLevelItem(i).child(j).data(0, Qt.ItemDataRole.UserRole) == "imprimir"
    )
    datos = panel.paleta.mimeData([item])
    assert _soltar_con_raton(panel, datos, _zona(panel, main.id, "cuerpo", 2)) == (True, True)
    nuevo = panel.modelo.programa[0].listas["cuerpo"][2]
    assert panel.foco == nuevo.id and "imprimir" in panel.estado.text().lower()
    assert _soltar_con_raton(panel, mime_paleta("texto"), _zona(panel, nuevo.id, "valor"))[1]
    texto = panel.modelo.programa[0].listas["cuerpo"][2].huecos["valor"]
    panel.editar_campos(texto.id, {"valor": '"fin"'})
    assert generado and generado[-1].endswith('imprimir("fin");\n}\n')
    # Mover con el ratón el valor «x» del primer imprimir a la declaración no cabe…
    x = panel.modelo.programa[0].listas["cuerpo"][1].huecos["valor"]
    decl = panel.modelo.programa[0].listas["cuerpo"][0]
    assert _soltar_con_raton(panel, mime_bloque(x.id), _zona(panel, decl.id, "valor"))[1] is False
    # …y un texto no encaja en el hueco de una condición: rechazo con motivo bilingüe.
    panel.aplicar(lambda m: bloques.insertar(m, bloques.nuevo_bloque("mientras"),
                                             bloques.Destino(main.id, "cuerpo")))
    ciclo = panel.modelo.programa[0].listas["cuerpo"][-1]
    aceptado = _soltar_con_raton(panel, mime_paleta("texto"), _zona(panel, ciclo.id, "condicion"))
    assert aceptado == (False, False)
    assert "lógico" in panel.estado.text()


def test_papelera_y_deshacer_rehacer(panel):
    panel.cargar_codigo(SENCILLO)
    imp = panel.modelo.programa[0].listas["cuerpo"][1].id
    from PySide6.QtGui import QDropEvent as Drop

    datos = mime_bloque(imp)  # el evento no se adueña de los datos: hay que mantenerlos vivos
    ev = Drop(QPointF(5, 5), Qt.DropAction.MoveAction, datos, Qt.MouseButton.LeftButton, _NADA)
    panel.papelera.dropEvent(ev)
    assert ev.isAccepted()
    assert len(panel.modelo.programa[0].listas["cuerpo"]) == 1
    panel.deshacer()
    assert len(panel.modelo.programa[0].listas["cuerpo"]) == 2
    panel.rehacer()
    assert len(panel.modelo.programa[0].listas["cuerpo"]) == 1


def test_teclado_completo(panel):
    """Recorrer, recoger y soltar, insertar desde la paleta, duplicar, borrar, zoom."""
    panel.cargar_codigo(SENCILLO)
    panel.lienzo.setFocus()
    orden = [c.id for c in panel.diseno.todas()]
    panel.tecla(Qt.Key.Key_Down, _NADA)
    assert panel.foco == orden[0]
    panel.tecla(Qt.Key.Key_Right, _NADA)
    assert panel.foco == orden[1]  # primera hija: la declaración
    assert "declarar" in panel.estado.text().lower()
    panel.tecla(Qt.Key.Key_Left, _NADA)
    assert panel.foco == orden[0]
    # Mover con el teclado: la declaración al final del cuerpo.
    decl = orden[1]
    panel.seleccionar(decl)
    panel.tecla(Qt.Key.Key_M, _NADA)
    assert panel._colocando == ("mover", decl)
    destino = next(k for k, z in enumerate(panel._zonas_validas)
                   if z.parte == "cuerpo" and z.indice == 2)
    for _ in range(destino - panel._zona_actual):
        panel.tecla(Qt.Key.Key_Down, _NADA)
    panel.tecla(Qt.Key.Key_Return, _NADA)
    assert [b.tipo for b in panel.modelo.programa[0].listas["cuerpo"]] == ["imprimir", "declarar"]
    panel.deshacer()
    # Insertar desde la paleta sólo con el teclado (buscar + Intro + flechas + Intro).
    panel.tecla(Qt.Key.Key_Insert, _NADA)
    panel.buscar.setText("imprimir")
    panel._primera_de_paleta()
    panel.paleta.itemActivated.emit(panel.paleta.currentItem(), 0)
    assert panel._colocando == ("paleta", "imprimir")
    panel.tecla(Qt.Key.Key_Down, _NADA)
    panel.tecla(Qt.Key.Key_Up, _NADA)
    assert "Soltar en" in panel.estado.text() or "Drop in" in panel.estado.text()
    panel.tecla(Qt.Key.Key_Return, _NADA)
    assert panel._colocando is None
    assert sum(b.tipo == "imprimir" for b in bloques.recorrer(panel.modelo.programa)) == 2
    panel.buscar.setText("")
    # Duplicar y eliminar con el teclado.
    panel.seleccionar(panel.modelo.programa[0].listas["cuerpo"][0].id)
    antes = len(panel.modelo.programa[0].listas["cuerpo"])
    panel.tecla(Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    assert len(panel.modelo.programa[0].listas["cuerpo"]) == antes + 1
    panel.tecla(Qt.Key.Key_Delete, _NADA)
    assert len(panel.modelo.programa[0].listas["cuerpo"]) == antes
    escala = panel._escala
    panel.tecla(Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier)
    assert panel._escala > escala
    panel.tecla(Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    assert abs(panel._escala - 1.0) < 1e-9


def test_romper_sin_destino_se_cancela(panel):
    panel.cargar_codigo(SENCILLO)
    panel.empezar_colocacion(("paleta", "romper"))
    assert panel._colocando is None and panel._zonas_validas == []


def test_ejecutar_traducir_y_guardar(panel, tmp_path):
    panel.cargar_codigo(TODO)
    panel.entrada.setText("3")
    assert panel.ejecutar()
    assert panel.salida.toPlainText()
    pedidos = []
    panel.trazar_codigo.connect(lambda codigo, entrada: pedidos.append(entrada))
    assert panel.paso_a_paso() and pedidos == [("3",)]
    panel.combo_idioma.setCurrentText("en")
    assert panel.modelo.idioma == "en"
    ruta = tmp_path / "b.json"
    assert panel.guardar_json(str(ruta))
    panel.nuevo()
    assert panel.abrir_json(str(ruta)) and panel.modelo.idioma == "en"
    panel.establecer_tema(True)
    assert panel.lienzo.escena.backgroundBrush().color().name().upper() == "#FFFFFF"


def test_ventana_sincroniza_editor_flujo_y_bloques(app):
    from inveniolang.gui_qt import MainWindow

    w = MainWindow()
    w.show()
    try:
        editor = w._tab_actual() or w._nueva_pestana()
        editor.setPlainText(SENCILLO)
        w.mostrar_bloques()
        pb = w.panel_bloques
        assert pb.modelo is not None and w.panel_flujo.modelo is not None
        main = pb.modelo.programa[0]
        _soltar_con_raton(pb, mime_paleta("imprimir"), _zona(pb, main.id, "cuerpo", 2))
        nuevo = pb.modelo.programa[0].listas["cuerpo"][2]
        _soltar_con_raton(pb, mime_paleta("numero"), _zona(pb, nuevo.id, "valor"))
        assert editor.toPlainText().endswith("imprimir(0);\n}\n")
        # El diagrama de flujo es la misma estructura, con los mismos ids.
        ids_flujo = [n.id for n in w.panel_flujo.modelo.diagramas()[0].cuerpo]
        assert ids_flujo == [b.id for b in pb.modelo.programa[0].listas["cuerpo"]]
        # Elegir un bloque lleva el cursor del editor a su línea y su caja al diagrama.
        imp = pb.modelo.programa[0].listas["cuerpo"][1].id
        pb.seleccionar(imp)
        assert editor.textCursor().blockNumber() + 1 == 3
        assert w.panel_flujo.arbol.currentItem().data(0, Qt.ItemDataRole.UserRole)[1] == imp
        # Editor → bloques: cambiar el código recarga los bloques.
        editor.setPlainText(SENCILLO.replace("imprimir(x);", "imprimir(x + 1);"))
        w._analizar_en_vivo(editor)
        assert pb.modelo.programa[0].listas["cuerpo"][1].huecos["valor"].tipo == "binaria"
        # Mover el cursor del editor elige el bloque de esa línea.
        cursor = editor.textCursor()
        cursor.setPosition(editor.document().findBlockByNumber(1).position())
        editor.setTextCursor(cursor)
        assert pb.foco == pb.modelo.programa[0].listas["cuerpo"][0].id
        # Paso a paso desde los bloques: el Visualizador recibe la traza.
        assert pb.paso_a_paso()
        assert w.dock_visualizador.isVisible()
        w._aplicar_tema(True)
    finally:
        for i in range(w.editor_tabs.count()):
            w.editor_tabs.widget(i).modificado = False
        w.close()
        w.deleteLater()
