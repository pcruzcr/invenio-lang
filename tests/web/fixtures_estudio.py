"""Fixtures del estudio web generadas con el compilador real (INV-4231).

``web/estudio/pruebas/fixtures/bloques.json`` es lo que el puente devuelve
para un programa con clases, ciclos, decisiones, huecos y listas en línea:
las pruebas de Node del lienzo (``pruebas/bloques.test.mjs``) trabajan sobre
esa vista real y no sobre una inventada. ``test_contrato_estudio.py``
comprueba que el archivo sigue siendo idéntico a lo que genera el puente, así
que un cambio del contrato de ``inveniolang.bloques`` no puede pasar sin que
se actualice. Uso: ``python tests/web/fixtures_estudio.py`` lo reescribe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DESTINO = RAIZ / "web" / "estudio" / "pruebas" / "fixtures" / "bloques.json"

PROGRAMA = """clase Contador {
    privado entero n;
    Contador(entero inicio) {
        este.n = inicio;
    }
    publico entero valor() {
        retornar este.n;
    }
}

entero doble(entero x) {
    retornar x * 2;
}

vacio main() {
    Contador c = nuevo Contador(1);
    para (entero i = 0; i < 3; i++) {
        si (i % 2 == 0) {
            imprimir(doble(i));
        } sino {
            romper;
        }
    }
    imprimir(c.valor());
}
"""


def generar() -> str:
    """Texto JSON de la fixture (determinista)."""
    from inveniolang.web import llamar

    datos = json.loads(
        llamar(json.dumps({"metodo": "bloques", "args": {"codigo": PROGRAMA, "idioma": "es"}}))
    )["datos"]
    fixture = {
        "programa": PROGRAMA,
        "modelo": datos["modelo"],
        "vista": datos["vista"],
        "paleta": datos["paleta"],
        "problemas": datos["problemas"],
    }
    return json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    DESTINO.write_text(generar(), encoding="utf-8")
    print(DESTINO)
