# PLAN MAESTRO DEFINITIVO: InvenioLang 12 "Premium"

## Contexto

En esta sesión se hicieron 13 auditorías independientes:
- documentación frente a código;
- arquitectura, GUI y CLI;
- cobertura curricular;
- front-end y back-end del compilador;
- inventario de funcionalidades;
- diseño UI/UX/gráfico;
- recorridos por perfil de usuario;
- prueba real del Estudio web;
- matriz normativa;
- pentest;
- rendimiento medido;
- revisión de los 133 ejercicios;
- inspección de accesibilidad de Qt.

También se revisaron los planes que ya existían en el proyecto: `docs/ROADMAP_V11.md`, `docs/RELEASE.md`, `docs/ERRATAS.md`, `docs/AUDITORIA_INGENIERIA_v10.1.md`, `scripts/ci.yml.nuevo` y `scripts/limpiar_obsoletos.py`.

Este plan los unifica todos en **un único programa de trabajo** cuyo objetivo es la **versión 12.0.0 "Premium"**: 10/10 en cada dimensión evaluada y una experiencia que se vea y se sienta como una aplicación AAA+.

**Qué significa "10/10" aquí.** Cada nota se define con **criterios objetivos y medibles** (§2). Una dimensión está en 10 solo cuando todos sus criterios pasan en CI o en una prueba documentada.

Dos límites honestos:
- La certificación ISO de sistemas de gestión (9001, 27001, 42001…) la obtiene una organización, no un repositorio. El objetivo es **alineación completa con evidencia lista para auditoría**.
- La percepción "premium" se valida con usuarios reales: SUS ≥ 85 y NPS ≥ 50.

Los hallazgos detallados que justifican cada tarea están en [CUMPLIMIENTO_NORMATIVO_v11.md](CUMPLIMIENTO_NORMATIVO_v11.md) (antes "Anexo A"), [INFORME_TECNICO_v11.md](INFORME_TECNICO_v11.md) e [INFORME_INTEGRAL_v11.md](INFORME_INTEGRAL_v11.md).

---

## 1. Principios no negociables
1. **Puertas de calidad automáticas.** Ningún cambio entra si rompe: conformidad 408/408, `pytest`, la suite diferencial de motores, el benchmark, axe-core, `verificar_docs.py` o el presupuesto de tamaño web.
2. **Una sola fuente de verdad** para cada cosa:
   - versión: `_version.py`;
   - gramática: PLY → EBNF generado;
   - diseño: `tokens.json`;
   - textos: `i18n/`;
   - cifras de la documentación: generadas desde el código;
   - requisitos: `requisitos.csv`.
3. **Todas las interfaces (CLI, LSP, Qt, Tk, web) consumen solo `api.py`.**
4. **Prueba antes de arreglar.** Cada fallo del Anexo A entra primero como prueba de regresión que falla.
5. **Paridad Qt ↔ web** definida por un contrato de funciones con pruebas.
6. **Sin código falso.** Lo que no funciona se elimina o se implementa; nunca se deja un stub con promesas.
7. **Compatibilidad.** Los cambios incompatibles van marcados `[BREAKING]`, con alias, avisos de deprecación de una versión y guía de migración.

---

## 2. Tablero objetivo: criterios de 10/10

| Dimensión | Hoy | Criterios para 10/10 (todos obligatorios) |
|---|---|---|
| **Corrección del compilador** | 7 | 0 fallos abiertos del Anexo A §4/§12; suite diferencial de 5 motores con 0 divergencias; fuzzing gramatical de 10 000 programas sin excepciones de Python; conformidad 408/408 + casos nuevos |
| **Completitud del lenguaje y back-end** | 6.5 | TAC 100 % y código objetivo ≥ 95 % de los programas (POO, closures, arreglos, `leer`, `try`); excepciones completas, `registro`, `protegido`, colecciones genéricas, funciones de cadena; CSE, LICM, copias, reducción de fuerza; SSA real con SCCP; coloreo de grafos |
| **Herramientas LF1/LF2** | 2 / 5.5 | Paquete `formales/` completo (§4, WS-F) con prácticas autocorregibles y validación contra casos de libro |
| **Seguridad** | 6 | 0 hallazgos Altos o Medios del pentest; OWASP ASVS L1 completo para la web; SSDF completo; firma y SLSA L2; `pip-audit`/CodeQL/Bandit en verde; política CVD |
| **Rendimiento** | 5 | Intérprete ≥ 5× más rápido (ciclo de 10⁶ ≤ 25 s → objetivo ≤ 15 s); compilación lineal (20k líneas ≤ 4 s); arranque CLI ≤ 0,5 s; GUI ≤ 1,5 s; corrección de 10 casos ≤ 2 s; Estudio web interactivo ≤ 3 s con caché (≤ 8 s en frío, con progreso); Lighthouse ≥ 95 |
| **Arquitectura y mantenibilidad** | 7 | Ningún módulo > 800 líneas; mypy `strict` en el núcleo; GUIs solo vía `api.py`; ADR 001–008; vistas ISO 42010; cobertura ≥ 90 % (núcleo ≥ 95 %); 0 código muerto (vulture) |
| **Documentación** | 4 | `verificar_docs.py` en verde (0 contradicciones); especificación en Markdown fuente con sitio Sphinx/MkDocs publicado; documentación en ES y EN; guías por perfil; `ARQUITECTURA.md`; changelog generado |
| **Diseño gráfico y marca** | 5 | Identidad (logotipo, isotipo, paleta, tipografías) en `docs/marca/`; `tokens.json` único aplicado a Qt, web, SVG y bloques; set de iconos propio; icono de app en todas las plataformas; 0 cadenas de versión antiguas |
| **UX** | 6 | SUS ≥ 85 con 5 usuarios por perfil; de la URL al "Hola mundo" en ≤ 60 s sin instalar; consola interactiva para `leer`; tour; celebración; 0 errores con posición 0:0; "¿quisiste decir?" en el 100 % de los identificadores desconocidos |
| **UI** | 6.5 | Biblioteca de componentes documentada con equivalentes Qt y web; menús reorganizados; dock "Visualizar"; atajos unificados; responsive de 320 px a 4K sin desbordes |
| **Accesibilidad** | 6.5 | WCAG 2.2 AA completo (AAA en contraste de texto) en Qt y web; axe-core sin violaciones; recorrido NVDA, VoiceOver y Orca; VPAT/ACR publicado; alto contraste seleccionable; zoom 50–300 % |
| **Pedagogía** | 7.5 | Los 133 enunciados con datos y formato de salida; salidas en el idioma del ejercicio; ≥ 3 casos (1 oculto) por ejercicio; Bloom con ≥ 30 % en Analizar/Evaluar/Crear; niveles 14 (técnicas algorítmicas), 15 (autómatas) y 16 (gramáticas); prueba de escritorio; quizzes; guías de 16 semanas para 8 cursos |
| **Herramientas docentes** | 7 | Evaluación por carpeta con CSV y diff; sandbox seguro (F9); plagio correcto (prueba de similitud ≥ 0,95) y escalable (MinHash); panel por alumno; exportar casos desde el currículo; LTI 1.3 / Moodle |
| **Privacidad y cumplimiento** | 6 | Matriz normativa (Anexo A §1–§9) con todos los aplicables en ✅: Ley 8968, Ley 10238, GDPR, FERPA, COPPA, WCAG/508/EAA, PI (avisos de terceros, LGPL); registro de riesgos ISO 31000; requisitos trazables |
| **Operación y release** | 3 | v12 en git con etiqueta firmada; CI en 3 SO × 4 versiones de Python; PyPI + `.exe`/`.msi`/`.dmg`/AppImage firmados; Estudio web en GitHub Pages con PWA; extensión publicada en VS Code Marketplace y Open VSX; SBOM CycloneDX en cada release |
| **Persona común / colegio** | 3.5 / 4.5 | Web pública sin instalar; "ñ", tildes, `principal`, `vacío`, `lógico` aceptados; modo Colegio; mensajes sin jerga ni tipos en inglés; prueba de usabilidad con estudiantes de 14–16 años con SUS ≥ 80 |
| **Profesor / estudiante universitario** | 7 / 6.5 | Plantillas sin solución; `runner --probar`; guías por curso con rúbricas y diapositivas; depurador en la web; autocompletado |

---

## 3. Organización: 12 frentes de trabajo (WS) en 5 olas

```
Ola 0 (semana 1)       WS-0 Release honesto
Ola 1 (semanas 2-4)    WS-1 Núcleo correcto · WS-2 Seguridad · WS-3 Rendimiento        (paralelos)
Ola 2 (semanas 5-9)    WS-4 Arquitectura · WS-5 Lenguaje y back-end · WS-F Formales     (paralelos)
Ola 3 (semanas 8-13)   WS-6 Diseño y marca · WS-7 Qt Premium · WS-8 Web Premium         (paralelos; 6 antes que 7 y 8)
Ola 4 (semanas 10-16)  WS-9 Pedagogía · WS-10 Docencia · WS-11 Docs, cumplimiento y distribución
Cierre (semanas 17-18) Validación con usuarios, auditoría final y release 12.0.0
```
Duración estimada: **unas 18 semanas** para una persona a tiempo completo, o de 8 a 10 semanas con trabajo paralelo en sesiones o worktrees separados por frente. Cada frente toca archivos distintos.

---

## 4. Frentes de trabajo y tareas

### WS-0: Release honesto (Ola 0)
- Commitear toda la v11. Ejecutar `scripts/limpiar_obsoletos.py --aplicar`, que elimina 19 módulos legado/falsos, entre ellos `analytics/predict.py` (riesgo AI Act), `tutor_llm.py`, `certification.py`, `backend/`, `ir_poo.py`, `uml.py`, `flowchart*.py` y `parser.out`. Además, eliminar `curriculum/nivel1..10` y `web/pyodide.html`.
- Limpiar la raíz: `build/ dist/ __pycache__ *.tmp`; `_audit.py` y `test_lexer_errors.py` pasan a `scripts/` y `tests/`; ampliar `.gitignore`.
- Instalar `scripts/ci.yml.nuevo` y añadir la matriz Windows/Linux/macOS × Python 3.10–3.13.
- Arreglar `main.py:49` (`--gui-tk`). Hacer que `main.py` delegue en `cli.build_argparser`.
- Guardar los informes en `docs/informes/`: README, INFORME_TECNICO, INFORME_INTEGRAL y CUMPLIMIENTO_NORMATIVO, más este plan.
- Crear `docs/riesgos.md` (ISO 31000), protección de rama y un segundo mantenedor.

**Hecho cuando:** `git status` está limpio, el CI nuevo pasa en verde y un clon limpio arranca.

### WS-1: Núcleo 100 % correcto (Ola 1)
Corregir con prueba de regresión:
1. Promoción `entero`→`real` en parámetros (`interpreter.py:705-707,735`).
2. Recursión de cola con llamadas anidadas (`ir.py:1294-1304`).
3. Límite de recursión en procedimientos (`interpreter.py:728`).
4. Captura de `RecursionError`/`MemoryError` en `core/compiler.py`, la API, el LSP y los importadores JSON, más una profundidad máxima en el parser.
5. `++`/`--` sobre literales.
6. Paridad del TAC: 32 bits, variables no inicializadas, límites.
7. Colisión con el registro `R0` (`ir.py:2064`).
8. `_siempre_retorna` con `segun`, `mientras(verdadero)` e `intentar`, más aviso de código inalcanzable (`semantic.py:1426`).
9. Léxico: líneas tras IL-LEX-010 y caso `2.e3` (`lexer.py:335,564`).
10. Parser: posiciones 0:0/0:1, programa vacío, lista de tokens esperados en `p_error`, genéricos anidados.
11. **Regex del plagio** (`plagiarism/cluster.py:22`).
12. `api.ejecutar(config=…)` debe llegar al intérprete.
13. `OverflowError` en `elevar` (`builtins.py:219`).
14. Contador global de pasos (F4) y límites de memoria y salida (F5): `max_string_len`, tope de salida, presupuesto de elementos.

Nuevos:
- `tests/test_motores_diferencial.py` (5 motores sobre `pruebas/`, currículo y casos borde).
- `tests/test_fuzz_gramatical.py` (programas generados desde la gramática).
- `tests/test_limites.py` (sondas del pentest).

**Hecho cuando:** se cumplen los criterios de "Corrección" del §2.

### WS-2: Seguridad (Ola 1)
- F9: evaluación en un `TemporaryDirectory` con entorno mínimo (`sandbox.py:220,226`).
- F2: `raiz_archivos` + `realpath` + `commonpath` en los builtins y `modulos.py`.
- F7: lectura con tope de la salida del sandbox.
- F1: `os.path.isreserved` y nombres de dispositivo ampliados (`security.py:60`).
- F11: ReDoS de PlantUML.
- F14: LSP robusto.
- F10: escape de Mermaid.
- `ActiveProcessLimit` en el Job Object.
- La GUI Qt ejecuta en un subproceso (`ResourceSandbox`), no en un `QThread`.
- `[BREAKING]` (del ROADMAP v11 §3): sandbox por defecto para código no confiable en CLI y GUI, con opción `--sin-sandbox`.
- Estudio web: CSP, Pyodide autoalojado con integridad (manifiesto SHA-256) y cabeceras seguras.
- DevSecOps: `pip-audit`, CodeQL, Bandit, Dependabot, lockfile con `--hash` que incluya PySide6, releases firmados con Sigstore y procedencia SLSA L2.
- `SECURITY.md` al estándar de GitHub con versiones soportadas, CVD y advisories.
- Revisión OWASP ASVS L1 documentada en `docs/seguridad/asvs.md`.

**Hecho cuando:** volver a ejecutar las sondas del pentest da diagnósticos IL dentro de los límites y no quedan hallazgos Altos ni Medios.

### WS-3: Rendimiento (Ola 1)
Optimizaciones medidas en el Anexo A §11:
1. `_calc_col` con `bisect` sobre los inicios de línea (análisis lineal).
2. Quitar `ABC` de `Visitable` y despachar por diccionario en `_evaluar_expresion`, `_ejecutar_elemento` y `_aplicar_binario`.
3. Resolver slots de variables en el semántico; no crear `Marco` vacíos; búsqueda de ámbito en una sola pasada; retorno sin excepción.
4. Lexer/parser únicos (`clone()`), `write_tables=False`, sin doble tokenización.
5. `parsetab.py` incluido en el zip web.
6. Sandbox con todos los casos en un solo hijo y sin compilación duplicada.
7. Plagio con huellas hasheadas y MinHash/LSH para N ≥ 400.
8. Importaciones diferidas (`__init__`, `api`, `config`, `uml.objetos`).
9. Trazas incrementales y SVG perezoso.
10. Liberar `Analisis.tokens`.
11. Subir el límite por defecto a 10 s solo si el benchmark lo justifica.

`tests/bench/` con `pytest-benchmark` y umbrales en CI.

**Hecho cuando:** se cumplen los criterios de "Rendimiento" del §2.

### WS-4: Arquitectura (Ola 2)
- Reorganizar el paquete por capas: `nucleo/`, `ejecucion/`, `backend/`, `formales/`, `herramientas/`, `docencia/`, `interfaces/`, `diseno/`. Mantener módulos de compatibilidad que reexportan con aviso de deprecación.
- Dividir `gui_qt.py` (≤ 800 líneas por módulo: editor, resaltador, depurador, paneles, ventana, controladores), `semantic.py` e `interpreter.py` (visitantes por familia de nodos).
- Hacer que GUI Qt y Tk usen solo `api.py`, eliminando las 7 + 4 reconstrucciones del pipeline.
- Integrar el IR como fase opcional en `FASES`.
- `[BREAKING]` (del ROADMAP v11 §4): API v12 con errores como objetos `{codigo, linea, columna, mensaje, explicacion, sugerencia}` y adaptador hacia la tupla antigua.
- mypy `strict` progresivo hasta cubrir todo el núcleo; unificar ruff, black y coverage en `pyproject.toml`; vulture en CI.
- PySide6 como extra `[gui]`; scripts `inveniolang-lsp` e `invenio-gui`.
- ADR 002–008: Pyodide, léxico bilingüe, sandbox, i18n, contratos JSON, tokens de diseño y API v12. Vistas ISO 42010 en `docs/ARQUITECTURA.md`.

### WS-5: Lenguaje y back-end (Ola 2)
- **Lenguaje:**
  - `lanzar`/`throw`, `finalmente`/`finally`, clases de excepción de usuario y jerarquía basada en `Excepcion`;
  - `registro`/`record`;
  - `protegido`/`protected`;
  - genéricos multiparámetro con herencia, y genéricos anidados (`>>` en contexto de tipo);
  - colecciones integradas `Lista<T>`, `Mapa<K,V>`, `Conjunto<T>` con `para_cada`;
  - cadenas: `dividir`, `unir`, `codigo_caracter`, `caracter_de_codigo`, `formatear`; comparación `<` entre cadenas;
  - archivos: lectura por líneas y CSV simple;
  - **alias de palabras clave con tilde** (`vacío`, `lógico`) y `principal` como alias de `main`;
  - **identificadores Unicode**;
  - `imprimir` con salto de línea y `escribir` sin salto, `[BREAKING]` con aviso y migración automática en `traducir`.
  
  Cada adición debe actualizar lexer, parser, semántico, tipos, intérprete, IR, Rosetta, traductor, conformidad, `ERRATAS.md`/especificación y currículo en es y en.
- **Back-end:**
  - IR para POO (vtables), closures (conversión de closures) y funciones como valores;
  - arreglos, `leer` y `try` en el código objetivo;
  - CSE (numeración de valores), propagación de copias, LICM, reducción de fuerza y plegado de `if_false`, cada uno con su flag `--opt=`;
  - SSA como estructura, destrucción de SSA y SCCP;
  - coloreo de grafos Chaitin-Briggs junto a linear scan, con comparación;
  - límites en las máquinas TAC y objetivo;
  - completar B-tree con borrado y Trie UTF-8 (ROADMAP v11 §6).

### WS-F: Laboratorio de Lenguajes Formales 1 y 2 (Ola 2)
Nuevo paquete `inveniolang/formales/` (reutiliza `grammar_validator.validar_gramatica()` y el patrón de `ll1.verificar_contra_lalr()`):
- **LF1:**
  - parser de regex, Thompson (regex→AFN-ε), subconjuntos (AFN→AFD), minimización (Hopcroft y Moore) y simulación paso a paso;
  - operaciones de cierre y equivalencia;
  - lema de bombeo interactivo, autómata de pila y máquina de Turing;
  - exportación DOT/SVG/Mermaid y tablas;
  - **AFD de los tokens reales** y un lexer por tabla verificado contra PLY sobre todos los `.inv`.
- **LF2:**
  - modelo de gramática (desde texto o desde PLY), FIRST/FOLLOW;
  - eliminación de recursión izquierda y factorización automáticas;
  - **tabla LL(1)** con conflictos y parser predictivo con pila y traza (reemplaza la tabla prometida en `ll1.py`);
  - ítems LR(0)/SLR/LALR(1)/LR(1), colección canónica, ACTION/GOTO exportable a CSV/HTML;
  - **traza desplazar/reducir del parser real**;
  - derivaciones izquierda y derecha, **CST** junto al AST;
  - formas normales de Chomsky y Greibach, CYK;
  - explicación de los 20 conflictos.
- `docs/gramatica.ebnf` **generado** desde PLY y verificado en CI. Eliminar la tabla `precedence` vestigial o documentarla. Corregir `Semana09` (afirmación de AFD, catálogo IL-LEX, `UMINUS`).
- CLI `inveniolang formales {regex,afn,afd,minimizar,ll1,lr,traza,derivar,cyk,ap,mt}`, API y paneles en Qt y web.

### WS-6: Diseño y marca (Ola 3, primero)
- Identidad: logotipo, isotipo e icono de aplicación (`.ico`, `.icns`, PNG, favicon, maskable PWA); paleta primaria y semántica; tipografías libres (Inter o Atkinson Hyperlegible para la interfaz, JetBrains Mono para el código); voz y tono (tú, cercano, sin jerga); guía de marca en `docs/marca/`.
- **`inveniolang/diseno/tokens.json`** con color (claro, oscuro, alto contraste, daltonismo), tipografía (escala de 6 pasos), espaciado (escala de 4 px), radios, sombras y movimiento. Un generador produce `gui/theme.py`, las variables CSS, las paletas SVG (flujo, trazas, UML) y el lienzo de bloques. Un solo fondo oscuro y un solo color de palabra clave en todas las superficies.
- Set de iconos propio (base Lucide o Phosphor, licencia libre) para Qt y web.
- Biblioteca de componentes documentada (botón, pestaña, tarjeta de error, tarjeta de ejercicio, chip de nivel, anillo de progreso, árbol de variables, toast, diálogo) con capturas Qt y web.
- Ilustraciones y mascota opcional para el modo Colegio, celebraciones con `prefers-reduced-motion`.
- La versión del título y del "Acerca de" sale de `__version__`. El "Acerca de" pasa a ser de producto, con créditos académicos en una sección aparte.

### WS-7: IDE Qt Premium (Ola 3)
- **Primera experiencia:** pantalla de bienvenida (Nuevo, Abrir, Ejemplos, Currículo, Continuar), selector de perfil (Colegio, Universitario, Compiladores) que muestra u oculta herramientas, y tour.
- **Menús:**
  - Archivo, **Editar** (deshacer, rehacer, cortar, copiar, pegar, comentar, duplicar línea, buscar y reemplazar), Ver (zoom Ctrl+= y Ctrl+−, temas incluido alto contraste, idioma), Ejecutar (Ejecutar, Depurar, Paso, Detener), **Compilador (avanzado)** (Tokens, AST, TAC, SSA, objetivo, Formales), Docencia, Ayuda;
  - **atajos unificados con la web:** F5 o Ctrl+Enter ejecutar, F9 breakpoint, F10 paso por encima, F11 entrar, Shift+F11 salir.
- **Editor:** autocompletado con firma, cierre y emparejado de llaves, plegado, lente de errores en línea, quick-fix desde `error_explainer`, minimapa accesible, autoguardado y detección de cambios externos.
- **Depurador:** paso por encima, entrar y salir; ejecutar hasta el cursor; breakpoints condicionales; **árbol de variables** expandible con resaltado de cambios; expresiones vigiladas; pila de llamadas; **prueba de escritorio** tabular.
- **Paneles:** dock único "Visualizar" (Flujo, UML, Bloques, Trazas, Objetos); **consola interactiva para `leer`** (se elimina "Entrada (simulada)"); tarjetas de error enriquecidas.
- **Calidad:** i18n completa (es/en); tuteo; nombres accesibles en el 100 % de los controles (incluido `CodeEditor`); foco de teclado en todo; fuente de interfaz escalable; alto contraste seleccionable; pruebas con NVDA y Orca.
- **Instaladores:** `.msi` y `.exe` firmados (sin consola, sin UPX, en modo directorio por la LGPL), `.dmg` firmado y notarizado, AppImage/Flatpak, actualizaciones automáticas opcionales.

### WS-8: Estudio web Premium (Ola 3)
- **PWA:** manifiesto y Service Worker con caché de Pyodide y del paquete; funciona sin conexión; instalable; progreso de carga por etapas con bytes.
- Editor **CodeMirror 6** (accesible) con resaltado propio, autocompletado, firma, cierre y emparejado de llaves, plegado, gutter de errores, quick-fix y "¿quisiste decir?".
- **Paridad con Qt** (contrato de funciones): depurador paso a paso con árbol de variables, prueba de escritorio, consola interactiva para `leer` (SharedArrayBuffer con COOP/COEP, o re-ejecución), editor visual de flujo y UML, perfiles.
- **Experiencia:**
  - plantilla "Hola mundo" y tour de 3 pasos;
  - idioma inicial preguntado o deducido con selector visible;
  - mapa de progreso del currículo como camino de niveles;
  - celebración y "Siguiente ejercicio";
  - logros;
  - compartir por URL (código comprimido en el fragmento, sin servidor);
  - modo examen y modo práctica.
- **Responsive real:** barra de acciones inferior en móvil, encabezado colapsable, paneles como hoja inferior, sin desbordes de 320 px a 4K.
- **Código:** dividir `app.js` en controladores; CSS por capas y componentes generado desde tokens; carga diferida del currículo del otro idioma; axe-core, Playwright y regresión visual en CI; Lighthouse ≥ 95.
- **Publicación** en GitHub Pages (dominio propio opcional), con CSP y cabeceras.

### WS-9: Pedagogía y contenidos (Ola 4)
- Reescribir los **unos 45 enunciados** con datos y bloque "Ejemplo de salida", y documentar la semilla de los pseudoaleatorios.
- `.expected.es` y `.expected.en` (adiós a `survivor =` y `says woof` en ejercicios en español).
- **≥ 3 casos por ejercicio** (uno oculto) en formato `casos.json`; plantillas `NN_nombre.plantilla.inv`; soluciones en `soluciones/` (solo docentes, o reveladas tras confirmación).
- Reordenar N02-E13, N03-E03, N03-E12 y N09-E07; quitar duplicados o convertirlos en variantes; añadir un ejercicio previo de rotaciones AVL.
- Promover desde `pruebas/`: kmp, mochila, n_reinas, kruskal, prim, floyd, heapsort, trie, deque, conjunto, archivo_io y 12 patrones.
- **Niveles nuevos:**
  - N14 Técnicas algorítmicas: recurrencias, divide y vencerás, voraz, backtracking, PD (mochila, LCS, edición), invariantes;
  - N15 Autómatas (con WS-F);
  - N16 Gramáticas y parsing (con WS-F);
  - además: registros, archivos, excepciones y pruebas unitarias en Programación 1; UML → código, excepciones propias, iterador, State, Composite, SOLID y proyecto en Programación 2; deque, Union-Find y caché LRU en Estructuras de Datos.
- **Tipos de actividad nuevos:**
  - depuración ("detecta el error");
  - predicción de salida;
  - Parsons;
  - escribir pruebas;
  - diseño abierto con rúbrica;
  - quizzes por nivel.
  
  Objetivo Bloom: ≥ 30 % en Analizar, Evaluar y Crear.
- `runner.py --probar ID mi.inv` con diff y siguiente pista; `--exportar-casos`.
- Mensajes pedagógicos: "¿quisiste decir?" (Levenshtein sobre palabras clave, builtins e identificadores); casos especiales (`=` frente a `==`, `x = leer()`, `"txt" + n`, código fuera de `main`, llave sin cerrar indicando su apertura); tipos en el idioma activo; explicaciones completas para los 30 códigos más frecuentes (sin "Así falla"/"Así funciona" vacíos); "Carácter" con tilde.
- **Modo Colegio:** palabras clave reducidas, sin POO al inicio, bloques primero y mensajes sin jerga.

### WS-10: Herramientas docentes (Ola 4)
- `inveniolang evaluar` (subcomando): carpeta completa, CSV y JSON de notas, diff por caso, pesos por caso, rutas absolutas, logs silenciosos salvo `-v`.
- Plagio: resultado como **indicio con revisión humana** (IEEE 7003), informe HTML lado a lado y MinHash.
- LMS: tabla por alumno y por tarea, seudonimización por defecto, cifrado opcional, **borrado y exportación por estudiante** (derechos ARCO / GDPR), retención automática, guardar solo códigos (sin texto libre).
- LTI 1.3 (Moodle, Canvas) y exportación de preguntas en Moodle XML.
- **Guías por curso** (Colegio, Intro, Algoritmos, Prog 1, Prog 2, ED, LF1, LF2, Compiladores): resultados de aprendizaje, plan de 16 semanas con ejercicios por ID, rúbricas, diapositivas y exámenes de ejemplo. `manual_docente.md` pasa a ser un sitio de guías.

### WS-11: Documentación, cumplimiento y distribución (Ola 4)
- **`scripts/verificar_docs.py`** en CI: palabras clave, builtins, producciones, estados, conflictos, número de pruebas, versión y lista de módulos, extraídos del código y comparados con README, CHANGELOG y docs.
- Corregir todo lo listado en el Anexo A §B: versiones, conteos, `funcion` activa, PATRONES_DISENO, Rosetta con 5 lenguajes, ACCESSIBILITY, ROADMAP, Semana09, QUICKSTART, SECURITY con Docker y `ply`, `docs/index.md`.
- README nuevo: arriba "Empieza en 3 pasos" (web, instalador, pip); capturas y GIF; la historia de etapas pasa a `docs/historia.md`.
- Especificación de 19 `.docx` convertida a Markdown fuente (los DOCX y PDF se generan) con las erratas E-xx integradas. Sitio de documentación (MkDocs Material o Sphinx) bilingüe y publicado.
- `docs/requisitos.csv` (INV-ID, sección de la especificación, módulo, prueba) verificado por `_audit.py` reescrito sobre `api.py`. `docs/ARQUITECTURA.md` con "tu primer cambio". CONTRIBUTING con preparación del entorno (Python, web, extensión), flujo de PR y good-first-issues.
- **Cumplimiento** (Anexo A §3–§7):
  - `THIRD_PARTY_NOTICES.md` (PLY BSD, Qt LGPL v3, Pyodide MPL-2.0…);
  - titularidad unificada;
  - licencia de contenidos (CC BY 4.0);
  - aviso de privacidad del Estudio web;
  - plantillas de consentimiento, registro de tratamiento y EIPD (Ley 8968 / Decreto 37554-JP / GDPR);
  - guía para menores (Ley 10238 / COPPA);
  - VPAT/ACR y declaración de accesibilidad (Ley 7600, Ley 9049, Section 508, EAA);
  - plan SQA y plan de pruebas (IEEE 730 / 29119-3);
  - política de uso aceptable para laboratorios.
- **Distribución:**
  - PyPI (`pip install inveniolang`);
  - GitHub Releases con instaladores firmados y SBOM CycloneDX;
  - VS Code Marketplace y Open VSX (extensión 1.0 con LSP completo: definición, referencias, renombrar, símbolos, formateo, acciones de código, firma, tokens semánticos);
  - imagen Docker oficial;
  - changelog generado (Conventional Commits).
- **REPL y CLI premium:** subcomandos (`run`, `check`, `fmt`, `trazar`, `flujo`, `uml`, `formales`, `evaluar`, `plagio`, `lms`, `repl`, `ejercicio`); diagnósticos con fragmento de código, caret, color y `NO_COLOR`; códigos de salida documentados (0/1/2/3/4); `--json` en todos los modos; `--explicar CODIGO`.

### Cierre (semanas 17–18)
- Pruebas de usabilidad: 5 usuarios por perfil (colegio, universitario, docente, persona común). Se itera hasta lograr SUS ≥ 85 (colegio ≥ 80).
- Auditoría final: se vuelven a ejecutar las 13 auditorías del Anexo A; el tablero del §2 debe quedar todo en 10. Se publica `docs/informes/AUDITORIA_v12.md`.
- Release 12.0.0 según `docs/RELEASE.md` actualizado: etiqueta firmada, artefactos firmados, SBOM, notas de versión, sitio, PWA, Marketplace y PyPI.

---

## 5. Puertas de CI (todas bloqueantes en v12)
`ruff` · `black` · `mypy --strict` (núcleo) · `vulture` · `pytest` con cobertura ≥ 90 % · conformidad · currículo es+en · suite diferencial de motores · fuzzing (muestra) · `grammar_validator` · EBNF generado sin diferencias · `verificar_docs.py` · benchmarks con umbral · `pip-audit` · CodeQL · Bandit · SBOM · `npm test` del Estudio y la extensión · Playwright + axe-core + regresión visual · Lighthouse ≥ 95 · presupuesto de tamaño web · `empaquetar_web.py --comprobar` · contraste de `tokens.json` (AA/AAA) · matriz 3 SO × Python 3.10–3.13.

## 6. Riesgos y mitigación
| Riesgo | Mitigación |
|---|---|
| Cambios `[BREAKING]` (`imprimir`, API v12, sandbox por defecto) rompen material existente | Alias + avisos durante una versión + migración automática con `traducir` + guía |
| Alcance enorme para una persona | Olas paralelas en worktrees por frente; prioridad estricta Ola 0 → 1; cada frente se puede publicar por separado (12.0 → 12.x) |
| Rendimiento de Pyodide | Caché de la PWA, `parsetab` incluido, Pyodide autoalojado |
| Regresiones semánticas al optimizar | La suite diferencial y la conformidad son puertas obligatorias |
| Licencia LGPL de Qt | Distribución en modo directorio, avisos y enlace al código de PySide6 |
| Perder el trabajo (un solo autor) | Remoto con respaldo y protección de rama desde la Ola 0 |

## 7. Orden de ejecución inmediato (al aprobar)
1. WS-0 completo (incluye guardar todos los informes en `docs/informes/`).
2. Abrir WS-1, WS-2 y WS-3 en paralelo, en sesiones o worktrees separados por frente, empezando por los fallos críticos: promoción entero→real, recursión de cola, regex del plagio, contador global de pasos, F9 y F5.
3. Seguir ola por ola con revisión al cierre de cada una, actualizando el tablero del §2 en `docs/informes/TABLERO.md`.

## 8. Verificación global
- Tablero del §2: cada criterio enlaza a su job de CI o a su acta de prueba. Se considera 10/10 solo con todos en verde.
- Repetición de las sondas del pentest, del benchmark, de la revisión de los 133 ejercicios y de la inspección de accesibilidad de Qt (con los mismos scripts de esta auditoría) y comparación antes y después.
- Clon limpio → `pip install inveniolang` → `inveniolang --version` = 12.0.0; el `.msi` firmado abre la bienvenida; la URL pública del Estudio lleva al "Hola mundo" en ≤ 60 s.

