# test_plataforma.py — LSP, presupuestos, SBOM y aislamiento
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang import api, lsp
from inveniolang.budgets import Budget, evaluar_metricas
from inveniolang.observability import PipelineMetrics
from inveniolang.sbom import generar_sbom


def test_lsp_initialize_y_didopen():
    """LSP interoperable con initialize y diagnostics."""
    docs: dict = {}
    r = lsp.manejar_mensaje({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, docs)
    assert r[0]["result"]["capabilities"]["hoverProvider"] is True
    r2 = lsp.manejar_mensaje(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "t.inv", "text": "void main() { }"}},
        },
        docs,
    )
    assert r2[0]["method"] == "textDocument/publishDiagnostics"


def test_lsp_hover_y_completion():
    """Hover contextual y completion localizable."""
    docs = {"t.inv": "void main() { int x = 1; }"}
    r = lsp.manejar_mensaje(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": "t.inv"}, "position": {"line": 0, "character": 20}},
        },
        docs,
    )
    assert "result" in r[0]
    c = lsp.completion_for("imp")
    assert any(x["label"] == "imprimir" for x in c)


def test_lsp_framing():
    """Framing Content-Length parseable."""
    cuerpo = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}).encode()
    flujo = io.BytesIO(b"Content-Length: " + str(len(cuerpo)).encode() + b"\r\n\r\n" + cuerpo)
    msgs = list(lsp.leer_mensajes(flujo))
    assert msgs[0]["method"] == "initialize"


def test_budgets_alertas():
    """Presupuestos monitorizables con alerta WARN."""
    m = PipelineMetrics()
    with m.mide("lexer"):
        pass
    assert evaluar_metricas(m, Budget(max_total_ms=100000))[0].nivel == "INFO"
    assert evaluar_metricas(m, Budget(max_total_ms=-1))[0].nivel in ("WARN", "CRIT")


def test_sbom_determinista():
    """SBOM reproducible y con hashes."""
    a = generar_sbom()
    b = generar_sbom()
    assert a["ficheros_clave"] == b["ficheros_clave"]
    assert a["producto"] == "inveniolang"
    assert all("sha256" in f for f in a["ficheros_clave"])


def test_aislado_ok_y_error():
    """Ejecución aislada atómica: ok y error controlado."""
    ok = api.ejecutar_aislado("void main() { imprimir(7); }", timeout=10)
    assert ok.ok
    assert "7" in "".join(ok.salida)
    mal = api.ejecutar_aislado("void main() { int x = 5 @ 3; }", timeout=10)
    assert not mal.ok
