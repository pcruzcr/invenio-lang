"""Recursos compartidos de la capa GUI (temas de color).

INV-1005: este paquete reexportaba ``MainWindow``/``CodeEditor`` desde
``gui_qt`` y ``InvenioLangGUI`` desde ``gui_tk`` "por compatibilidad", pero
ningún consumidor usaba esa ruta y, como ``gui_qt`` importa ``gui.theme``,
la reexportación creaba un import circular que dejaba los nombres en ``None``
según el orden de importación. Las ventanas se importan de ``gui_qt``/``gui_tk``.
"""

from .theme import COLORES, TEMA_ALTO_CONTRASTE, TEMA_CLARO, TEMA_OSCURO

__all__ = ["COLORES", "TEMA_ALTO_CONTRASTE", "TEMA_CLARO", "TEMA_OSCURO"]
