"""Anti-plagio para el docente (ver ``python -m inveniolang.evaluation plagio``)."""

from .cluster import cluster, gramas, normalizar, plagiarism_score, similitud_gramas

__all__ = ["cluster", "gramas", "normalizar", "plagiarism_score", "similitud_gramas"]
