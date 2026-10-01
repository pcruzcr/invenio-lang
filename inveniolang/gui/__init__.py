# gui package — Split de gui_qt.py (H1.3) + compatibilidad Tk
# Facade + Factory + Strategy. Mantiene compatibilidad: `from inveniolang.gui_qt import MainWindow`
# sigue funcionando
# pero ahora MainWindow vive en gui/main_window.py y gui_qt.py es fachada.
from .editor import CodeEditor, InvenioHighlighter, LineNumberArea, MiniMapArea
from .theme import COLORES, TEMA_ALTO_CONTRASTE, TEMA_CLARO, TEMA_OSCURO

try:
    from .main_window import MainWindow
except Exception:
    MainWindow = None

# Compatibilidad: re-exporta Tk GUI desde gui_tk.py (antes gui.py)
try:
    from ..gui_tk import InvenioLangGUI, main
except Exception:
    InvenioLangGUI = None
    main = None

__all__ = [
    "MainWindow",
    "CodeEditor",
    "InvenioHighlighter",
    "LineNumberArea",
    "MiniMapArea",
    "TEMA_OSCURO",
    "TEMA_CLARO",
    "TEMA_ALTO_CONTRASTE",
    "COLORES",
    "InvenioLangGUI",
    "main",
]
