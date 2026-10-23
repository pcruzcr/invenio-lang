"""Aislamiento entre pruebas del estado global de idioma.

La CLI fija el idioma del PROCESO con ``--idioma`` (correcto para un proceso
que atiende un solo comando). Las pruebas llaman a ``cli.main()`` dentro del
mismo proceso, así que sin esta restauración una prueba con ``--idioma en``
dejaba en inglés los diagnósticos de todas las siguientes.
"""

import pytest

from inveniolang import i18n


@pytest.fixture(autouse=True)
def _idioma_aislado():
    previo = i18n._idioma_proceso
    yield
    i18n.establecer_idioma(previo)
