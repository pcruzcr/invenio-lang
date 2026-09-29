# test_release.py — Puerta GA: política y artefactos
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang import policy


def test_politica_aula_aislada():
    """Lo no confiable corre aislado por defecto."""
    r = policy.ejecutar_no_confiable("void main() { imprimir(9); }", timeout=10)
    assert r.ok
    assert "9" in "".join(r.salida)
    assert "sandbox" in policy.AVISO_AULA.lower()


def test_limites_para_acta():
    """Límites serializables para examen."""
    d = policy.limites_aula()
    assert d["max_recursion"] == 500
    assert d["compiler_version"] == "10.0.0"


def test_artefactos_release():
    """SBOM y lock existen y son parseables."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sbom = json.load(open(os.path.join(raiz, "SBOM.json"), encoding="utf-8"))
    assert sbom["producto"] == "inveniolang"
    lock = open(os.path.join(raiz, "requirements-lock.txt"), encoding="utf-8").read()
    assert "ply==3.11" in lock
