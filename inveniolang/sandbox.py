# sandbox.py — Sprint 2 gVisor/resource sandbox para aula (Windows + Unix)
# Patrones: Strategy (sandbox strategy), Decorator (limite), Factory
from __future__ import annotations
import ctypes
import subprocess
import sys
import os
from typing import Dict, Any, List, Optional
from .patterns import Strategy
from .observability import get_logger

try:
    import resource  # type: ignore[assignment]

    HAS_RESOURCE = True
except ImportError:
    resource = None  # type: ignore[assignment]
    HAS_RESOURCE = False  # Windows: sin resource, usa timeout + Job

_log = get_logger("sandbox")

# Constantes Win32 para Job Objects (límite de memoria en Windows)
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_LIMIT_PROCESS_MEMORY_UIJOB = 0x00020000
_JobObjectExtendedLimitInformation = None
if os.name == "nt":

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            (n, ctypes.c_ulonglong)
            for n in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
                "ReadCount",
                "WriteCount",
                "OtherCount",
            )
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _JobObjectExtendedLimitInformation = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    _CREATE_NO_WINDOW = 0x08000000


def _windows_job_limits(job: int, mem_mb: int, procs: int = 64) -> bool:
    """Aplica límite de memoria + kill-on-close a un Job Object de Windows."""
    if _JobObjectExtendedLimitInformation is None:
        return False
    info = _JobObjectExtendedLimitInformation()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_PROCESS_MEMORY | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    info.ProcessMemoryLimit = mem_mb * 1024 * 1024
    return bool(
        ctypes.windll.kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    )  # 9 = JobObjectExtendedLimitInformation


class SandboxStrategy(Strategy):
    def execute(self, *args, **kwargs) -> Any:
        raise NotImplementedError


class ResourceSandbox(SandboxStrategy):
    """Sandbox Unix (resource) + Windows (timeout + Job) — 5s, 256M, sin fork bomb.

    Auditoría v10.2:
      - Soporta stdin (`entrada`: lista de líneas → se alimentan por pipe),
        imprescindible para casos de prueba en evaluation.py.
      - En Windows se usa Popen + AssignProcessToJobObject: el límite de
        memoria (mem_mb) es REAL vía Job Object, y KILL_ON_JOB_CLOSE garantiza
        que ningún proceso huérfano sobreviva al timeout.
    """

    def execute(
        self, cmd: List[str], timeout: int = 5, mem_mb: int = 256, entrada: Optional[List[str]] = None, *args, **kwargs
    ) -> Dict[str, Any]:
        stdin_text: Optional[str] = None
        if entrada is not None:
            stdin_text = "\n".join(str(e) for e in entrada) + "\n"

        def preexec():
            if not HAS_RESOURCE:
                return
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
                resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
                resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
            except Exception:
                pass

        use_job = os.name == "nt"
        creationflags = 0
        if use_job:
            try:
                import subprocess as sp

                creationflags = sp.CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW
            except Exception:
                creationflags = _CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=preexec if HAS_RESOURCE and not use_job else None,
                creationflags=creationflags,
            )
        except Exception as e:
            _log.error("sandbox_error", extra={"error": str(e)})
            return {"ok": False, "stdout": "", "stderr": str(e), "returncode": 1}

        job = None
        if use_job and _JobObjectExtendedLimitInformation is not None:
            k32 = ctypes.windll.kernel32
            job = k32.CreateJobObjectW(None, None)
            if job:
                _windows_job_limits(job, mem_mb)
                # Asigna el proceso hijo al Job (límite de memoria real en Windows)
                if not k32.AssignProcessToJobObject(job, int(proc._handle)):
                    _log.warning("job_assign_fallo")

        try:
            out, err = proc.communicate(input=stdin_text, timeout=timeout + 1)
            ok = proc.returncode == 0
            _log.info(
                "sandbox_ejecucion", extra={"returncode": proc.returncode, "ok": ok, "cmd": cmd[0] if cmd else ""}
            )
            return {"ok": ok, "stdout": (out or "")[:5000], "stderr": (err or "")[:2000], "returncode": proc.returncode}
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            _log.warning("sandbox_timeout", extra={"timeout": timeout})
            return {
                "ok": False,
                "stdout": (out or "")[:5000],
                "stderr": "Timeout IL-EJE-030 (sandbox %ss)" % timeout,
                "returncode": 124,
            }
        except Exception as e:
            _log.error("sandbox_error", extra={"error": str(e)})
            return {"ok": False, "stdout": "", "stderr": str(e), "returncode": 1}
        finally:
            if job:
                # KILL_ON_JOB_CLOSE: termina cualquier hijo superviviente
                ctypes.windll.kernel32.CloseHandle(job)


class WindowsSandbox(ResourceSandbox):
    """Alias explícito para aula Windows — usa timeout + límite 2M file size ya en cli.py."""


class DockerSandbox(SandboxStrategy):
    """Docker/gVisor sandbox descriptor — genera comando docker run."""

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        return {
            "docker": "docker run --rm --read-only --tmpfs /tmp --memory=256m --cpus=0.5 --pids-limit=64 --network=none -v $(pwd):/app -w /app python:3.11-slim python -m inveniolang.cli",
            "gvisor": "docker run --runtime=runsc --rm ... (ver docker/README.md)",
            "note": "Usar docker/Dockerfile + compose network_mode none",
        }


def run_sandboxed(
    file: str, strategy: str = "resource", timeout: int = 5, entrada: Optional[List[str]] = None
) -> Dict[str, Any]:
    m = {"resource": ResourceSandbox(), "docker": DockerSandbox()}
    strat = m.get(strategy, ResourceSandbox())
    if strategy == "docker":
        return strat.execute()
    return strat.execute([sys.executable, "-m", "inveniolang.cli", file], timeout=timeout, entrada=entrada)
