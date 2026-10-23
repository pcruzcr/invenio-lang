# Diagramas de flujo bidireccionales (Fase 3)

InvenioLang convierte **cualquier programa válido en diagramas de flujo** (uno
por subrutina, `main`, método y constructor) y **cualquier diagrama en
código**, en español o en inglés. Garantía probada en
`tests/flujo/test_flujo_ida_vuelta.py`: para *todos* los ejercicios de
`curriculum/es` y `curriculum/en`, código → diagrama → código (en los dos
idiomas) compila y produce exactamente la salida de su `.expected` con su
`.entrada`.

Paquete `inveniolang/flujo/` (sustituye a `flowchart.py` y
`flowchart_builder.py`, retirados en INV-3011 porque solo dibujaban un bloque
y editaban `main` sobre el AST, sin modelo serializable ni vuelta al programa
completo):

| Módulo | Qué hace |
|---|---|
| `modelo.py` | Contrato JSON v1 (`a_json`/`desde_json`, ida y vuelta exacta). |
| `extraccion.py` | Código → modelo (`modelo_desde_codigo`). |
| `generacion.py` | Modelo → código (`codigo_desde_modelo`) y `traducir_modelo`. |
| `esquema.py` | Símbolos ISO 5807, flechas y posiciones sin solapes. |
| `render_svg.py`, `render_mermaid.py`, `render_texto.py` | Exportaciones. |
| `edicion.py` | Edición estructurada y validación bilingüe. |

## Uso

### Línea de comandos

```
inveniolang flujo archivo.inv [--subrutina N] [--svg f.svg] [--mermaid f.mmd]
                  [--json f.json] [--texto] [--tema claro|oscuro|auto] [--idioma es|en]
inveniolang desde-flujo diagrama.json [--idioma es|en] [-o archivo.inv]
```

(`flowchart` y `from-flowchart` son alias; también `python -m inveniolang.cli ...`.)

* `flujo`: sin exportaciones imprime la descripción accesible (`--texto`).
  `--subrutina` elige un diagrama por su **clave** (`main`, `suma`,
  `Pila.apilar`, `Pila.Pila` para el constructor; las sobrecargas repetidas
  llevan `#2`, `#3`…); sin ella se incluyen todos. `--idioma` es el de los
  textos del diagrama (el programa se traduce antes) y de las etiquetas.
  Código 1 si el programa no compila (se imprimen los diagnósticos oficiales)
  o la subrutina no existe.
* `desde-flujo`: valida el diagrama (estructura, textos y compilación del
  programa generado); si hay problemas los lista como `[diagrama · nodo]
  mensaje` y termina con código 1 sin escribir nada.

```
$ inveniolang flujo curriculum/es/nivel03/01_funciones.inv --subrutina main
Diagrama de flujo de main. Símbolos: 6 de tipo datos (entrada/salida), 2 de tipo terminal.
1. Inicio. Sigue en 2.
2. Salida de datos (línea 24): imprimir cuadrado(9). Sigue en 3.
...
8. Fin. Aquí termina la subrutina.
```

### API

```python
from inveniolang import api, flujo

json_v1 = api.diagrama_flujo(codigo)                       # programa completo
svg = api.diagrama_flujo(codigo, "main", "svg", tema="auto")
mermaid = api.diagrama_flujo(codigo, None, "mermaid", idioma="en")
texto = api.diagrama_flujo(codigo, "suma", "texto")
codigo_en = api.codigo_desde_flujo(json_v1, "en")          # ModeloFlujo, dict o JSON
```

`diagrama_flujo(codigo, subrutina=None, formato="json"|"svg"|"mermaid"|"texto",
idioma=None, ruta, tema, modulos, ruta_fuente)` lanza `flujo.ErrorFlujo` si el
programa no compila (con `.diagnosticos`) o la subrutina no existe, y
`ValueError` con un formato o tema inválido. El JSON es siempre el programa
completo (es lo que permite volver a código); `subrutina` se valida igual.

## Modelo JSON (versión 1)

```json
{"formato": "inveniolang-flujo", "version": 1, "idioma": "es",
 "elementos": [
   {"tipo": "codigo", "texto": "importar \"util.inv\";"},
   {"tipo": "clase", "cabecera": "clase Pila", "miembros": [
      {"tipo": "codigo", "texto": "privado entero tope;"},
      {"tipo": "subrutina", "diagrama": {...}}]},
   {"tipo": "subrutina", "diagrama": {
      "clave": "main", "nombre": "main", "tipo": "main", "clase": null,
      "firma": "vacio main()", "linea": 3,
      "cuerpo": [{"id": "n1", "tipo": "declaracion", "linea": 4, "texto": "entero n = 0"}]}}]}
```

* El diagrama es un **árbol estructurado**: cada compuesto contiene sus
  secuencias, así que no se puede representar un salto arbitrario. Las flechas
  y conectores se derivan al dibujar.
* `elementos` conserva el orden del programa. Lo que no es flujo
  (importaciones, enumeraciones, globales, atributos, métodos abstractos) va
  como `codigo`; cada subrutina, método y constructor lleva su diagrama.
* Los textos son fragmentos InvenioLang **del propio código del estudiante**
  (tokens del lexer real, sin `;` final, con los comentarios quitados y los
  espacios normalizados). Los comentarios no forman parte del diagrama.
* `id` es único en todo el modelo; `linea` es la del código fuente (0 si el
  nodo se creó en el editor). `tipo` de diagrama: `main`, `funcion`,
  `procedimiento`, `metodo`, `constructor`.

| `tipo` de nodo | Campos | Construcción |
|---|---|---|
| `proceso` | `texto` | asignación, `x++` / `x--` |
| `declaracion` | `texto` | variable, constante, arreglo, matriz |
| `leer` / `escribir` | `texto` | `leer(x)` / `imprimir(e)` (interior del paréntesis) |
| `llamada` | `texto` | llamada a subrutina, a método o a `padre(...)` |
| `retornar` | `texto` (puede ser `""`) | `retornar [e]` |
| `romper` / `continuar` | — | `romper` / `continuar` |
| `si` | `ramas: [{condicion, cuerpo}]`, `sino` (lista o `null`) | `si` / `sino si` / `sino` |
| `segun` | `expresion`, `casos: [{valor, cuerpo}]`, `por_defecto` | `segun` / `caso` / `por_defecto` |
| `coincidir` | `expresion`, `casos: [{patron, cuerpo}]`, `por_defecto` | `emparejar` |
| `mientras` / `hacer_mientras` | `condicion`, `cuerpo` | `mientras` / `hacer … mientras` |
| `para` | `inicio`, `condicion`, `paso`, `cuerpo` | `para (i; c; p)` |
| `para_cada` | `variable`, `coleccion`, `cuerpo` | `para_cada (tipo x : c)` |
| `intentar` | `cuerpo`, `variable`, `captura` | `intentar … capturar (e)` |

`sino si`: el lenguaje exige llaves tras `sino`, así que `sino { si (…) … }`
con una única instrucción `si` se aplana en una rama más del mismo nodo y la
generación vuelve a escribir exactamente ese anidamiento. Un JSON que no
cumple el contrato produce `ErrorFlujo` con la ruta del dato (`$.elementos[2]
.diagrama.cuerpo[0].id`) y el motivo, en español o inglés.

## Símbolos ISO 5807

| Símbolo | Forma (SVG / Mermaid) | Se usa para |
|---|---|---|
| Terminal | óvalo `([…])` | Inicio, Fin, `retornar` |
| Proceso | rectángulo `[…]` | asignación, declaración, inicialización y paso del `para`, `intentar`, `capturar` |
| Decisión | rombo `{…}` | condición de `si`, `mientras`, `hacer-mientras`, `para`; `para_cada` («cada x en c»); expresión de `segun` / `emparejar` |
| Datos (E/S) | paralelogramo `[/…/]` | `leer`, `imprimir` |
| Proceso predefinido | rectángulo con barras `[[…]]` | llamada a subrutina o método |
| Conector | círculo `((…))` | unión de ramas; `romper`, `continuar` y caída de un `caso` al siguiente (pares de conectores con la misma letra) |

`intentar` no tiene símbolo propio en la norma: es un proceso con dos caminos,
«sin error» (el bloque protegido) y «si hay error» (hacia `capturar (e)`).

## Dibujo (SVG) y accesibilidad

* Sin solapes por construcción: cada construcción ocupa un rectángulo propio,
  las ramas van en columnas disjuntas, la vuelta de un ciclo sube por un
  carril izquierdo reservado y la salida «no» baja por uno derecho. Los saltos
  (`romper`, `continuar`, caída de caso) se dibujan como pares de conectores
  con letra (A, B…) en vez de líneas que crucen el diagrama.
  `tests/flujo/test_flujo_esquema.py` lo comprueba sobre todo el currículo:
  ningún símbolo se solapa, ninguna flecha atraviesa un símbolo ni queda
  suelta y ninguna etiqueta tapa un símbolo.
* `role="img"`, `<title>` y `<desc>` (la descripción textual completa); cada
  símbolo lleva su `<title>` («Decisión (línea 7): i < n») y `data-nodo` con
  el id del modelo.
* No depende del color: cada tipo tiene su forma, las salidas llevan su
  etiqueta escrita («Sí»/«No», el valor del caso) y los saltos su letra.
* Temas `claro`, `oscuro` y `auto` (CSS `prefers-color-scheme`); el texto
  tiene contraste ≥ 7:1 con todos los rellenos en ambos temas.
* Mermaid `flowchart TD` con `accTitle`/`accDescr`; los saltos son flechas
  punteadas. Con varios diagramas, un `subgraph` por cada uno.
* Descripción textual: cada símbolo numerado en orden de lectura con su papel,
  línea, texto y a qué número sigue por cada salida (««Sí» → 4; «No» → 9»,
  «Vuelve a 3», «Salta a 12»).

## Edición estructurada

Base del editor de la GUI y del futuro editor de arrastrar y soltar. Todas las
operaciones son puras (devuelven un modelo nuevo) y lanzan `ErrorFlujo` con
mensaje bilingüe si el resultado no fuera válido:

| Operación | Qué hace |
|---|---|
| `nuevo_nodo(tipo, **campos)` | crea un nodo; cada texto se analiza con el lexer y el parser reales dentro de un programa mínimo y debe ser exactamente una instrucción de su clase |
| `insertar(m, clave, Ubicacion(padre, parte, indice), nodo)` | inserta en `cuerpo`, `rama:K`, `caso:K`, `sino`, `por_defecto` o `captura` |
| `eliminar`, `mover` | quita / recoloca un nodo con su contenido (nunca dentro de sí mismo) |
| `envolver_en_si`, `envolver_en_ciclo` | mete nodos consecutivos en un `si` o en un ciclo nuevo |
| `editar(m, clave, id, campo, valor)` | cambia un texto (`rama:K` / `caso:K` para etiquetas) |
| `agregar_rama`, `quitar_rama` | `sino si`, `sino`, casos y `por_defecto` |
| `validar(m)` | estructura, textos y compilación del programa generado; cada diagnóstico se cuelga del nodo que lo causó |

Reglas que se comprueban tras cada operación: `romper` solo dentro de un ciclo
o de un `segun`; `continuar` solo dentro de un ciclo; un `si` conserva al menos
una condición.

## GUI Qt

El dock «Diagrama de flujo» (acciones «Mostrar diagrama de flujo» y
«Constructor de diagramas de flujo» del menú) es un único panel que
sustituye al dock de solo lectura y al antiguo «Constructor de diagramas»:
elige subrutina/método, dibuja el SVG accesible con el tema del IDE, resalta la
caja donde se detiene el depurador, edita el árbol con el menú contextual
(insertar, editar, eliminar, subir/bajar, envolver, ramas), muestra los
problemas, deshace, exporta (JSON, SVG, Mermaid, texto), abre JSON y genera el
código en español o inglés en una pestaña nueva.

---

## English summary

InvenioLang turns **any valid program into flowcharts** (one per subroutine,
`main`, method and constructor) and **any flowchart back into code**, in
Spanish or English. For every exercise in `curriculum/es` and `curriculum/en`,
code → flowchart → code (in both languages) compiles and prints exactly the
expected output — this is tested.

* CLI: `inveniolang flujo file.inv [--subrutina KEY] [--svg f|--mermaid f|--json f|--texto]
  [--tema claro|oscuro|auto] [--idioma es|en]` and `inveniolang desde-flujo
  flowchart.json [--idioma es|en] [-o file.inv]`.
* API: `api.diagrama_flujo(code, subrutina=None, formato="json"|"svg"|"mermaid"|"texto")`
  and `api.codigo_desde_flujo(model, idioma)`.
* Model: JSON version 1 (`"formato": "inveniolang-flujo"`), a structured tree
  per diagram (no arbitrary jumps can be expressed), box texts taken from the
  student's own tokens; exact round trip `desde_json(a_json(m)) == m`.
* ISO 5807 symbols: terminal (start/end/return), process, decision, data I/O
  (read/print), predefined process (calls), connector (joins and paired
  lettered connectors for break/continue/case fall-through).
* Accessible SVG (`<title>`, `<desc>`, per-symbol titles, shapes and written
  labels instead of colour alone, light/dark/auto themes, overlap-free layout),
  Mermaid `flowchart TD` with `accTitle`/`accDescr`, and a numbered text
  description in Spanish or English.
* Structured editing (insert, delete, move, wrap in if/loop, branches) with
  bilingual validation; the Qt "Flowchart" panel is built on it.
