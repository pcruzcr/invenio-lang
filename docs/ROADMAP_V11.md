# Roadmap v11 — Sin ruptura salvo lo marcado [BREAKING]

1. Calidad total: baseline `ruff`/`flake8` en `inveniolang/` o limpieza completa; hoy solo nuevos ficheros limpios (2731 errores legacy).
2. Publicación: PyPI/test-PyPI, `pip-audit` remoto, CI win/linux/mac verde (`ci.yml:84` jobs definidos).
3. [BREAKING] Sandbox por defecto para no confiable en `cli.py:169` (`api.ejecutar_aislado` hoy opt-in).
4. [BREAKING] `api v11`: errores como objetos `{codigo,linea,columna,fix}` en vez de `tuple[str,...]` en `core/__init__.py:17`.
5. Backend único: POO/matrices en IR (`ir.py` hoy lanza `NoSoportadoIR` con clases).
6. Lenguaje: excepciones de usuario, genéricos con herencia, currículum EN, B-tree con borrado, Trie UTF-8.
7. IDE: minimapa por teclado y Orca (`ACCESSIBILITY.md:16`), LSP publicado.
