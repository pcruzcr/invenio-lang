# scripts/verify_release.py — Puerta GA determinista y auditable
"""Verifica versión, SBOM, smoke funcional y artefactos de release."""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def fallo(msg):
    """Reporta fallo y retorna False."""
    print(f"FAIL: {msg}")
    return False


def main():
    """Puerta de release: retorna 0 si todo verifica."""
    ok = True
    # 1. Versiones únicas
    from inveniolang import __version__ as pkg_v
    from inveniolang.config import Config
    from inveniolang.core import COMPILER_VERSION

    if not (pkg_v == COMPILER_VERSION == Config().compiler_version == "10.0.0"):
        ok = fallo(f"versiones divergentes {pkg_v}/{COMPILER_VERSION}") and False
    # 2. SBOM y lock existen
    for f in ("SBOM.json", "requirements-lock.txt", "docs/QUICKSTART_EN.md"):
        if not (RAIZ / f).exists():
            ok = fallo(f"falta {f}") and False
    try:
        sbom = json.loads((RAIZ / "SBOM.json").read_text(encoding="utf-8"))
        assert sbom["producto"] == "inveniolang"
    except Exception as e:
        ok = fallo(f"SBOM ilegible: {e}") and False
    # 3. Smoke funcional determinista
    from inveniolang import api

    r = api.ejecutar("void main() { imprimir(2+3*4); }")
    if not (r.ok and "".join(r.salida) == "14"):
        ok = fallo(f"smoke ejecutar: {r}") and False
    m = api.ejecutar("void main() { int x = 5 @ 3; }")
    if m.ok or not any("IL-LEX-002" in e for e in m.errores):
        ok = fallo("smoke error oficial") and False
    # 4. Estructuras extendidas críticas
    for nombre, fragmento in (
        ("conjunto.inv", "union={1,2,3,4,5}"),
        ("kmp.inv", "pos=5"),
        ("floyd.inv", "floyd: 0 3 5 6"),
        ("arbol_b.inv", "buscar12=true"),
    ):
        cod = (RAIZ / "pruebas" / nombre).read_text(encoding="utf-8")
        rr = api.ejecutar(cod)
        if not (rr.ok and fragmento in "".join(rr.salida)):
            ok = fallo(f"{nombre}: {rr.errores if not rr.ok else ''.join(rr.salida)}") and False
    # 5. LSP/presupuestos/policy importables
    try:
        from inveniolang import budgets, lsp, policy  # noqa: F401
        from inveniolang.observability import PipelineMetrics

        mm = PipelineMetrics()
        with mm.mide("smoke"):
            pass
        assert budgets.evaluar_metricas(mm)
        assert "sandbox" in policy.AVISO_AULA
    except Exception as e:
        ok = fallo(f"plataforma: {e}") and False
    print("RELEASE_OK" if ok else "RELEASE_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
