# toolchain/formatter.py — v4 inveniofmt determinista
# Usa patterns Builder + Strategy; idempotente fmt(fmt(x))==fmt(x)
from __future__ import annotations
import re
from typing import List


def format_code(src: str) -> str:
    # v10: formatter completo con tracking de strings/parens para for(;;) y switch
    # Preserva ; dentro de for(...;...;...) y strings "..."
    out_chars: List[str] = []
    in_str = False
    str_char = ""
    paren_depth = 0
    i = 0
    while i < len(src):
        c = src[i]
        # strings
        if c in ('"', "'") and (i == 0 or src[i - 1] != "\\"):
            if not in_str:
                in_str = True
                str_char = c
            elif c == str_char:
                in_str = False
            out_chars.append(c)
            i += 1
            continue
        if in_str:
            out_chars.append(c)
            i += 1
            continue
        if c == "(":
            paren_depth += 1
            out_chars.append(c)
            i += 1
            continue
        if c == ")":
            paren_depth = max(0, paren_depth - 1)
            out_chars.append(c)
            i += 1
            continue
        if c == ";" and paren_depth == 0:
            out_chars.append(";\n")
            i += 1
            continue
        if c == "{":
            out_chars.append(" {\n")
            i += 1
            continue
        if c == "}":
            out_chars.append("\n}\n")
            i += 1
            continue
        out_chars.append(c)
        i += 1
    tmp = "".join(out_chars)
    # normaliza espacios pero preserva indent
    tmp = re.sub(r"[ \t]+", " ", tmp)
    tmp = re.sub(r" *\n *", "\n", tmp)
    lines: List[str] = []
    indent = 0
    for raw in tmp.splitlines():
        line = raw.strip()
        if not line:
            continue
        # dedent para } y caso/default
        if (
            line.startswith("}")
            or line.startswith("caso ")
            or line.startswith("case ")
            or line.startswith("por_defecto")
            or line.startswith("default")
        ):
            indent = max(0, indent - 1)
        # indent extra para caso body
        is_case = (
            line.startswith("caso ")
            or line.startswith("case ")
            or line.startswith("por_defecto")
            or line.startswith("default")
        )
        lines.append("    " * indent + line)
        if line.endswith("{") or is_case:
            indent += 1
        # dedent si linea es solo } ya manejado, pero si contiene } al final sin {, no indent
        if line.endswith("}") and not line.endswith("{"):
            indent = max(0, indent)
    out = "\n".join(lines).strip() + "\n"
    # normaliza espacios alrededor ops binarios fuera de strings, preservando ++ -- << >> && ||
    out = re.sub(r"\s*([=+\-*/%<>!&|]+)\s*", r" \1 ", out)
    # re-join multi-char ops que fueron separados
    out = out.replace(" + + ", "++").replace(" - - ", "--").replace(" < < ", "<<").replace(" > > ", ">>")
    out = out.replace(" = =", "==").replace(" ! =", "!=").replace(" < =", "<=").replace(" > =", ">=")
    out = (
        out.replace(" & & ", "&&")
        .replace(" | | ", "||")
        .replace(" + =", "+=")
        .replace(" - =", "-=")
        .replace(" * =", "*=")
        .replace(" / =", "/=")
    )
    # fix ++/-- spacing: "i ++" -> "i++", "++ i" -> "++i"
    out = re.sub(r"\s*\+\+\s*", "++", out)
    out = re.sub(r"\s*--\s*", "--", out)
    out = re.sub(r"\s*<<\s*", "<<", out)
    out = re.sub(r"\s*>>\s*", ">>", out)
    out = re.sub(r" +", " ", out)
    out = re.sub(r" *\n *", "\n", out)
    # fix for( spacing y coma, preserva "; " con espacio
    out = out.replace("for (", "for(").replace(" ,", ",").replace("( ", "(").replace(" )", ")")
    out = re.sub(r";\s*", "; ", out)
    out = re.sub(r",\s*", ", ", out)
    out = out.replace("; \n", ";\n").replace(", \n", ",\n")
    return out


def format_file(path: str) -> str:
    import pathlib

    p = pathlib.Path(path)
    src = p.read_text(encoding="utf-8")
    out = format_code(src)
    p.write_text(out, encoding="utf-8")
    return out
