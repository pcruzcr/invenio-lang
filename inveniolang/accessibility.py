# accessibility.py — helpers de accesibilidad para la IDE (WCAG 2.1 AA)
#
# Centraliza criterios profesionales que antes estaban dispersos o ausentes:
#   - Nombres y descripciones accesibles para lectores de pantalla
#   - Paleta de alto contraste (para daltonismo / baja visión)
#   - Escalado de fuente (dislexia / baja visión)
#   - Foco visible y navegación por teclado
#
# Sin dependencia nueva: solo Qt accesibility API (QAccessible).


# Paleta de alto contraste (WCAG AAA, contraste ~7:1) — alternativa al
# TEMA_CLARO/OSCURO existente. No reemplaza nada, se activa desde el menú
# Ver → Tema.
TEMA_ALTO_CONTRASTE = {
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

# Tamaños de fuente accesibles (pt) — se persiste en QSettings
TAMANOS_FUENTE_ACCESIBLES = [9, 10, 11, 12, 14, 16, 18, 20, 24]
TAMANO_FUENTE_DEFECTO = 11
TAMANO_FUENTE_MIN = 9
TAMANO_FUENTE_MAX = 24

# Fuente dislexia-friendly (si está instalada, se usa; si no, cae a monospace)
FUENTE_DISLEXIA_CANDIDATAS = [
    "OpenDyslexicMono",
    "Atkinson Hyperlegible Mono",
    "Consolas",
    "Courier New",
]


def describir_widget(widget, nombre: str, descripcion: str = "", atajo: str = ""):
    """Asigna nombre y descripción accesibles a un widget Qt.

    Llamar inmediatamente después de crear cada widget interactivo. Hace que
    lectores de pantalla (NVDA/JAWS/Orca) anuncien el propósito correctamente.
    """
    try:
        widget.setAccessibleName(nombre)
        if descripcion:
            widget.setAccessibleDescription(descripcion + (f" Atajo: {atajo}" if atajo else ""))
        if atajo:
            widget.setToolTip(
                f"{nombre} ({atajo}) — {descripcion}" if descripcion else f"{nombre} ({atajo})"
            )
        elif descripcion:
            widget.setToolTip(descripcion)
    except Exception:  # noqa: S110 - accesibilidad best-effort sin Qt completo
        pass


def contraste_ratio(c1: str, c2: str) -> float:
    """Calcula ratio de contraste WCAG entre dos colores hex (#rrggbb)."""

    def lum(hexcol):
        """Calcula la luminancia relativa."""
        r, g, b = int(hexcol[1:3], 16) / 255, int(hexcol[3:5], 16) / 255, int(hexcol[5:7], 16) / 255

        def lin(c):
            """Linealiza un canal sRGB."""
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    l1, l2 = lum(c1), lum(c2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def validar_tema_accesible(tema: dict) -> list:
    """Retorna lista de advertencias si algún par texto/fondo no cumple WCAG AA (4.5:1)."""
    advertencias = []
    pares = [("texto", "fondo"), ("gutter_linea", "gutter"), ("dfd_texto", "dfd_proceso")]
    for fg, bg in pares:
        if fg in tema and bg in tema:
            ratio = contraste_ratio(tema[fg], tema[bg])
            if ratio < 4.5:
                advertencias.append(f"{fg}/{bg}: {ratio:.1f}:1 < 4.5:1 (WCAG AA)")
    return advertencias
