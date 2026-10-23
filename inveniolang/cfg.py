"""Grafo de flujo de control (CFG) en bloques básicos sobre el TAC de ``ir.py``.

INV-1016: la versión anterior construía el CFG desde el AST y sus
"instrucciones" eran cadenas como ``"Assignment"`` o ``"if <repr>"``: no había
código que analizar y el SSA de encima solo anteponía un texto ``phi(...)``.
Ahora el CFG parte del código de tres direcciones real:

* **Líderes**: la primera instrucción, cada ``label`` y la instrucción que
  sigue a un salto (``goto``/``if_false``/``return``).
* **Aristas**: ``goto L`` → L; ``if_false c goto L`` → L y la siguiente;
  ``return`` → ninguna; ``try_begin catch=L`` añade una arista a L (cualquier
  instrucción del bloque protegido puede saltar al manejador).

Los bloques inalcanzables desde la entrada se descartan (no tienen dominador).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ir import Instr

__all__ = ["BloqueBasico", "construir_cfg"]

_SALTOS = ("goto", "if_false", "return")


@dataclass
class BloqueBasico:
    """Secuencia maximal de instrucciones TAC sin saltos internos."""

    id: str
    instrs: list[Instr] = field(default_factory=list)
    sucesores: list[str] = field(default_factory=list)
    predecesores: list[str] = field(default_factory=list)


def construir_cfg(instrucciones: list[Instr]) -> dict[str, BloqueBasico]:
    """Particiona ``instrucciones`` en bloques básicos enlazados; ``B0`` es la entrada."""
    if not instrucciones:
        return {"B0": BloqueBasico("B0")}
    lideres = {0}
    for i, ins in enumerate(instrucciones):
        if ins.op == "label":
            lideres.add(i)
        if ins.op in _SALTOS and i + 1 < len(instrucciones):
            lideres.add(i + 1)
    orden = sorted(lideres)
    bloques: dict[str, BloqueBasico] = {}
    etiqueta_a_bloque: dict[str, str] = {}
    for n, inicio in enumerate(orden):
        fin = orden[n + 1] if n + 1 < len(orden) else len(instrucciones)
        bid = f"B{n}"
        bloques[bid] = BloqueBasico(bid, list(instrucciones[inicio:fin]))
        if instrucciones[inicio].op == "label":
            etiqueta_a_bloque[instrucciones[inicio].arg1] = bid
    ids = list(bloques)
    for n, bid in enumerate(ids):
        blq = bloques[bid]
        ultima = blq.instrs[-1]
        destinos: list[str] = []
        for ins in blq.instrs:
            if ins.op == "try_begin" and ins.arg1 in etiqueta_a_bloque:
                destinos.append(etiqueta_a_bloque[ins.arg1])
        if ultima.op == "goto":
            destinos.append(etiqueta_a_bloque[ultima.arg1])
        elif ultima.op == "if_false":
            destinos.append(etiqueta_a_bloque[ultima.arg2])
        if ultima.op not in ("goto", "return") and n + 1 < len(ids):
            destinos.append(ids[n + 1])
        for d in destinos:
            if d not in blq.sucesores:
                blq.sucesores.append(d)
    alcanzables = _alcanzables(bloques, "B0")
    bloques = {b: blq for b, blq in bloques.items() if b in alcanzables}
    for bid, blq in bloques.items():
        blq.sucesores = [s for s in blq.sucesores if s in bloques]
        for s in blq.sucesores:
            bloques[s].predecesores.append(bid)
    return bloques


def _alcanzables(bloques: dict[str, BloqueBasico], entrada: str) -> set[str]:
    vistos = {entrada}
    pila = [entrada]
    while pila:
        for s in bloques[pila.pop()].sucesores:
            if s not in vistos:
                vistos.add(s)
                pila.append(s)
    return vistos
