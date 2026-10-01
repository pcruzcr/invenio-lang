# gui_qt.py - Interfaz gráfica de InvenioLang en PySide6 (Qt for Python)
#
# IDE estilo VS Code: pestañas multi-archivo, explorador de archivos,
# depurador visual con breakpoints (usa los ganchos debug_* ya expuestos por
# interpreter.py), buscar/reemplazar y persistencia de sesión.

import math
import os
import re
import threading

from PySide6.QtCore import QPointF, QSettings, QStringListModel, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QPolygonF,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFileSystemModel,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolTip,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import flowchart as fc

try:
    from .ds_visualizer import attach_to_interpreter as _attach_vis
except Exception:
    _attach_vis = None
from . import builtins as _builtins_mod
from . import flowchart_builder as fb
from . import ir as ir_mod
from .ast_nodes import (
    ASTNode,
    Bloque,
    DoWhileStmt,
    ForStmt,
    IfStmt,
    Parametro,
    PrintStmt,
    ReadStmt,
    VarDecl,
    WhileStmt,
)
from .docstrings import (
    _DOC_ATAJOS,
    _DOC_ERRORES,
    _DOC_FUNCIONES,
    _DOC_GUIA,
    _DOC_REFERENCIA,
    EJEMPLOS,
)
from .errors import ErrorManager
from .interpreter import DebugStopped, ExecutionCancelled, Interpreter
from .lexer import Lexer
from .parser import Parser
from .semantic import SemanticAnalyzer
from .type_checker import TypeChecker

# Accesibilidad profesional (WCAG 2.1 AA) — ver accessibility.py / ACCESSIBILITY.md
try:
    from . import accessibility as _acc
except Exception:
    _acc = None

# Temas — extraídos a gui/theme.py (hexagonal, Sprint 0). Import real, no duplicado.
try:
    from .gui.theme import COLORES, TEMA_ALTO_CONTRASTE, TEMA_CLARO, TEMA_OSCURO
except Exception:
    # Fallback si gui.theme no disponible (CI sin Qt)
    TEMA_OSCURO = {
        "fondo": "#1e1e1e",
        "panel": "#252526",
        "gutter": "#252526",
        "gutter_borde": "#3c3c3c",
        "gutter_linea": "#858585",
        "texto": "#d4d4d4",
        "keyword": "#569cd6",
        "type": "#4ec9b0",
        "string": "#ce9178",
        "comment": "#6a9955",
        "number": "#b5cea8",
        "builtin": "#dcdcaa",
        "operator": "#d4d4d4",
        "error_sub": "#f48771",
        "error_fondo": "#3a2020",
        "warn_sub": "#dcdcaa",
        "warn_fondo": "#413f23",
        "linea_activa": "#2a2d2e",
        "flash": "#264f78",
        "breakpoint": "#e51400",
        "dfd_inicio_fin": "#264f78",
        "dfd_proceso": "#2d2d30",
        "dfd_decision": "#3a3d21",
        "dfd_es": "#2d3d3d",
        "dfd_borde": "#9cdcfe",
        "dfd_flecha": "#c8c8c8",
        "dfd_texto": "#d4d4d4",
    }
    TEMA_CLARO = {
        "fondo": "#ffffff",
        "panel": "#f3f3f3",
        "gutter": "#f3f3f3",
        "gutter_borde": "#d4d4d4",
        "gutter_linea": "#237893",
        "texto": "#000000",
        "keyword": "#0000ff",
        "type": "#267f99",
        "string": "#a31515",
        "comment": "#008000",
        "number": "#098658",
        "builtin": "#795e26",
        "operator": "#000000",
        "error_sub": "#e51400",
        "error_fondo": "#fde7e9",
        "warn_sub": "#b89500",
        "warn_fondo": "#fff8e1",
        "linea_activa": "#f0f0f0",
        "flash": "#add6ff",
        "breakpoint": "#e51400",
        "dfd_inicio_fin": "#add6ff",
        "dfd_proceso": "#f3f3f3",
        "dfd_decision": "#fff2b3",
        "dfd_es": "#d6f5e3",
        "dfd_borde": "#0066cc",
        "dfd_flecha": "#333333",
        "dfd_texto": "#000000",
    }
    COLORES = dict(TEMA_OSCURO)
    TEMA_ALTO_CONTRASTE = _acc.TEMA_ALTO_CONTRASTE if _acc else TEMA_OSCURO

KEYWORDS = {
    "if",
    "si",
    "else",
    "sino",
    "while",
    "mientras",
    "for",
    "para",
    "return",
    "retornar",
    "break",
    "romper",
    "continue",
    "continuar",
    "main",
    "true",
    "verdadero",
    "false",
    "falso",
    "const",
    "constante",
    "print",
    "imprimir",
    "read",
    "leer",
    # POO (InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md)
    "class",
    "clase",
    "extends",
    "hereda",
    "new",
    "nuevo",
    "this",
    "este",
    "super",
    "padre",
    "public",
    "publico",
    "private",
    "privado",
    "null",
    "nulo",
    # Etapa 6 (lenguaje estructurado completo)
    "switch",
    "segun",
    "case",
    "caso",
    "default",
    "por_defecto",
    "do",
    "hacer",
    "try",
    "intentar",
    "catch",
    "capturar",
    # Etapa 7 (POO completo)
    "abstract",
    "abstracta",
    "abstracto",
    "static",
    "estatico",
    # Etapa 11 (cierre de brechas de Fase 2)
    "constructor",
    "enum",
    "enumeracion",
    # Etapa 12 (paradigma funcional, tipos suma, rigor de compiladores)
    "foreach",
    "para_cada",
    "implements",
    "implementa",
    "interface",
    "interfaz",
    "function",
    "funcion",
    "match",
    "emparejar",
}
TIPOS = {"int", "entero", "float", "real", "string", "texto", "bool", "logico", "void", "vacio"}
# BUILTINS se deriva de la tabla real de funciones integradas (incluye las 8
# de conversión de tipo, más la librería estándar de cadenas/matemática de
# la Etapa 6) para que el resaltador no se desincronice de builtins.py.
BUILTINS = set(_builtins_mod.FUNCIONES_BUILT_IN.keys())

# Autocompletado (Etapa 5): candidatos fijos (palabras clave bilingües +
# funciones integradas) -- los identificadores declarados por el estudiante
# se agregan aparte, en vivo, por cada CodeEditor.
_CANDIDATOS_ESTATICOS = KEYWORDS | TIPOS | BUILTINS
_RE_IDENTIFICADOR_COMPLETADO = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _formato(fore, bold=False):
    f = QTextCharFormat()
    f.setForeground(QColor(fore))
    f.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    return f


class LineNumberArea(QWidget):
    """Área de números de línea."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        """Tamaño sugerido del widget."""
        from PySide6.QtCore import QSize

        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        """Atiende el repintado."""
        self._editor.line_number_area_paint_event(event)

    def mousePressEvent(self, event):
        """Atiende el clic del mouse."""
        if event.button() == Qt.MouseButton.LeftButton:
            linea = self._editor._linea_en_y(event.position().y())
            if linea:
                self._editor.alternar_breakpoint(linea)


class MiniMapArea(QWidget):
    """Minimapa del editor (Etapa 9): vista miniatura de todo el documento.

    a la derecha, con clic (y arrastre) para saltar y un recuadro que marca
    la porción visible actualmente en el editor principal -- mismo patrón
    que LineNumberArea (widget hijo repintado por el editor), sin ninguna
    dependencia nueva.
    """

    ANCHO = 90

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self.setFixedWidth(self.ANCHO)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Minimapa")
        self.setAccessibleDescription("Vista miniatura navegable con teclado y mouse")

    def sizeHint(self):
        """Tamaño sugerido del widget."""
        from PySide6.QtCore import QSize

        return QSize(self.ANCHO, 0)

    def paintEvent(self, event):
        """Atiende el repintado."""
        self._editor._pintar_minimapa(self, event)

    def _linea_para_y(self, y):
        total = max(1, self._editor.document().blockCount())
        proporcion = min(max(y / max(1, self.height()), 0.0), 1.0)
        return max(1, min(total, int(proporcion * total) + 1))

    def mousePressEvent(self, event):
        """Atiende el clic del mouse."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._editor._saltar_desde_minimapa(self._linea_para_y(event.position().y()))

    def mouseMoveEvent(self, event):
        """Atiende el movimiento del mouse."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._editor._saltar_desde_minimapa(self._linea_para_y(event.position().y()))

    def keyPressEvent(self, event):
        """Atiende la tecla presionada."""
        from PySide6.QtCore import Qt

        if event.key() == Qt.Key.Key_Up:
            self._editor._saltar_desde_minimapa(max(1, self._editor.textCursor().blockNumber()))
            return
        if event.key() == Qt.Key.Key_Down:
            self._editor._saltar_desde_minimapa(self._editor.textCursor().blockNumber() + 2)
            return
        super().keyPressEvent(event)

    def focusInEvent(self, e):
        """Atiende el foco de entrada."""
        self.setAccessibleName("Minimapa")
        self.setAccessibleDescription(
            "Vista miniatura navegable con teclado Up/Down, clic y arrastre"
        )
        super().focusInEvent(e)


class InvenioHighlighter(QSyntaxHighlighter):
    """Resaltado sintáctico de InvenioLang."""

    def __init__(self, document):
        super().__init__(document)
        self._kw = re.compile(r"\b(" + "|".join(sorted(KEYWORDS)) + r")\b")
        self._tp = re.compile(r"\b(" + "|".join(sorted(TIPOS)) + r")\b")
        self._bl = re.compile(r"\b(" + "|".join(sorted(BUILTINS)) + r")\b")
        self._num = re.compile(r"\b\d+\.\d+([eE][+-]?\d+)?\b|\b\d+\b")
        self._str = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'')
        self._coment = re.compile(r"//[^\n]*")
        self.actualizar_colores()

    def actualizar_colores(self):
        """Reconstruye los formatos desde COLORES (Etapa 5: cambio de tema.

        en vivo) y vuelve a resaltar todo el documento.
        """
        self.fmt_keyword = _formato(COLORES["keyword"], bold=True)
        self.fmt_type = _formato(COLORES["type"])
        self.fmt_builtin = _formato(COLORES["builtin"])
        self.fmt_number = _formato(COLORES["number"])
        self.fmt_string = _formato(COLORES["string"])
        self.fmt_comment = _formato(COLORES["comment"])
        self.rehighlight()

    def highlightBlock(self, text):
        """Resalta el bloque actual."""
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
            start = text.find("/*")
            if start < 0:
                return
        end = text.find("*/", start + 2)
        if end >= 0:
            self.setFormat(start, end + 2 - start, self.fmt_comment)
            self.setCurrentBlockState(0)
        else:
            self.setFormat(start, len(text) - start, self.fmt_comment)
            self.setCurrentBlockState(1)


class CodeEditor(QPlainTextEdit):
    """Editor con numeración de líneas, resaltado y estado propio de pestaña.

    Cada instancia representa una pestaña del IDE: guarda su propia ruta,
    estado de modificación, breakpoints y resultados del análisis en vivo,
    en vez de que MainWindow mantenga listas paralelas por índice de pestaña.
    """

    # Tamaño de fuente por defecto para pestañas nuevas; MainWindow lo
    # actualiza en vivo desde el panel de configuración (Etapa 5).
    TAMANO_FUENTE_DEFECTO = 11

    # Ir-a-definición (Etapa 9): Ctrl+clic sobre un identificador emite esta
    # señal (el cursor ya quedó posicionado sobre el clic); MainWindow la
    # conecta a _ir_a_definicion, mismo patrón que _job_en_vivo.timeout.
    solicitud_definicion = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(CodeEditor.TAMANO_FUENTE_DEFECTO)
        self.setFont(font)
        self.setTabStopDistance(4 * QFontMetrics(font).horizontalAdvance(" "))
        self.setMouseTracking(True)  # necesario para el hover (Etapa 9)
        self.line_number_area = LineNumberArea(self)
        self.minimapa = MiniMapArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.updateRequest.connect(lambda *_: self.minimapa.update())
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._extra_adicional = []  # selecciones de errores/advertencias

        # Estado de IDE propio de esta pestaña.
        self.ruta = None
        self.modificado = False
        self.cargando = False
        self.breakpoints = set()
        self.errores_actuales = []
        # IntelliSense (Etapa 9): último AST que analizó correctamente
        # (se conserva aunque un análisis posterior falle por un error de
        # sintaxis/semántico/tipos transitorio mientras el usuario escribe
        # -- igual que un IDE real no borra los símbolos por un punto y
        # coma faltante) y la tabla de símbolos de la última pasada
        # semántica exitosa. Usados por breadcrumbs, autocompletado
        # consciente de tipos, ir-a-definición y hover.
        self.ast_en_vivo = None
        self.tabla_en_vivo = None
        self.highlighter = InvenioHighlighter(self.document())
        self._job_en_vivo = QTimer(self)
        self._job_en_vivo.setSingleShot(True)
        self._job_en_vivo.setInterval(500)

        # Autocompletado (Etapa 5): un QCompleter propio por pestaña, igual
        # que cada editor ya tiene su propio highlighter/breakpoints.
        self.completador = QCompleter(sorted(_CANDIDATOS_ESTATICOS), self)
        self.completador.setWidget(self)
        self.completador.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completador.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completador.activated.connect(self._insertar_completado)

        self._pintar_paleta()
        self._update_line_number_area_width(0)
        self._highlight_current_line()

    def _prefijo_bajo_cursor(self):
        """Texto de identificador ya escrito inmediatamente antes del cursor.

        (para completar), sin incluir lo que venga despues del cursor.
        """
        cursor = self.textCursor()
        texto = cursor.block().text()
        col = cursor.positionInBlock()
        inicio = col
        while inicio > 0 and (texto[inicio - 1].isalnum() or texto[inicio - 1] == "_"):
            inicio -= 1
        return texto[inicio:col]

    def _contexto_miembro_bajo_cursor(self):
        """Infiere el receptor para autocompletar.

        retorna (nombre_objeto, parcial); si no, retorna None. `parcial`
        puede ser '' (cursor inmediatamente después del punto).
        """
        cursor = self.textCursor()
        texto = cursor.block().text()
        col = cursor.positionInBlock()
        fin_parcial = col
        inicio_parcial = fin_parcial
        while inicio_parcial > 0 and (
            texto[inicio_parcial - 1].isalnum() or texto[inicio_parcial - 1] == "_"
        ):
            inicio_parcial -= 1
        if inicio_parcial == 0 or texto[inicio_parcial - 1] != ".":
            return None
        fin_obj = inicio_parcial - 1
        inicio_obj = fin_obj
        while inicio_obj > 0 and (texto[inicio_obj - 1].isalnum() or texto[inicio_obj - 1] == "_"):
            inicio_obj -= 1
        nombre_obj = texto[inicio_obj:fin_obj]
        if not nombre_obj:
            return None
        return nombre_obj, texto[inicio_parcial:fin_parcial]

    def _actualizar_candidatos_completado(self, ctx_miembro=None):
        """Candidatos del autocompletado (Etapa 9, IntelliSense real).

        Tras 'objeto.' (`ctx_miembro` no es None): SOLO los miembros
        públicos de la clase de `objeto`, inferida desde el AST del
        análisis en vivo (`_tipo_declarado`) y resueltos vía la tabla de
        símbolos real (`_miembros_publicos` -- resolver_atributo/
        resolver_metodo de symbol_table.py, no una lista aparte). Lista
        vacía si el tipo no se pudo inferir todavía (p. ej. mientras el
        programa tiene errores de sintaxis).

        En cualquier otra posición: el comportamiento original de la
        Etapa 5 -- palabras clave/funciones integradas + identificadores
        ya escritos en el buffer (extracción ligera por expresión regular,
        barata de recalcular en cada pulsación; puede sugerir de más
        alguna palabra dentro de un comentario o cadena, un falso positivo
        inofensivo).
        """
        if ctx_miembro is not None:
            nombre_obj, _ = ctx_miembro
            linea = self.textCursor().blockNumber() + 1
            tipo = _tipo_declarado(self.ast_en_vivo, self.tabla_en_vivo, nombre_obj, linea)
            candidatos = _miembros_publicos(self.tabla_en_vivo, tipo)
        else:
            identificadores = set(_RE_IDENTIFICADOR_COMPLETADO.findall(self.toPlainText()))
            candidatos = sorted(_CANDIDATOS_ESTATICOS | identificadores)
        modelo = self.completador.model()
        if not isinstance(modelo, QStringListModel):
            self.completador.setModel(QStringListModel(candidatos, self.completador))
        elif modelo.stringList() != candidatos:
            modelo.setStringList(candidatos)

    def _insertar_completado(self, texto):
        prefijo = self.completador.completionPrefix()
        cursor = self.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(prefijo)
        )
        cursor.insertText(texto)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event):
        """Atiende la tecla presionada."""
        popup = self.completador.popup()
        if popup.isVisible() and event.key() in (
            Qt.Key.Key_Enter,
            Qt.Key.Key_Return,
            Qt.Key.Key_Escape,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        ):
            event.ignore()  # el popup del QCompleter los consume
            return

        es_atajo = (
            bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            and event.key() == Qt.Key.Key_Space
        )
        if not es_atajo:
            super().keyPressEvent(event)

        # IntelliSense (Etapa 9): tras 'objeto.' el popup se dispara de
        # inmediato (incluso con 0 caracteres escritos después del punto),
        # igual que en un IDE real -- se detecta ANTES de aplicar el filtro
        # de "2+ caracteres de palabra" que rige el resto de los casos.
        ctx_miembro = self._contexto_miembro_bajo_cursor()
        if ctx_miembro is not None:
            prefijo = ctx_miembro[1]
        else:
            texto_tecla = event.text()
            es_texto_palabra = bool(texto_tecla) and (texto_tecla.isalnum() or texto_tecla == "_")
            prefijo = self._prefijo_bajo_cursor()
            if not es_atajo and (not es_texto_palabra or len(prefijo) < 2):
                popup.hide()
                return

        self._actualizar_candidatos_completado(ctx_miembro)
        if prefijo != self.completador.completionPrefix():
            self.completador.setCompletionPrefix(prefijo)
            popup.setCurrentIndex(self.completador.completionModel().index(0, 0))

        rect = self.cursorRect()
        rect.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width())
        self.completador.complete(rect)

    def mousePressEvent(self, event):
        """Atiende el clic del mouse.

        mismo atajo que F12 pero con el mouse. Se posiciona el cursor en el
        punto del clic y se emite `solicitud_definicion` -- MainWindow hace
        la resolución real (necesita el AST/tabla de análisis en vivo, que
        vive del lado de MainWindow, no de este widget).
        """
        if event.button() == Qt.MouseButton.LeftButton and bool(
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            cursor = self.cursorForPosition(event.position().toPoint())
            self.setTextCursor(cursor)
            self.solicitud_definicion.emit()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Hover (Etapa 9): tooltip con tipo/firma del identificador bajo.

        el mouse, usando la misma resolución de símbolo que ir-a-definición
        y el autocompletado tras 'objeto.' (_resolver_identificador_en).
        """
        super().mouseMoveEvent(event)
        pos = event.position().toPoint()
        cursor = self.cursorForPosition(pos)
        texto = cursor.block().text()
        col = cursor.positionInBlock()
        resultado = _resolver_identificador_en(
            self.ast_en_vivo, self.tabla_en_vivo, texto, col, cursor.blockNumber() + 1
        )
        if resultado is not None:
            _linea, _columna, descripcion = resultado
            QToolTip.showText(event.globalPosition().toPoint(), descripcion, self)
        else:
            QToolTip.hideText()

    def _pintar_paleta(self):
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor(COLORES["fondo"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(COLORES["texto"]))
        self.setPalette(pal)

    def line_number_area_width(self):
        """Ancho del área de números."""
        digits = max(2, len(str(self.blockCount())))
        fm = QFontMetrics(self.font())
        return 14 + fm.horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _=None):
        self.setViewportMargins(self.line_number_area_width(), 0, MiniMapArea.ANCHO, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

    def _resize_gutter(self, event):
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            cr.left(), cr.top(), self.line_number_area_width(), cr.height()
        )
        self.minimapa.setGeometry(
            cr.left() + cr.width() - MiniMapArea.ANCHO, cr.top(), MiniMapArea.ANCHO, cr.height()
        )

    def resizeEvent(self, event):
        """Atiende el cambio de tamaño."""
        super().resizeEvent(event)
        self._resize_gutter(event)

    def set_problemas(self, sels):
        """Establece las selecciones adicionales (errores/advertencias)."""
        self._extra_adicional = list(sels)
        self._highlight_current_line()

    def _highlight_current_line(self):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(COLORES["linea_activa"]))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel] + list(self._extra_adicional))

    def _recorrer_bloques(self):
        """Genera (block, top, bottom, numero_linea) para los bloques visibles."""
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid():
            yield block, top, bottom, block_number + 1
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def _linea_en_y(self, y):
        """Determina el número de línea (1-based) bajo la coordenada y del gutter."""
        for _block, top, bottom, linea in self._recorrer_bloques():
            if top <= y <= bottom:
                return linea
            if top > y:
                break
        return None

    def alternar_breakpoint(self, linea):
        """Alterna un breakpoint."""
        if linea in self.breakpoints:
            self.breakpoints.discard(linea)
        else:
            self.breakpoints.add(linea)
        self.line_number_area.update()

    def line_number_area_paint_event(self, event):
        """Pinta el área de números."""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(COLORES["gutter"]))
        fm = QFontMetrics(self.font())
        for block, top, bottom, linea in self._recorrer_bloques():
            if top > event.rect().bottom():
                break
            if not block.isVisible() or bottom < event.rect().top():
                continue
            if linea in self.breakpoints:
                painter.save()
                painter.setBrush(QColor(COLORES["breakpoint"]))
                painter.setPen(Qt.PenStyle.NoPen)
                radio = max(3, fm.height() // 4)
                cy = int(top + fm.height() / 2)
                painter.drawEllipse(3, cy - radio, radio * 2, radio * 2)
                painter.restore()
            painter.setPen(QColor(COLORES["gutter_linea"]))
            painter.drawText(
                0,
                int(top),
                self.line_number_area.width() - 6,
                fm.height(),
                Qt.AlignmentFlag.AlignRight,
                str(linea),
            )

    def _pintar_minimapa(self, widget, event):
        """Pinta el minimapa (Etapa 9): cada línea del documento se dibuja.

        como un segmento horizontal proporcional a su longitud (una
        representación de "forma" del código, no el texto real -- a esta
        escala no sería legible) más un recuadro que marca la porción
        visible actualmente en el editor principal.
        """
        painter = QPainter(widget)
        painter.fillRect(event.rect(), QColor(COLORES["gutter"]))
        doc = self.document()
        total = max(1, doc.blockCount())
        alto = widget.height()
        ancho = widget.width()
        paso = alto / total
        max_chars = 100
        color = QColor(COLORES["gutter_linea"])
        color.setAlpha(150)
        painter.setPen(color)
        block = doc.firstBlock()
        n = 0
        while block.isValid():
            texto = block.text().rstrip()
            if texto:
                largo = min(len(texto), max_chars)
                ancho_linea = max(1, int((ancho - 6) * largo / max_chars))
                y = int(n * paso)
                painter.drawLine(3, y, 3 + ancho_linea, y)
            n += 1
            block = block.next()

        primer_visible = self.firstVisibleBlock().blockNumber()
        altura_bloque = max(1.0, self.blockBoundingRect(self.firstVisibleBlock()).height())
        n_visibles = max(1, int(self.viewport().height() / altura_bloque))
        y1 = int(primer_visible * paso)
        y2 = int((primer_visible + n_visibles) * paso)
        overlay = QColor(COLORES["linea_activa"])
        overlay.setAlpha(140)
        painter.fillRect(0, y1, ancho, max(3, y2 - y1), overlay)

    def _saltar_desde_minimapa(self, linea):
        """Clic (o arrastre) en el minimapa: mueve el cursor a esa línea y.

        centra la vista, sin depender de MainWindow (el minimapa es
        exclusivamente del editor, igual que el gutter de breakpoints).
        """
        block = self.document().findBlockByNumber(max(0, linea - 1))
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        self.centerCursor()


class _HiloEjecucion(QThread):
    """Ejecuta el intérprete fuera del hilo de la interfaz.

    Mantener la interpretación en el hilo de la ventana la congelaba mientras
    el programa corría: con un ciclo sin terminación, hasta que saltaba el
    límite de IL-EJE-030. Es también la base del depurador paso a paso: al
    pausar en un breakpoint, `debug_wait` (invocado desde el hilo del
    intérprete) emite `pausado` -- Qt encola la señal hacia el hilo de la GUI
    automáticamente porque el receptor vive ahí -- y bloquea este hilo con un
    `threading.Event` hasta que la GUI pida Paso o Continuar. Nunca se debe
    tocar un widget Qt directamente desde este hilo.

    Emite `terminado(salida, error_manager, cancelado, fallo)` y, en modo
    depuración, `pausado(snapshot)` cada vez que se detiene.

    Terminal integrada (Etapa 9, `interactivo=True`): mismo patrón que el
    depurador, pero para entrada/salida en vez de breakpoints -- `linea_salida`
    se emite en vivo (línea a línea, vía `Interpreter.on_salida`) en lugar de
    esperar a `terminado`, y `solicitud_entrada` bloquea este hilo (otro
    `threading.Event`) hasta que la GUI llama a `recibir_entrada(texto)`
    con lo que el usuario escribió en el campo de la terminal.
    """

    terminado = Signal(list, object, bool, object)
    pausado = Signal(dict)
    linea_salida = Signal(str)
    solicitud_entrada = Signal()

    def __init__(
        self,
        ast,
        tabla,
        error_manager,
        entrada,
        breakpoints=None,
        depurar=False,
        interactivo=False,
        parent=None,
    ):
        super().__init__(parent)
        self._ast = ast
        self._entrada = entrada
        self._em = error_manager
        self._cancelar = False
        self._reanudar = threading.Event()
        self._entrada_lista = threading.Event()
        self._entrada_pendiente = ""
        self.interp = Interpreter(error_manager, tabla)
        self.interp.cancelado = lambda: self._cancelar
        if interactivo:
            self.interp.on_salida = self.linea_salida.emit
            self.interp.leer_interactivo = self._esperar_entrada_interactiva
        if depurar:
            self.interp.debug = True
            self.interp.debug_breakpoints = set(breakpoints or ())
            # H1.2 cableado ds_visualizer via Observer
            if _attach_vis and depurar:
                try:
                    self._visualizer = _attach_vis(self.interp)
                except Exception:  # noqa: S110 - visualizador opcional, depuración sigue
                    pass
            self.interp.debug_on_statement = self._on_debug_statement
            self.interp.debug_wait = self._on_debug_wait

    def _on_debug_statement(self, snap, pausar):
        # El intérprete sólo llama a este callback cuando `pausar` ya es
        # False (breakpoints/paso se resuelven antes, vía `pausar`); no
        # forzamos pausas adicionales en modo depurador visual.
        return False

    def _on_debug_wait(self, snap):
        self.pausado.emit(snap)
        self._reanudar.wait()
        self._reanudar.clear()

    def _esperar_entrada_interactiva(self):
        """Pide entrada a la terminal integrada.

        el de la GUI) cuando el programa llama a leer()/read() sin entrada
        simulada pendiente. Pide la entrada a la terminal y bloquea hasta
        que `recibir_entrada` la entregue -- o hasta que `cancelar()`
        libere el Event para no dejar el hilo colgado indefinidamente.
        """
        self._entrada_lista.clear()
        self.solicitud_entrada.emit()
        self._entrada_lista.wait()
        self._entrada_lista.clear()
        return self._entrada_pendiente

    def recibir_entrada(self, texto):
        """Llamado desde el hilo de la GUI cuando el usuario envía una línea.

        en el campo de entrada de la terminal -- desbloquea el hilo de
        ejecución, que estaba esperando dentro de leer()/read().
        """
        self._entrada_pendiente = texto
        self._entrada_lista.set()

    def cancelar(self):
        """Cancela la depuración."""
        self._cancelar = True
        self.interp.debug_detener = True
        self._reanudar.set()
        self._entrada_pendiente = ""
        self._entrada_lista.set()  # no dejar colgado un leer() interactivo

    def paso(self):
        """Avanza un paso de depuración."""
        self.interp.debug_step = True
        self._reanudar.set()

    def continuar(self):
        """Continúa la ejecución."""
        self._reanudar.set()

    def run(self):
        """Ejecuta el flujo."""
        salida, cancelado, fallo = [], False, None
        try:
            salida = self.interp.interpretar(self._ast, self._entrada, usar_stdin=False)
        except (ExecutionCancelled, DebugStopped):
            cancelado = True
            salida = list(self.interp.salida)
        except Exception as e:  # pragma: no cover
            fallo = str(e)
        self.terminado.emit(list(salida), self._em, cancelado, fallo)


def _crear_panel(parent=None, read_only=True):
    """Crea un QPlainTextEdit de solo lectura con el tema oscuro."""
    t = QPlainTextEdit(parent)
    if read_only:
        t.setReadOnly(True)
    t.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    pal = t.palette()
    pal.setColor(QPalette.ColorRole.Base, QColor(COLORES["panel"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(COLORES["texto"]))
    t.setPalette(pal)
    return t


class ErrorTextEdit(QPlainTextEdit):
    """Panel de errores/advertencias que emite el número de línea clicado."""

    clicked_line = Signal(int)

    def mouseReleaseEvent(self, event):
        """Atiende al soltar el mouse."""
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            self.clicked_line.emit(cursor.block().blockNumber() + 1)
        super().mouseReleaseEvent(event)


class _DiagramaView(QGraphicsView):
    """QGraphicsView con zoom en la rueda del mouse (Etapa 4)."""

    def wheelEvent(self, event):
        """Atiende la rueda del mouse."""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


def _ubicar_contexto(ast, linea):
    """Ubica la subrutina/método/constructor que contiene `linea`, dado el.

    AST del análisis en vivo (Etapa 9, breadcrumbs). Sin dependencia de Qt
    -- función pura, testeable igual que flowchart.py.

    El AST no guarda línea de fin por nodo (solo línea de inicio, ver
    ast_nodes.py), así que se usa la misma heurística que ya usa el resto
    del IDE para mapear 'línea actual' a 'contexto en ejecución': entre
    todos los candidatos cuya línea de inicio es <= `linea`, el de mayor
    línea de inicio es el que la contiene (el siguiente candidato, si
    existe, marca implícitamente dónde termina).

    Retorna (nombre_clase_o_None, nombre_subrutina_o_None). Ambos None si
    `linea` cae antes de toda declaración (encabezado del archivo) o si no
    hay AST disponible todavía.
    """
    if ast is None:
        return None, None
    candidatos = []  # (linea_inicio, clase_o_None, subrutina_o_None)
    for sub in ast.subrutinas:
        candidatos.append((sub.linea, None, sub.nombre))
    if ast.main is not None:
        candidatos.append((ast.main.linea, None, "main"))
    for clase in ast.clases:
        candidatos.append((clase.linea, clase.nombre, None))
        for ctor in clase.constructores:  # Etapa 10: sobrecarga de constructores
            candidatos.append((ctor.linea, clase.nombre, clase.nombre))
        for m in clase.metodos:
            candidatos.append((m.linea, clase.nombre, m.nombre))
    mejor = None
    for c in candidatos:
        if c[0] <= linea and (mejor is None or c[0] > mejor[0]):
            mejor = c
    if mejor is None:
        return None, None
    return mejor[1], mejor[2]


def _coincide_difuso(patron, texto):
    """Coincidencia de subsecuencia estilo VS Code (Etapa 9, paleta de.

    comandos): cada carácter de `patron` debe aparecer en `texto` en el
    mismo orden, no necesariamente contiguo. Sin dependencia de Qt --
    función pura, testeable de forma aislada.
    """
    texto = texto.lower()
    it = iter(texto)
    return all(c in it for c in patron.lower())


# ============================================================
# IntelliSense (Etapa 9): resolución de tipos sobre el AST/tabla de
# símbolos del análisis en vivo -- funciones puras, sin Qt, compartidas
# por autocompletado, ir-a-definición y hover.
# ============================================================


def _recolectar_vardecls(nodo, encontrados=None, visitados=None):
    """Recorre GENÉRICAMENTE (via vars(), sin enumerar cada tipo de nodo).

    cualquier nodo o lista de nodos del AST alcanzable desde `nodo` y
    recolecta el nodo VarDecl/Parametro de cada declaración encontrada
    (nombre -> nodo, para leer `.tipo`/`.linea`/`.columna` según haga
    falta) -- mismo patrón de reflexión que semantic.py ya usa para
    expandir genéricos (_expandir_genericos), reutilizado aquí para no
    tener que enumerar manualmente cada instrucción que puede contener un
    bloque anidado (if/while/for/switch/do-while/try).
    """
    if encontrados is None:
        encontrados = {}
    if visitados is None:
        visitados = set()
    if nodo is None or id(nodo) in visitados:
        return encontrados
    if isinstance(nodo, (VarDecl, Parametro)):
        encontrados.setdefault(nodo.nombre, nodo)
        return encontrados
    if isinstance(nodo, list):
        for item in nodo:
            _recolectar_vardecls(item, encontrados, visitados)
        return encontrados
    if isinstance(nodo, ASTNode):
        visitados.add(id(nodo))
        for valor in vars(nodo).values():
            _recolectar_vardecls(valor, encontrados, visitados)
    return encontrados


def _nodo_subrutina_en_contexto(ast, clase_ctx, sub_ctx, linea):
    """Ubica el nodo Subrutina/MethodDecl/ConstructorDecl/MainDecl real que.

    corresponde a (clase_ctx, sub_ctx) -- la salida de _ubicar_contexto --
    para poder inspeccionar sus parámetros y su bloque.

    Etapa 10 (sobrecarga de constructores): si `sub_ctx` es el caso
    constructor (mismo nombre que la clase), una clase puede tener VARIAS
    sobrecargas -- se elige la de mayor línea de inicio <= `linea`, misma
    heurística que ya usa `_ubicar_contexto` para el resto de las
    subrutinas/métodos.
    """
    if sub_ctx is None:
        return None
    if clase_ctx is None:
        if sub_ctx == "main":
            return ast.main
        return next((s for s in ast.subrutinas if s.nombre == sub_ctx), None)
    clase_ast = next((c for c in ast.clases if c.nombre == clase_ctx), None)
    if clase_ast is None:
        return None
    if sub_ctx == clase_ctx:  # constructor: mismo nombre que la clase
        candidatos = [c for c in clase_ast.constructores if c.linea <= linea]
        if not candidatos:
            return None
        return max(candidatos, key=lambda c: c.linea)
    return next((m for m in clase_ast.metodos if m.nombre == sub_ctx), None)


def _tipo_declarado(ast, tabla, nombre, linea):
    """Infiere el tipo (nombre de clase) de un identificador visible en.

    `linea`, para autocompletado/hover tras 'objeto.' o sobre `objeto`
    (Etapa 9). Es una heurística basada en el AST -- no un resolutor de
    ámbitos completo (no distingue sombreado de variables en bloques
    anidados con el mismo nombre) -- pero cubre el caso real: parámetro,
    variable local, variable global o atributo (propio o heredado) de la
    clase que contiene el cursor. Retorna None si no se puede inferir.
    """
    if ast is None:
        return None
    if nombre in ("this", "este"):
        clase, _ = _ubicar_contexto(ast, linea)
        return clase
    clase_ctx, sub_ctx = _ubicar_contexto(ast, linea)
    nodo_sub = _nodo_subrutina_en_contexto(ast, clase_ctx, sub_ctx, linea)
    if nodo_sub is not None:
        for p in getattr(nodo_sub, "parametros", None) or []:
            if p.nombre == nombre:
                return p.tipo
        vardecls = _recolectar_vardecls(getattr(nodo_sub, "bloque", None))
        if nombre in vardecls:
            return vardecls[nombre].tipo
    vardecls_globales = _recolectar_vardecls(ast.declaraciones_globales)
    vardecls_globales.update(_recolectar_vardecls(ast.declaraciones_posteriores))
    if nombre in vardecls_globales:
        return vardecls_globales[nombre].tipo
    if clase_ctx is not None and tabla is not None:
        actual = tabla.clases.get(clase_ctx)
        while actual is not None:
            if nombre in actual.atributos:
                return actual.atributos[nombre].tipo
            actual = tabla.clases.get(actual.padre) if actual.padre else None
    return None


def _resolver_miembro(tabla, nombre_clase, nombre_miembro):
    """Ubica el MiembroInfo/MetodoInfo (con `.linea`/`.columna`/`.tipo`) de.

    `nombre_miembro` dentro de `nombre_clase`, caminando la cadena de
    herencia -- para ir-a-definición/hover sobre 'objeto.miembro' (Etapa
    9). Retorna None si no existe (o si es privado -- fuera del alcance de
    lo que 'objeto.miembro' puede referenciar válidamente desde afuera).
    """
    if tabla is None or not nombre_clase:
        return None
    actual = tabla.clases.get(nombre_clase)
    while actual is not None:
        if nombre_miembro in actual.atributos:
            return actual.atributos[nombre_miembro]
        if nombre_miembro in actual.metodos:
            return actual.metodos[nombre_miembro][0]
        actual = tabla.clases.get(actual.padre) if actual.padre else None
    return None


def _resolver_declaracion(ast, tabla, nombre, linea):
    """Ubica dónde se declaró `nombre` (visible en `linea`), para.

    ir-a-definición (F12/Ctrl+clic) y hover (Etapa 9). Retorna
    (linea_decl, columna_decl, descripcion) o None si no se pudo resolver
    -- cubre clases, subrutinas/métodos/constructor, parámetros, variables
    locales y globales, y atributos de la propia clase envolvente
    (accedidos sin `this.` explícito).
    """
    if ast is None:
        return None
    if nombre in ("this", "este", "super", "padre"):
        clase_ctx, _ = _ubicar_contexto(ast, linea)
        info = tabla.clases.get(clase_ctx) if tabla else None
        if nombre in ("super", "padre") and info is not None:
            info = tabla.clases.get(info.padre) if info.padre else None
        if info is not None:
            return info.linea, info.columna, f"clase {info.nombre}"
        return None
    if tabla is not None and nombre in tabla.clases:
        info = tabla.clases[nombre]
        return info.linea, info.columna, f"clase {info.nombre}"
    if nombre == "main" and ast.main is not None:
        return ast.main.linea, ast.main.columna, "main()"
    sub = next((s for s in ast.subrutinas if s.nombre == nombre), None)
    if sub is not None:
        firma = f"{sub.tipo_retorno} {sub.nombre}({len(sub.parametros)} parám.)"
        return sub.linea, sub.columna, firma
    clase_ctx, sub_ctx = _ubicar_contexto(ast, linea)
    nodo_sub = _nodo_subrutina_en_contexto(ast, clase_ctx, sub_ctx, linea)
    if nodo_sub is not None:
        for p in getattr(nodo_sub, "parametros", None) or []:
            if p.nombre == nombre:
                return p.linea, p.columna, f"parámetro: {p.tipo} {p.nombre}"
        vardecls = _recolectar_vardecls(getattr(nodo_sub, "bloque", None))
        if nombre in vardecls:
            v = vardecls[nombre]
            return v.linea, v.columna, f"variable local: {v.tipo} {v.nombre}"
    vardecls_globales = _recolectar_vardecls(ast.declaraciones_globales)
    vardecls_globales.update(_recolectar_vardecls(ast.declaraciones_posteriores))
    if nombre in vardecls_globales:
        v = vardecls_globales[nombre]
        return v.linea, v.columna, f"variable global: {v.tipo} {v.nombre}"
    if clase_ctx is not None:
        miembro = _resolver_miembro(tabla, clase_ctx, nombre)
        if miembro is not None:
            prefijo = "atributo" if not hasattr(miembro, "params_tipos") else "método"
            return miembro.linea, miembro.columna, f"{prefijo}: {miembro.tipo} {nombre}"
    return None


def _miembros_publicos(tabla, nombre_clase):
    """Nombres de atributos y métodos PÚBLICOS de `nombre_clase`, caminando.

    la cadena de herencia (Etapa 9, autocompletado tras 'objeto.'). Reutiliza
    directamente ClaseInfo de symbol_table.py -- el mismo mecanismo que ya
    usa el resto del compilador para resolver miembros, no uno paralelo.
    """
    if tabla is None or not nombre_clase or nombre_clase not in tabla.clases:
        return []
    miembros = []
    vistos = set()
    actual = tabla.clases.get(nombre_clase)
    while actual is not None:
        for nombre_attr, info in actual.atributos.items():
            if info.visibilidad == "publico" and nombre_attr not in vistos:
                miembros.append(nombre_attr)
                vistos.add(nombre_attr)
        for nombre_met, sobrecargas in actual.metodos.items():
            if nombre_met not in vistos and any(s.visibilidad == "publico" for s in sobrecargas):
                miembros.append(nombre_met)
                vistos.add(nombre_met)
        actual = tabla.clases.get(actual.padre) if actual.padre else None
    return sorted(miembros)


def _palabra_en_columna(texto, col):
    """Extrae el identificador que contiene (o está pegado a) la columna.

    `col` de `texto` -- para ir-a-definición sobre clic y hover sobre la
    posición del mouse (Etapa 9). Retorna (inicio, fin, palabra), o None
    si `col` no cae sobre ni junto a un identificador.
    """
    n = len(texto)
    if col < 0 or col > n:
        return None

    def es_ident(c):
        """Indica es ident."""
        return c.isalnum() or c == "_"

    if col == n or not es_ident(texto[col]):
        if col > 0 and es_ident(texto[col - 1]):
            col -= 1
        else:
            return None
    inicio = col
    while inicio > 0 and es_ident(texto[inicio - 1]):
        inicio -= 1
    fin = col
    while fin < n and es_ident(texto[fin]):
        fin += 1
    palabra = texto[inicio:fin]
    if not palabra or palabra[0].isdigit():
        return None
    return inicio, fin, palabra


def _resolver_identificador_en(ast, tabla, texto_linea, col, linea):
    """Resuelve a qué declaración apunta el identificador bajo la columna.

    `col` de `linea` (Etapa 9: comparte lógica entre ir-a-definición F12/
    Ctrl+clic y hover). Si está precedido por un punto ('objeto.miembro')
    se resuelve como acceso a miembro; si no, como identificador simple
    (clase/subrutina/parámetro/variable/atributo propio). Retorna
    (linea_decl, columna_decl, descripcion) o None si no se pudo resolver.
    """
    ubic = _palabra_en_columna(texto_linea, col)
    if ubic is None:
        return None
    inicio, _fin, palabra = ubic
    if inicio > 0 and texto_linea[inicio - 1] == ".":
        fin_obj = inicio - 1
        inicio_obj = fin_obj
        while inicio_obj > 0 and (
            texto_linea[inicio_obj - 1].isalnum() or texto_linea[inicio_obj - 1] == "_"
        ):
            inicio_obj -= 1
        nombre_obj = texto_linea[inicio_obj:fin_obj]
        tipo = _tipo_declarado(ast, tabla, nombre_obj, linea)
        miembro = _resolver_miembro(tabla, tipo, palabra)
        if miembro is None:
            return None
        prefijo = "atributo" if not hasattr(miembro, "params_tipos") else "método"
        return miembro.linea, miembro.columna, f"{prefijo}: {miembro.tipo} {palabra}"
    return _resolver_declaracion(ast, tabla, palabra, linea)


class MainWindow(QMainWindow):
    """Ventana principal del IDE."""

    def __init__(self):
        super().__init__()
        self._worker = None
        self._pausado = False
        self._tab_de_ejecucion = None
        self._errores_actuales = []
        self._idx_error = 0
        self._recientes = []
        self._raiz_establecida = False
        self.accion_ejecutar = None
        self.accion_detener = None
        self.accion_depurar = None
        self.accion_paso = None
        self.accion_continuar = None
        self._tema_claro = False
        # Paleta de comandos (Etapa 9): todas las QAction creadas vía
        # self._accion(...) se recolectan automáticamente aquí -- sin
        # mantener una lista separada a mano, como pide el plan.
        self._todas_las_acciones = []

        self.settings = QSettings("InvenioLang", "IDE")

        self.setWindowTitle("InvenioLang 2.0 - Compilador Educativo")
        self.resize(1100, 760)
        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._apply_qss()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Listo")
        self._register_shortcuts()
        self._restaurar_sesion()
        if self.editor_tabs.count() == 0:
            self._nueva_pestana()

    # ============================================================
    # Construcción de la interfaz
    # ============================================================

    def _build_ui(self):
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.setMovable(True)
        self.editor_tabs.tabCloseRequested.connect(self._cerrar_pestana)
        self.editor_tabs.currentChanged.connect(self._al_cambiar_pestana)

        self.buscar_bar = self._crear_barra_buscar()
        self.buscar_bar.hide()

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

        self.panel_tabs = QTabWidget()
        self.texto_salida = _crear_panel()
        self.texto_errores = ErrorTextEdit()
        self.texto_errores.clicked_line.connect(self._al_hacer_click_error)
        self.texto_warn = ErrorTextEdit()
        self.panel_tabs.addTab(self.texto_salida, "Salida")
        self.panel_tabs.addTab(self.texto_errores, "Errores")
        self.panel_tabs.addTab(self.texto_warn, "Advertencias")

        container = QWidget()
        cv = QVBoxLayout(container)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.addWidget(row)
        cv.addWidget(self.panel_tabs, 1)

        # Breadcrumb (Etapa 9): "archivo.inv > Clase > método" según la
        # posición del cursor, calculado desde editor.ast_en_vivo (el AST
        # del análisis en vivo ya existente, ver _analizar_en_vivo).
        self.breadcrumb = QLabel("")
        self.breadcrumb.setObjectName("breadcrumb")
        self.breadcrumb.setContentsMargins(8, 2, 8, 2)

        editor_container = QWidget()
        ecv = QVBoxLayout(editor_container)
        ecv.setContentsMargins(0, 0, 0, 0)
        ecv.setSpacing(0)
        ecv.addWidget(self.buscar_bar)
        ecv.addWidget(self.editor_tabs, 1)
        ecv.addWidget(self.breadcrumb)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(editor_container)
        split.addWidget(container)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        self.setCentralWidget(split)

        self._build_explorador()
        self._build_panel_variables()
        self._build_panel_diagrama()
        self._build_panel_constructor()
        self._build_panel_terminal()

    def _build_explorador(self):
        dock = QDockWidget("Explorador", self)
        dock.setObjectName("dock_explorador")
        self.modelo_archivos = QFileSystemModel()
        self.modelo_archivos.setNameFilters(["*.inv"])
        self.modelo_archivos.setNameFilterDisables(False)
        raiz = self.settings.value("carpeta_trabajo", os.getcwd())
        if not raiz or not os.path.isdir(raiz):
            raiz = os.getcwd()
        self.modelo_archivos.setRootPath(raiz)
        self.arbol_archivos = QTreeView()
        self.arbol_archivos.setModel(self.modelo_archivos)
        self.arbol_archivos.setRootIndex(self.modelo_archivos.index(raiz))
        for col in (1, 2, 3):
            self.arbol_archivos.hideColumn(col)
        self.arbol_archivos.doubleClicked.connect(self._al_hacer_doble_clic_explorador)
        dock.setWidget(self.arbol_archivos)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.dock_explorador = dock
        self._carpeta_trabajo = raiz

    def _build_panel_variables(self):
        dock = QDockWidget("Depurador", self)
        dock.setObjectName("dock_variables")
        cont = QWidget()
        lay = QVBoxLayout(cont)
        lay.addWidget(QLabel("Pila de llamadas:"))
        self.lista_pila = QListWidget()
        self.lista_pila.setMaximumHeight(90)
        lay.addWidget(self.lista_pila)
        lay.addWidget(QLabel("Variables visibles:"))
        self.tabla_variables = QTableWidget(0, 3)
        self.tabla_variables.setHorizontalHeaderLabels(["Nombre", "Tipo", "Valor"])
        self.tabla_variables.horizontalHeader().setStretchLastSection(True)
        self.tabla_variables.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.tabla_variables, 1)
        dock.setWidget(cont)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock_variables = dock
        dock.hide()

    def _build_panel_diagrama(self):
        dock = QDockWidget("Diagrama de flujo", self)
        dock.setObjectName("dock_diagrama")
        cont = QWidget()
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(4, 4, 4, 4)

        fila = QWidget()
        fila_lay = QHBoxLayout(fila)
        fila_lay.setContentsMargins(0, 0, 0, 0)
        fila_lay.addWidget(QLabel("Subrutina:"))
        self.combo_diagrama = QComboBox()
        self.combo_diagrama.currentIndexChanged.connect(self._al_cambiar_subrutina_diagrama)
        fila_lay.addWidget(self.combo_diagrama, 1)
        btn_generar = QPushButton("Generar")
        btn_generar.clicked.connect(self.generar_diagrama)
        fila_lay.addWidget(btn_generar)
        lay.addWidget(fila)

        self.escena_diagrama = QGraphicsScene()
        self.vista_diagrama = _DiagramaView(self.escena_diagrama)
        self.vista_diagrama.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.vista_diagrama.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.vista_diagrama.setBackgroundBrush(QColor(COLORES["fondo"]))
        lay.addWidget(self.vista_diagrama, 1)

        dock.setWidget(cont)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock_diagrama = dock
        self._subrutinas_diagrama = {}  # etiqueta -> Bloque, poblado al generar
        self._diagrama_actual = None
        self._resaltado_diagrama = None
        dock.hide()

    def _build_panel_constructor(self):
        """Constructor de diagramas de flujo (Etapa 13): panel NUEVO y.

        SEPARADO del dock "Diagrama de flujo" de arriba -- ese sigue
        siendo de solo lectura (revela el diagrama de código YA escrito);
        este es de AUTORÍA (el estudiante arma el diagrama insertando
        bloques de una paleta, y el diagrama GENERA el código). El
        estudiante nunca dibuja una flecha a mano -- inserta bloques en
        una posición de una secuencia (después de la caja seleccionada, o
        dentro de una rama/cuerpo seleccionado) y el layout se calcula
        solo, reutilizando `flowchart.py::construir_diagrama` sin ningún
        caso especial (ver `inveniolang/flowchart_builder.py`).
        """
        dock = QDockWidget("Constructor de diagramas", self)
        dock.setObjectName("dock_constructor_diagrama")
        cont = QWidget()
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(4, 4, 4, 4)

        ayuda = QLabel(
            "Arma el algoritmo insertando bloques (se agregan después de la "
            "caja seleccionada, o al inicio de una rama/cuerpo seleccionado). "
            "Doble clic en una caja para editar su texto."
        )
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        paleta = QWidget()
        paleta_lay = QHBoxLayout(paleta)
        paleta_lay.setContentsMargins(0, 0, 0, 0)
        for forma, etiqueta in (
            (fb.PROCESO, "Proceso"),
            (fb.ENTRADA, "Entrada"),
            (fb.SALIDA, "Salida"),
            (fb.DECISION, "Decisión"),
            (fb.MIENTRAS, "Mientras"),
            (fb.HACER_MIENTRAS, "Hacer-mientras"),
            (fb.PARA, "Para"),
        ):
            btn = QPushButton(etiqueta)
            btn.clicked.connect(lambda _=False, f=forma: self._insertar_forma_constructor(f))
            paleta_lay.addWidget(btn)
        lay.addWidget(paleta)

        split = QSplitter(Qt.Orientation.Vertical)
        self.arbol_constructor = QTreeWidget()
        self.arbol_constructor.setHeaderHidden(True)
        self.arbol_constructor.itemDoubleClicked.connect(self._editar_item_constructor)
        self.arbol_constructor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.arbol_constructor.customContextMenuRequested.connect(self._menu_contextual_constructor)
        split.addWidget(self.arbol_constructor)

        self.escena_constructor = QGraphicsScene()
        self.vista_constructor = _DiagramaView(self.escena_constructor)
        self.vista_constructor.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.vista_constructor.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.vista_constructor.setBackgroundBrush(QColor(COLORES["fondo"]))
        split.addWidget(self.vista_constructor)
        lay.addWidget(split, 1)

        fila_botones = QWidget()
        fila_botones_lay = QHBoxLayout(fila_botones)
        fila_botones_lay.setContentsMargins(0, 0, 0, 0)
        btn_nuevo = QPushButton("Nuevo diagrama")
        btn_nuevo.clicked.connect(self.nuevo_diagrama_constructor)
        fila_botones_lay.addWidget(btn_nuevo)
        btn_generar = QPushButton("Generar código InvenioLang")
        btn_generar.clicked.connect(self.generar_codigo_constructor)
        fila_botones_lay.addWidget(btn_generar)
        lay.addWidget(fila_botones)

        dock.setWidget(cont)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock_constructor = dock
        self._bloque_constructor = Bloque([])
        dock.hide()
        self._reconstruir_arbol_constructor()

    def _build_panel_terminal(self):
        """Terminal integrada (Etapa 9): corre el archivo activo con salida.

        EN VIVO (línea a línea, no toda junta al final como el flujo
        Ejecutar/"Entrada simulada" ya existente) y un campo de entrada que
        se habilita cada vez que el programa llama a leer()/read() -- ver
        _HiloEjecucion(interactivo=True). Es un camino de ejecución
        ADICIONAL: no reemplaza ni modifica el Ejecutar por lotes existente.
        """
        dock = QDockWidget("Terminal", self)
        dock.setObjectName("dock_terminal")
        cont = QWidget()
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(4, 4, 4, 4)

        fila_botones = QWidget()
        fb_lay = QHBoxLayout(fila_botones)
        fb_lay.setContentsMargins(0, 0, 0, 0)
        self.accion_terminal_ejecutar = QPushButton("Ejecutar en terminal")
        self.accion_terminal_ejecutar.clicked.connect(self.ejecutar_en_terminal)
        self.accion_terminal_detener = QPushButton("Detener")
        self.accion_terminal_detener.setEnabled(False)
        self.accion_terminal_detener.clicked.connect(self.detener_terminal)
        btn_limpiar = QPushButton("Limpiar")
        btn_limpiar.clicked.connect(lambda: self.texto_terminal.clear())
        fb_lay.addWidget(self.accion_terminal_ejecutar)
        fb_lay.addWidget(self.accion_terminal_detener)
        fb_lay.addWidget(btn_limpiar)
        fb_lay.addStretch(1)
        lay.addWidget(fila_botones)

        self.texto_terminal = _crear_panel()
        lay.addWidget(self.texto_terminal, 1)

        self.entrada_terminal = QLineEdit()
        self.entrada_terminal.setPlaceholderText(
            "Ejecute el archivo para habilitar la entrada (leer/read)…"
        )
        self.entrada_terminal.setEnabled(False)
        self.entrada_terminal.returnPressed.connect(self._enviar_entrada_terminal)
        lay.addWidget(self.entrada_terminal)

        dock.setWidget(cont)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.dock_terminal = dock
        self._worker_terminal = None
        dock.hide()

    def _crear_barra_buscar(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.addWidget(QLabel("Buscar:"))
        self.campo_buscar = QLineEdit()
        lay.addWidget(self.campo_buscar, 1)
        btn_sig = QPushButton("Siguiente")
        btn_sig.clicked.connect(lambda: self._buscar(1))
        lay.addWidget(btn_sig)
        btn_ant = QPushButton("Anterior")
        btn_ant.clicked.connect(lambda: self._buscar(-1))
        lay.addWidget(btn_ant)
        lay.addWidget(QLabel("Reemplazar:"))
        self.campo_reemplazar = QLineEdit()
        lay.addWidget(self.campo_reemplazar, 1)
        btn_reemp = QPushButton("Reemplazar")
        btn_reemp.clicked.connect(self._reemplazar)
        lay.addWidget(btn_reemp)
        btn_reemp_todo = QPushButton("Reemplazar todo")
        btn_reemp_todo.clicked.connect(self._reemplazar_todo)
        lay.addWidget(btn_reemp_todo)
        btn_cerrar = QPushButton("✕")
        btn_cerrar.setFixedWidth(28)
        btn_cerrar.clicked.connect(w.hide)
        lay.addWidget(btn_cerrar)
        return w

    def _accion(self, texto, atajo, fn, menu, icono=None):
        """Crea una QAction. `icono` es opcional -- un QStyle.StandardPixmap.

        (icono estándar del sistema, sin dependencias nuevas, Etapa 9) que
        se usa tanto en el menú como en la barra de herramientas si la
        acción se agrega ahí después.
        """
        a = QAction(texto, self)
        if atajo:
            a.setShortcut(atajo)
        if icono is not None:
            a.setIcon(self.style().standardIcon(icono))
        a.triggered.connect(lambda: fn())
        menu.addAction(a)
        self._todas_las_acciones.append(a)
        return a

    def _build_menu(self):
        mb = self.menuBar()

        m = mb.addMenu("Archivo")
        self.accion_nuevo = self._accion(
            "Nuevo",
            QKeySequence.StandardKey.New,
            self.nuevo_archivo,
            m,
            icono=QStyle.StandardPixmap.SP_FileIcon,
        )
        self.accion_abrir = self._accion(
            "Abrir...",
            QKeySequence.StandardKey.Open,
            self.abrir_archivo,
            m,
            icono=QStyle.StandardPixmap.SP_DialogOpenButton,
        )
        self.accion_guardar = self._accion(
            "Guardar",
            QKeySequence.StandardKey.Save,
            self.guardar_archivo,
            m,
            icono=QStyle.StandardPixmap.SP_DialogSaveButton,
        )
        self._accion("Guardar como...", None, self.guardar_como, m)
        self._accion("Cerrar pestaña", QKeySequence("Ctrl+W"), self._cerrar_pestana_actual, m)
        m.addSeparator()
        self.menu_recientes = m.addMenu("Abrir reciente")
        self._actualizar_menu_recientes()
        m.addSeparator()
        self._accion("Configuración...", None, self._abrir_configuracion, m)
        m.addSeparator()
        self._accion("Salir", None, self.close, m)

        mv = mb.addMenu("Ver")
        self._accion(
            "Explorador de archivos",
            "Ctrl+B",
            lambda: self.dock_explorador.setVisible(not self.dock_explorador.isVisible()),
            mv,
        )
        self._accion(
            "Panel del depurador",
            None,
            lambda: self.dock_variables.setVisible(not self.dock_variables.isVisible()),
            mv,
        )
        self._accion(
            "Diagrama de flujo",
            None,
            lambda: self.dock_diagrama.setVisible(not self.dock_diagrama.isVisible()),
            mv,
        )
        self._accion(
            "Constructor de diagramas",
            None,
            lambda: self.dock_constructor.setVisible(not self.dock_constructor.isVisible()),
            mv,
        )
        self._accion(
            "Terminal",
            QKeySequence("Ctrl+`"),
            lambda: self.dock_terminal.setVisible(not self.dock_terminal.isVisible()),
            mv,
        )
        self._accion("Buscar / Reemplazar", None, self._mostrar_buscar, mv)
        mv.addSeparator()
        self._accion(
            "Paleta de comandos...", QKeySequence("Ctrl+Shift+P"), self._mostrar_paleta_comandos, mv
        )

        me = mb.addMenu("Ejecutar")
        self.accion_ejecutar = self._accion(
            "Ejecutar",
            QKeySequence("Ctrl+R"),
            self.ejecutar,
            me,
            icono=QStyle.StandardPixmap.SP_MediaPlay,
        )
        self.accion_depurar = self._accion(
            "Depurar (con breakpoints)",
            QKeySequence("F5"),
            self.depurar,
            me,
            icono=QStyle.StandardPixmap.SP_MediaSeekForward,
        )
        self.accion_paso = self._accion(
            "Paso", QKeySequence("F10"), self.paso, me, icono=QStyle.StandardPixmap.SP_ArrowForward
        )
        self.accion_continuar = self._accion(
            "Continuar",
            QKeySequence("F6"),
            self.continuar,
            me,
            icono=QStyle.StandardPixmap.SP_MediaSkipForward,
        )
        self.accion_detener = self._accion(
            "Detener",
            QKeySequence("Ctrl+."),
            self.detener,
            me,
            icono=QStyle.StandardPixmap.SP_MediaStop,
        )
        self.accion_paso.setEnabled(False)
        self.accion_continuar.setEnabled(False)
        self.accion_detener.setEnabled(False)
        me.addSeparator()
        self._accion(
            "Alternar breakpoint en línea actual",
            QKeySequence("F9"),
            self._alternar_breakpoint_actual,
            me,
        )
        me.addSeparator()
        self._accion("Ir a definición", QKeySequence("F12"), lambda: self._ir_a_definicion(), me)
        me.addSeparator()
        self._accion("Revisar (estático)", None, self.revisar, me)
        self._accion("Mostrar Tokens", None, self.mostrar_tokens, me)
        self._accion("Mostrar AST", None, self.mostrar_ast, me)
        self._accion("Mostrar código intermedio", None, self.mostrar_ir, me)
        self._accion("Mostrar código objetivo", None, self.mostrar_objetivo, me)
        self._accion(
            "Mostrar código objetivo con registros", None, self.mostrar_objetivo_registros, me
        )
        self._accion("Mostrar diagrama de flujo", None, self.generar_diagrama, me)
        self._accion("Constructor de diagramas de flujo", None, self.abrir_constructor_diagrama, me)

        ay = mb.addMenu("Ayuda")
        self._accion("Documentación (F1)", "F1", self._abrir_documentacion, ay)
        self._accion("Guía rápida", None, lambda: self._mostrar_ayuda("Guía rápida", _DOC_GUIA), ay)
        self._accion(
            "Referencia del lenguaje",
            None,
            lambda: self._mostrar_ayuda("Referencia del lenguaje", _DOC_REFERENCIA),
            ay,
        )
        self._accion(
            "Funciones integradas",
            None,
            lambda: self._mostrar_ayuda("Funciones integradas", _DOC_FUNCIONES),
            ay,
        )
        self._accion(
            "Catálogo de errores",
            None,
            lambda: self._mostrar_ayuda("Catálogo de errores", _DOC_ERRORES),
            ay,
        )
        self._accion(
            "Atajos de teclado",
            None,
            lambda: self._mostrar_ayuda("Atajos de teclado", _DOC_ATAJOS),
            ay,
        )
        ay.addSeparator()
        subm = ay.addMenu("Ejemplos")
        for nombre in EJEMPLOS:
            a = QAction(nombre, self)
            a.triggered.connect(lambda _=False, n=nombre: self._cargar_ejemplo(n))
            subm.addAction(a)
        ay.addSeparator()
        self._accion("Acerca de", None, self.mostrar_acerca, ay)

    def _build_toolbar(self):
        tb = QToolBar("Principal", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self.accion_nuevo)
        tb.addAction(self.accion_abrir)
        tb.addAction(self.accion_guardar)
        tb.addSeparator()
        tb.addAction(self.accion_ejecutar)
        tb.addAction(self.accion_depurar)
        tb.addAction(self.accion_paso)
        tb.addAction(self.accion_continuar)
        tb.addAction(self.accion_detener)

    def _register_shortcuts(self):
        QShortcut(QKeySequence("F8"), self, activated=lambda: self._siguiente_error(1))
        QShortcut(QKeySequence("Shift+F8"), self, activated=lambda: self._siguiente_error(-1))
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self._ir_a_linea)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._mostrar_buscar)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self._mostrar_buscar)
        QShortcut(QKeySequence("Ctrl+Tab"), self, activated=lambda: self._siguiente_pestana(1))
        QShortcut(
            QKeySequence("Ctrl+Shift+Tab"), self, activated=lambda: self._siguiente_pestana(-1)
        )

    def _apply_qss(self):
        self.setStyleSheet(
            f"QMainWindow, QDialog {{ background: {COLORES['fondo']}; }}\n"
            f"QPlainTextEdit {{ background: {COLORES['fondo']}; "
            f"color: {COLORES['texto']}; border: 1px solid {COLORES['gutter_borde']}; }}\n"
            f"QStatusBar, QTabWidget::pane {{ background: {COLORES['panel']}; }}\n"
            f"#breadcrumb {{ background: {COLORES['panel']}; "
            f"color: {COLORES['gutter_linea']}; "
            f"border-top: 1px solid {COLORES['gutter_borde']}; }}"
        )

    # ============================================================
    # Configuración: tema y tamaño de fuente (Etapa 5)
    # ============================================================

    def _aplicar_paleta_panel(self, widget):
        pal = widget.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor(COLORES["panel"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(COLORES["texto"]))
        widget.setPalette(pal)

    def _aplicar_tema(self, claro):
        """Cambia de tema EN VIVO, sin reiniciar: `COLORES` se muta.

        in-place (no se reasigna), así que todo lo que ya lee `COLORES[...]`
        en tiempo de pintado (el gutter, por ejemplo) se entera solo; lo
        que quedó horneado en la construcción (highlighter, paletas fijas)
        se reaplica explícitamente aquí.
        """
        self._tema_claro = claro
        COLORES.clear()
        COLORES.update(TEMA_CLARO if claro else TEMA_OSCURO)
        self._apply_qss()
        for t in (
            getattr(self, "texto_salida", None),
            getattr(self, "texto_errores", None),
            getattr(self, "texto_warn", None),
        ):
            if t is not None:
                self._aplicar_paleta_panel(t)
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            editor._pintar_paleta()
            editor.highlighter.actualizar_colores()
            editor.line_number_area.update()
        if hasattr(self, "vista_diagrama"):
            self.vista_diagrama.setBackgroundBrush(QColor(COLORES["fondo"]))
        self.settings.setValue("tema", "claro" if claro else "oscuro")

    def _aplicar_tamano_fuente(self, tam):
        CodeEditor.TAMANO_FUENTE_DEFECTO = tam
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            fuente = editor.font()
            fuente.setPointSize(tam)
            editor.setFont(fuente)
            editor.setTabStopDistance(4 * QFontMetrics(fuente).horizontalAdvance(" "))
            editor._update_line_number_area_width()
        self.settings.setValue("fuente_tamano", tam)

    def _abrir_configuracion(self):
        d, lay = self._crear_dialogo("Configuración")
        d.resize(340, 150)

        fila_tema = QWidget()
        fl = QHBoxLayout(fila_tema)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(QLabel("Tema:"))
        combo_tema = QComboBox()
        combo_tema.addItems(["Oscuro", "Claro"])
        combo_tema.setCurrentIndex(1 if self._tema_claro else 0)
        combo_tema.currentIndexChanged.connect(lambda i: self._aplicar_tema(i == 1))
        fl.addWidget(combo_tema, 1)
        lay.addWidget(fila_tema)

        fila_fuente = QWidget()
        ffl = QHBoxLayout(fila_fuente)
        ffl.setContentsMargins(0, 0, 0, 0)
        ffl.addWidget(QLabel("Tamaño de fuente del editor:"))
        spin_fuente = QSpinBox()
        spin_fuente.setRange(8, 24)
        spin_fuente.setValue(CodeEditor.TAMANO_FUENTE_DEFECTO)
        spin_fuente.valueChanged.connect(self._aplicar_tamano_fuente)
        ffl.addWidget(spin_fuente, 1)
        lay.addWidget(fila_fuente)

        lay.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(d.reject)
        bb.clicked.connect(d.accept)
        lay.addWidget(bb)
        d.exec()

    # ============================================================
    # Pestañas
    # ============================================================

    def _tab_actual(self):
        return self.editor_tabs.currentWidget()

    def _tab_valida(self, editor):
        return editor is not None and self.editor_tabs.indexOf(editor) >= 0

    def _titulo_pestana(self, editor):
        base = os.path.basename(editor.ruta) if editor.ruta else "Sin título"
        return ("* " if editor.modificado else "") + base

    def _icono_pestana(self, editor):
        """Icono por tipo de pestaña (Etapa 9): archivo .inv guardado vs.

        pestaña nueva sin guardar aún -- icono estándar de QStyle, sin
        depender de un set de iconos externo.
        """
        pixmap = (
            QStyle.StandardPixmap.SP_FileIcon
            if editor.ruta
            else QStyle.StandardPixmap.SP_FileDialogNewFolder
        )
        return self.style().standardIcon(pixmap)

    def _actualizar_titulo_pestana(self, editor):
        idx = self.editor_tabs.indexOf(editor)
        if idx >= 0:
            self.editor_tabs.setTabText(idx, self._titulo_pestana(editor))
            self.editor_tabs.setTabToolTip(idx, editor.ruta or "Sin título")
            self.editor_tabs.setTabIcon(idx, self._icono_pestana(editor))
        self._actualizar_titulo_ventana()

    def _actualizar_titulo_ventana(self):
        editor = self._tab_actual()
        if editor is not None:
            self.setWindowTitle(f"InvenioLang 2.0 - {self._titulo_pestana(editor)}")
        else:
            self.setWindowTitle("InvenioLang 2.0 - Compilador Educativo")

    def _nueva_pestana(self, ruta=None, codigo=""):
        editor = CodeEditor()
        editor.ruta = ruta
        editor.cargando = True
        if codigo:
            editor.setPlainText(codigo)
        editor.document().setModified(False)
        editor.cargando = False
        editor.textChanged.connect(lambda e=editor: self._on_edit(e))
        editor._job_en_vivo.timeout.connect(lambda e=editor: self._analizar_en_vivo(e))
        editor.cursorPositionChanged.connect(lambda e=editor: self._actualizar_breadcrumb(e))
        editor.solicitud_definicion.connect(lambda e=editor: self._ir_a_definicion(e))
        idx = self.editor_tabs.addTab(
            editor, self._icono_pestana(editor), self._titulo_pestana(editor)
        )
        self.editor_tabs.setCurrentIndex(idx)
        self._analizar_en_vivo(editor)
        return editor

    def _encontrar_pestana(self, ruta):
        ruta_abs = os.path.abspath(ruta)
        for i in range(self.editor_tabs.count()):
            e = self.editor_tabs.widget(i)
            if e.ruta and os.path.abspath(e.ruta) == ruta_abs:
                return i
        return -1

    def _cerrar_pestana(self, idx):
        editor = self.editor_tabs.widget(idx)
        if editor is None:
            return
        if editor.modificado:
            resp = QMessageBox.question(
                self,
                "Confirmar",
                f"«{self._titulo_pestana(editor).lstrip('* ')}» tiene cambios sin "
                "guardar. ¿Descartarlos y cerrar?",
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        editor._job_en_vivo.stop()
        self.editor_tabs.removeTab(idx)
        editor.deleteLater()
        if self.editor_tabs.count() == 0:
            self._nueva_pestana()

    def _cerrar_pestana_actual(self):
        idx = self.editor_tabs.currentIndex()
        if idx >= 0:
            self._cerrar_pestana(idx)

    def _siguiente_pestana(self, delta):
        n = self.editor_tabs.count()
        if n == 0:
            return
        idx = (self.editor_tabs.currentIndex() + delta) % n
        self.editor_tabs.setCurrentIndex(idx)

    def _al_cambiar_pestana(self, _idx):
        self._actualizar_titulo_ventana()
        self._actualizar_breadcrumb(self._tab_actual())

    # ============================================================
    # Operaciones de archivo
    # ============================================================

    def _on_edit(self, editor):
        if editor.cargando:
            return
        editor.modificado = True
        self._actualizar_titulo_pestana(editor)
        editor._job_en_vivo.start()

    def nuevo_archivo(self):
        """Crea un archivo nuevo."""
        self._nueva_pestana()
        self.statusBar().showMessage("Nuevo archivo")

    def _abrir_ruta(self, ruta):
        idx = self._encontrar_pestana(ruta)
        if idx >= 0:
            self.editor_tabs.setCurrentIndex(idx)
            return self.editor_tabs.widget(idx)
        try:
            with open(ruta, encoding="utf-8") as f:
                codigo = f.read()
        except UnicodeDecodeError as e:
            # §2.1: un archivo que no sea UTF-8 valido se rechaza con el codigo
            # del catalogo, el mismo que daria la CLI.
            QMessageBox.critical(
                self,
                "Codificación inválida",
                f"[IL-LEX-001] {os.path.basename(ruta)}\n\n"
                f"El archivo no está codificado en UTF-8 válido "
                f"(byte inválido en la posición {e.start}).\n\n"
                f"InvenioLang exige archivos fuente en UTF-8.",
            )
            return None
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el archivo:\n{e}")
            return None
        editor = self._nueva_pestana(ruta=ruta, codigo=codigo)
        self._agregar_reciente(ruta)
        if not self._raiz_establecida:
            self._establecer_carpeta_trabajo(ruta)
            self._raiz_establecida = True
        self.statusBar().showMessage(f"Abierto: {ruta}")
        return editor

    def abrir_archivo(self):
        """Abre un archivo .inv."""
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir archivo InvenioLang", "", "Archivos InvenioLang (*.inv);;Todos (*.*)"
        )
        if not ruta:
            return
        self._abrir_ruta(ruta)

    def guardar_archivo(self):
        """Guarda archivo."""
        editor = self._tab_actual()
        if editor is None:
            return
        if editor.ruta:
            try:
                with open(editor.ruta, "w", encoding="utf-8") as f:
                    f.write(editor.toPlainText())
                editor.modificado = False
                editor.document().setModified(False)
                self._actualizar_titulo_pestana(editor)
                self.statusBar().showMessage(f"Guardado: {editor.ruta}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")
        else:
            self.guardar_como()

    def guardar_como(self):
        """Guarda como."""
        editor = self._tab_actual()
        if editor is None:
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar archivo InvenioLang", "", "Archivos InvenioLang (*.inv);;Todos (*.*)"
        )
        if not ruta:
            return
        if not ruta.lower().endswith(".inv"):
            ruta += ".inv"
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            editor.ruta = ruta
            editor.modificado = False
            editor.document().setModified(False)
            self._actualizar_titulo_pestana(editor)
            self._agregar_reciente(ruta)
            self.statusBar().showMessage(f"Guardado: {ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    # ============================================================
    # Explorador de archivos
    # ============================================================

    def _establecer_carpeta_trabajo(self, ruta):
        carpeta = os.path.dirname(os.path.abspath(ruta))
        if carpeta and carpeta != getattr(self, "_carpeta_trabajo", None):
            self._carpeta_trabajo = carpeta
            self.modelo_archivos.setRootPath(carpeta)
            self.arbol_archivos.setRootIndex(self.modelo_archivos.index(carpeta))

    def _al_hacer_doble_clic_explorador(self, indice):
        ruta = self.modelo_archivos.filePath(indice)
        if os.path.isfile(ruta):
            self._abrir_ruta(ruta)

    # ============================================================
    # Archivos recientes
    # ============================================================

    def _agregar_reciente(self, ruta):
        ruta = os.path.abspath(ruta)
        self._recientes = [r for r in self._recientes if r != ruta]
        self._recientes.insert(0, ruta)
        self._recientes = self._recientes[:10]
        self._actualizar_menu_recientes()

    def _actualizar_menu_recientes(self):
        self.menu_recientes.clear()
        if not self._recientes:
            a = QAction("(vacío)", self)
            a.setEnabled(False)
            self.menu_recientes.addAction(a)
            return
        for ruta in self._recientes:
            a = QAction(ruta, self)
            a.triggered.connect(lambda _=False, r=ruta: self._abrir_ruta(r))
            self.menu_recientes.addAction(a)

    # ============================================================
    # Buscar / Reemplazar
    # ============================================================

    def _mostrar_buscar(self):
        self.buscar_bar.show()
        self.campo_buscar.setFocus()
        self.campo_buscar.selectAll()

    def _buscar(self, direccion):
        editor = self._tab_actual()
        if editor is None:
            return
        texto = self.campo_buscar.text()
        if not texto:
            return
        if direccion < 0:
            encontrado = editor.find(texto, QTextDocument.FindFlag.FindBackward)
        else:
            encontrado = editor.find(texto)
        if not encontrado:
            cursor = editor.textCursor()
            cursor.movePosition(
                QTextCursor.MoveOperation.End if direccion > 0 else QTextCursor.MoveOperation.Start
            )
            editor.setTextCursor(cursor)
            if direccion < 0:
                editor.find(texto, QTextDocument.FindFlag.FindBackward)
            else:
                editor.find(texto)

    def _reemplazar(self):
        editor = self._tab_actual()
        if editor is None:
            return
        cursor = editor.textCursor()
        if cursor.hasSelectedText() and cursor.selectedText() == self.campo_buscar.text():
            cursor.insertText(self.campo_reemplazar.text())
        self._buscar(1)

    def _reemplazar_todo(self):
        editor = self._tab_actual()
        if editor is None:
            return
        buscar, reemplazo = self.campo_buscar.text(), self.campo_reemplazar.text()
        if not buscar:
            return
        doc = editor.document()
        cursor_edicion = editor.textCursor()
        cursor_edicion.beginEditBlock()
        cursor = QTextCursor(doc)
        n = 0
        while True:
            cursor = doc.find(buscar, cursor)
            if cursor.isNull():
                break
            cursor.insertText(reemplazo)
            n += 1
        cursor_edicion.endEditBlock()
        self.statusBar().showMessage(f"{n} reemplazo(s)")

    # ============================================================
    # Ejecución
    # ============================================================

    def _iniciar_ejecucion(self, depurar=False):
        editor = self._tab_actual()
        if editor is None:
            return
        codigo = editor.toPlainText().strip()
        if not codigo:
            QMessageBox.warning(self, "Advertencia", "El editor está vacío")
            return
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "En ejecución",
                "Ya hay un programa ejecutándose. Use Detener para interrumpirlo.",
            )
            return
        entrada_str = self.entry_input.text().strip()
        entrada = entrada_str.split() if entrada_str else None
        nombre = editor.ruta or "<sin_titulo>"
        self.statusBar().showMessage("Compilando...")

        em = ErrorManager()
        lexer = Lexer(em)
        lexer.tokenizar(codigo, nombre)
        if em.hay_errores():
            self._mostrar_errores(em, editor)
            self.panel_tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error léxico")
            return
        parser = Parser(lexer, em)
        ast, em = parser.analizar(codigo, nombre)
        if em.hay_errores():
            self._mostrar_errores(em, editor)
            self.panel_tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error sintáctico")
            return
        semantico = SemanticAnalyzer(em)
        tabla = semantico.analizar(ast)
        if em.hay_errores():
            self._mostrar_errores(em, editor)
            self.panel_tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error semántico")
            return
        if em.warnings:
            self._mostrar_advertencias(em)
        tc = TypeChecker(em, tabla)
        tc.verificar(ast)
        if em.hay_errores():
            self._mostrar_errores(em, editor)
            self.panel_tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error de tipos")
            return

        # La interpretación corre en un hilo aparte para que la ventana no se
        # congele con un programa lento o con un ciclo sin terminación, y para
        # que el botón Detener pueda interrumpirlo (o desbloquear una pausa
        # del depurador).
        self._tab_de_ejecucion = editor
        self._pausado = False
        self._worker = _HiloEjecucion(
            ast, tabla, em, entrada, breakpoints=editor.breakpoints, depurar=depurar, parent=self
        )
        self._worker.terminado.connect(self._al_terminar_ejecucion)
        if depurar:
            self._worker.pausado.connect(self._al_pausar)
        self._marcar_ejecutando(True)
        self.statusBar().showMessage("Depurando..." if depurar else "Ejecutando...")
        self._worker.start()

    def ejecutar(self):
        """Ejecuta el programa."""
        self._iniciar_ejecucion(depurar=False)

    def depurar(self):
        """Inicia la depuración."""
        self._iniciar_ejecucion(depurar=True)

    def paso(self):
        """Avanza un paso de depuración."""
        if self._worker is not None:
            self._pausado = False
            self._marcar_ejecutando(True)
            self._worker.paso()

    def continuar(self):
        """Continúa la ejecución."""
        if self._worker is not None:
            self._pausado = False
            self._marcar_ejecutando(True)
            self._worker.continuar()

    def detener(self):
        """Interrumpe el programa en ejecución.

        incluso si está pausado en un breakpoint.
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancelar()
            self.statusBar().showMessage("Deteniendo...")

    def _alternar_breakpoint_actual(self):
        editor = self._tab_actual()
        if editor is None:
            return
        linea = editor.textCursor().blockNumber() + 1
        editor.alternar_breakpoint(linea)

    def _marcar_ejecutando(self, activo):
        """Habilita o deshabilita las acciones según haya ejecución en curso."""
        if self.accion_ejecutar is not None:
            self.accion_ejecutar.setEnabled(not activo)
        if self.accion_depurar is not None:
            self.accion_depurar.setEnabled(not activo)
        if self.accion_detener is not None:
            self.accion_detener.setEnabled(activo)
        en_pausa = activo and self._pausado
        if self.accion_paso is not None:
            self.accion_paso.setEnabled(en_pausa)
        if self.accion_continuar is not None:
            self.accion_continuar.setEnabled(en_pausa)

    def _al_pausar(self, snap):
        self._pausado = True
        self._marcar_ejecutando(True)
        self._actualizar_panel_variables(snap)
        if self._tab_valida(self._tab_de_ejecucion):
            self._saltar_a_linea(
                self._tab_de_ejecucion, snap.get("linea", 1), snap.get("columna", 1) or 1
            )
        self._resaltar_en_diagrama(snap)
        self.statusBar().showMessage(f"Pausado en línea {snap.get('linea', '?')}")

    def _actualizar_panel_variables(self, snap):
        self.dock_variables.show()
        variables = snap.get("variables", [])
        self.tabla_variables.setRowCount(len(variables))
        for i, v in enumerate(variables):
            self.tabla_variables.setItem(i, 0, QTableWidgetItem(str(v["nombre"])))
            self.tabla_variables.setItem(i, 1, QTableWidgetItem(str(v["tipo"])))
            self.tabla_variables.setItem(i, 2, QTableWidgetItem(repr(v["valor"])))
        self.lista_pila.clear()
        pila = snap.get("pila", [])
        self.lista_pila.addItems(pila if pila else ["(main)"])

    def _al_terminar_ejecucion(self, salida, em, cancelado, fallo):
        self._pausado = False
        self._marcar_ejecutando(False)
        self._worker = None
        self._quitar_resaltado_diagrama()
        if fallo:
            self._agregar_panel(self.texto_errores, f"Error inesperado: {fallo}\n")
            self.panel_tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error de ejecución")
            return
        if cancelado:
            self.texto_salida.setPlainText(
                "".join(salida) + "\n\n--- Ejecución detenida por el usuario ---"
            )
            self.panel_tabs.setCurrentIndex(0)
            self.statusBar().showMessage("Ejecución detenida")
            return
        if em.hay_errores():
            self._mostrar_errores(em)
            self.panel_tabs.setCurrentIndex(1)
            self.statusBar().showMessage("Error de ejecución")
            return
        self.texto_salida.setPlainText("".join(salida))
        self.panel_tabs.setCurrentIndex(0)
        self.statusBar().showMessage("Ejecución exitosa")

    # ============================================================
    # Terminal integrada (Etapa 9) -- camino de ejecución ADICIONAL al
    # Ejecutar por lotes de arriba: salida en vivo (línea a línea) y un
    # campo de entrada que se habilita en cada leer()/read(), en vez de
    # requerir toda la entrada precargada de antemano en "Entrada
    # (simulada)". Reutiliza el mismo _HiloEjecucion con interactivo=True.
    # ============================================================

    def ejecutar_en_terminal(self):
        """Ejecuta en terminal."""
        editor = self._tab_actual()
        if editor is None:
            return
        codigo = editor.toPlainText().strip()
        if not codigo:
            QMessageBox.warning(self, "Advertencia", "El editor está vacío")
            return
        if self._worker_terminal is not None and self._worker_terminal.isRunning():
            QMessageBox.information(
                self,
                "En ejecución",
                "Ya hay un programa ejecutándose en la terminal. Use Detener para interrumpirlo.",
            )
            return
        nombre = editor.ruta or "<sin_titulo>"

        em = ErrorManager()
        lexer = Lexer(em)
        lexer.tokenizar(codigo, nombre)
        if not em.hay_errores():
            parser = Parser(lexer, em)
            ast, em = parser.analizar(codigo, nombre)
            if ast is not None and not em.hay_errores():
                semantico = SemanticAnalyzer(em)
                tabla = semantico.analizar(ast)
                if not em.hay_errores():
                    tc = TypeChecker(em, tabla)
                    tc.verificar(ast)
        if em.hay_errores():
            self.texto_terminal.appendPlainText(
                "=== Errores de compilación ===\n" + "\n".join(em.obtener_reportes())
            )
            self.dock_terminal.show()
            return

        self.texto_terminal.clear()
        self.texto_terminal.appendPlainText(f"$ ejecutando {os.path.basename(nombre)}")
        self.entrada_terminal.setEnabled(False)
        self.accion_terminal_ejecutar.setEnabled(False)
        self.accion_terminal_detener.setEnabled(True)
        self.dock_terminal.show()

        self._worker_terminal = _HiloEjecucion(ast, tabla, em, None, interactivo=True, parent=self)
        self._worker_terminal.linea_salida.connect(self._agregar_linea_terminal)
        self._worker_terminal.solicitud_entrada.connect(self._habilitar_entrada_terminal)
        self._worker_terminal.terminado.connect(self._al_terminar_ejecucion_terminal)
        self._worker_terminal.start()

    def detener_terminal(self):
        """Detiene la terminal integrada."""
        if self._worker_terminal is not None and self._worker_terminal.isRunning():
            self._worker_terminal.cancelar()
            self.statusBar().showMessage("Deteniendo terminal...")

    def _agregar_linea_terminal(self, texto):
        """Slot de `linea_salida` -- se ejecuta en el hilo de la GUI (Qt.

        encola la señal automáticamente porque se emitió desde otro hilo),
        así que tocar el widget aquí es seguro.
        """
        cursor = self.texto_terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(texto)
        self.texto_terminal.setTextCursor(cursor)
        self.texto_terminal.ensureCursorVisible()

    def _habilitar_entrada_terminal(self):
        self.entrada_terminal.setEnabled(True)
        self.entrada_terminal.setFocus()
        self.statusBar().showMessage("El programa espera una entrada (leer/read)...")

    def _enviar_entrada_terminal(self):
        if self._worker_terminal is None or not self._worker_terminal.isRunning():
            return
        texto = self.entrada_terminal.text()
        self._agregar_linea_terminal(f"> {texto}\n")
        self.entrada_terminal.clear()
        self.entrada_terminal.setEnabled(False)
        self._worker_terminal.recibir_entrada(texto)

    def _al_terminar_ejecucion_terminal(self, salida, em, cancelado, fallo):
        self._worker_terminal = None
        self.accion_terminal_ejecutar.setEnabled(True)
        self.accion_terminal_detener.setEnabled(False)
        self.entrada_terminal.setEnabled(False)
        if fallo:
            self._agregar_linea_terminal(f"\n=== Error inesperado: {fallo} ===\n")
            self.statusBar().showMessage("Error de ejecución (terminal)")
            return
        if cancelado:
            self._agregar_linea_terminal("\n--- Detenido por el usuario ---\n")
            self.statusBar().showMessage("Terminal: ejecución detenida")
            return
        if em.hay_errores():
            self._agregar_linea_terminal(
                "\n=== Errores de ejecución ===\n" + "\n".join(em.obtener_reportes()) + "\n"
            )
            self.statusBar().showMessage("Error de ejecución (terminal)")
            return
        self._agregar_linea_terminal("\n--- Fin de ejecución ---\n")
        self.statusBar().showMessage("Terminal: ejecución exitosa")

    def revisar(self):
        """Análisis estático completo sin ejecutar (como el CLI --check)."""
        editor = self._tab_actual()
        if editor is None:
            return
        codigo = editor.toPlainText().strip()
        if not codigo:
            return
        nombre = editor.ruta or "<sin_titulo>"
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
        lineas.append(
            ("OK" if n_err == 0 else "ERROR") + f" - {n_err} error(es), {n_warn} advertencia(s)"
        )
        self._errores_actuales = list(em.errores)
        self._tab_de_ejecucion = editor
        self.texto_salida.setPlainText("\n".join(lineas))
        self.panel_tabs.setCurrentIndex(0)
        self.statusBar().showMessage("Revisión estática completada")

    def limpiar_resultados(self):
        """Limpia los resultados."""
        for t in (self.texto_salida, self.texto_errores, self.texto_warn):
            t.clear()
        self._errores_actuales = []
        editor = self._tab_actual()
        if editor is not None:
            self._limpiar_marcadores(editor)
        self.statusBar().showMessage("Resultados limpiados")

    def _mostrar_errores(self, em, editor=None):
        # obtener_reportes() ya devuelve las cadenas formateadas (§15.8.1)
        self.texto_errores.setPlainText("\n".join(em.obtener_reportes()))
        self._errores_actuales = list(em.errores)
        self._idx_error = 0
        if editor is not None:
            self._tab_de_ejecucion = editor

    def _mostrar_advertencias(self, em):
        self.texto_warn.setPlainText("\n".join(em.obtener_advertencias()))

    def _agregar_panel(self, widget, texto):
        widget.setPlainText(widget.toPlainText() + texto)

    # ============================================================
    # Análisis en vivo y marcado de problemas (estilo IDE)
    # ============================================================

    def _limpiar_marcadores(self, editor):
        editor.set_problemas([])

    def _char_pos(self, editor, linea, col):
        doc = editor.document()
        block = doc.findBlockByNumber(max(linea - 1, 0))
        fin = block.position() + max(block.length() - 1, 0)
        return min(block.position() + max(col - 1, 0), fin)

    def _longitud_token(self, editor, linea, col):
        doc = editor.document()
        block = doc.findBlockByNumber(max(linea - 1, 0))
        texto = block.text()
        c = max(col - 1, 0)
        if c < 0 or c >= len(texto):
            return 1
        i = c
        while i < len(texto) and not texto[i].isspace() and texto[i] not in ";{}()[],+-*/%=<>&|!":
            i += 1
        return max(i - c, 1)

    def _marcar_problemas(self, editor, errores, warnings):
        problema = []

        for err, es_error in [(e, True) for e in errores] + [(w, False) for w in warnings]:
            linea, col = err.linea, max(err.columna - 1, 0)
            start = self._char_pos(editor, linea, col)
            end = start + self._longitud_token(editor, linea, col)
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            if es_error:
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                fmt.setUnderlineColor(QColor(COLORES["error_sub"]))
                fmt.setBackground(QColor(COLORES["error_fondo"]))
            else:
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DashUnderline)
                fmt.setUnderlineColor(QColor(COLORES["warn_sub"]))
                fmt.setBackground(QColor(COLORES["warn_fondo"]))
            sel.format = fmt
            sel.cursor = QTextCursor(editor.document())
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            problema.append(sel)
        editor.set_problemas(problema)

    def _actualizar_breadcrumb(self, editor):
        """Breadcrumb (Etapa 9): 'archivo.inv > Clase > método', calculado.

        desde editor.ast_en_vivo (el AST del análisis en vivo) y la línea
        actual del cursor. Solo actualiza si `editor` es la pestaña visible
        -- si el cursor cambió en una pestaña de fondo, se ignora.
        """
        if not self._tab_valida(editor) or editor is not self._tab_actual():
            return
        nombre_archivo = os.path.basename(editor.ruta) if editor.ruta else "Sin título"
        linea = editor.textCursor().blockNumber() + 1
        clase, sub = _ubicar_contexto(editor.ast_en_vivo, linea)
        partes = [nombre_archivo]
        if clase:
            partes.append(clase)
        if sub:
            partes.append(sub)
        self.breadcrumb.setText(" › ".join(partes))

    def _analizar_en_vivo(self, editor):
        if not self._tab_valida(editor):
            return
        codigo = editor.toPlainText()
        if not codigo.strip():
            editor.errores_actuales = []
            editor.ast_en_vivo = None
            editor.tabla_en_vivo = None
            self._limpiar_marcadores(editor)
            if editor is self._tab_actual():
                self.statusBar().showMessage("Listo")
                self._actualizar_breadcrumb(editor)
            return
        em = ErrorManager()
        try:
            lexer = Lexer(em)
            lexer.tokenizar(codigo, "<en_vivo>")
            if not em.hay_errores():
                parser = Parser(lexer, em)
                ast, em = parser.analizar(codigo, "<en_vivo>")
                if ast is not None:
                    # Se conserva aunque el resto de las fases falle (ver
                    # el comentario en CodeEditor.__init__): IntelliSense
                    # sigue funcionando sobre el último AST bien formado
                    # mientras el usuario termina de escribir.
                    editor.ast_en_vivo = ast
                if ast is not None and not em.hay_errores():
                    sem = SemanticAnalyzer(em)
                    tabla = sem.analizar(ast)
                    editor.tabla_en_vivo = tabla
                    if not em.hay_errores():
                        tc = TypeChecker(em, tabla)
                        tc.verificar(ast)
        except Exception:  # noqa: S110 - análisis en vivo best-effort con parciales
            pass
        editor.errores_actuales = list(em.errores)
        self._marcar_problemas(editor, em.errores, em.warnings)
        if editor is self._tab_actual():
            n_err, n_warn = len(em.errores), len(em.warnings)
            if n_err or n_warn:
                self.statusBar().showMessage(f"Errores: {n_err}  Advertencias: {n_warn}")
            else:
                self.statusBar().showMessage("Sin problemas")
        self._actualizar_breadcrumb(editor)

    def _saltar_a_linea(self, editor, linea, col=1):
        if not self._tab_valida(editor):
            return
        if self.editor_tabs.currentWidget() is not editor:
            self.editor_tabs.setCurrentWidget(editor)
        doc = editor.document()
        block = doc.findBlockByNumber(max(linea - 1, 0))
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + max(col - 1, 0))
        editor.setTextCursor(cursor)
        editor.setFocus()
        QTimer.singleShot(700, lambda: self._analizar_en_vivo(editor))

    def _al_hacer_click_error(self, lin):
        if 0 < lin <= len(self._errores_actuales) and self._tab_valida(self._tab_de_ejecucion):
            err = self._errores_actuales[lin - 1]
            self._saltar_a_linea(self._tab_de_ejecucion, err.linea, err.columna)

    def _siguiente_error(self, delta):
        if not self._errores_actuales or not self._tab_valida(self._tab_de_ejecucion):
            self.statusBar().showMessage("No hay errores para navegar")
            return
        n = len(self._errores_actuales)
        self._idx_error = (self._idx_error + delta) % n
        err = self._errores_actuales[self._idx_error]
        self._saltar_a_linea(self._tab_de_ejecucion, err.linea, err.columna)

    def _mostrar_paleta_comandos(self):
        """Paleta de comandos Ctrl+Shift+P (Etapa 9): búsqueda difusa sobre.

        todas las QAction ya registradas vía self._accion(...) -- no se
        mantiene una lista de comandos aparte, se reutiliza el menú real.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Paleta de comandos")
        dlg.resize(520, 360)
        lay = QVBoxLayout(dlg)
        campo = QLineEdit()
        campo.setPlaceholderText("Escriba para filtrar comandos…")
        lista = QListWidget()
        lay.addWidget(campo)
        lay.addWidget(lista, 1)

        acciones_validas = [a for a in self._todas_las_acciones if a.text()]

        def _refrescar():
            patron = campo.text().strip()
            lista.clear()
            for a in acciones_validas:
                if not patron or _coincide_difuso(patron, a.text()):
                    atajo = a.shortcut().toString()
                    etiqueta = a.text() + (f"   [{atajo}]" if atajo else "")
                    item = QListWidgetItem(etiqueta)
                    item.setData(Qt.ItemDataRole.UserRole, a)
                    if not a.isEnabled():
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                    lista.addItem(item)
            if lista.count() > 0:
                lista.setCurrentRow(0)

        def _ejecutar_seleccion():
            item = lista.currentItem()
            if item is None:
                return
            accion = item.data(Qt.ItemDataRole.UserRole)
            dlg.accept()
            if accion.isEnabled():
                accion.trigger()

        campo.textChanged.connect(_refrescar)
        campo.returnPressed.connect(_ejecutar_seleccion)
        lista.itemActivated.connect(lambda _item: _ejecutar_seleccion())
        _refrescar()
        campo.setFocus()
        dlg.exec()

    def _ir_a_linea(self):
        editor = self._tab_actual()
        if editor is None:
            return
        num, ok = QInputDialog.getInt(self, "Ir a línea", "Número de línea:", 1, 1, 10**7)
        if ok:
            self._saltar_a_linea(editor, num)

    def _ir_a_definicion(self, editor=None):
        """Ir a definición (F12/Ctrl+clic, Etapa 9): resuelve el.

        identificador bajo el cursor de `editor` (o la pestaña actual si se
        omite) y salta a la línea de su declaración, reutilizando
        _saltar_a_linea (ya existente, Etapa 1).
        """
        if editor is None:
            editor = self._tab_actual()
        if not self._tab_valida(editor):
            return
        cursor = editor.textCursor()
        texto = cursor.block().text()
        col = cursor.positionInBlock()
        linea = cursor.blockNumber() + 1
        resultado = _resolver_identificador_en(
            editor.ast_en_vivo, editor.tabla_en_vivo, texto, col, linea
        )
        if resultado is None:
            self.statusBar().showMessage("No se encontró la declaración", 3000)
            return
        linea_decl, columna_decl, descripcion = resultado
        self._saltar_a_linea(editor, linea_decl, columna_decl)
        self.statusBar().showMessage(f"Definición: {descripcion}", 3000)

    # ============================================================
    # Tokens / AST
    # ============================================================

    def mostrar_tokens(self):
        """Muestra los tokens."""
        editor = self._tab_actual()
        if editor is None:
            return
        codigo = editor.toPlainText()
        if not codigo.strip():
            return
        nombre = editor.ruta or "<sin_titulo>"
        em = ErrorManager()
        lexer = Lexer(em)
        toks = lexer.tokenizar(codigo, nombre)
        lineas = [f"{t[0]:20s} {repr(t[1]):30s} L{t[2]}:C{t[3]}" for t in toks]
        if em.hay_errores():
            lineas += ["\n--- ERRORES LÉXICOS ---"] + em.obtener_reportes()
        self.texto_salida.setPlainText("\n".join(lineas))
        self.panel_tabs.setCurrentIndex(0)

    def _ast_a_texto(self, nodo, nivel):
        if nodo is None:
            return "  " * nivel + "None\n"
        linea = "  " * nivel + nodo.__class__.__name__
        if getattr(nodo, "nombre", None):
            linea += f"({nodo.nombre})"
        if hasattr(nodo, "tipo_retorno"):
            linea += f" : {nodo.tipo_retorno}"
        elif isinstance(getattr(nodo, "tipo", None), str):
            linea += f" : {nodo.tipo}"
        res = linea + "\n"
        for attr in (
            "elementos",
            "bloque",
            "declaraciones_globales",
            "declaraciones_posteriores",
            "subrutinas",
            "main",
        ):
            v = getattr(nodo, attr, None)
            if isinstance(v, list):
                for e in v:
                    res += self._ast_a_texto(e, nivel + 1)
            elif v is not None:
                res += self._ast_a_texto(v, nivel + 1)
        return res

    def mostrar_ast(self):
        """Muestra el AST."""
        editor = self._tab_actual()
        if editor is None:
            return
        codigo = editor.toPlainText()
        if not codigo.strip():
            return
        nombre = editor.ruta or "<sin_titulo>"
        em = ErrorManager()
        lexer = Lexer(em)
        parser = Parser(lexer, em)
        ast, _ = parser.analizar(codigo, nombre)
        self.texto_salida.setPlainText(
            self._ast_a_texto(ast, 0) if ast else "No se pudo generar el AST\n"
        )
        self.panel_tabs.setCurrentIndex(0)

    def mostrar_ir(self):
        """Muestra el TAC del archivo activo.

        antes y después de optimizar (Etapa 5, ítem 4) -- mismo patrón que
        `revisar()`: análisis estático completo (léxico->sintáctico->
        semántico->tipos) y, si no hay errores, `ir.generar_programa`.
        Alcance: subconjunto estructurado (sin clases/POO ni matrices, ver
        `inveniolang/ir.py`); en ese caso se avisa en vez de fallar.
        """
        editor = self._tab_actual()
        if editor is None:
            return
        codigo = editor.toPlainText().strip()
        if not codigo:
            return
        nombre = editor.ruta or "<sin_titulo>"
        em = ErrorManager()
        lexer = Lexer(em)
        lexer.tokenizar(codigo, nombre)
        ast = None
        if not em.hay_errores():
            parser = Parser(lexer, em)
            ast, em = parser.analizar(codigo, nombre)
            if ast is not None and not em.hay_errores():
                sem = SemanticAnalyzer(em)
                tabla = sem.analizar(ast)
                if not em.hay_errores():
                    tc = TypeChecker(em, tabla)
                    tc.verificar(ast)

        lineas = [f"=== CÓDIGO INTERMEDIO (TAC): {nombre} ==="]
        if ast is None or em.hay_errores():
            lineas.append("Corrija los errores primero:")
            lineas += ["  " + r for r in em.obtener_reportes()]
        else:
            try:
                subrutinas, globales = ir_mod.generar_programa(ast)
            except ir_mod.NoSoportadoIR as e:
                lineas.append(str(e))
                self.texto_salida.setPlainText("\n".join(lineas))
                self.panel_tabs.setCurrentIndex(0)
                return

            def _bloque(titulo, instrucciones):
                lineas.append(f"--- {titulo} ---")
                lineas.append(ir_mod.formatear(instrucciones) if instrucciones else "  (vacío)")

            _bloque("variables globales", globales)
            for nom, (parametros, instrs) in subrutinas.items():
                _bloque(f"{nom}({', '.join(parametros)})", instrs)

            opt_globales, resumen_globales = ir_mod.optimizar(globales)
            opt_subrutinas, resumenes = ir_mod.optimizar_programa(subrutinas)
            lineas.append("")
            lineas.append("=== CÓDIGO INTERMEDIO OPTIMIZADO ===")
            _bloque("variables globales", opt_globales)
            if resumen_globales:
                lineas.append(
                    "  optimizaciones: " + ", ".join(f"{n} x{c}" for n, c in resumen_globales)
                )
            for nom, (parametros, instrs) in opt_subrutinas.items():
                _bloque(f"{nom}({', '.join(parametros)})", instrs)
                resumen = resumenes.get(nom) or []
                if resumen:
                    lineas.append("  optimizaciones: " + ", ".join(f"{n} x{c}" for n, c in resumen))

        self.texto_salida.setPlainText("\n".join(lineas))
        self.panel_tabs.setCurrentIndex(0)

    def mostrar_objetivo(self, k_registros=None):
        """Muestra el código objetivo (ISA de juguete, Etapa 12.11) del.

        archivo activo -- traducción del TAC ya optimizado (incluye TCO,
        Etapa 12.8, si aplica). Mismo patrón que `mostrar_ir`; alcance del
        generador de código objetivo: subconjunto estructurado MENOS
        arreglos y try/catch, ver `inveniolang/ir.py`.

        Con `k_registros` (Etapa 12.12): corre liveness + asignación de
        registros (linear-scan) antes de traducir, y agrega un resumen de
        qué variable/temporal quedó en qué registro o en memoria (spill)
        por subrutina.
        """
        editor = self._tab_actual()
        if editor is None:
            return
        codigo = editor.toPlainText().strip()
        if not codigo:
            return
        nombre = editor.ruta or "<sin_titulo>"
        em = ErrorManager()
        lexer = Lexer(em)
        lexer.tokenizar(codigo, nombre)
        ast = None
        if not em.hay_errores():
            parser = Parser(lexer, em)
            ast, em = parser.analizar(codigo, nombre)
            if ast is not None and not em.hay_errores():
                sem = SemanticAnalyzer(em)
                tabla = sem.analizar(ast)
                if not em.hay_errores():
                    tc = TypeChecker(em, tabla)
                    tc.verificar(ast)

        titulo = (
            "CÓDIGO OBJETIVO CON REGISTROS" if k_registros else "CÓDIGO OBJETIVO (ISA de juguete)"
        )
        lineas = [f"=== {titulo}: {nombre} ==="]
        if k_registros:
            lineas.append(f"  (linear-scan, {k_registros} registros disponibles)")
        if ast is None or em.hay_errores():
            lineas.append("Corrija los errores primero:")
            lineas += ["  " + r for r in em.obtener_reportes()]
        else:
            try:
                subrutinas, _ = ir_mod.generar_programa(ast)
            except ir_mod.NoSoportadoIR as e:
                lineas.append(str(e))
                self.texto_salida.setPlainText("\n".join(lineas))
                self.panel_tabs.setCurrentIndex(0)
                return
            subrutinas_opt, _ = ir_mod.optimizar_programa(subrutinas)
            try:
                objetivo, resumen_registros = ir_mod.generar_objetivo_programa(
                    subrutinas_opt, k_registros
                )
            except ir_mod.NoSoportadoObjetivo as e:
                lineas.append(str(e))
                self.texto_salida.setPlainText("\n".join(lineas))
                self.panel_tabs.setCurrentIndex(0)
                return
            for nom, (parametros, instrs) in objetivo.items():
                lineas.append(f"--- {nom}({', '.join(parametros)}) ---")
                lineas.append(ir_mod.formatear_objetivo(instrs) if instrs else "  (vacío)")
                if nom in resumen_registros:
                    asignacion, spills = resumen_registros[nom]
                    registros = {v: r for v, r in asignacion.items() if r.startswith("R")}
                    if registros:
                        lineas.append(
                            "  asignación: " + ", ".join(f"{v}->{r}" for v, r in registros.items())
                        )
                    if spills:
                        lineas.append(f"  spill (memoria): {', '.join(spills)}")

        self.texto_salida.setPlainText("\n".join(lineas))
        self.panel_tabs.setCurrentIndex(0)

    def mostrar_objetivo_registros(self):
        """Acción de menú para --target-reg (Etapa 12.12): mismo código.

        objetivo que `mostrar_objetivo`, con asignación de registros
        (4 registros por defecto).
        """
        self.mostrar_objetivo(k_registros=4)

    # ============================================================
    # Diagrama de flujo (Etapa 4)
    # ============================================================

    def _listar_subrutinas_diagrama(self, ast):
        """Mapea 'etiqueta visible' -> Bloque para cada subrutina/método.

        diagramable del programa (main, funciones/procedimientos, y
        constructores/métodos de cada clase, POO). Con sobrecarga (Etapa 7:
        métodos: Etapa 10: constructores) puede haber varias entradas con
        el mismo nombre -- se distinguen por firma en la etiqueta para no
        pisarse unas a otras en el dict. Un método abstracto (sin cuerpo)
        no tiene Bloque que diagramar y se omite.
        """

        def _firma(params):
            return "(" + ", ".join(p.tipo for p in params) + ")"

        subrutinas = {}
        if ast.main is not None:
            subrutinas["main"] = ast.main.bloque
        for sub in ast.subrutinas:
            subrutinas[sub.nombre] = sub.bloque
        for c in ast.clases:
            varios_ctor = len(c.constructores) > 1
            for ctor in c.constructores:
                sufijo = _firma(ctor.parametros) if varios_ctor else ""
                subrutinas[f"{c.nombre}.{ctor.nombre}{sufijo} (constructor)"] = ctor.bloque
            por_nombre = {}
            for met in c.metodos:
                por_nombre.setdefault(met.nombre, []).append(met)
            for nombre_met, sobrecargas in por_nombre.items():
                varios = len(sobrecargas) > 1
                for met in sobrecargas:
                    if met.bloque is None:
                        continue  # método abstracto (Etapa 7): sin cuerpo
                    sufijo = _firma(met.parametros) if varios else ""
                    subrutinas[f"{c.nombre}.{nombre_met}{sufijo}"] = met.bloque
        return subrutinas

    def generar_diagrama(self):
        """Compila el archivo activo (lexer→parser→semántico, como.

        `revisar()`) y puebla el selector de subrutinas del panel de
        diagrama. No hace falta el verificador de tipos: el diagrama es
        estructural, no depende de la compatibilidad de tipos.
        """
        editor = self._tab_actual()
        if editor is None:
            return
        codigo = editor.toPlainText().strip()
        if not codigo:
            return
        nombre = editor.ruta or "<sin_titulo>"

        em = ErrorManager()
        lexer = Lexer(em)
        lexer.tokenizar(codigo, nombre)
        ast = None
        if not em.hay_errores():
            parser = Parser(lexer, em)
            ast, em = parser.analizar(codigo, nombre)
            if ast is not None and not em.hay_errores():
                SemanticAnalyzer(em).analizar(ast)

        self.dock_diagrama.show()
        self.dock_diagrama.raise_()

        if ast is None or em.hay_errores():
            self.escena_diagrama.clear()
            self.escena_diagrama.addSimpleText(
                "Corrija los errores de compilación primero (pestaña Errores)."
            )
            return

        self._subrutinas_diagrama = self._listar_subrutinas_diagrama(ast)
        if not self._subrutinas_diagrama:
            self.escena_diagrama.clear()
            self.escena_diagrama.addSimpleText("No hay ninguna subrutina para diagramar.")
            return

        etiqueta_previa = self.combo_diagrama.currentText()
        self.combo_diagrama.blockSignals(True)
        self.combo_diagrama.clear()
        self.combo_diagrama.addItems(list(self._subrutinas_diagrama.keys()))
        idx = self.combo_diagrama.findText(etiqueta_previa)
        self.combo_diagrama.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo_diagrama.blockSignals(False)

        self._dibujar_subrutina_diagrama()

    def _al_cambiar_subrutina_diagrama(self, _idx):
        self._dibujar_subrutina_diagrama()

    def abrir_constructor_diagrama(self):
        """Abre y enfoca el panel del constructor de diagramas (Etapa 13).

        -- no necesita ningún archivo abierto/compilado, a diferencia de
        `generar_diagrama` (que sí revela el de un archivo existente):
        el estudiante empieza a construir desde cero.
        """
        self.dock_constructor.show()
        self.dock_constructor.raise_()

    def _dibujar_subrutina_diagrama(self):
        bloque = self._subrutinas_diagrama.get(self.combo_diagrama.currentText())
        if bloque is None:
            return
        # La escena se limpia dentro de _pintar_diagrama; cualquier item de
        # resaltado que hubiera queda invalido (C++ ya lo destruyo), asi que
        # se olvida la referencia en vez de intentar removerlo.
        self._resaltado_diagrama = None
        self._diagrama_actual = fc.construir_diagrama(bloque)
        self._pintar_diagrama(self._diagrama_actual, self.escena_diagrama, self.vista_diagrama)

    # ---- Enlace con el depurador (Etapa 5) ----

    def _resaltar_en_diagrama(self, snap):
        """Si el panel de diagrama está visible, lo sincroniza con la.

        subrutina que el depurador está ejecutando ahora mismo y resalta la
        línea pausada -- estilo PSeInt.
        """
        if not self.dock_diagrama.isVisible():
            return
        if not self._subrutinas_diagrama:
            self.generar_diagrama()
            if not self._subrutinas_diagrama:
                return

        pila = snap.get("pila") or []
        etiqueta = pila[-1] if pila else "main"
        if etiqueta not in self._subrutinas_diagrama:
            alterna = f"{etiqueta} (constructor)"
            etiqueta = alterna if alterna in self._subrutinas_diagrama else None
        if etiqueta is None:
            self._quitar_resaltado_diagrama()
            return

        if self.combo_diagrama.currentText() != etiqueta:
            idx = self.combo_diagrama.findText(etiqueta)
            if idx >= 0:
                self.combo_diagrama.blockSignals(True)
                self.combo_diagrama.setCurrentIndex(idx)
                self.combo_diagrama.blockSignals(False)
                self._dibujar_subrutina_diagrama()

        self._resaltar_caja_linea(snap.get("linea"))

    def _resaltar_caja_linea(self, linea):
        self._quitar_resaltado_diagrama()
        if linea is None or self._diagrama_actual is None:
            return
        for caja in self._diagrama_actual.cajas:
            if caja.linea == linea:
                pen = QPen(QColor("#ffcc00"))
                pen.setWidth(3)
                item = self.escena_diagrama.addRect(
                    caja.x - 4, caja.y - 4, caja.w + 8, caja.h + 8, pen
                )
                item.setZValue(10)
                self._resaltado_diagrama = item
                self.vista_diagrama.centerOn(item)
                break

    def _quitar_resaltado_diagrama(self):
        if self._resaltado_diagrama is not None:
            self.escena_diagrama.removeItem(self._resaltado_diagrama)
            self._resaltado_diagrama = None

    def _pintar_diagrama(self, diagrama, escena, vista):
        """Pinta cualquier `Diagrama` (flowchart.py) en la `escena`/`vista`.

        dadas -- generalizado en la Etapa 13 para que tanto el dock de
        solo lectura (diagrama generado desde código) como el panel del
        constructor (diagrama armado por el estudiante) reusen exactamente
        el mismo dibujo, sin duplicar esta función.
        """
        escena.clear()
        escena.setSceneRect(0, 0, diagrama.ancho, diagrama.alto)

        fuente = QFont("Consolas", 9)
        color_texto = QColor(COLORES["dfd_texto"])
        pen_borde = QPen(QColor(COLORES["dfd_borde"]))
        pen_borde.setWidth(2)
        pen_flecha = QPen(QColor(COLORES["dfd_flecha"]))
        pen_flecha.setWidth(2)
        rellenos = {
            fc.INICIO: COLORES["dfd_inicio_fin"],
            fc.FIN: COLORES["dfd_inicio_fin"],
            fc.PROCESO: COLORES["dfd_proceso"],
            fc.DECISION: COLORES["dfd_decision"],
            fc.ENTRADA_SALIDA: COLORES["dfd_es"],
        }

        for caja in diagrama.cajas:
            if caja.forma == fc.CONECTOR:
                continue
            relleno = QColor(rellenos.get(caja.forma, COLORES["dfd_proceso"]))
            if caja.forma in (fc.INICIO, fc.FIN):
                item = escena.addEllipse(caja.x, caja.y, caja.w, caja.h, pen_borde, relleno)
            elif caja.forma == fc.DECISION:
                poligono = QPolygonF(
                    [
                        QPointF(caja.x + caja.w / 2, caja.y),
                        QPointF(caja.x + caja.w, caja.y + caja.h / 2),
                        QPointF(caja.x + caja.w / 2, caja.y + caja.h),
                        QPointF(caja.x, caja.y + caja.h / 2),
                    ]
                )
                item = escena.addPolygon(poligono, pen_borde, relleno)
            elif caja.forma == fc.ENTRADA_SALIDA:
                d = 16
                poligono = QPolygonF(
                    [
                        QPointF(caja.x + d, caja.y),
                        QPointF(caja.x + caja.w, caja.y),
                        QPointF(caja.x + caja.w - d, caja.y + caja.h),
                        QPointF(caja.x, caja.y + caja.h),
                    ]
                )
                item = escena.addPolygon(poligono, pen_borde, relleno)
            else:
                item = escena.addRect(caja.x, caja.y, caja.w, caja.h, pen_borde, relleno)
            if caja.linea:
                item.setToolTip(f"Línea {caja.linea}")

            texto = QGraphicsSimpleTextItem(caja.texto)
            texto.setFont(fuente)
            texto.setBrush(color_texto)
            tb = texto.boundingRect()
            texto.setPos(caja.x + (caja.w - tb.width()) / 2, caja.y + (caja.h - tb.height()) / 2)
            escena.addItem(texto)

        for flecha in diagrama.flechas:
            puntos = flecha.puntos
            for i in range(len(puntos) - 1):
                x1, y1 = puntos[i]
                x2, y2 = puntos[i + 1]
                escena.addLine(x1, y1, x2, y2, pen_flecha)
            self._agregar_punta_flecha(puntos[-2], puntos[-1], pen_flecha, escena)
            if flecha.etiqueta:
                etq = QGraphicsSimpleTextItem(flecha.etiqueta)
                etq.setFont(fuente)
                etq.setBrush(QColor(COLORES["dfd_borde"]))
                ex, ey = puntos[0]
                etq.setPos(ex + 6, ey + 4)
                escena.addItem(etq)

        vista.setSceneRect(escena.itemsBoundingRect())

    def _agregar_punta_flecha(self, origen, destino, pen, escena):
        x1, y1 = origen
        x2, y2 = destino
        angulo = math.atan2(y2 - y1, x2 - x1)
        tam = 8
        p1 = QPointF(x2, y2)
        p2 = QPointF(
            x2 - tam * math.cos(angulo - math.pi / 6), y2 - tam * math.sin(angulo - math.pi / 6)
        )
        p3 = QPointF(
            x2 - tam * math.cos(angulo + math.pi / 6), y2 - tam * math.sin(angulo + math.pi / 6)
        )
        escena.addPolygon(QPolygonF([p1, p2, p3]), pen, QColor(COLORES["dfd_flecha"]))

    # ============================================================
    # Constructor de diagramas de flujo (Etapa 13)
    # ============================================================
    #
    # El estado del diagrama que arma el estudiante es `self.
    # _bloque_constructor`, un `Bloque` REAL de ast_nodes.py -- las mismas
    # clases que produce el parser real (ver inveniolang/
    # flowchart_builder.py). Cada QTreeWidgetItem guarda en
    # `UserRole` la tupla `(bloque_contenedor, nodo_o_None)`:
    #   - nodo no es None: el ítem representa una instrucción/decisión/
    #     ciclo real, viviendo dentro de `bloque_contenedor.elementos`.
    #   - nodo es None: el ítem es un encabezado de contenedor ("Rama Sí"/
    #     "Rama No"/"Cuerpo"), usado como punto de inserción explícito
    #     para "insertar como primer elemento de esta rama/cuerpo".

    def _etiqueta_nodo_constructor(self, nodo):
        if isinstance(nodo, IfStmt):
            return f"Decisión: si ({fc._texto_expr(nodo.condicion)})"
        if isinstance(nodo, WhileStmt):
            return f"Mientras ({fc._texto_expr(nodo.condicion)})"
        if isinstance(nodo, DoWhileStmt):
            return f"Hacer ... mientras ({fc._texto_expr(nodo.condicion)})"
        if isinstance(nodo, ForStmt):
            init_txt = fc._texto_for_init_act(nodo.init_stmt)
            cond_txt = fc._texto_expr(nodo.cond_expr)
            act_txt = fc._texto_for_init_act(nodo.act_stmt)
            return f"Para ({init_txt}; {cond_txt}; {act_txt})"
        texto = fc._texto_instruccion(nodo)
        return texto if texto is not None else "?"

    def _llenar_arbol_constructor(self, item_padre_qt, bloque):
        for nodo in bloque.elementos:
            item = QTreeWidgetItem([self._etiqueta_nodo_constructor(nodo)])
            item.setData(0, Qt.ItemDataRole.UserRole, (bloque, nodo))
            item_padre_qt.addChild(item)
            if isinstance(nodo, IfStmt):
                item_si = QTreeWidgetItem(["   Rama Sí"])
                item_si.setData(0, Qt.ItemDataRole.UserRole, (nodo.bloque_then, None))
                item.addChild(item_si)
                self._llenar_arbol_constructor(item_si, nodo.bloque_then)
                if nodo.bloque_else is not None:
                    item_no = QTreeWidgetItem(["   Rama No"])
                    item_no.setData(0, Qt.ItemDataRole.UserRole, (nodo.bloque_else, None))
                    item.addChild(item_no)
                    self._llenar_arbol_constructor(item_no, nodo.bloque_else)
            elif isinstance(nodo, (WhileStmt, DoWhileStmt, ForStmt)):
                item_cuerpo = QTreeWidgetItem(["   Cuerpo"])
                item_cuerpo.setData(0, Qt.ItemDataRole.UserRole, (nodo.bloque, None))
                item.addChild(item_cuerpo)
                self._llenar_arbol_constructor(item_cuerpo, nodo.bloque)

    def _reconstruir_arbol_constructor(self):
        self.arbol_constructor.clear()
        self._llenar_arbol_constructor(
            self.arbol_constructor.invisibleRootItem(), self._bloque_constructor
        )
        self.arbol_constructor.expandAll()
        self._actualizar_vista_constructor()

    def _actualizar_vista_constructor(self):
        diagrama = fc.construir_diagrama(self._bloque_constructor)
        self._pintar_diagrama(diagrama, self.escena_constructor, self.vista_constructor)
        _, errores_por_nodo = fb.validar_diagrama(self._bloque_constructor)
        self._marcar_errores_constructor(
            self.arbol_constructor.invisibleRootItem(), errores_por_nodo
        )

    def _marcar_errores_constructor(self, item_qt, errores_por_nodo):
        for i in range(item_qt.childCount()):
            hijo = item_qt.child(i)
            _, nodo = hijo.data(0, Qt.ItemDataRole.UserRole)
            if nodo is not None and id(nodo) in errores_por_nodo:
                hijo.setForeground(0, QColor("#ff5555"))
                hijo.setToolTip(
                    0, "\n".join(e.formato_oficial() for e in errores_por_nodo[id(nodo)])
                )
            else:
                hijo.setForeground(0, QColor(COLORES["texto"]))
                hijo.setToolTip(0, "")
            self._marcar_errores_constructor(hijo, errores_por_nodo)

    def _punto_insercion_constructor(self):
        """(bloque_destino, índice) donde debe caer el próximo bloque.

        insertado -- después del ítem seleccionado (en su mismo nivel de
        anidación), al inicio del contenedor si el ítem seleccionado es
        un encabezado de rama/cuerpo, o al final de la secuencia raíz si
        no hay nada seleccionado.
        """
        item = self.arbol_constructor.currentItem()
        if item is None:
            return self._bloque_constructor, len(self._bloque_constructor.elementos)
        bloque, nodo = item.data(0, Qt.ItemDataRole.UserRole)
        if nodo is None:
            return bloque, 0
        return bloque, bloque.elementos.index(nodo) + 1

    def _dialogo_para(self, init="entero i = 0", cond="i < 10", paso="i++"):
        d = QDialog(self)
        d.setWindowTitle("Para")
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel("Inicialización:"))
        e_init = QLineEdit(init)
        lay.addWidget(e_init)
        lay.addWidget(QLabel("Condición:"))
        e_cond = QLineEdit(cond)
        lay.addWidget(e_cond)
        lay.addWidget(QLabel("Paso:"))
        e_paso = QLineEdit(paso)
        lay.addWidget(e_paso)
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(d.accept)
        botones.rejected.connect(d.reject)
        lay.addWidget(botones)
        if d.exec() != QDialog.DialogCode.Accepted:
            return None
        return e_init.text(), e_cond.text(), e_paso.text()

    def _mostrar_errores_fragmento(self, errores):
        QMessageBox.warning(
            self, "Error de sintaxis", "\n".join(e.formato_oficial() for e in errores)
        )

    def _insertar_forma_constructor(self, forma):
        bloque_destino, indice = self._punto_insercion_constructor()
        nodo, errores = None, []
        if forma == fb.PROCESO:
            texto, ok = QInputDialog.getText(self, "Proceso", "Instrucción InvenioLang:")
            if not ok or not texto.strip():
                return
            nodo, errores = fb.crear_proceso(texto)
        elif forma == fb.ENTRADA:
            texto, ok = QInputDialog.getText(self, "Entrada", "Variable a leer (leer):")
            if not ok or not texto.strip():
                return
            nodo, errores = fb.crear_entrada(texto)
        elif forma == fb.SALIDA:
            texto, ok = QInputDialog.getText(self, "Salida", "Expresión a imprimir:")
            if not ok or not texto.strip():
                return
            nodo, errores = fb.crear_salida(texto)
        elif forma == fb.DECISION:
            texto, ok = QInputDialog.getText(self, "Decisión (si)", "Condición:")
            if not ok or not texto.strip():
                return
            nodo, errores = fb.crear_decision(texto)
        elif forma == fb.MIENTRAS:
            texto, ok = QInputDialog.getText(self, "Mientras", "Condición:")
            if not ok or not texto.strip():
                return
            nodo, errores = fb.crear_mientras(texto)
        elif forma == fb.HACER_MIENTRAS:
            texto, ok = QInputDialog.getText(
                self, "Hacer-mientras", "Condición (se evalúa DESPUÉS del cuerpo):"
            )
            if not ok or not texto.strip():
                return
            nodo, errores = fb.crear_hacer_mientras(texto)
        elif forma == fb.PARA:
            datos = self._dialogo_para()
            if datos is None:
                return
            nodo, errores = fb.crear_para(*datos)
        else:
            return

        if errores:
            self._mostrar_errores_fragmento(errores)
            return
        fb.insertar(bloque_destino, indice, nodo)
        self._reconstruir_arbol_constructor()

    def _editar_item_constructor(self, item, _columna):
        bloque, nodo = item.data(0, Qt.ItemDataRole.UserRole)
        if nodo is None:
            return  # encabezado de rama/cuerpo: no se edita directamente

        if isinstance(nodo, IfStmt):
            texto, ok = QInputDialog.getText(
                self, "Editar decisión", "Condición:", text=fc._texto_expr(nodo.condicion)
            )
            if not ok:
                return
            nuevo, errores = fb.crear_decision(texto)
            if errores:
                self._mostrar_errores_fragmento(errores)
                return
            nodo.condicion = nuevo.condicion
        elif isinstance(nodo, WhileStmt):
            texto, ok = QInputDialog.getText(
                self, "Editar mientras", "Condición:", text=fc._texto_expr(nodo.condicion)
            )
            if not ok:
                return
            nuevo, errores = fb.crear_mientras(texto)
            if errores:
                self._mostrar_errores_fragmento(errores)
                return
            nodo.condicion = nuevo.condicion
        elif isinstance(nodo, DoWhileStmt):
            texto, ok = QInputDialog.getText(
                self, "Editar hacer-mientras", "Condición:", text=fc._texto_expr(nodo.condicion)
            )
            if not ok:
                return
            nuevo, errores = fb.crear_hacer_mientras(texto)
            if errores:
                self._mostrar_errores_fragmento(errores)
                return
            nodo.condicion = nuevo.condicion
        elif isinstance(nodo, ForStmt):
            datos = self._dialogo_para(
                fc._texto_for_init_act(nodo.init_stmt),
                fc._texto_expr(nodo.cond_expr),
                fc._texto_for_init_act(nodo.act_stmt),
            )
            if datos is None:
                return
            nuevo, errores = fb.crear_para(*datos)
            if errores:
                self._mostrar_errores_fragmento(errores)
                return
            nodo.init_stmt, nodo.cond_expr, nodo.act_stmt = (
                nuevo.init_stmt,
                nuevo.cond_expr,
                nuevo.act_stmt,
            )
        else:
            # Proceso/Entrada/Salida: sin hijos que preservar, reemplazo
            # completo del nodo en su misma posición.
            if isinstance(nodo, ReadStmt):
                texto, ok = QInputDialog.getText(
                    self, "Editar entrada", "Variable a leer:", text=nodo.nombre
                )
                constructor = fb.crear_entrada
            elif isinstance(nodo, PrintStmt):
                texto, ok = QInputDialog.getText(
                    self, "Editar salida", "Expresión a imprimir:", text=fc._texto_expr(nodo.expr)
                )
                constructor = fb.crear_salida
            else:
                texto, ok = QInputDialog.getText(
                    self, "Editar proceso", "Instrucción:", text=fc._texto_instruccion(nodo) or ""
                )
                constructor = fb.crear_proceso
            if not ok:
                return
            nuevo, errores = constructor(texto)
            if errores:
                self._mostrar_errores_fragmento(errores)
                return
            fb.reemplazar(bloque, nodo, nuevo)
        self._reconstruir_arbol_constructor()

    def _menu_contextual_constructor(self, punto):
        item = self.arbol_constructor.itemAt(punto)
        if item is None:
            return
        bloque, nodo = item.data(0, Qt.ItemDataRole.UserRole)
        if nodo is None:
            return
        menu = QMenu(self)
        menu.addAction("Eliminar", lambda: self._eliminar_item_constructor(bloque, nodo))
        menu.addAction("Mover arriba", lambda: self._mover_item_constructor(bloque, nodo, -1))
        menu.addAction("Mover abajo", lambda: self._mover_item_constructor(bloque, nodo, 1))
        if isinstance(nodo, IfStmt):
            if nodo.bloque_else is None:
                menu.addAction('Agregar rama "sino"', lambda: self._agregar_else_constructor(nodo))
            else:
                menu.addAction('Quitar rama "sino"', lambda: self._quitar_else_constructor(nodo))
        menu.exec(self.arbol_constructor.viewport().mapToGlobal(punto))

    def _eliminar_item_constructor(self, bloque, nodo):
        fb.eliminar(bloque, nodo)
        self._reconstruir_arbol_constructor()

    def _mover_item_constructor(self, bloque, nodo, delta):
        fb.mover(bloque, nodo, delta)
        self._reconstruir_arbol_constructor()

    def _agregar_else_constructor(self, nodo):
        fb.agregar_rama_else(nodo)
        self._reconstruir_arbol_constructor()

    def _quitar_else_constructor(self, nodo):
        if (
            nodo.bloque_else.elementos
            and QMessageBox.question(
                self,
                'Quitar rama "sino"',
                'La rama "sino" tiene contenido -- ¿quitarla de todas formas?',
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        fb.quitar_rama_else(nodo)
        self._reconstruir_arbol_constructor()

    def nuevo_diagrama_constructor(self):
        """Abre el constructor de diagramas."""
        if (
            self._bloque_constructor.elementos
            and QMessageBox.question(
                self, "Nuevo diagrama", "Se perderá el diagrama actual. ¿Continuar?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._bloque_constructor = Bloque([])
        self._reconstruir_arbol_constructor()

    def generar_codigo_constructor(self):
        """Botón "Generar código InvenioLang": valida TODO el diagrama.

        junto (ver flowchart_builder.py::validar_diagrama) y, si hay
        errores pendientes, confirma antes de continuar -- no bloquea,
        el estudiante puede seguir corrigiendo en el editor de texto
        normal. Reusa `_nueva_pestana` exactamente como ya hace la carga
        de ejemplos (Ayuda → Ejemplos), sin caso especial.
        """
        texto, errores_por_nodo = fb.validar_diagrama(self._bloque_constructor)
        if errores_por_nodo:
            total = sum(len(v) for v in errores_por_nodo.values())
            if (
                QMessageBox.question(
                    self,
                    "Diagrama con errores",
                    f"El diagrama tiene {total} error(es) pendientes (marcados en rojo "
                    "en el árbol). ¿Generar el código de todas formas?",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        self._nueva_pestana(codigo=texto)

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
        for titulo, contenido in [
            ("Guía rápida", _DOC_GUIA),
            ("Referencia", _DOC_REFERENCIA),
            ("Funciones integradas", _DOC_FUNCIONES),
            ("Catálogo de errores", _DOC_ERRORES),
            ("Atajos", _DOC_ATAJOS),
        ]:
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
        ruta = os.path.join(base, "..", "pruebas", f"{nombre}.inv")
        if not os.path.exists(ruta):
            QMessageBox.critical(self, "Ejemplo", f"No se encontró el ejemplo: {nombre}")
            return
        self._abrir_ruta(os.path.abspath(ruta))

    def mostrar_acerca(self):
        """Muestra el diálogo acerca de."""
        QMessageBox.about(
            self,
            "Acerca de InvenioLang 2.0",
            "InvenioLang 2.0 - Compilador Educativo\n"
            "Curso: TIIT2002.2 Lenguajes Formales II\n"
            "Universidad Invenio\n"
            "Profesor: Donny Núñez del Rosario\n\n"
            "Fase 1 (estructurado): variables, control de flujo, funciones,\n"
            "arreglos/matrices, switch/do-while/ternario/try-catch,\n"
            "librería estándar de cadenas y matemática.\n"
            "Fase 2 (POO completo): clases, herencia, polimorfismo,\n"
            "abstractas, miembros estáticos, sobrecarga y genéricos.\n\n"
            "Implementado con Python, PLY y PySide6 (Qt for Python)",
        )

    # ============================================================
    # Persistencia de sesión
    # ============================================================

    def _restaurar_sesion(self):
        # Preferencias (Etapa 5): antes de abrir pestañas, para que las
        # restauradas ya nazcan con el tema/tamaño de fuente correctos.
        self._aplicar_tema(self.settings.value("tema", "oscuro") == "claro")
        self._aplicar_tamano_fuente(int(self.settings.value("fuente_tamano", 11)))

        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        estado = self.settings.value("windowState")
        if estado is not None:
            self.restoreState(estado)
        recientes = self.settings.value("recientes", [])
        if isinstance(recientes, str):
            recientes = [recientes] if recientes else []
        self._recientes = [r for r in (recientes or []) if os.path.isfile(r)]
        self._actualizar_menu_recientes()
        rutas = self.settings.value("pestanas_abiertas", [])
        if isinstance(rutas, str):
            rutas = [rutas] if rutas else []
        for ruta in rutas or []:
            if os.path.isfile(ruta):
                self._abrir_ruta(ruta)

    def _guardar_sesion(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        rutas = [
            self.editor_tabs.widget(i).ruta
            for i in range(self.editor_tabs.count())
            if self.editor_tabs.widget(i).ruta
        ]
        self.settings.setValue("pestanas_abiertas", rutas)
        self.settings.setValue("carpeta_trabajo", getattr(self, "_carpeta_trabajo", os.getcwd()))
        self.settings.setValue("recientes", self._recientes)

    def closeEvent(self, event):
        """Atiende el cierre de la ventana."""
        sin_guardar = [
            self.editor_tabs.widget(i)
            for i in range(self.editor_tabs.count())
            if self.editor_tabs.widget(i).modificado
        ]
        if sin_guardar:
            resp = QMessageBox.question(
                self,
                "Confirmar",
                f"Hay {len(sin_guardar)} pestaña(s) con cambios sin guardar. "
                "¿Cerrar de todas formas?",
            )
            if resp != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._guardar_sesion()
        event.accept()


def main():
    """Punto de entrada del programa."""
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    import sys

    sys.exit(main())
