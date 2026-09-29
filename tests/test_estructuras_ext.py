# test_estructuras_ext.py — Estructuras/algoritmos extendidos AAA+
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang import api


def _ejecutar_archivo(nombre):
    """Ejecuta un .inv de pruebas y retorna salida."""
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pruebas", nombre
    )
    cod = open(ruta, encoding="utf-8").read()
    r = api.ejecutar(cod)
    assert r.ok, r.errores
    return "".join(r.salida)


def test_conjunto():
    """Set con unión e intersección deterministas."""
    s = _ejecutar_archivo("conjunto.inv")
    assert "union={1,2,3,4,5}" in s
    assert "inter={3}" in s


def test_trie():
    """Trie con prefijos y negativos."""
    s = _ejecutar_archivo("trie.inv")
    assert "hola=true" in s
    assert "ho=false" in s


def test_kmp():
    """KMP encuentra patrón y retorna -1 si ausente."""
    s = _ejecutar_archivo("kmp.inv")
    assert "pos=5" in s
    assert "pos3=-1" in s


def test_floyd():
    """Floyd-Warshall 4x4 determinista."""
    s = _ejecutar_archivo("floyd.inv")
    assert "floyd: 0 3 5 6" in s


def test_arbol_b():
    """Árbol B t=2 ordenado y búsqueda."""
    s = _ejecutar_archivo("arbol_b.inv")
    assert "inorder: 5 6 7 10 12 17 20 30" in s
    assert "buscar12=true" in s
    assert "buscar99=false" in s
