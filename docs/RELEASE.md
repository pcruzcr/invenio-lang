# Release 11.0.0 — Procedimiento de congelamiento

1. `python pruebas/conformidad.py` → 408/408 (391 + 17 de InvenioLang 11).
2. `python -m pytest tests/ -q` → verde.
3. `python scripts/verify_release.py` → `RELEASE_OK`.
4. `python -m inveniolang.sbom > SBOM.json`.
5. `git add -A && git commit -m "InvenioLang 11.0.0 GA" && git tag -a v11.0.0 -m "GA"`.
6. Distribuir `git archive v11.0.0`, nunca el worktree sucio.
7. Aula no confiable: exigir `--sandbox` / `api.ejecutar_aislado`.
