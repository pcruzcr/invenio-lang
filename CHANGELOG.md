# Changelog — InvenioLang

Todas las mejoras notables de la auditoría profesional.

## [11.0.0] - 2026-10-03 — Lenguaje educativo completo: núcleo bilingüe, visualización, diagramas, bloques y web

Resumen de las cuatro fases de la versión 11 (detalle por fase debajo).

### Fase 4: estudio visual y cierre

#### Añadido
- **Editor de bloques (INV-4000..INV-4012).** `inveniolang/bloques/`: bloques estilo
  Scratch/Blockly sobre el mismo árbol que el diagrama de flujo (mismos ids); contrato JSON v1
  y catálogo publicable; código ⇄ bloques en es/en probado sobre los 266 ejercicios del
  currículo; encaje tipado con las reglas del verificador de tipos y motivo bilingüe; edición
  pura; paleta accesible (color + icono + forma, contraste AAA). Panel «Bloques» en Qt con
  arrastrar y soltar real, papelera, zoom, deshacer/rehacer, uso completo por teclado con
  anuncios al lector de pantalla y sincronía con el editor y el diagrama de flujo. API
  `bloques`/`codigo_desde_bloques`/`catalogo_bloques`; CLI `bloques`/`desde-bloques`.
- **Estudio web (INV-4200..INV-4241).** `web/estudio/`: InvenioLang en el navegador con
  Pyodide dentro de un Web Worker: editor con resaltado es/en, ejecución con entrada y botón
  Detener, errores explicados, bloques, diagrama de flujo, UML, reproductor paso a paso,
  traductor, currículo con comprobación, temas y es/en; WCAG 2.2 AA (AAA en texto).
  `scripts/empaquetar_web.py` determinista. Extensión de VS Code con cliente LSP real,
  gramática es/en generada del lexer y comandos ejecutar/trazar/flujo.
- **Acceso a miembro encadenado** `a.b.c`, `a.b.c = v`, `a.b.m()` (spec POO §14, INV-4406);
  17 casos de conformidad nuevos (408 en total).
- `trazar --objetos N` y botón «Diagrama de objetos» en el Visualizador (INV-4402);
  `--step` muestra archivo:línea y el código (INV-4404).
- `scripts/limpiar_obsoletos.py` y avisos de la puerta de calidad y `_audit.py` sobre
  archivos retirados que queden en una copia vieja (INV-4409, INV-4412).

#### Corregido
- Visualizador: cima de una pila sobre arreglo y sinónimos de "fin" (INV-4400/4401).
- Rosetta: tipos de arreglos/matrices, printf/scanf tipados, división entera, sin salto
  añadido; verificado compilando con gcc/g++/javac (INV-4403).
- Complejidad: memoización y ciclos amortizados (Fibonacci memo y KMP en O(n)); la salida
  explica método y límites (INV-4405).
- Un error de ejecución ya conserva la salida impresa antes del fallo (INV-4202).
- Errata del tipo función en la spec §12.5 (INV-4407); documentación sin enlaces rotos (INV-4411).

#### Cambiado
- Versión 11.0.0 en todos los artefactos (INV-4408); el parser ya no escribe `parser.out`
  dentro del paquete.

#### Eliminado
- `web/pyodide.html`: sustituido por el estudio web.

### Fase 3: diagramas de flujo y UML bidireccionales

### Añadido
- **Diagramas de flujo bidireccionales (INV-3000..INV-3011).** Paquete `inveniolang/flujo/`:
  modelo JSON v1 con ida y vuelta exacta; un diagrama por subrutina, `main`, método y
  constructor; símbolos ISO 5807 y layout sin solapes (saltos con conectores con letra);
  código ⇄ diagrama en es/en, con garantía probada sobre los 266 ejercicios del currículo
  (compila y da la misma salida); SVG accesible (claro/oscuro/auto), Mermaid y texto es/en;
  edición estructurada con validación bilingüe. API `diagrama_flujo`/`codigo_desde_flujo`,
  CLI `flujo` y `desde-flujo`, panel único «Diagrama de flujo» en la GUI Qt.
- **UML de clases bidireccional (INV-3200..INV-3214).** Paquete `inveniolang/uml/`: modelo
  JSON v1; interfaces, abstractas, enumeraciones y tipos suma, genéricos, constructores,
  estáticos y relaciones (herencia, realización, composición, agregación, asociación con
  multiplicidad, dependencia) con criterio documentado; PlantUML, Mermaid, SVG propio y
  texto es/en; lector de un subconjunto de PlantUML; esqueletos que compilan en es/en
  (ida y vuelta probada en los niveles 8–12 y la stdlib); diagrama de objetos desde un
  paso de traza. API `uml` (firma compatible) / `codigo_desde_uml` / `diagrama_objetos`,
  CLI `--uml plantuml|mermaid|svg|json|texto` y `desde-uml`, panel «Diagrama UML».

### Eliminado
- `flowchart.py`, `flowchart_builder.py` y `uml.py`: sustituidos por `flujo/` y `uml/`.

### Fase 2: visualización paso a paso

### Añadido
- **Trazador (INV-2000..INV-2010).** `api.trazar` e `inveniolang trazar archivo.inv
  [--html f] [--json f] [--svg-paso N f] [--texto] [--max-pasos N] [--idioma es|en]`:
  pila de llamadas, montículo con ids estables, celdas y campos leídos/escritos, salida y
  estructuras reconocidas (arreglo, matriz, pila, cola, listas, árbol binario, grafo).
  Contrato JSON v1; coste nulo en la ejecución normal.
- **Vistas (INV-2200..INV-2241).** Descripción accesible es/en por paso, SVG determinista
  (WCAG AAA en texto, resaltados que no dependen sólo del color, árbol Reingold–Tilford,
  grafo circular con pesos), reproductor HTML autónomo con atajos y aria-live, y panel
  «Visualizador» en la GUI Qt.

### Corregido
- Las asignaciones tenían línea 0 en el AST: sus errores decían `:0:0` y el depurador no se
  detenía en ellas (INV-2004).
- Una lista sin contenedor perdía su primer nodo al dibujarse (INV-2007).

### Fase 1: núcleo real, bilingüe y currículo completo

**Lenguaje (INV-1400…1440, INV-1290…1293)**
- Mensajes bilingües es/en desde un catálogo central (`inveniolang/i18n`): todos los diagnósticos IL-XXX-NNN, la ejecución, la CLI y el explicador de errores. Idioma con `--idioma es|en`, `INVENIO_IDIOMA` o `compile_pure(..., idioma=)`.
- `inveniolang traducir archivo.inv --a en|es`: traductor de código por tokens que conserva comentarios, literales y formato (ida y vuelta verificada sobre `pruebas/` y el currículo).
- Módulos: `importar "ruta";` / `import "path";`, con resolución relativa, rutas validadas, detección de ciclos y diagnósticos IL-MOD-001…007; también desde memoria (`api.ejecutar(..., modulos={...})`).
- Biblioteca estándar educativa escrita en InvenioLang, en español e inglés: pila, cola, lista enlazada simple y doble, árbol binario de búsqueda, grafo (BFS, DFS, Dijkstra), vector dinámico, matrices, ordenamientos y búsquedas.
- Atributos arreglo y `nuevo tipo[n]` (IL-TIPO-023); funciones integradas `absoluto_real`/`fabs`, `redondear`/`round`, `longitud_arreglo`/`array_length`, `lanzar_error`/`throw_error` (IL-EJE-060).
- Corregido: `+=` en la actualización de un `para` asignaba en vez de sumar; una declaración en un bloque tapaba la global homónima; alcance dinámico en lugar de léxico; conversión entero→real en `--run-ir`; `--step` se caía con errores de compilación.

**Núcleo (INV-1000…1033)**
- Eliminados 19 módulos fingidos o sin uso (JIT y WASM de demostración, generador de gramática, tutor "LLM", analítica predictiva, studio, transpiler, toolchain pkg/linter, certification, ds_visualizer, visual/trees, tipado gradual, policy, ast_validator, ir_poo, gui/collab, gui/editor).
- Fachada única del pipeline: `core.analizar_fuente`/`compile_pure` + `api`; la CLI, el LSP, el visor y el currículo pasan por ella.
- Análisis reales nuevos: complejidad O(·) (ciclos, ciclos logarítmicos, recursión y teorema maestro), efectos y pureza, CFG + SSA (Cytron) y validación LALR(1) contra el baseline documentado. Flags `--ssa`, `--complejidad`, `--efectos`, `--uml`, `--ver-como`, `--formatear`.
- LSP con protocolo real (`Content-Length`); evaluación y panel docente xAPI (`python -m inveniolang.evaluation`, `python -m inveniolang.lms`); contraste WCAG AA del tema oscuro.
- Guardia de calidad (`tests/test_calidad_paquete.py`): ningún módulo huérfano, ninguna función sin uso, ninguna marca de "demo/stub".

**Currículo (INV-1200…1205)**
- 13 niveles y 133 ejercicios, cada uno con versión de palabras clave en español (`curriculum/es/`) y en inglés (`curriculum/en/`): fundamentos, control, funciones y recursión, arreglos y búsqueda, ordenamiento, matrices, cadenas, POO I y II con patrones de diseño, pilas y colas, listas, árboles (ABB, heap, AVL, hash), grafos (BFS, DFS, Dijkstra, topológico) y complejidad.
- Cada ejercicio con solución comentada, salida exacta, enunciado, objetivos y pistas graduadas en su idioma; `curriculum/runner.py` verifica ambas versiones, muestra enunciados y pistas (`--idioma`) y sale con código ≠ 0 si algo falla.

**Calidad:** 949 pruebas (antes 193), cobertura 87,4 % (antes 56,8 %), ruff 0 en todo el repositorio, flake8/black/mypy en verde, conformidad 391/391.

## [10.0.1] - 2026-10-01 — Auditoría de corrección (sin cambios de API)

**Back end (IR/TAC, código objetivo)** — verificado por paridad intérprete ↔ `--run-ir` ↔ `--run-ir-opt` sobre los 77 programas de `pruebas/`:
- Operadores bit a bit (`& | ^ << >>`) y `~` soportados en MaquinaTAC, plegado y código objetivo (antes: "operación no soportada"; `~x` se traducía a `!x`).
- Temporales identificados por tipo (`ir.Temp`), no por el prefijo "t": la eliminación de código muerto ya no borra globales como `tam`/`total` (`monticulo.inv`, `arbol_b.inv` fallaban con `--run-ir-opt`).
- Matrices: columnas de las matrices globales conservadas entre subrutinas, dimensiones con constante con nombre, parámetros `int [][]` (op `ncols`) y matrices locales; ya no se asume 10 columnas en silencio.
- Declaraciones locales (`ir.Local`) ya no sobrescriben globales homónimas; los temporales de las globales ya no se comparten con las subrutinas (recursión corrompía resultados).
- El plegado de constantes invalida las globales tras un `call`; la recursión de cola asigna parámetros en paralelo (`f(b, a)`).
- Código objetivo: literales inmediatos con `PUSH` (antes `LOAD 1` → None); globales y parámetros fuera de la asignación de registros incorrecta.

**Semántico:** un método sin cuerpo y sin `abstracto` reporta IL-POO-022 en vez de caer con `AttributeError`.

**Seguridad:** `leer/escribir/agregar_archivo` aplican además `security.validar_ruta_relativa` (flujos NTFS `a:b.txt`, `CON.txt`/`NUL.log`, comodines, caracteres de control); el sandbox ejecuta con el directorio del programa como `cwd` (antes escribía en la carpeta del docente).

**Arquitectura:** versión en `inveniolang/_version.py` (antes repetida en 5 módulos); límites de `config.py` como fuente única (security/cli/builtins/intérprete) y `INVE_*` realmente aplicados; `compile_pure` atiende `modo="ast"`, devuelve tokens sin exigir programa válido y rechaza modos desconocidos; `gui.MainWindow` apuntaba a un módulo inexistente; `ir_ssa.to_ssa` ya no muta su entrada; clúster de plagio calcula cada huella una vez.

**Pruebas:** `pytest` recorre `pruebas/` y `tests/` (antes `tests/` quedaba fuera); `_audit.py` ya no se ejecuta al importarse; `tests/test_regresiones_auditoria.py` (39 casos; 34 fallan con el código anterior).

## [10.0.0] - 2026-08-31 — Plataforma de referencia (v4-v10) — viewer-only

**Solo InvenioLang se compila/ejecuta** (`core/compiler.py:1` `compile_pure` + `interpreter.py:149`); el resto es **Rosetta viewer** `viewer/rosetta.py:1` (no `backend/wasm.py` demo) + `docs/rosetta.md:1` para aprender C/C++/Python/Java/C#/Pascal/.NET sin compilar.

**v4 Toolchain:** `toolchain/formatter.py:1` `inveniofmt` idempotente, `toolchain/linter.py:1` `IL-WARN` Strategy, `toolchain/pkg.py:1` `invenio.json`, `invenio test` con 30 casos ocultos firmados.

**v5 Verificación:** `ir_ssa.py:1` `compute_dominators` + `to_ssa` phi, `grammar/generator.py:1` EBNF→parser, `types/gradual.py:1` `dynamic` + `consistent/join`.

**v6 Distribuido:** `gui/collab.py:1` `LWWRegister` CRDT, `docker/Dockerfile:1` `runsc` + `seccomp.json`, `lms.py:27` ya heatmap + `plagiarism/cluster.py:1` escala 1000.

**v7 IA:** `tutor_llm.py:1` `guardrail` Socrático + `complexity.py:1` `O(n log n)` heurística, `effects/__init__.py:1`.

**v8 Lenguaje:** `types/gradual`, `effects`, `grammar/generator` + `docs/tipos.md` 11 juicios.

**v9 Hardware:** `backend/wasm.py:1` `tac_to_wat`/`tac_to_riscv` demo (no pipeline estable), `backend/jit.py:1` `JITHotCounter` threshold 100.

**v10 Plataforma:** `curriculum/` 70 inv (30+40) → 300 pipeline, `plagiarism/cluster` + `analytics/predict.py:1` `risk_score`, `studio/allinone.py:1` `ver_como` (no `transpilado`), bump `10.0.0` en `pyproject.toml:6`/`__init__.py:3`.

## [3.0.0] - 2026-08-31 — Estable para aula (Sprint 0)
- **Arquitectura hexagonal:** `inveniolang/core/__init__.py` `CompileRequest/CompileResult` frozen + `core/compiler.py:1` `compile_pure` puro; `gui_qt.py:52` importa `gui/theme.py` (split real), `cli.py:589` `build_argparser()` argparse puro con `--json` y validación.
- **Formal verificable:** `docs/gramatica.ebnf:1` 63 líneas + `grammar_validator.py:14` FIRST/FOLLOW punto fijo + `validate_lalr1` parsetab introspección + `docs/tipos.md:1` 11 juicios con POO + `cfg.py:52` Switch/Try/For fallthrough + `core` test.
- **Backend estable:** `ir.py:201` `_cols` + `_gen_matrix_decl` row-major `array_new(filas*cols)` + `MatrixAccess` `fila*cols+col` + `MatrixLValue`; `ir_poo.py:1` stub documentado; `cli.py:459` `_generar_ir_o_avisar` ya no falla `--run-ir` matrices en aula.
- **Seguridad:** `sandbox.py:7` `HAS_RESOURCE` guard + `WindowsSandbox` `CREATE_NEW_PROCESS_GROUP` + timeout; `evaluation.py:23` `run_secure` con `use_sandbox` por caso.
- **Producto:** `curriculum/:1` 30 ejercicios (15+15) con runner timeout, `lms.py:27` `plagiarism_score` integrado + `dashboard`, `ds_visualizer.py:70` cableado en `_HiloEjecucion`, `gui_qt.py:171` `MiniMapArea` teclado Up/Down + `AccessibleName`, `complexity.py:16` `O(n log n)` heurística, `certification.py:45` `emitir_pdf`.
- **Calidad:** `pyproject.toml:90` `fail_under=80` bloqueante sin fallback, `ci.yml:30` strict, `docs/conf.py` Sphinx + `docs/index.md`, `docs/PATRONES_DISENO.md` + `SECURITY.md`/`ACCESSIBILITY.md`.
- **Verificación:** `pruebas/conformidad.py` 391/391, `curriculum` 30/30, `grammar_validator: OK`, `core` matriz `('3',)`.

## [2.0.0] - 2026-08-30 — Profesionalización

### Seguridad
- **Builtins file I/O hardening** (`inveniolang/builtins.py`): validación de rutas
  relativas (bloquea `..`, rutas absolutas, extensiones peligrosas `.py/.exe/.dll`),
  límite 2 MiB por archivo, bloqueo de dispositivos reservados Windows (`CON`/`PRN`/...).
  Añadido `.tmp` a extensiones permitidas para `archivo_io.inv`. Código `IL-EST-015/016/017` preservado.
- **CLI `leer_fuente` hardening** (`inveniolang/cli.py`): límite 1 MiB por `.inv`,
  validación de longitud de ruta, manejo `OSError`/`UnicodeDecodeError` centralizado,
  rechazo temprano `IL-LEX-001` sin fuga de excepción cruda.
- **Array/Matriz DoS mitigation** (`inveniolang/semantic.py`, `inveniolang/interpreter.py`):
  dimensión máxima 100k (arreglo), 10k×10k con `filas*cols ≤ 200k` (matriz), errores
  `IL-SEM-071` / `IL-EJE-050` en tiempo de compilación y ejecución.
- **Infraestructura**: nuevo módulo `inveniolang/security.py` + `SECURITY.md` con
  modelo de amenaza, tabla de controles y contacto de reporte.

### Accesibilidad (WCAG 2.1 AA)
- Nuevo módulo `inveniolang/accessibility.py` (paleta alto contraste 7:1, escalado
  9–24 pt, fuente dislexia-friendly, `validar_tema_accesible()`).
- `inveniolang/gui_qt.py`: import de `accessibility`, tema `TEMA_ALTO_CONTRASTE`,
  helpers `describir_widget` (AccessibleName/Description para lectores NVDA/JAWS/Orca),
  tooltips con atajos. Documentado en `ACCESSIBILITY.md`.
- Persistencia de tema y tamaño de fuente en `QSettings`.

### Eficiencia / Corrección
- `inveniolang/lexer.py`: corregido `t_error` — `& | ^ ~ %` ya no se reportan como
  `IL-LEX-002` tras Etapa 11 (ahora son operadores bit a bit válidos); `IL-LEX-002`
  solo para `@#$` `` ` ``.
- `inveniolang/ir.py` (`plegado_constantes`): no pliega división/módulo por cero
  ni `0.0/0.0` → `nan/inf`; preserva `IL-EJE-002/006` en runtime — evita divergencia
  entre TAC optimizado y árbol.
- `inveniolang/interpreter.py`: límites de memoria en ejecución coherentes con
  `semantic.py` (defensa en profundidad).
- `inveniolang/errors.py`: `obtener_reportes_json()` + `resumen()` para integración
  IDE/CI (`--json`).

### Compatibilidad / GUI
- `inveniolang/gui.py` (Tk respaldo): sincronizado con `lexer.keywords` (81 formas,
  38 parejas bilingües + Etapa 11/12), `BUILTINS` ahora dinámico desde
  `builtins.FUNCIONES_BUILT_IN` (60 funciones), título actualizado a 2.0.
- `inveniolang/gui_qt.py`: sincronizado con `accessibility.py`, versión 2.0.

### CLI / Tooling profesional
- `pyproject.toml` (PEP 517/518, `setuptools`, `ruff`, `mypy`, `black`, `pytest`,
  `coverage`, scripts `inveniolang`/`invenio-gui`).
- `.editorconfig`, `.pre-commit-config.yaml` (trailing whitespace, `ruff`, `mypy`).
- `.github/workflows/ci.yml` — matriz 3.10/3.11/3.12, conformidad 391 + lexer 28.
- `requirements.txt` actualizado a 2.0 con nota `[dev]`.
- `main.py` + `cli.py`: `--version` (2.0.0), `--json` (errores en JSON), ayuda
  ampliada con `--ir`/`--target`.
- `Proyecto/README.md` creado (eliminación de "still blank").

### Documentación
- `SECURITY.md`, `ACCESSIBILITY.md`, `CHANGELOG.md` nuevos.
- `README.md` (raíz) sigue declarando 391 casos conformes; `docs/` sin cambios
  normativos (solo erratas ya documentadas en `ERRATAS.md`).

### Verificación
- `python pruebas/conformidad.py` → **391/391 CONFORME**
- `python test_lexer_errors.py` → **28/28 OK**
- `python -c "from inveniolang.security import auditar_seguridad; ..."` → OK
- `python main.py --version` → 2.0.0

## [1.0] - 2026-08-19 — Baseline
- Compilador 1.0 + POO 2.0 + Etapas 6–13 (ver `README.md` v1.0).
