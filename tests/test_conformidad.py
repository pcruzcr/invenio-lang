"""La batería de conformidad (391 casos + 17 de InvenioLang 11) también corre bajo pytest.

INV-1032: ``pruebas/conformidad.py`` solo se ejecutaba como script, así que
su recorrido por intérprete, IR, código objetivo, diagramas de flujo y el
parser LL(1) no contaba para ``pytest --cov``. Cada grupo es ahora un caso.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

_spec = importlib.util.spec_from_file_location("conformidad", RAIZ / "pruebas" / "conformidad.py")
assert _spec is not None and _spec.loader is not None
conformidad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conformidad)


@pytest.mark.parametrize("grupo", list(conformidad.GRUPOS))
def test_grupo_de_conformidad(grupo, monkeypatch):
    """Cada grupo de la especificación pasa completo."""
    monkeypatch.chdir(RAIZ)
    res = conformidad.Resultados()
    conformidad.GRUPOS[grupo](res, False)
    assert res.fallos == []
    assert res.ok == res.total > 0
