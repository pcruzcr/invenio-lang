# Privacy Notice — Classroom Data

InvenioLang core (`core/compiler.py:17` `compile_pure`) processes code in memory
and emits no telemetry by default. Logging via `observability.py:94`
`configure_observability` writes to stderr only when enabled by the operator.

Optional modules that may handle student data:

* `lms.py:27` xAPI statements (failed/passed, error codes).
* `plagiarism/cluster.py:1` similarity over submitted sources.
* `analytics/predict.py:1` risk scores.
* GUI `QSettings` persistence (theme, font size).

Classroom policy for worldwide use:

1. Disable LMS/analytics by default; enable only with institutional consent.
2. Retain submissions max 12 months unless regulation requires less.
3. No third-party tracking in CLI/core. Qt GUI makes no network calls.
4. Isolate untrusted code with `--sandbox` / `api.ejecutar_aislado`.

Contact: `tic@invenio.ac.cr` with subject `[PRIVACY] InvenioLang`.
