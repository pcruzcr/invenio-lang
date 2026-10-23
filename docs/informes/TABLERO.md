# Tablero v12: estado hacia 10/10

> Los criterios de cada dimensión están en el [plan maestro §2](PLAN_MAESTRO_v12.md). Una dimensión solo llega a 10 cuando cumple todos sus criterios.

## Frentes de trabajo

| Frente | Estado | Notas |
|---|---|---|
| WS-0 Release honesto | **Hecho** (salvo protección de rama, segundo mantenedor y macOS en CI) | Hecho: rama `v12/ws0-release-honesto`, 19 módulos legado y 10 carpetas del currículo viejo eliminados, CI nuevo con Python 3.13, `--gui-tk` corregido (INV-5001), informes y registro de riesgos guardados. Falta: protección de rama, segundo mantenedor y matriz de CI en macOS |
| WS-1 Núcleo correcto | **En curso** | Hecho: plagio (INV-5005), promoción de parámetros (5006), recursión de procedimientos (5007), recursión de cola anidada (5008), tiempo global (5009), `config` (5010), intérprete ~1,9× (5011..5014). Falta: `--5`, paridad TAC, `R0`, `_siempre_retorna`/inalcanzable, posiciones del léxico y parser, tokens esperados, topes de memoria, `OverflowError` en `elevar`, suite diferencial y fuzzing |
| WS-2 Seguridad | Pendiente | — |
| WS-3 Rendimiento | Pendiente | — |
| WS-4 Arquitectura | Pendiente | — |
| WS-5 Lenguaje y back-end | Pendiente | — |
| WS-F Lenguajes Formales | Pendiente | — |
| WS-6 Diseño y marca | Pendiente | — |
| WS-7 Qt Premium | Pendiente | — |
| WS-8 Web Premium | Pendiente | — |
| WS-9 Pedagogía | Pendiente | — |
| WS-10 Docencia | Pendiente | — |
| WS-11 Docs, cumplimiento y distribución | Pendiente | Mover `_audit.py` y `test_lexer_errors.py` a `scripts/` y `tests/` quedó aquí (tienen unas 10 referencias en docs y CI) |

## Dimensiones (línea base 2026-10-22 → objetivo 10)

| Dimensión | Base | Actual |
|---|---|---|
| Corrección del compilador | 7 | 7 |
| Completitud del lenguaje y back-end | 6.5 | 6.5 |
| Herramientas LF1 / LF2 | 2 / 5.5 | 2 / 5.5 |
| Seguridad | 6 | 6 |
| Rendimiento | 5 | 5 |
| Arquitectura y mantenibilidad | 7 | 7 |
| Documentación | 4 | 4.5 |
| Diseño gráfico y marca | 5 | 5 |
| UX | 6 | 6 |
| UI | 6.5 | 6.5 |
| Accesibilidad | 6.5 | 6.5 |
| Pedagogía | 7.5 | 7.5 |
| Herramientas docentes | 7 | 7 |
| Privacidad y cumplimiento | 6 | 6.5 |
| Operación y release | 3 | 5 |
| Persona común / colegio | 3.5 / 4.5 | 3.5 / 4.5 |
| Profesor / estudiante universitario | 7 / 6.5 | 7 / 6.5 |
