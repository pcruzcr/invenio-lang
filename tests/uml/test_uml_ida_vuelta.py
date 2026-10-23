"""Ida y vuelta código → UML → código sobre todo el POO del currículo y la stdlib (INV-3206).

Para cada ejercicio de los niveles 8 a 12 (versiones es y en) y cada módulo
de la biblioteca estándar: el modelo sale del código, el esqueleto generado
en español y en inglés COMPILA y, al volver a analizarlo, produce clases con
la misma estructura (mismos miembros, firmas y relaciones). También se
comprueba la ida y vuelta por PlantUML y por JSON.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from inveniolang import api, uml
from inveniolang.modulos import RAIZ_STDLIB
from inveniolang.uml.reglas import normalizar

RAIZ = Path(__file__).resolve().parents[2]
CLASE = ("clase ", "class ", "interfaz ", "interface ", "enumeracion ", "enum ")


def _casos():
    casos = []
    for idioma, prefijo in (("es", "nivel"), ("en", "level")):
        for nivel in range(8, 13):
            for ruta in sorted(
                (RAIZ / "curriculum" / idioma / f"{prefijo}{nivel:02d}").glob("*.inv")
            ):
                texto = ruta.read_text(encoding="utf-8")
                if any(
                    linea.lstrip().startswith(CLASE) or linea.startswith("abstract")
                    for linea in texto.splitlines()
                ):
                    casos.append(pytest.param(texto, str(ruta), id=f"{idioma}-{ruta.stem}"))
    # Los módulos de algoritmos solo tienen subrutinas: no hay diagrama de clases.
    for ruta in sorted(Path(RAIZ_STDLIB).glob("*/*.inv")):
        if ruta.parent.name not in ("estructuras", "structures"):
            continue
        modulo = f"{ruta.parent.name}/{ruta.stem}"
        ingles = ruta.parent.name in ("algorithms", "structures")
        texto = (
            f'import "{modulo}";\nvoid main() {{ }}\n'
            if ingles
            else f'importar "{modulo}";\nvacio main() {{ }}\n'
        )
        casos.append(pytest.param(texto, str(Path(RAIZ_STDLIB) / "x.inv"), id=f"stdlib-{modulo}"))
    return casos


CASOS = _casos()


def _modelo(codigo: str, ruta_fuente: str | None = None) -> uml.DiagramaClases:
    r = api.uml(codigo, formato="json", ruta_fuente=ruta_fuente)
    assert r.ok, r.errores
    return uml.desde_json(r.salida[0])


def _estructura(m: uml.DiagramaClases):
    """Lo que debe conservarse: clasificadores (sin su módulo de origen) y relaciones."""
    return (
        {c.nombre: replace(c, modulo=None) for c in m.clasificadores},
        sorted(m.relaciones, key=repr),
    )


def test_hay_casos_de_todos_los_niveles():
    ids = [c.id for c in CASOS]
    assert len([i for i in ids if i.startswith("es-")]) == len(
        [i for i in ids if i.startswith("en-")]
    )
    assert len([i for i in ids if i.startswith("es-")]) >= 35
    assert len([i for i in ids if i.startswith("stdlib-")]) == 14


@pytest.mark.parametrize(("codigo", "ruta"), CASOS)
def test_codigo_uml_codigo(codigo, ruta):
    original = _modelo(codigo, ruta)
    assert original.clasificadores
    assert normalizar(original) == original
    for idioma in ("es", "en"):
        r = api.codigo_desde_uml(original, idioma)
        assert r.ok, (idioma, r.errores)
        assert _estructura(_modelo(r.salida[0])) == _estructura(original), idioma
    por_plantuml = uml.leer_plantuml(uml.exportar(original, "plantuml"))
    assert _estructura(por_plantuml) == _estructura(original)
    assert uml.desde_json(uml.a_json(original)) == original
