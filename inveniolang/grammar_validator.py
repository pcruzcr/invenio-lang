"""Verificación formal de la gramática LALR(1) real de ``parser.py``.

Uso: ``python -m inveniolang.grammar_validator`` (CI); sale con código 1 si
hay conflictos sin documentar o símbolos sin definir.

INV-1017: la versión anterior calculaba FIRST desde ``docs/gramatica.ebnf``
(no desde la gramática que usa el compilador), ``follow_sets`` devolvía
conjuntos vacíos (un bucle con ``pass``) y los "conflictos" se detectaban
buscando la palabra ``conflict`` en ``parsetab.py``. Ahora se reconstruye la
gramática exactamente como lo hace ``ply.yacc.yacc()`` a partir de las
producciones ``p_*`` del ``Parser`` y se obtienen de PLY los conjuntos FIRST y
FOLLOW reales y la tabla LALR(1) con sus conflictos shift/reduce y
reduce/reduce.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

from ply import yacc

from .lexer import Lexer
from .parser import Parser

__all__ = ["BASELINE_SHIFT_REDUCE", "InformeGramatica", "validar_gramatica"]


# Baseline documentado en docs/InvenioLang_GramaticaFormal.md §0 y §6
# (20 shift/reduce, 0 reduce/reduce; PLY los resuelve con "shift": dangling
# else, `;`/`)` opcionales tras sentencias, `++`/`--` postfijos y `{` de
# inicializadores). Por token, para que un conflicto NUEVO no quede oculto
# porque otro desapareció.
BASELINE_SHIFT_REDUCE: dict[str, int] = {
    "DEL_PUNTO_COMA": 7,
    "OP_INC": 3,
    "OP_DEC": 3,
    "KW_ELSE": 3,
    "DEL_PAREN_C": 2,
    "DEL_LLAVE_A": 2,
}


@dataclass
class InformeGramatica:
    """Resultado de :func:`validar_gramatica`."""

    producciones: int
    no_terminales: int
    terminales: int
    estados: int
    first: dict[str, list[str]]
    follow: dict[str, list[str]]
    shift_reduce: list[tuple[int, str, str]] = field(default_factory=list)
    reduce_reduce: list[tuple[int, str, str]] = field(default_factory=list)
    no_definidos: list[str] = field(default_factory=list)

    @property
    def inesperados(self) -> list[tuple[int, str, str]]:
        """Conflictos shift/reduce por encima del baseline documentado (por token)."""
        vistos: dict[str, int] = {}
        extra = []
        for conflicto in self.shift_reduce:
            vistos[conflicto[1]] = vistos.get(conflicto[1], 0) + 1
            if vistos[conflicto[1]] > BASELINE_SHIFT_REDUCE.get(conflicto[1], 0):
                extra.append(conflicto)
        return extra

    @property
    def ok(self) -> bool:
        """Gramática LALR(1) sin conflictos sorpresa ni símbolos sin definir."""
        return not (self.inesperados or self.reduce_reduce or self.no_definidos)

    def como_dict(self) -> dict[str, Any]:
        """Resumen serializable para CI."""
        return {
            "producciones": self.producciones,
            "no_terminales": self.no_terminales,
            "terminales": self.terminales,
            "estados_lalr": self.estados,
            "shift_reduce": len(self.shift_reduce),
            "shift_reduce_inesperados": [list(c) for c in self.inesperados],
            "reduce_reduce": len(self.reduce_reduce),
            "no_definidos": self.no_definidos,
            "estado": "OK" if self.ok else "REVISAR",
        }


def _gramatica() -> yacc.Grammar:
    """Construye ``ply.yacc.Grammar`` con los mismos pasos que ``yacc.yacc(module=...)``."""
    modulo = Parser(Lexer())
    pdict = {k: getattr(modulo, k) for k in dir(modulo)}
    info = yacc.ParserReflect(pdict, log=yacc.NullLogger())
    info.get_all()
    if info.error or info.validate_all():
        raise yacc.YaccError("la reflexión de PLY sobre Parser falló")
    gramatica = yacc.Grammar(info.tokens)
    for term, asociatividad, nivel in info.preclist:
        gramatica.set_precedence(term, asociatividad, nivel)
    for nombre_funcion, (archivo, linea, produccion, simbolos) in info.grammar:
        gramatica.add_production(produccion, simbolos, nombre_funcion, archivo, linea)
    gramatica.set_start(info.start)
    return gramatica


def validar_gramatica() -> InformeGramatica:
    """Calcula FIRST/FOLLOW y la tabla LALR(1) de la gramática del compilador."""
    g = _gramatica()
    no_definidos = sorted({sym for sym, _ in g.undefined_symbols()})
    g.build_lritems()
    first = g.compute_first()
    follow = g.compute_follow()
    tabla = yacc.LRGeneratedTable(g, "LALR", yacc.NullLogger())
    no_terminales = sorted(g.Nonterminals)
    return InformeGramatica(
        producciones=len(g.Productions) - 1,  # la 0 es S' -> inicio
        no_terminales=len(no_terminales),
        terminales=len(g.Terminals),
        estados=len(tabla.lr_action),
        first={nt: sorted(first[nt]) for nt in no_terminales},
        follow={nt: sorted(follow.get(nt, [])) for nt in no_terminales},
        shift_reduce=list(tabla.sr_conflicts),
        reduce_reduce=list(tabla.rr_conflicts),
        no_definidos=no_definidos,
    )


def main() -> int:
    """CLI: imprime el resumen JSON y devuelve 1 si la gramática no es LALR(1) limpia."""
    informe = validar_gramatica()
    sys.stdout.write(json.dumps(informe.como_dict(), indent=2, ensure_ascii=False) + "\n")
    return 0 if informe.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
