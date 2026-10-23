"""INV-4405: memoización y ciclos amortizados (KMP) en ``complexity.py``.

Antes Fibonacci memoizado salía ``O(2^n)`` y KMP ``O(n²)``: el análisis no
veía que la tabla evita repetir subproblemas ni que la variable del ciclo
interno no se reinicia. La salida al estudiante explica ahora el método y
sus límites.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import api  # noqa: E402
from inveniolang.complexity import analizar_complejidad, describir  # noqa: E402
from inveniolang.core import analizar_fuente  # noqa: E402
from inveniolang.i18n import t  # noqa: E402

PRUEBAS = RAIZ / "pruebas"


def _cotas(codigo: str) -> dict[str, str]:
    analisis = analizar_fuente(codigo, "t.inv")
    assert analisis.ok, analisis.errores.obtener_reportes()
    return {n: r.estimado for n, r in analizar_complejidad(analisis.ast).items()}


def test_fibonacci_memoizado_es_lineal():
    cotas = _cotas((PRUEBAS / "fibonacci_memo.inv").read_text(encoding="utf-8"))
    assert cotas["fib"] == "O(n)" and cotas["main"] == "O(n)"


def test_kmp_es_lineal():
    cotas = _cotas((PRUEBAS / "kmp.inv").read_text(encoding="utf-8"))
    assert cotas["prefijo"] == cotas["buscarKmp"] == cotas["main"] == "O(n)"


CASOS = """
const int N = 50;
int[N][N] memo;
int caminos(int f, int c) {
    si (f == 0 || c == 0) { retornar 1; }
    si (memo[f][c] != 0) { retornar memo[f][c]; }
    memo[f][c] = caminos(f - 1, c) + caminos(f, c - 1);
    retornar memo[f][c];
}
int[N] solo_llena;
int sinConsulta(int n) {
    si (n <= 1) { retornar n; }
    solo_llena[n] = sinConsulta(n - 1) + sinConsulta(n - 2);
    retornar solo_llena[n];
}
int dosPunteros(int[] a, int n, int objetivo) {
    int j = 0;
    int pares = 0;
    para (int i = 0; i < n; i++) {
        mientras (j < n && a[j] - a[i] < objetivo) { j++; }
        si (j < n && a[j] - a[i] == objetivo) { pares++; }
    }
    retornar pares;
}
int reinicia(int[] a, int n) {
    int j = 0;
    int s = 0;
    para (int i = 0; i < n; i++) {
        j = 0;
        mientras (j < i) { s = s + a[j]; j++; }
    }
    retornar s;
}
void insercion(int[] a, int n) {
    para (int i = 1; i < n; i++) {
        int clave = a[i];
        int j = i - 1;
        mientras (j >= 0 && a[j] > clave) { a[j + 1] = a[j]; j--; }
        a[j + 1] = clave;
    }
}
void main() {
    int[5] v = {1, 3, 5, 7, 9};
    insercion(v, 5);
    imprimir(caminos(3, 3) + sinConsulta(5) + dosPunteros(v, 5, 2) + reinicia(v, 5));
}
"""


def test_memo_en_matriz_dos_punteros_y_casos_que_no_se_rebajan():
    cotas = _cotas(CASOS)
    assert cotas["caminos"] == "O(n²)"  # n² estados de una tabla 2D, O(1) cada uno
    assert cotas["sinConsulta"] == "O(2^n)"  # guarda pero nunca consulta: no es memoización
    assert cotas["dosPunteros"] == "O(n)"  # j nunca se reinicia
    assert cotas["reinicia"] == "O(n²)"  # j = 0 en cada vuelta: no hay amortización
    assert cotas["insercion"] == "O(n²)"  # j se declara dentro del ciclo externo


def test_notas_explican_metodo_y_limites_en_ambos_idiomas():
    for idioma in ("es", "en"):
        r = api.complejidad((PRUEBAS / "kmp.inv").read_text(encoding="utf-8"), idioma=idioma)
        texto = "".join(r.salida)
        assert t("COMP.metodo", idioma) in texto and t("COMP.limites", idioma) in texto
        assert t("COMP.bucle_amortizado", idioma, linea=6, var="k") in texto
    analisis = analizar_fuente(
        (PRUEBAS / "fibonacci_memo.inv").read_text(encoding="utf-8"), "f.inv"
    )
    texto = "\n".join(describir(analizar_complejidad(analisis.ast), "en"))
    assert "memoization" in texto and "computed only once" in texto
