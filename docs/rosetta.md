# Rosetta InvenioLang — Aprender 7 lenguajes sin compilarlos

**Solo InvenioLang (`*.inv`) se compila y ejecuta** (`inveniolang/core:1` `compile_pure` + `interpreter.py:149`). El resto es **vista educativa read-only** vía `viewer/rosetta.py`. InvenioLang es puente para entender lógica, no reemplazo de toolchains.

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
Variables, constantes, **arreglos y matrices** (declaración, inicialización,
parámetro, acceso y asignación), asignación, `imprimir`, `leer`, `if`,
`while`, `for` (Pascal y Python lo desazucaran a `while`),
funciones/procedimientos, `return`/`break`/`continue`, llamadas y expresiones
se traducen de verdad. POO, `switch`/`try`/`foreach`/`match` y closures se
degradan a comentario.

Tipos (INV-4403): cada emisor conoce el tipo y las dimensiones de cada variable
visible y los usa donde el destino los exige.

| InvenioLang | C / C++ | Java | C# | Pascal | Python |
|---|---|---|---|---|---|
| parámetro `int[] a` | `int a[]` | `int[] a` | `int[] a` | `var a: array of integer` | `a` |
| parámetro `float[][] m` | `double m[][C]` (columnas de la matriz declarada) | `double[][] m` | `double[,] m` | `var m: TMatrizReal` | `m` |
| `int[3] a = {1,2,3};` | `int a[3] = {1, 2, 3};` | `int[] a = {1, 2, 3};` | `int[] a = {1, 2, 3};` | `a: array[0..3 - 1] of integer` | `a = [1, 2, 3]` |
| `m[i][j]` | `m[i][j]` | `m[i][j]` | `m[i, j]` | `m[i][j]` | `m[i][j]` |
| `const int N = 4;` (global) | `#define N 4` | `static final int N = 4;` | `const int N = 4;` | `const N = 4;` | `N = 4` |
| `imprimir(x)` (sin salto) | `printf("%d"/"%g"/"%s", x)` | `System.out.print(x)` | `Console.Write(x)` | `write(x)` | `print(x, end="")` |
| `leer(x)` | `scanf("%d", &x)` | `x = entrada.nextInt()` | `x = int.Parse(Console.ReadLine())` | `readln(x)` | `x = int(input())` |
| `a / b` enteros | `/` | `/` | `/` | `div` | `//` |

Los lógicos se imprimen `true`/`false` como en InvenioLang. Límite conocido:
`printf("%g")` escribe `4` donde InvenioLang escribe `4.0`. La prueba
`tests/cierre/test_rosetta_tipos.py` compila con gcc, g++ y javac (si están
instalados) y ejecuta también la vista Python: la salida debe ser la misma que
la de InvenioLang.

## Por qué no compilar otros
Compilar C/Java/C# exigiría `gcc`/`javac`/`dotnet` + `sandbox.py:7` por lenguaje + 6×391 tests. Para aprender, basta ver correspondencia + ejecutar InvenioLang. Desde la CLI: `python main.py --cli --ver-como java programa.inv`; desde código: `api.ver_como("java", codigo)`.


## Ver
`pruebas/conversor.inv` + `docs/manual_docente.md:1` para clase Rosetta.
