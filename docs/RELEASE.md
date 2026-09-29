# Release 10.0.0 — Procedimiento de congelamiento

1. `python pruebas/conformidad.py` → 391/391.
2. `python -m pytest tests/ -q` → verde.
3. `python scripts/verify_release.py` → `RELEASE_OK`.
4. `python -m inveniolang.sbom > SBOM.json`.
5. `git add -A && git commit -m "InvenioLang 10.0.0 GA" && git tag -a v10.0.0 -m "GA"`.
6. Distribuir `git archive v10.0.0`, nunca el worktree sucio.
7. Aula no confiable: exigir `--sandbox` / `policy.ejecutar_no_confiable`.
