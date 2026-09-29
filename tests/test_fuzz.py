# test_fuzz.py — Fuzzing determinista, resiliente y reproducible
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang import api


def test_fuzz_no_cuelga_interprete():
    """Entradas mutadas nunca deben lanzar excepción Python."""
    rnd = random.Random(20260929)  # noqa: S311 - semilla determinista para reproducibilidad
    alfabeto = 'intx=;{}()"+ \n@#si'
    base = "void main() { int x = 1; imprimir(x); }"
    for _ in range(60):
        pos = rnd.randrange(len(base))
        ch = rnd.choice(alfabeto)
        mut = base[:pos] + ch + base[pos:]
        r = api.ejecutar(mut)
        assert isinstance(r.salida, tuple)
        assert isinstance(r.errores, tuple)
        # Determinista: repetir da mismo resultado
        r2 = api.ejecutar(mut)
        assert (r.ok, r.salida, r.errores) == (r2.ok, r2.salida, r2.errores)


def test_fuzz_lexico_seguro():
    """Caracteres ilegales producen IL-LEX, no traceback."""
    for cod in [
        "void main() { int x = 1 @ 2; }",
        'void main() { string s = "sin cerrar; }',
        "void main() { int 1x = 5; }",
    ]:
        r = api.ejecutar(cod)
        assert not r.ok
        assert any(e.startswith("[IL-") for e in r.errores)
