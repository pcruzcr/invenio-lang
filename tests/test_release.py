# test_release.py — Puerta GA: política y artefactos
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang import api
from inveniolang.config import DEFAULT_CONFIG


def test_codigo_no_confiable_corre_aislado():
    """INV-1025: `policy.ejecutar_no_confiable` era un alias de `api.ejecutar_aislado`.

    La política de aula es usar la fachada aislada directamente (con entrada).
    """
    r = api.ejecutar_aislado(
        "void main() { int x; leer(x); imprimir(x + 1); }", timeout=10, entrada=("8",)
    )
    assert r.ok
    assert "9" in "".join(r.salida)


def test_limites_para_acta():
    """Límites serializables para examen (antes `policy.limites_aula`)."""
    d = DEFAULT_CONFIG.como_dict()
    assert d["max_recursion"] == 500
    assert d["compiler_version"] == "11.0.0"


def test_artefactos_release():
    """SBOM y lock existen y son parseables."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sbom = json.load(open(os.path.join(raiz, "SBOM.json"), encoding="utf-8"))
    assert sbom["producto"] == "inveniolang"
    lock = open(os.path.join(raiz, "requirements-lock.txt"), encoding="utf-8").read()
    assert "ply==3.11" in lock
