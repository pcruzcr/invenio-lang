# viewer — Rosetta viewer para aprender 7 lenguajes sin compilarlos
from .rosetta import TranspilerFactory, transpile

__all__ = ["transpile", "TranspilerFactory"]
