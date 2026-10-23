"""INV-5008 / INV-5009 / INV-5010: recursión de cola, tiempo total y ``config``.

* La eliminación de recursión de cola ya no toma los ``param`` de una
  llamada anidada en un argumento (``f(n - 1, g(n, acc))``): antes la máquina
  TAC optimizada daba 12 donde el intérprete daba 30.
* El límite de tiempo vigila el programa entero: tres ciclos anidados de
  1999 vueltas o una recursión sin ciclos ya no corren sin límite.
* ``api.ejecutar(config=...)`` aplica los límites pedidos; antes se ignoraban.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import api  # noqa: E402
from inveniolang.config import DEFAULT_CONFIG  # noqa: E402

COLA_ANIDADA = """entero g(entero a, entero b) { retornar a * 10 + b; }
entero f(entero n, entero acc) {
    si (n == 0) { retornar acc; }
    retornar f(n - 1, g(n, acc));
}
vacio main() { imprimir(f(2, 0)); }
"""

COLA_SIMPLE = """entero suma(entero n, entero acc) {
    si (n == 0) { retornar acc; }
    retornar suma(n - 1, acc + n);
}
vacio main() { imprimir(suma(100, 0)); }
"""


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "inveniolang.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=RAIZ,
        timeout=120,
    )


@pytest.mark.parametrize("programa,esperado", [(COLA_ANIDADA, "30"), (COLA_SIMPLE, "5050")])
def test_los_tres_motores_coinciden_en_recursion_de_cola(tmp_path, programa, esperado):
    fuente = tmp_path / "p.inv"
    fuente.write_text(programa, encoding="utf-8")
    for modo in ([], ["--run-ir"], ["--run-ir-opt"]):
        r = _cli(str(fuente), *modo)
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.strip() == esperado, modo


def test_la_recursion_de_cola_simple_se_sigue_optimizando(tmp_path):
    fuente = tmp_path / "p.inv"
    fuente.write_text(COLA_SIMPLE, encoding="utf-8")
    assert "__tco_suma" in _cli(str(fuente), "--ir-opt").stdout


TRES_CICLOS = (
    "vacio main() { entero s = 0; para (entero i = 0; i < 1999; i++) {"
    " para (entero j = 0; j < 1999; j++) { para (entero k = 0; k < 1999; k++) {"
    " s = s + 1; } } } imprimir(s); }"
)
RECURSION_SIN_CICLOS = (
    "entero f(entero n) { si (n == 0) { retornar 1; } retornar f(n - 1) + f(n - 1); }\n"
    "vacio main() { imprimir(f(40)); }"
)


@pytest.mark.parametrize(
    "programa", [TRES_CICLOS, RECURSION_SIN_CICLOS], ids=["ciclos", "recursion"]
)
def test_el_limite_de_tiempo_vigila_el_programa_entero(programa):
    cfg = dataclasses.replace(DEFAULT_CONFIG, max_segundos=1.0)
    inicio = time.monotonic()
    r = api.ejecutar(programa, config=cfg)
    transcurrido = time.monotonic() - inicio
    assert not r.ok and "[IL-EJE-030]" in r.errores[0]
    assert transcurrido < 10, transcurrido  # antes: sin límite


def test_config_limita_iteraciones_y_recursion():
    ciclo = "vacio main() { entero i = 0; mientras (i < 50) { i++; } imprimir(i); }"
    assert api.ejecutar(ciclo).salida == ("50",)
    cfg = dataclasses.replace(DEFAULT_CONFIG, max_iteraciones=10)
    assert "[IL-EJE-030]" in api.ejecutar(ciclo, config=cfg).errores[0]

    recursion = (
        "entero f(entero n) { si (n == 0) { retornar 0; } retornar f(n - 1); }\n"
        "vacio main() { imprimir(f(30)); }"
    )
    assert api.ejecutar(recursion).salida == ("0",)
    cfg = dataclasses.replace(DEFAULT_CONFIG, max_recursion=20)
    assert "[IL-EJE-040]" in api.ejecutar(recursion, config=cfg).errores[0]
