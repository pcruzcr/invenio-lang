"""Complejidad, efectos, CFG/SSA y núcleo (INV-1014, INV-1015, INV-1016, INV-1022)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from inveniolang import ir  # noqa: E402
from inveniolang.cfg import construir_cfg  # noqa: E402
from inveniolang.complexity import (  # noqa: E402
    EXPONENCIAL,
    Costo,
    analizar_complejidad,
    describir,
)
from inveniolang.core import CompileRequest, analizar_fuente, compile_pure  # noqa: E402
from inveniolang.effects import analizar_efectos, describir_efectos, es_pura  # noqa: E402
from inveniolang.ir_ssa import a_ssa, dominadores, formatear_ssa, frontera_dominancia  # noqa: E402

PRUEBAS = RAIZ / "pruebas"


def _ast(codigo: str):
    analisis = analizar_fuente(codigo, hasta="parser")
    assert analisis.ok, analisis.errores.obtener_reportes()
    return analisis.ast


def _cotas(codigo: str) -> dict[str, str]:
    return {n: r.estimado for n, r in analizar_complejidad(_ast(codigo)).items()}


# ------------------------------------------------------------ complejidad
@pytest.mark.parametrize(
    ("programa", "subrutina", "cota"),
    [
        ("mergesort.inv", "mergesort", "O(n log n)"),
        ("quicksort.inv", "quicksort", "O(n log n)"),
        ("busqueda_binaria.inv", "busquedaBinaria", "O(log n)"),
        ("heapsort.inv", "siftDownMax", "O(log n)"),
        ("heapsort.inv", "heapsort", "O(n log n)"),
        ("hanoi.inv", "hanoi", "O(2^n)"),
        ("n_reinas.inv", "resolver", "O(2^n)"),
        ("ordenamiento_insercion.inv", "ordenarInsercion", "O(n²)"),
        ("floyd.inv", "main", "O(n³)"),
    ],
)
def test_cotas_de_algoritmos_clasicos(programa, subrutina, cota):
    """INV-1015: antes O(n log n) salía solo si el árbol contenía la palabra "merge"."""
    assert _cotas((PRUEBAS / programa).read_text(encoding="utf-8"))[subrutina] == cota


def test_complejidad_casos_finos():
    codigo = """
    int lineal(int n) { si (n <= 0) { retornar 0; } retornar lineal(n - 1) + 1; }
    int fijo() { int s = 0; para (int i = 0; i < 10; i++) { s = s + i; } retornar s; }
    int duplica(int n) { int i = 1; mientras (i < n) { i = i * 2; } retornar i; }
    int par(int n) { si (n == 0) { retornar 1; } retornar impar(n - 1); }
    int impar(int n) { si (n == 0) { retornar 0; } retornar par(n - 1); }
    int usa(int n) { int t = 0; para (int i = 0; i < n; i++) { t = t + duplica(n); } retornar t; }
    int mitades(int n) { si (n <= 1) { retornar 1; }
        retornar mitades(n / 2) + mitades(n / 2) + mitades(n / 2); }
    void main() { imprimir(lineal(3) + fijo() + par(4) + usa(8) + mitades(8)); }
    """
    cotas = _cotas(codigo)
    assert cotas["lineal"] == "O(n)"
    assert cotas["fijo"] == "O(1)"
    assert cotas["duplica"] == "O(log n)"
    assert cotas["par"] == cotas["impar"] == "O(n)"
    assert cotas["usa"] == "O(n log n)"
    assert cotas["mitades"] == "O(n^1.58)"
    resultados = analizar_complejidad(_ast(codigo))
    assert resultados["par"].recursiva
    texto_es = "\n".join(describir(resultados))
    texto_en = "\n".join(describir(resultados, "en"))
    assert "recursión mutua con impar" in texto_es and "mutual recursion" in texto_en


def test_costos_se_componen():
    assert str(Costo(grado=2, log=2)) == "O(n² log^2 n)"
    assert str(Costo(grado=4)) == "O(n^4)"
    assert Costo(grado=1).por(EXPONENCIAL) == EXPONENCIAL


def test_complejidad_de_metodos():
    codigo = (PRUEBAS / "arbol_binario.inv").read_text(encoding="utf-8")
    assert any("." in nombre for nombre in _cotas(codigo))


# ------------------------------------------------------------ efectos
def test_efectos_transitivos_y_por_referencia():
    """INV-1014: imprimir/leer son sentencias; los efectos se heredan por llamadas."""
    codigo = """
    int contador = 0;
    int cuadrado(int x) { retornar x * x; }
    void anotar() { contador++; }
    void llenar(int[] a, int n) { para (int i = 0; i < n; i++) { a[i] = cuadrado(i); } }
    void delega(int[] b) { llenar(b, 3); }
    void azaroso() { imprimir(azar(1, 6)); }
    void archivo() { escribir_archivo("x.txt", "hola"); }
    void pide() { int v; leer(v); anotar(); }
    void main() { int[3] z; delega(z); azaroso(); archivo(); pide(); }
    """
    ef = analizar_efectos(_ast(codigo))
    assert es_pura(ef, "cuadrado")
    assert ef["anotar"] == {"estado_global"}
    assert ef["llenar"] == {"modifica_parametro"}
    assert ef["delega"] == {"modifica_parametro"}
    assert ef["azaroso"] == {"aleatorio", "salida"}
    assert ef["archivo"] == {"archivo"}
    assert ef["pide"] == {"entrada", "estado_global"}
    assert "modifica_parametro" not in ef["main"]
    assert "pure" in describir_efectos(ef, "en")[0] or "cuadrado: pure" in describir_efectos(
        ef, "en"
    )


# ------------------------------------------------------------ CFG / SSA
def test_cfg_try_y_codigo_inalcanzable():
    codigo = """
    int f(int n) { intentar { imprimir(10 / n); } capturar (e) { imprimir("x"); } retornar 1; }
    void main() { imprimir(f(2)); }
    """
    analisis = analizar_fuente(codigo)
    assert analisis.ok, analisis.errores.obtener_reportes()
    tac = ir.generar_programa(analisis.ast)[0]["f"][1]
    cfg = construir_cfg(tac)
    assert any(len(b.sucesores) >= 2 for b in cfg.values())
    dom = dominadores(cfg)
    assert all("B0" in d for d in dom.values())
    assert set(frontera_dominancia(cfg)) == set(cfg)
    assert "B0:" in formatear_ssa(a_ssa(tac))
    assert construir_cfg([])["B0"].instrs == []


# ------------------------------------------------------------ núcleo
def test_analizar_fuente_corta_por_fase():
    assert analizar_fuente("void main() { }", hasta="lexer").ast is None
    assert analizar_fuente("void main() { }", hasta="parser").tabla is None
    sem = analizar_fuente("void main() { imprimir(z); }")
    assert sem.fase_fallida == "semantico" and sem.tabla is not None
    with pytest.raises(ValueError):
        analizar_fuente("", hasta="optimizador")


def test_compile_pure_errores_en_ejecucion():
    r = compile_pure(CompileRequest("t.inv", "void main() { int x = 0; imprimir(1 / x); }"))
    assert not r.ok and any("IL-EJE" in e for e in r.errores)
