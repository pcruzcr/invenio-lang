# Support — Worldwide Classroom

## Channels

* Bugs/security: see `SECURITY.md:47` (`tic@invenio.ac.cr`, subject `[SECURITY]`).
* General: repository issues with `.inv` reproducer + `python pruebas/conformidad.py` output.

## Service levels (classroom pilot)

* Security reports: first response 5 business days.
* Reproducible crashes (no `IL-` code, Python traceback): triaged next teaching cycle.
* No 24/7 SLA. For exams, pre-validate with `SBOM.json` + `requirements-lock.txt`.

## Reporting template

```text
version: python main.py --version
os/python: Windows 11 / Python 3.11
reproducer: pruebas/*.inv or inline code
expected: IL-XXX-NNN or output
obtained: output + run_id from api
conformidad: 391/391 yes/no
```
