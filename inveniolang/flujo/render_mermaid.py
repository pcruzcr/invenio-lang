"""Exportación a Mermaid ``flowchart TD`` (INV-3006).

Cada símbolo usa la forma Mermaid equivalente a su símbolo ISO 5807
(terminal ``([…])``, proceso ``[…]``, decisión ``{…}``, datos ``[/…/]``,
proceso predefinido ``[[…]]``, conector ``((…))``). Mermaid hace su propio
trazado, así que aquí los saltos (``romper``, ``continuar``, caída de un
caso) sí se dibujan como flechas, punteadas para distinguirlas. Se añaden
``accTitle``/``accDescr`` para los lectores de pantalla.
"""

from __future__ import annotations

from .esquema import Esquema

__all__ = ["mermaid_esquemas"]

_FORMAS = {
    "terminal": ('(["', '"])'),
    "proceso": ('["', '"]'),
    "decision": ('{"', '"}'),
    "datos": ('[/"', '"/]'),
    "predefinido": ('[["', '"]]'),
    "conector": ('(("', '"))'),
}


def _escapar(texto: str) -> str:
    """Texto seguro dentro de las comillas de una etiqueta Mermaid."""
    reemplazos = {"&": "#amp;", '"': "#quot;", "<": "#lt;", ">": "#gt;", "\n": " "}
    return "".join(reemplazos.get(c, c) for c in texto)


def _una_linea(texto: str) -> str:
    return " ".join(texto.split())


def _cuerpo(e: Esquema, prefijo: str, sangria: str) -> list[str]:
    lineas: list[str] = []
    for n in e.nodos:
        abre, cierra = _FORMAS[n.simbolo]
        if n.simbolo == "conector":
            texto = " ".join(x for x in (n.marca, n.texto) if x) or " "
        else:
            texto = n.texto
        lineas.append(f"{sangria}{prefijo}{n.id}{abre}{_escapar(texto)}{cierra}")
    for a in e.aristas:
        flecha = "-.->" if a.salto else "-->"
        etiqueta = f'|"{_escapar(a.etiqueta)}"|' if a.etiqueta else ""
        lineas.append(f"{sangria}{prefijo}{a.desde} {flecha}{etiqueta} {prefijo}{a.hasta}")
    return lineas


def mermaid_esquemas(esquemas: list[Esquema], titulo: str, descripcion: str) -> str:
    """Un ``flowchart TD``; con varios diagramas, un ``subgraph`` por cada uno."""
    lineas = [
        "flowchart TD",
        f"    accTitle: {_una_linea(titulo)}",
        f"    accDescr: {_una_linea(descripcion)}",
    ]
    if len(esquemas) == 1:
        lineas.extend(_cuerpo(esquemas[0], "", "    "))
    else:
        for k, e in enumerate(esquemas):
            lineas.append(f'    subgraph d{k}["{_escapar(e.titulo)}"]')
            lineas.extend(_cuerpo(e, f"d{k}_", "        "))
            lineas.append("    end")
    return "\n".join(lineas) + "\n"
