"""CLI ``inveniolang trazar`` (INV-2005): JSON, texto, límites, idioma y errores."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import cli  # noqa: E402
from inveniolang.visualizacion.modelo import desde_json  # noqa: E402

BURBUJA_ES = RAIZ / "curriculum" / "es" / "nivel05" / "01_burbuja.inv"
LECTURA_EN = RAIZ / "curriculum" / "en" / "level01" / "08_reading_input.inv"


def _cli(monkeypatch, capsys, *args: str) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["inveniolang", *args])
    rc = cli.main()
    return rc, capsys.readouterr().out


def test_trazar_json_se_puede_leer(monkeypatch, capsys, tmp_path):
    destino = tmp_path / "traza.json"
    rc, out = _cli(monkeypatch, capsys, "trazar", str(BURBUJA_ES), "--json", str(destino))
    assert rc == 0 and "traza.json" in out
    traza = desde_json(destino.read_text(encoding="utf-8"))
    assert traza.idioma == "es" and traza.pasos and not traza.truncada
    assert "TRAZA" not in out  # con --json solo, no se imprime el texto


def test_trazar_texto_por_defecto_y_max_pasos(monkeypatch, capsys):
    rc, out = _cli(monkeypatch, capsys, "trazar", str(BURBUJA_ES), "--max-pasos", "12")
    assert rc == 0
    assert "=== TRAZA: 01_burbuja.inv · 12 pasos ===" in out
    # INV-2009: --texto usa la descripción accesible de render_texto.describir.
    assert "Paso 12, línea" in out and "Paso 13" not in out
    assert "Se escribe a[0]" in out and "truncada" in out


def test_trace_en_ingles_con_entrada(monkeypatch, capsys, tmp_path):
    entrada = LECTURA_EN.with_suffix(".entrada").read_text(encoding="utf-8").split()
    destino = tmp_path / "t.json"
    rc, out = _cli(
        monkeypatch, capsys, "trace", str(LECTURA_EN), *entrada, "--texto", "--json", str(destino)
    )
    assert rc == 0 and "=== TRACE:" in out and "Program output:" in out
    esperado = LECTURA_EN.with_suffix(".expected").read_text(encoding="utf-8")
    assert "".join(desde_json(destino.read_text(encoding="utf-8")).salida) == esperado


def test_trazar_con_error_sale_con_1(monkeypatch, capsys, tmp_path):
    prog = tmp_path / "e.inv"
    prog.write_text("void main() {\n    int [2] a;\n    a[4] = 1;\n}\n", encoding="utf-8")
    rc, out = _cli(monkeypatch, capsys, "trazar", str(prog), "--idioma", "en")
    assert rc == 1 and "Error:" in out and "IL-EJE-050" in out and "e.inv:3" in out


def test_trazar_rechaza_max_pasos_fuera_de_rango(monkeypatch, capsys):
    rc, out = _cli(monkeypatch, capsys, "trazar", str(BURBUJA_ES), "--max-pasos", "0")
    assert rc == 2 and "--max-pasos" in out


def test_trazar_json_en_ruta_imposible(monkeypatch, capsys, tmp_path):
    destino = tmp_path / "no" / "existe" / "t.json"
    rc, out = _cli(monkeypatch, capsys, "trazar", str(BURBUJA_ES), "--json", str(destino))
    assert rc == 1 and "No se pudo escribir" in out


def test_ayuda_menciona_trazar(monkeypatch, capsys):
    rc, out = _cli(monkeypatch, capsys, "--help")
    assert rc == 0 and "trazar <archivo.inv>" in out


def test_trazar_html_y_svg_de_un_paso(monkeypatch, capsys, tmp_path):
    """INV-2009: --html escribe el reproductor y --svg-paso N el dibujo del paso N."""
    import xml.etree.ElementTree as ET

    html, svg = tmp_path / "t.html", tmp_path / "p.svg"
    rc, out = _cli(
        monkeypatch,
        capsys,
        "trazar",
        str(BURBUJA_ES),
        "--max-pasos",
        "40",
        "--html",
        str(html),
        "--svg-paso",
        "11",
        str(svg),
    )
    assert rc == 0 and "t.html" in out and "p.svg" in out and "Paso 1," not in out
    contenido = html.read_text(encoding="utf-8")
    assert contenido.lower().startswith("<!doctype html>") and "http://" not in contenido.replace(
        "http://www.w3.org", ""
    )
    raiz = ET.fromstring(svg.read_text(encoding="utf-8"))
    assert raiz.tag.endswith("svg")


def test_trazar_svg_paso_inexistente(monkeypatch, capsys, tmp_path):
    rc, out = _cli(
        monkeypatch,
        capsys,
        "trazar",
        str(BURBUJA_ES),
        "--max-pasos",
        "5",
        "--svg-paso",
        "9",
        str(tmp_path / "p.svg"),
    )
    assert rc == 2 and "el paso 9 no existe" in out
    rc, out = _cli(monkeypatch, capsys, "trazar", str(BURBUJA_ES), "--svg-paso", "x", "p.svg")
    assert rc == 2
