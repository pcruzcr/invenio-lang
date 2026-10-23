"""Dominadores y forma SSA (Static Single Assignment) del TAC.

INV-1016: antes ``to_ssa`` anteponía la cadena ``"phi(a, b)"`` a cualquier
bloque con dos predecesores, sin variables ni renombrado: no era SSA. Ahora
es el algoritmo de Cytron et al. sobre el CFG real de :mod:`inveniolang.cfg`:

1. **Dominadores** por punto fijo y dominador inmediato (``idom``).
2. **Frontera de dominancia** (algoritmo de Cooper, Harvey y Kennedy).
3. **Inserción de φ** en la frontera iterada de los bloques que definen cada
   variable, *podada* por liveness: solo donde la variable está viva.
4. **Renombrado** recorriendo el árbol de dominadores con una pila de
   versiones por variable: cada definición crea ``x_1``, ``x_2``...; los
   parámetros y las globales entran como versión ``_0``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cfg import BloqueBasico, construir_cfg
from .ir import Instr, _usos_defs_instr

__all__ = ["FuncionSSA", "a_ssa", "dominadores", "frontera_dominancia", "formatear_ssa"]


def dominadores(cfg: dict[str, BloqueBasico], entrada: str = "B0") -> dict[str, set[str]]:
    """``dom[b]``: bloques que dominan a ``b`` (incluido ``b``)."""
    todos = set(cfg)
    dom = {b: set(todos) for b in cfg}
    dom[entrada] = {entrada}
    cambio = True
    while cambio:
        cambio = False
        for b in cfg:
            if b == entrada or not cfg[b].predecesores:
                continue
            nuevo = set.intersection(*(dom[p] for p in cfg[b].predecesores)) | {b}
            if nuevo != dom[b]:
                dom[b] = nuevo
                cambio = True
    return dom


def _idom(dom: dict[str, set[str]], entrada: str) -> dict[str, str]:
    """Dominador inmediato: el dominador estricto con más dominadores propios."""
    return {
        b: max(dom[b] - {b}, key=lambda d: len(dom[d]))
        for b in dom
        if b != entrada and dom[b] - {b}
    }


def frontera_dominancia(cfg: dict[str, BloqueBasico], entrada: str = "B0") -> dict[str, set[str]]:
    """``DF[b]``: bloques donde deja de valer la dominancia de ``b``."""
    idom = _idom(dominadores(cfg, entrada), entrada)
    df: dict[str, set[str]] = {b: set() for b in cfg}
    for b, blq in cfg.items():
        if len(blq.predecesores) < 2:
            continue
        for p in blq.predecesores:
            corredor: str | None = p
            while corredor is not None and corredor != idom.get(b):
                df[corredor].add(b)
                corredor = idom.get(corredor)
    return df


@dataclass
class Phi:
    """``destino = φ(pred: version, ...)`` al inicio de un bloque."""

    variable: str
    destino: str = ""
    argumentos: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        args = ", ".join(f"{p}: {v}" for p, v in sorted(self.argumentos.items()))
        return f"    {self.destino} = φ({args})"


@dataclass
class FuncionSSA:
    """Resultado de :func:`a_ssa`: bloques con sus φ y sus instrucciones renombradas."""

    cfg: dict[str, BloqueBasico]
    phis: dict[str, list[Phi]]
    instrs: dict[str, list[str]]


def _vivas_al_entrar(cfg: dict[str, BloqueBasico]) -> dict[str, set[str]]:
    usos: dict[str, set[str]] = {}
    defs: dict[str, set[str]] = {}
    for b, blq in cfg.items():
        u: set[str] = set()
        d: set[str] = set()
        for ins in blq.instrs:
            iu, idf = _usos_defs_instr(ins)
            u |= iu - d
            d |= idf
        usos[b], defs[b] = u, d
    vivas = {b: set(usos[b]) for b in cfg}
    cambio = True
    while cambio:
        cambio = False
        for b in cfg:
            salida = set().union(*(vivas[s] for s in cfg[b].sucesores))
            nuevo = usos[b] | (salida - defs[b])
            if nuevo != vivas[b]:
                vivas[b] = nuevo
                cambio = True
    return vivas


def _renombrar_instr(ins: Instr, actual: dict[str, str], nueva: str | None) -> str:
    usos, _ = _usos_defs_instr(ins)
    campos = [ins.arg1, ins.arg2, ins.arg3]
    campos = [actual.get(c, f"{c}_0") if isinstance(c, str) and c in usos else c for c in campos]
    a1, a2, a3 = campos
    copia = Instr(ins.op, a1, a2, a3, resultado=nueva if nueva is not None else ins.resultado)
    return repr(copia)


def a_ssa(instrucciones: list[Instr], entrada: str = "B0") -> FuncionSSA:
    """Convierte el TAC de una subrutina a SSA podada."""
    cfg = construir_cfg(instrucciones)
    df = frontera_dominancia(cfg, entrada)
    vivas = _vivas_al_entrar(cfg)
    sitios: dict[str, set[str]] = {}
    for b, blq in cfg.items():
        for ins in blq.instrs:
            for v in _usos_defs_instr(ins)[1]:
                sitios.setdefault(v, set()).add(b)
    phis: dict[str, list[Phi]] = {b: [] for b in cfg}
    for v, bloques_def in sitios.items():
        trabajo = list(bloques_def)
        con_phi: set[str] = set()
        while trabajo:
            for y in df[trabajo.pop()]:
                if y not in con_phi and v in vivas[y]:
                    con_phi.add(y)
                    phis[y].append(Phi(v))
                    if y not in bloques_def:
                        trabajo.append(y)
    idom = _idom(dominadores(cfg, entrada), entrada)
    hijos: dict[str, list[str]] = {b: [] for b in cfg}
    for b, padre in idom.items():
        hijos[padre].append(b)
    contador: dict[str, int] = {}
    instrs: dict[str, list[str]] = {}

    def nueva_version(v: str) -> str:
        contador[v] = contador.get(v, 0) + 1
        return f"{v}_{contador[v]}"

    pendientes: list[tuple[str, dict[str, str]]] = [(entrada, {})]
    while pendientes:
        b, heredado = pendientes.pop()
        actual = dict(heredado)
        for phi in phis[b]:
            phi.destino = nueva_version(phi.variable)
            actual[phi.variable] = phi.destino
        lineas = []
        for ins in cfg[b].instrs:
            defs = _usos_defs_instr(ins)[1]
            destino = nueva_version(next(iter(defs))) if defs else None
            lineas.append(_renombrar_instr(ins, actual, destino))
            if defs and destino is not None:
                actual[next(iter(defs))] = destino
        instrs[b] = lineas
        for s in cfg[b].sucesores:
            for phi in phis[s]:
                phi.argumentos[b] = actual.get(phi.variable, f"{phi.variable}_0")
        for h in sorted(hijos[b], reverse=True):
            pendientes.append((h, actual))
    return FuncionSSA(cfg, phis, instrs)


def formatear_ssa(funcion: FuncionSSA) -> str:
    """Texto legible: cada bloque con predecesores, φ e instrucciones renombradas."""
    salida = []
    for b, blq in funcion.cfg.items():
        preds = ", ".join(blq.predecesores) or "-"
        salida.append(f"{b}:  (pred: {preds}; suc: {', '.join(blq.sucesores) or '-'})")
        salida.extend(str(p) for p in funcion.phis[b])
        salida.extend(funcion.instrs.get(b, []))
    return "\n".join(salida)
