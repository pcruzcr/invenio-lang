# cfg.py — Sprint 1 IR: CFG/SSA (Control Flow Graph)
# Patrones: Builder + Visitor + Strategy
from __future__ import annotations

from dataclasses import dataclass, field

from .ast_nodes import (
    Any,
    ASTNode,
    Bloque,
    IfStmt,
    WhileStmt,
)
from .patterns import Visitor


@dataclass
class BloqueCFG:
    """Bloque básico del CFG."""

    id: str
    instrs: list[str] = field(default_factory=list)
    sucesores: list[str] = field(default_factory=list)
    predecesores: list[str] = field(default_factory=list)


class CFGBuilder(Visitor):
    """Visitor que construye CFG desde Bloque AST. Cada bloque if/while/for genera nodos."""

    def __init__(self):
        self.bloques: dict[str, BloqueCFG] = {}
        self._next = 0
        self._cur = self._new_block("entry")

    def _new_block(self, prefix: str) -> BloqueCFG:
        bid = f"{prefix}_{self._next}"
        self._next += 1
        b = BloqueCFG(id=bid)
        self.bloques[bid] = b
        return b

    def visit_Bloque(self, node: Bloque) -> Any:
        """Visita un nodo Bloque del AST."""
        for elem in node.elementos:
            self.visit(elem)
        return self.bloques

    def visit_IfStmt(self, node: IfStmt) -> Any:
        """Visita un nodo IfStmt del AST."""
        cond = self._cur
        cond.instrs.append(f"if {node.condicion}")
        then_b = self._new_block("then")
        else_b = self._new_block("else") if node.bloque_else else None
        merge = self._new_block("merge")
        cond.sucesores = [then_b.id, else_b.id if else_b else merge.id]
        self._cur = then_b
        self.visit(node.bloque_then)
        then_b.sucesores.append(merge.id)
        if else_b:
            self._cur = else_b
            self.visit(node.bloque_else)
            else_b.sucesores.append(merge.id)
        self._cur = merge
        return merge

    def visit_WhileStmt(self, node: WhileStmt) -> Any:
        """Visita un nodo WhileStmt del AST."""
        cond = self._new_block("while_cond")
        self._cur.sucesores.append(cond.id)
        body = self._new_block("while_body")
        exit_b = self._new_block("while_exit")
        cond.instrs.append(f"while {node.condicion}")
        cond.sucesores = [body.id, exit_b.id]
        self._cur = body
        self.visit(node.bloque)
        body.sucesores.append(cond.id)
        self._cur = exit_b
        return exit_b

    def visit_SwitchStmt(self, node) -> Any:
        """Visita un nodo SwitchStmt del AST."""
        cond = self._cur
        cond.instrs.append(f"switch {node.expr}")
        merge = self._new_block("switch_merge")
        for caso in node.casos:
            case_b = self._new_block("case")
            cond.sucesores.append(case_b.id)
            self._cur = case_b
            self.visit(caso.bloque)
            case_b.sucesores.append(merge.id)
        if node.bloque_default:
            def_b = self._new_block("default")
            cond.sucesores.append(def_b.id)
            self._cur = def_b
            self.visit(node.bloque_default)
            def_b.sucesores.append(merge.id)
        # fallthrough modelado como merge; si no hay default, cond->merge directo
        if not node.casos and not node.bloque_default:
            cond.sucesores.append(merge.id)
        self._cur = merge
        return merge

    def visit_TryStmt(self, node) -> Any:
        """Visita un nodo TryStmt del AST."""
        try_b = self._new_block("try")
        catch_b = self._new_block("catch")
        merge = self._new_block("try_merge")
        self._cur.sucesores.append(try_b.id)
        try_b.sucesores = [merge.id, catch_b.id]  # normal vs excepción
        self._cur = try_b
        self.visit(node.bloque_try)
        try_b.sucesores[0] = merge.id
        self._cur = catch_b
        self.visit(node.bloque_catch)
        catch_b.sucesores.append(merge.id)
        self._cur = merge
        return merge

    def visit_ForStmt(self, node) -> Any:
        """Visita un nodo ForStmt del AST."""
        init_b = self._new_block("for_init")
        cond = self._new_block("for_cond")
        body = self._new_block("for_body")
        exit_b = self._new_block("for_exit")
        self._cur.sucesores.append(init_b.id)
        init_b.sucesores = [cond.id]
        cond.instrs.append(f"for {node.cond_expr}")
        cond.sucesores = [body.id, exit_b.id]
        self._cur = body
        self.visit(node.bloque)
        body.sucesores.append(cond.id)
        self._cur = exit_b
        return exit_b

    def generic_visit(self, node: Any) -> Any:
        """Visita genérica por introspección."""
        # leaf instr
        self._cur.instrs.append(type(node).__name__)
        # recurse generico cubre try/catch/switch ya manejados arriba, pero fallback para resto
        for attr in (
            "bloque",
            "bloque_then",
            "bloque_else",
            "bloque_try",
            "bloque_catch",
            "bloque_default",
            "casos",
            "elementos",
            "subrutinas",
            "main",
            "declaraciones_globales",
            "declaraciones_posteriores",
        ):
            val = getattr(node, attr, None)
            if isinstance(val, list):
                for item in val:
                    if hasattr(item, "accept"):
                        item.accept(self)
                    elif isinstance(item, ASTNode):
                        self.visit(item)
            elif isinstance(val, ASTNode):
                val.accept(self)
        return self._cur


def build_cfg(bloque: Bloque) -> dict[str, BloqueCFG]:
    """Construye el grafo de flujo del bloque."""
    b = CFGBuilder()
    b.visit(bloque)
    # calcular predecesores
    for bid, blk in b.bloques.items():
        for succ in blk.sucesores:
            if succ in b.bloques:
                b.bloques[succ].predecesores.append(bid)
    return b.bloques


def to_dot(cfg: dict[str, BloqueCFG]) -> str:
    """Serializa el CFG a Graphviz DOT."""
    lines = ["digraph CFG {"]
    for bid, blk in cfg.items():
        label = f"{bid}\\n" + "\\n".join(blk.instrs[:3])
        lines.append(f'  {bid} [label="{label}", shape=box];')
        for s in blk.sucesores:
            lines.append(f"  {bid} -> {s};")
    lines.append("}")
    return "\n".join(lines)
