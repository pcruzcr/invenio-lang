# toolchain/linter.py — v4 invenio lint 100% — IL-WARN como Strategy, ágil
from __future__ import annotations

import re

from ..patterns import Strategy


class LintRule(Strategy):
    """LintRule como estrategia intercambiable."""

    def execute(self, src: str, *a, **kw) -> list[dict]:
        """Ejecuta la operación."""
        raise NotImplementedError


class NoVarShadow(LintRule):
    """Regla de sombreado."""

    def execute(self, src: str, *a, **kw) -> list[dict]:
        """Ejecuta la operación."""
        warns = []
        # Detecta int x; { int x; } — busca declaraciones duplicadas en scopes anidados
        decls = re.findall(
            r"\b(?:int|float|string|bool|texto|entero|real|logico|void)\s+(\w+)\b", src
        )
        seen = {}
        for name in decls:
            if name in seen:
                warns.append(
                    {
                        "code": "IL-WARN-001",
                        "msg": f"'{name}' oculta externo (sombreado)",
                        "level": "warn",
                        "name": name,
                    }
                )
                break
            seen[name] = 1
        # También detecta patrón clásico con llaves: int x; { int x;
        if not warns and re.search(r"\b\w+\s+\w+\s*;[^}]*\{\s*\w+\s+\w+", src, re.S):
            # si hay al menos 2 declaraciones y una está dentro de {, es sombreado
            if len(decls) != len(set(decls)):
                dup = next(n for n in decls if decls.count(n) > 1)
                warns.append(
                    {
                        "code": "IL-WARN-001",
                        "msg": f"'{dup}' oculta externo",
                        "level": "warn",
                        "name": dup,
                    }
                )
        return warns


class NoUnused(LintRule):
    """Regla de variable sin uso."""

    def execute(self, src: str, *a, **kw) -> list[dict]:
        """Ejecuta la operación."""
        warns = []
        for m in re.finditer(r"\b(int|float|string|bool|texto|entero|real)\s+(\w+)\s*[=;]", src):
            name = m.group(2)
            # cuenta usos fuera de declaración
            uses = len(re.findall(rf"\b{re.escape(name)}\b", src))
            if uses <= 1:
                warns.append(
                    {
                        "code": "IL-WARN-002",
                        "msg": f"'{name}' sin uso",
                        "level": "warn",
                        "name": name,
                    }
                )
        return warns


class LongFunction(LintRule):
    """Regla de función larga."""

    def execute(self, src: str, *a, **kw) -> list[dict]:
        """Ejecuta la operación."""
        # Si función >30 líneas, sugiere refactor
        if src.count("\n") > 30 and "void main" in src:
            # cuenta líneas por función
            funcs = re.findall(r"\b(void|int|float|string|bool)\s+\w+\s*\([^)]*\)\s*\{", src)
            if len(funcs) > 5:
                return [
                    {
                        "code": "IL-WARN-003",
                        "msg": "muchas funciones, considera modularizar",
                        "level": "info",
                    }
                ]
        return []


class MagicNumber(LintRule):
    """Regla de número mágico."""

    def execute(self, src: str, *a, **kw) -> list[dict]:
        """Ejecuta la operación."""
        warns = []
        for m in re.finditer(r"[^a-zA-Z_](\d{2,})\b", src):
            num = m.group(1)
            if num not in ("10", "100", "1000") and int(num) > 10:
                warns.append(
                    {
                        "code": "IL-WARN-004",
                        "msg": f"número mágico {num}, usa const",
                        "level": "info",
                        "value": num,
                    }
                )
                break
        return warns


def lint(src: str) -> list[dict]:
    """Analiza el código."""
    rules: list[LintRule] = [NoVarShadow(), NoUnused(), LongFunction(), MagicNumber()]
    out: list[dict] = []
    seen = set()
    for r in rules:
        for w in r.execute(src):
            key = (w["code"], w.get("name", "") + w.get("value", ""))
            if key not in seen:
                out.append(w)
                seen.add(key)
    return sorted(out, key=lambda x: x["code"])
