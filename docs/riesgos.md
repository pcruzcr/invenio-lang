# Registro de riesgos — InvenioLang (ISO 31000)

> Creado el 2026-10-22 a partir de la auditoría de `docs/informes/`. Revisar al cerrar cada ola del [plan maestro](informes/PLAN_MAESTRO_v12.md).
>
> Probabilidad e impacto se puntúan de 1 (bajo) a 5 (alto). Nivel = P × I.

| ID | Riesgo | Categoría | P | I | Nivel | Tratamiento | Frente | Estado |
|---|---|---|---|---|---|---|---|---|
| R-01 | Pérdida de trabajo: la v11 estaba sin commitear y hay un solo mantenedor | Continuidad | 4 | 5 | 20 | Commit en rama + remoto con respaldo + protección de rama + segundo mantenedor | WS-0 | Mitigado en parte (commit hecho; faltan protección y segundo mantenedor) |
| R-02 | Resultados incorrectos del compilador (promoción entero→real, recursión de cola, `--5`) usados como referencia en clase | Calidad | 4 | 5 | 20 | Prueba de regresión + suite diferencial de 5 motores + fuzzing | WS-1 | Abierto |
| R-03 | El detector de plagio da siempre 0 por la regex con `re.S` | Calidad / docencia | 5 | 4 | 20 | Corregir la regex y probar que la similitud es ≥ 0,95 | WS-1 | **Mitigado** (INV-5005) |
| R-04 | Un estudiante congela el equipo: el límite de pasos se elude y no hay tope de memoria | Seguridad / disponibilidad | 4 | 4 | 16 | Contador global de pasos, topes de cadena y salida, GUI en subproceso | WS-1, WS-2 | Mitigado en parte (tiempo global INV-5009; faltan topes de memoria y GUI en subproceso) |
| R-05 | Trampa en la evaluación: la entrega lee `casos.json` desde su carpeta | Integridad académica | 3 | 5 | 15 | Ejecutar en una carpeta temporal con entorno mínimo | WS-2 | Abierto |
| R-06 | Datos personales de estudiantes, incluidos menores, en texto plano (`aula.jsonl`) | Privacidad (Ley 8968, Ley 10238, GDPR) | 3 | 4 | 12 | Seudonimización, cifrado, borrado y exportación, aviso y consentimiento | WS-10, WS-11 | Abierto |
| R-07 | Incumplir la LGPL de Qt en el `.exe` de un solo archivo | Legal / PI | 3 | 3 | 9 | Distribución en directorio y `THIRD_PARTY_NOTICES.md` | WS-7, WS-11 | Abierto |
| R-08 | Afirmaciones de la documentación que no son ciertas (AFD O(n), 7 lenguajes, conteos) | Reputación / FTC §5 | 4 | 3 | 12 | `verificar_docs.py` en CI + corrección | WS-11 | Abierto |
| R-09 | Vulnerabilidades en dependencias sin detectar | Seguridad / cadena de suministro | 3 | 3 | 9 | `pip-audit`, CodeQL, Dependabot, lockfile con hashes, firma | WS-2 | Abierto |
| R-10 | Abandono de principiantes (instalación, "ñ", mensajes técnicos) | Adopción | 5 | 3 | 15 | Web pública, alias y Unicode, "¿quisiste decir…?", modo Colegio | WS-5, WS-8, WS-9 | Abierto |
| R-11 | El intérprete lento corta programas de clase (límite de 10 s desde INV-5015; antes 5 s, casi nunca aplicado) | Rendimiento | 4 | 3 | 12 | Optimizaciones medidas + benchmarks en CI | WS-3 | Abierto |
| R-12 | Los cambios `[BREAKING]` (API v12, `imprimir`, sandbox por defecto) rompen material existente | Compatibilidad | 3 | 3 | 9 | Alias, avisos de deprecación, migración con `traducir`, guía | WS-4, WS-5 | Abierto |
| R-13 | Si se reactivara la analítica predictiva de abandono, sería IA de alto riesgo según el AI Act (Anexo III-3) | Cumplimiento IA | 1 | 4 | 4 | `analytics/predict.py` eliminado; cualquier IA futura pasa por ISO 42001 y AI RMF | WS-0 | **Mitigado** |
| R-14 | Código falso o legado que confunde a los estudiantes (`backend/jit.py`, `tutor_llm.py`…) | Calidad / reputación | 5 | 2 | 10 | 19 módulos eliminados con `limpiar_obsoletos.py` | WS-0 | **Mitigado** |
