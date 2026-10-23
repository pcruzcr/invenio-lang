"""Servidor HTTP local para las pruebas del estudio web (INV-4230).

Sirve ``web/estudio/`` en ``/``, una copia de Pyodide (real o simulada) en
``/__pyodide/`` y, para el Pyodide simulado, el puente real en ``POST
/__puente``. Solo escucha en 127.0.0.1 y en un puerto libre.
"""

from __future__ import annotations

import mimetypes
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from inveniolang.web import llamar

RAIZ = Path(__file__).resolve().parents[2]
ESTUDIO = RAIZ / "web" / "estudio"
SIMULADO = Path(__file__).resolve().parent / "pyodide_simulado"

mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("application/wasm", ".wasm")


def crear_servidor(
    pyodide: Path | None = None, generado: Path | None = None, estudio: Path = ESTUDIO
) -> ThreadingHTTPServer:
    """Servidor sin arrancar; ``pyodide`` None usa el simulado.

    ``generado`` sirve ``/generado/`` desde otro directorio (las pruebas
    empaquetan en uno temporal para no depender de lo que haya en el árbol).
    """
    base_pyodide = pyodide or SIMULADO

    class Manejador(SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:
            ruta = path.split("?", 1)[0].split("#", 1)[0]
            if ruta.startswith("/__pyodide/"):
                return str(base_pyodide / ruta[len("/__pyodide/") :])
            if generado is not None and ruta.startswith("/generado/"):
                return str(generado / ruta[len("/generado/") :])
            return str(estudio / ruta.lstrip("/"))

        def do_POST(self) -> None:  # noqa: N802 - nombre exigido por http.server
            if self.path != "/__puente":
                self.send_error(404)
                return
            largo = int(self.headers.get("Content-Length", "0"))
            respuesta = llamar(self.rfile.read(largo).decode("utf-8")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(respuesta)))
            self.end_headers()
            self.wfile.write(respuesta)

        def log_message(self, *args: object) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", 0), Manejador)


def arrancar(
    pyodide: Path | None = None, generado: Path | None = None
) -> tuple[ThreadingHTTPServer, str]:
    """Arranca el servidor en un hilo y devuelve (servidor, URL base)."""
    servidor = crear_servidor(pyodide, generado)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"http://127.0.0.1:{servidor.server_address[1]}/"


if __name__ == "__main__":
    import sys
    import time

    real = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    _, url = arrancar(real)
    print(f"{url}index.html?pyodide=/__pyodide/", flush=True)
    while True:
        time.sleep(3600)
