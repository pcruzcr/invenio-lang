"""Integración de InvenioLang con el estudio web (``web/estudio/``, Fase 4).

INV-4200: el estudio corre el compilador real dentro de Pyodide (CPython en
WebAssembly) en un *Web Worker*. Entre JavaScript y Python solo cruza texto
JSON a través de :func:`inveniolang.web.puente.llamar`, de modo que el
contrato es explícito, versionado y se prueba igual en CPython que en el
navegador. Documentación: ``web/README.md``.
"""

from __future__ import annotations

from .puente import CONTRATO, METODOS, llamar

__all__ = ["CONTRATO", "METODOS", "llamar"]
