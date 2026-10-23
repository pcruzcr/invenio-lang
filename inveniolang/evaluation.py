"""Evaluación automática de entregas en sandbox + anti-plagio (herramienta docente).

Uso::

    python -m inveniolang.evaluation evaluar prog.inv casos.json [--store aula.jsonl --actor a01]
    python -m inveniolang.evaluation plagio carpeta_entregas/ [--umbral 0.7]

``casos.json`` es una lista de ``{"entrada": ["5", "7"], "esperado": "12"}``.

INV-1024: ``run_secure`` dependía de ``cli.CompilerFacade`` (una segunda copia
del pipeline) para el camino sin sandbox y nada la invocaba. Ahora el camino
sin aislar usa la fachada única ``api.ejecutar``, cada evaluación puede
registrarse en el LMS y el módulo es una herramienta ``python -m`` documentada.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

from . import api
from .lms import LMSStore
from .plagiarism import cluster
from .sandbox import run_sandboxed
from .security import validar_ruta_relativa

__all__ = ["main", "run_secure"]


def _caso_sandbox(file: str, caso: dict[str, Any], timeout: int) -> tuple[bool, str]:
    sb = run_sandboxed(file, timeout=timeout, entrada=list(caso.get("entrada") or []))
    salida = sb.get("stdout", "")
    return bool(sb.get("ok")) and salida.strip() == str(caso.get("esperado", "")).strip(), salida


def _caso_directo(codigo: str, file: str, caso: dict[str, Any]) -> tuple[bool, str]:
    r = api.ejecutar(codigo, ruta=file, entrada=tuple(caso.get("entrada") or ()))
    salida = "".join(r.salida) if r.ok else "\n".join(r.errores)
    return r.ok and salida.strip() == str(caso.get("esperado", "")).strip(), salida


def run_secure(
    file: str,
    casos: list[dict[str, Any]],
    timeout: int = 5,
    use_sandbox: bool = True,
    store: LMSStore | None = None,
    actor: str = "anonimo",
) -> dict[str, Any]:
    """Evalúa un ``.inv`` contra casos de prueba y devuelve nota 0..10.

    Con ``use_sandbox=True`` (por defecto, código de estudiantes) cada caso
    corre en un subproceso con límites de CPU/memoria y el único resultado
    válido es el del sandbox. ``use_sandbox=False`` es solo para código
    confiable del docente. Si se pasa ``store`` se registra un intento xAPI
    (``passed``/``failed``) con los códigos de error observados.
    """
    codigo = "" if use_sandbox else pathlib.Path(file).read_text(encoding="utf-8")
    results = []
    for c in casos:
        if use_sandbox:
            ok, salida = _caso_sandbox(file, c, timeout)
        else:
            ok, salida = _caso_directo(codigo, file, c)
        results.append({"caso": c, "ok": ok, "salida": salida[:200]})
    passed = sum(1 for r in results if r["ok"])
    resumen = {
        "passed": passed,
        "total": len(casos),
        "results": results,
        "nota": round(passed / max(1, len(casos)) * 10, 2),
        "sandbox": use_sandbox,
    }
    if store is not None:
        verbo = "passed" if passed == len(casos) else "failed"
        errores = [r["salida"] for r in results if not r["ok"]]
        store.record(actor, verbo, file, {"nota": resumen["nota"], "errores": errores})
    return resumen


def _evaluar(args: argparse.Namespace) -> int:
    validar_ruta_relativa(args.programa)
    casos = json.loads(pathlib.Path(args.casos).read_text(encoding="utf-8"))
    store = LMSStore(args.store) if args.store else None
    r = run_secure(args.programa, casos, timeout=args.timeout, store=store, actor=args.actor)
    for i, res in enumerate(r["results"], 1):
        print(f"caso {i}: {'OK' if res['ok'] else 'FALLA'}")
    print(f"nota: {r['nota']} ({r['passed']}/{r['total']})")
    return 0 if r["passed"] == r["total"] else 1


def _plagio(args: argparse.Namespace) -> int:
    rutas = sorted(pathlib.Path(args.carpeta).glob("*.inv"))
    grupos = cluster([p.read_text(encoding="utf-8") for p in rutas], args.umbral)
    for grupo in grupos:
        print("similares: " + ", ".join(rutas[i].name for i in sorted(grupo)))
    if not grupos:
        print("sin entregas similares")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI docente: subcomandos ``evaluar`` y ``plagio``."""
    p = argparse.ArgumentParser(prog="python -m inveniolang.evaluation")
    sub = p.add_subparsers(dest="comando", required=True)
    ev = sub.add_parser("evaluar", help="corre casos de prueba en sandbox")
    ev.add_argument("programa")
    ev.add_argument("casos", help="JSON: lista de {entrada, esperado}")
    ev.add_argument("--timeout", type=int, default=5)
    ev.add_argument("--store", help="registro xAPI JSONL (ver python -m inveniolang.lms)")
    ev.add_argument("--actor", default="anonimo")
    pl = sub.add_parser("plagio", help="agrupa entregas .inv similares de una carpeta")
    pl.add_argument("carpeta")
    pl.add_argument("--umbral", type=float, default=0.7)
    args = p.parse_args(argv)
    return _evaluar(args) if args.comando == "evaluar" else _plagio(args)


if __name__ == "__main__":
    raise SystemExit(main())
