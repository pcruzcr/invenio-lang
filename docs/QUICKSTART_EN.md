# InvenioLang 11 — Quickstart (EN)

Classroom-ready compiler for Formal Languages. Spanish/English bilingual language; this guide is in English for worldwide adoption.

## Requirements

* Python 3.10–3.14 (tested 3.10, 3.11, 3.12).
* `ply==3.11` required. `PySide6>=6.6` only for Qt GUI; CLI needs no GUI.

## Install

```bash
pip install -r requirements.txt
python pruebas/conformidad.py   # must report 391/391
python -m pytest tests/ -q
```

Portable/no-GUI classroom:

```bash
python main.py --check pruebas/hola_mundo.inv
python main.py pruebas/hola_mundo.inv
python -m inveniolang.cli --sandbox pruebas/hola_mundo.inv
```

## Untrusted code policy

Default in-process execution is for trusted teacher examples only. For student
submissions use isolation:

```bash
python -m inveniolang.cli --sandbox submission.inv
```

```python
from inveniolang import api
api.ejecutar_aislado(open("submission.inv", encoding="utf-8").read())
```

See `docs/PRIVACY.md`, `docs/SUPPORT.md`, `SECURITY.md`.
