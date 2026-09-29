# Web IDE — Pyodide + Sandbox (H2.4)

## Pyodide (navegador, cero instalación)
`web/pyodide.html` carga `inveniolang` vía Pyodide (CPython en WASM).
Reusa `lexer.py:9`, `parser.py:11`, `semantic.py:44`, `interpreter.py:149` sin cambios — solo `micropip.install("ply")`.

```html
<script type="module">
import {loadPyodide} from "https://cdn.jsdelivr.net/pyodide/v0.26.1/full/pyodide.mjs";
const py = await loadPyodide();
await py.loadPackage("micropip");
await py.runPythonAsync(`
import sys
sys.path.insert(0, "/inveniolang")
from inveniolang.cli import CompilerFacade
print(CompilerFacade().execute("pruebas/hola_mundo.inv"))
`);
</script>
```

## Docker Sandbox (aula compartida)
`docker/Dockerfile` aísla `builtins.py` file I/O con `readOnlyRootFilesystem` + `tmpfs`.

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m runner && chown -R runner /app
USER runner
# límites: 256M, 5s, sin red
CMD ["python","-m","inveniolang.cli","--check"]
```

Compose con límites:
```yaml
services:
  runner:
    build: .
    read_only: true
    tmpfs: ["/tmp"]
    mem_limit: 256m
    cpus: 0.5
    network_mode: none
    pids_limit: 64
```

Validación: `docker run --rm inveniolang python pruebas/conformidad.py` → 391/391.
