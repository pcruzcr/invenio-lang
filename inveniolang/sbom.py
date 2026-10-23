# sbom.py — SBOM determinista mínimo, auditable y soberano
#
# Cubre: auditable, gobernable, cumplible, verificable, reproducible,
# preparado para auditoría/cambios regulatorios. Sin red, sin dependencias.
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

from ._version import __version__


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def generar_sbom(raiz: str | None = None) -> dict:
    """Genera SBOM determinista del proyecto."""
    raiz_p = Path(raiz or Path(__file__).resolve().parent.parent)
    ficheros = []
    for nombre in ("pyproject.toml", "requirements.txt", "main.py"):
        p = raiz_p / nombre
        if p.exists():
            ficheros.append({"ruta": nombre, "sha256": _sha256_file(p), "bytes": p.stat().st_size})
    try:
        import ply  # type: ignore

        ply_v = getattr(ply, "__version__", "?")
    except Exception:
        ply_v = "no-instalado"
    return {
        "producto": "inveniolang",
        "version": __version__,
        "python": platform.python_version(),
        "plataforma": sys.platform,
        "dependencias": [
            {"nombre": "ply", "version": ply_v},
            {"nombre": "PySide6", "version": ">=6.6-opcional-gui"},
        ],
        "ficheros_clave": sorted(ficheros, key=lambda x: x["ruta"]),
    }


def main() -> int:
    """CLI: python -m inveniolang.sbom [--check]."""
    import sys as _sys

    sbom = generar_sbom()
    texto = json.dumps(sbom, ensure_ascii=False, indent=2, sort_keys=True)
    if "--check" in _sys.argv:
        # Verificable: regenerar dos veces debe dar mismo resultado salvo plataforma.
        otra = generar_sbom()
        ok = sbom["ficheros_clave"] == otra["ficheros_clave"]
        print(texto)
        return 0 if ok else 1
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
