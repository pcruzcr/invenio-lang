# Changelog — InvenioLang

Todas las mejoras notables de la auditoría profesional.

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
