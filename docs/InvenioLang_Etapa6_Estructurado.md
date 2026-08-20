# InvenioLang — Etapa 6: Lenguaje Estructurado Completo

Documento formal de la Etapa 6 (Fase 2), con el mismo nivel de rigor que
`docs/InvenioLang_2.0_POO.md`: gramática, reglas semánticas, catálogo de
errores y programa de referencia. Se valida contra
`pruebas/conformidad.py` (grupo `estructurado`).

## 0. Por qué esta etapa

Un análisis de Fase 1/Fase 2 contra los temarios de Fundamentos de
Programación, Algoritmos, Estructuras de Datos y Programación 1/2
identificó huecos reales en el subconjunto **estructurado**: sin
`switch`/`do-while`/ternario, sin manejo de errores recuperable, y una
librería estándar de solo 8 funciones (todas de conversión de tipo, nada
de cadenas ni matemática). Esta etapa los cierra, **sin tocar nada de lo
ya construido**: es aditiva sobre el lexer/parser/semántico/tipos/
intérprete/backend IR existentes, igual que la Etapa 2 (POO) lo fue sobre
la v1.0.

Alcance confirmado con el usuario: `try`/`catch` **genérico** (captura
cualquier error de ejecución del catálogo, sin clases de excepción
definidas por el usuario — eso queda fuera, ver §4.4).

## 1. Palabras reservadas nuevas (bilingües)

| Concepto | Inglés | Español |
|---|---|---|
| Selección múltiple | `switch` | `segun` |
| Caso | `case` | `caso` |
| Caso por defecto | `default` | `por_defecto` |
| Ciclo con post-condición | `do` | `hacer` |
| Intentar | `try` | `intentar` |
| Capturar | `catch` | `capturar` |

Delimitadores nuevos: `:` (dos puntos, separador de `case`/`default` y del
operador ternario) y `?` (operador ternario).

## 2. Gramática

```
switch_stmt ::= ("switch"|"segun") "(" expresion ")" "{" caso* [("default"|"por_defecto") ":" elem_bloque*] "}"
caso        ::= ("case"|"caso") literal_caso ":" elem_bloque*
literal_caso ::= ENTERO_LIT | "-" ENTERO_LIT | TEXTO_LIT | bool_lit

do_while_stmt ::= ("do"|"hacer") bloque ("while"|"mientras") "(" expresion ")" ";"

expresion ::= expr_or ["?" expresion ":" expresion]   -- asociativo a la derecha

try_stmt ::= ("try"|"intentar") bloque ("catch"|"capturar") "(" IDENTIFICADOR ")" bloque
```

Ninguna de las cuatro producciones introdujo un conflicto LALR nuevo sobre
el baseline de 20 shift/reduce establecido desde la Etapa 2 (verificado
con `parser.py(debug=True)` tras cada adición).

## 3. Reglas semánticas

1. **`switch`/`segun`** (§3.1): la expresión debe ser `int`, `string` o
   `bool` (`IL-EST-001`) — no `float`, porque comparar reales por igualdad
   exacta no tiene sentido. Cada `case` debe ser del mismo tipo que la
   expresión (`IL-EST-002`). Dos `case` con el mismo valor en el mismo
   `switch` son error (`IL-EST-003`). **Semántica de caída (fallthrough)**:
   igual que C — si un `case` no termina en `break`/`romper`, la ejecución
   continúa en el siguiente `case` sin volver a comparar.
2. **`break`/`romper`** (§3.2): válido dentro de un ciclo (`while`/`for`/
   `do-while`) **o** de un `switch` (`IL-SEM-040` si no). Un `switch` NO
   satisface `continue`/`continuar` (`IL-SEM-041` si el `continue` más
   cercano solo tiene un `switch` alrededor, sin ciclo) — distinción
   deliberada: `continue` siempre se refiere al ciclo, nunca al `switch`.
3. **Operador ternario** (§3.3): la condición debe ser `bool`
   (`IL-TIPO-019`, mismo código que `if`/`while`). Las dos ramas deben ser
   del mismo tipo o compatibles entre sí por las mismas reglas que
   asignaciones/argumentos (promoción `int→float`, upcasting de clases,
   `nulo`) — si no, `IL-EST-004`.
4. **Limitación documentada — análisis de "toda ruta retorna" (`IL-SEM-050`,
   §10.4 v1.0)**: no se extendió para reconocer un `switch` exhaustivo (con
   `default`, todas las ramas retornando) como cierre de ruta — se trata
   igual que un ciclo (conservador: "puede no ejecutarse"), consistente con
   cómo ya se trataban `while`/`for` antes de esta etapa. Una función que
   solo retorna dentro de un `switch` necesita un `return` adicional al
   final (ver el programa de referencia, §7).
5. **`try`/`catch`** (§3.4): la variable del `catch` queda declarada, solo
   dentro del bloque `catch`, con tipo `Excepcion` — una clase sintética
   siempre disponible (no se declara, no se puede redefinir sin
   `IL-POO-001` de duplicado) con dos campos públicos de solo lectura:
   `codigo` (string) y `mensaje` (string). El resto de las reglas de
   acceso a miembro de POO (§14 de `InvenioLang_2.0_POO.md`) se aplican
   sin cambios porque `Excepcion` es una `ClaseInfo` real en la tabla de
   símbolos.

## 4. Semántica de ejecución

### 4.1 `switch`/`segun`
Se evalúa la expresión una sola vez; se compara (`==`) contra cada `case`
en orden de declaración; en el primero que coincide, la ejecución entra
ahí y sigue cayendo por los `case` siguientes hasta un `break` o el final
del `switch`. Si ninguno coincide, se ejecuta `default` si existe.

### 4.2 `do`/`hacer` ... `while`/`mientras`
El cuerpo se ejecuta **siempre al menos una vez**, luego se evalúa la
condición; si es verdadera, se repite. `continue`/`continuar` salta
directo a evaluar la condición (no reinicia el cuerpo sin evaluarla).

### 4.3 Operador ternario
Solo se evalúa la rama elegida — la rama descartada **no se ejecuta en
absoluto** (mismo criterio de cortocircuito que `&&`/`||`, §6.3.1 v1.0).
Esto importa si la rama descartada tendría un efecto secundario o un
error (p. ej. `x != 0 ? 10/x : 0` nunca divide por cero).

### 4.4 `try`/`catch`
Cualquier error del catálogo de ejecución (`IL-EJE-*`) levantado dentro
del bloque `try` se captura; la ejecución continúa en el bloque `catch`
con la variable ligada a la instancia de `Excepcion` correspondiente, y
sigue normalmente después del `catch`. Un error **léxico, sintáctico,
semántico o de tipos** (detectado antes de ejecutar, en tiempo de
compilación) **nunca** es capturable — solo errores de ejecución.
**No hay clases de excepción definidas por el usuario** (alcance
confirmado): no existe `lanzar`/`throw`, ni se puede declarar una
subclase de `Excepcion`.

## 5. Catálogo de errores — prefijo `IL-EST-NNN`

Prefijo propio (igual criterio que `IL-POO` en la Etapa 2): no se
renumeran los catálogos `IL-SEM`/`IL-SIN`/`IL-TIPO`/`IL-EJE` de la v1.0
(§18.1 los declara estables entre versiones).

| Código | Descripción |
|---|---|
| `IL-EST-001` | La expresión de un `switch` no es `int`/`string`/`bool` |
| `IL-EST-002` | Un `case` no coincide con el tipo de la expresión del `switch` |
| `IL-EST-003` | Valor de `case` duplicado dentro del mismo `switch` |
| `IL-EST-004` | Las dos ramas del operador ternario tienen tipos incompatibles |
| `IL-EST-010` | `subcadena`: rango `[inicio,fin)` inválido |
| `IL-EST-011` | `caracter_en`: índice fuera de rango |
| `IL-EST-012` | `raiz_cuadrada`: argumento negativo |
| `IL-EST-013` | `elevar`: el resultado no es un número real |
| `IL-EST-014` | `azar`: mínimo mayor que máximo |

`IL-SEM-040`/`IL-SEM-041` (break/continue fuera de contexto) se reutilizan
sin cambios — ya existían en la v1.0, solo se amplió qué contextos los
satisfacen (§3.2).

## 6. Librería estándar

Igual que las 8 funciones de conversión de la Sección 19 de la v1.0: un
nombre canónico en español + un alias en inglés, registrados en
`inveniolang/builtins.py`. Ver el comentario de diseño en ese archivo
sobre por qué **no** se usan los nombres "obvios" `longitud`, `raiz`,
`potencia`, `maximo`/`minimo` — colisionan con variables/funciones que ya
usan varios programas de referencia permanentes (§18.1) como ejercicio
("escriba su propia función potencia").

| Español | Inglés | Firma | Descripción |
|---|---|---|---|
| `longitud_texto` | `text_length` | `(string) -> int` | Cantidad de caracteres |
| `subcadena` | `substring` | `(string, int, int) -> string` | Subcadena `[inicio,fin)` |
| `mayusculas` | `to_upper` | `(string) -> string` | Convierte a mayúsculas |
| `minusculas` | `to_lower` | `(string) -> string` | Convierte a minúsculas |
| `caracter_en` | `char_at` | `(string, int) -> string` | Carácter en la posición `i` |
| `indice_de` | `index_of` | `(string, string) -> int` | Posición de la primera aparición, o `-1` |
| `recortar` | `trim` | `(string) -> string` | Quita espacios al inicio/final |
| `raiz_cuadrada` | `sqrt` | `(float) -> float` | Raíz cuadrada |
| `elevar` | `pow` | `(float, float) -> float` | Potenciación |
| `absoluto` | `abs` | `(int) -> int` | Valor absoluto |
| `piso` | `floor` | `(float) -> int` | Redondeo hacia abajo |
| `techo` | `ceil` | `(float) -> int` | Redondeo hacia arriba |
| `azar` | `random` | `(int, int) -> int` | Entero aleatorio uniforme en `[min,max]` |

No hay `maximo`/`minimo`: con el operador ternario, `a > b ? a : b` los
vuelve triviales de escribir sin arriesgar la colisión de nombres arriba.

## 7. Programa de referencia

```
int categorizar(int nota) {
    switch (nota / 10) {
        case 10:
        case 9: return 0;   // Excelente (cae de 10 a 9)
        case 8: return 1;   // Muy bueno
        case 7: return 2;   // Bueno
        default: return 3;  // Insuficiente
    }
    return 3;  // inalcanzable en la práctica: el análisis de "toda ruta
               // retorna" (IL-SEM-050, §10.4 v1.0) no reconoce un switch
               // exhaustivo como cierre de ruta -- lo trata igual que un
               // ciclo (conservador a propósito, ver ERRATAS de esta etapa)
}

void main() {
    int [5] notas = {95, 82, 71, 60, 100};
    string [4] etiquetas = {"Excelente", "Muy bueno", "Bueno", "Insuficiente"};

    int i = 0;
    do {
        int cat = categorizar(notas[i]);
        imprimir(entero_a_texto(notas[i]));
        imprimir(": ");
        imprimir(etiquetas[cat]);
        imprimir(notas[i] >= 60 ? " (aprobado)\n" : " (reprobado)\n");
        i = i + 1;
    } while (i < 5);

    try {
        int x = 10 / (notas[0] - 95);  // division por cero intencional
    } catch (e) {
        imprimir("Error controlado: ");
        imprimir(e.codigo);
        imprimir("\n");
    }

    imprimir(mayusculas(subcadena("fin del programa", 0, 3)));
}
```

Salida esperada (ver `pruebas/conformidad.py`, grupo `estructurado`, para
los casos unitarios que cubren cada construcción por separado):
```
95: Excelente (aprobado)
82: Muy bueno (aprobado)
71: Bueno (aprobado)
60: Insuficiente (aprobado)
100: Excelente (aprobado)
Error controlado: IL-EJE-006
FIN
```

## 8. Backend de código intermedio (`inveniolang/ir.py`)

Las cuatro construcciones tienen TAC propio y se ejecutan idéntico en
`MaquinaTAC` (`--run-ir`) que en el intérprete de árbol — verificado en
`pruebas/conformidad.py` y con comparación directa salida-a-salida.
`try`/`catch` es la pieza más delicada del backend: `MaquinaTAC` mantiene
una pila de manejadores activos (`try_begin`/`try_end`/`pop_manejador`) y
un `break`/`continue` que salta fuera de un `try` cierra los manejadores
abiertos correctamente (ver comentarios en `ir.py::GeneradorIR._gen_try`).
`MaquinaTAC` no replica el catálogo completo de errores de `interpreter.py`
— solo división/módulo por cero e índice fuera de rango — lo suficiente
para que `try`/`catch` tenga algo real que capturar en el backend de
demostración.
