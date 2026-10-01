# theme.py — Strategy para temas (extraído de gui_qt.py:52)
# Patrón Strategy + Singleton
from __future__ import annotations

try:
    from ..accessibility import TEMA_ALTO_CONTRASTE as ACC_TEMA
except Exception:
    ACC_TEMA = None

TEMA_OSCURO: dict[str, str] = {
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
TEMA_CLARO: dict[str, str] = {
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
TEMA_ALTO_CONTRASTE: dict[str, str] = (
    ACC_TEMA
    if ACC_TEMA
    else {
        "fondo": "#000000",
        "panel": "#000000",
        "gutter": "#000000",
        "gutter_borde": "#ffff00",
        "gutter_linea": "#ffffff",
        "texto": "#ffffff",
        "keyword": "#ffff00",
        "type": "#00ffff",
        "string": "#ff9e9e",
        "comment": "#00ff00",
        "number": "#ff8000",
        "builtin": "#ff80ff",
        "operator": "#ffffff",
        "error_sub": "#ff0000",
        "error_fondo": "#400000",
        "warn_sub": "#ffff00",
        "warn_fondo": "#404000",
        "linea_activa": "#1a1a1a",
        "flash": "#333300",
        "breakpoint": "#ff0000",
        "dfd_inicio_fin": "#003366",
        "dfd_proceso": "#000000",
        "dfd_decision": "#333300",
        "dfd_es": "#003300",
        "dfd_borde": "#ffff00",
        "dfd_flecha": "#ffffff",
        "dfd_texto": "#ffffff",
    }
)
COLORES: dict[str, str] = dict(TEMA_OSCURO)


class ThemeStrategy:
    """Estrategia theme."""

    def apply(self, nombre: str):
        """Aplica el tema."""
        mapa = {"oscuro": TEMA_OSCURO, "claro": TEMA_CLARO, "alto": TEMA_ALTO_CONTRASTE}
        COLORES.clear()
        COLORES.update(mapa.get(nombre, TEMA_OSCURO))
        return COLORES
