# Manual Docente — InvenioLang 3.0 Estable

**Métrica éxito H1+H2:** tiempo corrección -50%, completitud `arbol_avl.inv` +30%.

## Flujo clase (45 min)
1. **Live coding** (10'): `curriculum/nivel1/01_hola.inv` → `CompilerFacade:cli.py:230` check instantáneo.
2. **Visualización** (15'): `ds_visualizer.py:1` → arreglo/lista `pila_marcos:interpreter.py:169` + `to_dot()` proyectado.
3. **Entrega** (15'): estudiante sube `.inv` → `evaluation.py:20` `run_secure` con timeout 5s + `plagiarism_score:15`.
4. **Dashboard** (5'): `lms.py:55` `dashboard()` → heatmap `IL-SEM-003` pico → refuerzo.

## Rúbrica micro-credencial `certification.py:67`
- Compila 0.2 + Tests ocultos 0.5 + Complejidad `complexity.py:16` ≤O(n²) 0.15 + Estilo 0.15 = nota 10. `aprobado >=6`.

## Instalación aula
```
pip install -e .[dev]  # pyproject.toml:33
docker compose up --build  # docker/Dockerfile:1 read-only + gVisor
code --install-extension vscode-extension/inveniolang-vscode-0.1.0.vsix  # lsp.py:10
```

## Accesibilidad (WCAG AA)
- `accessibility.py:1` `TEMA_ALTO_CONTRASTE` (7:1), `gui/theme.py:1` Strategy, `editor` con `AccessibleName`.
- Atajos: `Ctrl+Shift+P` paleta, `F8` error, `Ctrl+\`` terminal. Ver `ACCESSIBILITY.md:1`.

## Gramática verificable
`docs/gramatica.ebnf:1` + `grammar_validator.py:1` → CI `python -m inveniolang.grammar_validator` falla si `lalr_conflict: true` o `first_sets<10`.

## Soporte
`SECURITY.md:1` contacto `tic@invenio.ac.cr`, `CHANGELOG.md:1`, versión `__version__="10.0.0"` en `inveniolang/__init__.py:4` y `COMPILER_VERSION="10.0.0"` en `inveniolang/core/__init__.py:4`.
