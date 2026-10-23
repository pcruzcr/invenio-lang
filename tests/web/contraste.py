"""Contraste WCAG de los colores del estudio web (INV-4220).

Lee las variables CSS de ``web/estudio/estilos.css`` por tema y calcula la
razón de contraste de WCAG 2.x. Lo usa ``test_estudio_estatico.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "web" / "estudio" / "estilos.css"

# Texto (AAA, >= 7:1) sobre los fondos donde aparece.
FONDOS_GENERALES = ("fondo", "superficie", "superficie-2", "elevada", "editor-fondo")
TEXTOS_GENERALES = ("texto", "texto-suave", "acento", "error")
PARES_TEXTO = [
    *[(t, f) for t in TEXTOS_GENERALES for f in FONDOS_GENERALES],
    ("texto", "acento-suave"),
    ("texto", "linea-actual"),
    ("texto", "marca-error"),
    ("acento-texto", "acento-fondo"),
    ("acento-texto", "acento"),
    ("error", "error-fondo"),
    ("exito", "exito-fondo"),
    ("exito", "fondo"),
    ("aviso", "aviso-fondo"),
    *[
        (f"tk-{k}", f)
        for k in (
            "clave",
            "tipo",
            "literal",
            "cadena",
            "numero",
            "comentario",
            "integrada",
            "operador",
        )
        for f in ("editor-fondo", "marca-error")
    ],
]
# Componentes no textuales (bordes de controles, foco): >= 3:1 (WCAG 1.4.11).
PARES_NO_TEXTO = [
    ("borde", "fondo"),
    ("borde", "superficie"),
    ("borde", "editor-fondo"),
    ("foco", "fondo"),
    ("foco", "superficie"),
    ("foco", "editor-fondo"),
    ("acento-fondo", "fondo"),
]


def variables(bloque: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;", bloque))


def temas(css: str | None = None) -> dict[str, dict[str, str]]:
    """{"claro": {...}, "oscuro": {...}, "sistema_oscuro": {...}}."""
    texto = CSS.read_text(encoding="utf-8") if css is None else css
    claro = re.search(r"^:root \{(.*?)^\}", texto, re.S | re.M)
    oscuro = re.search(r'^:root\[data-tema="oscuro"\] \{(.*?)^\}', texto, re.S | re.M)
    sistema = re.search(r'^  :root\[data-tema="sistema"\] \{(.*?)^  \}', texto, re.S | re.M)
    assert claro and oscuro and sistema, "faltan bloques de tema en estilos.css"
    return {
        "claro": variables(claro.group(1)),
        "oscuro": variables(oscuro.group(1)),
        "sistema_oscuro": variables(sistema.group(1)),
    }


def luminancia(color: str) -> float:
    canales = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def fallos(tema: dict[str, str]) -> list[str]:
    """Pares que no llegan a su mínimo (vacío: todo cumple)."""
    salida = []
    for pares, minimo in ((PARES_TEXTO, 7.0), (PARES_NO_TEXTO, 3.0)):
        for a, b in pares:
            r = contraste(tema[a], tema[b])
            if r < minimo:
                salida.append(f"{a} sobre {b}: {r:.2f} < {minimo}")
    return salida


if __name__ == "__main__":
    for nombre, tema in temas().items():
        print(nombre, fallos(tema))
