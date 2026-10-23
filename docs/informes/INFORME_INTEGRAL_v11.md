# InvenioLang 11.0.0 — Análisis integral desde 14 perspectivas

> Fecha: 2026-10-22. Auditoría en solo lectura. Incluye una prueba real del Estudio web en navegador (escritorio y móvil) y recorridos simulados por perfil de usuario. Forma parte de `docs/informes/` (ver [README](README.md)).

## 0. Veredicto global

InvenioLang es un proyecto académico **excepcionalmente ambicioso y en gran parte real**. Su núcleo funciona: 408/408 en conformidad y 208/208 programas en el intérprete. Aun así, **no está listo para ser un producto premium**, por varias razones:
- 10 fallos de corrección;
- la v11 sin commitear (resuelto en WS-0);
- 19 módulos falsos o legados (eliminados en WS-0);
- documentación que contradice al código;
- fricciones graves para principiantes: rechaza la "ñ", no sugiere "¿quisiste decir…?" y hay errores en la posición 0:0;
- no se puede usar sin instalar Python.

| Perspectiva | Nota | Resumen |
|---|---|---|
| Pedagogo | 7.5 | Buen andamiaje (pistas graduadas, visualización); falta evaluación formativa y diseño instruccional explícito |
| Analista de sistemas | 5.5 | Funcionalidad amplia; trazabilidad informal |
| Ingeniero de software | 6.5 | Núcleo probado (3111 pruebas), pero release roto y fallos de corrección |
| Arquitecto de software | 7 | Fachada y capas correctas; GUI monolítica que se salta la fachada |
| Frontend developer | 7 | Web vanilla limpia y accesible; editor básico, sin PWA |
| Backend developer | 7 | Compilador real; IR sin POO, recursión de cola con fallo |
| Diseñador gráfico | 5 | Tres paletas incompatibles, marca débil, título "2.0" |
| Diseñador UX | 6 | Web cálida; Qt saturado y técnico; `leer` sin consola interactiva |
| Diseñador UI | 6.5 | Web ordenada; Qt con 7 paneles acoplables y 17 ítems en "Ejecutar" |
| Diseñador UC | 6.5 | Casos de uso cubiertos, pero no guiados |
| Profesor universitario | 7 | Ideal para Compiladores y LF2; para Prog y ED faltan sílabo y rúbricas |
| Estudiante universitario | 6.5 | Currículo excelente, pero las soluciones están a la vista en los archivos |
| Persona común | 3.5 | No puede empezar sin Python, pip y consola |
| Estudiante de colegio | 4.5 | La web le gusta, pero rechaza "ñ" y `vacio main()` le frustra |

## 1. Pedagogo
- **Fortalezas:**
  - 13 niveles con progresión coherente;
  - 3 pistas graduadas por ejercicio;
  - cinco representaciones (código, bloques, flujo, UML y traza visual) que se convierten en ambos sentidos;
  - bilingüismo con salida idéntica en los dos idiomas;
  - errores explicados en cinco partes.
- **Debilidades:**
  - no hay quizzes, predicción de salida, problemas de Parsons ni autoevaluación;
  - los enunciados no dan el formato de salida (N01-E02 espera `a = 7, b = 3` sin decirlo);
  - no hay prueba de escritorio;
  - faltan técnicas algorítmicas y excepciones;
  - un solo caso por ejercicio;
  - `imprimir` no añade salto de línea (`print(a); print(b)` → `73`).

## 2. Analista de sistemas
- Hay unos 280 IDs `INV-NNNN`, pero solo en comentarios; no existe una matriz que lleve de requisito a prueba.
- `_audit.py` usa la ruta antigua del pipeline.
- La auditoría v10.1 está desactualizada ("15 000 líneas", "LL(1)").
- La especificación está en `.docx` y no se puede verificar contra el código.
- Los actores (perfiles de usuario) no están modelados.

## 3. Ingeniero de software
- **Lo que funciona:** 3111 pruebas, golden, fuzzing, CI con matriz y SBOM.
- **Lo que falla:** 10 fallos (ver [INFORME_TECNICO](INFORME_TECNICO_v11.md) §4).
- **Ya corregido en WS-0:** v11 sin commitear, legado en disco y CI pendiente.
- **Sigue pendiente:**
  - `mypy` está apagado en el núcleo;
  - `dist/InvenioLang.exe` está desactualizado.

## 4. Arquitecto de software
- **Fortalezas:**
  - pipeline en un solo sentido y fachada única;
  - ADR 001;
  - contratos JSON v1.
- **Debilidades:**
  - la GUI vuelve a montar el pipeline 7 veces;
  - cinco motores sin suite diferencial;
  - el IR queda fuera de `FASES`;
  - solo existe 1 ADR;
  - no hay tokens de diseño compartidos.

La arquitectura objetivo está en el plan maestro, WS-4.

## 5. Frontend developer (probado en el navegador)
- ✅ Funcionan:
  - ejecutar el programa;
  - panel de errores con explicación;
  - currículo con búsqueda y progreso;
  - aviso de cambios sin guardar;
  - "Comprobar ejercicio" mostrando la diferencia.
- ⚠️ La carga no muestra progreso (~10 MB de Pyodide desde jsDelivr) y no hay Service Worker.
- ⚠️ El editor no cierra llaves, no autocompleta y no pliega.
- ⚠️ Las pestañas desbordan a 800 px y la tarjeta del ejercicio se recorta a 375 px.
- ⚠️ La interfaz arranca en inglés sin preguntar.
- **Código:** `app.js` tiene 1114 líneas dentro de un solo cierre y el CSS tiene 1735 líneas con el tema oscuro duplicado.

## 6. Backend developer
- **Parser:** LALR(1) con 311 producciones, 787 estados, 20 conflictos S/R y 0 R/R.
- **IR:** TAC con cobertura del 66 %.
- **Código objetivo:** cobertura del 22 %.
- **Máquinas TAC y objetivo:** sin límites de ejecución.
- **`evaluar`:** rechaza rutas absolutas con un `ValueError` sin capturar y corrige un archivo por vez.

## 7. Diseñador gráfico
- **Tres sistemas de color:**
  - Qt usa VS Code Dark+;
  - la web usa un azul marino propio;
  - los SVG usan Primer.
  
  La palabra clave sale de tres colores distintos.
- **Marca débil:**
  - Qt no tiene icono;
  - el título dice "InvenioLang 2.0";
  - el "Acerca de" tiene créditos de curso.
- **Tipografía:** solo fuentes del sistema, unos 15 tamaños sueltos y `Consolas 11` fijo en Qt.

## 8. Diseñador UX (probado)
- **Errores que encontraría un principiante:**
  - código fuera de `main` → el mensaje dice "Falta punto y coma", que es un diagnóstico equivocado;
  - `entero año` → "Carácter ilegal: ñ", y además las secciones "Así falla / Así funciona" aparecen vacías;
  - llave sin cerrar → error en la posición 0:0;
  - `imprmir(...)` → no sugiere "¿quisiste decir imprimir?".
- **Fricciones de uso:**
  - no hay forma de empezar sin instalar nada;
  - `leer` obliga a escribir la entrada antes de ejecutar;
  - el editor arranca vacío;
  - Qt tiene 7 paneles acoplables;
  - Qt no usa `error_explainer`;
  - los atajos de teclado difieren entre Qt y web;
  - no hay celebración al resolver un ejercicio.

## 9. Diseñador UI
- **Web:**
  - ARIA correcto;
  - foco de 3 px;
  - objetivos táctiles de 2,25 rem;
  - respeta `prefers-*` y `forced-colors`.
- **Qt:**
  - sin pantalla de bienvenida;
  - alto contraste no seleccionable;
  - sin zoom;
  - sin menú Editar;
  - las variables se muestran con `repr()`.
- **Inconsistencias entre ambas:**
  - "Depurador" frente a "Paso a paso";
  - tuteo frente a usted.

## 10. Diseñador UC (casos de uso y contenido)

| Caso de uso | Estado |
|---|---|
| Primer programa | ⚠️ requiere Python o un servidor local |
| Ejercicio guiado | ✅ web / ❌ escritorio y CLI |
| Visualizar la ejecución | ✅ |
| De bloques a código | ✅ |
| Flujo → código | ✅ (web de solo lectura) |
| UML → código | ⚠️ solo texto |
| Tarea docente de punta a punta | ⚠️ |
| Plagio | ✅ CLI (pero ver el fallo de la regex en CUMPLIMIENTO §12) |
| Teoría de autómatas | ❌ |
| Contribuir | ⚠️ |

**Contenido:**
- **Lo bueno:** el tuteo cálido de la web.
- **Lo que falla:**
  - los tipos aparecen en inglés dentro de mensajes en español;
  - "Caracter" va sin tilde;
  - al alumno le llegan textos de desarrollador.

## 11. Profesor universitario

| Curso | Preparación | Falta |
|---|---|---|
| Intro | Alta | prueba de escritorio, quizzes, código inicial |
| Algoritmos | Media | DyV, voraz, backtracking, PD, recurrencias |
| Programación 1 | Alta | registros, archivos, excepciones |
| Programación 2 | Alta con reservas | `protegido`, excepciones, UML de secuencia, editor UML |
| Estructuras de Datos | Alta | colecciones genéricas, borrado en árbol B |
| LF1 | **Baja** | autómatas |
| LF2 | Media | tabla LL(1), ítems LR, traza, CST, CYK |
| Compiladores | Alta | fallos, IR de POO, CSE/LICM |

Herramientas docentes:
- ✅ sandbox;
- ✅ licencia MIT;
- ❌ evaluación por lotes;
- ❌ `casos.json` de ejemplo;
- ❌ panel por alumno;
- ❌ guías por curso.

## 12. Estudiante universitario
- La solución **es** el archivo del ejercicio, así que está a la vista.
- `runner.py` no permite comprobar el intento propio.
- Los enunciados no dan el formato de salida.
- El progreso solo se guarda en el navegador.

## 13. Persona común y estudiante de colegio
Recorrido real:
1. El README empieza con datos del curso y la instalación pide Python + pip + PySide6. La persona abandona.
2. La web solo funciona con un servidor local.
3. Rechaza `año`, `lógico`, `vacío main()` y `principal()`.
4. `"Edad: " + 15` muestra los tipos en inglés y no sugiere qué hacer.
5. `si (a = 1)` devuelve un error sobre ";".

**Imprescindible:**
- web pública;
- README con "Empieza en 3 pasos";
- `.exe` en Releases;
- alias con tilde y `principal`;
- identificadores Unicode;
- tipos en el idioma activo;
- sugerencias de "¿quisiste decir…?";
- modo Colegio.

El plan para llevar cada perspectiva a 10/10 está en [PLAN_MAESTRO_v12.md](PLAN_MAESTRO_v12.md).
