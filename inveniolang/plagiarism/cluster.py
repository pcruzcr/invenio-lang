"""Detección de similitud entre entregas: huellas de k-gramas + Union-Find.

INV-1024: estas funciones vivían en ``evaluation.py`` y aquí solo se
reexportaban (con un ``noqa: F401``); ahora este es su único hogar y
``evaluation`` las consume.
"""

from __future__ import annotations

import re

__all__ = ["cluster", "gramas", "normalizar", "plagiarism_score", "similitud_gramas"]

_TIPOS = r"\b(int|float|string|bool|void|texto|entero|real|logico)\b"
# INV-5005: un solo patrón con alternativas y coincidencia más a la izquierda.
# Antes era ``//.*`` con ``re.S``: el punto cruzaba saltos de línea y el primer
# ``//`` borraba TODO el resto del archivo, así que cualquier entrega con un
# comentario quedaba vacía y la similitud salía siempre 0. Los literales de
# texto se conservan: un ``"//"`` dentro de una cadena no es un comentario.
_COMENTARIO_O_TEXTO = re.compile(
    r""""(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|//[^\n]*|/\*[\s\S]*?\*/"""
)


def _sin_comentarios(codigo: str) -> str:
    return _COMENTARIO_O_TEXTO.sub(lambda m: m.group(0) if m.group(0)[0] in "\"'" else " ", codigo)


def normalizar(codigo: str) -> str:
    """Quita comentarios y reduce tipos e identificadores a comodines.

    Renombrar variables o cambiar ``int`` por ``entero`` no oculta una copia.
    """
    codigo = _sin_comentarios(codigo)
    codigo = re.sub(_TIPOS, "TIPO", codigo)
    codigo = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", "X", codigo)
    return " ".join(codigo.split())


def gramas(codigo: str, k: int = 5) -> frozenset[str]:
    """K-gramas del código normalizado (huella para comparar entregas)."""
    s = normalizar(codigo)
    if not s:
        return frozenset()
    if len(s) < k:
        return frozenset({s})
    return frozenset(s[i : i + k] for i in range(len(s) - k + 1))


def similitud_gramas(grams_a: frozenset[str], grams_b: frozenset[str]) -> float:
    """Índice de Jaccard entre dos huellas."""
    if not grams_a or not grams_b:
        return 0.0
    return len(grams_a & grams_b) / len(grams_a | grams_b)


def plagiarism_score(a: str, b: str, k: int = 5) -> float:
    """Similitud 0..1 entre dos entregas; dos vacías no cuentan como idénticas."""
    return similitud_gramas(gramas(a, k), gramas(b, k))


def cluster(codes: list[str], threshold: float = 0.7) -> list[set[int]]:
    """Agrupa (por índice) las entregas cuya similitud supera ``threshold``."""
    n = len(codes)
    padre = list(range(n))

    def raiz(x: int) -> int:
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    # Huellas calculadas UNA vez por entrega (no por par).
    huellas = [gramas(c) for c in codes]
    for i in range(n):
        for j in range(i + 1, n):
            if similitud_gramas(huellas[i], huellas[j]) >= threshold:
                ri, rj = raiz(i), raiz(j)
                if ri != rj:
                    padre[rj] = ri
    grupos: dict[int, set[int]] = {}
    for i in range(n):
        grupos.setdefault(raiz(i), set()).add(i)
    return [g for g in grupos.values() if len(g) > 1]
