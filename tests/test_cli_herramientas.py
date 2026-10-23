"""CLI y herramientas didácticas/docentes (INV-1009..1026).

Cada prueba documenta el defecto que corrige: la mayoría falla contra el
árbol anterior (herramienta inexistente, código fingido o error de la CLI).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from inveniolang import api, cli, lsp  # noqa: E402
from inveniolang.accessibility import contraste_ratio, validar_tema_accesible  # noqa: E402
from inveniolang.core import analizar_fuente  # noqa: E402
from inveniolang.formatter import formatear  # noqa: E402
from inveniolang.observability import get_current_run  # noqa: E402

PRUEBAS = RAIZ / "pruebas"


def _cli(monkeypatch, capsys, *args: str) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["inveniolang", *args])
    rc = cli.main()
    return rc, capsys.readouterr().out


# ---------------------------------------------------------------- CLI
@pytest.mark.parametrize(
    ("flags", "esperado"),
    [
        (["--check"], "OK - 0 error(es)"),
        (["--tokens"], "KW_VOID"),
        (["--ast"], "MainDecl(main)"),
        (["--tabla"], "TABLA DE SÍMBOLOS"),
        (["--ir"], "CÓDIGO INTERMEDIO (TAC)"),
        (["--ir-opt"], "CÓDIGO INTERMEDIO OPTIMIZADO"),
        (["--target"], "CÓDIGO OBJETIVO"),
        (["--target-reg"], "linear-scan"),
        (["--run-ir"], "Hola"),
        (["--run-ir-opt"], "Hola"),
        (["--ssa"], "B0:"),
        (["--complejidad"], "main: O(1)"),
        (["--efectos", "--idioma", "en"], "main: writes to the screen"),
        (["--ver-como", "python"], "def main"),
        (["--formatear"], "void main"),
        (["--step", "--maxpasos", "2"], "TRAZA DE EJECUCIÓN"),
        (["--check", "--json"], '"ok": true'),
        ([], "Hola, mundo!"),
    ],
)
def test_flags_cli(monkeypatch, capsys, flags, esperado):
    """Todas las vistas de la CLI responden sobre un programa válido."""
    rc, out = _cli(monkeypatch, capsys, str(PRUEBAS / "hola_mundo.inv"), *flags)
    assert rc == 0, out
    assert esperado in out


def test_uml_cli(monkeypatch, capsys):
    """--uml mermaid sobre un programa con clases."""
    rc, out = _cli(monkeypatch, capsys, str(PRUEBAS / "arbol_binario.inv"), "--uml", "mermaid")
    assert rc == 0 and out.startswith("classDiagram")


def test_step_con_error_no_revienta(tmp_path, monkeypatch, capsys):
    """INV-1022: --step hacía `e.formato_oficial()` sobre un str (AttributeError)."""
    prog = tmp_path / "mal.inv"
    prog.write_text("void main() { int x = 5 @ 3; }", encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, str(prog), "--step")
    assert rc == 1
    assert "ERRORES LÉXICOS" in out and "IL-LEX-002" in out


def test_ejecucion_muestra_advertencias_de_tipos(tmp_path, monkeypatch, capsys):
    """INV-1022: las advertencias del verificador de tipos no se mostraban al ejecutar."""
    codigo = "int f() { retornar 1; } void main() { f(); imprimir(1); }"
    prog = tmp_path / "w.inv"
    prog.write_text(codigo, encoding="utf-8")
    esperadas = analizar_fuente(codigo).errores.obtener_advertencias()
    rc, out = _cli(monkeypatch, capsys, str(prog))
    assert rc == 0
    for advertencia in esperadas:
        assert advertencia.split("— ")[-1] in out


@pytest.mark.parametrize(
    ("codigo", "titulo"),
    [
        ("void main() { int x = 5 @ 3; }", "ERRORES LÉXICOS"),
        ("void main() { int x = ; }", "ERRORES SINTÁCTICOS"),
        ("void main() { imprimir(z); }", "ERRORES SEMÁNTICOS"),
        ('void main() { int x = "a"; }', "ERRORES DE TIPOS"),
        ("void main() { int x = 0; imprimir(5 / x); }", "ERRORES DE EJECUCIÓN"),
    ],
)
def test_errores_por_fase(tmp_path, monkeypatch, capsys, codigo, titulo):
    """Cada fase reporta su título y el diagnóstico oficial con caret."""
    prog = tmp_path / "p.inv"
    prog.write_text(codigo, encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, str(prog))
    assert rc == 1 and titulo in out and "^" in out
    rc, out = _cli(monkeypatch, capsys, str(prog), "--ir")
    if titulo != "ERRORES DE EJECUCIÓN":
        assert rc == 1 and titulo in out


def test_herramienta_con_error_devuelve_1(tmp_path, monkeypatch, capsys):
    prog = tmp_path / "p.inv"
    prog.write_text("void main() { imprimir(z); }", encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, str(prog), "--complejidad")
    assert rc == 1 and "IL-SEM-003" in out


def test_ir_no_disponible_para_poo(monkeypatch, capsys):
    rc, out = _cli(monkeypatch, capsys, str(PRUEBAS / "arbol_binario.inv"), "--ir")
    assert rc == 1 and "NO DISPONIBLE" in out
    assert not api.ssa((PRUEBAS / "arbol_binario.inv").read_text(encoding="utf-8")).ok


def test_metrics_incluye_alertas_de_presupuesto(monkeypatch, capsys):
    """INV-1026: --metrics adjunta las alertas de budgets.py y el run_id."""
    rc, out = _cli(monkeypatch, capsys, str(PRUEBAS / "hola_mundo.inv"), "--metrics")
    datos = json.loads(out)
    assert rc == 0 and datos["ok"]
    assert datos["alertas"][0]["nivel"] in ("INFO", "WARN", "CRIT")
    assert len(datos["run_id"]) == 12


def test_sandbox_pasa_la_entrada(tmp_path, monkeypatch, capsys):
    """INV-1022: `--sandbox` descartaba la entrada simulada."""
    prog = tmp_path / "eco.inv"
    prog.write_text("void main() { int x; leer(x); imprimir(x * 3); }", encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, str(prog), "7", "--sandbox")
    assert rc == 0 and "21" in out


@pytest.mark.parametrize(
    "args",
    [["--version"], ["--help"], [], ["--ast"], ["noexiste.inv"], ["--modo-raro", "x.inv"]],
)
def test_cli_casos_borde(monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["inveniolang", *args])
    rc = cli.main()
    out = capsys.readouterr().out
    assert rc in (0, 1, 2)
    if args == ["--help"]:
        assert "--complejidad" in out and "--ssa" in out


def test_leer_fuente_rechaza_entradas_invalidas(tmp_path):
    from inveniolang.errors import ErrorManager

    assert cli.leer_fuente("") == (None, 1)
    assert cli.leer_fuente("x" * 5000) == (None, 1)
    binario = tmp_path / "b.inv"
    binario.write_bytes(b"\xff\xfe\x00")
    em = ErrorManager()
    assert cli.leer_fuente(str(binario), em) == (None, 1)
    assert "IL-LEX-001" in em.obtener_reportes()[0]
    assert cli.leer_fuente(str(tmp_path)) == (None, 1)  # directorio: OSError


# ---------------------------------------------------------------- api
def test_run_id_de_api_es_el_de_los_logs():
    """INV-1022: api.ejecutar devolvía un run_id distinto del registrado."""
    r = api.ejecutar("void main() { imprimir(1); }")
    assert r.run_id == get_current_run()["run_id"]


def test_api_tokens_y_aislado_con_errores():
    assert api.tokens_de("void main() { int x = 5 @ 3; }").ok is False
    assert api.tokens_de("void main() { }").ok
    malo = api.ejecutar_aislado("void main() { int x = 5 @ 3; }")
    assert not malo.ok and "IL-LEX-002" in malo.errores[0]
    assert not api.formatear("@@").ok
    with pytest.raises(ValueError):
        api.uml("void main() { }", formato="png")  # INV-3212: svg ya es válido


# ---------------------------------------------------------------- formatter
def test_formateador_no_toca_cadenas_ni_tokens():
    """INV-1009: el formateador anterior convertía "a=b" en "a = b" dentro de cadenas."""
    codigo = 'void main(){\nimprimir("a=b{");   \n\n\n  /* x\n   y */\n}'
    salida = formatear(codigo)
    assert 'imprimir("a=b{");' in salida
    assert "\n\n\n" not in salida
    assert formatear(salida) == salida
    for prog in sorted(PRUEBAS.glob("*.inv")):
        fuente = prog.read_text(encoding="utf-8")
        a = [t[:2] for t in analizar_fuente(fuente, hasta="lexer").tokens]
        b = [t[:2] for t in analizar_fuente(formatear(fuente), hasta="lexer").tokens]
        assert a == b, prog.name
    assert formatear("") == ""


# ---------------------------------------------------------------- gramática
def test_validador_de_gramatica_usa_la_tabla_lalr_real(capsys):
    """INV-1017: FOLLOW antes era siempre vacío y los conflictos se buscaban por texto."""
    from inveniolang import grammar_validator as gv

    informe = gv.validar_gramatica()
    assert informe.ok
    assert len(informe.shift_reduce) == sum(gv.BASELINE_SHIFT_REDUCE.values()) == 20
    assert informe.follow["programa"] == ["$end"]
    assert all(informe.follow[nt] for nt in informe.follow)
    assert gv.main() == 0 and '"estado": "OK"' in capsys.readouterr().out
    informe.shift_reduce.append((0, "OP_SUMA", "shift"))
    assert not informe.ok and informe.como_dict()["estado"] == "REVISAR"


def test_parser_ll1_coincide_con_lalr():
    from inveniolang import ll1

    ok, detalles = ll1.verificar_contra_lalr()
    assert ok and detalles


# ---------------------------------------------------------------- LSP
def _marco(msg: dict) -> bytes:
    cuerpo = json.dumps(msg).encode()
    return b"Content-Length: " + str(len(cuerpo)).encode() + b"\r\n\r\n" + cuerpo


def _respuestas(salida: bytes) -> list[dict]:
    return list(lsp.leer_mensajes(io.BytesIO(salida)))


def test_servidor_lsp_habla_protocolo_enmarcado():
    """INV-1023: main() leía JSON por líneas; los clientes LSP enmarcan con Content-Length."""
    entrada = io.BytesIO(
        _marco({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        + b"X-Basura: 1\r\n\r\n"
        + _marco(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {"uri": "a.inv", "text": "void main() {\n imprimir(z);\n}"}
                },
            }
        )
        + _marco(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": "a.inv"},
                    "contentChanges": [{"text": "void main() {\n imprimir(z);\n}"}],
                },
            }
        )
        + _marco(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": "a.inv"},
                    "position": {"line": 1, "character": 3},
                },
            }
        )
        + _marco(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/completion",
                "params": {
                    "textDocument": {"uri": "a.inv"},
                    "position": {"line": 1, "character": 4},
                },
            }
        )
        + _marco({"jsonrpc": "2.0", "id": 4, "method": "desconocido"})
        + b"Content-Length: 3\r\n\r\n{x}"
        + _marco({"jsonrpc": "2.0", "id": 5, "method": "shutdown"})
        + _marco({"jsonrpc": "2.0", "method": "exit"})
    )
    salida = io.BytesIO()
    assert lsp.main(entrada, salida) == 0
    resp = _respuestas(salida.getvalue())
    assert resp[0]["result"]["capabilities"]["completionProvider"] is not None
    assert resp[1]["params"]["diagnostics"][0]["code"] == "IL-SEM-003"
    assert resp[3]["result"]["contents"].startswith("[IL-SEM-003]")
    assert "L2:C" in resp[3]["result"]["contents"]
    assert {"label": "imprimir"} in resp[4]["result"]
    assert resp[5]["error"]["code"] == -32601
    assert resp[6]["result"] is None


def test_hover_sobre_codigo_escrito_y_fuera_de_rango():
    docs = {"a.inv": "// ver IL-SEM-003\nvoid main() { }"}
    r = lsp.manejar_mensaje(
        {
            "id": 1,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": "a.inv"}, "position": {"line": 0, "character": 9}},
        },
        docs,
    )
    assert "IL-SEM-003" in r[0]["result"]["contents"]
    fuera = lsp.manejar_mensaje(
        {
            "id": 2,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": "a.inv"}, "position": {"line": 9, "character": 0}},
        },
        docs,
    )
    assert fuera[0]["result"]["contents"] == ""
    assert lsp.manejar_mensaje({"method": "initialized"}, docs) == []
    assert lsp.hover_for("palabra") == ""


# ---------------------------------------------------------------- docente
def test_evaluacion_registra_en_lms_y_panel(tmp_path, monkeypatch, capsys):
    """INV-1024: nada registraba intentos; el panel siempre estaba vacío."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "doble.inv").write_text(
        "void main() { int x; leer(x); imprimir(x * 2); }", encoding="utf-8"
    )
    (tmp_path / "casos.json").write_text(
        json.dumps([{"entrada": ["4"], "esperado": "8"}, {"entrada": ["1"], "esperado": "3"}]),
        encoding="utf-8",
    )
    from inveniolang import evaluation, lms

    rc = evaluation.main(
        ["evaluar", "doble.inv", "casos.json", "--store", "aula.jsonl", "--actor", "a@b.cr"]
    )
    out = capsys.readouterr().out
    assert rc == 1 and "nota: 5.0 (1/2)" in out
    (tmp_path / "roto.inv").write_text("void main() { imprimir(z); }", encoding="utf-8")
    directo = evaluation.run_secure(
        "roto.inv",
        [{"entrada": [], "esperado": ""}],
        use_sandbox=False,
        store=lms.LMSStore("aula.jsonl"),
        actor="a02",
    )
    assert directo["nota"] == 0.0
    with open("aula.jsonl", "a", encoding="utf-8") as f:
        f.write("{corrupta\n")
    panel = lms.LMSStore("aula.jsonl").dashboard()
    assert panel["total_intentos"] == 2
    assert panel["heatmap"] == {"IL-SEM-003": 1}
    assert panel["sugerencia"] == "Refuerzo en IL-SEM-003"
    assert lms.main(["aula.jsonl"]) == 0
    assert "IL-SEM-003: 1" in capsys.readouterr().out
    assert "plagio_check" not in panel


def test_lms_en_memoria_y_vacio():
    from inveniolang.lms import LMSStore

    vacio = LMSStore(":memory:")
    assert vacio.dashboard()["sugerencia"] == "Sin datos"
    vacio.record("a01", "failed", "x.inv", {"errores": ["[IL-LEX-002] x"]})
    assert vacio.heatmap_errores() == {"IL-LEX-002": 1}
    assert LMSStore("no_existe.jsonl").dashboard()["total_intentos"] == 0


def test_plagio_cli(tmp_path, capsys):
    from inveniolang import evaluation

    (tmp_path / "a.inv").write_text("void main(){ int x=1; imprimir(x); }", encoding="utf-8")
    (tmp_path / "b.inv").write_text("void main(){ int y=1; imprimir(y); }", encoding="utf-8")
    assert evaluation.main(["plagio", str(tmp_path)]) == 0
    assert "similares: a.inv, b.inv" in capsys.readouterr().out
    (tmp_path / "b.inv").unlink()
    evaluation.main(["plagio", str(tmp_path)])
    assert "sin entregas similares" in capsys.readouterr().out


# ---------------------------------------------------------------- accesibilidad
def test_temas_cumplen_wcag_aa():
    """Los tres temas de la IDE pasan el contraste AA que promete ACCESSIBILITY.md."""
    from inveniolang.gui import TEMA_ALTO_CONTRASTE, TEMA_CLARO, TEMA_OSCURO

    for tema in (TEMA_ALTO_CONTRASTE, TEMA_CLARO, TEMA_OSCURO):
        assert validar_tema_accesible(tema) == []
    assert round(contraste_ratio("#000000", "#ffffff"), 1) == 21.0
    assert validar_tema_accesible({"texto": "#777777", "fondo": "#888888"})


def test_docstrings_de_ayuda_cargan():
    from inveniolang import docstrings

    assert "main" in docstrings._DOC_GUIA and docstrings.EJEMPLOS


# ---------------------------------------------------------------- integración i18n/módulos
def test_api_modulos_en_memoria_e_idioma():
    """La fachada api sirve `importar` desde memoria (CargadorMemoria) y respeta el idioma."""
    r = api.ejecutar(
        'importar "lib/mates";\nvoid main() { imprimir(doble(4)); }',
        ruta="main.inv",
        modulos={"lib/mates.inv": "entero doble(entero x) { retornar 2 * x; }"},
    )
    assert r.ok and r.salida == ("8",)
    falta = api.compilar('importar "nada";\nvoid main() { }', ruta="main.inv", modulos={})
    assert not falta.ok and "IL-MOD-001" in falta.errores[0]
    assert "Undeclared" in api.compilar("void main() { imprimir(z); }", idioma="en").errores[0]


def test_informes_salen_del_catalogo_i18n(monkeypatch, capsys):
    """Complejidad/efectos usan el catálogo único (claves COMP.*/EFE.*), no tablas propias."""
    from inveniolang.i18n import t

    rc, out = _cli(
        monkeypatch, capsys, str(PRUEBAS / "mergesort.inv"), "--complejidad", "--idioma", "en"
    )
    assert rc == 0 and t("COMP.bucle", "en", linea=7) in out
    rc, out = _cli(
        monkeypatch, capsys, str(PRUEBAS / "hola_mundo.inv"), "--efectos", "--idioma", "es"
    )
    assert rc == 0 and t("EFE.salida", "es") in out


def test_traducir_desde_la_cli(tmp_path, monkeypatch, capsys):
    rc, out = _cli(monkeypatch, capsys, "traducir", str(PRUEBAS / "hola_mundo.inv"), "--a", "en")
    assert rc == 0 and "print" in out
