# InvenioLang 1.0 - Compilador Educativo

**Curso:** TIIT2002.2 Lenguajes Formales II  
**Universidad:** Invenio - Tecnologias de Informacion y Comunicacion Empresarial (TICEC)  
**Profesor:** Donny Nunez del Rosario  
**Sede:** Los Angeles de Tilaran  

## Descripcion

InvenioLang es un lenguaje de programacion educativo disenado para la construccion incremental de un compilador completo. Este proyecto implementa un compilador e interprete para InvenioLang 1.0, cubriendo:

- Analisis lexico (lexer)
- Analisis sintactico (parser) con construccion de AST
- Analisis semantico y tabla de simbolos
- Verificacion de tipos
- Interpretacion mediante recorrido de arbol

## Requisitos

- Python 3.10 o superior
- PLY 3.11+ (`pip install ply`)

## Instalacion

```bash
pip install -r requirements.txt
```

## Estructura del Proyecto

```
proyecto_inveniolang/
├── inveniolang/            # Paquete principal del compilador
│   ├── __init__.py
│   ├── ast_nodes.py        # Definicion de nodos del AST
│   ├── builtins.py         # Funciones integradas de conversion
│   ├── cli.py              # Interfaz de linea de comandos
│   ├── docstrings.py       # Textos de ayuda del catalogo de errores
│   ├── errors.py           # Gestion de errores (catalogo oficial)
│   ├── gui.py              # Interfaz grafica alternativa (Tkinter)
│   ├── gui_qt.py           # Interfaz grafica principal (PySide6 / Qt)
│   ├── interpreter.py      # Interprete de arbol
│   ├── lexer.py            # Analizador lexico (PLY)
│   ├── parser.py           # Analizador sintactico (PLY)
│   ├── semantic.py         # Analisis semantico
│   ├── symbol_table.py     # Tabla de simbolos con ambitos
│   └── type_checker.py     # Verificador de tipos
├── pruebas/                # Programas de prueba y suite de conformidad
│   ├── conformidad.py      # Suite de regresion (167 casos, Sec. 18.1)
│   ├── hola_mundo.inv      # Programas de referencia de la Seccion 17
│   ├── tipos.inv
│   ├── condicionales.inv
│   ├── ciclos.inv
│   ├── funciones.inv
│   ├── procedimientos.inv
│   ├── arreglos.inv
│   ├── matrices.inv
│   ├── sistema_ventas.inv
│   ├── escapes.inv         # Programas del Apendice E
│   ├── calculadora_es.inv
│   ├── guardia.inv
│   ├── hanoi.inv
│   ├── calculadora.inv     # Programa original #1
│   ├── estadisticas.inv    # Programa original #2
│   └── conversor.inv       # Programa original #3
├── docs/                   # Especificacion del lenguaje
│   ├── InvenioLang_Seccion*.docx
│   └── ERRATAS.md          # Fe de erratas de la especificacion
├── test_lexer_errors.py    # Pruebas de deteccion de errores lexicos
├── _audit.py               # Auditoria general del proyecto
├── main.py                 # Punto de entrada principal
├── requirements.txt
└── README.md
```

## Pruebas

```bash
# Suite de conformidad con la especificacion (167 casos)
python pruebas/conformidad.py

# Solo un grupo: catalogo | expresiones | ejecucion | referencia
python pruebas/conformidad.py catalogo

# Deteccion de errores lexicos (28 casos)
python test_lexer_errors.py

# Auditoria general del proyecto
python _audit.py
```

La Seccion 18.1 declara que los codigos del catalogo son estables entre
versiones y que los programas de referencia de la Seccion 17 son casos de prueba
permanentes: `pruebas/conformidad.py` es la red que hace cumplir ambas
garantias y debe pasar al 100 % antes de cualquier cambio.

## Uso

### Linea de Comandos (CLI)

```bash
# Ejecutar un programa
python main.py pruebas/hola_mundo.inv

# Ejecutar con entrada simulada
python main.py pruebas/mi_programa.inv entrada1 entrada2

# Mostrar tokens (analisis lexico)
python main.py --tokens pruebas/hola_mundo.inv

# Mostrar AST
python main.py --ast pruebas/hola_mundo.inv

# Revisar el codigo sin ejecutarlo (analisis estatico completo: lexico, sintactico, semantico y tipos)
python main.py --check pruebas/hola_mundo.inv

# Traza de ejecucion paso a paso (linea, variables y pila de llamadas)
python main.py --step pruebas/ciclos.inv
python main.py --step --maxpasos 20 pruebas/ciclos.inv   # limitar a N pasos

# Ayuda
python main.py --help
```

### Interfaz Grafica (GUI)

```bash
python main.py --gui            # GUI por defecto (PySide6 / Qt)
python main.py --gui-tk         # GUI alternativa (Tkinter)
```

La GUI (PySide6) es una pequeña **IDE** que permite:
- Crear, abrir y guardar archivos `.inv`
- Ejecutar el pipeline completo del compilador
- Visualizar salida, errores y advertencias en pestanas separadas
- Ver el analisis de tokens y el AST
- **Analisis en vivo**: subrayado **ondulado rojo** (errores) y punteado ambar (advertencias) mientras escribes, con conteo en la barra de estado
- **Navegacion de errores**: clic en un error salta a la linea, `F8`/`Shift+F8` recorren errores, `Ctrl+G` ir a linea
- **Menu Ayuda (F1)**: guia rapida, referencia del lenguaje, funciones integradas, catalogo de errores, atajos y ejemplos cargables
- Resaltado sintactico, numeracion de lineas y linea activa

## Caracteristicas del Lenguaje

### Tipos de Datos
| Tipo | Ingles | Espanol | Descripcion |
|------|--------|---------|-------------|
| Entero | `int` | `entero` | 32 bits con signo |
| Real | `float` | `real` | IEEE 754 doble precision |
| Texto | `string` | `texto` | Unicode |
| Logico | `bool` | `logico` | true/false, verdadero/falso |
| Vacio | `void` | `vacio` | Sin valor |

### Palabras Reservadas Bilingues
InvenioLang soporta palabras reservadas en ingles y espanol:

- `if` / `si`, `else` / `sino`
- `while` / `mientras`, `for` / `para`
- `print` / `imprimir`, `read` / `leer`
- `int` / `entero`, `float` / `real`, `string` / `texto`, `bool` / `logico`
- `void` / `vacio`, `const` / `constante`
- `break` / `romper`, `continue` / `continuar`
- `return` / `retornar`, `true` / `verdadero`, `false` / `falso`

Las 19 parejas cubren todas las instrucciones del lenguaje, de modo que un
programa puede escribirse integramente en cualquiera de los dos idiomas.

### Estructuras de Control
- Condicionales: `if`/`si`-`else`/`sino` (anidados)
- Ciclos: `while`/`mientras`, `for`/`para`
- Control de ciclo: `break`/`romper`, `continue`/`continuar`

### Funciones y Procedimientos
- Funciones con retorno de cualquier tipo
- Procedimientos (tipo void)
- Parametros por valor (arreglos por referencia)
- Recursion
- Funciones integradas de conversion

### Arreglos y Matrices
- Arreglos unidimensionales: `int[tam] nombre` (forma canonica)
- Matrices bidimensionales: `int[filas][cols] nombre`
- Acceso por indice: `arr[i]`, `mat[i][j]` (desde 0, con verificacion de limites)
- La forma postfija `int nombre[tam];` se acepta con la advertencia `IL-WARN-040`
- No se puede copiar un arreglo completo con `=` (`IL-SIN-070`)
- Una matriz requiere siempre dos indices (`IL-SIN-080`)

### Funciones Integradas

Las ocho funciones de conversion aceptan tres nomenclaturas equivalentes: la
abreviada usada en la Seccion 4 y el Apendice E, y las formas normativas en
ingles y espanol de la Seccion 19. Los 24 nombres son intercambiables.

| Abreviado (Sec. 4) | Ingles (Sec. 19) | Espanol (Sec. 19) | Descripcion |
|--------------------|------------------|-------------------|-------------|
| `int_a_float(n)`   | `int_to_float`   | `entero_a_real`   | Entero a real |
| `float_a_int(f)`   | `float_to_int`   | `real_a_entero`   | Real a entero (trunca hacia cero) |
| `int_a_texto(n)`   | `int_to_string`  | `entero_a_texto`  | Entero a texto |
| `float_a_texto(f)` | `float_to_string`| `real_a_texto`    | Real a texto |
| `texto_a_int(s)`   | `string_to_int`  | `texto_a_entero`  | Texto a entero |
| `texto_a_float(s)` | `string_to_float`| `texto_a_real`    | Texto a real |
| `bool_a_texto(b)`  | `bool_to_string` | `logico_a_texto`  | Logico a texto |
| `texto_a_bool(s)`  | `string_to_bool` | `texto_a_logico`  | Texto a logico |

Los nombres de las funciones integradas estan reservados en todo ambito y no
pueden usarse como identificadores (`IL-SEM-080`).

### Palabras Reservadas sin Uso en la Version 1.0

`function` / `funcion` y `procedure` / `procedimiento` figuran como reservadas
en el Apendice A pero no participan en ninguna produccion de la gramatica 1.0.
Usarlas como identificador produce `IL-LEX-006`.

### Fe de Erratas de la Especificacion

La especificacion contiene diez contradicciones internas, resueltas y
documentadas en [`docs/ERRATAS.md`](docs/ERRATAS.md). Las tres con efecto sobre
el lenguaje aceptado:

- **`retornar` SI es palabra reservada** (equivalente de `return`), de modo que
  el bilinguismo es completo y el programa del Apendice E.3 compila.
- **Se aceptan las dos formas de declarar arreglos**: la prefija `int [5] arr;`
  es canonica y la postfija `int arr[5];` emite la advertencia `IL-WARN-040`.
  Asi compilan los diecisiete programas de referencia tal como estan impresos.
- **La division real entre cero produce `IL-EJE-002`** y la entera `IL-EJE-006`,
  en lugar de usar el mismo codigo para ambas.

### Limites de Ejecucion

Para garantizar un entorno seguro de aprendizaje, el interprete impone limites
que producen errores del catalogo en lugar de colgar el proceso:

| Limite | Valor por defecto | Error |
|--------|-------------------|-------|
| Iteraciones por ciclo | 1 000 000 | `IL-EJE-030` |
| Profundidad de recursion | 500 llamadas | `IL-EJE-040` |
| Rango del tipo `int` | 32 bits con signo | `IL-EJE-001` |

El limite de iteraciones es configurable con `Interpreter.max_iteraciones`
(`None` lo desactiva).

## Pipeline del Compilador

```
Archivo .inv  -->  Lexer  -->  Parser  -->  AST  -->  Semantico  -->  Type Checker  -->  Interprete  -->  Salida
                     |             |              |             |                |               |
               Errores         Errores        Errores       Errores         Errores        Errores
               lexicos       sintacticos    semanticos      de tipos       de ejecucion
```

## Referencias

- Aho, A. et al. "Compilers: Principles, Techniques, and Tools" (2da ed.)
- Cooper, K. & Torczon, L. "Engineering a Compiler" (3ra ed.)
- Nystrom, R. "Crafting Interpreters"
- Documentacion oficial de PLY: https://www.dabeaz.com/ply/
