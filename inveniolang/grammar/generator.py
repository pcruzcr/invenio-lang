# grammar/generator.py — v8 generador EBNF → parser.py
from __future__ import annotations

import pathlib


# Lee docs/gramatica.ebnf y genera esqueleto parser.py (demostración)
def generate(src="docs/gramatica.ebnf", dst="inveniolang/parser_gen.py"):
    """Genera el esqueleto desde la EBNF."""
    ebnf = pathlib.Path(src).read_text(encoding="utf-8")
    prods = [ln for ln in ebnf.splitlines() if "::=" in ln]
    out = f"# AUTO-GENERADO desde {src} — {len(prods)} prods — no editar\n"
    out += "prods = " + repr(prods[:3]) + "\n"
    pathlib.Path(dst).write_text(out, encoding="utf-8")
    return f"{len(prods)} prods → {dst}"


if __name__ == "__main__":
    print(generate())
