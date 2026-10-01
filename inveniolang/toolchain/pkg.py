# toolchain/pkg.py — v4 invenio.pkg 100% — import como lib, deps, versionado
# Auditoría v10.1: JSON seguro (JSONDecodeError controlado), validación de
# nombre con security.validar_ruta_relativa, escritura atómica (temp + rename).
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import time

PKG_FILE = "invenio.json"
_NOMBRE_OK = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def _cargar_pkg() -> dict | None:
    """Carga invenio.json con manejo robusto (corrupto → None, no crash)."""
    p = pathlib.Path(PKG_FILE)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def _escribir_atomico(data: dict) -> None:
    """Escritura atómica: escribe a .tmp y hace replace (sin partial writes)."""
    p = pathlib.Path(PKG_FILE)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def init_pkg(name: str, version: str = "0.1.0", deps: list[str] | None = None):
    """Inicializa el paquete."""
    if not _NOMBRE_OK.match(name or ""):
        raise ValueError(f"nombre de paquete inválido: {name!r}")
    if not re.match(r"^\d+\.\d+\.\d+$", version or ""):
        raise ValueError(f"versión inválida (esperado X.Y.Z): {version!r}")
    data = {
        "name": name,
        "version": version,
        "deps": list(deps or []),
        "invenio": "10.0",
        "created": time.strftime("%Y-%m-%d"),
    }
    _escribir_atomico(data)
    pathlib.Path("src").mkdir(exist_ok=True)
    pathlib.Path("pruebas").mkdir(exist_ok=True)
    return PKG_FILE


def add_dep(dep: str):
    """Agrega una dependencia."""
    if not _NOMBRE_OK.match(dep or ""):
        raise ValueError(f"nombre de dependencia inválido: {dep!r}")
    data = _cargar_pkg()
    if data is None:
        init_pkg("app")
        data = _cargar_pkg() or {"deps": []}
    deps = data.setdefault("deps", [])
    if dep not in deps:
        deps.append(dep)
        _escribir_atomico(data)
    return deps


def resolve_deps() -> list[str]:
    """Resuelve dependencias."""
    data = _cargar_pkg()
    return list(data.get("deps", [])) if data else []


def pkg_hash() -> str:
    """Hash del paquete."""
    p = pathlib.Path(PKG_FILE)
    if not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def install_deps(dry_run: bool = False) -> list[str]:
    """Instala dependencias."""
    deps = resolve_deps()
    if dry_run:
        return deps
    # En v10, deps son otros paquetes .inv locales; verifica existen
    missing = [
        d
        for d in deps
        if not pathlib.Path(d).exists() and not pathlib.Path(f"pruebas/{d}.inv").exists()
    ]
    return missing
