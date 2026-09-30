# Rosetta InvenioLang — Aprender 7 lenguajes sin compilarlos

**Solo InvenioLang (`*.inv`) se compila y ejecuta** (`inveniolang/core:1` `compile_pure` + `interpreter.py:149`). El resto es **vista educativa read-only** vía `viewer/rosetta.py` (no `backend/wasm.py` que es demo). InvenioLang es puente para entender lógica, no reemplazo de toolchains.

## Tabla comparativa (concepto → sintaxis)

| Concepto InvenioLang | C | C++ | Python | Java | C# (.NET) | Pascal |
|----------------------|---|-----|--------|------|-----------|--------|
| `int x=5;` | `int x=5;` | `int x=5;` | `x=5` | `int x=5;` | `int x=5;` | `x: integer := 5;` |
| `si (x>0) { }` | `if (x>0) {}` | `if (x>0) {}` | `if x>0:` | `if (x>0) {}` | `if (x>0) {}` | `if x>0 then begin end;` |
| `mientras (c) {}` | `while(c){}` | `while(c){}` | `while c:` | `while(c){}` | `while(c){}` | `while c do begin end;` |
| `para(int i=0;i<n;i++)` | `for(int i=0;i<n;i++)` | `for(int i=0;i<n;i++)` | `for i in range(n):` | `for(int i=0;i<n;i++)` | `for(int i=0;i<n;i++)` | `for i:=0 to n-1 do` |
| `clase A hereda B` | `struct A: B` | `class A: public B` | `class A(B):` | `class A extends B` | `class A : B` | `type A = class(B)` |
| `imprimir(x)` | `printf` | `cout<<` | `print(x)` | `System.out.print` | `Console.Write` | `writeln(x)` |

## Uso viewer (no compila)
```python
from inveniolang.viewer.rosetta import transpile
code = open("pruebas/hola_mundo.inv").read()
print(transpile("python", code))  # vista
print(transpile("java", code))    # vista
# Ejecución real solo:
from inveniolang.core import CompileRequest, compile_pure
compile_pure(CompileRequest(ruta="hola.inv", codigo=code, modo="run"))
```

## Fidelidad del viewer (subconjunto estructurado)
Variables, asignación, `imprimir`, `if`, `while`, `for` (Pascal desazucarado a
`while`), funciones/procedimientos, `return`/`break`/`continue`, llamadas y
expresiones se traducen de verdad (`tests/test_rosetta.py:1`). POO, arreglos,
`switch`/`try`/`foreach`/`match` se degradan a comentario. C elige
`printf` `%s/%d/%g` por literal; resto es vista, no toolchain.

## Por qué no compilar otros
Compilar C/Java/C# exigiría `gcc`/`javac`/`dotnet` + `sandbox.py:7` por lenguaje + 6×391 tests. Para aprender, basta ver correspondencia + ejecutar InvenioLang. Ver `studio/allinone.py:1` `StudioFacade` (`ver_como`).

## Demo WASM (no estable)
`backend/wasm.py:1` genera `wat`/`riscv` solo como demo didáctico (`tac_to_wat`), no en `pruebas/conformidad.py`. Estable es `interpreter.py`.

## Ver
`pruebas/conversor.inv` + `docs/manual_docente.md:1` para clase Rosetta.
