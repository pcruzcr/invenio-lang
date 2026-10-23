"""Viewer Rosetta: ver un programa InvenioLang escrito en Python, C, Java, C# o Pascal."""

from .rosetta import TranspilerFactory, transpile

__all__ = ["transpile", "TranspilerFactory"]
