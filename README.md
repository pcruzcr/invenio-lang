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
- PLY 3.11+ (`pip install ply`) — analizador lexico/sintactico
- PySide6 6.6+ (`pip install PySide6`) — GUI principal (Qt); trae consigo
  `shiboken6`, `PySide6_Essentials` y `PySide6_Addons` como dependencias
  propias, no hace falta instalarlas por separado
- Tkinter (incluido en la instalacion estandar de Python, no se instala con
  pip) — GUI de respaldo si PySide6 no esta disponible (`python main.py
  --gui-tk`); solo el modo `--cli`/linea de comandos no requiere ninguna
  libreria grafica

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
│   ├── conformidad.py      # Suite de regresion (273: 175 v1.0 + 32 POO/2.0 + 7 estructuras + 20 Etapa 6 + 15 Etapa 7 + 9 Etapa 8 + 15 Etapa 10)
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
# Suite de conformidad con la especificacion (311 casos)
python pruebas/conformidad.py

# Solo un grupo: catalogo | expresiones | ejecucion | codificacion
# | referencia | clases | estructuras | estructurado | poo_completo
# | etapa10 | etapa11
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

# Codigo intermedio (TAC): ver "Pipeline del Compilador" mas abajo
python main.py --ir pruebas/ciclos.inv
python main.py --ir-opt pruebas/ciclos.inv
python main.py --run-ir pruebas/ciclos.inv

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

Estas 17 parejas cubren las instrucciones de InvenioLang 1.0, de modo que un
programa puede escribirse integramente en cualquiera de los dos idiomas.
Las Etapas 2, 6, 7, 10, 11 y 12 (InvenioLang 2.0) agregan 21 parejas mas
para clases, control avanzado, excepciones, funciones de primera clase y
tipos suma (`class`/`clase`, `switch`/`segun`, `try`/`intentar`,
`enum`/`enumeracion`, `funcion`/`function`, `emparejar`/`match`, ...) — 38
parejas bilingues en total, mas dos palabras sin alias (`main`,
`constructor`, identicas en ambos idiomas) y una con tres formas
(`abstract`/`abstracta`/`abstracto`): 41 palabras reservadas distintas, 81
formas lexicas. Ver
[`docs/InvenioLang_2.0_POO.md`](docs/InvenioLang_2.0_POO.md) para el
catalogo completo de palabras reservadas nuevas.

### Estructuras de Control
- Condicionales: `if`/`si`-`else`/`sino` (anidados), operador ternario `?:`
- Ciclos: `while`/`mientras`, `for`/`para`, `do`/`hacer`-`while`/`mientras`
- Seleccion multiple: `switch`/`segun`-`case`/`caso`-`default`/`por_defecto`
- Control de ciclo: `break`/`romper` (tambien valido en `switch`), `continue`/`continuar`
- Manejo de excepciones: `try`/`intentar`-`catch`/`capturar` (ver Etapa 6 mas abajo)

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

## Etapa 6 — Lenguaje Estructurado Completo

Extension aditiva sobre la v1.0 (no toca nada existente) documentada en
[`docs/InvenioLang_Etapa6_Estructurado.md`](docs/InvenioLang_Etapa6_Estructurado.md):

- **`switch`/`segun`**: con `case`/`caso` y `default`/`por_defecto`,
  semantica de caida (fallthrough) igual que C -- `break`/`romper` corta la
  caida (y ahora tambien es valido dentro de un switch, no solo de un ciclo).
- **`do`/`hacer` ... `while`/`mientras`**: el cuerpo se ejecuta siempre al
  menos una vez.
- **Operador ternario** `cond ? si : no`: asociativo a la derecha, con
  cortocircuito real (la rama descartada nunca se evalua).
- **`try`/`catch` generico** (`try`/`intentar` ... `catch`/`capturar`):
  captura cualquier error de ejecucion del catalogo (`IL-EJE-*`); la
  variable del catch expone `.codigo` y `.mensaje`. Sin clases de excepcion
  definidas por el usuario (alcance deliberado).
- **Libreria estandar ampliada** (`inveniolang/builtins.py`): funciones de
  cadenas (`longitud_texto`, `subcadena`, `mayusculas`, `minusculas`,
  `caracter_en`, `indice_de`, `recortar`) y de matematica (`raiz_cuadrada`,
  `elevar`, `absoluto`, `piso`, `techo`, `azar`), con alias en ingles.
- Catalogo de errores nuevo `IL-EST-NNN` (validacion de `switch`/ternario y
  errores de la libreria estandar) -- ver la tabla completa en el documento
  de la etapa.
- El backend de codigo intermedio (`--ir`/`--ir-opt`/`--run-ir`) cubre las
  cuatro construcciones nuevas, `try`/`catch` incluido.

Programa de referencia: [`pruebas/estructurado.inv`](pruebas/estructurado.inv).

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

## InvenioLang 2.0 — Programacion Orientada a Objetos (POO)

La especificacion de la v1.0 declara la POO **excluida permanentemente**
(§1.3, §18.3.3: "InvenioLang es y seguira siendo un lenguaje de programacion
estructurada"). InvenioLang 2.0 revierte esa decision de forma deliberada y
documentada, con el mismo rigor que la v1.0: especificacion formal propia
([`docs/InvenioLang_2.0_POO.md`](docs/InvenioLang_2.0_POO.md)), catalogo de
errores dedicado (`IL-POO-NNN`, no se reutilizan ni renumeran los 92 codigos
de la v1.0) y sus propios grupos de conformidad (`pruebas/conformidad.py
clases`, 25 casos de la POO basica, mas `poo_completo` con las 4
caracteristicas de la Etapa 7 -- ver mas abajo).

### Palabras Reservadas Nuevas

| Concepto | Ingles | Espanol |
|---|---|---|
| Declarar clase | `class` | `clase` |
| Herencia | `extends` | `hereda` |
| Instanciar | `new` | `nuevo` |
| Instancia actual | `this` | `este` |
| Superclase | `super` | `padre` |
| Visibilidad publica | `public` | `publico` |
| Visibilidad privada | `private` | `privado` |

### Caracteristicas

- Clases con atributos y metodos (`publico`/`privado`), constructor (mismo
  nombre que la clase, sin tipo de retorno), y herencia simple
  (`hereda`/`extends`, un solo padre).
- **Polimorfismo real**: toda llamada a metodo se resuelve por la clase
  dinamica del objeto (despacho virtual), no por el tipo estatico de la
  variable. `padre.metodo(...)` invoca explicitamente la version del padre.
- Un nombre de clase es un tipo valido en cualquier lugar donde antes solo
  cabia `int`/`float`/`string`/`bool`: variables, parametros, atributos
  (composicion) y retorno de metodo. Asignar una subclase a una variable de
  un tipo ancestro (upcasting) es valido; lo contrario no.
- **Limitacion deliberada**: el acceso a miembro es de un solo nivel
  (`receptor.miembro`, sin encadenar `a.b.c()`) para no generalizar la
  gramatica de expresiones a una cadena postfija recursiva. Se resuelve con
  una variable intermedia (`Motor m = this.motor; m.hp();`).
- **Fuera de alcance** (candidatos a un incremento futuro): sobrecarga de
  operadores, excepciones definidas por el usuario (hay manejo de
  excepciones *generico*, ver la seccion Etapa 6 mas abajo). Miembros
  estaticos, clases abstractas y sobrecarga de metodos sí se agregaron —
  ver "Etapa 7" mas abajo; los arreglos de objetos tambien — ver
  "Estructuras de Datos".

### Ejemplo

```
clase Animal {
    privado texto nombre;
    Animal(texto n) { this.nombre = n; }
    publico texto sonido() { return "..."; }
}
clase Perro hereda Animal {
    Perro(texto n) { super(n); }
    publico texto sonido() { return "Guau"; }
}
void main() {
    Animal a = nuevo Perro("Rex");
    imprimir(a.sonido());   // "Guau" -- despacho virtual, no "..."
}
```

## Etapa 7 — POO Completo

Cuatro caracteristicas mas, documentadas en detalle en
[`docs/InvenioLang_2.0_POO.md`](docs/InvenioLang_2.0_POO.md#9-etapa-7--poo-completo)
(seccion 9):

- **Clases y metodos abstractos** (`abstracta clase`/`abstract class`,
  metodo `abstracto`/`abstract` sin cuerpo): no instanciables, una
  subclase concreta debe implementar todo metodo abstracto heredado. No
  hay una palabra `interfaz` separada -- una clase 100% abstracta ya
  cumple ese rol.
- **Miembros estaticos** (`estatico`/`static`): atributos y metodos de
  *clase*, no de instancia -- una sola copia compartida, accesible como
  `NombreClase.miembro` (o, de forma permisiva, tambien via una
  instancia).
- **Sobrecarga de metodos**: mismo nombre, distinta aridad o tipos de
  parametros dentro de la misma clase. Convive con el despacho virtual
  (polimorfismo) ya existente: la sobrecarga se resuelve por firma en
  tiempo de compilacion, la sobrescritura por la clase real del objeto en
  tiempo de ejecucion.
- **Genericos** (`clase Caja<T> { ... }`, `Caja<entero> c = nuevo
  Caja<entero>();`): sustitucion sintactica en tiempo de compilacion (al
  estilo de un template de C++), no un sistema de tipos genericos con
  inferencia. Alcance acotado: un solo parametro de tipo, sin genericos
  anidados/auto-referenciados ni combinados con herencia -- documentado en
  detalle en la spec.

Catalogo de errores nuevo: `IL-POO-020` a `IL-POO-027`. Programa de
referencia combinando las 4 caracteristicas:
[`pruebas/poo_completo.inv`](pruebas/poo_completo.inv).

## Etapa 8 — Mas Estructuras de Datos y Algoritmos

Documentada en detalle en
[`docs/InvenioLang_Etapa8_Estructuras.md`](docs/InvenioLang_Etapa8_Estructuras.md).
A diferencia de las Etapas 6 y 7, **no toca el lenguaje** — son 9 programas
de referencia nuevos en `pruebas/` (implementados en InvenioLang, no como
tipos nativos) que cierran los huecos de grafos, tablas hash y algoritmos
de ordenamiento/busqueda:

| Sin objetos (arreglos) | Con objetos (clases) |
|---|---|
| `tabla_hash_arreglo.inv` (sondeo lineal) | `tabla_hash_encadenada.inv` |
| `grafo_matriz.inv` (BFS/DFS) | `grafo_lista_adyacencia.inv` (BFS/DFS) |
| `ordenamiento_insercion.inv` | |
| `ordenamiento_seleccion.inv` | |
| `busqueda_binaria.inv` | |
| `quicksort.inv` | |
| `mergesort.inv` | |

Los atributos de arreglo en una clase no existen en InvenioLang (limitacion
de lenguaje preexistente) — los dos archivos "con objetos" representan su
arreglo de cabezas/cubetas como variable local (arreglo de objetos, Etapa
3) con procedimientos libres operando sobre el, en vez de una clase
contenedora. Ver detalle en la spec de esta etapa.

## Etapa 9 — IDE: Pulido Visual + IntelliSense

Como las Etapas 6-8, **no toca el lenguaje** — es aditiva sobre
`inveniolang/gui_qt.py` e `inveniolang/interpreter.py` (dos ganchos
opcionales, sin efecto salvo que la terminal integrada los use, ver
abajo). Cierra la brecha entre "IDE funcional" y "IDE moderno":

**Pulido visual**
- **Iconos** (QStyle estandar, sin dependencias nuevas) en las acciones
  principales y en cada pestaña del editor.
- **Minimapa** a la derecha de cada editor: vista miniatura de todo el
  archivo con clic/arrastre para saltar, y un recuadro que marca la
  porcion visible actualmente.
- **Paleta de comandos** (`Ctrl+Shift+P`): busqueda difusa (subsecuencia,
  estilo VS Code) sobre las acciones reales del menu — no una lista
  separada, si se agrega una accion al menu aparece sola en la paleta.
- **Breadcrumbs**: `archivo.inv › Clase › método` segun la posicion del
  cursor, calculado desde el AST del analisis en vivo.
- **Terminal integrada** (dock, `Ctrl+\``): corre el archivo activo con
  salida **en vivo** (linea a linea, a diferencia del Ejecutar por lotes
  existente que muestra todo junto al terminar) y un campo de entrada que
  se habilita automaticamente en cada `leer()`/`read()` — el programa
  queda bloqueado esperando, igual que una terminal real, en vez de
  requerir toda la entrada precargada de antemano.

**IntelliSense real** (no solo palabras clave, como el autocompletado de
la Etapa 5)
- **Autocompletado consciente de tipos**: tras `objeto.` solo se ofrecen
  los miembros **publicos** de la clase real de `objeto` — el tipo se
  infiere del AST (variable local, parametro, atributo propio o `this`) y
  los miembros se resuelven contra la tabla de simbolos real
  (`symbol_table.py`, caminando la cadena de herencia), no una lista
  aparte.
- **Ir a definicion** (`F12` o `Ctrl+clic`): salta a la declaracion real
  de una clase, metodo, atributo, variable o parametro.
- **Hover**: tooltip con el tipo/firma del identificador bajo el mouse,
  misma resolucion que los dos anteriores.

Los tres reutilizan el mismo nucleo de resolucion basado en el AST del
analisis en vivo (`_ubicar_contexto`, `_tipo_declarado`,
`_resolver_identificador_en` en `gui_qt.py`) — es una heuristica basada en
el AST, no un resolutor de ambitos completo (no distingue sombreado de
variables con el mismo nombre en bloques anidados), pero cubre el caso
real de un programa educativo.

## Etapa 10 — Cierre de Brechas de Fase 1/Fase 2

Documentada en detalle en
[`docs/InvenioLang_2.0_POO.md`](docs/InvenioLang_2.0_POO.md#10-etapa-10--cierre-de-brechas-de-fase-1fase-2)
(seccion 10). Cierra dos huecos reales encontrados al auditar POO completo
y la libreria estandar, aditiva sobre la Etapa 2/6/7 (cero cambios de
gramatica: `lista_miembros_clase` ya aceptaba varios constructores, solo
la validacion semantica los colapsaba a uno):

- **Sobrecarga de constructores** (`clase C { C() {..} C(entero x) {..} }`):
  mismo mecanismo que la sobrecarga de metodos de la Etapa 7, incluyendo
  `padre(...)` resolviendo la sobrecarga correcta del padre por tipo.
  Nuevo codigo `IL-POO-029`; `IL-POO-019` ampliado.
- **`imprimir(objeto)` personalizable**: si la clase declara publicamente
  `aTexto()`/`toString()` (sin parametros, retorna texto), se usa esa
  representacion en vez del formato automatico `Clase(campo=valor, ...)`
  — con despacho virtual, igual que cualquier otro metodo.
- **Libreria estandar**: entrada/salida de archivos de texto plano
  (`leer_archivo`, `escribir_archivo`, `agregar_archivo`, `existe_archivo`
  — nuevos codigos `IL-EST-015..017`) e `invertir_texto`.

Programas de referencia:
[`pruebas/poo_extendido.inv`](pruebas/poo_extendido.inv) (constructores +
`aTexto()`), [`pruebas/monticulo.inv`](pruebas/monticulo.inv) +
[`pruebas/heapsort.inv`](pruebas/heapsort.inv) (monticulo/cola de
prioridad, el hueco de estructuras de datos que quedaba de la Etapa 8), y
[`pruebas/archivo_io.inv`](pruebas/archivo_io.inv).

## Etapa 11 — Patrones de Diseño y Mejoras Finales de Fase 2

Documentada en detalle en
[`docs/InvenioLang_2.0_POO.md`](docs/InvenioLang_2.0_POO.md#11-etapa-11--patrones-de-diseño-y-mejoras-finales-de-fase-2)
(seccion 11). Cierra los ultimos huecos reales de Fase 1/Fase 2
encontrados al auditar el proyecto completo por segunda vez; la Fase 3
propuesta (herramientas graficas separadas: editor de bloques estilo
Scratch + prototipador UI/UX) se evaluo y se descarto explicitamente por
falta de valor pedagogico frente a alternativas ya maduras (seccion 11.12
de la spec), redirigiendo el esfuerzo a esta etapa.

- **Visibilidad de constructores** (`publico`/`privado`, nueva palabra
  reservada `constructor`): habilita el patron Singleton real. Nuevo
  codigo `IL-POO-030`.
- **`esIgual()`/`equals()` personalizable**: mismo mecanismo por convencion
  de nombre que `aTexto()`/`toString()` (Etapa 10), para `==`/`!=` entre
  objetos.
- **Cinco patrones de diseno** de referencia (Singleton, Factory, Observer,
  Strategy, Decorator) — sin mecanismo de lenguaje nuevo.
- **Algoritmos de grafos con peso**: Dijkstra, Kruskal (Union-Find), orden
  topologico (Kahn).
- **Backtracking y programacion dinamica**: N-reinas, permutaciones,
  Fibonacci memoizado, mochila 0/1.
- **Lista doblemente enlazada, deque y arbol AVL** (con las cuatro
  rotaciones de balanceo).
- **Enumeraciones** (`enum`/`enumeracion`): azucar sintactica sobre el
  mecanismo de clases (miembros estaticos), nominalmente tipadas (sin
  compatibilidad implicita con `int`). Nuevos codigos `IL-POO-031`,
  `IL-POO-032`.
- **Operadores bit a bit** (`&`, `|`, `^`, `~`, `<<`, `>>`), exclusivos de
  `int`.
- **`const` sobre arreglos** (`const int [3] X = {...};`): reasignar un
  elemento reutiliza `IL-SEM-031`, el mismo codigo que una constante
  escalar.

Programas de referencia nuevos en `pruebas/`: `patron_singleton.inv`,
`patron_factory.inv`, `patron_observer.inv`, `patron_strategy.inv`,
`patron_decorator.inv`, `dijkstra.inv`, `kruskal.inv`,
`orden_topologico.inv`, `n_reinas.inv`, `permutaciones.inv`,
`fibonacci_memo.inv`, `mochila.inv`, `lista_doble.inv`, `deque.inv`,
`arbol_avl.inv`, `enumeraciones.inv`, `bit_a_bit.inv`.

## Etapa 12 — Paradigma Funcional, Tipos Suma y Rigor de Compiladores

Documentada en detalle en
[`docs/InvenioLang_2.0_POO.md`](docs/InvenioLang_2.0_POO.md#12-etapa-12--paradigma-funcional-tipos-suma-y-rigor-de-compiladores)
(seccion 12) y en
[`docs/InvenioLang_GramaticaFormal.md`](docs/InvenioLang_GramaticaFormal.md).
Evaluado con criterio de teoria de lenguajes formales, el hueco real tras
la Etapa 11 no era de contenido de asignaturas (ya cubierto) sino de
**paradigma**: sin funciones de primera clase, sin tipos suma/*pattern
matching*, y un backend de compilador que se quedaba corto del tramo que
un curso de Lenguajes Formales/Compiladores mas quiere mostrar. Cierre
final: **372/372** en `pruebas/conformidad.py`.

- **`para_cada`/`foreach`**: recorrido de arreglos sin indice explicito,
  respeta `romper`/`continuar`.
- **`?.`/`??`** (acceso seguro / coalescencia nula): `p?.nombre ?? "x"` no
  lanza `IL-EJE-010` si `p` es nulo; `??` es cortocircuito real.
- **Interfaces multiples** (`interfaz`/`interface`, `implementa`/
  `implements`): una clase puede implementar varias, evita el diamante por
  diseno. Nuevos codigos `IL-POO-033`, `IL-POO-034`.
- **Documentacion formal de gramatica**: EBNF completa, FIRST/FOLLOW,
  fragmentos reales de la tabla LALR(1) — `docs/InvenioLang_GramaticaFormal.md`.
- **Funciones de primera clase (closures)**: tipo `funcion(tipos) retorno`
  (equivalencia estructural, unica excepcion a que InvenioLang es
  nominal), captura por referencia, funciones top-level pasables por
  nombre. Activa la palabra `funcion`/`function`, reservada desde la v1.0.
- **Orden superior** (`mapear`/`filtrar`/`reducir`) sobre arreglos, usando
  closures.
- **Recursion de cola (TCO)** en el backend `ir.py`: profundidad de pila
  constante con `--run-ir-opt` para funciones escritas con acumulador.
- **Tipos suma + *pattern matching*** (`enum` con variantes con carga +
  `emparejar`/`match`): se desazucara a clases reales (herencia +
  despacho virtual de la Etapa 7), con verificacion de exhaustividad
  (`IL-TIPO-022`) — la razon de ser pedagogica frente a un `switch`
  normal. Contraste directo con herencia+polimorfismo en
  `pruebas/tipos_suma.inv` vs `pruebas/poo_completo.inv`.
- **Generacion de codigo a un objetivo de juguete** (`--target`): ISA de
  pila de operandos de 26 instrucciones, cierra el pipeline fuente ->
  AST -> TAC -> TAC optimizado -> codigo objetivo.
- **Liveness analysis + asignacion de registros** (`--target-reg`):
  analisis de flujo de datos clasico (USE/DEF, punto fijo IN/OUT) +
  asignador *linear-scan* con *spill*, verificado con un caso que fuerza
  al menos un *spill* real y produce el mismo resultado.
- **Parser LL(1) de comparacion** (`inveniolang/ll1_demo.py`): modulo
  aparte, no conectado al pipeline principal, sobre expresiones
  aritmeticas — mismo resultado que el LALR(1) real sobre el mismo
  conjunto de pruebas.

Programas de referencia nuevos en `pruebas/`: `suma_cola.inv`,
`tipos_suma.inv`.

## Etapa 13 — Constructor de Diagramas de Flujo

Documentada en detalle en
[`docs/InvenioLang_2.0_POO.md`](docs/InvenioLang_2.0_POO.md#13-etapa-13--constructor-de-diagramas-de-flujo)
(seccion 13). Cierra un hueco identificado al revisar el cierre de Fase
1/Fase 2: el panel "Diagrama de flujo" (Etapa 4) es una herramienta de
**revelar** (genera el diagrama a partir de codigo YA escrito); el
objetivo pedagogico real es el opuesto — que el estudiante **dibuje** el
diagrama primero, como paso de planeacion, y que el diagrama **genere**
el codigo.

- **Constructor nuevo e independiente** (menu Ver/Ejecutar → "Constructor
  de diagramas"): el estudiante arma el algoritmo insertando bloques de
  una paleta (Proceso, Decision, Mientras, Hacer-mientras, Para, Entrada,
  Salida) en una secuencia — nunca dibuja una flecha a mano. El diagrama
  es estructuralmente valido por construccion (sin el problema, en
  general sin solucion limpia, de convertir un grafo arbitrario de cajas/
  flechas a codigo estructurado).
- **Reuso total**: el estado del diagrama es un `Bloque` real de
  `ast_nodes.py` (las mismas clases que produce el parser real);
  `flowchart.py::construir_diagrama` (Etapa 4) dibuja la vista previa en
  vivo sin ningun cambio; cada fragmento que escribe el estudiante se
  valida envolviendolo en un programa minimo y corriendolo por el
  Lexer/Parser reales — mismo patron ya usado por
  `pruebas/conformidad.py`/`ll1_demo.py`. Nuevo modulo
  `inveniolang/flowchart_builder.py`, sin Qt, testeable aislado.
- **Boton "Generar codigo InvenioLang"**: abre el resultado en una
  pestana nueva del editor — desde ahi el flujo normal del IDE
  (`--check`, ejecutar, depurar) sigue igual.
- Alcance v1: secuencia, si/si-sino, mientras, hacer-mientras, para,
  entrada/salida, proceso — genera el cuerpo de `main()`. Fuera de
  alcance v1: switch/try-catch/romper/continuar dentro del constructor,
  multiples funciones por diagrama, POO/arreglos.

## Estructuras de Datos (con y sin objetos)

Extiende InvenioLang 2.0 con lo necesario para implementar estructuras
enlazadas: la palabra reservada `nulo`/`null` (ausencia de objeto —
imprescindible para detectar el final de una lista o un árbol, ver
[`docs/InvenioLang_2.0_POO.md`](docs/InvenioLang_2.0_POO.md#7-referencia-nula-nulo--null))
y arreglos de objetos (`Persona[10] personas;`, **solo forma postfija** —
ver [§8 de la spec](docs/InvenioLang_2.0_POO.md#8-arreglos-de-objetos) para
por qué la prefija no es soportada).

Programas de referencia en `pruebas/` (cargables desde el menú Ayuda →
Ejemplos de la GUI):

| Sin objetos (arreglos, v1.0) | Con objetos (clases, v2.0) |
|---|---|
| `pila_arreglo.inv` | `lista_enlazada.inv` |
| `cola_arreglo.inv` | `pila_enlazada.inv` |
| | `cola_enlazada.inv` |
| | `arbol_binario.inv` |
| | `arreglo_objetos.inv` |

## Pipeline del Compilador

```
Archivo .inv  -->  Lexer  -->  Parser  -->  AST  -->  Semantico  -->  Type Checker  -->  Interprete  -->  Salida
                     |             |              |             |                |               |
               Errores         Errores        Errores       Errores         Errores        Errores
               lexicos       sintacticos    semanticos      de tipos       de ejecucion
                                                                     |
                                                                     +--> Generador IR --> Optimizador --> MaquinaTAC --> Salida
                                                                          (inveniolang/ir.py, --ir / --ir-opt / --run-ir)
```

El interprete de arbol (`interpreter.py`) sigue siendo el motor de ejecucion
de produccion del IDE (depurador, 273 pruebas de conformidad). El backend de
codigo intermedio es un camino **nuevo y aparte**, pensado para mostrar las
etapas clasicas que le faltaban al front-end (generacion de codigo,
optimizacion, ejecucion del codigo objetivo) sin arriesgar ese motor:

- **`inveniolang/ir.py`**: `GeneradorIR` recorre el AST y produce codigo de
  tres direcciones (TAC) — cuadruplas con temporales (`t1`, `t2`, ...) y
  etiquetas (`L1`, `L2`, ...) — para el subconjunto **estructurado** de la
  v1.0 (variables, arreglos de una dimension, funciones/procedimientos,
  control de flujo completo). **No cubre clases/POO ni matrices** en este
  incremento (`NoSoportadoIR` con un mensaje claro si el programa las usa).
- Optimizaciones como pasadas independientes sobre la lista de TAC: plegado
  y propagacion de constantes, eliminacion de codigo muerto e inalcanzable,
  y una pasada de peephole (saltos redundantes) — cada una reporta cuantas
  instrucciones cambio.
- **`MaquinaTAC`**: interprete lineal que ejecuta el TAC (optimizado o no)
  directamente. Verificado contra el interprete de arbol: los programas de
  referencia estructurados de `pruebas/` producen **exactamente la misma
  salida** por ambos caminos, optimizado o sin optimizar.
- **`generar_objetivo_programa`/`MaquinaObjetivo`** (Etapa 12.11): un
  segundo paso de traduccion, TAC -> un ISA de juguete de pila de operandos
  (`PUSH`/`LOAD`/`STORE`/`ADD`/.../`CALL`/`RET`/`PRINT`, 26 instrucciones,
  documentado completo en `ir.py`) — ese es el "codigo objetivo" real de
  esta etapa, cerrando el pipeline fuente -> AST -> TAC -> TAC optimizado ->
  codigo objetivo. Opcionalmente pasa antes por liveness analysis +
  asignacion de registros *linear-scan* (Etapa 12.12, `--target-reg`).

```bash
# Mostrar el codigo de tres direcciones (TAC) sin optimizar
python main.py --ir pruebas/ciclos.inv

# TAC optimizado + resumen de que cambio cada pasada
python main.py --ir-opt pruebas/ciclos.inv

# Ejecutar con la MaquinaTAC en vez del interprete de arbol
python main.py --run-ir pruebas/ciclos.inv

# Codigo objetivo (ISA de juguete) / con asignacion de registros
python main.py --target pruebas/ciclos.inv
python main.py --target-reg pruebas/ciclos.inv
```

En la GUI: menu **Ejecutar → Mostrar código intermedio**.

### Resto de la Etapa 5 (IDE avanzado)

- **Depurador ↔ diagrama de flujo**: al pausar en un breakpoint, el panel de
  diagrama cambia automaticamente a la subrutina en ejecucion (siguiendo la
  pila de llamadas) y resalta la caja de la linea actual.
- **Autocompletado**: `Ctrl+Espacio` o 2+ caracteres muestran sugerencias de
  palabras clave bilingues y de identificadores ya usados en el archivo.
- **Panel de configuracion** (menu Archivo → Configuración): tema claro/oscuro
  y tamaño de fuente del editor, aplicados en vivo y persistidos entre
  sesiones.

## Referencias

- Aho, A. et al. "Compilers: Principles, Techniques, and Tools" (2da ed.)
- Cooper, K. & Torczon, L. "Engineering a Compiler" (3ra ed.)
- Nystrom, R. "Crafting Interpreters"
- Documentacion oficial de PLY: https://www.dabeaz.com/ply/
