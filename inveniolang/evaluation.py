# evaluation.py — Evaluación cerrada + anti-plagio (Sprint 2)
# Patrones: Strategy (rúbrica), Factory (casos), Observer (progreso)
from __future__ import annotations

import re
from typing import Any

from .cli import CompilerFacade


def normalize_ast(text: str) -> str:
    """Normaliza el AST para comparar."""
    # winnowing: quita comentarios, normaliza identificadores a X
    text = re.sub(r"//.*|/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"\b(int|float|string|bool|void|texto|entero|real|logico)\b", "TIPO", text)
    text = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", "X", text)
    return " ".join(text.split())


def plagiarism_score(a: str, b: str, k: int = 5) -> float:
    """Calcula similitud entre entregas."""

    # winnowing k-grams Jaccard
    def grams(s):
        """Calcula k-gramas para similitud."""
        return {s[i : i + k] for i in range(len(s) - k + 1)} if len(s) >= k else {s}

    grams_a, grams_b = grams(normalize_ast(a)), grams(normalize_ast(b))
    if not grams_a or not grams_b:
        return 0.0
    return len(grams_a & grams_b) / len(grams_a | grams_b)


def run_secure(
    file: str, casos: list[dict[str, Any]], timeout: int = 5, use_sandbox: bool = True
) -> dict[str, Any]:
    """Evalúa un .inv contra casos de prueba.

    Corrección de seguridad (auditoría): antes se lanzaba el sandbox pero su
    resultado se ignoraba y luego se ejecutaba el programa de nuevo SIN
    aislamiento (doble ejecución, ninguna realmente aislada). Ahora, cuando
    use_sandbox=True, el único resultado válido es el del sandbox.
    """
    from .sandbox import run_sandboxed

    fac = CompilerFacade()
    results = []
    for c in casos:
        if use_sandbox:
            sb = run_sandboxed(
                file, strategy="resource", timeout=timeout, entrada=list(c.get("entrada") or [])
            )
            salida = sb.get("stdout", "")
            ok = sb.get("ok") and salida.strip() == c.get("esperado", "").strip()
            results.append(
                {
                    "caso": c,
                    "ok": ok,
                    "salida": salida[:200],
                    "sandbox": "ok" if sb.get("ok") else "fallo",
                }
            )
            continue
        r = fac.execute(file, c.get("entrada", []))
        ok = r.get("ok") and "".join(r.get("salida", [])).strip() == c.get("esperado", "").strip()
        results.append({"caso": c, "ok": ok, "salida": "".join(r.get("salida", []))[:200]})
    passed = sum(1 for r in results if r["ok"])
    return {
        "passed": passed,
        "total": len(casos),
        "results": results,
        "nota": round(passed / max(1, len(casos)) * 10, 2),
        "sandbox": use_sandbox,
    }
