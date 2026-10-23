"""Accesibilidad de la IDE (WCAG 2.1 AA): tema de alto contraste y verificación.

INV-1027: aquí vivían también ``describir_widget`` y constantes de tamaños y
fuentes "dislexia-friendly" que ningún widget usaba (la IDE fija sus nombres
accesibles y su escalado de fuente por su cuenta). Se eliminaron: lo que queda
es la paleta que consume ``gui/theme.py`` y el verificador de contraste que
documenta ACCESSIBILITY.md.
"""

from __future__ import annotations

__all__ = ["TEMA_ALTO_CONTRASTE", "contraste_ratio", "validar_tema_accesible"]

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


def _luminancia(hexcol: str) -> float:
    """Luminancia relativa WCAG de un color ``#rrggbb``."""

    def lineal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hexcol[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * lineal(r) + 0.7152 * lineal(g) + 0.0722 * lineal(b)


def contraste_ratio(c1: str, c2: str) -> float:
    """Calcula ratio de contraste WCAG entre dos colores hex (#rrggbb)."""
    l1, l2 = _luminancia(c1), _luminancia(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def validar_tema_accesible(tema: dict[str, str]) -> list[str]:
    """Retorna lista de advertencias si algún par texto/fondo no cumple WCAG AA (4.5:1)."""
    advertencias: list[str] = []
    pares = [("texto", "fondo"), ("gutter_linea", "gutter"), ("dfd_texto", "dfd_proceso")]
    for fg, bg in pares:
        if fg in tema and bg in tema:
            ratio = contraste_ratio(tema[fg], tema[bg])
            if ratio < 4.5:
                advertencias.append(f"{fg}/{bg}: {ratio:.1f}:1 < 4.5:1 (WCAG AA)")
    return advertencias
