# Programación por bloques (Fase 4)

InvenioLang se puede programar **construyendo con bloques**, al estilo de
Scratch o Blockly, en español o en inglés, y pasar en cualquier momento al
código o al diagrama de flujo. Los bloques cubren **todo el lenguaje**:
declaraciones, expresiones anidables con huecos tipados, entrada y salida,
control, subrutinas, funciones anónimas, clases con atributos, métodos,
constructores, herencia, interfaces y genéricos, enumeraciones, arreglos y
matrices e `importar`.

Garantía probada (`tests/bloques/test_bloques_ida_vuelta.py`): para **todos**
los ejercicios de `curriculum/es` y `curriculum/en` (266), código → bloques →
código, en español y en inglés, compila y produce exactamente la salida de su
`.expected` con su `.entrada`; el JSON hace ida y vuelta exacta y los bloques
validan sin problemas.

Paquete `inveniolang/bloques/`:

| Módulo | Qué hace |
|---|---|
| `catalogo.py` | Tipos de bloque (forma, categoría, campos, huecos tipados, listas), categorías con icono y colores accesibles, paleta; `catalogo_dict(idioma)` lo publica en JSON. |
| `modelo.py` | Contrato JSON v1 (`a_json`/`desde_json`, ida y vuelta exacta, errores con la ruta del dato). |
| `lector.py` / `escritor.py` | Textos InvenioLang ⇄ bloques (tokens del lexer real, misma precedencia que `parser.py`, paréntesis sólo donde hacen falta, literales tal cual). |
| `conversion.py` | Código ⇄ bloques ⇄ diagrama de flujo; `codigo_con_lineas` (línea de cada bloque). |
| `reglas.py` | Encaje al soltar: familias de lista, huecos tipados, inferencia de tipos con las reglas de `type_checker.py`. |
| `edicion.py` | Operaciones puras (insertar, mover, eliminar, duplicar, envolver, editar) y `validar` con el compilador real. |
| `texto.py` | Rótulos de los bloques y descripción textual accesible. |
| `diseno.py` | Geometría del lienzo y zonas de soltar, sin Qt. |

La GUI está en `inveniolang/gui/panel_bloques.py`.

## Bloques y diagrama de flujo: el mismo árbol

El diagrama de flujo (`docs/diagramas_de_flujo.md`) ya es un árbol
estructurado: cada subrutina, método y constructor tiene su secuencia de
instrucciones y cada compuesto (`si`, `mientras`…) contiene las suyas. Los
bloques **no duplican** ese modelo: son la misma estructura en la que cada
texto de una caja se descompone en bloques de valor.

* Código → bloques: `flujo.modelo_desde_codigo` (compilador real) y después
  `lector.py` descompone cada texto.
* Bloques → código: `conversion.a_flujo` vuelve a escribir cada texto y el
  programa lo genera `flujo.generacion` (palabras clave en es/en y el
  formateador del proyecto). No hay un segundo generador de código.
* Cada **instrucción** de bloques lleva el **mismo id** que su caja del
  diagrama, así que elegir una señala la otra en la GUI.

Para esto se generalizó `inveniolang/flujo` sin cambiar su contrato:
`extraccion.tokens_fuente` (público), `extraccion.nodos_de_bloque` (diagrama
del cuerpo de una función anónima, sólo sintaxis) y `Generado.inicios`
(línea donde empieza cada elemento y miembro de clase).

## Uso

### Línea de comandos

```
inveniolang bloques archivo.inv [--json f.json] [--texto] [--catalogo c.json] [--idioma es|en]
inveniolang desde-bloques bloques.json [--idioma es|en] [-o archivo.inv]
```

(`blocks` y `from-blocks` son alias; también `python -m inveniolang.cli ...`.)

* `bloques`: sin `--json` ni `--catalogo` imprime la descripción accesible.
  `--idioma` es el de los bloques (el programa se traduce antes). Código 1 y
  los diagnósticos oficiales si el programa no compila.
* `desde-bloques`: valida los bloques (estructura, campos, tipos y
  compilación); si hay problemas los lista como `[id del bloque] mensaje` y
  termina con código 1 sin escribir nada.

```
$ inveniolang bloques curriculum/es/nivel02/05_ciclo_mientras.inv
definir vacio main ()
  declarar entero n = 27
  declarar entero pasos = 0
  declarar entero maximo = n
  mientras n != 1
    si (con sino)
      si n % 2 == 0 entonces
        n = n / 2
...
```

### API

```python
from inveniolang import api, bloques

json_v1 = api.bloques(codigo)                       # JSON v1 del programa
texto = api.bloques(codigo, "texto", idioma="en")   # descripción accesible
codigo_en = api.codigo_desde_bloques(json_v1, "en") # ModeloBloques, dict o JSON
catalogo = api.catalogo_bloques("es")               # tipos, paleta, colores

m = bloques.bloques_desde_codigo(codigo)
main = m.programa[-1]                               # bloque «definir vacio main ()»
m = bloques.insertar(m, bloques.desde_paleta("mientras"), bloques.Destino(main.id, "cuerpo", 0))
problemas = bloques.validar(m)                      # [] si el programa es correcto
```

`api.bloques` lanza `flujo.ErrorFlujo` (con `.diagnosticos`) si el programa no
compila y `ValueError` con un formato inválido; `api.codigo_desde_bloques`
lanza `bloques.ErrorBloques` si el JSON no cumple el contrato o si falta algo
para escribir el programa (hueco obligatorio vacío, campo sin valor).

## Modelo JSON (versión 1)

```json
{"formato": "inveniolang-bloques", "version": 1, "idioma": "es",
 "programa": [BLOQUE, ...]}
```

Todo bloque tiene la misma forma:

```json
{"id": "n3", "tipo": "mientras", "linea": 7,
 "campos": {},
 "huecos": {"condicion": {"id": "b9", "tipo": "binaria", "linea": 7,
                          "campos": {"op": "<"},
                          "huecos": {"izquierda": {...}, "derecha": {...}},
                          "listas": {}}},
 "listas": {"cuerpo": [BLOQUE, ...]}}
```

* `campos`: datos atómicos: texto o, para las banderas, `true`/`false`. Los
  valores que son palabras clave se guardan en forma **neutral** (la española
  canónica: `publico`, `estatico`, `verdadero`…) y se escriben en el idioma
  del modelo; tipos, nombres y literales se guardan como se escriben en el
  idioma del modelo (`"entero"`, `"Pila<int>"`, `"1.50"`, `"\"hola\""`).
* `huecos`: un bloque de **valor** o `null` (hueco aún vacío: el programa está
  en construcción; `validar` lo señala).
* `listas`: secuencias ordenadas de bloques.
* Las claves de `campos`, `huecos` y `listas` de cada `tipo` son **exactamente**
  las del catálogo; un JSON con claves de más o de menos, un tipo desconocido,
  un id repetido o un bloque en una lista que no lo admite se rechaza con la
  ruta (`$.programa[2].listas.cuerpo[0].huecos.condicion`) y el motivo, en
  español o inglés.
* `id` es único en todo el modelo; `linea` es la del código fuente (0 si el
  bloque se creó en el editor).

### Catálogo

`catalogo_dict(idioma)` (y `inveniolang bloques f.inv --catalogo c.json`)
publica `{"formato": "inveniolang-bloques-catalogo", "version": 1, ...}` con:
`tipos` (forma, categoría, salida, plantilla, nombre, campos, huecos, listas),
`familias` (qué tipos admite cada familia de lista; `null` = por forma),
`globales`, `categorias` (nombre, icono y colores por tema) y `paleta`
(entradas con campos preestablecidos). El estudio web lo usa para dibujar y
validar igual que la GUI.

**Formas**: `valor` (devuelve algo; los lógicos se dibujan hexagonales),
`instruccion` (pieza de pila), `c` (abraza pilas), `definicion` (sombrero),
`miembro` (dentro de una clase), `parte` (rama, caso, fila, parámetro…).

**Plantillas**: `BLQ.plantilla.<tipo>` en `i18n/es.py`/`en.py`, p. ej.
`"mientras {condicion}"`. `{x}` es un campo, un hueco o una lista en línea;
`<? … ?>` es un tramo opcional (en texto se omite si está vacío; el lienzo lo
muestra para poder rellenarlo). Las listas que no aparecen en la plantilla son
**bocas** dibujadas debajo; algunas llevan rótulo (`BLQ.boca.si.sino`).

| Categoría | Tipos |
|---|---|
| Valores | `numero`, `texto`, `logico`, `nulo` |
| Variables | `variable`, `declarar` (variable o constante), `asignar` (`=`, `+=`…), `incrementar` (`x++;`), `incremento` (`x++` dentro de una expresión) |
| Operadores | `binaria` (aritméticos, comparación, lógicos, bits, `??`), `unaria` (`-`, `!`, `~`), `ternaria` |
| Entrada y salida | `leer` (hueco asignable), `imprimir` (un valor) |
| Control | `si` + `rama_si` (cadena «sino si») + `sino`; `segun` + `caso` + `por_defecto`; `coincidir` + `caso_patron`; `mientras`, `hacer_mientras`, `para` (inicio/condición/paso), `para_cada`, `romper`, `continuar`, `intentar` (cuerpo + `captura`) |
| Subrutinas | `subrutina` (incluido `main`), `parametro`, `llamada` (valor), `llamar` (instrucción), `retornar`, `lambda` (función anónima con su pila) |
| Clases y objetos | `clase` (abstracta, genérica, `hereda`, `implementa`), `interfaz`, `atributo`, `metodo` (con o sin cuerpo), `constructor`, `nuevo`, `propiedad` (`o.x`, `o?.x`), `llamada_metodo`, `este`, `padre`, `llamar_padre`, `enumeracion` + `miembro_enum` |
| Arreglos | `arreglo` (1D/2D/3D, `tipo[3] v` o `tipo v[3]`, constante, valores o `fila`s), `fila`, `indice` (`a[i]`), `nuevo_arreglo` |
| Módulos | `importar` |

## Encaje al soltar (validación tipada)

`reglas.motivo_rechazo(modelo, bloque, padre, ranura)` dice por qué un bloque
**no** puede ir en un sitio (o `None`). Lo usan la edición, la GUI mientras se
arrastra y la colocación con teclado:

* **Familia de lista**: en una pila sólo instrucciones; en `miembros` sólo
  atributos, métodos y constructores; en el programa sólo definiciones y
  declaraciones globales; en el inicio de `para` una declaración o una
  asignación… y el máximo de la lista (`para` admite un solo inicio).
* **Forma del hueco**: `asignable` (variable, `a[i]`, `obj.campo`), `llamada`,
  `variable`; un hueco nunca admite una instrucción.
* **Tipos**: inferencia prudente de familias (`entero`, `real`, `texto`,
  `logico`, `nulo`, `arreglo`, `objeto`, `funcion`, `cualquiera`) con las
  **mismas reglas que `type_checker.py`**: la condición debe ser lógica; `%` y
  los operadores de bits sólo con enteros; `+` suma números o une textos, sin
  mezclarlos; `<` compara números; a un `entero` no se le asigna un `real` (al
  revés sí); `nulo` sólo vale para objetos. Las variables se buscan en su
  ámbito (parámetros, declaraciones, atributos para `este.x`, globales). Sólo
  se rechaza cuando ambas familias se conocen; en la duda decide el compilador
  en `validar`. `tests/bloques/test_bloques_reglas.py` comprueba que cada
  veredicto coincide con el del compilador.
* `romper` fuera de un ciclo o de un `segun` y `continuar` fuera de un ciclo
  (mismos mensajes que el diagrama de flujo).

Ejemplo: «No encaja: «condición» de «mientras» espera un valor lógico
(verdadero/falso) y este bloque da un número entero.» / «Does not fit:
«condition» of «while» expects a boolean (true/false) and this block gives an
integer.»

## Edición pura

Todas devuelven un modelo **nuevo** (la GUI guarda los anteriores para
deshacer y rehacer) o lanzan `ErrorBloques` con el motivo bilingüe:

| Operación | Qué hace |
|---|---|
| `nuevo_bloque(tipo, idioma, **campos)`, `desde_paleta(clave, idioma)` | crea un bloque con sus campos validados (un `si` nace con su primera rama) |
| `insertar(m, bloque, Destino(padre, parte, indice))` | en una lista o en un hueco; sobre un hueco ocupado, si el bloque nuevo tiene un hueco libre compatible el anterior pasa a él (soltar «+» sobre `x` da `x + _`), como en Blockly |
| `mover(m, id, destino)` | nunca dentro de sí mismo; el índice cuenta ya sin el bloque |
| `eliminar`, `duplicar` | quitar (un hueco queda vacío) / copiar con ids nuevos justo detrás |
| `envolver(m, ids, tipo)` | bloques consecutivos dentro de un `si`, `mientras`, `para`, `intentar`… |
| `editar(m, id, campo, valor)` | campo validado con el lexer real; no deja apagar una bandera que esconde bloques ni dejar un valor que ya no encaja donde está |
| `validar(m)` | estructura, campos, tipos y compilación del programa generado; cada diagnóstico se cuelga del bloque que lo causó |

## Panel «Bloques» de la GUI Qt

Menú *Ejecutar › Editor de bloques* (o *Ver › Bloques*):

* **Lienzo** `QGraphicsView` con la geometría de `diseno.py`. Cada categoría
  tiene color, **icono** y la **silueta** de su forma (muesca de pila, «C»,
  sombrero, valor redondeado, lógico hexagonal): el color nunca es la única
  pista. Los bloques con problemas llevan borde discontinuo rojo y el motivo
  en su descripción.
* **Arrastrar y soltar** desde la paleta, entre sitios del lienzo y a la
  **papelera**; mientras se arrastra, la zona se marca en verde o en rojo con
  el motivo en la barra de estado.
* **Teclado** (todo lo que se hace con el ratón): ↑/↓ recorren los bloques en
  orden de lectura, ← va al padre y → al primer hijo; `Intro`/`F2` edita los
  campos; `M` recoge el bloque y las flechas eligen el destino entre las
  **mismas zonas** que usa el ratón, `Intro` suelta y `Escape` cancela;
  `Insert` lleva al buscador de la paleta e `Intro` sobre una entrada empieza
  a colocarla; `Supr` borra; `Ctrl+D` duplica; `Ctrl+Z`/`Ctrl+Y` deshacer y
  rehacer; `Ctrl++`/`Ctrl+-`/`Ctrl+0` zoom (también `Ctrl`+rueda);
  `Mayús+F10` abre el menú del bloque (envolver, mover…). Cada foco y cada
  cambio se **anuncia** al lector de pantalla (`QAccessibleAnnouncementEvent`)
  con el tipo, el contenido y el lugar («En cuerpo de mientras, 2 de 3»).
* **Sincronía**: con «Sincronizar con el editor», cada cambio válido de los
  bloques reescribe el editor (una sola edición deshacible) y editar el código
  recarga los bloques en vivo; elegir un bloque lleva el cursor a su línea y
  su caja al **diagrama de flujo**, y los cambios del diagrama llegan a los
  bloques (mismo árbol, mismos ids).
* **Ejecutar** (con entrada) y **Paso a paso**: el Visualizador traza el
  programa de los bloques y en cada paso se resalta el bloque que se ejecuta.
* Abrir y guardar JSON v1, idioma de los bloques es/en, temas claro y oscuro.

## Accesibilidad

* Contraste del texto de cada bloque ≥ 7:1 (AAA) con su relleno en ambos
  temas y borde ≥ 3:1 con el lienzo (lo prueba
  `test_bloques_modelo.py::test_colores_accesibles_y_nunca_solo_color`).
* Forma + icono + texto, nunca sólo color; foco visible (marco discontinuo
  grueso).
* Alternativa textual completa: `describir` (CLI `bloques --texto`) y los
  anuncios del panel dicen lo mismo que el lienzo.

---

## English summary

InvenioLang programs can be **built with blocks** (Scratch/Blockly style) in
Spanish or English, covering the whole language (declarations, nestable
expressions with typed slots, I/O, control flow, subroutines and anonymous
functions, classes with attributes, methods, constructors, inheritance,
interfaces and generics, enums, arrays/matrices and `import`). For every
exercise in `curriculum/es` and `curriculum/en`, code → blocks → code in both
languages compiles and prints exactly the expected output — this is tested.

* **Same tree as the flowchart**: blocks reuse `inveniolang/flujo` (extraction
  and code generation); each block statement keeps the id of its flowchart
  box, so both views select each other.
* **CLI**: `inveniolang bloques file.inv [--json f] [--texto] [--catalogo f]
  [--idioma es|en]` and `inveniolang desde-bloques blocks.json [--idioma es|en]
  [-o file.inv]` (aliases `blocks`, `from-blocks`).
* **API**: `api.bloques(code, "json"|"texto")`, `api.codigo_desde_bloques(model,
  idioma)`, `api.catalogo_bloques(idioma)`.
* **JSON v1** (`"formato": "inveniolang-bloques"`): every block is
  `{id, tipo, linea, campos, huecos, listas}` with exactly the catalogue's keys;
  exact round trip; keyword-valued fields stored in neutral (canonical
  Spanish) form; invalid JSON is rejected with the data path. The catalogue
  (`"formato": "inveniolang-bloques-catalogo"`) describes every block type,
  list family, category (icon and colours) and palette entry.
* **Typed drop validation** with the same rules as the type checker (boolean
  conditions, `%` on integers, no string/number mixing…), structural rules
  (which blocks fit in each list, maximum sizes, `break`/`continue`
  placement), with bilingual explanations.
* **Pure editing**: insert (Blockly-style bump into a free compatible slot),
  move, delete, duplicate, wrap, edit a field, and full validation with the
  real compiler.
* **Qt "Blocks" panel**: real drag and drop (palette, canvas, trash), complete
  keyboard operation using the same drop zones as the mouse, screen-reader
  announcements, undo/redo, zoom, live sync with the code editor and the
  flowchart panel, run and step-by-step visualisation from the blocks.
* **Accessible palette**: category colour + icon + shape, text contrast ≥ 7:1.
