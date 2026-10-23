"""INV-4403: Rosetta respeta los tipos (arreglos, matrices, E/S) en cada destino.

Antes un parámetro ``int[] arr`` salía como ``int arr`` en Java/C/C#, las
declaraciones de arreglos y matrices eran un comentario, ``m[i][j]`` se
convertía en ``/*expr-MatrixAccess*/0``, ``printf`` usaba siempre ``%d``,
Python hacía ``7/3 = 2.33`` y escribía ``&&``/``true``, e ``imprimir``
añadía saltos de línea que InvenioLang no añade. Si hay compiladores en la
máquina (gcc, g++, javac, python3) el código generado se compila, se
ejecuta y su salida debe ser IDÉNTICA a la de InvenioLang.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import api  # noqa: E402
from inveniolang.viewer.rosetta import transpile  # noqa: E402

PROGRAMA = """
const int N = 4;
const int C = 2;
int[N] datos = {5, 3, 8, 1};
int llamadas = 0;

int suma(int[] arr, int n) {
    llamadas++;
    int s = 0;
    para (int i = 0; i < n; i++) { s = s + arr[i]; }
    return s;
}

void escalar(float[][] m, int filas, float k) {
    para (int i = 0; i < filas; i++) {
        para (int j = 0; j < C; j++) { m[i][j] = m[i][j] * k; }
    }
}

bool todosPositivos(int[] arr, int n) {
    para (int i = 0; i < n; i++) { si (arr[i] <= 0) { return false; } }
    return true;
}

void main() {
    float[2][C] m = {{1.5, 2.0}, {0.5, 4.0}};
    escalar(m, 2, 2.0);
    imprimir(suma(datos, N)); imprimir(" ");
    imprimir(suma(datos, N) / 3); imprimir(" ");
    imprimir(m[0][0] + m[1][0]); imprimir(" ");
    imprimir(todosPositivos(datos, N) && llamadas == 2); imprimir(" ");
    int x = 0;
    leer(x);
    imprimir(x * 2);
    imprimir("\\n");
}
"""
ENTRADA = "21\n"


def _esperado() -> str:
    r = api.ejecutar(PROGRAMA, entrada=("21",))
    assert r.ok, r.errores
    return "".join(r.salida)


def test_salida_de_referencia():
    assert _esperado() == "17 5 4.0 true 42\n"


def test_firmas_con_arreglos_y_matrices_en_cada_destino():
    java = transpile("java", PROGRAMA)
    assert "static int suma(int[] arr, int n)" in java
    assert "static void escalar(double[][] m, int filas, double k)" in java
    assert "static final int N = 4;" in java and "const int" not in java
    assert "double[][] m = {{1.5, 2.0}, {0.5, 4.0}};" in java
    assert "m[i][j]" in java and "no-soportado" not in java and "expr-" not in java

    c = transpile("c", PROGRAMA)
    assert "static int suma(int arr[], int n)" in c
    assert "static void escalar(double m[][C], int filas, double k)" in c
    assert "int datos[N] = {5, 3, 8, 1};" in c
    assert 'printf("%g", ((m[0][0] + m[1][0])))' in c or 'printf("%g", (m[0][0] + m[1][0]))' in c
    assert 'scanf("%d", &x)' in c

    cs = transpile("csharp", PROGRAMA)
    assert "static int suma(int[] arr, int n)" in cs
    assert "static void escalar(double[,] m, int filas, double k)" in cs
    assert "double[,] m = {{1.5, 2.0}, {0.5, 4.0}};" in cs and "m[i, j]" in cs
    assert "x = int.Parse(Console.ReadLine())" in cs

    pas = transpile("pascal", PROGRAMA)
    assert "function suma(var arr: array of integer; n: integer): integer;" in pas
    assert "TMatrizReal = array of array of real;" in pas
    assert "procedure escalar(var m: TMatrizReal; filas: integer; k: real);" in pas
    assert "(suma(datos, N) div 3)" in pas and "Exit(s);" in pas
    assert "writeln" not in pas  # imprimir no añade salto de línea

    py = transpile("python", PROGRAMA)
    assert "(suma(datos, N) // 3)" in py
    assert " and " in py and "&&" not in py
    assert "    global llamadas" in py
    assert "x = int(input())" in py


def _correr(cmd: list[str], cwd: Path) -> str:
    r = subprocess.run(cmd, input=ENTRADA, capture_output=True, text=True, cwd=cwd, timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_python_generado_da_la_misma_salida(tmp_path):
    (tmp_path / "p.py").write_text(transpile("python", PROGRAMA), encoding="utf-8")
    assert _correr([sys.executable, "p.py"], tmp_path) == _esperado()


@pytest.mark.parametrize("compilador, destino", [("gcc", "c"), ("g++", "cpp")])
def test_c_generado_compila_y_da_la_misma_salida(tmp_path, compilador, destino):
    if shutil.which(compilador) is None:
        pytest.skip(f"{compilador} no está instalado")
    fuente = tmp_path / ("p.c" if destino == "c" else "p.cpp")
    fuente.write_text(transpile(destino, PROGRAMA), encoding="utf-8")
    _correr([compilador, "-Wall", "-o", "p", fuente.name], tmp_path)
    salida = _correr([str(tmp_path / "p")], tmp_path)
    # %g escribe 4 donde InvenioLang escribe 4.0: única diferencia documentada.
    assert salida == _esperado().replace("4.0", "4")


def test_java_generado_compila_y_da_la_misma_salida(tmp_path):
    if shutil.which("javac") is None or shutil.which("java") is None:
        pytest.skip("JDK no instalado")
    (tmp_path / "Main.java").write_text(transpile("java", PROGRAMA), encoding="utf-8")
    _correr(["javac", "Main.java"], tmp_path)
    assert _correr(["java", "-cp", ".", "Main"], tmp_path) == _esperado()
