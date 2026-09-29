# visual/trees.py — v10 visualización árboles AVL, grafos, listas
from __future__ import annotations
from typing import Any, List


def render_arbol(nodo: Any, get_val=lambda n: str(n), get_izq=lambda n: None, get_der=lambda n: None) -> str:
    # ASCII art para AVL/BST, agil O(n) - usa ASCII puro para Windows cp1252
    if nodo is None:
        return "(vacio)"
    lines: List[str] = []

    def dfs(n, pref="", is_left=True):
        if n is None:
            return
        lines.append(pref + ("|-- " if is_left else "`-- ") + get_val(n))
        izq, der = get_izq(n), get_der(n)
        if izq or der:
            if izq:
                dfs(izq, pref + ("|   " if is_left else "    "), True)
            if der:
                dfs(der, pref + ("|   " if is_left else "    "), False)

    dfs(nodo, "", False)
    return "\n".join(lines)


def render_grafo(matriz: List[List[int]], labels: List[str] = None) -> str:
    n = len(matriz)
    labels = labels or [str(i) for i in range(n)]
    out = ["graph G {"]
    for i in range(n):
        for j in range(i + 1, n):
            if matriz[i][j]:
                out.append(f'  {labels[i]} -- {labels[j]} [label="{matriz[i][j]}"];')
    out.append("}")
    return "\n".join(out)


def render_lista(
    head: Any, get_val=lambda n: n.campos.get("valor", "?"), get_next=lambda n: n.campos.get("siguiente")
) -> str:
    vals = []
    cur = head
    seen = set()
    while cur and id(cur) not in seen and len(vals) < 50:
        seen.add(id(cur))
        vals.append(str(get_val(cur)))
        cur = get_next(cur)
    return " -> ".join(vals) + (" -> null" if vals else "(vacio)")
