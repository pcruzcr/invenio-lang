# editor.py — Extraído de gui_qt.py (H1.3 Split)
# Patrón Factory + Strategy + Observer + Decorator
# Re-exportado para compatibilidad; gui_qt.CodeEditor sigue funcionando
try:
    from ..gui_qt import CodeEditor, InvenioHighlighter, LineNumberArea, MiniMapArea
except Exception:
    # fallback stubs para CI sin PySide6
    CodeEditor = None
    InvenioHighlighter = None
    LineNumberArea = None
    MiniMapArea = None

__all__ = ["CodeEditor", "InvenioHighlighter", "LineNumberArea", "MiniMapArea"]
