# Visualización paso a paso: trazas de ejecución

InvenioLang puede ejecutar un programa **registrando cada instrucción** para que
el estudiante vea cómo cambian sus arreglos, matrices, pilas, colas, listas
enlazadas, árboles y grafos, qué celdas se leen y se escriben, la pila de
llamadas (recursión) y la salida. El resultado es una **traza**: un documento
JSON con un contrato estable (versión 1) que consumen la CLI, la API, el
reproductor HTML/SVG y la GUI.

Paquete `inveniolang/visualizacion/`: el trazador (`modelo.py`, `traza.py`,
`clasificador.py`) produce la traza; los renderizadores la consumen:
`render_texto.describir` (descripción accesible de un paso, es/en),
`render_svg.svg_paso` (dibujo SVG con `<title>`/`<desc>`) y
`reproductor.html_traza` (reproductor HTML autónomo, sin red). La GUI Qt los
usa en el panel "Visualizador" (botón Trazar).

## Uso

### Línea de comandos

```
inveniolang trazar archivo.inv [entrada...] [--json traza.json] [--texto]
                   [--html traza.html] [--svg-paso N paso.svg]
                   [--objetos N objetos.svg|objetos.txt]
                   [--max-pasos N] [--idioma es|en]
```

(`trace` es un alias de `trazar`; también `python -m inveniolang.cli trazar ...`.)

* `entrada...`: un valor por cada `leer`/`read` del programa; nunca se lee el
  teclado.
* `--json archivo`: escribe la traza completa.
* `--html archivo`: escribe el reproductor HTML autónomo (controles, teclado,
  región `aria-live`, código con la línea actual, tema claro/oscuro).
* `--svg-paso N archivo`: escribe el dibujo SVG del paso número N (el mismo
  número que muestra `--texto`).
* `--objetos N archivo` (alias `--objects`, INV-4402): escribe el **diagrama de
  objetos UML** del paso número N (ver [uml.md](uml.md#diagrama-de-objetos)):
  SVG si el archivo termina en `.svg`; si no, su descripción en texto.
* `--texto`: imprime la descripción accesible de cada paso
  (`render_texto.describir`: línea, lecturas y escrituras con sus valores,
  salida, pila de llamadas, variables y estado de cada estructura). Es lo que se
  hace si no se pide ninguna exportación.
* `--max-pasos N` (1 a 100 000, por defecto 5000): al llegar a N pasos el
  programa **se detiene** y la traza queda marcada como truncada.
* `--idioma`: idioma de los mensajes y del campo `idioma` de la traza. Si no se
  indica, se deduce de las palabras clave del programa (`mientras` → es,
  `while` → en).

Código de salida: 0 si el programa terminó (o se truncó) sin errores, 1 si hubo
errores de compilación o de ejecución, 2 si `--max-pasos` o el paso de
`--svg-paso`/`--objetos` están fuera de rango.

```
$ inveniolang trazar curriculum/es/nivel05/01_burbuja.inv --max-pasos 12
=== TRAZA: 01_burbuja.inv · 12 pasos ===
Paso 1, línea 24. Se escribe a, que ahora vale → a. Ejecutando main; ...
...
Paso 11, línea 19. Se lee a[1], que vale 34. Se escribe a[0], que ahora vale 34.
Ejecutando intercambiar; profundidad de la pila de llamadas: 3. ...
Arreglo a con 7 elementos: 34, 34, 25, 12, 22, 11, 90.
```

### API

```python
from inveniolang import api
from inveniolang.visualizacion.modelo import a_json, desde_json

traza = api.trazar(codigo, ruta="burbuja.inv", entrada=("5",), idioma=None,
                   max_pasos=5000, modulos=None, ruta_fuente=None)
texto = a_json(traza)              # JSON del contrato
html = api.traza_html(codigo)      # reproductor (también api.traza_html(traza))
svg = api.traza_svg(traza, 0)      # SVG del paso en la posición 0 (paso n = 1)
assert desde_json(texto) == traza  # ida y vuelta exacta
```

* `modulos={"util.inv": "..."}` sirve los `importar` desde memoria (web, LMS);
  `ruta_fuente="ruta/real.inv"` los resuelve desde disco (CLI, GUI).
* Con errores de compilación la traza no tiene pasos y `error` lleva los
  diagnósticos oficiales. Con un error de ejecución, los pasos llegan hasta la
  instrucción que falló y `error` lo describe.
* `max_pasos` fuera de 1..100 000 o un idioma no soportado: `ValueError`.

## Qué es un paso

Un paso corresponde a **una instrucción** del programa principal y describe el
estado **después** de ejecutarla, junto con lo que ella hizo:

* `linea`, `columna`: la instrucción.
* `accesos`: lecturas y escrituras que hizo (celdas `a[i]`, `m[f][c]`, campos
  `nodo.siguiente`, variables escritas).
* `salida_nueva`: lo que imprimió.
* `marcos`: la pila de llamadas completa, del ámbito global (`<global>`) a la
  activación en curso, con todas sus variables.
* `monticulo`: arreglos, matrices y objetos alcanzables, con **ids estables**: el
  mismo arreglo tiene el mismo id en todos los pasos (permite animar).
* `estructuras`: la forma reconocida de cada estructura viva.

Detalles que conviene conocer:

* Una instrucción compuesta (`si`, `mientras`, `para`) es un paso propio: el de
  evaluar su condición. La actualización de un `para` (`i++`) se agrupa con la
  última instrucción de la vuelta.
* Al llamar a una subrutina, el paso de la llamada ya muestra el marco nuevo con
  sus parámetros. Un `retornar` todavía muestra el marco que termina; al volver
  hay un paso de **regreso** en la línea del llamador (con un marco menos) que
  recoge, por ejemplo, la asignación del valor devuelto.
* El código de **módulos importados** (incluida la biblioteca estándar) está en
  otro archivo: sus instrucciones no son pasos propios, se agrupan en el paso de
  la llamada. `p.apilar(3)` es un paso con todas sus escrituras (`este.cima`,
  `este.cantidad`).
* Un lambda escrito en la misma línea que la llamada a `mapear` produce pasos en
  esa misma línea (uno por invocación).

## Contrato JSON (versión 1)

```
Traza      = {"version":1, "idioma":"es"|"en", "fuente":str, "pasos":[Paso],
              "truncada":bool, "error":str|null, "salida":[str]}
Paso       = {"n":int (1, 2, ...), "linea":int, "columna":int,
              "marcos":[Marco] (base → tope), "monticulo":{"id":NodoMonticulo},
              "accesos":[Acceso], "salida_nueva":[str], "estructuras":[Estructura]}
Marco      = {"subrutina":str, "linea":int,
              "variables":{nombre:{"tipo":str, "valor":Valor}}}
Valor      = {"t":"escalar", "tipo":str, "v":int|float|str|bool|null}
           | {"t":"ref", "id":int}
NodoMonticulo = {"id":int, "tipo":"arreglo"|"matriz"|"objeto", "clase":str|null,
                 "elementos":[Valor] | [[Valor]] (matriz: lista de filas),
                 "campos":{nombre:Valor}}
Acceso     = {"op":"lee"|"escribe", "var":str|null, "nodo":int|null,
              "indices":[int], "campo":str|null}
Estructura = {"forma":"arreglo"|"matriz"|"pila"|"cola"|"lista_enlazada"|
              "lista_doble"|"arbol_binario"|"grafo"|"objeto",
              "raiz":int, "etiqueta":str, "nodos":[int], "aristas":[[int,int,str]],
              "cima":int (opcional)}
```

Precisiones:

* JSON solo tiene claves de texto: el montículo se indexa con `"3"` y cada nodo
  repite su `id` entero. `desde_json` valida todo el documento y devuelve
  exactamente la traza original (`ValueError` con la ruta del dato si algo no
  cumple el contrato, por ejemplo una versión distinta de 1).
* Tipos escalares: `int`, `float`, `string`, `bool`, `null` (también una variable
  local declarada aún sin valor), `funcion` (`v` = nombre de la subrutina o
  `"lambda"`). Los reales no finitos viajan como texto (`"inf"`, `"nan"`): JSON
  estándar no los admite.
* El `tipo` de una variable de un marco es el declarado (`int`, `Nodo`...); en
  arreglos se completa con `[]`/`[][]` según el valor real.
* La variable `este` (`this` si la traza está en inglés) aparece en los marcos de
  métodos y constructores. Las activaciones se llaman como la subrutina
  (`main`, `factorial`), `Clase.metodo`, `Clase.Clase` (constructor) o
  `<lambda>`.
* `Acceso`: una lectura de `a[i]` lleva `var:"a"`, `nodo` (id del arreglo) e
  `indices:[i]`; `m[f][c]` lleva dos índices; `p.campo` lleva `campo` y `var:"p"`
  (`"este"`/`"this"` dentro de un método); una variable escrita lleva solo
  `var`. `a[i] op= e` (y `p.campo op= e`) registra la lectura y la escritura. No se registran las
  lecturas de variables simples (cada instrucción lee varias; serían ruido).

### Formas de las estructuras

**Convención única de `raiz` y `nodos`** (INV-2007, la usan el clasificador y
todos los renderizadores):

* `nodos` lista **solo elementos**, en orden de recorrido (tope/frente/cabeza
  primero, árbol en preorden, vértices del grafo).
* `raiz` es el **contenedor** cuando existe (el objeto `Pila`, `ListaEnlazada`,
  `ArbolBB`, `Grafo`..., o el arreglo de una pila/cola sobre arreglo) y entonces
  **no** está en `nodos`. Si una variable apunta directamente al primer nodo
  (sin contenedor), `raiz` es ese nodo y **sí** está en `nodos`. Regla para
  leerla: *la raíz es un elemento si y solo si está en `nodos`*.
* Si `nodos` está vacío y `raiz` es un arreglo, los elementos son sus celdas (en
  una cola el frente es la primera). En una pila sobre arreglo la cima es la
  celda `cima` (INV-4400): el índice que marca la variable hermana
  `tope`/`top`/`cima` o, en un objeto `Pila`/`Stack`, su campo
  `tope`/`top`/`cima` o `tamano`/`size` - 1; `-1` es pila vacía y las celdas por
  encima de la cima no se muestran. Sin ese dato (clave ausente) la cima es la
  última celda.
* Grafo: si `monticulo[raiz]` es una `matriz` o un `arreglo` (adyacencia sin
  objetos vértice), los vértices son los índices `0..n-1` (n = filas o celdas),
  `nodos` está vacío y los extremos de cada arista son esos **índices**; en otro
  caso los extremos son ids del montículo de los vértices listados en `nodos`.
  La etiqueta de una arista es su peso (`""` si no tiene o vale 1).
* Árbol: el lado de cada arista sale de su etiqueta (`izq`/`left`...); las
  aristas que salen del contenedor (`raiz`, `root`...) no son del árbol.

| forma | `raiz` | `nodos` | `aristas` |
|---|---|---|---|
| `arreglo`, `matriz` | el arreglo | `[raiz]` | — |
| `pila`, `cola` (nodos enlazados) | el contenedor | elementos del tope/frente al fondo/final | contenedor → primero (`cima`, `frente`...), enlaces, contenedor → último (`final`, `cola`, `tail`, `queue`...) |
| `pila`, `cola` (sobre arreglo) | el arreglo | `[]` (las celdas son los elementos; en la pila, hasta `cima`) | — |
| `lista_enlazada`, `lista_doble` | el contenedor, o la cabeza si no lo hay | de la cabeza al último | contenedor → cabeza/cola (si hay), `siguiente`/`next` (y `anterior`/`prev`) |
| `arbol_binario` | el contenedor, o la raíz real si no lo hay | preorden | contenedor → raíz (si hay), padre → hijo con el nombre del campo |
| `grafo` con vértices objeto | el objeto grafo | los vértices | vértice → vértice, etiqueta = peso (o `""`) |
| `grafo` con matriz o arreglo de adyacencia | la matriz/el arreglo | `[]` | **índices** de vértice `0..n-1` |
| `objeto` | el objeto | `[raiz]` | — |

Reglas del clasificador (una sola tabla bilingüe de sinónimos en
`clasificador.py`):

* **pila/cola**: clase cuyo nombre contiene `Pila`/`Stack` o `Cola`/`Queue`
  (`PilaEnlazada`, `ColaCircular`; no `NodoCola`), o un arreglo guardado en una
  variable llamada así (`entero [4] pila`).
* **grafo**: clase `Grafo`/`Graph`, objeto con campo `adyacencia`/`adjacency`, o
  matriz cuadrada en una variable `adj`/`adyacencia`/`adjacency` (en ese caso se
  muestra también como `matriz`).
* **árbol binario**: objetos con enlaces `izq/der`, `izquierdo/derecho`,
  `left/right`. **lista**: enlace `siguiente`/`sig`/`next` (y
  `anterior`/`prev` para la doble). Una variable que apunta a la mitad de una
  lista o a un subárbol no crea otra estructura: se muestra la completa, desde
  su cabeza o raíz, etiquetada con la variable que apunta a ella si existe.
* Un objeto contenedor (`ListaSimple`, `ArbolBB`...) es la raíz de la lista o
  árbol que guarda, con la etiqueta de su variable; los arreglos de un objeto
  (`Vector.datos`) se muestran aparte con etiqueta `variable.campo` (`v.datos`).
* Los objetos guardados en un arreglo solo generan estructuras compuestas
  (listas, árboles...), no un `objeto` por celda.

## Límites y rendimiento

* `max_pasos` (por defecto 5000, máximo 100 000) detiene la ejecución.
* Presupuesto total de celdas copiadas (2 000 000): si un programa reescribe una
  y otra vez estructuras enormes, la traza se trunca en vez de agotar la memoria.
* Se conservan los primeros 500 accesos de cada paso.
* Siguen activos los límites del intérprete (iteraciones, segundos, recursión):
  un ciclo infinito o una recursión sin fin terminan con su error del catálogo.
* El montículo se comparte entre pasos: un nodo solo se vuelve a copiar si se
  escribió, y de un arreglo solo las celdas escritas.
* **Coste cero sin traza**: la ejecución normal no construye instantáneas ni
  llama al registro de accesos (el gancho `registro_accesos` del intérprete está
  en `None`; la contabilidad de activaciones vive en la subclase
  `InterpreteTrazado`).

---

## English summary

`inveniolang trazar file.inv [input...] [--json trace.json] [--texto]
[--max-pasos N] [--idioma es|en]` (alias `trace`) runs a program and records
**one step per statement** of the main file: the state *after* the statement,
the cells/fields it read and wrote, the new output, the full call stack and a
heap with **stable ids** (the same array keeps its id in every step). Code from
imported modules (standard library included) is grouped into the step of the
call. `--html` writes the self-contained HTML player, `--svg-paso N f` the SVG
of step number N, and `--texto` (the default when nothing is exported) prints
the accessible description of every step.
`--max-pasos` (default 5000, max 100 000) stops the program and marks the trace
as truncated; the interpreter's iteration/time/recursion limits still apply.
The language is deduced from the program keywords unless `--idioma` is given.

From Python: `api.trazar(code, ruta=..., entrada=(...), idioma=None,
max_pasos=5000, modulos=None, ruta_fuente=None)` returns a `Traza`;
`visualizacion.modelo.a_json(trace)` / `desde_json(text)` convert it to and from
the version-1 JSON contract above (exact round trip, strict validation).
`api.traza_html(code_or_trace)` and `api.traza_svg(code_or_trace, position)`
render it (a `str` is source code; a `Traza` or its `dict` is used as is).

Single convention for `raiz`/`nodos`: `nodos` lists only elements in traversal
order; `raiz` is the container when there is one (then it is not in `nodos`),
or the first node when a variable points straight at it (then it is in
`nodos`): *the root is an element iff it is in `nodos`*. With empty `nodos`
and an array root, the cells are the elements (stack top = last cell).

Recognised structure shapes (`estructuras`): arrays, matrices, stacks and
queues (classes named `Stack`/`Pila`, `Queue`/`Cola`, or arrays stored in
variables with those names), singly and doubly linked lists
(`next`/`siguiente`, `prev`/`anterior`), binary trees (`left/right`,
`izq/der`), graphs (`Graph`/`Grafo` classes, `adjacency` fields or a square
matrix in a variable named `adj`/`adjacency`) and plain objects. For a graph
whose adjacency is a matrix or an array of lists there are no vertex objects:
`raiz` is that matrix/array, `nodos` is empty and edge endpoints are **vertex
indices** `0..n-1`; otherwise edge endpoints are heap ids of the vertex objects. Normal
execution pays nothing for tracing: the interpreter's `registro_accesos` hook
is `None` by default.
