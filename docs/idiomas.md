# InvenioLang bilingüe: español e inglés

InvenioLang se puede **escribir** y **leer** en español o en inglés. Las dos
cosas son independientes: un programa con `si`/`mientras` puede compilarse con
los diagnósticos en inglés, y uno con `if`/`while`, con los diagnósticos en
español.

## 1. Palabras clave y funciones integradas

Cada palabra clave existe en ambos idiomas y produce el mismo token
(`si`/`if`, `mientras`/`while`, `clase`/`class`, `importar`/`import`, ...;
lista completa en `inveniolang/lexer.py`). Las funciones integradas también
(tabla `BUILT_INS_BILINGUES` de `inveniolang/builtins.py`): cada fila es **una**
implementación con su nombre en español, su nombre en inglés y, si los hay,
alias históricos.

| Español | Inglés | Notas |
|---|---|---|
| `entero_a_real`, `real_a_entero`, `entero_a_texto`, `real_a_texto`, `texto_a_entero`, `texto_a_real`, `logico_a_texto`, `texto_a_logico` | `int_to_float`, `float_to_int`, `int_to_string`, ... | alias §4: `int_a_float`, ... |
| `longitud_texto`, `subcadena`, `mayusculas`, `minusculas`, `caracter_en`, `indice_de`, `recortar`, `invertir_texto` | `text_length`, `substring`, `to_upper`, `to_lower`, `char_at`, `index_of`, `trim`, `reverse_string` | |
| `raiz_cuadrada`, `elevar`, `absoluto`, `piso`, `techo`, `azar` | `sqrt`, `pow`, `abs`, `floor`, `ceil`, `random` | |
| `absoluto_real`, `redondear` | `fabs`, `round` | nuevas (INV-1410); `redondear(2.5)` = 3, `redondear(-2.5)` = -3 |
| `longitud_arreglo` | `array_length` | nueva (INV-1410): elementos de un arreglo (filas si es matriz) |
| `lanzar_error(texto)` | `throw_error(string)` | nueva (INV-1410): IL-EJE-060, capturable con `intentar`/`capturar` |
| `existe_archivo`, `leer_archivo`, `escribir_archivo`, `agregar_archivo` | `file_exists`, `read_file`, `write_file`, `append_file` | |
| `reducir`, `mapear`, `filtrar` | `reduce`, `map`, `filter` | orden superior |

La variable de un `capturar (e)` tiene los campos `e.codigo`/`e.mensaje` y sus
equivalentes `e.code`/`e.message`.

## 2. Idioma de los mensajes

Todos los diagnósticos del catálogo (`IL-XXX-NNN`), los mensajes de ejecución
que recibe un `capturar`, las explicaciones pedagógicas y los textos del CLI
salen de un **catálogo central** (`inveniolang/i18n/`):

* `es.py` y `en.py`: `clave -> plantilla` (misma clave, mismos marcadores);
* cada idioma es una *Strategy* (`CatalogoIdioma`) registrada en un
  *Registry* (`RegistroIdiomas`): añadir un idioma es registrar otro
  diccionario;
* el código que detecta un error crea un `Mensaje` diferido con
  `M("IL-SEM-003.funcion_no_encontrada", nombre=...)`; el idioma lo decide
  quien presenta el error, no quien lo detecta.

Cómo elegir el idioma (de mayor a menor prioridad):

| Dónde | Cómo |
|---|---|
| CLI | `python -m inveniolang.cli programa.inv --idioma en` |
| API | `compile_pure(request, idioma="en")` |
| `ErrorManager` | `ErrorManager(idioma="en")` |
| Todo el proceso | variable de entorno `INVENIO_IDIOMA=en` (acepta `en_US.UTF-8`; un valor desconocido se ignora y se usa `es`) |

`tests/test_i18n.py` verifica que ningún idioma carece de una clave, que los
marcadores coinciden y que ningún diagnóstico se escribe como texto literal.

## 3. Traductor de código fuente

```
python -m inveniolang.cli traducir programa.inv --a en
python -m inveniolang.cli traducir programa.inv --a es --salida programa_es.inv
```

Traduce **por tokens** (`inveniolang/traductor.py`): reescribe solo palabras
clave, llamadas a funciones integradas y `e.codigo`/`e.mensaje` dentro de un
`capturar`; comentarios, literales, espacios y nombres del estudiante se
copian sin cambios. El resultado es el mismo programa (misma secuencia de
tokens, misma salida). Traducir a `es` normaliza además los programas que
mezclan idiomas (`void main` → `vacio main`); una segunda traducción ya no
cambia nada (punto fijo). `tests/test_traductor.py` lo comprueba con todos los
programas de `pruebas/` y del currículo.

Reglas con contexto: `abstract` se traduce `abstracta` delante de `clase` y
`abstracto` delante de un método; un identificador igual a una función
integrada solo se traduce si es una llamada que no es `obj.metodo(` ni la
declaración de un método.
