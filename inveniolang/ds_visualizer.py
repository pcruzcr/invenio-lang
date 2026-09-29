# ds_visualizer.py — H1.2 Visualización memoria viva
# Reusa symbol_table.py:116 SymbolTable + interpreter.py:240 pila_marcos
# Patrones: Observer (escucha Interpreter), Strategy (render por tipo), Builder (grafo)
from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from .patterns import Observer, Strategy


@dataclass
class NodoVisual:
    id: str
    tipo: str  # arreglo, lista, pila, objeto, variable
    etiqueta: str
    valores: List[Any] = field(default_factory=list)
    conexiones: List[str] = field(default_factory=list)  # ids destino
    linea: int = 0


@dataclass
class SnapshotMemoria:
    # Capturado desde Interpreter._snapshot_debug + SymbolTable
    variables: List[Dict[str, Any]]
    pila: List[str]
    linea: int
    nodos: List[NodoVisual] = field(default_factory=list)


class RenderStrategy(Strategy):
    def execute(self, valor: Any, nombre: str, tipo: str, *args, **kwargs) -> Optional[NodoVisual]:
        raise NotImplementedError


class ArregloStrategy(RenderStrategy):
    def execute(self, valor: Any, nombre: str, tipo: str, *args, **kwargs) -> Optional[NodoVisual]:
        if isinstance(valor, list) and tipo in ("int", "float", "string", "bool"):
            return NodoVisual(id=nombre, tipo="arreglo", etiqueta=f"{nombre}[{len(valor)}]:{tipo}", valores=list(valor))
        return None


class ListaEnlazadaStrategy(RenderStrategy):
    def execute(self, valor: Any, nombre: str, tipo: str, *args, **kwargs) -> Optional[NodoVisual]:
        # Detecta InstanciaObjeto con campo 'siguiente' o 'next'
        from .interpreter import InstanciaObjeto

        if isinstance(valor, InstanciaObjeto):
            # Recolecta cadena siguiente
            nodos = []
            cur = valor
            visited = set()
            while cur and id(cur) not in visited and len(nodos) < 50:
                visited.add(id(cur))
                nodos.append(cur)
                nxt = cur.campos.get("siguiente") or cur.campos.get("next") or cur.campos.get("sig")
                if isinstance(nxt, InstanciaObjeto):
                    cur = nxt
                else:
                    break
            if len(nodos) >= 1 and any("siguiente" in n.campos or "next" in n.campos for n in nodos):
                # Nodo cabeza
                vals = [f"{list(n.campos.values())[0] if n.campos else ''}" for n in nodos]
                return NodoVisual(
                    id=nombre,
                    tipo="lista",
                    etiqueta=f"{nombre}:Lista({len(nodos)})",
                    valores=vals,
                    conexiones=[f"{nombre}_n{i}" for i in range(1, len(nodos))],
                )
        return None


class PilaStrategy(RenderStrategy):
    def execute(self, valor: Any, nombre: str, tipo: str, *args, **kwargs) -> Optional[NodoVisual]:
        if isinstance(valor, list) and "pila" in nombre.lower():
            return NodoVisual(id=nombre, tipo="pila", etiqueta=f"{nombre}:Pila", valores=list(reversed(valor)))
        return None


class VisualizerObserver(Observer):
    """Observer que se suscribe a Interpreter (Subject) vía debug_on_statement."""

    def __init__(self):
        self.history: List[SnapshotMemoria] = []
        self.strategies: List[RenderStrategy] = [ListaEnlazadaStrategy(), ArregloStrategy(), PilaStrategy()]

    def update(self, event: str, data: Any) -> None:
        if event == "snapshot":
            self.history.append(data)

    def visualizar_variables(self, variables: List[Dict[str, Any]], linea: int, pila: List[str]) -> SnapshotMemoria:
        snap = SnapshotMemoria(variables=variables, pila=pila, linea=linea)
        for v in variables:
            nombre = v.get("nombre", "")
            tipo = v.get("tipo", "")
            valor = v.get("valor")
            for strat in self.strategies:
                nodo = strat.execute(valor, nombre, tipo)
                if nodo:
                    nodo.linea = linea
                    snap.nodos.append(nodo)
                    break
            # fallback: variable escalar
            if not any(n.id == nombre for n in snap.nodos):
                snap.nodos.append(
                    NodoVisual(
                        id=nombre, tipo="scalar", etiqueta=f"{nombre}:{tipo}={valor!r}", valores=[valor], linea=linea
                    )
                )
        return snap

    def to_dot(self, snap: SnapshotMemoria) -> str:
        lines = ["digraph G { rankdir=LR; node [shape=record];"]
        for n in snap.nodos:
            if n.tipo == "arreglo":
                label = f"{n.etiqueta}|" + "|".join(f"<f{i}> {v!r}" for i, v in enumerate(n.valores))
                lines.append(f'  {n.id} [label="{label}"];')
            elif n.tipo == "lista":
                label = f"{n.etiqueta}|" + " -> ".join(str(v) for v in n.valores)
                lines.append(f'  {n.id} [shape=box label="{label}"];')
            else:
                lines.append(f'  {n.id} [label="{n.etiqueta}"];')
        lines.append("}")
        return "\n".join(lines)


# Integración con Interpreter hooks sin reescribir lógica
def attach_to_interpreter(interp) -> VisualizerObserver:
    obs = VisualizerObserver()
    orig = interp.debug_on_statement

    def wrapped(snap, pausar):
        # snap ya es dict de _snapshot_debug
        vis = obs.visualizar_variables(snap.get("variables", []), snap.get("linea", 0), snap.get("pila", []))
        obs.history.append(vis)
        interp.notify("snapshot", vis) if hasattr(interp, "notify") else None
        if orig:
            return orig(snap, pausar)
        return False

    interp.debug_on_statement = wrapped
    # asegúrate debug=True para que hook se llame
    return obs
