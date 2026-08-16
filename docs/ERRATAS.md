# Fe de Erratas — Especificacion de InvenioLang 1.0

**Curso:** TIIT2002.2 Lenguajes Formales II
**Universidad:** Invenio — TICEC
**Estado:** aplicada en la implementacion de referencia

Este documento registra las contradicciones internas detectadas en la
especificacion (`docs/InvenioLang_Seccion*.docx`) y la resolucion adoptada en
cada caso. Segun la Seccion 18.2, una correccion de especificacion que no altera
la semantica **no incrementa el numero de version**: InvenioLang sigue siendo 1.0.

Cada errata indica las secciones en conflicto, la resolucion, y que secciones del
documento deben corregirse en la proxima revision.

---

## E-01 — La palabra reservada `retornar`

| | |
|---|---|
| **En conflicto** | §2.5.2 y Apendice E.3 la usan · §16.11, Apendice A y §18.3.1 la niegan |
| **Resolucion** | **`retornar` ES palabra reservada en InvenioLang 1.0**, sinonimo exacto de `return` |
| **Corregir** | §16.11, Apendice A y §18.3.1 |

§2.5.2 lista `retornar` en la tabla de palabras reservadas en espanol, con token
interno `KW_RETURN`. El Apendice E.3 la utiliza en un programa presentado como
«integramente en espanol». Sin embargo §16.11 afirma que «no tiene equivalente en
espanol», el Apendice A la marca como «(sin equiv.)» y §18.3.1 la lista como
candidata para la version 1.1.

Se resuelve a favor de §2.5.2 por dos razones. Primera: el bilinguismo completo es
un principio de diseno declarado en §1 y §2.5, y sin `retornar` ningun programa con
funciones puede escribirse integramente en espanol. Segunda: sin ella, el programa
del Apendice E.3 no compila, lo que contradice su propio encabezado «— VALIDO».

`return` sigue siendo valida y ambas formas producen el mismo token, conforme a la
regla general de §2.5.3.

---

## E-02 — Sintaxis de declaracion de arreglos y matrices

| | |
|---|---|
| **En conflicto** | §16.5, §17.7, §17.8, §17.9 usan la forma prefija · §17.3 usa la postfija |
| **Resolucion** | **Ambas formas son validas.** La prefija es canonica; la postfija emite `IL-WARN-040` |
| **Corregir** | §16.5 (anadir la forma postfija) y §15.7 (anadir `IL-WARN-040`) |

La gramatica de §16.5 define `⟨decl_arreglo⟩ ::= ⟨tipo⟩ "[" ⟨tam⟩ "]" IDENTIFICADOR`
y los programas de referencia §17.7, §17.8 y §17.9 la respetan (`int [N] datos`).
El programa §17.3 declara en cambio `float temps[5] = {…}`, en el estilo de C.

Como §18.1 declara que los programas de la Seccion 17 son casos de prueba
permanentes y deben producir exactamente la salida especificada, un programa de
referencia que no compila es un defecto de la especificacion. Se admiten ambas
formas para que los diecisiete programas de referencia compilen tal como estan
impresos.

La forma postfija emite la advertencia **`IL-WARN-040` — Declaracion postfija**,
que no impide la compilacion y recomienda la forma canonica. Es un codigo nuevo,
adicion compatible hacia atras segun §18.2.

---

## E-03 — Division real entre cero

| | |
|---|---|
| **En conflicto** | §4.3 y §15.6 asignan `IL-EJE-002` · §6.6.4 asigna `IL-EJE-006` |
| **Resolucion** | **La division real produce `IL-EJE-002`; la entera, `IL-EJE-006`** |
| **Corregir** | §6.6.4 |

§4.3 establece que una operacion de punto flotante que produzca un valor especial
de IEEE 754 genera `IL-EJE-002`, y §15.6 lo confirma con el ejemplo `1.0 / 0.0`.
§6.6.4 dice en cambio que «la division entera **o real** entre cero» produce
`IL-EJE-006`.

Se resuelve a favor de §4.3 y §15.6 porque distinguir ambos casos aporta
informacion al estudiante —la division entera y el desbordamiento de punto
flotante son fenomenos distintos— y porque de otro modo `IL-EJE-002` quedaria sin
ningun caso alcanzable, contradiciendo su presencia en el catalogo normativo.

El operador `%` mantiene `IL-EJE-006`, ya que §4.3 solo lo define para enteros.

---

## E-04 — Codigos ausentes del catalogo de §15.4

| | |
|---|---|
| **En conflicto** | `IL-SEM-010`, `IL-SEM-080` e `IL-SEM-081` se definen fuera del catalogo |
| **Resolucion** | **Los tres son normativos** y deben integrarse en §15.4 |
| **Corregir** | §15.4 |

- `IL-SEM-010` (literal entero fuera de rango) se define en §2.6 y §4.2.1.
- `IL-SEM-080` (redefinicion de funcion integrada) se define en §19.11.
- `IL-SEM-081` (argumento incompatible en funcion integrada) se define en §19.11.

§18.1 declara que «los codigos de error del catalogo de la Seccion 15 son
estables» y sirven «como referencia comun para docentes, estudiantes y
herramientas de evaluacion automatica». Un codigo normativo que no figura en el
catalogo no puede cumplir esa funcion. Los tres estan implementados.

---

## E-05 — `IL-SEM-051` no tiene caso alcanzable

| | |
|---|---|
| **En conflicto** | §15.4 lo ilustra con `void f() { return 1; }`, que es un procedimiento |
| **Resolucion** | **Retirar `IL-SEM-051` del catalogo**; el caso corresponde a `IL-SEM-061` |
| **Corregir** | §15.4 y §10.2 |

§15.4 describe `IL-SEM-051` como «funcion declarada con void como tipo de retorno»
y lo ejemplifica con `void f() { return 1; }`. Pero la gramatica de §16.8 y §16.9
distingue funcion de procedimiento precisamente por el tipo de retorno: una
subrutina declarada `void` **es** un procedimiento, no una funcion con tipo
invalido. El error real de ese ejemplo es el `return` con valor dentro de un
procedimiento, que ya cubre `IL-SEM-061` (§11.5).

No existe forma de escribir una «funcion con tipo de retorno void» en la gramatica
1.0, por lo que el codigo es inalcanzable por construccion.

---

## E-06 — `IL-SIN-033` es ambiguo con la gramatica

| | |
|---|---|
| **En conflicto** | §8.2 define «instruccion entre then y else» como error propio |
| **Resolucion** | **El caso se reporta como `IL-SIN-032`**; `IL-SIN-033` queda sin uso |
| **Corregir** | §15.3 |

Detectar `IL-SIN-033` requiere una produccion de la forma
`if "(" expr ")" bloque instruccion "else" bloque`, que es ambigua con el patron
«`if` sin `else` seguido de otra instruccion» —el mas frecuente del lenguaje— y
provoca un conflicto *reduce/reduce* que hace fallar programas validos. Se
verifico experimentalmente: con esa produccion, seis de los doce programas de
referencia de §17 dejan de compilar.

Un `else` separado de su `if` por una instruccion se reporta como
`IL-SIN-032` (clausula `else` sin `if` previo), que es un diagnostico correcto y
util para el estudiante.

---

## E-07 — `IL-LEX-005` con el guion

| | |
|---|---|
| **En conflicto** | §2.4.3 marca `mi-variable` como `IL-LEX-005` |
| **Resolucion** | **Retirar ese ejemplo**; `-` es el operador de resta |
| **Corregir** | §2.4.3 |

§2.4.3 lista `mi-variable // INVALIDO — IL-LEX-005: contiene guion` entre los
identificadores mal formados. Pero `-` es el operador de resta de §2.10.1: la
secuencia `mi-variable` es lexicamente indistinguible de `a - b`, y rechazarla
haria imposible escribir cualquier resta entre identificadores.

El resto de `IL-LEX-005` (la letra `ñ`, caracteres acentuados y demas simbolos
fuera de ASCII) funciona correctamente. Solo el subcaso del guion es irrealizable.

---

## E-08 — Nomenclatura de las funciones integradas

| | |
|---|---|
| **En conflicto** | §4.8 y Apendice E.2 usan nombres abreviados · §19.2 declara otros normativos |
| **Resolucion** | **Las tres nomenclaturas son validas y equivalentes** (24 nombres) |
| **Corregir** | §4.8 y Apendice E.2 (nota de equivalencia) |

§4.8 y el Apendice E.2 usan `int_a_float`, `texto_a_int`, etc., y enumeran siete
funciones. §19.2 declara normativos `int_to_float` / `entero_a_real` y define
ocho, anadiendo `string_to_bool` / `texto_a_logico`. El propio §19.2 reconoce la
discrepancia y mantiene los nombres abreviados «como sinonimos validos».

La implementacion registra los 24 nombres (8 funciones × 3 nomenclaturas) como
alias indistinguibles, que es la unica lectura que satisface a ambas secciones.

Nota menor: el Apendice E.2 dice «las seis funciones de conversion integradas»
mientras enumera siete. Son ocho.

---

## E-09 — Formato del reporte de errores

| | |
|---|---|
| **En conflicto** | §15.8.1 usa raya (`—`); la implementacion previa usaba guion (`-`) |
| **Resolucion** | **Se adopta la raya de §15.8.1** |
| **Corregir** | nada; era un defecto de implementacion |

Se registra aqui porque afecta a cualquier comparacion automatica de salidas entre
implementaciones, que es justamente el proposito declarado del formato normalizado
de §15.8.

---

## E-10 — Ejemplo contradictorio en §3.5.2

| | |
|---|---|
| **En conflicto** | §3.5.2 marca «INVALIDO — IL-SEM-003» un programa cuyo propio comentario dice «VALIDO» |
| **Resolucion** | **El programa es valido**: las subrutinas se registran antes de analizar sus cuerpos |
| **Corregir** | §3.5.2 |

El primer bloque de §3.5.2 presenta un programa que llama a `calcular` desde
`main` con `calcular` definida despues, lo etiqueta «INVALIDO — IL-SEM-003», y
sin embargo el comentario dentro del propio codigo dice «VALIDO: calcular
declarado antes del main». El segundo bloque muestra el mismo programa con el
orden invertido y lo etiqueta «VALIDO».

La implementacion registra todas las funciones y procedimientos en la tabla de
simbolos antes de visitar sus cuerpos, de modo que ambos ordenes son validos. Esto
es ademas lo que exige §3.2 al decir que «main podria declararse en cualquier
posicion del archivo».

---

## Resumen de codigos afectados

| Codigo | Estado tras las erratas |
|--------|-------------------------|
| `IL-EJE-002` | Activo — division real entre cero (E-03) |
| `IL-EJE-006` | Activo — division entera entre cero y modulo (E-03) |
| `IL-SEM-010` | Activo — integrar en el catalogo §15.4 (E-04) |
| `IL-SEM-051` | **Retirado** — inalcanzable por construccion (E-05) |
| `IL-SEM-080` | Activo — integrar en el catalogo §15.4 (E-04) |
| `IL-SEM-081` | Activo — integrar en el catalogo §15.4 (E-04) |
| `IL-SIN-033` | **Retirado** — cubierto por `IL-SIN-032` (E-06) |
| `IL-WARN-040` | **Nuevo** — declaracion postfija de arreglo o matriz (E-02) |

Con estas resoluciones el catalogo queda **completo**: todos los codigos vigentes
tienen al menos un caso alcanzable, y la suite `pruebas/conformidad.py` ejercita
cada uno.
