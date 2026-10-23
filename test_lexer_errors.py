"""Pruebas especificas para validar deteccion de errores lexicos segun documentacion.

Se ejecuta como script: python test_lexer_errors.py
La funcion auxiliar se llama `verificar` (no `test`) para que pytest no la
recolecte como caso de prueba y falle pidiendo fixtures inexistentes.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from inveniolang.errors import ErrorManager
from inveniolang.lexer import Lexer


def verificar(nombre, codigo, errores_esperados):
    """Ejecuta una prueba y reporta si los errores esperados se produjeron."""
    em = ErrorManager()
    lex = Lexer(em)
    lex.build()
    lex.tokenizar(codigo)
    codigos_reales = sorted({e.codigo for e in em.errores})
    codigos_esperados = sorted(errores_esperados)

    if codigos_reales == codigos_esperados:
        print(f"  [OK] {nombre}")
        return True
    else:
        print(f"  [FAIL] {nombre}")
        print(f"        Esperado: {codigos_esperados}")
        print(f"        Obtenido: {codigos_reales}")
        if em.errores:
            for e in em.errores:
                print(f"          {e.formato_oficial()}")
        return False


print("=" * 60)
print("VALIDACION DE ERRORES LEXICOS (IL-LEX)")
print("Segun catalogo Seccion 15.2 y Especificacion Lexica Seccion 2.14")
print("=" * 60)

resultados = []

print("\n[IL-LEX-002] Caracter invalido")
r = verificar("caracter @", "void main() { @ }", ["IL-LEX-002"])
resultados.append(r)
r = verificar("caracter #", "void main() { # }", ["IL-LEX-002"])
resultados.append(r)
r = verificar("caracter $", "void main() { $ }", ["IL-LEX-002"])
resultados.append(r)
r = verificar("caracter `", "void main() { ` }", ["IL-LEX-002"])
resultados.append(r)

print("\n[IL-LEX-003] Caracter de control invalido")
r = verificar("control \\x03", "void main() { \x03 }", ["IL-LEX-003"])
resultados.append(r)

print("\n[IL-LEX-004] Identificador inicia con digito")
r = verificar("1contador", "void main() { int 1contador; }", ["IL-LEX-004"])
resultados.append(r)
r = verificar("3x", "void main() { int 3x; }", ["IL-LEX-004"])
resultados.append(r)

print("\n[IL-LEX-005] Caracter ilegal en identificador")
r = verificar("año (ñ)", "void main() { int año; }", ["IL-LEX-005"])
resultados.append(r)
r = verificar("posicion (acento)", "void main() { int posición; }", ["IL-LEX-005"])
resultados.append(r)

print("\n[IL-LEX-006] Identificador es palabra reservada")
em = ErrorManager()
lex = Lexer(em)
lex.build()
tokens = lex.tokenizar("int while = 5;")
codigos = [t[0] for t in tokens]
print(f"  Tokens: {codigos}  Errores: {[e.codigo for e in em.errores]}")
has_kw_while = 'KW_WHILE' in codigos
if has_kw_while:
    print("  [OK] while tokenizado como KW_WHILE")
    resultados.append(True)
else:
    print("  [FAIL] while no fue tokenizado como KW_WHILE")
    resultados.append(False)

print("\n[IL-LEX-007] Subrayado en entero")
r = verificar("1_000", "void main() { int x = 1_000; }", ["IL-LEX-007"])
resultados.append(r)

print("\n[IL-LEX-008] Base no soportada")
r = verificar("0xFF (hex)", "void main() { int x = 0xFF; }", ["IL-LEX-008"])
resultados.append(r)
r = verificar("0b101 (bin)", "void main() { int x = 0b101; }", ["IL-LEX-008"])
resultados.append(r)
r = verificar("0o77 (octal)", "void main() { int x = 0o77; }", ["IL-LEX-008"])
resultados.append(r)

print("\n[IL-LEX-009] Real mal formado")
r = verificar(".5 (falta digito antes)", "void main() { float x = .5; }", ["IL-LEX-009"])
resultados.append(r)
r = verificar("5. (falta digito despues)", "void main() { float x = 5.; }", ["IL-LEX-009"])
resultados.append(r)
r = verificar("1e10 (sin punto decimal)", "void main() { float x = 1e10; }", ["IL-LEX-009"])
resultados.append(r)
r = verificar("1.0e (exponente vacio)", "float x = 1.0e;", ["IL-LEX-009"])
resultados.append(r)

print("\n[IL-LEX-010] Salto de linea en string")
codigo_con_salto = 'void main() { string s = "linea 1\nlinea 2"; }'
r = verificar("salto en string", codigo_con_salto, ["IL-LEX-010"])
resultados.append(r)

print("\n[IL-LEX-011] Escape desconocido")
r = verificar('escape \\q', 'void main() { string s = "escape \\q"; }', ["IL-LEX-011"])
resultados.append(r)
r = verificar('escape \\z', 'void main() { string s = "escape \\z"; }', ["IL-LEX-011"])
resultados.append(r)

print("\n[IL-LEX-012] String no terminado")
r = verificar('string sin cerrar EOF',
         'void main() { string s = "texto sin cerrar; }', ["IL-LEX-012"])
resultados.append(r)
codigo_sin_cerrar = '''void main() { string s = "hola;
}'''
r = verificar("string sin cerrar por salto", codigo_sin_cerrar, ["IL-LEX-012"])
resultados.append(r)

print("\n[IL-LEX-013] Delimitadores no coinciden")
r = verificar('comillas mixtas doble-simple',
         "void main() { string s = \"texto'; }", ["IL-LEX-013"])
resultados.append(r)
r = verificar("comillas mixtas simple-doble",
         "void main() { string s = 'texto\"; }", ["IL-LEX-013"])
resultados.append(r)

print("\n[IL-LEX-014] Comentario bloque no terminado")
r = verificar('/* sin cerrar', "void main() { /* comentario sin cerrar }", ["IL-LEX-014"])
resultados.append(r)

print("\n[VERIFICACION] Comentario bloque bien formado")
em = ErrorManager()
lex = Lexer(em)
lex.build()
em.tokenizar_o = lex.tokenizar
lex.tokenizar("/* comentario */ x")
if len(em.errores) == 0:
    print("  [OK] No produce errores")
    resultados.append(True)
else:
    print("  [FAIL] Produjo errores:", [e.codigo for e in em.errores])
    resultados.append(False)

print("\n[VERIFICACION] Funcionamiento normal no afectado")
em = ErrorManager()
lex = Lexer(em)
lex.build()
tokens = lex.tokenizar("void main() { int x = 42; imprimir(x); }")
codigos = [t[0] for t in tokens]
tokens_ok = 'KW_VOID' in codigos and 'KW_MAIN' in codigos
tokens_ok = tokens_ok and 'IDENTIFICADOR' in codigos
errores_ok = len(em.errores) == 0
if tokens_ok and errores_ok:
    print("  [OK] Tokenizacion normal funciona")
    resultados.append(True)
else:
    print(f"  [FAIL] Tokens: {codigos}, Errores: {[e.codigo for e in em.errores]}")
    resultados.append(False)

# Resumen
print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)
total = len(resultados)
exitos = sum(1 for r in resultados if r)
fallos = total - exitos
print(f"Pruebas: {total}, Exitos: {exitos}, Fallos: {fallos}")
if fallos > 0:
    print("\nERRORES DETECTADOS - El lexer NO cumple completamente con la documentacion")
else:
    print("\nTODO OK - El lexer cumple con la deteccion de errores segun la documentacion")
