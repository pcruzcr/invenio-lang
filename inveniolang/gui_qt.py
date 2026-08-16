# gui_qt.py - Interfaz gráfica de InvenioLang en PySide6 (Qt for Python)
# Crecerá hacia un PSeInt moderno: depurador paso a paso, diagramas, etc.

import os

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import (QAction, QColor, QFont, QFontMetrics, QKeySequence,
                           QPainter, QPalette, QShortcut, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor, QTextFormat)
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                               QFileDialog, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter,
                               QStatusBar, QTabWidget, QTextEdit, QVBoxLayout,
                               QWidget)

from .lexer import Lexer
from .parser import Parser
from .errors import ErrorManager
from .semantic import SemanticAnalyzer
from .type_checker import TypeChecker
from .interpreter import ExecutionCancelled, Interpreter
from .docstrings import (EJEMPLOS, _DOC_ATAJOS, _DOC_ERRORES, _DOC_FUNCIONES,
                         _DOC_GUIA, _DOC_REFERENCIA)

# Tema oscuro estilo VS Code
COLORES = {
    'fondo': '#1e1e1e', 'panel': '#252526', 'gutter': '#252526',
    'gutter_borde': '#3c3c3c', 'gutter_linea': '#858585',
    'texto': '#d4d4d4', 'keyword': '#569cd6', 'type': '#4ec9b0',
    'string': '#ce9178', 'comment': '#6a9955', 'number': '#b5cea8',
    'builtin': '#dcdcaa', 'operator': '#d4d4d4',
    'error_sub': '#f48771', 'error_fondo': '#3a2020',
    'warn_sub': '#dcdcaa', 'warn_fondo': '#413f23',
    'linea_activa': '#2a2d2e', 'flash': '#264f78',
}

KEYWORDS = {
    'if', 'si', 'else', 'sino', 'while', 'mientras', 'for', 'para',
    'return', 'break', 'romper', 'continue', 'continuar', 'main',
    'true', 'verdadero', 'false', 'falso', 'const', 'constante',
    'print', 'imprimir', 'read', 'leer',
}
TIPOS = {'int', 'entero', 'float', 'real', 'string', 'texto', 'bool',
         'logico', 'void', 'vacio'}
BUILTINS = {
    'int_a_float', 'float_a_int', 'int_a_texto', 'float_a_texto',
    'texto_a_int', 'texto_a_float', 'bool_a_texto', 'texto_a_bool',
    'int_to_float', 'float_to_int', 'int_to_string', 'float_to_string',
    'string_to_int', 'string_to_float', 'bool_to_string', 'string_to_bool',
    'entero_a_real', 'real_a_entero', 'entero_a_texto', 'real_a_texto',
    'texto_a_entero', 'texto_a_real', 'logico_a_texto', 'texto_a_logico',
}


def _formato(fore, bold=False):
    f = QTextCharFormat()
    f.setForeground(QColor(fore))
    f.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    return f


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Editor con numeración de líneas y resaltado de la línea activa."""

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont('Consolas')
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.setFont(font)
        self.setTabStopDistance(4 * QFontMetrics(font).horizontalAdvance(' '))
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._extra_adicional = []  # selecciones de errores/advertencias
        self._pintar_paleta()
        self._update_line_number_area_width(0)
        self._highlight_current_line()

    def _pintar_paleta(self):
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor(COLORES['fondo']))
        pal.setColor(QPalette.ColorRole.Text, QColor(COLORES['texto']))
        self.setPalette(pal)

    def line_number_area_width(self):
        digits = max(2, len(str(self.blockCount())))
        fm = QFontMetrics(self.font())
        return 14 + fm.horizontalAdvance('9') * digits

    def _update_line_number_area_width(self, _=None):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(),
                                         self.line_number_area.width(),
                                         rect.height())

    def _resize_gutter(self, event):
        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(),
                                          self.line_number_area_width(),
                                          cr.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_gutter(event)

    def set_problemas(self, sels):
        """Establece las selecciones adicionales (errores/advertencias)."""
        self._extra_adicional = list(sels)
        self._highlight_current_line()

    def _highlight_current_line(self):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(COLORES['linea_activa']))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel] + list(self._extra_adicional))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(COLORES['gutter']))
        painter.setPen(QColor(COLORES['gutter_linea']))
        fm = QFontMetrics(self.font())
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(0, int(top),
                                 self.line_number_area.width() - 6,
                                 fm.height(),
                                 Qt.AlignmentFlag.AlignRight,
                                 str(block_number + 1))
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

import re


class _HiloEjecucion(QThread):
    """Ejecuta el intérprete fuera del hilo de la interfaz.

    Mantener la interpretación en el hilo de la ventana la congelaba mientras
    el programa corría: con un ciclo sin terminación, hasta que saltaba el
    límite de IL-EJE-030. Además es la base que necesita el depurador paso a
    paso, que debe poder pausar sin bloquear la interfaz.

    Emite `terminado(salida, error_manager, cancelado, fallo)`.
    """

    terminado = Signal(list, object, bool, object)

    def __init__(self, ast, tabla, error_manager, entrada, parent=None):
        super().__init__(parent)
        self._ast = ast
        self._entrada = entrada
        self._em = error_manager
        self._cancelar = False
        self.interp = Interpreter(error_manager, tabla)
        self.interp.cancelado = lambda: self._cancelar

    def cancelar(self):
        self._cancelar = True

    def run(self):
        salida, cancelado, fallo = [], False, None
        try:
            salida = self.interp.interpretar(self._ast, self._entrada,
                                             usar_stdin=False)
        except ExecutionCancelled:
            cancelado = True
            salida = list(self.interp.salida)
        except Exception as e:                      # pragma: no cover
            fallo = str(e)
        self.terminado.emit(list(salida), self._em, cancelado, fallo)


class InvenioHighlighter(QSyntaxHighlighter):
    """Resaltado sintáctico de InvenioLang."""

    def __init__(self, document):
        super().__init__(document)
        self.fmt_keyword = _formato(COLORES['keyword'], bold=True)
        self.fmt_type = _formato(COLORES['type'])
        self.fmt_builtin = _formato(COLORES['builtin'])
        self.fmt_number = _formato(COLORES['number'])
        self.fmt_string = _formato(COLORES['string'])
        self.fmt_comment = _formato(COLORES['comment'])
        self._kw = re.compile(r'\b(' + '|'.join(sorted(KEYWORDS)) + r')\b')
        self._tp = re.compile(r'\b(' + '|'.join(sorted(TIPOS)) + r')\b')
        self._bl = re.compile(r'\b(' + '|'.join(sorted(BUILTINS)) + r')\b')
        self._num = re.compile(r'\b\d+\.\d+([eE][+-]?\d+)?\b|\b\d+\b')
        self._str = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'')
        self._coment = re.compile(r'//[^\n]*')

    def highlightBlock(self, text):
        self._comentario_bloque(text)
        for m in self._str.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_string)
        for m in self._num.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_number)
        for m in self._kw.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_keyword)
        for m in self._tp.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_type)
        for m in self._bl.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_builtin)
        for m in self._coment.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_comment)

    def _comentario_bloque(self, text):
        self.setCurrentBlockState(0)
        if self.previousBlockState() == 1:
            start = 0
        else:
            start = text.find('/*')
            if start < 0:
                return
        end = text.find('*/', start + 2)
        if end >= 0:
            self.setFormat(start, end + 2 - start, self.fmt_comment)
            self.setCurrentBlockState(0)
        else:
            self.setFormat(start, len(text) - start, self.fmt_comment)
            self.setCurrentBlockState(1)

def _crear_panel(parent=None, read_only=True):
    """Crea un QPlainTextEdit de solo lectura con el tema oscuro."""
    t = QPlainTextEdit(parent)
    if read_only:
        t.setReadOnly(True)
    t.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    pal = t.palette()
    pal.setColor(QPalette.ColorRole.Base, QColor(COLORES['panel']))
    pal.setColor(QPalette.ColorRole.Text, QColor(COLORES['texto']))
    t.setPalette(pal)
    return t


class ErrorTextEdit(QPlainTextEdit):
    """Panel de errores/advertencias que emite el número de línea clicado."""

    clicked_line = Signal(int)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            self.clicked_line.emit(cursor.block().blockNumber() + 1)
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.archivo_actual = None
        self.modificado = False
        self._cargando = False
        self._errores_actuales = []
        self._idx_error = 0
        # Ejecucion en hilo aparte (véase _HiloEjecucion)
        self._worker = None
        self.accion_ejecutar = None
        self.accion_detener = None

        self._job_en_vivo = QTimer(self)
        self._job_en_vivo.setSingleShot(True)
        self._job_en_vivo.setInterval(500)
        self._job_en_vivo.timeout.connect(self._analizar_en_vivo)

        self.setWindowTitle("InvenioLang 1.0 - Compilador Educativo")
        self.resize(1000, 720)
        self._build_ui()
        self._build_menu()
        self._apply_qss()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Listo")
        self._register_shortcuts()

    def _build_ui(self):
        self.editor = CodeEditor()
        self.highlighter = InvenioHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._on_edit)

        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.addWidget(QLabel("Entrada (simulada):"))
        self.entry_input = QLineEdit()
        lay.addWidget(self.entry_input, 1)
        btn = QPushButton("Ejecutar")
        btn.clicked.connect(self.ejecutar)
        lay.addWidget(btn)
        btn2 = QPushButton("Limpiar")
        btn2.clicked.connect(self.limpiar_resultados)
        lay.addWidget(btn2)

        self.tabs = QTabWidget()
        self.texto_salida = _crear_panel()
        self.texto_errores = ErrorTextEdit()
        self.texto_errores.clicked_line.connect(self._al_hacer_click_error)
        self.texto_warn = ErrorTextEdit()
        self.tabs.addTab(self.texto_salida, "Salida")
        self.tabs.addTab(self.texto_errores, "Errores")
        self.tabs.addTab(self.texto_warn, "Advertencias")

        container = QWidget()
        cv = QVBoxLayout(container)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.addWidget(row)
        cv.addWidget(self.tabs, 1)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.editor)
        split.addWidget(container)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        self.setCentralWidget(split)

    def _accion(self, texto, atajo, fn, menu):
        a = QAction(texto, self)
        if atajo:
            a.setShortcut(atajo)
        a.triggered.connect(lambda: fn())
        menu.addAction(a)
        return a

    def _build_menu(self):
        mb = self.menuBar()

        m = mb.addMenu("Archivo")
        self._accion("Nuevo", QKeySequence.StandardKey.New, self.nuevo_archivo, m)
        self._accion("Abrir...", QKeySequence.StandardKey.Open, self.abrir_archivo, m)
        self._accion("Guardar", QKeySequence.StandardKey.Save, self.guardar_archivo, m)
        self._accion("Guardar como...", None, self.guardar_como, m)
        m.addSeparator()
        self._accion("Salir", None, self.close, m)

        me = mb.addMenu("Ejecutar")
        self.accion_ejecutar = self._accion("Ejecutar", QKeySequence("Ctrl+R"),
                                            self.ejecutar, me)
        self.accion_detener = self._accion("Detener", QKeySequence("Ctrl+."),
                                           self.detener, me)
        self.accion_detener.setEnabled(False)
        me.addSeparator()
        self._accion("Revisar (estático)", None, self.revisar, me)
        self._accion("Mostrar Tokens", None, self.mostrar_tokens, me)
        self._accion("Mostrar AST", None, self.mostrar_ast, me)

        ay = mb.addMenu("Ayuda")
        self._accion("Documentación (F1)", "F1", self._abrir_documentacion, ay)
        self._accion("Guía rápida", None,
                     lambda: self._mostrar_ayuda("Guía rápida", _DOC_GUIA), ay)
        self._accion("Referencia del lenguaje", None,
                     lambda: self._mostrar_ayuda("Referencia del lenguaje",
                                                 _DOC_REFERENCIA), ay)
        self._accion("Funciones integradas", None,
                     lambda: self._mostrar_ayuda("Funciones integradas",
                                                 _DOC_FUNCIONES), ay)
        self._accion("Catálogo de errores", None,
                     lambda: self._mostrar_ayuda("Catálogo de errores",
                                                 _DOC_ERRORES), ay)
        self._accion("Atajos de teclado", None,
                     lambda: self._mostrar_ayuda("Atajos de teclado",
                                                 _DOC_ATAJOS), ay)
        ay.addSeparator()
        subm = ay.addMenu("Ejemplos")
        for nombre in EJEMPLOS:
            a = QAction(nombre, self)
            a.triggered.connect(lambda _=False, n=nombre: self._cargar_ejemplo(n))
            subm.addAction(a)
        ay.addSeparator()
        self._accion("Acerca de", None, self.mostrar_acerca, ay)

    def _register_shortcuts(self):
        QShortcut(QKeySequence("F8"), self, activated=lambda: self._siguiente_error(1))
        QShortcut(QKeySequence("Shift+F8"), self, activated=lambda: self._siguiente_error(-1))
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self._ir_a_linea)
        QShortcut(QKeySequence("F1"), self, activated=self._abrir_documentacion)

    def _apply_qss(self):
        self.setStyleSheet(
            f"QMainWindow, QDialog {{ background: {COLORES['fondo']}; }}\n"
            f"QPlainTextEdit {{ background: {COLORES['fondo']}; "
            f"color: {COLORES['texto']}; border: 1px solid {COLORES['gutter_borde']}; }}\n"
            f"QStatusBar, QTabWidget::pane {{ background: {COLORES['panel']}; }}"
        )

    # ============================================================
    # Operaciones de archivo y ejecución
    # ============================================================

    def _on_edit(self):
        if self._cargando:
            return
        self.modificado = True
        if not self.windowTitle().startswith('*'):
            self.setWindowTitle('* ' + self.windowTitle())
        self._job_en_vivo.start()

    def nuevo_archivo(self):
        if self.modificado:
            if QMessageBox.question(self, "Confirmar", "Descarta los cambios actuales?") \
                    != QMessageBox.StandardButton.Yes:
                return
        self._cargando = True
        self.editor.clear()
        self._cargando = False
        self.archivo_actual = None
        self.modificado = False
        self.setWindowTitle("InvenioLang 1.0 - [Sin título]")
        self.statusBar().showMessage("Nuevo archivo")

    def abrir_archivo(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir archivo InvenioLang", "",
            "Archivos InvenioLang (*.inv);;Todos (*.*)")
        if not ruta:
            return
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                codigo = f.read()
        except UnicodeDecodeError as e:
            # §2.1: un archivo que no sea UTF-8 valido se rechaza con el codigo
            # del catalogo, el mismo que daria la CLI.
            QMessageBox.critical(
                self, "Codificación inválida",
                f"[IL-LEX-001] {os.path.basename(ruta)}\n\n"
                f"El archivo no está codificado en UTF-8 válido "
                f"(byte inválido en la posición {e.start}).\n\n"
                f"InvenioLang exige archivos fuente en UTF-8.")
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el archivo:\n{e}")
            return
        self._cargando = True
        self.editor.setPlainText(codigo)
        self._cargando = False
        self.editor.document().setModified(False)
        self.archivo_actual = ruta
        self.modificado = False
        self.setWindowTitle(f"InvenioLang 1.0 - {os.path.basename(ruta)}")
        self.statusBar().showMessage(f"Abierto: {ruta}")
        self._analizar_en_vivo()

    def guardar_archivo(self):
        if self.archivo_actual:
            try:
                with open(self.archivo_actual, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())
                self.modificado = False
                self.editor.document().setModified(False)
                self.setWindowTitle(self.windowTitle().lstrip('* '))
                self.statusBar().showMessage(f"Guardado: {self.archivo_actual}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")
        else:
            self.guardar_como()

    def guardar_como(self):
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar archivo InvenioLang", "",
            "Archivos InvenioLang (*.inv);;Todos (*.*)")
        if not ruta:
            return
        if not ruta.lower().endswith('.inv'):
            ruta += '.inv'
        try:
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.archivo_actual = ruta
            self.modificado = False
            self.setWindowTitle(f"InvenioLang 1.0 - {os.path.basename(ruta)}")
            self.statusBar().showMessage(f"Guardado: {ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    def ejecutar(self):
        codigo = self.editor.toPlainText().strip()
        if not codigo:
            QMessageBox.warning(self, "Advertencia", "El editor está vacío")
            return
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "En ejecución",
                                    "Ya hay un programa ejecutándose. "
                                    "Use Detener para interrumpirlo.")
            return
        entrada_str = self.entry_input.text().strip()
        entrada = entrada_str.split() if entrada_str else None
        nombre = self.archivo_actual or "<sin_titulo>"
        self.statusBar().showMessage("Compilando...")

        em = ErrorManager()
        lexer = Lexer(em)
        lexer.tokenizar(codigo, nombre)
        if em.hay_errores():
            self._mostrar_errores(em); self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error léxico"); return
        parser = Parser(lexer, em)
        ast, em = parser.analizar(codigo, nombre)
        if em.hay_errores():
            self._mostrar_errores(em); self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error sintáctico"); return
        semantico = SemanticAnalyzer(em)
        tabla = semantico.analizar(ast)
        if em.hay_errores():
            self._mostrar_errores(em); self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error semántico"); return
        if em.warnings:
            self._mostrar_advertencias(em)
        tc = TypeChecker(em, tabla)
        tc.verificar(ast)
        if em.hay_errores():
            self._mostrar_errores(em); self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error de tipos"); return

        # La interpretación corre en un hilo aparte para que la ventana no se
        # congele con un programa lento o con un ciclo sin terminación, y para
        # que el botón Detener pueda interrumpirlo.
        self._worker = _HiloEjecucion(ast, tabla, em, entrada, self)
        self._worker.terminado.connect(self._al_terminar_ejecucion)
        self._marcar_ejecutando(True)
        self.statusBar().showMessage("Ejecutando...")
        self._worker.start()

    def detener(self):
        """Interrumpe el programa en ejecución (cancelación cooperativa)."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancelar()
            self.statusBar().showMessage("Deteniendo...")

    def _marcar_ejecutando(self, activo):
        """Habilita o deshabilita las acciones según haya ejecución en curso."""
        if self.accion_ejecutar is not None:
            self.accion_ejecutar.setEnabled(not activo)
        if self.accion_detener is not None:
            self.accion_detener.setEnabled(activo)

    def _al_terminar_ejecucion(self, salida, em, cancelado, fallo):
        self._marcar_ejecutando(False)
        self._worker = None
        if fallo:
            self._agregar_panel(self.texto_errores, f"Error inesperado: {fallo}\n")
            self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error de ejecución")
            return
        if cancelado:
            self.texto_salida.setPlainText(
                ''.join(salida) + "\n\n--- Ejecución detenida por el usuario ---")
            self.tabs.setCurrentIndex(0)
            self.statusBar().showMessage("Ejecución detenida")
            return
        if em.hay_errores():
            self._mostrar_errores(em)
            self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error de ejecución")
            return
        self.texto_salida.setPlainText(''.join(salida))
        self.tabs.setCurrentIndex(0)
        self.statusBar().showMessage("Ejecución exitosa")

    def revisar(self):
        """Análisis estático completo sin ejecutar (como el CLI --check)."""
        codigo = self.editor.toPlainText().strip()
        if not codigo:
            return
        nombre = self.archivo_actual or "<sin_titulo>"
        em = ErrorManager()
        lexer = Lexer(em)
        lexer.tokenizar(codigo, nombre)
        if not em.hay_errores():
            parser = Parser(lexer, em)
            ast, em = parser.analizar(codigo, nombre)
            if ast is not None and not em.hay_errores():
                sem = SemanticAnalyzer(em)
                tabla = sem.analizar(ast)
                if not em.hay_errores():
                    tc = TypeChecker(em, tabla)
                    tc.verificar(ast)
        lineas = [f"=== ANÁLISIS ESTÁTICO: {nombre} ==="]
        if em.errores:
            lineas.append("ERRORES:")
            lineas += ["  " + r for r in em.obtener_reportes()]
        if em.warnings:
            lineas.append("ADVERTENCIAS:")
            lineas += ["  " + a for a in em.obtener_advertencias()]
        n_err, n_warn = len(em.errores), len(em.warnings)
        lineas.append(("OK" if n_err == 0 else "ERROR") +
                      f" - {n_err} error(es), {n_warn} advertencia(s)")
        self._errores_actuales = list(em.errores)
        self.texto_salida.setPlainText("\n".join(lineas))
        self.tabs.setCurrentIndex(0)
        self.statusBar().showMessage("Revisión estática completada")

    def limpiar_resultados(self):
        for t in (self.texto_salida, self.texto_errores, self.texto_warn):
            t.clear()
        self._errores_actuales = []
        self._limpiar_marcadores()
        self.statusBar().showMessage("Resultados limpiados")

    def _mostrar_errores(self, em):
        # obtener_reportes() ya devuelve las cadenas formateadas (§15.8.1)
        self.texto_errores.setPlainText("\n".join(em.obtener_reportes()))
        self._errores_actuales = list(em.errores)

    def _mostrar_advertencias(self, em):
        self.texto_warn.setPlainText("\n".join(em.obtener_advertencias()))

    def _agregar_panel(self, widget, texto):
        widget.setPlainText(widget.toPlainText() + texto)

    # ============================================================
    # Análisis en vivo y marcado de problemas (estilo IDE)
    # ============================================================

    def _limpiar_marcadores(self):
        self.editor.set_problemas([])

    def _char_pos(self, linea, col):
        doc = self.editor.document()
        block = doc.findBlockByNumber(max(linea - 1, 0))
        fin = block.position() + max(block.length() - 1, 0)
        return min(block.position() + max(col - 1, 0), fin)

    def _longitud_token(self, linea, col):
        doc = self.editor.document()
        block = doc.findBlockByNumber(max(linea - 1, 0))
        texto = block.text()
        c = max(col - 1, 0)
        if c < 0 or c >= len(texto):
            return 1
        i = c
        while i < len(texto) and not texto[i].isspace() \
                and texto[i] not in ';{}()[],+-*/%=<>&|!':
            i += 1
        return max(i - c, 1)

    def _marcar_problemas(self, errores, warnings):
        problema = []

        for err, es_error in [(e, True) for e in errores] + [(w, False) for w in warnings]:
            linea, col = err.linea, max(err.columna - 1, 0)
            start = self._char_pos(linea, col)
            end = start + self._longitud_token(linea, col)
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            if es_error:
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                fmt.setUnderlineColor(QColor(COLORES['error_sub']))
                fmt.setBackground(QColor(COLORES['error_fondo']))
            else:
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DashUnderline)
                fmt.setUnderlineColor(QColor(COLORES['warn_sub']))
                fmt.setBackground(QColor(COLORES['warn_fondo']))
            sel.format = fmt
            sel.cursor = QTextCursor(self.editor.document())
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            problema.append(sel)
        self.editor.set_problemas(problema)

    def _analizar_en_vivo(self):
        codigo = self.editor.toPlainText()
        if not codigo.strip():
            self._errores_actuales = []
            self._limpiar_marcadores()
            self.statusBar().showMessage("Listo")
            return
        em = ErrorManager()
        try:
            lexer = Lexer(em)
            lexer.tokenizar(codigo, '<en_vivo>')
            if not em.hay_errores():
                parser = Parser(lexer, em)
                ast, em = parser.analizar(codigo, '<en_vivo>')
                if ast is not None and not em.hay_errores():
                    sem = SemanticAnalyzer(em)
                    tabla = sem.analizar(ast)
                    if not em.hay_errores():
                        tc = TypeChecker(em, tabla)
                        tc.verificar(ast)
        except Exception:
            pass
        self._errores_actuales = list(em.errores)
        self._marcar_problemas(em.errores, em.warnings)
        n_err, n_warn = len(em.errores), len(em.warnings)
        if n_err or n_warn:
            self.statusBar().showMessage(f"Errores: {n_err}  Advertencias: {n_warn}")
        else:
            self.statusBar().showMessage("Sin problemas")

    def _saltar_a_linea(self, linea, col=1):
        doc = self.editor.document()
        block = doc.findBlockByNumber(max(linea - 1, 0))
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + max(col - 1, 0))
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        QTimer.singleShot(700, self._analizar_en_vivo)

    def _al_hacer_click_error(self, lin):
        if 0 < lin <= len(self._errores_actuales):
            err = self._errores_actuales[lin - 1]
            self._saltar_a_linea(err.linea, err.columna)

    def _siguiente_error(self, delta):
        if not self._errores_actuales:
            self.statusBar().showMessage("No hay errores para navegar")
            return
        n = len(self._errores_actuales)
        self._idx_error = (self._idx_error + delta) % n
        err = self._errores_actuales[self._idx_error]
        self._saltar_a_linea(err.linea, err.columna)

    def _ir_a_linea(self):
        num, ok = QInputDialog.getInt(self, "Ir a línea", "Número de línea:",
                                      1, 1, 10 ** 7)
        if ok:
            self._saltar_a_linea(num)

    # ============================================================
    # Tokens / AST
    # ============================================================

    def mostrar_tokens(self):
        codigo = self.editor.toPlainText()
        if not codigo.strip():
            return
        nombre = self.archivo_actual or "<sin_titulo>"
        em = ErrorManager()
        lexer = Lexer(em)
        toks = lexer.tokenizar(codigo, nombre)
        lineas = [f"{t[0]:20s} {repr(t[1]):30s} L{t[2]}:C{t[3]}" for t in toks]
        if em.hay_errores():
            lineas += ["\n--- ERRORES LÉXICOS ---"] + em.obtener_reportes()
        self.texto_salida.setPlainText("\n".join(lineas))
        self.tabs.setCurrentIndex(0)

    def _ast_a_texto(self, nodo, nivel):
        if nodo is None:
            return "  " * nivel + "None\n"
        linea = "  " * nivel + nodo.__class__.__name__
        if getattr(nodo, 'nombre', None):
            linea += f"({nodo.nombre})"
        if hasattr(nodo, 'tipo_retorno'):
            linea += f" : {nodo.tipo_retorno}"
        elif isinstance(getattr(nodo, 'tipo', None), str):
            linea += f" : {nodo.tipo}"
        res = linea + "\n"
        for attr in ('elementos', 'bloque', 'declaraciones_globales',
                     'declaraciones_posteriores', 'subrutinas', 'main'):
            v = getattr(nodo, attr, None)
            if isinstance(v, list):
                for e in v:
                    res += self._ast_a_texto(e, nivel + 1)
            elif v is not None:
                res += self._ast_a_texto(v, nivel + 1)
        return res

    def mostrar_ast(self):
        codigo = self.editor.toPlainText()
        if not codigo.strip():
            return
        nombre = self.archivo_actual or "<sin_titulo>"
        em = ErrorManager()
        lexer = Lexer(em)
        parser = Parser(lexer, em)
        ast, _ = parser.analizar(codigo, nombre)
        self.texto_salida.setPlainText(self._ast_a_texto(ast, 0) if ast
                                       else "No se pudo generar el AST\n")
        self.tabs.setCurrentIndex(0)

    # ============================================================
    # Ayuda y documentación
    # ============================================================

    def _crear_dialogo(self, titulo):
        d = QDialog(self)
        d.setWindowTitle(titulo)
        d.resize(700, 520)
        lay = QVBoxLayout(d)
        return d, lay

    def _panel_ro(self, d):
        t = _crear_panel(d)
        return t

    def _mostrar_ayuda(self, titulo, contenido):
        d, lay = self._crear_dialogo(titulo)
        t = self._panel_ro(d)
        t.setPlainText(contenido)
        lay.addWidget(t, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(d.reject)
        bb.clicked.connect(d.accept)
        lay.addWidget(bb)
        d.exec()

    def _abrir_documentacion(self):
        d, lay = self._crear_dialogo("InvenioLang - Documentación y Ayuda")
        tabs = QTabWidget()
        for titulo, contenido in [("Guía rápida", _DOC_GUIA),
                                  ("Referencia", _DOC_REFERENCIA),
                                  ("Funciones integradas", _DOC_FUNCIONES),
                                  ("Catálogo de errores", _DOC_ERRORES),
                                  ("Atajos", _DOC_ATAJOS)]:
            p = self._panel_ro(d)
            p.setPlainText(contenido)
            tabs.addTab(p, titulo)
        lay.addWidget(tabs, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(d.reject)
        bb.clicked.connect(d.accept)
        lay.addWidget(bb)
        d.exec()

    def _cargar_ejemplo(self, nombre):
        base = os.path.dirname(os.path.abspath(__file__))
        ruta = os.path.join(base, '..', 'pruebas', f'{nombre}.inv')
        if not os.path.exists(ruta):
            QMessageBox.critical(self, "Ejemplo", f"No se encontró el ejemplo: {nombre}")
            return
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                codigo = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Ejemplo", f"No se pudo leer:\n{e}")
            return
        if self.modificado and self.editor.toPlainText().strip():
            if QMessageBox.question(self, "Confirmar",
                                    "Se reemplazará el contenido actual. Continuar?") \
                    != QMessageBox.StandardButton.Yes:
                return
        self._cargando = True
        self.editor.setPlainText(codigo)
        self._cargando = False
        self.editor.document().setModified(False)
        self.archivo_actual = os.path.abspath(ruta)
        self.modificado = False
        self.setWindowTitle(f"InvenioLang 1.0 - {nombre}.inv")
        self.statusBar().showMessage(f"Ejemplo cargado: {nombre}.inv")
        self._analizar_en_vivo()

    def mostrar_acerca(self):
        QMessageBox.about(
            self, "Acerca de InvenioLang 1.0",
            "InvenioLang 1.0 - Compilador Educativo\n"
            "Curso: TIIT2002.2 Lenguajes Formales II\n"
            "Universidad Invenio\n"
            "Profesor: Donny Núñez del Rosario\n\n"
            "Implementado con Python, PLY y PySide6 (Qt for Python)")


def main():
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == '__main__':
    import sys
    sys.exit(main())
