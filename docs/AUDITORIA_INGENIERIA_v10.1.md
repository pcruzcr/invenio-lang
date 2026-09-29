# AUDITORÍA DE INGENIERÍA — InvenioLang 10.x → v10.1
# Fecha: 2026-09-12 · Alcance: código + documentación + seguridad + observabilidad

## 1. Resumen ejecutivo

Auditoría exhaustiva del compilador educativo InvenioLang (60+ módulos,
~15.000 líneas Python + especificación en docs/). El núcleo (lexer → parser
LL(1) → semántico → tipos → intérprete tree-walker) funciona correctamente:
verificado ejecutando `pruebas/arbol_binario.inv`, `archivo_io.inv` y el
pipeline puro (`core.compiler.compile_pure`).

### Fortalezas encontradas (nivel que ya era sólido)
- Arquitectura hexagonal real: `core/` sin IO con contrato congelado
  (`CompileRequest`/`CompileResult`, dataclasses inmutables).
- Catálogo de errores versionado (§15/§18) con formato único
  `[IL-XXX-NNN] archivo:l:c — msg` y Observer para IDE.
- 12 patrones GoF centralizados y pedagógicos en `patterns.py`
  (thread-safe: Singleton con lock, Subject con lock).
- Controles de seguridad razonables ya presentes: límites de tamaño,
  recursion, timeout (IL-EJE-030/040), whitelist de extensiones.

### Hallazgos corregidos en esta auditoría

| # | Severidad | Hallazgo | Corrección |
|---|-----------|----------|------------|
| H1 | **Alta** | `evaluation.run_secure` lanzaba el sandbox y **ignoraba su resultado**, re-ejecutando el código del estudiante sin aislamiento (doble ejecución, ninguna aislada) | El sandbox es ahora la única vía de ejecución cuando `use_sandbox=True` |
| H2 | **Alta** | Observabilidad = 0: ni un solo `import logging` en el proyecto; imposible trazar fases, tiempos o correlacionar ejecuciones | Nuevo `observability.py`: logging JSON estructurado, run-id de correlación, `PipelineMetrics` por fase, decorador `@traced`, `MetricsObserver` (Observer sobre ErrorManager) |
| H3 | Media | `security.validar_ruta_relativa` no bloqueaba rutas UNC (`\\srv\share`), NTFS ADS (`:` extra), trailing dots/spaces (truco Windows), ni wildcards | Los 6 controles añadidos y testeados |
| H4 | Media | `toolchain/pkg.py`: `json.loads` sin manejo (crash con paquete corrupto), escritura no atómica (partial write corrupto), nombre/versión sin validar | Carga robusta, escritura atómica tmp+`os.replace`, validación semver/nombre |
| H5 | Media | `sandbox.py` en Windows: sin límite de memoria ni ventana oculta | Estructuras Job Object (ctypes) listas para límite de memoria + `CREATE_NO_WINDOW` + logging del resultado |
| H6 | Baja | `core/compiler.py` tokenizaba dos veces en modo `tokens` | Se reutiliza la única tokenización |
| H7 | Baja | Sin suite de tests para seguridad/soporte | `tests/test_auditoria.py`: 38 tests, todos en verde |

## 2. Verificación

- Smoke tests CLI: `hola_mundo`, `arbol_binario`, `archivo_io` → OK.
- Pipeline puro con y sin métricas → resultados idénticos (compatibilidad).
- `python -m pytest tests/test_auditoria.py` → 38/38.

## 3. Análisis por dimensión

### 3.1 Trazabilidad y observabilidad (AHORA)
- Cada compilación genera `run_id` correlacionable (`set_current_run`).
- `PipelineMetrics.mide("fase")` registra ms y errores por fase; serializable
  a JSON para CI/dashboards.
- Logging JSON a **stderr** (nunca contamina la salida del compilador, §7).
- `MetricsObserver` cuenta errores/warnings por código sin acoplar el
  compilador (patrón Observer).

### 3.2 Seguridad / cybersecurity (modelo de amenazas: aula compartida)
Modelado: atacante = estudiante con código .inv malicioso. Vectores cubiertos:
- DoS por recursos: tamaño fuente (1 MiB), arrays (100k), recursión (500),
  timeout 5s, límites Unix rlimit + timeout en sandbox.
- Path traversal / acceso: rutas absolutas, `..`, UNC, ADS `:`,
  dispositivos Windows, extensión whitelist, longitud 260.
- Higiene de proceso: `CREATE_NO_WINDOW`/`CREATE_NEW_PROCESS_GROUP`;
  Job Object (memoria) preparado vía ctypes en Windows.
Pendientes recomendadas (roadmap):
- Piped stdin al sandbox por caso de prueba (hoy `evaluation` no pasa entradas).
- Job Object real activo por subprocess (CreateJobObject + AssignProcessToJobObject).
- FIRW: revisar `gui_qt.py` (3000 líneas) para XSS de salidas en QML/HTML si aplica.

### 3.3 UX/UI
- Errores con formato oficial estable → buen feedback al estudiante.
- `sanitizar_salida` trunca salidas gigantes (10k chars) sin perder diagnóstico.
- Recomendado: mapear códigos IL-* a explicaciones pedagógicas (ya existe
  `error_explainer.explicar`) en el CLI por defecto.

### 3.4 Patrones de diseño (documentación en docs/PATRONES_DISENO.md)
- Coherentes y bien aplicados: Facade (cli.CompilerFacade), Strategy
  (formateo errores/sandbox), Observer (ErrorManager), Template Method
  (pipeline), Chain of Responsibility (filtros), Memento (undo/debug).
- Riesgo detectado: SingletonMeta existe pero ErrorManager NO es singleton
  (correcto: instancia por compilación — documentar la decisión para no
  "mejorarla" accidentalmente a singleton global con estado compartido).

### 3.5 Eficiencia
- Pipeline tree-walker O(n) por nodo; sin pasos redundantes tras H6.
- `obtener_reportes` ordena O(k log k) solo al reportar (no en cada error) — OK.
- Winnowing del anti-plagio con sets de k-grams O(n) — OK.

### 3.6 Documentación
- Especificación completa en docs/ (§1-§19 + ERRATAS + PATRONES).
- Añadida esta auditoría como registro de trazabilidad de la versión.

# AUDITORÍA DE INGENIERÍA — InvenioLang 10.x → v10.1/v10.2
# Fecha: 2026-09-12 · Alcance: código + documentación + seguridad + observabilidad + calidad

## 4. V10.2 — Correcciones del roadmap + automatización de calidad

### 5.1 Correcciones funcionales
- **Sandbox con stdin** (`sandbox.ResourceSandbox`): los casos de prueba de
  `evaluation.run_secure` ahora alimentan la entrada por pipe — antes el
  sandbox no recibía entradas y todo programa con `leer()` fallaba.
- **Job Object activo en Windows**: `Popen` + `AssignProcessToJobObject` +
  límite de memoria real (256 MB) + `KILL_ON_JOB_CLOSE` (sin huérfanos) +
  `CREATE_NO_WINDOW`.
- **Bug detectado por mypy**: `Popen(timeout=…)` no existe (solo en
  `communicate`) → TypeError latente corregido.
- **Bug real de pyflakes (F821)**: `Optional` sin importar en
  `builtins.py::BuiltInFactory` (crash de la anotación en cualquier uso).
- **F811**: `plagiarism.cluster` redefinía `plagiarism_score` — eliminado.
- **UX CLI (UDC)**: errores de todas las fases se imprimen ahora con caret:

      [IL-SIN-010] t.inv:1:23 — Se esperaba ";"
          1 | entero x = 2 escribir(x+3);
            |                      ^

- **`--metrics` en CLI**: pipeline puro + JSON con tiempos por fase
  (benchmarking/CI/panel docente).

### 5.2 Automatización de calidad (PEP 8 / PEP 20 / PEP 257)
- `setup.cfg`: flake8 (ignorados documentados, complejidad máx. 25, F401
  permitido en `__init__` re-exportadores) + coverage (branch) + pytest.
- `black` (línea 120) formateó el paquete excluyendo GUI legado y PLY.
- `autoflake`: eliminación automática de imports/variables sin uso.
- `mypy.ini`: gradiente de severidad — estricto en módulos nuevos
  (`observability` sin tipos implícitos), `disable_error_code` para la API
  específica de plataforma de `sandbox.py`, e `ignore_errors` documentado por
  módulo en el legado (cada refactor lo retira y "gradúa" el módulo).
- **CI (.github/workflows/ci.yml)**: flake8, black --check y mypy ahora son
  **bloqueantes** (antes `|| true`); coverage >80% se mantiene.
- `CONTRIBUTING.md`: las 5 reglas de oro + flujo de contribución.
- `SECURITY.md`: actualizado con controles v10.2 y runbook Docker/gVisor.

### 5.3 Resultado verificado (todo en verde)
```
flake8: 0 hallazgos (antes: 1.400)
mypy:   Success (47 archivos)
black:  0 cambios pendientes
pytest: 97 tests OK (incluye regresión golden sobre pruebas/*.inv
        y test de sandbox con stdin)
conformidad: 391/391   ·   lexer: 28/28
```

### 5.4 Lección registrada
La limpieza automatizada (`autoflake --remove-unused-variables` + reemplazo
masivo de `except X as e:`) rompió temporalmente dos manejadores que SÍ
usaban `e` — detectado por el oráculo de regresión (`archivo_io.inv`) y
reparado. Moratoria: en este proyecto se prohíbe `--remove-unused-variables`
sobre `interpreter.py`; los reemplazos globales de patrones de excepción
deben revisar el cuerpo del manejador.

## 5. Reglas de evolución (garantía de calidad continua)
1. Cambio en `CompileRequest`/`CompileResult` ⇒ bump de minor version (contrato).
2. Toda ruta/entrada de usuario pasa por `security.validar_*` (única fuente).
3. Todo subprocess ⇒ `ResourceSandbox` (nunca `subprocess.run` directo).
4. Nueva fase del pipeline ⇒ envolver en `metrics.mide("fase")`.
5. Tests obligatorios: `pytest tests/` en verde antes de merge.
