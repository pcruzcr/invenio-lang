"""INV-4404: ``--step`` muestra el archivo y la línea de código de cada paso.

Antes cada paso decía solo ``L3``: sin archivo (con ``importar`` no se sabía
si la línea 3 era del programa o del módulo) y sin el código ejecutado.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import cli  # noqa: E402

MODULO = "int doble(int x) {\n    int r = x * 2;\n    return r;\n}\n"
PROGRAMA = 'importar "util";\nvoid main() {\n    int a = 4;\n    imprimir(doble(a));\n}\n'


def _step(monkeypatch, capsys, *args: str) -> tuple[int, list[str]]:
    monkeypatch.setattr(sys, "argv", ["inveniolang", *args, "--step"])
    rc = cli.main()
    return rc, capsys.readouterr().out.splitlines()


def test_step_muestra_archivo_y_codigo_incluso_en_modulos(tmp_path, monkeypatch, capsys):
    (tmp_path / "util.inv").write_text(MODULO, encoding="utf-8")
    prog = tmp_path / "prog.inv"
    prog.write_text(PROGRAMA, encoding="utf-8")
    rc, lineas = _step(monkeypatch, capsys, str(prog))
    assert rc == 0, lineas
    pasos = [(a, b) for a, b in zip(lineas, lineas[1:], strict=False) if a.startswith("[")]
    assert [p[0].split("]")[1].split()[0] for p in pasos] == [
        "prog.inv:3",
        "prog.inv:4",
        "util.inv:2",
        "util.inv:3",
    ]
    assert [p[1] for p in pasos] == [
        "      | int a = 4;",
        "      | imprimir(doble(a));",
        "      | int r = x * 2;",
        "      | return r;",
    ]


def test_step_en_metodos_de_clase(tmp_path, monkeypatch, capsys):
    prog = tmp_path / "c.inv"
    prog.write_text(
        "clase A {\n    publico entero v;\n    A() { este.v = 1; }\n"
        "    publico entero doble() { retornar este.v * 2; }\n}\n"
        "vacio main() {\n    A a = nuevo A();\n    imprimir(a.doble());\n}\n",
        encoding="utf-8",
    )
    rc, lineas = _step(monkeypatch, capsys, str(prog))
    assert rc == 0
    texto = "\n".join(lineas)
    assert "c.inv:3 " in texto and "| A() { este.v = 1; }" in texto
    assert "c.inv:4 " in texto and "| publico entero doble() { retornar este.v * 2; }" in texto
