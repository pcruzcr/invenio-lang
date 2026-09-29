# backend/wasm.py — v9 WASM backend DEMO (no pipeline estable) — solo InvenioLang se ejecuta vía interpreter.py
# Para aprender, ver viewer/rosetta.py. Este backend es demo didáctico, no producción.
from __future__ import annotations
from typing import List
from ..ir import Instr

_WAT_BINOP = {
    "+": "i32.add",
    "-": "i32.sub",
    "*": "i32.mul",
    "/": "i32.div_s",
    "%": "i32.rem_s",
    "==": "i32.eq",
    "!=": "i32.ne",
    "<": "i32.lt_s",
    ">": "i32.gt_s",
    "<=": "i32.le_s",
    ">=": "i32.ge_s",
    "&&": "i32.and",
    "||": "i32.or",
    "&": "i32.and",
    "|": "i32.or",
    "^": "i32.xor",
    "<<": "i32.shl",
    ">>": "i32.shr_s",
}
_RV_BINOP = {
    "+": "add",
    "-": "sub",
    "*": "mul",
    "/": "div",
    "%": "rem",
    "==": "seqz",
    "!=": "snez",
    "<": "slt",
    ">": "sgt",
}


def tac_to_wat(instrs: List[Instr]) -> str:
    lines = ["(module", '  (import "env" "print" (func $print (param i32)))', "  (func $main (result i32)"]
    for ins in instrs:
        op = ins.op
        if op == "const":
            if isinstance(ins.arg1, int):
                lines.append(f"    i32.const {ins.arg1}  ;; {ins.resultado}")
            elif isinstance(ins.arg1, float):
                lines.append(f"    f64.const {ins.arg1}  ;; {ins.resultado}")
            elif isinstance(ins.arg1, str):
                lines.append(f"    ;; const string {ins.arg1!r} -> {ins.resultado}")
            else:
                lines.append(f"    i32.const 0  ;; {ins.resultado} bool/null")
        elif op in _WAT_BINOP:
            lines.append(f"    {_WAT_BINOP[op]}  ;; {ins.resultado} = {ins.arg1} {op} {ins.arg2}")
        elif op == "neg":
            lines.append(f"    i32.const 0\n    i32.sub  ;; neg {ins.resultado}")
        elif op == "not":
            lines.append(f"    i32.eqz  ;; not {ins.resultado}")
        elif op == "copy":
            lines.append(f"    local.get ${ins.arg1}\n    local.set ${ins.resultado}  ;; copy")
        elif op == "label":
            lines.append(f"  {ins.arg1}:  ;; label")
        elif op == "goto":
            lines.append(f"    br {ins.arg1}")
        elif op == "if_false":
            lines.append(f"    br_if {ins.arg2}  ;; if_false {ins.arg1}")
        elif op == "call":
            lines.append(f"    call ${ins.arg1}  ;; {ins.resultado} = call")
        elif op == "return":
            if ins.arg1:
                lines.append(f"    local.get ${ins.arg1}\n    return")
            else:
                lines.append("    return")
        elif op == "print":
            lines.append(f"    local.get ${ins.arg1}\n    call $print")
        elif op in ("array_new", "array_get", "array_set"):
            lines.append(f"    ;; {op} {ins.arg1} (mem op)")
        elif op in ("try_begin", "try_end", "pop_manejador"):
            lines.append(f"    ;; {op} (exception)")
        else:
            lines.append(f"    ;; unhandled {op}")
    lines += ["    i32.const 0", "  )", '  (export "main" (func $main))', '  (export "_start" (func $main))', ")"]
    return "\n".join(lines)


def tac_to_riscv(instrs: List[Instr]) -> str:
    lines = [".text", ".globl main", "main:", "  addi sp, sp, -128  # frame"]
    reg_map = {}
    next_reg = 0

    def reg(name):
        nonlocal next_reg
        if name not in reg_map:
            r = f"t{next_reg%7}" if next_reg < 7 else f"s{next_reg-7}"
            reg_map[name] = r
            next_reg += 1
        return reg_map[name]

    for ins in instrs:
        op = ins.op
        if op == "const":
            if isinstance(ins.arg1, int):
                lines.append(f"  li {reg(ins.resultado)}, {ins.arg1}")
            elif isinstance(ins.arg1, float):
                lines.append(f"  li {reg(ins.resultado)}, {int(ins.arg1)}  # float truncated")
        elif op in _RV_BINOP:
            lines.append(f"  {_RV_BINOP[op]} {reg(ins.resultado)}, {reg(ins.arg1)}, {reg(ins.arg2)}")
        elif op == "copy":
            lines.append(f"  mv {reg(ins.resultado)}, {reg(ins.arg1)}")
        elif op == "label":
            lines.append(f"{ins.arg1}:")
        elif op == "goto":
            lines.append(f"  j {ins.arg1}")
        elif op == "if_false":
            lines.append(f"  beqz {reg(ins.arg1)}, {ins.arg2}")
        elif op == "call":
            lines.append(f"  call {ins.arg1}  # {ins.resultado}")
        elif op == "return":
            if ins.arg1:
                lines.append(f"  mv a0, {reg(ins.arg1)}")
            lines.append("  ret")
        elif op == "print":
            lines.append(f"  mv a0, {reg(ins.arg1)}; call print")
        else:
            lines.append(f"  # {op} {ins.arg1} {ins.arg2} -> {ins.resultado}")
    lines.append("  li a0, 0; ret")
    return "\n".join(lines)
