# CONTRIBUTING.md — Guía de contribución InvenioLang

## Reglas de oro (no negociables)

1. **Contrato del núcleo**: cualquier cambio en `CompileRequest`/`CompileResult`
   requiere bump de versión minor. `core/` no hace IO ni usa `print`/`sys`.
2. **Seguridad**: toda ruta/entrada de usuario pasa por `security.validar_*`.
   Todo subprocess externo va por `sandbox.ResourceSandbox` (nunca
   `subprocess.run` directo fuera de sandbox.py).
3. **Observabilidad**: toda fase nueva del pipeline se envuelve en
   `metrics.mide("fase")`; los eventos van por `observability.get_logger` a
   stderr, jamás a stdout (contrato §7 de E/S del compilador).
4. **Errores**: todo diagnóstico usa el catálogo §15 con formato
   `[IL-XXX-NNN] archivo:l:c — mensaje` vía `ErrorManager`.
5. **Tests en verde antes de merge**:

```bash
python -m pytest tests -q          # unitarias + regresión golden
python pruebas/conformidad.py      # 391 casos de conformidad
python -m flake8 inveniolang       # PEP 8 / pyflakes (0 hallazgos)
python -m mypy inveniolang --config-file mypy.ini
python -m black --check inveniolang --extend-exclude "gui_qt.py|gui_tk.py|parsetab.py|parser.py"
```

## Estilo (PEP 8 / PEP 20 / PEP 257)

- **black** es el formateador autoritativo (línea a 120).
- Los ignorados de flake8 están documentados en `setup.cfg` — no ampliar la
  lista sin justificación en el PR.
- Docstrings en todos los módulos y funciones públicas (PEP 257).
- "Beautiful is better than ugly": prefiero 3 funciones pequeñas a 1
  función de 200 líneas.

## mypy: gradiente de severidad

`mypy.ini` marca módulos legado con `ignore_errors = True`. Al refactorizar
un módulo, **retira su sección** de la lista y corrige sus errores — así el
 chequeo estricto crece con el tiempo en lugar de degradarse.

## Añadir un built-in / nodo del AST

1. Nodo en `ast_nodes.py` (+ Visitor).
2. Regla en `parser.py` y semántica en `semantic.py`.
3. Type checker + intérprete (`visit_*`).
4. Casos en `pruebas/` + test en `tests/`.
5. Documentar en la sección correspondiente de `docs/`.
