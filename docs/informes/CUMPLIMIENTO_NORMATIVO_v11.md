# Cumplimiento normativo y análisis profundos — InvenioLang 11.0.0

> Fecha: 2026-10-22. Auditoría en solo lectura. Forma parte de `docs/informes/` (ver [README](README.md)).


## Contexto

Se pidió evaluar si InvenioLang **cumple o aplica** a ~120 atributos de calidad y ~200 normas y leyes (ISO/IEC, IEEE, NIST, UE, EE. UU. y Costa Rica). La evaluación se basa en evidencia ya verificada en esta sesión:
- conformidad 408/408;
- 3111 pruebas recolectadas;
- 208 programas ejecutados en 5 motores;
- 10 fallos de corrección reproducidos;
- prueba real del Estudio web;
- lectura de `SECURITY.md`, `docs/PRIVACY.md`, `NOTICE`, `sandbox.py`, `security.py`, `observability.py`, `lms.py`, `analytics/predict.py`, `tutor_llm.py`, CI y archivos de dependencias.

Al aprobar, el primer entregable es guardar esta matriz como `docs/CUMPLIMIENTO_NORMATIVO_v11.md` y luego ejecutar el plan del §8.

**Qué es InvenioLang a efectos normativos.** Es software educativo instalable: CLI, IDE Qt, extensión VS Code y Estudio web estático que ejecuta todo en el navegador. Licencia MIT, de un autor individual, uso académico en la Universidad Invenio (Costa Rica).
- **No** es un servicio en la nube.
- **No** tiene cuentas de usuario, ni servidor, ni pagos.
- **No** usa IA en producción.
- **Sí** trata datos de estudiantes, que pueden ser menores, en tres módulos opcionales: LMS xAPI, plagio y autograder. También guarda progreso en `localStorage`.

Esto determina qué normas aplican.

**Leyenda:**
- ✅ Cumple: evidencia sólida.
- 🟡 Parcial: existe, pero con huecos.
- ❌ No cumple: aplica y falta.
- ⚪ No aplica: fuera del alcance del producto. Pasaría a aplicar si cambia el modelo (SaaS, IA, venta en la UE).

**Aviso importante.** Las normas de sistema de gestión (ISO 9001, 27001, 20000-1, 22301, 42001, 27701, 37301) **certifican organizaciones, no programas**. Un repositorio no puede "cumplir ISO 27001". Lo que sí puede es *alinearse* con sus controles y aportar evidencia a la institución que se certifique.

---

## 1. Atributos de funcionalidad

| Atributo | Estado | Evidencia / brecha |
|---|---|---|
| Corrección | 🟡 | 408/408 de conformidad y 208/208 en el intérprete. Fallan 10 casos verificados: `g(3)` con parámetro `real` da 1.0; la recursión de cola optimizada da 12 en vez de 30; `--5` imprime 4; y otros |
| Completitud | 🟡 | Lenguaje y herramientas muy amplios. El IR cubre el 66 % y el código objetivo el 22 %. Faltan excepciones completas, `registro` y autómatas para LF1 |
| Exactitud | 🟡 | Enteros de 32 bits y división truncada en el intérprete. El TAC no detecta desbordamiento ni variables sin inicializar |
| Eficacia | ✅ | Cumple su objetivo docente: 133 ejercicios × 2 idiomas verificados |
| Robustez | 🟡 | Hay sandbox y límites. Pero hay `RecursionError` de Python que escapan (procedimientos, expresiones largas) y `evaluar` falla con rutas absolutas |
| Confiabilidad | 🟡 | Determinista. Los motores alternativos no tienen límites de pasos ni de recursión |
| Disponibilidad | 🟡 | Funciona sin conexión en escritorio. La web depende del CDN jsDelivr y no tiene Service Worker |
| Resiliencia / tolerancia a fallos | 🟡 | Conserva la salida parcial ante un error y el Estudio web reinicia el Worker. El parser pierde errores tras su recuperación |
| Consistencia | ❌ | Tres paletas visuales distintas; versión "2.0" en la GUI y 11.0.0 en el código; atajos distintos en Qt y web; docs que contradicen al código |
| Integridad | 🟡 | SBOM con SHA-256 y manifiesto web con hashes. La v11 entera está **sin commitear** |
| Interoperabilidad | ✅ | API Python, LSP, JSON v1 (traza, flujo, UML, bloques), PlantUML/Mermaid, xAPI 1.0 |
| Compatibilidad | 🟡 | Python 3.10–3.12 en CI (falta 3.13). Windows, Linux y macOS. Navegadores modernos |
| Adaptabilidad / configurabilidad | 🟡 | `Config` con límites, idioma es/en y temas. Sin perfiles por nivel (colegio, universidad) |
| Extensibilidad | ✅ | Fachada `core/compiler.py`, `api.py`, stdlib en InvenioLang, contratos versionados |
| Mantenibilidad | 🟡 | Buena modularidad en el núcleo. `gui_qt.py` tiene 3852 líneas, hay 19 módulos legado en disco y mypy está desactivado en el núcleo |
| Usabilidad | 🟡 | La web es cálida y está bien hecha. Rechaza la "ñ", no sugiere "¿quisiste decir…?", reporta errores en 0:0 y no se puede usar sin instalar Python |
| Accesibilidad | 🟡 | La web tiene ARIA sólido, contraste AAA, `forced-colors` y bloques usables con teclado. En Qt el alto contraste no se puede elegir, faltan nombres accesibles y no hay zoom. No hay auditoría axe-core |
| Cumplimiento | 🟡 | Ver §3 a §7 |
| Seguridad funcional | ⚪ | No controla sistemas físicos (IEC 61508 no aplica). Equivalente educativo: sandbox ✅ |

## 2. Calidad técnica, operación, seguridad e IA (atributos)

| Atributo | Estado | Evidencia / brecha |
|---|---|---|
| Eficiencia / rendimiento | 🟡 | Parser LALR iterativo y límites de tiempo. El Estudio web descarga ~10 MB en cada visita en frío. El plagio es O(n²) |
| Escalabilidad / elasticidad | ⚪/🟡 | Escritorio y web estática: escala trivialmente porque se ejecuta en el cliente. El plagio y el LMS no escalan a nivel institucional |
| Modularidad, cohesión, bajo acoplamiento, desacoplamiento | 🟡 | El núcleo es unidireccional y sin ciclos. La GUI rehace el pipeline 7 veces y se salta la fachada |
| Reutilización | ✅ | `api.py` es usada por la CLI, el LSP y la web; la stdlib es reutilizable |
| Portabilidad | ✅ | Python puro más Pyodide. Tk como respaldo |
| Testabilidad / verificabilidad | ✅/🟡 | 3111 pruebas, golden tests, fuzzing y validador de gramática. Falta una suite diferencial entre motores |
| Legibilidad / simplicidad | 🟡 | Docstrings y comentarios en español. Funciones de más de 2000 líneas en `MainWindow` |
| Versionado / compatibilidad hacia atrás | 🟡 | `_version.py` es la fuente única y los contratos JSON son v1. Las versiones no coinciden entre artefactos y no hay política de deprecación |
| Automatización | 🟡 | CI con flake8, mypy, conformidad y cobertura ≥80 %. El CI mejorado (`scripts/ci.yml.nuevo`) no está instalado y el actual tiene pasos de relleno |
| Patrones de diseño | ✅ | Observer, Strategy, Factory, Visitor y Memento reales; 18 GoF en ejemplos |
| Observabilidad, logging, métricas, telemetría, trazabilidad técnica | 🟡 | `observability.py`: logs JSON, `run_id` y `PipelineMetrics`; `budgets.py` con alertas de tiempo. Sin OpenTelemetry. La telemetría está desactivada por defecto, lo cual es correcto por privacidad |
| Monitorización, alertas, SLI/SLO/SLA, HA, balanceo, autoescalado, redundancia, DR, backup, gestión de incidentes y problemas | ⚪ | No hay servicio operado. Pasaría a aplicar si se ofrece como SaaS (§8, fase 7) |
| Diagnóstico | ✅ | 148 códigos `IL-XXX-NNN`, `error_explainer`, `--metrics` |
| Recuperación ante fallos | 🟡 | El Worker web se reinicia; el sandbox mata el proceso. Sin autoguardado en Qt |
| Autenticación, autorización, identidades, control de acceso | ⚪ | Sin cuentas ni servidor. Si se agrega LMS o SaaS, serán obligatorios |
| Mínimo privilegio / hardening | 🟡 | Rutas relativas, extensiones permitidas, Job Objects con límite de memoria, rlimits, Docker sin root con `seccomp.json`. El ejemplo Docker de `SECURITY.md` falla (sin `ply`). La GUI ejecuta en proceso salvo con `--sandbox` |
| Cifrado / confidencialidad | ❌ (si se usa el LMS) | `aula.jsonl` guarda correos o IDs de estudiantes en texto plano. `SECURITY.md` declara que no cifra |
| Gestión de secretos | ⚪/✅ | No hay secretos en el código (verificado) |
| Privacidad / protección de datos | 🟡 | `PRIVACY.md` existe: el LMS está desactivado por defecto y se recomienda retención de 12 meses. No hay consentimiento, borrado, anonimización, registro de tratamiento ni aviso en el Estudio web sobre `localStorage` y el CDN |
| Auditoría / trazabilidad de requisitos | 🟡 | `_audit.py` y unos 280 IDs `INV-NNNN` en comentarios. No hay matriz requisito → prueba |
| Gestión de vulnerabilidades | ❌ | `pip-audit` aparece solo como "recomendado". No hay Dependabot, CodeQL ni Bandit en CI. El lockfile no tiene `--hash` ni incluye PySide6 |
| Cadena de suministro | 🟡 | SBOM determinista ✅. Sin firma (Sigstore/cosign), sin procedencia SLSA, sin `THIRD_PARTY_NOTICES`. El `.exe` de un solo archivo incluye PySide6 (LGPL) sin aviso ni mecanismo de reenlazado |
| DevSecOps / seguridad de aplicaciones | 🟡 | Modelo de amenaza en `SECURITY.md` y canal de reporte con plazo de 5 días. Sin SAST/DAST, sin CSP en el Estudio web |
| MLOps, LLMOps, deriva, gestión de modelos, versionado de datos, linaje | ⚪ | No hay IA en producción. `tutor_llm.py` es un esbozo sin LLM y `analytics/predict.py` es una regla fija; ambos son legado y no se importan |
| Explicabilidad / interpretabilidad | ✅ (del compilador) | Errores con "por qué" y "cómo arreglar", trazas visuales y decisiones del parser visibles |
| Sesgo / equidad | 🟡 | Bilingüe y accesible. Excluye a quien no tiene equipo con Python; rechaza "ñ" y tildes |
| FinOps / eficiencia energética / optimización de recursos | ✅/⚪ | Ejecución en el cliente: coste de servidor casi nulo. El Estudio web podría cachear Pyodide para no descargarlo cada vez |
| Mejora continua | 🟡 | CHANGELOG, ROADMAP y auditorías periódicas. La documentación se desfasa respecto al código |

---

## 3. Normas de calidad, ciclo de vida, arquitectura y pruebas

| Norma | Aplica | Estado | Evidencia / brecha |
|---|---|---|---|
| ISO/IEC 25010:2023 (calidad de producto) | Sí | 🟡 | Ver §1 y §2. Puntos fuertes: interoperabilidad, portabilidad y testabilidad. Puntos débiles: corrección (10 fallos), consistencia y seguridad de datos |
| ISO/IEC 25019 (calidad en uso) | Sí | 🟡 | Eficacia alta. Satisfacción y libertad de riesgo limitadas por las fricciones de usabilidad y la falta de pruebas con usuarios |
| ISO/IEC 25012 (calidad de datos) | Parcial | 🟡 | Datos del currículo validados (`.expected`). Hay discrepancias entre enunciado y salida (N01-E08) |
| ISO/IEC/IEEE 12207 / 15288 (ciclo de vida) | Sí | 🟡 | Hay procesos de desarrollo, pruebas y release (`verify_release.py`). Faltan gestión de configuración (la v11 no está en git), procesos de retiro (el legado no se elimina) y operación |
| ISO/IEC/IEEE 29148 (requisitos) | Sí | 🟡 | Especificación en 19 `.docx` y 408 casos normativos. Faltan requisitos identificados, priorizados y trazables a pruebas |
| ISO/IEC/IEEE 29119 / IEEE 829 (pruebas) | Sí | 🟡 | Muchas pruebas y de buena calidad. Falta documentación de pruebas (plan, diseño, informe), criterios de entrada y salida, y pruebas de usabilidad y aceptación |
| ISO/IEC/IEEE 1012 / ANSI/IEEE 1012 (V&V) | Sí | 🟡 | Verificación fuerte (conformidad, validador de gramática). Falta la validación con usuarios reales y la V&V entre los cinco motores |
| IEEE 730 (aseguramiento de calidad) | Sí | 🟡 | Hay compuertas de CI. No hay plan SQA documentado y el CI mejorado no está instalado |
| ISO/IEC/IEEE 42010 / ANSI/IEEE 1471 (arquitectura) | Sí | 🟡 | Hay un solo ADR y diagramas sueltos. Faltan vistas y puntos de vista (lógica, desarrollo, despliegue) y el registro de decisiones 002–006 |
| ISO/IEC 5055 (calidad estructural, CISQ) | Sí | 🟡 | ruff y flake8 limpios. Riesgos de mantenibilidad: módulos de 2000–3800 líneas, código muerto y mypy desactivado |
| ISO 9001 (gestión de calidad) | Organizacional | ⚪/🟡 | Es para la institución. El proyecto aporta evidencias (CHANGELOG, CI, auditorías) |
| ISO 31000 (riesgos) | Sí | ❌ | No hay registro de riesgos (técnicos, de privacidad, legales, de continuidad) |
| ISO 22301 / 27031 (continuidad) | Organizacional | ⚪/❌ | Riesgo real: un solo autor y la v11 sin commitear. El riesgo de pérdida de trabajo es alto |
| TOGAF, ArchiMate, COBIT, ISO/IEC 38500 | Organizacional | ⚪ | Pasarían a aplicar si la universidad lo adopta como servicio institucional |
| ITIL 4, ISO/IEC 20000-1 | Solo si es servicio | ⚪ | — |
| Twelve-Factor App | Parcial | 🟡 | Configuración por `Config`, logs a stderr, sin estado. No es una aplicación web de servidor |

## 4. Seguridad y ciberseguridad

| Norma | Aplica | Estado | Evidencia / brecha |
|---|---|---|---|
| ISO/IEC 27001/27002 (controles) | Organizacional, con controles de producto | 🟡 | Controles presentes: 8.25–8.28 de desarrollo seguro (sandbox, validación de entradas, límites, revisión) y 8.8 de vulnerabilidades (solo "recomendado"). Faltan: 5.34 privacidad de PII, 8.24 criptografía y 8.30 gestión de terceros |
| ISO/IEC 27034 (seguridad de aplicaciones) | Sí | 🟡 | Hay modelo de amenaza y controles. No hay marco de controles normativo ni verificación periódica |
| ISO/IEC 27035 / NIST SP 800-61 (incidentes) | Sí (mínimo) | 🟡 | Canal `[SECURITY]` y plazo de 5 días. No hay `SECURITY.md` estándar de GitHub con versiones soportadas, CVD/CVE, ni plan de respuesta |
| ISO/IEC 27036 / NIST SP 800-161 (cadena de suministro) | Sí | 🟡 | SBOM ✅. Sin firma, sin hashes en el lockfile, sin evaluación de dependencias |
| NIST SP 800-218 SSDF | Sí | 🟡 | PO (preparar): 🟡. PS (proteger el software): 🟡, sin firma ni integridad del repositorio. PW (producir bien): ✅ pruebas, 🟡 SAST. RV (responder a vulnerabilidades): 🟡 |
| NIST CSF 2.0 | Organizacional | 🟡 | Identificar: 🟡 (SBOM). Proteger: 🟡. Detectar, Responder y Recuperar: mínimos. Gobernar: ❌ |
| NIST SP 800-53 / FISMA / FedRAMP | Gobierno de EE. UU. | ⚪ | — |
| NIST SP 800-207 Zero Trust | Solo si es servicio | ⚪ | — |
| CIS Controls v8 | Organizacional | 🟡 | IG1 relevantes: inventario de software (SBOM ✅), gestión de vulnerabilidades ❌, protección de datos ❌ |
| OWASP Top 10 / ASVS (Estudio web) | Sí | 🟡 | Ejecución aislada en un Worker, iframe con `sandbox` para el paso a paso, sin `eval` de HTML externo. Falta **Content-Security-Policy**, falta SRI en el script de Pyodide del CDN y falta revisión ASVS nivel 1 |
| OWASP SAMM | Sí | 🟡 | Madurez aproximada de 1 en Diseño e Implementación y de 0–1 en Verificación y Operaciones |
| OWASP API Top 10 | No hay API de red | ⚪ | — |
| ISA/IEC 62443 (OT), DORA (finanzas), TIA-942, IEEE 493/1366/802/1588 | No | ⚪ | Fuera del dominio |
| Cyber Resilience Act (UE) 2024/2847 | Condicional | ⚪ hoy / ❌ si se comercializa | El software libre no comercial está excluido. Si se vende o monetiza en la UE (obligaciones desde 2027), exigirá seguridad por diseño, gestión de vulnerabilidades, SBOM (✅), actualizaciones de seguridad, reporte a ENISA y marcado CE |
| NIS2 | No (el producto no es entidad esencial) | ⚪ | Aplicaría a la universidad si se clasifica como entidad |

## 5. Privacidad y protección de datos (incluye menores)

Datos tratados:
- `lms.py` guarda actor (correo o ID), resultados y códigos de error en `aula.jsonl` en texto plano.
- El plagio procesa el código de los estudiantes.
- `localStorage` del navegador guarda progreso y borradores.
- El CDN jsDelivr recibe la IP del visitante del Estudio web.
- `analytics/predict.py` calcula un "riesgo de abandono" (legado, no se importa).

| Norma | Aplica | Estado | Brecha |
|---|---|---|---|
| **Ley 8968 CR** + Decreto 37554-JP | **Sí** (uso en la Universidad Invenio) | 🟡 | Falta consentimiento informado, finalidad, derechos ARCO (acceso, rectificación, cancelación, oposición) con un procedimiento para ejecutarlos y medidas de seguridad (cifrado). Evaluar si la base de datos debe inscribirse ante PRODHAB. La retención de 12 meses es solo recomendación |
| **Ley 10238 CR** (imagen, voz y datos de menores) | Sí si se usa en colegios | ❌ | No hay modo para menores, ni consentimiento parental, ni minimización explícita |
| GDPR (UE) 2016/679 | Si hay estudiantes en la UE | 🟡 | Mismas brechas. Además: transferencia al CDN (IP), aviso de `localStorage` (ePrivacy: es almacenamiento estrictamente necesario, pero debe informarse), privacidad desde el diseño (art. 25) y EIPD si se perfila a estudiantes |
| ePrivacy Directive | Sí (web en la UE) | 🟡 | `localStorage` funcional sin aviso |
| FERPA (EE. UU.) | Si lo usa una institución de EE. UU. | 🟡 | Los registros del LMS son "education records". Falta control de acceso y de divulgación |
| COPPA (EE. UU., menores de 13) | Si hay menores de 13 en EE. UU. | ❌ | Sin consentimiento parental verificable. El Estudio web no recoge datos en servidor, lo que reduce el riesgo |
| CCPA/CPRA y leyes estatales de privacidad | Solo con umbrales comerciales | ⚪ | — |
| Leyes estatales de notificación de brechas | Solo si hay servicio con PII | ⚪ | — |
| ISO/IEC 27701 / 29100 / 27555 (borrado) / IEEE 7002 / IEEE 2857 | Recomendable | 🟡 | Principios de minimización (LMS desactivado por defecto) ✅. Falta procedimiento de borrado, seudonimización por defecto y registro de tratamiento |
| ISO/IEC 27018 / 27017 (nube) | Solo si es SaaS | ⚪ | — |
| HIPAA, HITECH, GLBA, SOX, FCRA, ECOA, Fair Housing, EEO | No | ⚪ | No trata salud, finanzas, crédito, vivienda ni empleo |

## 6. Accesibilidad

| Norma | Aplica | Estado | Brecha |
|---|---|---|---|
| WCAG 2.2 AA (base de las siguientes) | Sí | 🟡 | Web: alto cumplimiento declarado (contraste AAA probado, ARIA, teclado, movimiento reducido). Qt: alto contraste no seleccionable, nombres accesibles escasos, sin zoom. No hay auditoría formal |
| Section 508 / ADA (EE. UU.) | Si lo adopta una institución de EE. UU. | 🟡 | Requiere VPAT/ACR, que no existe |
| European Accessibility Act (2025) | Si se comercializa en la UE | 🟡 | Igual que lo anterior más una declaración de accesibilidad |
| Costa Rica: Ley 7600 y Ley 9049 (accesibilidad digital en el sector público; no estaban en la lista, pero aplican a una universidad) | Sí | 🟡 | Falta declaración de accesibilidad |

## 7. Firma digital, propiedad intelectual, delitos informáticos e IA

| Norma | Aplica | Estado | Evidencia / brecha |
|---|---|---|---|
| Ley 6683 (derechos de autor) / Ley 8039 (PI) CR | Sí | 🟡 | MIT y `NOTICE` claros. Hay contradicción de titularidad: `pyproject.toml` nombra a "Universidad Invenio" y `LICENSE` a Pablo José Cruz Salazar. Falta `THIRD_PARTY_NOTICES` con PLY (BSD), PySide6/Qt (**LGPL v3**: el `.exe` de un solo archivo debe permitir reemplazar Qt y adjuntar la licencia) y Pyodide (MPL-2.0). La autoría de los 133 ejercicios y los textos de las pistas también debe quedar declarada |
| Ley 8454 (firma digital) / eIDAS / eIDAS 2 | Solo si se emiten certificados | ⚪ | `certification.py` (legado) emitía PDF sin firma. Si se emiten constancias oficiales, usar firma digital certificada (BCCR) o eIDAS |
| Ley 9048 / 9135 / 9452 Budapest CR, CFAA EE. UU. | Sí, como contexto | ✅ | El sandbox y la validación de rutas impiden que código de un estudiante acceda a archivos de otros. Conviene una política de uso aceptable para laboratorios |
| Ley 8642 telecomunicaciones / Ley 9738 teletrabajo / Ley 7169 ciencia y tecnología | Marginal | ⚪ | Ley 7169: posible vía de financiamiento o incentivos (MICITT) |
| Estrategia Nacional de Ciberseguridad 2023–2027 / MICITT | Orientativa | 🟡 | Se alinea con SSDF y SBOM; falta gestión de vulnerabilidades |
| FTC Act §5 | Si se comercializa en EE. UU. | 🟡 | Riesgo de afirmaciones engañosas: la documentación promete "AFD O(n)", "7 lenguajes Rosetta", "JIT", "tutor LLM", "módulos eliminados" y conteos de pruebas falsos. Hay que corregir la documentación (§8, fase 1) |
| **EU AI Act 2024/1689** | **Hoy no** (no hay IA activa) | ⚪ / ⚠️ riesgo latente | `analytics/predict.py` calcula un "riesgo de abandono" de estudiantes. Un sistema de IA usado en educación para evaluar o monitorizar a estudiantes es de **alto riesgo (Anexo III, punto 3)**. Hoy es una regla fija sin uso, pero si se reactivara o se convirtiera en un modelo implicaría obligaciones de alto riesgo. **Recomendación: eliminarlo.** `tutor_llm.py` (esbozo): si se implementa un tutor con LLM, aplican obligaciones de transparencia (art. 50) y la alfabetización en IA (art. 4) |
| ISO/IEC 42001, 22989, 23053, 23894, 24027, 24028, 24029, 25058, 25059, 5338, 5259, 12792, 38507, 8183, 12791 | No (sin IA) | ⚪ | Pasan a aplicar al incorporar un tutor con IA o analítica predictiva. Mínimo recomendado entonces: 42001 + 23894 + NIST AI RMF + perfil GenAI 600-1 |
| NIST AI RMF / AI 600-1 | No (sin IA) | ⚪ | Ídem |
| IEEE 7000 (ética en el diseño) | Sí (es software educativo) | 🟡 | Valores implícitos (inclusión, bilingüismo, accesibilidad, no dar la solución). No hay registro de valores ni partes interesadas |
| IEEE 7001 (transparencia) | Parcial | ✅ | Explicabilidad del compilador muy alta |
| IEEE 7003 (sesgo algorítmico) | Parcial | 🟡 | Sesgo lingüístico: rechaza "ñ" y tildes. Plagio: falsos positivos posibles sin revisión humana documentada |
| IEEE 7009 (diseño a prueba de fallos) | Parcial | 🟡 | El sandbox y los límites existen; hay errores de Python que escapan |
| IEEE 7005, 7010, 7011, 7012 | No | ⚪ | — |
| Digital Services Act, Data Act, Data Governance Act | No | ⚪ | — |

---

## 8. Plan para alcanzar el cumplimiento (por prioridad)

### Fase 0: Integridad y continuidad (1–2 días). Cubre ISO 12207, 22301, 31000 y 25010 (integridad)
- Commitear toda la v11. Aplicar `scripts/limpiar_obsoletos.py --aplicar`, que elimina `analytics/predict.py` (riesgo AI Act), `tutor_llm.py` y `certification.py`.
- Instalar `scripts/ci.yml.nuevo`.
- Subir el repositorio a un remoto con respaldo, protección de rama y un segundo mantenedor (riesgo de un solo autor).
- Crear `docs/riesgos.md` (registro ISO 31000: técnico, privacidad, legal, continuidad).

### Fase 1: Corrección y veracidad (1–2 semanas). Cubre 25010 (corrección), 1012, 29119 y FTC §5
- Corregir los 10 fallos verificados.
- Suite diferencial de los cinco motores y fuzzing gramatical.
- `scripts/verificar_docs.py`, que falle en CI si la documentación contradice al código.
- Retirar las afirmaciones falsas: AFD O(n), 7 lenguajes, JIT, conteos de pruebas.

### Fase 2: Seguridad de la cadena de suministro y DevSecOps (1 semana). Cubre SSDF, 27036, 800-161, CRA, OWASP y CIS
- `pip-audit`, Bandit/CodeQL y Dependabot en CI.
- Lockfile con `--hash` que incluya PySide6.
- Releases firmados (Sigstore/cosign) con procedencia SLSA nivel 2 mediante GitHub Actions, y SBOM adjunto en formato CycloneDX o SPDX.
- `SECURITY.md` al estándar de GitHub: versiones soportadas, CVD y advisories.
- Estudio web: **CSP**, SRI para Pyodide u opción autoalojada, cabeceras seguras en GitHub Pages.
- Corregir el ejemplo Docker.

### Fase 3: Privacidad y menores (1–2 semanas). Cubre Ley 8968, Decreto 37554-JP, Ley 10238, GDPR, FERPA, COPPA, 27701 y 29100
- `lms.py`:
  - seudonimización por defecto (hash con sal del actor);
  - cifrado opcional en reposo;
  - comando de **borrado y exportación por estudiante** (derechos ARCO / art. 15–17 GDPR);
  - retención automática configurable.
- Aviso de privacidad en el Estudio web (`localStorage` y CDN), opción "borrar mis datos" y Pyodide autoalojado para no enviar la IP a terceros.
- **Modo menores**: sin LMS, sin identificadores y con guía de consentimiento parental para colegios.
- Plantillas: consentimiento informado, registro de actividades de tratamiento, EIPD, y orientación para la eventual inscripción ante PRODHAB (la decide la universidad).
- Plagio: documentar que el resultado es indicio y no prueba, con revisión humana obligatoria (IEEE 7003).

### Fase 4: Accesibilidad certificable (1–2 semanas). Cubre WCAG 2.2 AA, Section 508, EAA, Ley 7600 y 9049
- Alto contraste seleccionable y zoom en Qt, nombres accesibles completos.
- axe-core y pruebas con lector de pantalla (NVDA y VoiceOver).
- **VPAT/ACR** y declaración de accesibilidad.
- Aceptar "ñ" y tildes en identificadores y alias de palabras clave (también reduce el sesgo, IEEE 7003).

### Fase 5: Propiedad intelectual y licencias (2–3 días). Cubre Ley 6683, Ley 8039 y LGPL
- `THIRD_PARTY_NOTICES.md` con PLY (BSD), PySide6/Qt (LGPL v3), Pyodide (MPL-2.0) y sus dependencias.
- Distribuir el `.exe` en modo directorio (onedir), o explicar cómo reemplazar Qt.
- Unificar la titularidad (`pyproject.toml` frente a `LICENSE`).
- Declarar la licencia de los contenidos: currículo y documentación con CC BY 4.0 o MIT.

### Fase 6: Requisitos, arquitectura y pruebas documentadas (2 semanas). Cubre 29148, 42010, 29119-3, IEEE 730 y 5055
- `docs/requisitos.csv` (ID, sección de la especificación, módulo, prueba) verificado en CI.
- Especificación `.docx` convertida a Markdown fuente.
- `docs/ARQUITECTURA.md` con vistas 42010 y ADR 002–006.
- Plan de pruebas y plan SQA con criterios de entrada y salida.
- Pruebas de usabilidad con estudiantes (validación 1012 / calidad en uso 25019).
- Partir los módulos gigantes y reactivar mypy en el núcleo (5055).

### Fase 7: Solo si pasa a ser SaaS, se comercializa o incorpora IA
- **SaaS**: ISO 27001 y 20000-1 en la organización, SLI/SLO (disponibilidad del Estudio web y latencia de corrección), OpenTelemetry con Prometheus y Grafana, backup y recuperación ante desastres, autenticación (OIDC con la universidad), autorización por rol (docente, estudiante), ISO 27017/27018 y plan de incidentes (NIST 800-61).
- **Venta en la UE**: CRA (marcado CE, reporte de vulnerabilidades a ENISA) y EAA.
- **IA** (tutor LLM o analítica): ISO/IEC 42001 + 23894 + NIST AI RMF y 600-1, AI Act (transparencia del art. 50; alto riesgo si evalúa o monitoriza a estudiantes, Anexo III-3), evaluación continua y registro de modelos, mitigación de sesgos, supervisión humana y sin decisiones automatizadas sobre calificaciones.
- **Constancias oficiales**: firma digital Ley 8454 / eIDAS.

---

## 9. Resumen por bloque

| Bloque | Aplicable hoy | Cumple | Parcial | No cumple |
|---|---|---|---|---|
| Funcionalidad (atributos) | 20 | 3 | 15 | 1 |
| Calidad técnica (atributos) | 18 | 5 | 13 | 0 |
| Operación | 5 de 21 (resto ⚪ sin servicio) | 1 | 4 | 0 |
| Seguridad y gobierno | 14 de 20 | 1 | 10 | 3 |
| IA y evolución | 5 de 25 (resto ⚪ sin IA) | 2 | 3 | 0 |
| Normas de calidad y ciclo de vida | 13 | 0 | 12 | 1 |
| Normas de seguridad | 10 | 0 | 10 | 0 |
| Privacidad y menores | 7 | 0 | 5 | 2 |
| Accesibilidad | 4 | 0 | 4 | 0 |
| PI, legal e IA | 6 | 2 | 4 | 0 |

**Conclusión:**
- InvenioLang **no incumple ninguna ley de forma grave hoy**, porque no opera un servicio, no usa IA activa y el LMS está desactivado por defecto.
- **Casi todo lo aplicable está "parcial"**. Los bloqueantes reales son:
  1. corrección del núcleo;
  2. integridad del repositorio (v11 sin commitear);
  3. gestión de vulnerabilidades y firma;
  4. privacidad del LMS (Ley 8968 y menores);
  5. licencias de terceros (LGPL de Qt);
  6. veracidad de la documentación;
  7. eliminar el legado con riesgo AI Act.
- Con las fases 0 a 6 (6–9 semanas), el proyecto quedaría **alineado** con ISO 25010, 12207, 29148, 29119, 1012, 42010, SSDF, OWASP ASVS L1, WCAG 2.2 AA, Ley 8968, Ley 10238, GDPR y la PI de Costa Rica.
- La certificación formal ISO de sistemas de gestión corresponde a la institución, no al repositorio.

---

## 10. Análisis profundo de seguridad (pentest en solo lectura)

| ID | Severidad | Hallazgo | Ubicación | Corrección |
|---|---|---|---|---|
| F4 | **Alta** | El límite de 1M iteraciones / 5 s se elude. El contador es por ciclo y el reloj solo se mira cada 2000 vueltas, así que tres ciclos anidados de 1999 vueltas o la recursión sin ciclos corren sin límite (25 s sin IL-EJE-030) | `interpreter.py:1777-1828` | Contador global de pasos (ciclos + llamadas) y reloj cada N pasos globales |
| F5 | **Alta** | Sin límite de memoria dentro del proceso: `max_string_len` nunca se aplica (`s=s+s` llega a 225 MB), arreglos de 1,18 GB, salida sin tope, `elevar(3, 2147483647)` bloquea con el GIL tomado. La GUI y la web ejecutan dentro del proceso | `config.py:40`, `builtins.py:219`, `gui_qt.py:838` | Tope de cadena y salida, presupuesto acumulado de elementos, `elevar` en float, GUI en subproceso |
| F9 | **Alta (integridad de la evaluación)** | `evaluation` ejecuta cada entrega con cwd = carpeta de entregas: el alumno puede `leer_archivo("casos.json")` y copiar la salida esperada, o sobrescribir entregas ajenas | `sandbox.py:226` | Copiar la entrega a un `TemporaryDirectory` y pasar un entorno mínimo |
| F2 | **Alta** | Builtins de archivo sin confinamiento a una raíz y sin `realpath`: resuelven contra el cwd del proceso (se pudo leer `requirements.txt` y `SBOM.json`); escritura posible en `.vscode/tasks.json`, que es vector de ejecución; un symlink o junction escapa | `builtins.py:274-314` | `raiz_archivos` explícita + `realpath` + `commonpath` |
| F6/F8 | Media | `RecursionError` sin capturar: procedimientos recursivos, 3000 `si` anidados, expresiones largas. La compilación previa al sandbox corre dentro del proceso; 100k paréntesis tardan 23 s | `interpreter.py:728`, `api.py:183` | Profundidad máxima en el parser, capturar en toda entrada, compilar en el hijo |
| F7 | Media | `communicate()` acumula toda la salida del hijo antes de truncarla (300 MB en menos de 1 s) | `sandbox.py:180` | Lectura en streaming con tope |
| F1 | Media | Se aceptan nombres de dispositivo: `CONIN$.txt` bloquea el intérprete más de 15 s; `NUL .txt`, `COM¹.txt` | `security.py:60-62` | `os.path.isreserved` + lista ampliada |
| F11 | Media | ReDoS en el importador PlantUML: 52 s con una flecha de 8000 guiones | `uml/plantuml.py:70-73` | Tope de longitud de línea y regex sin retroceso |
| F14 | Media | El LSP cae con `Content-Length: abc`, JSON no objeto, anidamiento profundo o `+1`×5000 en el editor; sin tamaño máximo | `lsp.py:80-214` | Validar tamaño y tipo; `try/except` con error JSON-RPC −32603 |
| — | Media | El sandbox pasa todo `os.environ` al hijo (fuga de claves del docente) y en Windows no limita el número de procesos | `sandbox.py:220`, `:94-107` | Entorno mínimo y `ActiveProcessLimit` |
| F10/F12/F13/F15 | Baja | Mermaid sin escapar; JSON profundo produce `RecursionError` en los importadores; Estudio web sin CSP ni SRI; la línea no-dict del LMS rompe el mapa de calor y el alumno puede inflarlo | varios | — |
| ✅ | Info | Bloquea `..`, rutas absolutas, UNC, ADS, punto o espacio final, extensiones en mayúsculas y nulos. Sin `eval`/`exec`/`pickle`/`shell=True`. **HTML/SVG escapados correctamente (sin XSS)**, iframe con `sandbox`, Worker solo por `postMessage`. El timeout del sandbox mata el árbol de procesos (Job Object) | — | — |

## 11. Análisis profundo de rendimiento (medido)

| Medida | Resultado |
|---|---|
| Arranque: `import inveniolang.api` / CLI `--version` / GUI Qt | 1,0 s / 1,1 s / 2,5–2,9 s |
| Fases de hola mundo (léxico/sintaxis/semántica/tipos/ejecución) | 4 / 6 / 0,4 / 0,05 / 0,1 ms; 9 de los 12 ms se van en reconstruir lexer y parser en cada compilación |
| 20 000 líneas | léxico 13,7 s y parser 15,9 s, **crecimiento cuadrático** por `data[:lexpos]` en `_calc_col` (`lexer.py:614`, `parser.py:1762`); con `rfind` baja a 2,5 s y 8,5 s, lineal |
| **Intérprete frente a Python puro** | ciclo de 10⁶: **402× más lento** (119 s); fib(25): 485×; burbuja n=400: 741×; la máquina TAC es 3,4–4,5× más rápida que el intérprete de árbol |
| Consecuencia en el aula | con el límite de 5 s, un ciclo de más de ~40 000 vueltas o una burbuja de más de 200 elementos se corta con IL-EJE-030 |
| Memoria | compilar 10k líneas: 18,8 MB; fib(25): 0,12 MB |
| Herramientas | `trazar` 132 ms (1,7 KB/paso); `traza_html` 1,3 s; flujo, UML, formateador y traductor < 200 ms; `validar_gramatica` 1,7 s |
| Sandbox por caso | **1,14 s** (reimporta el paquete) frente a 10,7 ms dentro del proceso; una tarea de 10 casos tarda ~11 s |
| Plagio | O(n²), N=800 en 31,6 s; **además está roto (§12)** |
| Estudio web | `generado/` 1,1 MB + JS 107 KB + Pyodide (~6–7 MB, estimado sin medir) desde el CDN; **`parsetab.py` se excluye del zip**, así que cada carga reconstruye las tablas LALR (2,5 s nativo, más en WASM) |
| Configuración | **`api.ejecutar(config=...)` se ignora**: el intérprete lee constantes globales; solo funcionan las variables de entorno |

Causas en el camino crítico del intérprete:
- `Visitable(ABC)` vuelve lento cada `isinstance`: 1,34 µs frente a 0,30 µs con `type(x) is X`, unas 62 comprobaciones por vuelta.
- Cadenas de `isinstance` en lugar de despacho por tabla.
- Doble búsqueda de ámbito.
- Un `Marco` nuevo por bloque.
- `ReturnException` en cada retorno.
- Operadores comparados como cadenas.

**Optimizaciones**, por orden:
1. Columnas con `rfind`/`bisect`: el análisis queda lineal.
2. Quitar `ABC` y despachar con diccionarios: ~3×.
3. Resolver slots de variables en el semántico y no crear `Marco` vacíos: ~5× en total junto con el punto 2.
4. Un único lexer/parser con `write_tables=False`: de 12 a 3 ms.
5. No volver a tokenizar.
6. Incluir `parsetab.py` en el zip web.
7. Sandbox con todos los casos en un solo hijo: de 11 s a 1,5 s.
8. Plagio con MinHash/LSH.
9. Pasar `config` al intérprete.
10. Importaciones diferidas: arranque a 0,5 s.
11. Trazas incrementales.

## 12. Fallos funcionales nuevos (verificados)
- **El detector de plagio no funciona**: `re.sub(r"//.*|/\*.*?\*/", "", flags=re.S)` en `plagiarism/cluster.py:22` borra todo desde el primer `//` hasta el final del archivo, porque con `re.S` el `.*` cruza los saltos de línea. Verificado: un programa que empieza con un comentario queda como `''`. Todo el currículo tiene comentarios, así que la similitud sale siempre 0. **Severidad crítica para su uso docente.**
- `api.ejecutar(config=...)` ignora los límites indicados.
- `elevar(10, 400)` produce un `OverflowError` sin capturar (`builtins.py:219`).

## 13. Pedagogía curso por curso (revisión de los 133 ejercicios)
- **Taxonomía de Bloom**:

| Nivel | Ejercicios |
|---|---|
| Recordar | 0 |
| Comprender | 13 |
| **Aplicar** | **100** |
| Analizar | 15 |
| Evaluar | 3 |
| Crear | 2 |

  Falta pensamiento de diseño y evaluación. Total: unas 180 h de trabajo del estudiante.
- **Unos 45 enunciados no permiten deducir la salida exacta**: faltan datos o formato. Ejemplos: N01-E03, N01-E08, N02-E04, N03-E02, N08-E01…E09, N09-E01…E12, N13-E03/E05/E06/E08, donde el "pseudoaleatorio" usa una semilla sin documentar. **63 `.expected` llevan rótulos en inglés** (`survivor =`, `says woof`, `RED`) dentro de ejercicios en español.
- Solo 6 de 133 ejercicios usan entrada (`leer`). Hay temas usados antes de enseñarlos (arreglos en N02-E13, N03-E03, N03-E12; lista enlazada en N09-E07), saltos de dificultad (N03 con 7 ejercicios de recursión de golpe; AVL sin ejercicio previo de rotaciones) y unos 12 conceptos duplicados (búsqueda binaria ×3, burbuja ×3…).
- No hay ejercicios de depuración, de predecir la salida, de escribir pruebas ni con varios casos.

| Curso | Cobertura | Faltan (resumen) |
|---|---|---|
| Intro / Lógica | Buena en control de flujo | tablas de verdad/De Morgan, flujograma → programa, prueba de escritorio, menú, "detecta el error" ×3 |
| Programación 1 | Buena | **registros, archivos, excepciones, pruebas unitarias**, proyecto integrador |
| Programación 2 | Parcial (un ejercicio por concepto) | UML → código, excepciones propias, iterador, State, Composite, SOLID, proyecto de más de 5 clases |
| Estructuras de Datos | Buena | deque, heapsort, trie, conjunto, Union-Find, rotaciones AVL guiadas, caché LRU |
| Algoritmos | Media | **recurrencias/teorema maestro, PD (mochila, LCS, edición), voraz, backtracking, MST, Floyd, KMP, invariantes** |
| **Lenguajes Formales 1** | **Sin ejercicios** (solo teoría en `Semana09`) | nivel N14: AFD, AFN → AFD, minimización, Thompson, AP para aⁿbⁿ, MT, bombeo |
| **Lenguajes Formales 2** | **Sin ejercicios** (solo documentación) | nivel N15: derivaciones, recursión izquierda, FIRST/FOLLOW, LL(1), descenso recursivo, shunting-yard, AST, else colgante, TAC |

Plan semanal de 16 semanas por curso con los ejercicios existentes, listo en el informe del agente. **Unos 60 % de los huecos se cubren promoviendo programas de `pruebas/`** al currículo: kmp, mochila, n_reinas, kruskal, prim, floyd, heapsort, trie, deque, conjunto, archivo_io y 12 patrones.

## 14. Accesibilidad e IDE Qt (inspección en vivo, offscreen)
- 337 widgets, 97 interactivos. **16 sin nombre accesible, entre ellos el propio `CodeEditor`**, además de 4 `QLineEdit`, el árbol del explorador y la lista de errores. Un lector de pantalla anuncia el editor principal sin nombre (WCAG 4.1.2).
- 26 botones sin foco de teclado: "Cerrar pestaña", los botones de cerrar/flotar de cada dock y los de la barra (WCAG 2.1.1, en parte por los valores por defecto de Qt).
- 125 acciones, **solo 16 con atajo**. No hay atajos de zoom (Ctrl+=, Ctrl+−). Existen Ctrl+Z, Ctrl+Y, Ctrl+F, Ctrl+H y Ctrl+G como `QShortcut`, no como acciones de menú, por lo que no se descubren.
- Fuente de la interfaz: 9 pt, sin escalado global. **Icono de ventana nulo. Título "InvenioLang 2.0"**. La sesión anterior se restaura sin bienvenida.
- Contraste: los textos principales cumplen. En el tema claro, el aviso `warn_sub` tiene **2,86:1** frente al fondo, por debajo del 3:1 exigido para componentes no textuales (WCAG 1.4.11).
- Alto contraste definido pero no seleccionable (WCAG 1.4.3/1.4.11 para usuarios con baja visión).
- Web (probada): ARIA, foco y contraste correctos. Las pestañas desbordan a 800 px y la tarjeta del ejercicio queda recortada a 375 px (WCAG 1.4.10 reflow, parcial).

## 15. Plan actualizado: adiciones a las fases del §8
- **Fase 1 (núcleo)**, además de lo ya listado:
  - contador global de pasos (F4);
  - límites de memoria, salida y `elevar` (F5);
  - profundidad máxima en el parser y captura de `RecursionError` en API, LSP e importadores JSON (F6, F8, F12, F14);
  - **corregir la regex del plagio** (`re.S` → procesar línea por línea o `//[^\n]*`) con prueba de regresión;
  - pasar `config` al intérprete;
  - `OverflowError` en `elevar`.
- **Fase 2 (seguridad)**:
  - evaluación en un `TemporaryDirectory` con entorno mínimo (F9);
  - `raiz_archivos` + `realpath` (F2);
  - lectura de la salida del sandbox con tope (F7);
  - `os.path.isreserved` (F1);
  - ReDoS de PlantUML (F11);
  - LSP robusto (F14);
  - CSP;
  - escape de Mermaid;
  - GUI Qt ejecutando en subproceso.
- **Nueva fase R (rendimiento, 1–2 semanas)**: optimizaciones 1–11 del §11, con objetivo de intérprete ≥5× más rápido, compilación lineal, arranque ≤0,5 s, corrección de 10 casos ≤2 s, `parsetab` en la web y benchmarks en CI (`pytest-benchmark`) para evitar regresiones.
- **Fase 6 (pedagogía)**:
  - reescribir unos 45 enunciados con datos y formato de salida;
  - `.expected.es` / `.expected.en` o rótulos neutros;
  - varios casos ocultos por ejercicio;
  - reordenar N02-E13, N03-E03, N03-E12 y N09-E07;
  - promover `pruebas/` al currículo;
  - nuevos niveles N14 Autómatas y N15 Gramáticas;
  - ejercicios de depuración, predicción y diseño (subir el porcentaje de Analizar, Evaluar y Crear);
  - guías de 16 semanas por curso.
- **Fase 4 (accesibilidad)**:
  - nombre accesible en `CodeEditor` y en los 15 widgets restantes;
  - foco en "Cerrar pestaña";
  - acciones de menú para Editar y zoom;
  - fuente escalable;
  - icono de app;
  - `warn_sub` con contraste ≥3:1;
  - alto contraste seleccionable;
  - reflow web a 320 px.

## Verificación
- Seguridad: repetir las sondas del §10 (tres ciclos anidados, `s=s+s`, `CONIN$.txt`, `casos.json` desde la entrega, PlantUML con 8000 guiones, LSP con `Content-Length: abc`): todas deben terminar en un diagnóstico IL dentro del límite.
- Rendimiento: benchmark reproducible (ciclo de 10⁶, fib(25), burbuja 400, compilación de 20k líneas) con umbrales en CI.
- Plagio: dos entregas idénticas con comentarios deben dar similitud ≥0,95.
- Pedagogía: un script valida que cada `.json` declare el formato de salida y que existan ≥3 casos por ejercicio.
- Fase 0: `git status` limpio, CI nuevo en verde, legado ausente (`tests/flujo/test_flujo_api_cli.py` y `cierre/test_limpiar_obsoletos.py` en verde).
- Fase 1: fuzzing y suite diferencial sin divergencias; conformidad 408/408; `verificar_docs.py` en verde.
- Fase 2: `pip-audit` sin hallazgos; firma verificable con `cosign verify-blob`; CSP comprobada en el navegador.
- Fase 3: prueba de borrado y exportación por actor en `lms.py`; el Estudio web sin peticiones a terceros con Pyodide autoalojado (panel de red).
- Fase 4: axe-core sin violaciones; recorrido completo con NVDA.
- Fase 5: `THIRD_PARTY_NOTICES.md` cubre el 100 % del SBOM.
- Fase 6: cada requisito de `requisitos.csv` enlaza a una prueba existente y en verde.
