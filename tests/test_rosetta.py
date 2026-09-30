# test_rosetta.py — Fidelidad estructurada del viewer (no compila otros)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang.viewer.rosetta import transpile

PROG = (
    "int doble(int x) { return x * 2; }\n"
    "void main() {\n"
    "  int a = 3;\n"
    '  imprimir("hola");\n'
    "  si (a > 0) { imprimir(doble(a)); }\n"
    "  mientras (a < 6) { a = a + 1; }\n"
    "  para (int i = 0; i < 2; i++) { imprimir(i); }\n"
    "}\n"
)


def test_python_fiel():
    """Python conserva def, if, while y print."""
    s = transpile("python", PROG)
    assert "def doble(x):" in s
    assert "if (a > 0):" in s
    assert "while (a < 6):" in s
    assert 'print("hola")' in s
    assert "doble(a)" in s
    assert "pass  #" not in s


def test_c_fiel():
    """C conserva tipos, printf con formato y for."""
    s = transpile("c", PROG)
    assert "static int doble(int x)" in s
    assert 'printf("%s\\n", "hola")' in s
    assert "for (int i = 0;" in s
    assert "return (x * 2);" in s


def test_java_csharp_fiel():
    """Java y C# conservan firmas y salidas."""
    j = transpile("java", PROG)
    assert "static int doble(int x)" in j
    assert "System.out.print" in j
    assert "for (int i = 0;" in j
    cs = transpile("csharp", PROG)
    assert "static int doble(int x)" in cs
    assert "Console.Write" in cs


def test_pascal_fiel():
    """Pascal conserva program, writeln y while desazucarado."""
    s = transpile("pascal", PROG)
    assert "program Main;" in s
    assert "writeln(" in s
    assert "while" in s
    assert "for desazucarado" in s


def test_hola_mundo_sin_crash():
    """Hola mundo no deja escapes crudos en ningún target."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = open(os.path.join(base, "pruebas", "hola_mundo.inv"), encoding="utf-8").read()
    for t in ("python", "c", "java", "csharp", "pascal"):
        s = transpile(t, code)
        assert "Hola, mundo!" in s
        assert '\n"' not in s  # sin salto crudo dentro de literal
