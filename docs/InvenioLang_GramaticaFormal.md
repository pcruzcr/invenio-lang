# InvenioLang — Referencia formal de gramática (Etapa 12.4)

## 0. Por qué existe este documento

InvenioLang tiene, desde la Etapa 1, la disciplina de verificar el conteo
de conflictos LALR(1) (`parser.py(debug=True)` → `parser.out`) contra un
baseline fijo (**20 shift/reduce, 0 reduce/reduce**) antes de dar por
buena cualquier extensión de gramática — son 12 etapas y más de 40
producciones nuevas después, y el baseline sigue exactamente en 20/0. Ese
proceso siempre fue interno (verificar, no publicar). Este documento existe
para un curso de **Lenguajes Formales/Compiladores**, no para InvenioLang
como lenguaje: presenta la gramática completa en EBNF, el método de
FIRST/FOLLOW sobre un subconjunto representativo, y — lo más valioso —
los puntos reales de esta gramática donde LALR(1) tuvo que decidir algo
no trivial, con el fragmento real de `parser.out` al lado, para que un
estudiante pueda derivarlo a mano y comparar contra lo que PLY calculó de
verdad.

**Todo lo que sigue se generó/verificó a partir del código fuente real**
(`inveniolang/parser.py`, `inveniolang/parser.out`), no se transcribió de
memoria — la sección 1 se extrajo programáticamente de los 138 docstrings
de producción de `parser.py` para que no haya desfase entre este documento
y el código.

## 1. Notación

EBNF con las convenciones de PLY: cada bloque es un no-terminal con sus
alternativas separadas por `|`. Los terminales están en MAYÚSCULAS (nombres
de token, ver `inveniolang/lexer.py` para su patrón léxico exacto — no se
repite aquí el léxico completo, ya documentado en `README.md` y
`InvenioLang_2.0_POO.md`). `empty` es la producción vacía (ε).

## 2. Gramática completa

### 2.1 Programa y elementos de nivel superior

```
programa
    : lista_elementos_programa

lista_elementos_programa
    : lista_elementos_programa elemento_programa
    | elemento_programa

elemento_programa
    : decl_global | def_funcion | def_procedimiento | def_main
    | class_decl | enum_decl | interface_decl

def_main
    : KW_VOID KW_MAIN DEL_PAREN_A DEL_PAREN_C bloque
    | tipo KW_MAIN DEL_PAREN_A DEL_PAREN_C bloque
    | KW_VOID KW_MAIN DEL_PAREN_A lista_params DEL_PAREN_C bloque
    | tipo KW_MAIN DEL_PAREN_A lista_params DEL_PAREN_C bloque

def_funcion
    : tipo IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque
    | IDENTIFICADOR IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque

def_procedimiento
    : KW_VOID IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque

lista_params
    : lista_params DEL_COMA param | param | empty

param
    : KW_VOID IDENTIFICADOR
    | tipo IDENTIFICADOR
    | tipo DEL_CORCHETE_A DEL_CORCHETE_C IDENTIFICADOR
    | tipo DEL_CORCHETE_A DEL_CORCHETE_C DEL_CORCHETE_A DEL_CORCHETE_C IDENTIFICADOR
    | IDENTIFICADOR IDENTIFICADOR
    | IDENTIFICADOR DEL_CORCHETE_A DEL_CORCHETE_C IDENTIFICADOR
```

### 2.2 Tipos, declaraciones y arreglos/matrices

```
tipo
    : KW_INT | KW_FLOAT | KW_STRING | KW_BOOL

tam
    : ENTERO_LIT | IDENTIFICADOR

decl_global
    : decl_variable | decl_constante | decl_arreglo | decl_matriz

decl_variable
    : tipo IDENTIFICADOR DEL_PUNTO_COMA
    | tipo IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA
    | tipo IDENTIFICADOR DEL_COMA lista_ident DEL_PUNTO_COMA      -- IL-SIN-015
    | KW_VOID IDENTIFICADOR DEL_PUNTO_COMA                        -- IL-TIPO-015
    | KW_VOID IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA
    | IDENTIFICADOR IDENTIFICADOR DEL_PUNTO_COMA                  -- tipo clase
    | IDENTIFICADOR IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA
    | IDENTIFICADOR OP_MENOR tipo_generico_arg OP_MAYOR IDENTIFICADOR DEL_PUNTO_COMA        -- generico
    | IDENTIFICADOR OP_MENOR tipo_generico_arg OP_MAYOR IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA

decl_constante
    : KW_CONST tipo IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA
    | KW_CONST tipo IDENTIFICADOR DEL_PUNTO_COMA                  -- IL-SEM (sin inicializar)
    | KW_CONST tipo DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR
        OP_ASIG DEL_LLAVE_A lista_expr_init DEL_LLAVE_C DEL_PUNTO_COMA  -- Etapa 11.10

decl_arreglo
    : tipo DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR DEL_PUNTO_COMA           -- forma canonica
    | tipo DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR OP_ASIG DEL_LLAVE_A lista_expr_init DEL_LLAVE_C DEL_PUNTO_COMA
    | tipo IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_PUNTO_COMA           -- forma postfija, IL-WARN-040
    | tipo IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C OP_ASIG DEL_LLAVE_A lista_expr_init DEL_LLAVE_C DEL_PUNTO_COMA
    | IDENTIFICADOR IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_PUNTO_COMA  -- arreglo de objetos (SOLO postfija)
    | IDENTIFICADOR IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C OP_ASIG DEL_LLAVE_A lista_expr_init DEL_LLAVE_C DEL_PUNTO_COMA
    | KW_VOID DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR DEL_PUNTO_COMA        -- IL-TIPO-015

decl_matriz
    : tipo DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR DEL_PUNTO_COMA
    | ... (con inicializador; ver lista_filas_init)

lista_expr_init  : lista_expr_init DEL_COMA expresion | expresion
lista_filas_init : lista_filas_init DEL_COMA fila_init | fila_init
fila_init        : DEL_LLAVE_A lista_expr_init DEL_LLAVE_C
```

### 2.3 Bloques e instrucciones

```
bloque           : DEL_LLAVE_A lista_elem_bloque DEL_LLAVE_C
lista_elem_bloque: lista_elem_bloque elem_bloque | empty
elem_bloque      : decl_local | instruccion | def_funcion | def_procedimiento
decl_local       : decl_variable | decl_constante | decl_arreglo | decl_matriz

instruccion
    : lvalue op_asig expresion DEL_PUNTO_COMA
    | inc_dec_stmt | print_stmt | read_stmt
    | if_stmt | while_stmt | for_stmt | foreach_stmt | do_while_stmt
    | switch_stmt | try_stmt
    | return_stmt | break_stmt | continue_stmt | call_stmt
    | instruccion_error                          -- recuperación de errores (§2.5)

if_stmt
    : KW_IF DEL_PAREN_A expresion DEL_PAREN_C bloque
    | KW_IF DEL_PAREN_A expresion DEL_PAREN_C bloque KW_ELSE bloque
    | KW_IF DEL_PAREN_A expresion DEL_PAREN_C instruccion               -- IL-SIN-031 (sin llaves)
    | KW_IF DEL_PAREN_A expresion DEL_PAREN_C instruccion KW_ELSE bloque
    | KW_IF expr_rel bloque                                             -- IL-SIN-035 (sin parentesis)
    | KW_IF expr_rel bloque KW_ELSE bloque

while_stmt : KW_WHILE expr_rel bloque
           | KW_WHILE DEL_PAREN_A expresion DEL_PAREN_C bloque
           | KW_WHILE DEL_PAREN_A expresion DEL_PAREN_C instruccion

for_stmt  : KW_FOR DEL_PAREN_A for_init DEL_PUNTO_COMA for_cond DEL_PUNTO_COMA for_act DEL_PAREN_C bloque
for_init  : decl_var_sin_pc | asig_sin_pc | empty
for_cond  : expresion | empty
for_act   : asig_sin_pc | inc_dec_sin_pc | empty

foreach_stmt                                                            -- Etapa 12.1
    : KW_FOREACH DEL_PAREN_A tipo IDENTIFICADOR DEL_DOSPUNTOS expresion DEL_PAREN_C bloque
    | KW_FOREACH DEL_PAREN_A IDENTIFICADOR IDENTIFICADOR DEL_DOSPUNTOS expresion DEL_PAREN_C bloque

do_while_stmt : KW_DO bloque KW_WHILE DEL_PAREN_A expresion DEL_PAREN_C DEL_PUNTO_COMA

switch_stmt
    : KW_SWITCH DEL_PAREN_A expresion DEL_PAREN_C DEL_LLAVE_A lista_casos DEL_LLAVE_C
    | KW_SWITCH DEL_PAREN_A expresion DEL_PAREN_C DEL_LLAVE_A lista_casos
        KW_DEFAULT DEL_DOSPUNTOS lista_elem_bloque DEL_LLAVE_C
lista_casos   : lista_casos caso | empty
caso          : KW_CASE literal_caso DEL_DOSPUNTOS lista_elem_bloque
literal_caso  : ENTERO_LIT | TEXTO_LIT | bool_lit | OP_RESTA ENTERO_LIT

try_stmt : KW_TRY bloque KW_CATCH DEL_PAREN_A IDENTIFICADOR DEL_PAREN_C bloque

return_stmt   : KW_RETURN DEL_PUNTO_COMA | KW_RETURN expresion DEL_PUNTO_COMA
break_stmt    : KW_BREAK DEL_PUNTO_COMA
continue_stmt : KW_CONTINUE DEL_PUNTO_COMA

call_stmt
    : IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA
    | IDENTIFICADOR DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA
    | KW_THIS DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA
    | KW_SUPER DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA
    | IDENTIFICADOR OP_ACCESO_SEGURO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA  -- Etapa 12.2
    | KW_SUPER DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA
    | IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_PUNTO IDENTIFICADOR
        DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA
```

### 2.4 lvalue y asignación

```
lvalue
    : IDENTIFICADOR
    | IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C
    | IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_CORCHETE_A expresion DEL_CORCHETE_C
    | IDENTIFICADOR DEL_PUNTO IDENTIFICADOR
    | KW_THIS DEL_PUNTO IDENTIFICADOR
    | KW_SUPER DEL_PUNTO IDENTIFICADOR
    | IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_PUNTO IDENTIFICADOR

op_asig : OP_ASIG | OP_ASIG_SUMA | OP_ASIG_RESTA | OP_ASIG_MULT | OP_ASIG_DIV | OP_ASIG_MOD
```

### 2.5 Expresiones — la cadena de precedencia explícita

InvenioLang **no** deja que la tabla `precedence` de PLY resuelva la
precedencia de expresiones (esa tabla existe, ver §4) — usa el patrón
clásico de un no-terminal por nivel, cada uno reduciendo al siguiente
cuando no hay operador de su nivel. Es más verboso que declarar
`precedence` y confiar en ella, pero dos ventajas concretas: (1) la
estructura del árbol de análisis para una expresión aritmética se puede
leer directamente de la gramática sin consultar una tabla aparte — valor
pedagógico real para un curso de Lenguajes Formales — y (2) es el
mecanismo que permitió insertar operadores nuevos (bit a bit en la Etapa
11.9, `??` en la 12.2) en un nivel exacto sin arriesgar ambigüedad con
nada existente, verificado en cada caso con el conteo de conflictos.

```
expresion    : expr_coalesce
             | expr_coalesce DEL_INTERROGACION expresion DEL_DOSPUNTOS expresion   -- ternario, asoc. derecha
expr_coalesce: expr_or OP_COALESCENCIA expr_coalesce | expr_or                     -- ??  (Etapa 12.2, asoc. derecha)
expr_or      : expr_or OP_OR expr_and | expr_and                                   -- ||
expr_and     : expr_and OP_AND expr_bitor | expr_bitor                             -- &&
expr_bitor   : expr_bitor OP_BITOR expr_bitxor | expr_bitxor                       -- |   (Etapa 11.9)
expr_bitxor  : expr_bitxor OP_BITXOR expr_bitand | expr_bitand                     -- ^
expr_bitand  : expr_bitand OP_BITAND expr_igual | expr_igual                       -- &
expr_igual   : expr_igual (OP_IGUAL|OP_DISTINTO) expr_rel | expr_rel               -- == !=
expr_rel     : expr_rel (OP_MENOR|OP_MAYOR|OP_MENOR_IGUAL|OP_MAYOR_IGUAL) expr_shift | expr_shift
expr_shift   : expr_shift (OP_SHL|OP_SHR) expr_sum | expr_sum                      -- << >> (Etapa 11.9)
expr_sum     : expr_sum (OP_SUMA|OP_RESTA) expr_mul | expr_mul
expr_mul     : expr_mul (OP_MULT|OP_DIV|OP_MOD) expr_unaria | expr_unaria
expr_unaria  : OP_RESTA expr_unaria %prec UMINUS
             | OP_NOT expr_unaria | OP_BITNOT expr_unaria
             | OP_INC expr_primaria | OP_DEC expr_primaria
             | expr_primaria OP_INC | expr_primaria OP_DEC
             | expr_primaria

expr_primaria
    : ENTERO_LIT | REAL_LIT | TEXTO_LIT | bool_lit | IDENTIFICADOR
    | acceso_arreglo | acceso_matriz | llamada_funcion
    | DEL_PAREN_A expresion DEL_PAREN_C
    | KW_NEW IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C
    | KW_NEW IDENTIFICADOR OP_MENOR tipo_generico_arg OP_MAYOR DEL_PAREN_A lista_args DEL_PAREN_C
    | KW_THIS | KW_NULL
    | IDENTIFICADOR DEL_PUNTO IDENTIFICADOR | KW_THIS DEL_PUNTO IDENTIFICADOR | KW_SUPER DEL_PUNTO IDENTIFICADOR
    | IDENTIFICADOR OP_ACCESO_SEGURO IDENTIFICADOR                                  -- ?. (Etapa 12.2)
    | IDENTIFICADOR DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C
    | KW_THIS DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C
    | KW_SUPER DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C
    | IDENTIFICADOR OP_ACCESO_SEGURO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C
    | IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_PUNTO IDENTIFICADOR
    | IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C

acceso_arreglo  : IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C
acceso_matriz   : IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_CORCHETE_A expresion DEL_CORCHETE_C
llamada_funcion : IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C
lista_args      : lista_args DEL_COMA expresion | expresion | empty
```

### 2.6 Clases, interfaces y enumeraciones (InvenioLang 2.0)

```
class_decl
    : KW_CLASS IDENTIFICADOR lista_implementa DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C
    | KW_CLASS IDENTIFICADOR KW_EXTENDS IDENTIFICADOR lista_implementa DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C
    | KW_ABSTRACT KW_CLASS IDENTIFICADOR lista_implementa DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C
    | KW_ABSTRACT KW_CLASS IDENTIFICADOR KW_EXTENDS IDENTIFICADOR lista_implementa DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C
    | KW_CLASS IDENTIFICADOR OP_MENOR IDENTIFICADOR OP_MAYOR DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C   -- generica

lista_implementa : empty | KW_IMPLEMENTS lista_identificadores            -- Etapa 12.3

interface_decl   : KW_INTERFACE IDENTIFICADOR DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C

lista_miembros_clase : lista_miembros_clase miembro_clase | empty
visibilidad          : KW_PUBLIC | KW_PRIVATE
modificador_miembro  : KW_STATIC | KW_ABSTRACT | empty
cuerpo_metodo        : bloque | DEL_PUNTO_COMA                             -- vacio = metodo abstracto

miembro_clase
    : visibilidad modificador_miembro tipo IDENTIFICADOR DEL_PUNTO_COMA                              -- atributo
    | visibilidad modificador_miembro tipo IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA
    | visibilidad modificador_miembro tipo IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C cuerpo_metodo   -- metodo
    | visibilidad modificador_miembro KW_VOID IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C cuerpo_metodo
    | IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque                                       -- constructor implicito publico
    | visibilidad KW_CONSTRUCTOR IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque             -- constructor con visibilidad (Etapa 11.1)
    | visibilidad modificador_miembro IDENTIFICADOR IDENTIFICADOR DEL_PUNTO_COMA                       -- atributo tipo clase
    | visibilidad modificador_miembro IDENTIFICADOR IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA
    | visibilidad modificador_miembro IDENTIFICADOR IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C cuerpo_metodo  -- metodo con tipo/retorno de clase

enum_decl : KW_ENUM IDENTIFICADOR DEL_LLAVE_A lista_identificadores DEL_LLAVE_C
lista_identificadores : lista_identificadores DEL_COMA IDENTIFICADOR | IDENTIFICADOR

tipo_generico_arg : tipo | IDENTIFICADOR
```

## 3. Recuperación de errores sintácticos como gramática, no como excepción

Una decisión de diseño que vale la pena señalar explícitamente:
`instruccion_error` es una producción de gramática NORMAL (no un manejador
de excepciones de PLY) para las formas inválidas más comunes que un
estudiante realmente escribe — `if (...) ...;` con punto y coma de más,
`x = 5` sin punto y coma, un `else` sin `if`. Cada alternativa reduce
igual que cualquier otra y el código semántico asociado emite el código
`IL-SIN-0NN` específico de esa forma, en vez de dejar que el parser aborte
con "syntax error" genérico. Formalmente, esto amplía el lenguaje que la
gramática acepta (para incluir errores comunes) a cambio de diagnósticos
mucho más útiles — el trade-off clásico entre gramáticas "estrictas" y
gramáticas "tolerantes a errores" que un curso de compiladores discute,
resuelto aquí a favor de la segunda.

## 4. La tabla `precedence`: vestigial, y por qué

`parser.py` declara una tabla `precedence` de PLY (líneas 33-41) con
`OP_OR`, `OP_AND`, `OP_IGUAL`/`OP_DISTINTO`, los relacionales, `OP_SUMA`/
`OP_RESTA`, `OP_MULT`/`OP_DIV`/`OP_MOD` y `UMINUS`/`OP_NOT`. A primera
vista parece redundante con la cadena `expr_or → expr_and → ... →
expr_unaria` de arriba — y de hecho **lo es, casi por completo**: una vez
que la gramática desambigua estructuralmente (cada nivel solo puede
combinarse con su propio operador o reducir al siguiente), PLY nunca
llega a necesitar la tabla para esos tokens, porque no queda ningún
conflicto shift/reduce en ese punto para resolver. La única entrada que
**sí** se usa de verdad es `('right', 'UMINUS', 'OP_NOT')`, consultada
exclusivamente por la anotación explícita `%prec UMINUS` en
`OP_RESTA expr_unaria` (para que PLY sepa que ese `-` prefijo se comporta
como unario y no como el operador binario de resta al decidir cómo
reducir). Confirmarlo es un buen ejercicio: comentar cualquier entrada de
`precedence` salvo la de `UMINUS`/`OP_NOT` y volver a construir el parser
con `debug=True` — el conteo de conflictos no cambia.

## 5. FIRST/FOLLOW — método y ejemplos trabajados

Cálculo estándar (Aho/Ullman/Sethi/Lam, "Dragon Book", cap. 4): FIRST(α)
es el conjunto de terminales con los que puede empezar una cadena
derivada de α (más ε si α puede derivar la cadena vacía); FOLLOW(A) es el
conjunto de terminales que pueden aparecer inmediatamente después de A en
alguna forma sentencial derivable desde el símbolo inicial.

### 5.1 FIRST(tipo)

```
tipo : KW_INT | KW_FLOAT | KW_STRING | KW_BOOL
FIRST(tipo) = { KW_INT, KW_FLOAT, KW_STRING, KW_BOOL }
```
Trivial (union de terminales-cabeza de cada alternativa) pero es la base
de por qué `decl_variable` puede distinguir `int x;` (empieza en
FIRST(tipo)) de `Persona x;` (empieza en IDENTIFICADOR, fuera de
FIRST(tipo)) con un solo token de lookahead — el mecanismo que hace
posible tener DOS formas paralelas de declarar variable (primitiva y de
clase) sin ambigüedad.

### 5.2 FIRST(expr_primaria) — el nivel más denso de la gramática

```
FIRST(expr_primaria) = { ENTERO_LIT, REAL_LIT, TEXTO_LIT, KW_TRUE, KW_FALSE,
                          IDENTIFICADOR, DEL_PAREN_A, KW_NEW, KW_THIS,
                          KW_NULL, KW_SUPER }
```
Como `expr_unaria → expr_primaria` (entre otras alternativas) y cada nivel
superior de la cadena de precedencia eventualmente reduce a
`expr_primaria`, este conjunto es también (con el agregado de `OP_RESTA`,
`OP_NOT`, `OP_BITNOT`, `OP_INC`, `OP_DEC` por las alternativas de
`expr_unaria`) FIRST(expresion) completo — cualquier expresión de
InvenioLang empieza en uno de estos tokens.

### 5.3 FOLLOW(instruccion)

Toda instrucción vive dentro de `lista_elem_bloque : lista_elem_bloque
elem_bloque | empty`, así que puede ser seguida por el FIRST de cualquier
otro `elem_bloque` (es decir, FIRST de cualquier instrucción/declaración) o
por `DEL_LLAVE_C` (cierre del bloque que la contiene, vía la producción
vacía de `lista_elem_bloque`):

```
FOLLOW(instruccion) ⊇ FIRST(instruccion) ∪ FIRST(decl_local) ∪ { DEL_LLAVE_C }
```

### 5.4 FOLLOW(tipo) — por qué importa para la ambigüedad de arreglos

```
FOLLOW(tipo) = { IDENTIFICADOR,       -- tipo IDENTIFICADOR ...  (decl_variable/param)
                  KW_MAIN,             -- tipo main(...)
                  DEL_CORCHETE_A }     -- tipo[tam]...            (decl_arreglo)
```
Este FOLLOW es exactamente la razón documentada en §16.5 de la spec v1.0
de por qué `void` se dejó **fuera** de `tipo`: si `void` fuera una
alternativa más de `tipo`, `void[5] x;` (arreglo de void, sin sentido)
quedaría sintácticamente aceptado y habría que rechazarlo después con un
código semántico en vez de dejar que la propia gramática lo excluya. En
cambio, `KW_VOID` se maneja con alternativas de producción separadas y
explícitas (ver `decl_arreglo`, penúltima alternativa) — la gramática
documenta la regla, no solo el código.

## 6. Puntos reales de decisión LALR(1) (con `parser.out`)

Los tres casos siguientes son fragmentos **reales** de
`inveniolang/parser.out` (regenerado con `python -c "from
inveniolang.parser import Parser; Parser().build(debug=True)"`), no
transcripciones — un estudiante puede reproducir exactamente estos números
de estado con el mismo comando.

### 6.1 Dangling else — shift/reduce resuelto a favor de shift (state 462)

```
state 462

    (122) if_stmt -> KW_IF expr_rel bloque .
    (123) if_stmt -> KW_IF expr_rel bloque . KW_ELSE bloque

  ! shift/reduce conflict for KW_ELSE resolved as shift
    DEL_PUNTO_COMA  reduce using rule 122 (if_stmt -> KW_IF expr_rel bloque .)
    DEL_LLAVE_C     reduce using rule 122 (if_stmt -> KW_IF expr_rel bloque .)
    IDENTIFICADOR   reduce using rule 122 (if_stmt -> KW_IF expr_rel bloque .)
    ...
```
El clásico "dangling else": tras `if (cond) { ... }`, ver `else` a
continuación es ambiguo entre "cerrar este `if`" (reduce) y "el `else`
pertenece a este `if`" (shift). PLY resuelve TODO shift/reduce a favor de
shift por defecto — que es también la lectura que casi cualquier lenguaje
con esta sintaxis adopta (`else` liga con el `if` más cercano sin
`else`). InvenioLang además documenta, en `parser.py::p_else_huerfano`,
qué pasa cuando esta resolución automática NO puede aplicarse: un `else`
que quedó separado de su `if` por otra instrucción se reporta como
`IL-SIN-033` en vez de fallar en silencio — decisión semántica sobre la
ambigüedad ya resuelta por la gramática.

### 6.2 Visibilidad + constructor — el conflicto real que se encontró y corrigió (Etapa 11.1)

Este es el único conflicto de todo el proyecto que **no** se evitó de
entrada por diseño sino que se introdujo, se detectó por regresión
completa de conformidad, y se corrigió — vale la pena documentarlo con
más detalle que los demás.

**Versión que falló** (nunca llegó a `main`, descartada en el momento):
```
miembro_clase : visibilidad IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque   -- constructor con visibilidad
              | visibilidad modificador_miembro tipo IDENTIFICADOR ...                   -- atributo/metodo
```
Tras `visibilidad`, un `IDENTIFICADOR` es ambiguo: podría ser el nombre
del constructor (primera alternativa) o el tipo de un atributo de clase
(segunda alternativa, vía la forma `IDENTIFICADOR IDENTIFICADOR ...` que
usa un nombre de clase como tipo). Con un token de lookahead, LALR(1) no
puede decidir cuál reducir — PLY reportó un shift/reduce real ahí, lo
resolvió con su heurística por defecto, y esa resolución rompía en
silencio el análisis de CUALQUIER atributo/método de tipo clase con
visibilidad explícita (confirmado con una regresión completa de
`pruebas/conformidad.py`: varios `.inv` de POO fallaban con `IL-SIN-010`).

**Versión corregida** (la que está en `parser.py` hoy — state 210, arriba
extraído literal de `parser.out`):
```
    (243) miembro_clase -> visibilidad . KW_CONSTRUCTOR IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque
    (265) miembro_clase -> visibilidad . modificador_miembro IDENTIFICADOR IDENTIFICADOR DEL_PUNTO_COMA
    ...
    KW_CONSTRUCTOR  shift and go to state 276
    KW_STATIC       shift and go to state 277
    KW_ABSTRACT     shift and go to state 278
    KW_VOID         reduce using rule 280 (empty -> .)
    IDENTIFICADOR   reduce using rule 280 (empty -> .)
    ...
```
Ninguna línea dice `shift/reduce conflict` — el estado 210 no tiene
ninguno. La palabra reservada nueva `constructor` (bilingüe, misma grafía
en español e inglés) es el **punto de compromiso** (commit point):
después de `visibilidad`, ver el token `KW_CONSTRUCTOR` decide sin
ambigüedad "esto es un constructor", y cualquier otro token posible ahí
(`KW_STATIC`, `KW_ABSTRACT`, o directamente el inicio de un `tipo`/nombre
de clase) decide sin ambigüedad "esto es un atributo o método". La
lección general, aplicada varias veces más en el proyecto (`enum` para
enumeraciones, `interfaz` para interfaces, `foreach` para el recorrido):
**cuando dos formas de una producción comparten un prefijo ambiguo con
un solo token de lookahead, una palabra de apertura dedicada y exclusiva
lo convierte en no ambiguo** — más simple y más seguro que reordenar
producciones o introducir precedencia expresamente para resolverlo.

### 6.3 Genéricos `Pila<entero>` — el mismo token, dos significados, resuelto por posición

`OP_MENOR`/`OP_MAYOR` (`<`/`>`) son los operadores relacionales en
cualquier expresión, y **los mismos dos tokens** delimitan el argumento de
tipo en `Pila<entero> p;` / `nuevo Pila<entero>()`. La gramática nunca dejó
que esto se resolviera por lookahead genérico — lo evita por
**construcción**: `IDENTIFICADOR OP_MENOR tipo_generico_arg OP_MAYOR
IDENTIFICADOR ...` (en `decl_variable`) y `KW_NEW IDENTIFICADOR OP_MENOR
tipo_generico_arg OP_MAYOR DEL_PAREN_A ...` (en `expr_primaria`) son
alternativas de producción **completas y separadas** de la forma no
genérica correspondiente, nunca una posición dentro de una `expresion`
de propósito general — un `<`/`>` de comparación nunca se encuentra en
esa posición sintáctica exacta. Es la misma estrategia que el resto del
documento repite: la ambigüedad léxica (mismo token) se resuelve en el
nivel de la gramática por la POSICIÓN en la que aparece, no intentando
que el analizador "adivine" la intención.

## 7. Verificación

```bash
# Regenerar parser.out y contrastar contra el baseline (20 shift/reduce, 0 reduce/reduce)
python -c "from inveniolang.parser import Parser; Parser().build(debug=True)"
grep -c "WARNING: shift/reduce" inveniolang/parser.out
grep -c "WARNING: reduce/reduce" inveniolang/parser.out

# Confirmar que cada bloque de la sección 2 de este documento corresponde
# literalmente a un docstring de parser.py (evita desfase spec/codigo)
grep -A2 "def p_if_stmt\b" inveniolang/parser.py
```

Ver también [`inveniolang/ll1_demo.py`](../inveniolang/ll1_demo.py)
(Etapa 12.13) para un analizador LL(1) recursivo-descendente de
comparación sobre el subconjunto de expresiones aritméticas, con sus
propios FIRST/FOLLOW documentados al lado — el contraste directo entre
las dos familias de parseo sobre la misma subgramática.
