# Política de Seguridad — InvenioLang

**Versión:** 2.0  
**Contacto:** tic@invenio.ac.cr

## Modelo de amenaza (entorno educativo)

InvenioLang se ejecuta en aulas con 20–40 estudiantes sobre la misma red y,
a veces, sobre el mismo equipo compartido. El programa del estudiante es
**código no confiable**: debe estar aislado del sistema.

## Controles implementados

| Riesgo | Control | Código |
|--------|---------|--------|
| **Path traversal** vía `leer_archivo`/`escribir_archivo` | Solo rutas relativas simples, sin `..`, sin `:`/`/`, extensiones permitidas `.txt/.inv/.csv/.dat/.log/.json`, máx 260 chars | `inveniolang/builtins.py::_validar_ruta` + `inveniolang/security.py` |
| **DoS por archivo gigante** | `leer_archivo` máx 2 MiB, `.inv` fuente máx 1 MiB, truncado con error `IL-EST-015` | `builtins.py`, `cli.py::leer_fuente`, `security.py` |
| **DoS por arreglo/matriz gigante** | `int[100000]` máx 100k, matriz 10k×10k pero `filas*cols` ≤ 200k, error `IL-SEM-071` | `semantic.py`, `interpreter.py` |
| **Ciclo infinito / recursión** | `max_iteraciones=1M` → `IL-EJE-030`, `max_segundos=5s`, `MAX_RECURSION=500` → `IL-EJE-040` | `interpreter.py` |
| **Ejecución aislada (v10.2)** | `ResourceSandbox`: timeout + rlimits (Unix) y **Job Object con límite de memoria + `KILL_ON_JOB_CLOSE`** (Windows, vía ctypes); stdin por caso de prueba vía pipe | `sandbox.py` |
| **fork bomb / procesos** | `RLIMIT_NPROC=64` (Unix), `--pids-limit=64` (Docker), `CREATE_NEW_PROCESS_GROUP` (Windows) | `sandbox.py` |
| **Ventanas emergentes ocultas** | `CREATE_NO_WINDOW` en subprocess de sandbox | `sandbox.py` |
| **Codificación no UTF-8** | Rechazo temprano con `IL-LEX-001` antes del lexer | `cli.py::leer_fuente`, `gui_qt.py`, `gui.py` |
| **Inyección / XSS en salida** | Salida sanitizada/truncada en GUI, sin `eval`/`exec` de código del estudiante | `security.py::sanitizar_salida` |
| **Sobrescritura de binarios** | Extensiones `.py/.exe/.dll/.sh` bloqueadas en builtins | `builtins.py` |

## Lo que NO se promete

- Aislamiento a nivel de OS por defecto. Para despliegue multi-tenant real,
  use el sandbox de contenedor incluido:

```bash
docker run --rm --read-only --tmpfs /tmp --memory=256m --cpus=0.5 \
  --pids-limit=64 --network=none -v "$(pwd):/app" -w /app \
  python:3.11-slim python -m inveniolang.cli programa.inv
# opcional: --runtime=runsc (gVisor) para aislamiento a nivel kernel
```

- Cifrado de archivos del estudiante.

## Escaneo de dependencias (recomendado en CI)

```bash
pip install pip-audit && pip-audit -r requirements.txt
```

## Reportar vulnerabilidad

Envíe un correo a **tic@invenio.ac.cr** con asunto `[SECURITY] InvenioLang`.
No abra un issue público hasta coordinar la divulgación. Tiempo de respuesta
objetivo: 5 días hábiles.

## Auditoría

```bash
python -c "from inveniolang.security import auditar_seguridad; print(auditar_seguridad())"
python pruebas/conformidad.py   # 391 casos, debe pasar al 100%
```
