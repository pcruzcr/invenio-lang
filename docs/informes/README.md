# Informes de auditoría y plan v12

Auditoría integral de InvenioLang 11.0.0, hecha el 2026-10-22 en modo solo lectura, y el plan que la convierte en trabajo.

| Documento | Contenido |
|---|---|
| [PLAN_MAESTRO_v12.md](PLAN_MAESTRO_v12.md) | **Plan definitivo**: criterios medibles de 10/10 por dimensión, 12 frentes de trabajo en 5 olas, puertas de CI y riesgos |
| [TABLERO.md](TABLERO.md) | Estado de cada frente y de cada dimensión; se actualiza al cerrar cada ola |
| [INFORME_TECNICO_v11.md](INFORME_TECNICO_v11.md) | Arquitectura, compilador fase por fase, los 10 fallos de corrección, cobertura de LF1/LF2, inventario con uso pedagógico y comercial |
| [INFORME_INTEGRAL_v11.md](INFORME_INTEGRAL_v11.md) | 14 perspectivas, de pedagogo a estudiante de colegio, con la prueba real del Estudio web |
| [CUMPLIMIENTO_NORMATIVO_v11.md](CUMPLIMIENTO_NORMATIVO_v11.md) | Matriz de atributos y normas (ISO/IEC, IEEE, NIST, UE, EE. UU., Costa Rica), pentest, rendimiento medido, revisión de los 133 ejercicios y accesibilidad de Qt |
| [../riesgos.md](../riesgos.md) | Registro de riesgos (ISO 31000) |

## Método

Se hicieron 13 auditorías independientes:
- documentación frente a código;
- arquitectura, GUI y CLI;
- cobertura curricular;
- front-end y back-end del compilador;
- inventario de funcionalidades;
- diseño UI, UX y gráfico;
- recorridos por perfil de usuario;
- prueba del Estudio web en navegador;
- matriz normativa;
- pentest;
- rendimiento medido;
- revisión de los 133 ejercicios;
- inspección offscreen de la GUI Qt.

Para verificar, se reconstruyó la gramática en memoria, se ejecutaron 208 programas en los 5 motores y se reprodujeron los fallos con `api.ejecutar`. Además, `pruebas/conformidad.py` dio 408/408.

## Resultado en una línea

El núcleo funciona y la funcionalidad es muy amplia. Antes de considerarlo un producto premium hay que resolver estos bloqueantes:
1. **Corrección**: 10 fallos del compilador más el detector de plagio, que no funciona.
2. **Seguridad**: el límite de pasos se puede eludir, no hay límite de memoria y el evaluador deja leer `casos.json`.
3. **Rendimiento**: el intérprete es entre 400 y 740 veces más lento que Python.
4. **Experiencia de principiante**: no admite "ñ" ni tildes, no ofrece "¿quisiste decir…?" y no se puede usar sin instalar nada.
5. **Coherencia visual y documental.**
6. **Privacidad del LMS.**
7. **Licencias de terceros.**
