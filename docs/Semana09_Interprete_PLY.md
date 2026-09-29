# Investigación Exhaustiva — Lenguajes Formales II / InvenioLang: de la Teoría al Intérprete, IR y Optimización (Semana 9, Hito H4)

**Curso:** TIIT2002.2 Lenguajes Formales II — Universidad Invenio (TICEC) | **Profesor:** Donny Núñez del Rosario
**Proyecto eje:** InvenioLang 1.0 / 10.0 | **Semana 9 de 12 | Hito H4 | 16–18h**
**Base:** Syllabus Unidades I–X · Documento B Semanas 1–12 · Spec §§1–19 · `gramatica.ebnf` · `lexer.py / parser.py / ast_nodes.py / symbol_table.py / semantic.py / type_checker.py / interpreter.py / ir.py / builtins.py / errors.py`
**Web verificada (sep-2026):** PLY oficial `ply.readthedocs.io`, `dabeaz.com/ply`, `github.com/dabeaz/ply`; Dragon Pearson/Archive; `craftinginterpreters.com`; TAC (GeeksforGeeks, WPI §6.3.3, OpenGenus, GateVidyalay); LALR (Cornell, Johnson yacc, kindatechnical); dataflow (O'Reilly Cooper cap. 9, ResearchGate). URLs completas en Anexo C.
**Lectura:** cada capítulo trae *Definición formal + Explicación sencilla + Fundamento citado + Ejemplo PLY/InvenioLang + Errores + Mini-cierre*. Cada capítulo está dimensionado para ≥3 páginas impresas (≈1500 palabras).

---

## Capítulo 1. Fundamentos de lenguajes formales (≈3 páginas)

### 1.1 Alfabetos, cadenas, lenguajes y operaciones
**Definición formal.** Un alfabeto Σ es un conjunto finito no vacío de símbolos. En InvenioLang Σ es Unicode [SpecInv, §2.1] ([Aho07, §3.1]; [Scott16, §2.1]). Una cadena es una secuencia finita sobre Σ; `ε` es la cadena vacía; `|w|` su longitud. Un lenguaje es cualquier conjunto de cadenas (finito o infinito). Operaciones: unión `L∪M`, concatenación `LM = {xy | x∈L, y∈M}`, clausura `L* = ∪_{i≥0} L^i`, `L+ = LL*`. Estas operaciones son cerradas y asociativas salvo conmutatividad.
**Explicación sencilla.** El alfabeto es el Scrabble; la cadena, la palabra que armas; el lenguaje, el diccionario que dice cuáles valen. `*` significa "repite cuantas veces quieras, incluso cero".
**Por qué importa en InvenioLang.** Todo `.inv` es una cadena sobre Unicode; el compilador decide si pertenece al lenguaje. Los espacios y comentarios pertenecen al alfabeto pero no al lenguaje significativo: el lexer los filtra. Los identificadores `cont4dor` son cadenas; la regla "no empezar con dígito" es una restricción del lenguaje, no del alfabeto.
**Ejemplo.** Σ={a,b}; L={ab, abb}; L* incluye `ε, ab, abb, abab, ababb, abbabb…`. En InvenioLang, Σ incluye `@` pero el lenguaje de tokens lo rechaza → `IL-LEX-002`.
**Mini-cierre.** Sin esta base no se entiende por qué `@` es error léxico y `x+y*z` no es problema léxico sino sintáctico.

### 1.2 Expresiones regulares, lenguajes regulares y Kleene
**Definición.** Regex sobre Σ: `∅` (vacío), `ε`, `a∈Σ`, `(r|s)` unión, `(rs)` concat, `(r*)` estrella, más azúcar `(r+, r?, [a-z])` ([Aho07, §3.3]). Precedencia regex: `*` > concat > `|`. Cada regex denota un lenguaje regular.
**Teorema de Kleene.** Todo regex tiene un AFD equivalente y viceversa ([Cooper22, §2.2]). Prueba constructiva: Thompson (regex→AFN) + subconjuntos (AFN→AFD) + minimización ([Aho07, §3.6–3.7]). Consecuencia práctica: el lexer corre en O(n) con memoria finita, sin pila ni recursión.
**Lema de bombeo (para saber qué NO es regular).** Si L es regular existe p tal que toda `w∈L, |w|≥p` se bombea `w=xyz, |y|>0, |xy|≤p, xyⁱz∈L` ([Aho07, §3.2]). `aⁿbⁿ`, llaves balanceadas `{ⁿ}ⁿ` y expresiones anidadas lo violan: por eso van al parser, jamás al lexer. Intentar reconocer bloques con regex es el error teórico más grave del trimestre.
**InvenioLang aplicado.** `ENTERO \d+`, `REAL \d+\.\d+`, `ID [A-Za-z_][A-Za-z0-9_]*`, `TEXTO "..."` con escapes, operadores `== != <= >= && ||`. Cada `t_*` de PLY es un regex; PLY los compila a un AFD combinado ([BeazleyPLY]).
**Ejemplo PLY mínimo.**
```python
t_ENTERO = r'\d+'
def t_REAL(t):
    r'\d+\.\d+'
    t.value = float(t.value); return t
```
**Mini-cierre.** Si puedes dibujar el AFD, puedes escribir el regex; si necesitas contar, ya no es léxico.

### 1.3 Autómatas finitos: AFN, AFD, Thompson y subconjuntos
**AFD:** quíntupla `(Q, Σ, δ, q0, F)` determinista; **AFN:** permite ε y múltiples destinos ([Aho07, §3.5]). Thompson traduce cada operador regex a 2–4 estados con ε; subconjuntos convierte conjuntos de estados AFN en un estado AFD (peor caso exponencial, en la práctica lineal para tokens); minimización (Hopcroft) reduce estados equivalentes.
**Lookahead como estados.** `=` vs `==`: tras leer `=` el AFD está en estado "quizá `==`"; si lo siguiente es `=`, acepta `OP_IGUAL`, si no, emite `OP_ASIG` y retrocede un carácter ([Cooper22, §2.4]). PLY lo hace solo; un lexer manual usa `mirar(1)` ([Watt00, §3]).
**Maximal munch.** Ante particiones rivales se elige la más larga ([Aho07, §3.4]): `>=` es uno, no dos; `mientras` es keyword, no id. En PLY: funciones por orden de definición, cadenas por longitud descendente ([BeazleyPLY]).
**Tabla de decisión.**
| Situación | Acción PLY | Fundamento |
|---|---|---|
| `REAL` vs `ENTERO` en `3.14` | gana `REAL` (función) | prioridad función>candena |
| `==` vs `=` | gana `==` (más larga) | maximal munch |
| `si` vs id | gana `KW_IF` (tabla) | keywords.get |
**Mini-cierre.** Todo token multi-char es un mini-AFD con lookahead; quien no lo dibuja, lo rompe con `?.` vs `?` o `<<` vs `<`.

### 1.4 Gramáticas, Chomsky, BNF y EBNF
**Definición.** G=(N,Σ,P,S): no-terminales, terminales (tokens), producciones `A→α`, inicial S ([Aho07, §4.1]). Jerarquía: Tipo 3 regular ⊊ Tipo 2 libre de contexto ⊊ Tipo 1 sensible ⊊ Tipo 0 irrestricto ([Scott16, §2.2]). InvenioLang: Tipo 3 para léxico, Tipo 2 para sintaxis — expresividad mínima suficiente.
**BNF vs EBNF** ([Aho07, §4.2]): `::=` define, `|` alterna; EBNF añade `{x}` (0+), `[x]` (opcional), `( )` grupo. `programa ::= { elemento }` equivale a recursión izquierda `programa ::= programa elemento | ε` pero legible. Toda la sintaxis vive en `gramatica.ebnf` (Anexo A).
**Derivaciones y ambigüedad.** Derivar = sustituir no-terminales hasta solo terminales. Árbol concreto guarda todo; gramática ambigua = dos árboles para una cadena ([Aho07, §3]). `E→E+E|E*E` es ambigua para `2+3*4`; la precedencia la desambigua (§4.3 de este doc).
**Mini-cierre.** La gramática es el contrato; el parser, el inspector que lo hace cumplir.

### 1.5 FIRST, FOLLOW, LL y LR (puente al Capítulo 4)
FIRST(A) = terminales que inician A; FOLLOW(A) = los que pueden seguirla ([Aho07, §4.4]). Con ellos se construyen tablas LL(1) (descendente, sin retroceso) y LR/LALR (ascendente, shift/reduce). `grammar_validator.py` exige LALR sin conflictos y FIRST≥10: prueba mecánica de determinismo. Detalle completo en Cap. 4 con notas Cornell y Johnson.

### 1.6 Historia en cinco fechas y prueba del bombeo (≈1 página)
Chomsky (1956) clasifica gramáticas; Backus-Naur (1959–60, Algol 60) notan sintaxis; Thompson (1968) compila regex a AFN; Johnson (1975) genera LALR con Yacc; Beazley (2001) lo porta a Python (PLY). Cada fecha elimina una tarea manual: ya no se escriben AFD a mano ni tablas LR a mano. **Bombeo en un párrafo:** supone `L={aⁿbⁿ}` regular con p; toma `aᵖbᵖ`; el AFD repite estado en las `a` y puede repetir el ciclo, aceptando `aᵖ⁺ᵏbᵖ` ∉ L: contradicción. Por eso contar llaves exige pila (= parser). Este argumento, bien dicho, cierra cualquier pregunta de "¿por qué no todo en regex?".

### 1.7 Mini-ejemplo Thompson + subconjuntos (≈½ página)
Regex `a(b|c)*`: Thompson crea ε-ramas para `|` y ciclo para `*`; subconjuntos agrupa `{q0,q1,q2}` como estado AFD inicial, etc. PLY hace esto por cada `t_*` y los une con ε desde un inicio común, determinizando una vez. El estudiante no dibuja 200 estados, pero debe saber que existen: de ahí viene la garantía O(n).

### 1.8 Caso integrador y ejercicios (≈1 página)
Calcule FIRST de `E ::= T {"+" T}`, `T ::= F {"*" F}`, `F ::= id | "(" E ")"`: FIRST(F)={id,(}, FIRST(T)=FIRST(F), FIRST(E)=FIRST(T); FOLLOW(E) incluye `$,),+`. Con esa tabla un LL(1) decide cada alternativa con un token: ejemplo de predictividad. **Ejercicios resueltos:** (1) Demuestre que `{0ⁿ1ⁿ}` no es regular por bombeo (tome `0ᵖ1ᵖ`, bombee ceros). (2) Escriba regex de `REAL` y explique por qué `.5` se rechaza (falta dígito previo: el AFD exige al menos uno antes del punto). (3) Convierta `{x}[,x]` a BNF con recursión de cola. Soluciones en clase: el (2) es `IL-LEX-009` vivo.

### 1.9 Lecturas guiadas y mapa de estudio del capítulo (≈½ página)
Lea [Aho07, §§3.1–3.7] para regex→AFD con pruebas; [Cooper22, §2.2] para Thompson/subconjuntos con pseudocódigo; [Scott16, §2.2] para Chomsky con ejemplos de lenguajes. Mapa: lunes alfabetos+operaciones, martes regex+Kleene, miércoles AFD+lookahead, jueves BNF/EBNF, viernes FIRST/FOLLOW. Cada día un ejercicio de escritura (regex, gramática, derivación) y uno de lectura (trazar AFD, leer `t_*`). Quien cumple el mapa llega al Cap. 2 sin lagunas.

### 1.10 Diez errores de examen del capítulo (≈½ página)
(1) Decir que `*` regex significa "multiplicar". (2) Poner bloques en el lexer. (3) Confundir `ε` con "espacio". (4) Creer que EBNF es otro lenguaje y no azúcar. (5) Olvidar `FOLLOW` en LL. (6) No justificar maximal munch. (7) Dibujar AFD sin estado trampa. (8) Mezclar token con lexema. (9) Ignorar `lineno`. (10) Citar sin capítulo. Corregirlos suma más que memorizar.

### 1.11 Jurado: 8 preguntas con respuesta modelo (≈1 página)
(1) ¿Qué es un lenguaje? — Conjunto de cadenas, finito o infinito. (2) ¿Kleene en una frase? — Regex⇔AFD. (3) ¿Bombeo para qué sirve? — Para probar no-regularidad. (4) ¿Chomsky 2 vs 3? — Anidamiento exige Tipo 2. (5) ¿BNF vs EBNF? — Azúcar `{[]}`. (6) ¿FIRST de `F`? — `{id,(}`. (7) ¿Por qué `REAL` no es `ENTERO`? — Punto con dígitos. (8) ¿Token vs lexema en `si`? — `KW_IF` vs `"si"`. Responder las 8 sin mirar es el aprobado del capítulo.

### 1.12 Cierre: mapa mental del capítulo (≈½ página)
Alfabeto→cadenas→lenguaje→regex→AFD→gramática→derivación→FIRST/FOLLOW. Cada flecha es una construcción efectiva (Thompson, subconjuntos, tablas). Si alguna flecha se rompe (regex para bloques, gramática ambigua sin precedencia), todo lo posterior hereda el defecto. Por eso el curso dedica 3 semanas al frontend antes de ejecutar una línea: los cimientos pagan intereses.

---

---

---

---

---

---

## Capítulo 2. Arquitectura de procesadores: frontend, backend y decisiones (≈3 páginas)

### 2.1 Las 6 fases InvenioLang y la Figura 1.6 del Dragon
Flujo [DocB, §1.1.2] instanciando [Aho07, Fig. 1.6]: `caracteres→[léxico]→tokens→[sintaxis]→AST→[semántica]→AST+tabla→[tipos]→AST tipado→[IR]→TAC→[opt]→TAC→[ejecución]→salida`, con tabla transversal y errores por fase. Frontend = independiente de máquina (análisis); backend = dependiente (síntesis/ejecución). Fases lógicas agrupables en pasadas (ej. todo el frontend en una pasada).
**Qué garantiza cada fase.** Léxico: palabras bien formadas. Sintaxis: frases bien armadas. Semántica: frases con referente. Tipos: operaciones compatibles. IR/opt: representación plana equivalente y más rápida. Ejecución: efecto observable. Interfaz: todo usable.
**Separación de diagnósticos** ([Grune12, §2]): ninguna fase reporta errores de otra. El lexer jamás dice "no declarado"; el tipador jamás dice "falta `;`". Violarlo es defecto de diseño y se penaliza en defensa.

### 2.2 Tres modelos de ejecución comparados
| Modelo | Mecanismo | Pro | Contra | En InvenioLang |
|---|---|---|---|---|
| Árbol ([Nystrom21, P.II]) | `visitar(nodo)` recursivo | simple, depurable | lento, sin opt global | `interpreter.py` (producción) |
| TAC+VM | aplana a cuádruplas, ejecuta lineal | optimizable, portable | costo traducción | `ir.py` + `MaquinaTAC` |
| ISA objetivo (Et.12) | pila de 26 instr | cierra pipeline real | solo juguete | `--target/--target-reg` |
Mapa Nystrom ([craftinginterpreters.com/a-map-of-the-territory.html]): caracteres→tokens→árbol→análisis = frontend; IR (CFG/SSA/CPS/TAC)→opt = middle; gen→VM→runtime = backend. Single-pass (Pascal/C) genera sin árbol por falta de memoria histórica; tree-walk (Ruby MRI, jlox) prioriza claridad; transpilador traduce alto→alto (TS→JS).

### 2.3 Herramientas: Lex/Yacc → PLY → ANTLR
Lex/Yacc (Johnson, Unix 70s) generan C desde specs; PLY (Beazley, Chicago 2001, 2910★) reimplementa LALR(1) en Python puro **por reflexión**: las specs *son* Python válido, sin generador externo ([ply.readthedocs.io], [github.com/dabeaz/ply]). ANTLR (Parr, ALL(*)) más expresivo pero más pesado ([Parr13]). El curso elige PLY: fidelidad LALR del syllabus + auditoría en clase + diagnóstico para novatos.
**Diferencia operativa.** Unix yacc: `yacc gram.y → y.tab.c → compilar`. PLY: `yacc.yacc(module=self)` introspecta `p_*` y `precedence` en memoria; `lex.lex(optimize=1)` cachea `lextab/parsetab` y desactiva chequeo (solo proyecto estable).

### 2.4 Estrategia incremental y pruebas por fase
Pipeline impone orden total: sin tokens no hay AST; sin AST no hay tabla; sin tabla no hay tipos; sin tipos no hay ejecución segura ([DocB, cap. 2]). Por eso cada semana prueba **solo** su componente con `.inv` diseñados (H1 lexer, H2 parser, H3 semántico, H4 ejecución, H5 integración). Intentar `sistema_ventas.inv` en semana 2 es error metodológico, no técnico.

### 2.5 Historia mínima: de Fortran a PLY (por qué el pipeline es así)
Los primeros compiladores (Fortran, 1957) eran monolitos de una pasada por falta de memoria: generaban código al leer, sin AST completo ([Nystrom21, cap. 2]; [Aho07, §1.1]). Pascal y C heredaron restricciones single-pass (declaración antes de uso, `forward`) por esa economía. Con memoria barata el diseño se modularizó en fases con IR común: un frontend por lenguaje × un backend por máquina produce N×M compiladores combinando piezas ([Aho07, §1.2]). Lex (Lesk) y Yacc (Johnson, años 70 Unix) convirtieron scanner/parser en especificaciones declarativas en vez de código manual propenso a errores. PLY (Beazley, Chicago 2001) replica ese flujo en Python para enseñar: el estudiante sufre lo justo —escribe regex y gramática— y la herramienta construye AFD y tablas LALR. ANTLR (Parr) generaliza a ALL(*) con adaptatividad, a costo de mayor complejidad ([Parr13]). InvenioLang elige PLY porque el syllabus evalúa teoría LALR clásica, no poder adaptativo.

### 2.6 Tabla entrada/salida/error por fase (para memorizar)
| Fase | Entrada | Salida | Error típico | Pregunta de defensa |
|---|---|---|---|---|
| Léxico | caracteres | tokens + posición | `IL-LEX-012` string abierto | ¿Por qué `@` es léxico y no sintáctico? |
| Sintaxis | tokens | AST | `IL-SIN-010` falta `;` | ¿Qué producción falla en `int a b;`? |
| Semántica | AST | AST + tabla | `IL-SEM-003` no declarado | ¿En qué nivel buscó y no halló? |
| Tipos | AST anotado | AST tipado | `IL-TIPO-019` `si(5)` | ¿Qué juicio `Γ ⊢` falla? |
| IR | AST tipado | TAC | `NoSoportadoIR` (POO) | ¿Por qué esa construcción no se aplana? |
| Opt | TAC | TAC equivalente | regresión (cambia salida) | ¿Qué pasada rompió equivalencia? |
| Ejecución | AST/TAC | salida / `IL-EJE-*` | `IL-EJE-010` índice | ¿Chequeó límites antes de acceder? |
Memorizar esta tabla es aprobar la mitad de la defensa H4: cada error tiene exactamente una fase dueña.

### 2.7 Frontend vs backend vs middle-end (vocabulario Nystrom)
Frontend = caracteres→significado (scan, parse, análisis). Middle = significado→significado más barato (IR, opt). Backend = significado→máquina (gen, VM, runtime) ([craftinginterpreters.com/a-map-of-the-territory.html]). InvenioLang cubre frontend completo, middle (TAC + 4 pasadas) y un backend juguete (ISA de pila + linear-scan). No hay GC ni nativo: decisión pedagógica, no carencia ([Cooper22, §1]).

### 2.8 Memoria histórica y por qué C exige declaraciones previas (≈½ página)
Con 64KB no cabía el AST: el compilador generaba al leer y por eso C pide prototipos y Pascal `forward`. Hoy con GB de RAM el AST completo cabe y permite análisis globales (tipos, liveness). InvenioLang enseña ambas eras: el intérprete recorre el árbol completo (moderno), pero el `for` con `for_init` local recuerda la restricción histórica de declarar antes de usar en el mismo ámbito.

### 2.9 Filosofía del error útil (≈½ página)
Un buen error tiene código estable, posición exacta, mensaje accionable y no-cascada ([Grune12, §2.4]; [SpecInv, §15.8]). `IL-XXX-NNN` es estable entre versiones (§18.1): los tests `conformidad.py` lo exigen al 100%. Máximo 50 errores (`ErrorManager.max_errores`) para no ahogar; ordenados por posición, no por descubrimiento. La GUI subraya en vivo con el mismo catálogo: teoría y herramienta coinciden.

### 2.10 Cronograma de estudio y entregables del capítulo (≈½ página)
Semana 1 real: día 1 pipeline + Fig. 1.6; día 2 frontend a mano (tokenizar y parsear en papel); día 3 backend (TAC de 5 líneas); día 4 herramientas (PLY mínimo); día 5 defensa simulada de 10 minutos. Entregables: estructura de directorios, `main` de bienvenida, lector `.inv`, README con decisión de lenguaje/UI y resumen de 1 página. Criterio: lector abre `§17.1` y lo muestra intacto; si falla aquí, todo lo demás hereda el fallo.

### 2.11 Comparativa single-pass vs multi-pass con números (≈½ página)
Con 64KB y programa de 100KB, single-pass lo compila sin cargarlo entero (memoria O(ventana)); multi-pass necesita O(programa) pero permite análisis globales (tipos, liveness) imposibles en una pasada. InvenioLang multi-pass paga memoria para ganar diagnósticos: decisión correcta en 2026 con GB de RAM. Explicar este trade-off con números muestra criterio ingenieril, no solo teoría.

### 2.12 Jurado del capítulo (≈½ página)
(1) Dibuje Fig. 1.6 con entradas/salidas. (2) ¿Frontend vs backend? — Independencia de máquina. (3) ¿Tres modelos de ejecución? — Árbol, TAC+VM, ISA. (4) ¿PLY vs yacc? — Reflexión vs codegen. (5) ¿Por qué incremental? — Orden total de dependencias. (6) ¿Fase dueña de `no declarado`? — Semántica. (7) ¿Máximo de errores y por qué? — 50, no ahogar. (8) ¿Qué es middle-end? — IR+opt.

### 2.13 Cierre: la decisión más cara del trimestre (≈½ página)
Elegir monolito vs fases es la decisión arquitectónica con mayor costo de reversión: un monolito entrega demos rápidas en semana 2 pero impide diagnósticos por fase y optimización en semana 9; unas fases bien separadas tardan en arrancar pero permiten H1–H5 independientes y defensa por capas. InvenioLang elige fases con IR común precisamente para que cada hito sea calificable sin el siguiente. Esa es la lección de gestión, no solo técnica, del capítulo.

---

---

---

---

---

## Capítulo 3. Léxico exhaustivo con PLY (≈3 páginas)

### 3.1 Inventario completo de terminales InvenioLang
Familias ([SpecInv, §2]; `lexer.py: keywords/tokens`): identificadores `[A-Za-z_][A-Za-z0-9_]*`; `ENTERO_LIT \d+` (rango 32b verificado en ejecución); `REAL_LIT \d+\.\d+`; `TEXTO_LIT` con escapes `\\ \n \t \" \'`; asignaciones `= += -= *= /= %=`; `++ --`; relacionales `== != < > <= >=`; lógicos `&& || !`; bits `& | ^ ~ << >>` solo `int` (Et.11); nulos `?. ??` (Et.12); delimitadores `{}()[];, : ? .`; 41 palabras bilingües (`if/si, while/mientras, for/para, print/imprimir, read/leer, int/entero, float/real, string/texto, bool/logico, void/vacio, const/constante, true/verdadero, false/falso, break/romper, continue/continuar, return/retornar, switch/segun, case/caso, default/por_defecto, do/hacer, try/intentar, catch/capturar, class/clase, extends/hereda, new/nuevo, this/este, super/padre, public/publico, private/privado, null/nulo, foreach/para_cada, function/funcion, match/emparejar, enum/enumeracion, abstract/abstracta/abstracto, static/estatico, implements/implementa, interface/interfaz`) + `main` + `constructor`.
**Principio de diseño.** Duplicar léxico sin duplicar gramática: dos lexemas, un terminal. La tabla `keywords` lo implementa en O(1) ([Cooper22, §2.3]).

### 3.2 Regex canónicas, prioridad y AFD combinado
```python
t_OP_IGUAL, t_OP_DISTINTO = r'==', r'!='
t_OP_MENOR_IGUAL, t_OP_MAYOR_IGUAL = r'<=', r'>='
t_OP_AND, t_OP_OR = r'&&', r'\|\|'
t_OP_SHL, t_OP_SHR = r'<<', r'>>'
t_OP_ACCESO_SEGURO, t_OP_COALESCENCIA = r'\?\.', r'\?\?'
t_OP_SUMA, t_OP_ASIG = r'\+', r'='
t_DEL_LLAVE_A, t_DEL_LLAVE_C = r'\{', r'\}'
t_ignore = ' \t\r\v'
def t_REAL_LIT(t):
    r'\d+\.\d+'
    t.value = float(t.value); return t
def t_ENTERO_LIT(t):
    r'\d+'
    t.value = int(t.value); return t
def t_TEXTO_LIT(t):
    r'"[^"\\\n]*(?:\\.[^"\\\n]*)*"|\'[^\'\\\n]*(?:\\.[^\'\\\n]*)*\''
    t.value = t.value[1:-1]; return t
def t_IDENTIFICADOR(t):
    r'[A-Za-z_][A-Za-z0-9_]*'
    t.type = keywords.get(t.value, 'IDENTIFICADOR'); return t
def t_newline(t):
    r'\n+'; t.lexer.lineno += len(t.value)
def t_COMMENT(t):
    r'//.*|/\*(.|\n)*?\*/'; t.lexer.lineno += t.value.count('\n')
def t_error(t):
    t.lexer.skip(1)  # más reporte IL-LEX-002 con línea/col
```
**Reglas PLY verificadas** ([ply.readthedocs.io/en/latest/ply.html]): funciones por orden de definición; cadenas por longitud descendente; `t_ignore` salta; `t_error` recupera; `lineno` es invariante manual. `?. ?? << >>` ganan a `? < >` sin código por longitud. `REAL` debe ser función o `ENTERO` la partiría.

### 3.3 Strings, escapes y comentarios: tres autómatas trampa
**Strings** ([SpecInv, §2.9]): apertura=cierre; `\n \t \\ \" \'` un símbolo; salto real → `IL-LEX-010`; sin cierre → `012`; cruce `"…'` → `013`; `\q` → `011`. El regex solo acepta bien cerrados; el resto lo clasifica `_t_error_string` mirando cómo termina.
**Comentarios** ([SpecInv, §2.12]): `//` a fin de línea; `/*…*/` al primer `*/`, no anidables (lenguaje sigue regular); se descartan pero suman líneas o todo error posterior miente. Sin `*/` → `014`.
**Números.** `.5, 5., 1e` → `009` (forma exige dígitos a ambos lados del punto).

### 3.4 Catálogo léxico IL-LEX-001…014 (qué estado falla)
`001` BOM/encoding · `002` `@ $ \`` fuera de literal · `003` codificación · `004` `1x` (AFD id rechaza dígito inicial) · `005` ilegal interno (`mi-var`) · `006` futura (`procedure`) como id · `007` id excesivo · `008` entero rango · `009` real malformado · `010` salto en string · `011` escape · `012` sin cierre · `013` cruce · `014` bloque abierto. Todos con `archivo:línea:columna` ([SpecInv, §15.8]).

### 3.5 Ingeniería del scanner: buffering, O(n) y posición exacta
Un lexer ingenuo que reabre el archivo por token sería O(n²). El diseño clásico usa doble búfer con centinela para no retroceder más de un carácter salvo lookahead ([Aho07, §3.2]; [Cooper22, §2.3]). PLY lo abstrae: `lexer.input(text)`, `token()` consume贪 pero `lineno/lexpos` los mantiene el autor. Regla de oro InvenioLang: **cada `\n` —incluso dentro de comentarios y strings rotos— suma `lineno`**; cada `skip(1)` en `t_error` evita bucle infinito. Sin esto, el error 50 líneas después de un `/*` abierto mentiría su línea y la defensa se pierde. Caso de estudio: `si (x>=10 && x!=5) { imprimir("hola\n"); }` produce `KW_IF DEL_PAREN_A IDENTIFICADOR OP_MAYOR_IGUAL ENTERO_LIT OP_AND IDENTIFICADOR OP_DISTINTO ENTERO_LIT DEL_PAREN_C DEL_LLAVE_A KW_PRINT DEL_PAREN_A TEXTO_LIT DEL_PAREN_C DEL_PUNTO_COMA DEL_LLAVE_C`: 18 tokens, cero ambigüedad gracias a longitud + tabla.

### 3.6 Bilingüismo: decisión de diseño, no capricho
Duplicar 41 entradas léxicas cuesta una tabla; duplicar 60 producciones costaría una gramática paralela. La equivalencia `if≡si` a nivel terminal mantiene LALR determinista con el mismo número de estados ([SpecInv, §2.5]). Alternativas descartadas: preprocesador traductor (rompería posiciones) y dos gramáticas (doble mantenimiento). Las integradas con 3 nombres (`int_a_float ≡ int_to_float ≡ entero_a_real`) aplican el mismo principio a nivel de entorno, no de token.

### 3.7 Tabla maestra token→regex→ejemplo (≈1 página)
| Token | Regex | Ejemplo | Trampa |
|---|---|---|---|
| `KW_IF` | `if\|si` vía tabla | `si` | `silla` es id (munch) |
| `IDENTIFICADOR` | `[A-Za-z_][A-Za-z0-9_]*` | `temperatura_1` | `1t` → 004 |
| `ENTERO_LIT` | `\d+` | `42` | `9999999999` rango |
| `REAL_LIT` | `\d+\.\d+` | `3.14` | `.5` → 009 |
| `TEXTO_LIT` | `"…"`/`'…'` + escapes | `"hola\n"` | salto real → 010 |
| `OP_*` 2-char | `== != <= >= && \|\| ++ -- += …` | `a+=2` | `=+` son dos |
| `DEL_*` | `{}()[];, : ? .` | `{` | — |
| Comentarios | `//.*` , `/\*…\*/` | `/* hola */` | sin cierre → 014 |
Recitar esta tabla de memoria es el Hito H1 oral: si dudas en `?.` vs `?`, no dominas longitud.

### 3.8 Errores PLY que todo novato comete (≈½ página)
Olvidar un token en `tokens` (PLY avisa "defined but not used" al revés); poner `REAL` como cadena (la parte entera); no sumar `lineno` en comentarios multilínea; retornar algo en `t_COMMENT` (debe descartar); `t_error` sin `skip` (bucle infinito). PLY es "quisquilloso a propósito" ([ply.readthedocs.io]): cada warning es una lección.

### 3.9 Práctica calificada del capítulo (≈1 página)
Tokenice a mano `entero[5] arr = {1,2,3,4,5};` listando tipo+lexema+posición de cada uno (son 16 tokens). Luego provoque los 6 errores `002,004,009,010,012,014` con el archivo más corto posible (uno por línea) y anote el `línea:columna` reportado. Si algún reporte miente la posición, el bug está en su `lineno`: corríjalo antes de seguir. Esta práctica es el Hito H1 en miniatura y vale como evidencia de la semana 3.

### 3.10 Jurado del capítulo (≈½ página)
(1) Tripleta del token en `mientras`. (2) ¿Por qué `>=` es uno? — Munch+longitud. (3) ¿Función vs cadena en PLY? — Prioridad. (4) ¿`REAL` como función por qué? — Ganar a `ENTERO`. (5) ¿Apertura=cierre en strings por qué? — Delimitador. (6) ¿Comentario anidado por qué no? — Regularidad. (7) ¿`t_error` sin `skip`? — Bucle. (8) ¿Bilingüe sin duplicar gramática cómo? — Tabla.

### 3.11 Cierre: el lexer como contrato de posiciones (≈½ página)
Cada token es una promesa: "estos caracteres, en esta línea:columna, significan esto". Si la promesa miente (línea mal contada, lexema truncado, keyword no mapeada), todos los contratos posteriores (AST, tabla, tipos, ejecución) heredan la mentira. Por eso el Hito H1 exige tokens exactos en §17.1 antes de autorizar el parser: sin posiciones fiables no hay defensa posible.

---

---

---

---

---

## Capítulo 4. Sintaxis exhaustiva y AST (≈3 páginas)

### 4.1 Gramática EBNF completa y su lectura (≈1 página)
`programa ::= { elemento }`; elemento = global|función|procedimiento|main|clase|enum|interfaz ([SpecInv, §16]; `gramatica.ebnf`; Anexo A). Declaraciones exigen `;`; `bloque ::= "{" { elem } "}"`; 13 instrucciones (asig, inc/dec, print/read, if/while/for/foreach/do/switch/match/try/return/break/continue/call); `lvalue` con 0–2 índices o `receptor.miembro`; 13 niveles de expresión hasta primaria (literales, `(e)`, llamadas, `new`, `?.`). *void* solo retorno (§16.5). EBNF: `{}` repite, `[]` opcional, `()` agrupa, `|` alterna ([Aho07, §4.2]). Leer una producción es leer un contrato: todo `.inv` válido es una derivación desde `programa`; todo error sintáctico es una cadena sin derivación. Ejemplo: `int x = 5;` deriva `decl_variable → tipo IDENTIFICADOR "=" expresion ";"` con `expresion ⇒ expr_primaria ⇒ ENTERO_LIT`. La recursión `{ elemento }` equivale a `resto ::= resto elemento | ε` pero legible y sin recursión izquierda problemática para LL.

### 4.2 Nodos AST: el vocabulario del backend (≈1 página)
Tipos en `ast_nodes.py`: `Program(globales, subrutinas, clases, enums, main)`, `VarDecl/ConstDecl/ArrayDecl/MatrixDecl`, `Block`, `If/While/For/Foreach/DoWhile/Switch/Match/TryCatch`, `Return/Break/Continue`, `Assign/Call`, `Binary/Unary/Ternary`, `Literal/Ident/Index/Member/New/Null` (+POO). Cada nodo guarda línea/columna; sin ellas no hay diagnóstico ([Watt00, §4]). Árbol concreto guarda `;()`; AST los descarta y guarda semántica ([Aho07, §5.3]). El pretty-printer del AST es el puente didáctico: ver `NodoIf(cond, entonces, sino)` enseña más que mil diapositivas. Patrón Builder/Factory en `parser.py` + `ASTFactory`: cada `p_*` construye un nodo y lo retorna en `p[0]`; el padre los compone. Error típico: olvidar `p[0]` deja `None` y el intérprete falla lejos del origen.

### 4.3 LALR(1), conflictos y precedencia total (≈1 página)
PLY yacc es LALR(1) como yacc/Bison ([ply.readthedocs.io]; Cornell; Johnson). Shift/reduce desde ítems LR(0)+lookahead; fusión de núcleos = LALR compacta. Conflictos: shift/reduce (`else` colgante, `E→E+E` con `+`) y reduce/reduce. Reglas Johnson: mayor precedencia gana; empate left=reduce, right=shift, nonassoc=error; sin precedencia=shift+reporte. Jerarquía InvenioLang menor→mayor: `?:`(right)→`??`→`||`→`&&`→`|`→`^`→`&`→`== !=`→`< > <= >=`→`<< >>`→`+ -`→`* / %`→unarios(right)→primaria.
```python
precedence = (
    ('left','OP_OR'),('left','OP_AND'),
    ('left','OP_IGUAL','OP_DISTINTO'),
    ('left','OP_MENOR','OP_MAYOR','OP_MENOR_IGUAL','OP_MAYOR_IGUAL'),
    ('left','OP_SUMA','OP_RESTA'),('left','OP_MULT','OP_DIV','OP_MOD'),
    ('right','UMINUS','OP_NOT'),
)
```
Left=bucle (`a-b-c≡(a-b)-c`); right=recursión (`a?b:(c?d:e)`, `=`, unarios) ([Scott16, §2.3]). `UMINUS/%prec` da a `-x` prioridad de `*` ([dabeaz.com/ply]). `debug=True`+`parser.out`+`grammar_validator` certifican cero conflictos. Poder `LL(1)⊊SLR(1)⊊LALR(1)⊊LR(1)`; SLR falla en `S→L=R|R` por FOLLOW global, LALR acierta con lookahead específico. Recuperación modo pánico en `;`/`}` ([Grune12]).

### 4.4 Catálogo IL-SIN, 19 códigos (≈½ página)
`005` elemento inválido · `006` falta `}` · `010` falta `;` · `011/012` `)`/`]` · `015` `int a,b;` · `020` cabecera · `025/026/027` if/while/for · `030/031` expresión · `032/033` else huérfano/sin if · `035` ternario · `040` contexto · `050` función en bloque · `070` asignar arreglo · `080/081` matriz. Formato `[IL-SIN-NNN] arch:lín:col — msg` ([SpecInv, §15.8]).

### 4.5 Caso completo: de tokens a AST de un `si-sino` (≈1 página)
Entrada `si (x >= 10) { imprimir("sí"); } sino { imprimir("no"); }` → tokens `KW_IF ( IDENTIFICADOR OP_MAYOR_IGUAL ENTERO_LIT ) { KW_PRINT ( TEXTO_LIT ) ; } KW_ELSE { … }`. Derivación: `instruccion ⇒ if_stmt ⇒ "if" "(" expresion ")" bloque "else" bloque`; `expresion ⇒ … ⇒ IDENTIFICADOR OP_MAYOR_IGUAL ENTERO_LIT`. Acciones PLY: `p_if` construye `NodoIf(cond, entonces, sino)`; `p_expr_rel` construye `NodoBinario(">=", Ident(x), Lit(10))`. El pretty-printer muestra el árbol sin `()`/`;`/`{}`: la prueba de que el AST abstrae. Si falta el `;` tras `imprimir(…)`, `p_error` recibe el token `}` y emite `IL-SIN-010` esperando `;`, luego sincroniza: ejemplo vivo de modo pánico.

### 4.6 LL vs LR en una tabla y por qué PLY es LALR (≈1 página)
| | LL (descendente manual) | LR/LALR (PLY) |
|---|---|---|
| Dirección | predice desde `S` | reduce hacia `S` |
| Recursión izquierda | la cuelga (hay que eliminarla) | la ama (bucle natural) |
| Tabla | `FIRST/FOLLOW`, una entrada por no-terminal | estados LR(0)+lookahead, shift/reduce |
| Conflicto típico | FIRST solapados | shift/reduce, dangling else |
| Depuración | traza de llamadas | `parser.out`, nº de conflictos |
| En InvenioLang | Documento B lo enseña como intuición | repo lo implementa (producción) |
Conclusión ([Cooper22, §3]): para gramáticas de expresiones con 13 niveles, LALR con `precedence` es imbatible en brevedad; reescribirla a mano en LL exigiría factorizar cada nivel.

### 4.7 El `else` colgante y UMINUS a fondo (≈1 página)
`si(a) si(b) x(); sino y();` ¿a qué `si` pertenece el `sino`? Yacc/PLY eligen shift (el más interno) por defecto: coincide con C/Java y con la Spec. Es el shift/reduce más famoso (Johnson §else). Forzar lo contrario exigiría llaves obligatorias. **UMINUS:** en `3+4*-5`, el `-` unario debe tener prioridad de `*` aunque el `-` binario tenga la de `+`; `%prec UMINUS` le presta esa prioridad sin crear token real ([dabeaz.com/ply]). Sin él, `-5` se agruparía `(3+4)*-5`. Ambos casos demuestran que precedencia = semántica, no cosmética.

### 4.8 Debugging con `parser.out` (≈½ página)
`yacc(debug=True)` vuelca estados LR(0), transiciones y conflictos `shift 45, reduce 18 on ELSE`. Leer ese archivo es la habilidad que separa al que copia gramáticas del que las domina: muestra el estado exacto, los ítems activos y el lookahead culpable. `grammar_validator` automatiza el veredicto (cero conflictos), pero el humano debe interpretar el porqué.

### 4.9 Práctica calificada del capítulo (≈1 página)
Dado `int a = 2 + 3 * 4;`: dibuje tokens, árbol concreto, AST con `NodoBinario`, y la secuencia shift/reduce que lo acepta. Luego rompa la precedencia (quite la línea `MULT`) y anote cuántos conflictos aparecen en `parser.out` y qué salida errónea (`20` vs `14`) produce. Restaurar la línea y ver cero conflictos es entender LALR de verdad: el Hito H2 en un ejercicio.

### 4.10 Jurado del capítulo (≈½ página)
(1) ¿Concreto vs AST? — Auxiliares. (2) ¿Left vs right con ejemplos? — `-` bucle, `=` recursión. (3) ¿Conflicto shift/reduce en `else`? — Shift al interno. (4) ¿UMINUS para qué? — Prioridad unaria. (5) ¿`p[0]` olvidado qué pasa? — `None` aguas abajo. (6) ¿SLR vs LALR en `S→L=R|R`? — FOLLOW vs lookahead. (7) ¿Modo pánico dónde sincroniza? — `;`/`}`. (8) ¿Cero conflictos qué prueba? — Determinismo.

### 4.11 Cierre: la gramática como ley (≈½ página)
Todo programa válido es una derivación; todo error sintáctico, una cadena sin derivación con el prefijo válido más largo como pista. El parser no "adivina intenciones": aplica la ley (producciones + precedencia + recuperación). Quien interioriza esto deja de pelear con el parser y empieza a leer sus mensajes como citas de artículos legales: "se esperaba X en tal posición según tal regla".

---

---

---

---

---

---

## Capítulo 5. Semántica estática exhaustiva (≈3 páginas)

### 5.1 Entornos como pila y resolución (≈1 página)
Alcance léxico estático por bloques ([Scott16, §3.3]): E=[E0 global, E1 función, E2+ bloques]. `entrar=push({})`, `salir=pop()`, `declarar` en tope, `buscar` de arriba abajo (`symbol_table.py`). **Duplicado** mismo nivel→`IL-SEM-002`; **shadowing** interno→válido+`IL-WARN-001`; **ausente**→`IL-SEM-003`. Analogía carpetas anidadas. Sin tabla correcta colapsan tipos y ejecución ([Aho07, §2.7]). Ejemplo triple `n` (global=1, main=2, if=3): tres entradas, cada uso resuelve a la más interna visible; salir del bloque la olvida. Error clásico: buscar solo en tope rompe globales; no apilar params rompe recursión.

### 5.2 Reglas semánticas §14 (≈1 página)
Declaración antes de uso; `main` única `void main()`; aridad y tipos exactos (`052`); `void` sin valor (`061`); `break/continue` en ciclo/switch; índices enteros con límites en ejecución; arreglos por referencia; integradas no redeclarables (`080`); `const` inmutable (`031`); matrices 2 índices. Recorrido top-down con entorno heredado + atributos sintetizados ([Aho07, §5.1]).

### 5.3 Cobertura de retorno como flujo elemental (≈1 página)
`G(return)=true; G(if/else)=G(A)∧G(B); G(while)=false; G(seq)=∨` ([SpecInv, §14.6]). Sin `G(cuerpo)` en no-void→`050`. `while` nunca garantiza (0 iteraciones). Es dataflow embrionario que anticipa Cooper cap. 9. Ejemplo que falla: `si(c){return 1;}` sin `else` → `050`; que pasa: `si(c){return 1;}sino{return 2;}`. Casos `051/053` (incompatible/inaccesible) y `060` completan.

### 5.4 Catálogo IL-SEM, 25 códigos
`002` duplicado · `003` no declarado · `004/005` params · `010` mal uso · `020–023` main · `030/031/032` const/arreglo · `040/041` matriz · `050–053` retorno · `060/061` void · `070–073` contexto · `080/081` integrada/clase.

### 5.5 Tres programas que todo estudiante debe trazar a mano (≈1 página)
(a) Duplicado: `void main(){int x=1; int x=2;}` → segunda inserta en mismo mapa → `002`. (b) No declarado: `void main(){int y=z+1;}` → búsqueda agota pila → `003`. (c) Shadowing válido: `int n=100; void main(){int n=200; imprimir(n);}` → halla el interno, emite `WARN-001`, imprime 200. Trazar entornos paso a paso es el ejercicio que más sube la nota de validación: demuestra que se entiende pila, no solo sintaxis.

### 5.6 Funciones, aridad y `main` única (≈1 página)
Cada `FunctionDecl` registra firma `(nombre, [tipos params], retorno)`; cada llamada verifica longitud y compatibilidad (con promoción) → `052` si falla. `main` se registra aparte y se exige exactamente una con firma `void main()` → `020–023`. Los parámetros viven en E1, por eso la recursión funciona: cada llamada apila su propio E1 con sus valores. `break/continue` verifican una pila auxiliar de contextos de ciclo/switch → `070–073` fuera de ellos.

### 5.7 Implementación: hash + padres y gramáticas de atributos (≈1 página)
Cada nivel es un `dict` (hash O(1) promedio) con puntero al padre ([Appel04, §5]; [Scott16, §3.3]). Buscar sube punteros; insertar solo toca el tope; salir descarta el dict (libera memoria y evita fugas entre funciones). Las gramáticas de atributos ([Aho07, §5.1]) formalizan esto: entorno heredado que baja, tipos/errores sintetizados que suben. El visitor de `semantic.py` es esa teoría en código: `_visitar_Bloque` hace push/visita-hijos/pop; `_visitar_Ident` sintetiza "resuelto/no-resuelto". Entender heredado vs sintetizado permite leer cualquier analizador moderno.

### 5.8 Shadowing: política y advertencia (≈½ página)
Permitir shadowing con `WARN-001` (en vez de prohibirlo) es decisión pedagógica: enseña ámbito sin castigar refactors. Lenguajes como Java lo prohíben en locales; Python lo permite silenciosamente; InvenioLang lo permite ruidosamente. La advertencia incluye ambas posiciones (declaración externa e interna) para que el estudiante vea el ocultamiento.

### 5.9 Atributos heredados vs sintetizados con ejemplo (≈1 página)
`bloque(n: entero)` hereda el entorno de entrada; al salir sintetiza errores hallados dentro. `expresion` sintetiza su conjunto de variables libres; el padre las resuelve. Esta ida y vuelta es la traducción dirigida por sintaxis ([Aho07, cap. 5]): cada `p_*` recibe heredados por parámetros y retorna sintetizados en `p[0]`. Quien entiende esta disciplina lee `semantic.py` como prosa: cada visitador declara qué necesita (heredado) y qué produce (sintetizado).

### 5.10 Examen simulado de semántica (≈½ página)
(1) ¿`int x; { int x; x=1; }` es duplicado o shadowing? (shadowing, WARN). (2) `f(1,2)` con firma de 3 → ¿qué código? (052). (3) Función con `mientras(true){return 1;}` y nada más → ¿garantiza? (No: 050, el while puede no analizarse como garantía aunque sea infinito literal: la regla es sintáctica, no de valores). (4) `break` en `switch` → ¿válido? (Sí desde Etapa 6; antes solo ciclo). Justificar cada una con nivel de pila cierra la sección.

### 5.11 Práctica calificada del capítulo (≈1 página)
Escriba tres `.inv` mínimos: uno con `002`, uno con `003`, uno con shadowing + `WARN-001`; para cada uno dibuje la pila antes y después de cada declaración y marque dónde se detecta. Añada una función sin `return` en una rama y aplique `G()` para probar `050`. Estos cuatro archivos son evidencia H3 y defensa de la semana 7.

### 5.12 Jurado del capítulo (≈½ página)
(1) ¿Pila de qué? — Dicts con padre. (2) ¿Duplicado vs shadowing? — Nivel. (3) ¿`G(while)`? — false siempre. (4) ¿Aridad dónde? — Firma vs llamada. (5) ¿`main` cuántas? — Una. (6) ¿Heredado vs sintetizado? — Baja entorno, sube errores. (7) ¿`break` fuera? — 070. (8) ¿Integrada redeclare? — 080.

### 5.13 Cierre: el significado como resolución (≈½ página)
Un programa "tiene sentido" cuando cada uso resuelve a una declaración visible con firma compatible y cobertura de retorno. La tabla es el diccionario; el semántico, el corrector que verifica cada referencia contra él. Sin este paso, el tipador razonaría sobre fantasmas y el intérprete ejecutaría basura con forma correcta.

### 5.14 Lectura guiada y el error más caro (≈½ página)
Lea [Scott16, §3.3] (alcance) con un highlighter para "más interno visible"; [Aho07, §5.1] (atributos) marcando heredado/sintetizado; `symbol_table.py` y `semantic.py::_visitar_*` como espejo en código. El error más caro del capítulo: registrar `main` como función común y exigirle `return` con valor (rompe el Hito H3 entero). Separar `main` desde el día uno evita una semana de depuración.

### 5.15 Mapa semanal y entregable (≈½ página)
Lunes: pila con tres niveles en papel. Martes: `002/003/WARN` provocados. Miércoles: firmas y aridad. Jueves: `G()` en 5 funciones. Viernes: defensa de 5 minutos solo con la pila dibujada. Entregable: tabla de símbolos con push/busca/pop + 4 `.inv` + resumen de cobertura. Quien dibuja la pila sin dudar aprueba la semana 6–7 junta.

### 5.16 Demostración guiada: resolución paso a paso (≈1 página)
Programa: `int a=1; void f(int b){ imprimir(a+b); } void main(){ int a=2; f(3); }`. Pila inicial `[G:{a=1,f,main}]`; llamada `f(3)` apila `E1:{b=3}` sobre `[G]` (no sobre main: alcance léxico, no dinámico); `a` resuelve a `G.a=1` (no al `a=2` de main, invisible desde `f`); imprime 4. Si fuera alcance dinámico imprimiría 5: la diferencia observable que prueba léxico vs dinámico. Trazar qué ve cada función desde su punto de definición —no de llamada— es el teorema del capítulo hecho programa. Extensión: añada `{ int b=9; f(4); }` en main y verifique que `b` interno no afecta al parámetro `b` de `f` (niveles distintos, nombres coincidentes, cero interferencia).

---

---

---

---

---

---

---

---

---

---

## Capítulo 6. Sistema de tipos exhaustivo (≈3 páginas)

### 6.1 Juicios, reglas e inferencia bottom-up (≈1 página)
Juicio `Γ ⊢ e : τ` ([Scott16, §6]; [Appel04, §5]). Hojas: `5:int, 2.0:float, "x":string, true:bool, x:Γ(x)`. Binarios: igualdad salvo `int+float→float` con nodo `int_to_float` (única coerción); relacionales dan `bool`; `&& ||` y condiciones exigen `bool`; `% << >> & | ^ ~` solo `int`; `==` nominal (+`esIgual` Et.11); `match` exhaustivo (`022`); `?.` propaga nulo.
```python
def tipo_de(nodo, gamma):
    if es_literal(nodo): return tipo_hoja(nodo)
    ti, td = tipo_de(nodo.izq, gamma), tipo_de(nodo.der, gamma)
    if {ti, td} == {'int','float'}: return 'float'
    if ti != td: error('IL-TIPO-001')
    return ti
```

### 6.2 Promoción, arreglos y matrices (≈1 página)
Solo `int→float`, insertada en el AST para que el intérprete no piense. Arreglos `int[5]` homogéneos con índice `int`; matrices row-major 2 índices; `const int[3]` inmutable por elemento (`031` reutilizado, Et.11). `void` solo retorno. `texto_a_int("12")=12` pero `("ab")`→`IL-EJE-004` en runtime: el tipador garantiza forma, el runtime contenido.

### 6.3 Catálogo IL-TIPO, 14 códigos (≈1 página)
`001` incompatible (`int x="hola"`) · `010` `%` float · `011` bit no-int · `012` orden string/bool · `013/014` aridad · `015/016/017` índice/matriz/miembro · `018` `1&&2` · `019` `si(5)` · `020/021` retorno/arg · `022` match. Cada regla es un teorema comprobable en defensa: "muestre la derivación de tipos de `a+b*c`".

### 6.4 Derivaciones completas y errores que delatan (≈1 página)
Derive `float c = a + b` con `a:int, b:float`: `Γ⊢a:int`, `Γ⊢b:float` → promo → `float`. El verificador inserta `int_to_float(a)`; sin ese nodo el intérprete sumaría entero+flotante sin regla. Contraejemplos: `int x="hola"` falla en asignación (001); `si(5)` falla en condición (019) porque `5:int≠bool`; `7.0%2.0` falla (010) porque `%` es resto entero; `"a"<"b"` falla (012) porque orden solo vale en números. Memorizar estos cuatro cubre el 80% de preguntas de tipos.

### 6.5 Chequeo estático vs dinámico: quién atrapa qué (≈½ página)
El tipador atrapa formas (`si(5)`); el runtime atrapa contenidos (`texto_a_int("ab")`→`004`, `arr[99]`→`010`, `5/0`→`006`). Confundirlos lleva a exigir al tipador lo imposible (adivinar el valor de un `read`) o al runtime lo tardío (detectar `si(5)` ejecutando). La frontera es nítida: tipos = forma sin ejecutar; ejecución = valores ejecutando.

### 6.6 Nominal vs estructural y el `void` (≈1 página)
InvenioLang 1.0 es nominal: `int` y `float` son distintos aunque ambos sean números; solo la promo declarada los une. Las clases 2.0 extienden nominalidad con herencia (subclase asignable a ancestro = upcasting válido). Excepción única: tipo `funcion(...)` de primera clase (Et.12) con equivalencia estructural por firma. `void/vacio` no es valor: no hay variable `void`, no se opera, solo retorna procedimientos; usarlo como tipo de dato → error. Esta rigidez es intencional: enseña que los tipos son contratos, no etiquetas.

### 6.7 Funciones como tipos y aridad tipada (≈½ página)
Cada función tiene tipo ` (p1×p2×…×pn)→r`; la llamada verifica `n` y cada `pi` (con promo) → `020/021` si falla. `print` acepta cualquier `τ` (polimorfismo ad-hoc); `read` exige lvalue del tipo leído. El tipador recorre llamadas bottom-up igual que binarios: primero tipos de argumentos, luego compatibilidad con firma.

### 6.8 Reglas por operador en una tabla (≈1 página)
| Operador | Operandos | Resultado | Si no |
|---|---|---|---|
| `+ - * /` | `int,int→int`; con `float→float` (promo) | numérico | 001 |
| `%` | `int,int→int` | int | 010 |
| `== !=` | compatibles | bool | 001 |
| `< > <= >=` | numéricos | bool | 012 |
| `&& \|\|` | `bool,bool→bool` | bool | 018 |
| `!` | `bool→bool` | bool | 001 |
| `& \| ^ ~ << >>` | `int` | int | 011 |
| `?:` | `bool, τ, τ→τ` | τ | 019/001 |
| `??` | `τ?, τ→τ` | τ | 001 |
| `?.` | objeto?→miembro? | miembro? | 017 |
Esta tabla es el contrato del tipador: cada fila es una regla de inferencia con su código de violación.

### 6.9 Examen simulado de tipos (≈½ página)
(1) `int x = 2 + 3.0;` ¿válido? (No: resultado `float` → 001; declare `float x`). (2) `si("x")` → ? (019). (3) `true + 1` → ? (001). (4) `7 % 2.0` → ? (010). (5) `match` sin `default` ni todos los casos → ? (022). Resolver con derivaciones `Γ ⊢` en papel es el pase a H4.

### 6.10 Práctica calificada del capítulo (≈1 página)
Derive en papel `int a=5; float b=2.0; float c=a+b;` mostrando `Γ` tras cada declaración y el nodo `int_to_float` inserto. Luego fabrique cinco líneas, una por cada error `001,010,018,019,012`, y escriba el juicio que falla en cada una. Quien entrega estas seis derivaciones domina tipos; quien no, repetirá `si(5)` en defensa.

### 6.11 Jurado del capítulo (≈½ página)
(1) ¿Juicio de `5`? — `Γ⊢5:int`. (2) ¿Única promo? — `int→float`. (3) ¿`%` en qué? — Solo `int`. (4) ¿Condición de qué tipo? — `bool`. (5) ¿`&&` con `1`? — 018. (6) ¿`void` como variable? — Prohibido. (7) ¿Llamada verifica qué? — N y tipos. (8) ¿Estático vs dinámico? — Forma vs valor.

### 6.12 Cierre: tipos como contratos (≈½ página)
Cada anotación `τ` es una promesa comprobada sin ejecutar: "este valor siempre tendrá esta forma". La promo es la única cláusula de conversión automática; todo lo demás exige coincidencia. Quien firma contratos precisos (firmas de función, condiciones `bool`) recibe diagnósticos precisos; quien mezcla, recibe `IL-TIPO-*` con la derivación rota como prueba.

### 6.13 Lectura guiada y el error más caro (≈½ página)
Lea [Scott16, cap. 6] (juicios y equivalencia) escribiendo cada regla como `Γ ⊢`; [Appel04, §5] (entornos de tipos) comparando nominal vs estructural; `type_checker.py::_inferir_tipo` como implementación. El error más caro: permitir `int→string` implícito "por comodidad" (destruye la única promo y vuelve ambiguo cada `+`). La rigidez nominal es la que hace enseñable el sistema.

### 6.14 Mapa semanal y entregable (≈½ página)
Lunes: juicios de hojas. Martes: binarios + promo con nodo inserto. Miércoles: tabla por operador memorizada. Jueves: 5 errores provocados con juicio roto anotado. Viernes: derivación completa de `a+b*c` en pizarra. Entregable: verificador con `_inferir_tipo` + 6 derivaciones + tabla. Es la evidencia de la semana 8.

### 6.15 Demostración guiada: derivación con promo inserta (≈1 página)
`Γ=[a:int,b:float] ⊢ a+b*c` con `c:int`: primero `b*c` → `float*int` → promo `c` → `float`; luego `a+(todo)` → `int+float` → promo `a` → `float`. El AST final contiene dos nodos `int_to_float` que el fuente no mostraba: el tipador reescribe, no solo verifica. Si se quita la promo, la derivación se atasca en `int≠float` con `001`: la prueba de que la regla es necesaria, no decorativa. Dibuje el árbol antes y después de insertar conversiones: esa pareja de dibujos vale más que diez diapositivas.

---

---

---

---

---

---

---

---

---

---

## Capítulo 7. Representación intermedia TAC (≈3 páginas)

### 7.1 Por qué aplanar: del árbol a cuádruplas (≈1 página)
El árbol es recursivo y jerárquico; el TAC `(op,arg1,arg2,result)` con `tᵢ/Lᵢ` es lineal y explícito ([Aho07, §6.2]; WPI §6.3.3; GeeksforGeeks). Ventaja: independiza frontend/backend y expone flujo. Formas: `x=y op z | x=op y | x=y | goto L | if x relop y goto L | param/call/ret | array_get/set`. `ir.py: GeneradorIR` (Visitor) + `Instr` + `NoSoportadoIR` (POO/matrices fuera de alcance documentado).

### 7.2 Esquemas de traducción por construcción (≈1 página)
`x=e→eval e→t; store; if(c)A else B→if_false c→L1; A; goto L2; L1:B; L2:`; `while→L0:if_false→L1;cuerpo;goto L0;L1:`; `for→init+while`; `call→param…;call→t`; `a[i]→bounds;get`; `a+b` con promo→`int_to_float;add`. Ejemplo `float c=a+b` (a=5,b=2.0): `const 5→t1; const 2.0→t2; int_to_float t1→t3; add t3,t2→t4; store t4→c`. Triples `(op,arg1,arg2)` nombran por posición `(n)`; cuádruplas por nombre (estables al mover); indirectas por punteros ([GateVidyalay]).

### 7.3 TAC de un factorial completo (≈1 página)
`int f(int n){si(n<=1){return 1;}return n*f(n-1);}` → `L_f: le n,1→t1; if_false t1→L1; const 1→t2; ret t2; goto L2; L1: sub n,1→t3; param t3; call f→t4; mul n,t4→t5; ret t5; L2:`. Ver `ir.py` y GramáticaFormal para trazas reales. Invariante H4: `MaquinaTAC` ≡ intérprete en estructurados.

### 7.4 Cuádruplas vs triples vs indirectas con el ejemplo canónico (≈1 página)
`a = b*-c + b*-c` sin optimizar: 6 instrucciones, 5 temporales (`t1=-c, t2=b*t1, t3=-c, t4=b*t3, t5=t2+t4, a=t5`). Cuádrupla `(op,arg1,arg2,result)` nombra cada resultado (estable al mover); triple `(op,arg1,arg2)` nombra por posición `(n)` (mover obliga renumerar); indirecta añade capa de punteros (reordena sin renumerar) ([GateVidyalay]; WPI §6.3.3). Por eso `ir.py` usa cuádruplas (`Instr` con `resultado`): el optimizador mueve filas libremente. Contar instrucciones/temporales es pregunta clásica: el `=` final cuenta como instrucción pero no crea temporal; cada `-` unario cuenta aunque parezca "gratis".

### 7.5 Límites del IR InvenioLang y por qué son honestos (≈½ página)
Cubre estructurado + Etapa 6; rechaza POO/matrices con `NoSoportadoIR`. Alternativa deshonesta sería generar TAC a medias y fallar en ejecución; la honesta es rechazar en traducción con mensaje claro. Documentar no-soporte es también teoría: define el subconjunto compilable.

### 7.6 Direcciones de arreglos y row-major (≈1 página)
`a[i]` → `t_addr = base + i*ancho; t = mem[t_addr]` con `bounds_check 0<=i<n` antes ([Aho07, §6.4]). Matriz `m[i][j]` row-major: `addr = base + (i*ncols + j)*ancho`. El chequeo genera `IL-EJE-010` en vez de corrupción silenciosa: el TAC enseña que la seguridad cuesta instrucciones explícitas. `ir.py` cubre 1-D; 2-D se documenta como extensión con la misma fórmula.

### 7.7 Llamadas y retorno en TAC (≈½ página)
Convención: `param a1 … param an; call f → t;` el receptor guarda `t`; `ret v` copia a temporal de retorno y salta al epílogo. Recursión funciona porque cada `call` apila marco en `MaquinaTAC` igual que el intérprete. Ver el mismo factorial en AST, TAC y pila_runtime cierra el círculo frontend→backend.

### 7.8 Traducción de `para` y `switch` paso a paso (≈1 página)
`para(int i=0;i<5;i=i+1){cuerpo}` → `i=0; L0: if_false i<5 goto L1; cuerpo; i=i+1; goto L0; L1:`. Nótese que `for_act` va después del cuerpo: detalle que el AST oculta y el TAC revela. `switch(e){case 1: A; case 2: B; default: C}` → eval `e→t`; `if_false t==1 goto L1; A; goto Lfin; L1: if_false t==2 goto L2; B; goto Lfin; L2: C; Lfin:` con fallthrough si falta `break` (semántica C documentada en Etapa 6). Traducir control a saltos es el momento "¡ajá!" del backend.

### 7.9 Examen simulado de IR (≈½ página)
(1) ¿Cuántas instrucciones y temporales para `a=b+c*d`? (2 mul/add + store = 3 instr, 2 temps). (2) ¿Por qué `t=5` sin usos posteriores es candidata a DCE? (live-out vacío). (3) Dé la dirección de `m[1][2]` en matriz 3×4 de enteros base 1000, ancho 4. (Respuesta: `1000+(1*4+2)*4=1024`.) Estos tres prueban TAC, liveness y row-major de una vez.

### 7.10 Práctica calificada del capítulo (≈1 página)
Traduzca a TAC `si (x>0) { y=1; } sino { y=2; }` con etiquetas y temporales, luego el `para` del §7.8. Marque dónde insertaría `bounds_check` si `y` fuera `a[i]`. Compare su TAC con el generado por `ir.py`: las etiquetas pueden diferir en número pero no en estructura (mismo grafo). Esa invariancia estructural es lo que el docente verifica.

### 7.11 Jurado del capítulo (≈½ página)
(1) ¿Cuádrupla campos? — op,arg1,arg2,res. (2) ¿Triple nombra cómo? — Posición. (3) ¿`a=b+c*d` cuántos? — 3/2. (4) ¿`for` a qué se traduce? — init+while. (5) ¿Fallthrough en switch? — Sin `break` cae. (6) ¿`NoSoportadoIR` cuándo? — POO/matriz. (7) ¿Dirección `m[1][2]` 3×4? — 1024. (8) ¿Invariante H4? — TAC≡árbol.

### 7.12 Cierre: aplanar para razonar (≈½ página)
El TAC no añade significado: lo hace explícito y lineal para que el optimizador y la VM razonen sin recursión. Temporales, etiquetas y chequeos son el precio de la explicitud; la recompensa es un backend auditable instrucción por instrucción. Todo lenguaje serio pasa por aquí, aunque sea brevemente.

### 7.13 Lectura guiada y el error más caro (≈½ página)
Lea [Aho07, §§6.2–6.4] (cuádruplas y control) traduciendo cada ejemplo a mano; WPI §6.3.3 (quads mínimos); `ir.py::GeneradorIR` como plantilla. El error más caro: generar el salto con la condición invertida (`if_true` donde va `if_false`) — el programa "casi funciona" e invierte todos los `si`. Probar con condición siempre-falsa lo delata en un caso.

### 7.14 Mapa semanal y entregable (≈½ página)
Lunes: cuádruplas de 3 expresiones. Martes: `if/while/for` a saltos. Miércoles: llamadas + arreglos con `bounds_check`. Jueves: factorial completo y comparación con `ir.py`. Viernes: defensa "misma estructura, distintas etiquetas". Entregable: generador del subconjunto + trazas + invariante TAC≡árbol en 3 programas.

### 7.15 Demostración guiada: del `para` al grafo (≈½ página)
El TAC del `para` forma un diamante con ciclo: cabecera `L0`, cuerpo, incremento, salto atrás, salida `L1`. Dibuje nodos=instrucciones y aristas=saltos: el CFG de 4 bloques que dataflow analizará en el Cap. 8. Ver el mismo programa como texto, AST, TAC y grafo es la alfabetización completa del backend: cuatro alfabetos, un significado.

---

---

---

---

---

---

---

---

---

---

## Capítulo 8. Optimización dataflow (≈3 páginas)

### 8.1 Teoría: retículos, IN/OUT y punto fijo (≈1 página)
Dataflow iterativo ([Cooper22, cap. 9]; O'Reilly): `IN[B]=∪ OUT[pred]; OUT=gen∪(IN−kill)` hasta punto fijo monótono. Reaching definitions→propagation; liveness→DCE ([Appel04, §10]); SSA simplifica a un def por nombre; interprocedural con call-graph+jump functions (Callahan-Cooper). Sin convergencia no hay certificación.

### 8.2 Cuatro pasadas con ejemplos antes/después (≈1 página)
**Folding:** `2+3*4→14` (sin efectos, siempre correcta [Aho07, §9.2]). **Propagation:** retículo `⊤>c>⊥`; `x=5;y=x+1→y=6` hasta reasignación. **DCE:** `live-out=∅`→borra. **Peephole:** `goto L1;L1:→∅`. Orden fold→prop→fold→DCE→peephole, cada Strategy con conteo en `ir.py`. Ejemplo: `x=2+3*4; si(true){…}sino{…}` → `x=14` + rama muerta eliminada.

### 8.3 Corrección y códigos IL-EST (≈1 página)
Preserva semántica observable (misma salida y errores). `IL-EST-001…004` switch/ternario, `010–014` std, `015–017` archivos. POO `020–034` fuera del núcleo. Pregunta defensa: "dé un folding 3→1 y pruebe que no cambia salida".

### 8.4 Liveness con ejemplo numérico y SSA en una idea (≈1 página)
Bloque `t1=2; t2=3; t3=t1+t2; x=t3; return x`: live-out de `t1` incluye la suma, así que no se borra; si después nadie lee `t2`, su definición es muerta. Ecuaciones `IN/OUT` con `gen/kill` se iteran hasta punto fijo; con SSA (un def por nombre con φ en joins) el análisis se vuelve disperso y lineal ([Cooper22, cap. 9]; [Appel04, §10]). InvenioLang no exige SSA al estudiante, pero entenderla explica por qué propagation converge rápido en código sin joins y lento en ciclos (hay que iterar).

### 8.5 Orden de pasadas y cómo probar equivalencia (≈½ página)
fold→prop→fold→DCE→peephole: propagar crea nuevas constantes que permiten más folding; limpiar muertos al final evita resucitarlos. Prueba: ejecutar los 9 §17 por intérprete y por `MaquinaTAC` y comparar byte a byte; si difieren, la pasada es incorrecta por definición, por elegante que parezca. Esa es la ética del optimizador.

### 8.6 Antes/después real de un bloque (≈1 página)
Antes: `t1=2; t2=3; t3=t1*t2; x=t3; t4=true; if_false t4 goto L1; y=1; goto L2; L1: y=2; L2:`. Folding: `t3=6`. Propagation: `x=6`. DCE: `t1,t2,t3` muertas (nadie las relee) → borradas. Peephole: `if_false true` es `goto L1` directo… pero como `t4=true` constante, el salto es incondicional y la rama `y=1` muere (DCE de bloques con análisis de alcanzabilidad). Después: `x=6; y=2`. Mismo observable, 9→2 instrucciones. Este ejemplo, contado en voz alta, demuestra dominio de las 4 pasadas a la vez.

### 8.7 Cuándo NO optimizar (≈½ página)
No plegar llamadas con efectos (`read()`, `azar()`); no propagar a través de asignaciones; no borrar stores a globales/arreglos (vivos por alias); no mover código sobre `try/catch` que capture `IL-EJE-*`. Optimizar es prometer equivalencia: ante la duda, no tocar. Esa prudencia es la mitad de la nota de backend.

### 8.8 Punto fijo en 5 iteraciones con ejemplo (≈1 página)
CFG diamante `B0: x=2 → B1/B2 → B3: y=x+1`. Iteración 1: OUT(B0)={x=2}; IN(B1)=IN(B2)={x=2}; ambas propagan; B3 recibe `x=2` por ambos caminos → `y=3`. Si B2 reasignara `x=5`, B3 recibiría `{2,5}`=⊤ (no constante) y no plegaría: ejemplo de join que mata la oportunidad. Iterar hasta que ningún IN cambie es el punto fijo; con ciclos se repite (while) hasta estabilizar. Quien traza estas 5 iteraciones entiende dataflow mejor que quien memoriza definiciones.

### 8.9 SSA con φ en un párrafo operativo (≈½ página)
Renombre `x1=2; si(c){x2=3;} x3=φ(x1,x2); y=x3+1`: cada def es única; φ elige según camino. Propagation se vuelve local por nombre (sin sets por bloque) y converge en tiempo casi lineal ([Cooper22, cap. 9]). InvenioLang no lo exige, pero citarlo en defensa muestra horizonte.

### 8.10 Práctica calificada del capítulo (≈1 página)
Tome el bloque del §8.6 y aplique a mano fold→prop→DCE→peephole numerando instrucciones eliminadas y justificando cada una con live-out o retículo. Luego diseñe un caso donde propagation NO aplica (join con dos constantes distintas) y uno donde DCE NO puede borrar (store a global). Entregar los tres demuestra que se sabe cuándo sí y cuándo no: la marca del optimizador prudente.

### 8.11 Jurado del capítulo (≈½ página)
(1) ¿Ecuaciones dataflow? — IN/OUT gen/kill. (2) ¿Folding siempre? — Sin efectos sí. (3) ¿Prop cuándo no? — Join ⊤ o reasignación. (4) ¿DCE condición? — live-out vacío. (5) ¿Peephole ejemplo? — `goto L;L:`. (6) ¿Orden y por qué? — fold-prop-fold-DCE-peephole. (7) ¿SSA qué resuelve? — Un def, φ en joins. (8) ¿Prueba de corrección? — Byte a byte vs árbol.

### 8.12 Cierre: optimizar es prometer (≈½ página)
Cada pasada firma "mismo observable, menos costo". La firma se cobra con la prueba byte a byte en los 9 §17. Sin esa prueba, la optimización es decoración; con ella, es ingeniería. El backend honesto prefiere no tocar a tocar mal.

### 8.13 Lectura guiada y el error más caro (≈½ página)
Lea [Cooper22, cap. 9] (punto fijo) iterando un diamante a mano; [Aho07, §9.2] (folding) plegando una expresión; `ir.py` pasadas Strategy contando cambios. El error más caro: propagar una constante a través de una llamada con efectos (`x=read(); y=x+1` → `y=read()+1` duplicando la lectura). Congelar propagation ante llamadas/efectos lo evita.

### 8.14 Mapa semanal y entregable (≈½ página)
Lunes: folding en 5 expresiones. Martes: propagation con/sin join. Miércoles: DCE con live-out calculado. Jueves: peephole + orden completo en un bloque. Viernes: prueba byte a byte en 3 §17. Entregable: 4 pasadas con conteos + ejemplo 9→2 + casos donde NO aplica. Es la evidencia syllabus Unidad IX.

### 8.15 Demostración guiada: convergencia en el ciclo (≈½ página)
`x=0; mientras(x<3){x=x+1;}`: iteración 1 propaga `x=0` a la condición; tras el cuerpo `x=1` invalida; iteración 2 propaga `x=1`… el análisis itera hasta que el join de cabecera deja de cambiar (⊤ por múltiples llegadas). Por eso los ciclos cuestan iteraciones y los diamantes una: la convergencia es el precio de los joins. Trazar 3 vueltas del punto fijo enseña más que definirlo.

---

---

---

---

---

---

---

---

---

---

## Capítulo 9. Interpretación exhaustiva + PLY aplicado (≈3 páginas)

### 9.1 SOS por instrucción (≈1 página)
Semántica operacional ([Scott16, §3.2]; [Nystrom21, §§5–8]): `⟨E,x=e⟩→E[x↦v]`; `si` una rama; `mientras` punto fijo; `para` azúcar; `return` aborta con valor (`ReturnException`); `romper/continuar` abortan iteración; `&& || ?:/// ??` cortocircuito (rama descartada jamás se evalúa). Cada `visit_*` es una regla de inferencia.

### 9.2 Visitor, marcos, valor vs referencia (≈1 página)
`ejecutar(nodo)→_ejecutar_Tipo` ([Watt00]; Nystrom visitor): global persistente + `pila=[{}]`; llamada=push+ligar+ejecutar+pop (valor) o alias (arreglo/objeto) ([Scott16, §7.3]; [Appel04, §6]). Recursión apila marcos (`factorial(5)`=6); límites-fusible `001` overflow32, `002/006` ÷0, `003/004/005` conversión, `010` índice/nulo, `020–022` read, `030` 1M iters, `040` 500 calls, `050` memoria. Integradas 8×3 + stdlib Et.6 (cadenas/mate/archivos). Nueve §17 como oráculo (≥7/9, 1–5 obligatorios).

### 9.3 PLY de punta a punta y defensa (≈1 página)
Lex: `tokens`, `t_*`, `t_ignore/error/newline`, `lex.lex(module)`; yacc: `tokens` importado, `precedence`, `p_*` con docstring-regla, `p[0]/len(p)`, `p_error`, `yacc.yacc(debug)`; `parser.out/parsetab` borrar al cambiar gramática; `UMINUS/%prec`, nonassoc ([BeazleyPLY]; Johnson). Diez preguntas §V del doc anterior + "dibuje pila triple-n, derive tipos de `a+b*c`, dé TAC+folding". Bibliografía APA + §13 + Anexos A–C cierran.

### 9.4 Traza completa de `factorial(5)` por marcos (≈1 página)
`main→f(5)→f(4)→f(3)→f(2)→f(1)`: 6 marcos vivos en el pico, cada uno con su `n` y su punto de retorno. Al llegar a `n<=1` retorna 1; cada padre multiplica y retorna; al vaciarse la pila `main` imprime 120. Si falta el caso base, la pila crece hasta 500 y `IL-EJE-040` la corta: el fusible convierte no-terminación en diagnóstico localizable. Dibujar esta pirámide de memoria es la mejor respuesta a "¿qué es recursión?".

### 9.5 Nueve programas §17 como oráculo y plan de defensa (≈1 página)
Hola (E/S), tipos (5 + promo), condicionales (clasificador), ciclos (cuenta/suma/impares), funciones (factorial/primos), procedimientos (referencia), arreglos (ordenado), matrices (transpuesta), ventas (integrador). H4 exige ≥7/9 exactos con 1–5 obligatorios. Defensa: un válido, uno por familia `LEX/SIN/SEM/TIPO/EJE`, un original con arreglos+recursión, y modificación en vivo pedida por el docente (ej. cambiar `<=` por `<` y predecir la salida antes de ejecutar). Quien predice, entiende.

### 9.6 Tabla de las 24 integradas y stdlib (≈1 página)
Conversiones (8×3): `int_a_float≡int_to_float≡entero_a_real`, `float_a_int≡float_to_int≡real_a_entero` (trunca, `003` si desborda/no-finito), `int_a_texto`, `float_a_texto` (siempre con punto), `texto_a_int` (`004` si no numérico), `texto_a_real`, `bool_a_texto`, `texto_a_bool`. Cadenas (Et.6): `longitud_texto, subcadena, mayusculas, minusculas, caracter_en, indice_de, recortar`; mate: `raiz_cuadrada, elevar, absoluto, piso, techo, azar`; archivos: `leer/escribir/agregar/existe_archivo` (`015–017`) + `invertir_texto`. Todas reservadas (`080` si se redeclaran) y con códigos propios de fallo convertidos a `IL-EJE-*` con posición.

### 9.7 Guía de defensa H4 en 10 minutos (≈½ página)
Minuto 0–2: dibuja pipeline con entradas/salidas. 2–4: tokeniza una línea y justifica `>=` por longitud. 4–6: deriva `a+b*c` por niveles y dibuja su AST. 6–8: traza pila del triple-`n` y un factorial. 8–10: muestra un TAC con su folding y declara la equivalencia. Si algún minuto falla, esa es la sección a repasar: el examen se auto-diagnostica.

### 9.8 Cortocircuito y efectos: el experimento decisivo (≈1 página)
`falso && leer()` jamás lee; `verdad || leer()` jamás lee; `falso ? leer() : 1` vale 1 sin leer. Si el intérprete evaluara ambas ramas, el programa pediría entrada de más: observable y calificable. Implementarlo exige evaluar condición primero y solo una rama/cadena: la pereza es corrección, no pereza. El ternario y `??`/`?.` heredan la regla. Demostrarlo con un programa que cuenta lecturas es el experimento que convence al jurado de que se entiende evaluación, no solo sintaxis.

### 9.9 Checklist oral de 60 segundos por fase (≈½ página)
Léxico: tripleta + munch + `lineno`. Sintaxis: `p[0]`, precedencia, `p_error`. Semántica: push/busca/pop, 002/003/WARN. Tipos: bottom-up + promo. IR: cuádrupla + etiquetas. Opt: 4 pasadas + equivalencia. Ejecución: visitor + marcos + fusibles. Recitarlo sin titubear son 3 páginas habladas: la defensa entera.

### 9.10 Práctica calificada del capítulo (≈1 página)
Prepare la carpeta H4: 9 §17 ejecutados con salida anotada, 3 originales (uno con arreglo+recursión), 5 con error (uno por familia) con código esperado, y un TAC con su optimización contada por pasada. Ensaye la defensa de 10 minutos del §9.7 grabándose: si algún minuto excede, recorte ejemplo, no teoría. Esta carpeta es literalmente la evidencia de las semanas 9–11.

### 9.11 Jurado del capítulo (≈½ página)
(1) ¿SOS de `x=e`? — Evalúa y actualiza. (2) ¿Valor vs referencia? — Copia vs alias. (3) ¿Marcos de `factorial(5)`? — 6. (4) ¿Fusible loop/recursión? — 1M/500. (5) ¿Cortocircuito ejemplo? — `false&&leer()` no lee. (6) ¿24 integradas de qué? — 8×3 conversiones. (7) ¿H4 exige? — 7/9, 1–5. (8) ¿PLY punta a punta? — tokens, precedence, `p[0]`, debug.

### 9.12 Cierre: ejecutar es cumplir promesas (≈½ página)
Cada fase prometió algo; el intérprete las cobra todas: tokens fiables, AST determinista, nombres resueltos, tipos compatibles, TAC equivalente. Cuando imprime lo esperado en 7/9 §17, no "funciona por suerte": cumple nueve capítulos de contratos. Esa es la defensa H4 en una frase.

### 9.13 Lectura guiada y el error más caro (≈½ página)
Lea [Nystrom21, caps. 5–8] (visitor, entornos, resolución) implementando el `Environment` mínimo; [Scott16, §7.3] (valor vs referencia) con aliasing dibujado; `interpreter.py` marcos y `builtins.py` códigos. El error más caro: compartir el dict del marco entre llamadas (todas ven las mismas locales y la recursión colapsa). Crear dict nuevo por `call` es la línea que sostiene todo el capítulo.

### 9.14 Mapa semanal y entregable H4 (≈½ página)
Lunes: visitor + SOS de cada instrucción. Martes: marcos y factorial trazado. Miércoles: 24 integradas + fusibles provocados. Jueves: 9 §17 con tabla producido/esperado. Viernes: defensa 10 minutos grabada. Entregable: intérprete + carpeta H4 + TAC equivalente. Es la evidencia DocB Semana 9 y la puerta a H5/InvenioFest.

### 9.15 Demostración guiada: aliasing que sorprende (≈½ página)
`void doblar(int[] a){ a[0]=a[0]*2; } void main(){ int[2] v={3,4}; doblar(v); imprimir(v[0]); }` imprime 6, no 3: el arreglo se aliasó, el escalar no lo habría hecho. Cambie el parámetro a `int x` con `x=x*2` y `main` imprime el valor original: la pareja de programas demuestra valor vs referencia sin discurso. Quien los ejecuta y explica aprueba ejecución ante cualquier jurado.

---

---

---

---

---

---

---

---

---

---

## Bibliografía (APA)

Aho, A. V., Lam, M. S., Sethi, R., & Ullman, J. D. (2007). *Compilers: Principles, Techniques, and Tools* (2.ª ed.). Pearson. Caps. 1–2 frontend/backend y Fig. 1.6; 3 léxico/AFD; 4 sintaxis/FIRST/FOLLOW; 5 traducción; 6 IR/TAC; 7 runtime; 8 generación; 9 optimización; Ap. A frontend completo.
Cooper, K. D., & Torczon, L. (2022). *Engineering a Compiler* (3.ª ed.). Morgan Kaufmann. Back-end, dataflow iterativo punto fijo, SSA, scalar opts, selección/planificación/registros.
Scott, M. L. (2016). *Programming Language Pragmatics* (4.ª ed.). Morgan Kaufmann. Caps. 2 sintaxis, 3 semántica/alcance, 6 tipos, 7 llamadas.
Watt, D. A., & Brown, D. F. (2000). *Programming Language Processors in Java*. Prentice Hall. Lexers manuales, AST, visitors.
Grune, D. et al. (2012). *Modern Compiler Design* (2.ª ed.). Springer. Recuperación modo pánico, IR, peephole.
Parr, T. (2013). *The Definitive ANTLR 4 Reference*. Pragmatic. Contraste ALL(*) vs LALR.
Nystrom, R. (2021). *Crafting Interpreters*. Genever Benning. P.II jlox tree-walk (scan→parse→eval, Visitor, Environments parent-pointer) vs P.III clox bytecode.
Appel, A. W. (2004). *Modern Compiler Implementation*. Cambridge UP. Marcos, liveness, linear-scan.
Beazley, D. *PLY (Python Lex-Yacc)* v3.11/4.0 + repo `dabeaz/ply` (U. Chicago 2001; LALR(1) por reflexión; precedencia, UMINUS/%prec, optimize/lextab).
Johnson, S. C. *Yacc: Yet Another Compiler Compiler*. Reglas 1–4 shift/reduce, `else` colgante.
Universidad Invenio (2026). *Spec §§1–19; gramatica.ebnf; Documento B; Syllabus TIIT2002.2.*

---

## 13. Referencias web verificadas (sep-2026)

PLY: `https://ply.readthedocs.io/en/latest/ply.html` (LALR, lex/yacc, AST, vacías, precedencia, Aho/Levine prerrequisito); `https://ply.readthedocs.io/en/latest/index.html` (Py≥3.6, diagnóstico novatos); `http://www.dabeaz.com/ply/ply.html` (reflexión sin codegen, UMINUS/%prec, optimize); `https://github.com/dabeaz/ply` (2001 Chicago, cero deps).
Dragon: índice caps. 1–11 + Ap. A; Fig. 1.6 frontend/backend y fases agrupables.
Nystrom: `https://craftinginterpreters.com/a-tree-walk-interpreter.html`, `/a-map-of-the-territory.html`, `/statements-and-state.html` (montaña, tree-walk vs single-pass vs transpiler, `execute/evaluate`, `define/assign`, parent-pointer).
TAC: `https://www.geeksforgeeks.org/compiler-design/three-address-code-compiler/`, `https://web.cs.wpi.edu/~cs544/PLT6.3.3.html`, `https://iq.opengenus.org/three-address-code`, `https://www.gatevidyalay.com/implementation-of-three-address-code/` (formas, `a=b*-c+b*-c` 6/5, cuádrupla/triple/indirecta).
LALR: `https://www.cs.cornell.edu/courses/cs4120/2026sp/notes/lr/`, `https://www.cs.utexas.edu/~novak/yaccpaper.htm`, `https://kindatechnical.com/theory-of-computation/lalr-vs-lr-vs-slr-parser-comparison.html`, GeeksforGeeks YACC/SLR-CLR-LALR (jerarquía LL⊊SLR⊊LALR⊊LR, `S→L=R|R`).
Dataflow: O'Reilly Cooper cap. 9, `https://www.geeksforgeeks.org/compiler-design/data-flow-analysis-compiler/`, ResearchGate Callahan-Cooper (IN/OUT, gen/kill, SSA, jump functions).

---

## Anexo A — EBNF íntegra

```
programa ::= { elemento_programa } ;
elemento_programa ::= decl_global | def_funcion | def_procedimiento | def_main | class_decl | enum_decl | interface_decl ;
decl_variable ::= tipo IDENTIFICADOR [ "=" expresion ] ";" ;
decl_constante ::= "const" tipo IDENTIFICADOR "=" expresion ";" ;
tipo ::= "int" | "entero" | "float" | "real" | "string" | "texto" | "bool" | "logico" ;
bloque ::= "{" { elem_bloque } "}" ;
if_stmt ::= "if" "(" expresion ")" bloque [ "else" bloque ] ;
while_stmt ::= "while" "(" expresion ")" bloque ;
for_stmt ::= "for" "(" [ for_init ] ";" [ expresion ] ";" [ for_act ] ")" bloque ;
expresion ::= expr_coalesce [ "?" expresion ":" expresion ] ;
expr_coalesce ::= expr_or { "??" expr_or } ; expr_or ::= expr_and { "||" expr_and } ;
expr_and ::= expr_bitor { "&&" expr_bitor } ; expr_bitor ::= expr_bitxor { "|" expr_bitxor } ;
expr_bitxor ::= expr_bitand { "^" expr_bitand } ; expr_bitand ::= expr_igual { "&" expr_igual } ;
expr_igual ::= expr_rel { ("==" | "!=") expr_rel } ; expr_rel ::= expr_shift { ("<" | ">" | "<=" | ">=") expr_shift } ;
expr_shift ::= expr_sum { ("<<" | ">>") expr_sum } ; expr_sum ::= expr_mul { ("+" | "-") expr_mul } ;
expr_mul ::= expr_unaria { ("*" | "/" | "%") expr_unaria } ;
expr_unaria ::= ("-" | "!" | "~" | "++" | "--") expr_unaria | expr_primaria [ ("++"|"--") ] ;
```

## Anexo B — 139 códigos
LEX 14 (001–014) · SIN 19 · SEM 25 · TIPO 14 · EJE 13 · WARN 7 · POO 29 · EST 14. Formato `[IL-XXX-NNN] archivo:línea:columna — mensaje` (§15.8).

## Anexo C — URLs
PLY (4), Dragon (3), Nystrom (3), TAC (4), LALR (5), Dataflow (3): ver §13 para lista clicable completa (26 URLs contando variantes http/https).
