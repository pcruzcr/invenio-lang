# InvenioLang 11.0.0 — Informe técnico del compilador

> Fecha: 2026-10-22. Auditoría en solo lectura: gramática reconstruida en memoria, 208 programas ejecutados en los 5 motores y fallos reproducidos con `api.ejecutar`. Forma parte de `docs/informes/` (ver [README](README.md)).

Alcance: arquitectura, corrección del compilador fase por fase (como caso de estudio para **Lenguajes Formales y Autómatas 1 y 2 / Compiladores**) e inventario de funcionalidades con su uso pedagógico y comercial.

## 1. Resumen ejecutivo

| Dimensión | Veredicto | Nota (0-10) |
|---|---|---|
| Front-end sintáctico (gramática LALR) | Sólido, real y verificable | 8.5 |
| Léxico (PLY con regex) | Funciona, con 4 fallos; no muestra autómatas | 6.5 |
| Semántico y tipos | Muy completo (POO, genéricos, interfaces), con huecos en el flujo de control | 8 |
| Intérprete de árbol (motor de referencia) | 208/208 programas correctos, pero **2 fallos de corrección** | 7 |
| IR, optimización, SSA y registros | Real y didáctico; cobertura parcial (sin POO) y **1 fallo grave (recursión de cola)** | 6.5 |
| Herramientas para LF1 (autómatas) | **Casi ausentes** (solo prosa) | 2 |
| Herramientas para LF2 (gramáticas y parsing) | FIRST/FOLLOW, estados LALR y conflictos reales; faltan tabla LL(1), traza de desplazar/reducir, derivaciones y CST | 5.5 |
| Visualización, diagramas, bloques y UML | Excelente, bidireccional y accesible | 9 |
| Ecosistema docente (currículo, autograder, LMS, plagio) | Muy bueno, poco integrado en la CLI | 7.5 |
| Higiene del release (git, legado, docs, CI) | **Deficiente**: v11 sin commitear, legado en disco, docs desfasadas | 3 |

**Conclusión:** el núcleo todavía **no** funciona al 100 %. Hay 10 fallos de corrección verificados (§4) y el IR solo cubre ~66 % de los programas (sin POO). Para LF1 falta casi todo lo de autómatas; para LF2 falta exponer como artefactos lo que PLY ya calcula. Ninguno es un problema de diseño: la arquitectura (fachada única `core/compiler.py`, API `api.py`) es correcta y permite cerrarlos.

## 2. Arquitectura

### 2.1 Pipeline real
```
fuente .inv ─► Lexer (PLY lex, 87 tokens, 83 lexemas bilingües)
           ─► Parser (PLY yacc LALR(1): 311 prod., 89 NT, 88 T, 787 estados, 20 S/R, 0 R/R)
           ─► AST (ast_nodes.py)
           ─► Módulos (modulos.py: importar, cargadores de disco y de memoria)
           ─► Semántico + tabla de símbolos (semantic.py, symbol_table.py)
           ─► Verificador de tipos (type_checker.py)
           ├─► Intérprete de árbol (interpreter.py)  ← motor de producción
           └─► IR TAC (ir.py) ─► optimizador ─► MaquinaTAC
                              ─► CFG/SSA (cfg.py, ir_ssa.py) [solo visualización]
                              ─► Liveness + linear scan ─► ISA de pila ─► MaquinaObjetivo
```
- `core/compiler.py:41` define `FASES=("lexer","parser","modulos","semantico","tipos")`. Dentro de una fase los errores se acumulan; entre fases se corta. Tope de 50 errores.
- El IR **no** está en `FASES`: solo lo invocan la CLI (`cli.py:359-498`) y `api.ssa`.

### 2.2 Fortalezas
- Dependencias en un solo sentido y sin ciclos en el núcleo. Fachada única (`analizar_fuente`, `compile_pure`) con contrato `CompileRequest`/`CompileResult`, métricas inyectables y `run_id`.
- `api.py`, con 21 funciones públicas, lo cubre todo.
- `grammar_validator.py` reconstruye la gramática real por reflexión y fija la línea base de conflictos por token.
- 148 códigos de error estables `IL-XXX-NNN`, bilingües.

### 2.3 Debilidades
1. `gui_qt.py` (3852 líneas) es un módulo gigante, y la GUI **vuelve a montar el pipeline a mano 7 veces** (`gui_qt.py:2898,3073,3168,3309,3508,3533,3606`) y 4 veces en `gui_tk.py`, saltándose `modulos`, las métricas y el idioma.
2. Hay cinco motores de ejecución sin una suite diferencial sistemática.
3. `mypy.ini` ignora todo el núcleo.
4. PySide6 es obligatorio; PyInstaller usa `console=True` y UPX.

## 3. Auditoría fase por fase (LF1/LF2)

### 3.1 Léxico (`lexer.py`)
- PLY lex une todas las reglas en un único `re` de Python, que **retrocede: no es un AFD**. La afirmación de `docs/Semana09_Interprete_PLY.md` ("AFD combinado, O(n) garantizado") es falsa.
- Tokens: identificadores ASCII, `ENTERO_LIT`, `REAL_LIT` con exponente, `TEXTO_LIT` con escapes, operadores aritméticos, relacionales, lógicos, de bits y compuestos, `?.` y `??`, y comentarios.
- Las palabras clave se buscan en un diccionario. El bilingüismo funciona como dos lexemas que producen un solo token.
- **Fallos:**
  - a) tras IL-LEX-010 el contador de líneas se desfasa (`:335,:564`);
  - b) `2.e3` deja `e3` suelto como identificador;
  - c) la regex de cadenas depende de `re.VERBOSE`;
  - d) el catálogo IL-LEX de Semana09 §3.4 no coincide con el código;
  - e) `año` produce IL-LEX-005 y una cascada de errores (no admite identificadores Unicode).
- **Ausente para LF1:** Thompson, construcción de subconjuntos, minimización, tablas de transición y diagramas de autómatas.

### 3.2 Sintaxis (`parser.py`)
- LALR(1) real, con `parsetab.py` sincronizado. 20 conflictos S/R, todos resueltos desplazando, y 0 R/R:
  - 13 vienen de las producciones de error;
  - 2 de `main(`;
  - 3 de `++`/`--` posfijos;
  - 3 de else colgante, que solo existe por esas formas de error.
- La tabla `precedence` es vestigial: sin ella siguen saliendo 787 estados y 20/0. `UMINUS` no se usa.
- No hay token `error` ni lista de tokens esperados.
- **Fallos:**
  - programa vacío → error en la posición 0:0;
  - `x = y z = 3;` se reporta en 0:1;
  - `Caja<Caja<entero>>` no se admite;
  - **`imprimir(--5)` imprime 4**;
  - `1+1+…` repetido 3000 veces → `RecursionError` sin capturar.

### 3.3 LL(1) (`ll1.py`)
Descenso recursivo escrito a mano para aritmética. FIRST/FOLLOW aparecen solo en comentarios; **la tabla M prometida no existe**. `verificar_contra_lalr()` pasa 12/12.

### 3.4 Semántico, tabla de símbolos y tipos
- Ámbitos léxicos, sombreado, referencias adelantadas y sobrecarga de métodos. POO completa y genéricos por monomorfización.
- **Huecos:**
  - falsos IL-SEM-050 con un `segun` exhaustivo y con `mientras(verdadero)`;
  - sin aviso de código inalcanzable;
  - `<` no compara cadenas.

### 3.5 IR y back-end
- TAC en cuádruplas. Optimizaciones: plegado local, código inalcanzable, código muerto, mirilla y recursión de cola.
- **Faltan:** eliminación de subexpresiones comunes (CSE), propagación de copias, movimiento de invariantes (LICM), reducción de fuerza y plegado de `if_false`.
- CFG, dominadores y φ de Cytron correctos, pero solo como texto. Liveness y linear scan con k=4. ISA de pila de juguete.

| Motor | pruebas (75) | currículo (133) | Total |
|---|---|---|---|
| Intérprete de árbol | 75/75 | 133/133 | **100 %** |
| TAC / TAC optimizado | 44 + 31 no soportados | 94 + 39 | 66 % |
| Objetivo / con registros | 13 + 62 | 33 + 100 | 22 % |

En lo soportado, 0 salidas distintas.

### 3.6 Ejecución
Límites de 500 en recursión, 10⁶ iteraciones y 5 s; enteros de 32 bits; sandbox de proceso. Las máquinas TAC y objetivo no tienen límites.

## 4. Fallos de corrección verificados

| # | Severidad | Fallo | Ubicación | Reproducción |
|---|---|---|---|---|
| 1 | **Crítica** | No se promueve `entero` a `real` en los parámetros | `interpreter.py:705-707, 735` | `real g(real x){retornar x/2;}`: `g(3)` imprime **1.0** |
| 2 | **Crítica** | La recursión de cola calcula mal con llamadas anidadas | `ir.py:1294-1304` | `retornar f(n-1, g(n,acc))`: árbol 30, TAC optimizado 12 |
| 3 | Alta | Procedimientos recursivos sin IL-EJE-040 | `interpreter.py:728-731` | `p(5000)` → `RecursionError` |
| 4 | Alta | `RecursionError` en el semántico | `semantic.py:2413` | `1+1+…` ×3000 |
| 5 | Alta | Se acepta `--5` | parser/semántico | `imprimir(--5)` → 4 |
| 6 | Media | El TAC diverge del árbol (desbordamiento y variables sin inicializar) | `ir.py:1428-1645` | — |
| 7 | Media | Una global llamada `R0` choca con el registro | `ir.py:2064` | TAC 25 frente a objetivo 21 |
| 8 | Media | Falsos IL-SEM-050; sin aviso de código inalcanzable | `semantic.py:1426` | — |
| 9 | Media | Líneas y posiciones incorrectas (0:0, 0:1) | `lexer.py`, `parser.py` | — |
| 10 | Baja | `--gui-tk` no funcionaba | `main.py:49` | **Corregido en WS-0 (INV-5001)** |

## 5. Cobertura para Lenguajes Formales 1 y 2

| Tema | Estado |
|---|---|
| Regex de tokens y palabras clave bilingües | ✅ |
| Regex→AFN, AFN→AFD, minimización, tablas y diagramas, simulación | ❌ |
| Lema de bombeo, autómata de pila, máquina de Turing | ❌ |
| GLC / EBNF | ⚠️ (`gramatica.ebnf` usa 22 reglas sin definir) |
| FIRST/FOLLOW, estados LALR, conflictos | ✅ |
| Recursión izquierda y factorización automáticas, tabla LL(1) | ❌ |
| Colección canónica, ACTION/GOTO exportable, traza de desplazar/reducir | ⚠️ / ❌ |
| Derivaciones, CST, formas normales, CYK | ❌ |
| Tabla de símbolos, tipos, TAC, optimización, CFG, SSA, liveness, registros | ✅ con huecos |

## 6. Inventario de funcionalidades: uso pedagógico y comercial

| # | Funcionalidad | Entrada | Uso pedagógico | Uso comercial |
|---|---|---|---|---|
| 1 | Lenguaje bilingüe es/en | `.inv` | Intro, Prog 1-2 | Mercado hispano, licencias institucionales |
| 2 | Compilador por fases + API + JSON | `api.*`, `--check --json` | Compiladores | SDK embebible |
| 3 | Tokens, AST, tabla de símbolos | `--tokens --ast --tabla` | LF2 | Material de laboratorio |
| 4 | Validador de gramática LALR | `-m inveniolang.grammar_validator` | LF2 | QA de DSL |
| 5 | Parser LL(1) comparativo | `-m inveniolang.ll1` | LL frente a LR | — |
| 6 | TAC, optimizador y máquina TAC | `--ir --ir-opt --run-ir` | Compiladores | Laboratorios |
| 7 | CFG, dominadores y SSA | `--ssa` | Compiladores avanzados | — |
| 8 | Liveness, linear scan y código objetivo | `--target --target-reg` | Back-end | — |
| 9 | Complejidad O(·) | `--complejidad` | Algoritmos, ED | Diferenciador |
| 10 | Efectos y pureza | `--efectos` | Prog 2 | — |
| 11 | Formateador | `--formatear` | Estilo | Normalización de entregas |
| 12 | Rosetta (Python, C, Java, C#, Pascal) | `--ver-como` | Puente a lenguajes reales | Marketing |
| 13 | Traductor es⇄en | `traducir` | Cursos bilingües | Internacionalización |
| 14 | Errores explicados | web, LSP | Autoestudio | Menos soporte |
| 15 | Sandbox y seguridad de rutas | `--sandbox` | Laboratorio seguro | SaaS de corrección |
| 16 | Trazador visual | `trazar` | Prueba de escritorio, ED | MOOCs |
| 17 | Diagrama de objetos | `trazar --objetos` | POO | — |
| 18 | Flujogramas ISO 5807 en ambos sentidos | `flujo`, `desde-flujo` | Intro, Algoritmos | Sustituto de Raptor/DFD |
| 19 | Bloques en ambos sentidos | `bloques` | Colegio | K-12 |
| 20 | UML de clases en ambos sentidos | `--uml`, `desde-uml` | Prog 2 | Esqueletos desde el diseño |
| 21 | 18 patrones GoF | `pruebas/patron_*.inv` | Ingeniería de software | Contenido |
| 22 | stdlib educativa | `importar` | ED | — |
| 23 | Currículo de 13 niveles × 133 ejercicios × 2 idiomas | runner, web | Curso completo | Licenciable |
| 24 | Autograder | `-m inveniolang.evaluation evaluar` | Evaluación formativa | SaaS / LMS |
| 25 | Detector de plagio | `... plagio` | Integridad académica | Módulo premium |
| 26 | LMS xAPI local | `-m inveniolang.lms` | Analítica docente | Analítica de aprendizaje |
| 27 | IDE Qt con depurador | `invenio-gui` | Laboratorio | Instalable |
| 28 | IDE Tk de respaldo | `--gui-tk` | Equipos limitados | — |
| 29 | Estudio web con Pyodide | `web/estudio` | Autoestudio | SaaS freemium |
| 30 | VS Code + LSP | extensión | Transición profesional | Marketplace |
| 31 | Accesibilidad | — | Inclusión | Licitaciones públicas |
| 32 | Observabilidad | `--metrics` | — | Operación de SaaS |
| 33 | SBOM y verificación del release | `-m inveniolang.sbom` | — | Compras públicas |
| 34 | 408 casos de conformidad | `pruebas/conformidad.py` | Especificación ejecutable | Certificación |

**Modelos de negocio posibles:**
1. Núcleo abierto con licencia institucional para el currículo, el autograder, el plagio y la analítica.
2. SaaS web freemium.
3. Edición "Lenguajes Formales y Compiladores".
4. Formación y certificación docente.
5. LTI 1.3 con Moodle o Canvas.
6. Versión K-12.

El plan para cerrar todo lo anterior está en [PLAN_MAESTRO_v12.md](PLAN_MAESTRO_v12.md).
