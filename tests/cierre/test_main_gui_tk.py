"""INV-5001: ``python main.py --gui-tk`` abre la GUI Tk.

El README documenta ``--gui-tk`` como opción propia, pero ``main.py`` solo
entraba en la rama de GUI con ``--gui``: con ``--gui-tk`` solo caía al CLI,
que la rechazaba como opción desconocida.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

import main as punto_entrada  # noqa: E402
from inveniolang import gui_tk  # noqa: E402


def test_gui_tk_solo_abre_la_gui_tk(monkeypatch):
    llamadas = []
    monkeypatch.setattr(gui_tk, "main", lambda: llamadas.append("tk"))
    monkeypatch.setattr(sys, "argv", ["main.py", "--gui-tk"])
    assert punto_entrada.main() == 0
    assert llamadas == ["tk"]
