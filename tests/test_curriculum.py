"""Pruebas del currículo bilingüe y de su ejecutor (INV-1200..INV-1204).

Antes de INV-1200 el currículo tenía dos niveles reales en español, stubs
idénticos en los niveles 3 y 10 y un ejecutor que siempre salía con 0: todas
estas pruebas fallaban (no hay `es/`/`en/`, `runner.main` no existía y el
ejecutor aceptaba salidas pegadas). Ahora verifican:

* que TODO el currículo (las dos versiones de cada ejercicio) se ejecuta con
  el intérprete real y produce exactamente su `.expected`;
* que la versión con palabras clave en español y la versión en inglés de
  cada ejercicio producen la misma salida;
* la estructura: >= 10 niveles, >= 8 ejercicios reales por nivel desde el 3,
  metadatos completos en el idioma correcto, sin plantillas repetidas;
* el ejecutor: código de salida, idioma de los mensajes, entrada simulada,
  pareja faltante y compatibilidad con `runner.py nivel1`.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import re
import sys
from functools import cache

import pytest

RAIZ_REPO = pathlib.Path(__file__).resolve().parent.parent
CURRICULO = RAIZ_REPO / "curriculum"

_spec = importlib.util.spec_from_file_location("curriculum_runner", CURRICULO / "runner.py")
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner  # dataclasses resuelve anotaciones vía sys.modules
assert _spec.loader is not None
_spec.loader.exec_module(runner)

EJERCICIOS, PROBLEMAS = runner.descubrir(CURRICULO)
IDS = sorted({e.id for e in EJERCICIOS})


@cache
def _resultado(ruta: str):
    """Ejecuta cada versión una sola vez aunque varias pruebas la usen."""
    ej = next(e for e in EJERCICIOS if str(e.inv) == ruta)
    return runner.ejecutar(ej)


def _cuerpo(inv: pathlib.Path) -> str:
    """Programa sin la cabecera de comentarios generada (título/objetivos)."""
    lineas = inv.read_text(encoding="utf-8").split("\n")
    fin = lineas.index("//")
    return "\n".join(lineas[fin + 1 :])


# ---------------------------------------------------------------- estructura


def test_estructura_sin_problemas():
    assert PROBLEMAS == []


def test_al_menos_diez_niveles_en_ambos_idiomas():
    for idioma in runner.IDIOMAS:
        niveles = {e.nivel for e in EJERCICIOS if e.idioma == idioma}
        assert len(niveles) >= 10, idioma
        assert niveles == set(range(1, max(niveles) + 1)), "niveles sin huecos"


def test_minimo_ocho_ejercicios_por_nivel_desde_el_tercero():
    for idioma in runner.IDIOMAS:
        por_nivel: dict[int, int] = {}
        for e in EJERCICIOS:
            if e.idioma == idioma:
                por_nivel[e.nivel] = por_nivel.get(e.nivel, 0) + 1
        for nivel, n in por_nivel.items():
            assert n >= 8, (idioma, nivel, n)


def test_cada_ejercicio_existe_en_es_y_en():
    for ident in IDS:
        idiomas = sorted(e.idioma for e in EJERCICIOS if e.id == ident)
        assert idiomas == ["en", "es"], ident


def test_las_versiones_usan_palabras_clave_de_su_idioma():
    # Una versión "en" que conservara `mientras`/`imprimir` no enseñaría la
    # sintaxis inglesa; y viceversa.
    es_kw = re.compile(r"\b(imprimir|mientras|retornar|entero|vacio)\b")
    en_kw = re.compile(r"\b(print|while|return|int|void)\b")
    for e in EJERCICIOS:
        codigo = "\n".join(
            ln for ln in _cuerpo(e.inv).split("\n") if not ln.lstrip().startswith("//")
        )
        codigo = re.sub(r'"(?:\\.|[^"\\])*"|//.*', "", codigo)
        if e.idioma == "es":
            assert not en_kw.search(codigo), e.inv
            assert es_kw.search(codigo), e.inv
        else:
            assert not es_kw.search(codigo), e.inv
            assert en_kw.search(codigo), e.inv


def test_metadatos_completos_y_en_su_idioma():
    for e in EJERCICIOS:
        m = e.meta
        assert m["idioma"] == e.idioma, e.inv
        assert m["nivel"] == e.nivel and m["numero"] == e.numero, e.inv
        assert len(m["enunciado"]) >= 40, e.inv
        assert len(m["objetivos"]) >= 2 or e.nivel == 1, e.inv
        assert len(m["pistas"]) >= 3, f"pistas graduadas: {e.inv}"
        assert all(p.strip() for p in m["pistas"] + m["objetivos"] + m["conceptos"]), e.inv


def test_niveles_tienen_descripcion_bilingue():
    for idioma, prefijo in runner.PREFIJO_NIVEL.items():
        for carpeta in sorted((CURRICULO / idioma).iterdir()):
            meta = json.loads((carpeta / "nivel.json").read_text(encoding="utf-8"))
            assert carpeta.name.startswith(prefijo)
            assert meta["idioma"] == idioma and meta["titulo"] and meta["temas"], carpeta


def test_sin_plantillas_repetidas():
    for idioma in runner.IDIOMAS:
        propios = [e for e in EJERCICIOS if e.idioma == idioma]
        cuerpos = [_cuerpo(e.inv) for e in propios]
        titulos = [e.meta["titulo"] for e in propios]
        esperados = [e.esperado.read_text(encoding="utf-8") for e in propios]
        assert len(set(cuerpos)) == len(cuerpos), "programas duplicados"
        assert len(set(titulos)) == len(titulos), "títulos duplicados"
        assert len(set(esperados)) == len(esperados), "salidas duplicadas"


def test_soluciones_comentadas_y_esperados_no_triviales():
    for e in EJERCICIOS:
        assert "//" in _cuerpo(e.inv), f"solución sin comentarios: {e.inv}"
        esperado = e.esperado.read_text(encoding="utf-8")
        assert len(esperado.split()) >= 2 or len(esperado.strip()) >= 6, e.esperado


# ------------------------------------------------------- currículo completo


@pytest.mark.parametrize(
    "ruta", [str(e.inv) for e in EJERCICIOS], ids=[f"{e.id}-{e.idioma}" for e in EJERCICIOS]
)
def test_todo_el_curriculo_produce_su_salida_esperada(ruta):
    r = _resultado(ruta)
    assert r.salida is not None, r.errores
    assert runner.normalizar(r.salida) == runner.normalizar(r.esperado)


@pytest.mark.parametrize("ident", IDS)
def test_es_y_en_producen_la_misma_salida(ident):
    salidas = {e.idioma: _resultado(str(e.inv)).salida for e in EJERCICIOS if e.id == ident}
    assert salidas["es"] is not None and salidas["es"] == salidas["en"]
    pares = [e for e in EJERCICIOS if e.id == ident]
    textos = {e.esperado.read_text(encoding="utf-8") for e in pares}
    assert len(textos) == 1, "los .expected de es y en deben ser idénticos"


# --------------------------------------------------------------- el ejecutor


def _mini_curriculo(raiz: pathlib.Path, esperado_en: str = "3\n", entrada: str | None = None):
    """Currículo mínimo de un ejercicio en dos idiomas para probar el ejecutor."""
    versiones = {
        "es": (
            "nivel01",
            "01_suma",
            'vacio main() { entero a = 1; entero b = 2; imprimir(a + b); imprimir("\\n"); }',
        ),
        "en": (
            "level01",
            "01_sum",
            'void main() { int a = 1; int b = 2; print(a + b); print("\\n"); }',
        ),
    }
    if entrada is not None:
        versiones = {
            "es": (
                "nivel01",
                "01_suma",
                'vacio main() { entero a; leer(a); imprimir(a + 2); imprimir("\\n"); }',
            ),
            "en": (
                "level01",
                "01_sum",
                'void main() { int a; read(a); print(a + 2); print("\\n"); }',
            ),
        }
    textos = {
        "es": {
            "titulo": "Sumar",
            "enunciado": "Suma dos números enteros y muestra el resultado.",
            "pista": "Usa el operador +.",
        },
        "en": {
            "titulo": "Adding",
            "enunciado": "Add two integers and show the result on its own line.",
            "pista": "Use the + operator.",
        },
    }
    for idioma, (carpeta, base, codigo) in versiones.items():
        d = raiz / idioma / carpeta
        d.mkdir(parents=True)
        (d / f"{base}.inv").write_text(codigo, encoding="utf-8")
        (d / f"{base}.expected").write_text(
            "3\n" if idioma == "es" else esperado_en, encoding="utf-8"
        )
        if entrada is not None:
            (d / f"{base}.entrada").write_text(entrada, encoding="utf-8")
        t = textos[idioma]
        meta = {
            "id": "N01-E01",
            "nivel": 1,
            "numero": 1,
            "idioma": idioma,
            "titulo": t["titulo"],
            "enunciado": t["enunciado"],
            "objetivos": [t["titulo"]],
            "pistas": [t["pista"], t["pista"] + "!", t["pista"] + "!!"],
            "conceptos": ["+"],
        }
        (d / f"{base}.json").write_text(json.dumps(meta), encoding="utf-8")


def _correr(*args) -> tuple[int, str]:
    out = io.StringIO()
    codigo = runner.main(list(args), out=out)
    return codigo, out.getvalue()


def test_runner_pasa_con_codigo_cero(tmp_path):
    _mini_curriculo(tmp_path)
    codigo, salida = _correr("--raiz", str(tmp_path))
    assert codigo == 0, salida
    assert "TOTAL: 2/2" in salida


def test_runner_falla_con_codigo_distinto_de_cero_y_muestra_pistas_en_ingles(tmp_path):
    _mini_curriculo(tmp_path, esperado_en="4\n")
    codigo, salida = _correr("--raiz", str(tmp_path), "--idioma", "en", "--pistas", "2")
    assert codigo == 1
    assert "FAIL N01-E01 [en]" in salida
    assert "Statement: Add two integers" in salida
    assert "Hint 2: Use the + operator.!" in salida
    assert "Hint 3" not in salida  # pistas graduadas: solo las pedidas


def test_runner_muestra_enunciado_en_espanol(tmp_path):
    _mini_curriculo(tmp_path)
    codigo, salida = _correr("--raiz", str(tmp_path), "--enunciado", "--version", "en")
    assert codigo == 0
    assert "Enunciado: Suma dos números" in salida  # versión en, textos en es


def test_runner_no_acepta_salida_pegada(tmp_path):
    # El ejecutor viejo comparaba con strip(): "3" == "3\n\n" era OK, pero
    # también aceptaba cualquier salida que coincidiera tras recortar
    # espacios iniciales. Aquí un espacio inicial sí es una diferencia.
    _mini_curriculo(tmp_path, esperado_en=" 3\n")
    codigo, _ = _correr("--raiz", str(tmp_path))
    assert codigo == 1


def test_runner_detecta_es_y_en_distintos_aunque_cada_uno_cumpla(tmp_path):
    _mini_curriculo(tmp_path, esperado_en="3\n")
    en = tmp_path / "en" / "level01" / "01_sum"
    en.with_suffix(".inv").write_text('void main() { print("3 \\n"); }', encoding="utf-8")
    en.with_suffix(".expected").write_text("3 \n", encoding="utf-8")
    codigo, salida = _correr("--raiz", str(tmp_path))
    assert codigo == 1
    assert "las versiones es y en producen salidas distintas" in salida


def test_runner_usa_entrada_simulada_y_no_se_bloquea(tmp_path, monkeypatch):
    _mini_curriculo(tmp_path, entrada="1\n")
    codigo, salida = _correr("--raiz", str(tmp_path))
    assert codigo == 0, salida
    # Sin .entrada, `leer` no debe esperar teclado: falla limpio.
    for f in tmp_path.rglob("*.entrada"):
        f.unlink()

    class StdinProhibido(io.StringIO):
        def readline(self, *a):
            raise AssertionError("el ejecutor leyó de la entrada estándar real")

    monkeypatch.setattr(sys, "stdin", StdinProhibido())
    codigo, salida = _correr("--raiz", str(tmp_path))
    assert codigo == 1
    assert "IL-EJE-020" in salida


def test_runner_reporta_ejercicio_sin_pareja(tmp_path):
    _mini_curriculo(tmp_path)
    for f in (tmp_path / "en").rglob("*"):
        if f.is_file():
            f.unlink()
    codigo, salida = _correr("--raiz", str(tmp_path))
    assert codigo == 1
    assert "N01-E01 (en)" in salida
    # Pidiendo solo la versión es, el mismo currículo es válido.
    assert _correr("--raiz", str(tmp_path), "--version", "es")[0] == 0


def test_runner_acepta_nombres_de_nivel_heredados(tmp_path):
    _mini_curriculo(tmp_path)
    for nombre in ("nivel1", "level01", "1", "todos"):
        assert _correr("--raiz", str(tmp_path), nombre)[0] == 0, nombre
    assert _correr("--raiz", str(tmp_path), "nivel9")[0] == 2
    assert _correr("--raiz", str(tmp_path), "xyz")[0] == 2
