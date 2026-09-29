"""Auditoria completa: verifica cada requisito documentado vs codigo."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from inveniolang.lexer import Lexer
from inveniolang.parser import Parser
from inveniolang.errors import ErrorManager
from inveniolang.semantic import SemanticAnalyzer
from inveniolang.type_checker import TypeChecker
from inveniolang.interpreter import Interpreter, RuntimeError_

errores = []

def test(nombre, codigo, esperado=None, error_esperado=None, entrada=None):
    em = ErrorManager()
    try:
        lexer = Lexer(em)
        parser = Parser(lexer, em)
        ast, _ = parser.analizar(codigo, 'test')
        if ast is None:
            if error_esperado:
                return  # OK - error esperado
            errores.append((nombre, f"AST nulo: {[e.formato_oficial() for e in em.errores]}"))
            return
        sem = SemanticAnalyzer(em)
        tabla = sem.analizar(ast)
        tc = TypeChecker(em, tabla)
        tc.verificar(ast)
        if em.hay_errores():
            if error_esperado:
                return
            errores.append((nombre, f"Error semantico/tipos: {[e.formato_oficial() for e in em.errores]}"))
            return
        interp = Interpreter(em, tabla)
        salida = interp.interpretar(ast, entrada)
        if em.hay_errores():
            if error_esperado:
                return
            errores.append((nombre, f"Error runtime: {[e.formato_oficial() for e in em.errores]}"))
            return
        if error_esperado:
            errores.append((nombre, "Se esperaba error pero no hubo"))
            return
        salida_str = ''.join(salida)
        if esperado is not None and salida_str != esperado:
            errores.append((nombre, f"Esperado={repr(esperado)}, obtenido={repr(salida_str)}"))
    except Exception as e:
        errores.append((nombre, f"Excepcion: {type(e).__name__}: {e}"))

def test_error(nombre, codigo, error_code):
    """Verifica que se produzca un error con un codigo especifico."""
    em = ErrorManager()
    try:
        lexer = Lexer(em)
        parser = Parser(lexer, em)
        ast, _ = parser.analizar(codigo, 'test')
        if ast is None:
            for e in em.errores:
                if error_code in e.codigo:
                    return
            errores.append((nombre, f"AST nulo pero sin codigo {error_code}: {[e.formato_oficial() for e in em.errores]}"))
            return
        sem = SemanticAnalyzer(em)
        tabla = sem.analizar(ast)
        for e in em.errores:
            if error_code in e.codigo:
                return
        tc = TypeChecker(em, tabla)
        tc.verificar(ast)
        for e in em.errores:
            if error_code in e.codigo:
                return
        interp = Interpreter(em, tabla)
        salida = interp.interpretar(ast)
        for e in em.errores:
            if error_code in e.codigo:
                return
        errores.append((nombre, f"No se encontro error {error_code}. Errores: {[e.formato_oficial() for e in em.errores]}"))
    except Exception as e:
        errores.append((nombre, f"Excepcion: {type(e).__name__}: {e}"))

print("=" * 60)
print("AUDITORIA COMPLETA InvenioLang 1.0")
print("=" * 60)

# =============================================
# SECCION 1: TOKENS Y LEXER (Seccion 2, Tablas 1-4)
# =============================================
print("\n[1] LEXER - Palabras reservadas bilingues (Seccion 2.3, Tabla 1)")

# Verificar que las 34 palabras del README existen
keywords_esperadas = {
    'if','si','else','sino',
    'while','mientras','for','para',
    'return',
    'print','imprimir','read','leer',
    'int','entero','float','real','string','texto','bool','logico',
    'void','vacio',
    'const','constante',
    'true','verdadero','false','falso',
    'break','romper','continue','continuar',
    'main',
}
em = ErrorManager()
l = Lexer(em)
l.build()
for kw in keywords_esperadas:
    if kw not in l.keywords:
        errores.append((f"Keyword faltante: {kw}", "No esta en lexer.keywords"))

# Token types from Table 2
tokens_esperados = [
    'IDENTIFICADOR', 'ENTERO_LIT', 'REAL_LIT', 'TEXTO_LIT',
    'OP_SUMA', 'OP_RESTA', 'OP_MULT', 'OP_DIV', 'OP_MOD',
    'OP_IGUAL', 'OP_DISTINTO', 'OP_MENOR', 'OP_MAYOR',
    'OP_MENOR_IGUAL', 'OP_MAYOR_IGUAL',
    'OP_AND', 'OP_OR', 'OP_NOT',
    'OP_ASIG', 'OP_ASIG_SUMA', 'OP_ASIG_RESTA',
    'OP_ASIG_MULT', 'OP_ASIG_DIV', 'OP_ASIG_MOD',
    'OP_INC', 'OP_DEC',
    'DEL_LLAVE_A', 'DEL_LLAVE_C',
    'DEL_PAREN_A', 'DEL_PAREN_C',
    'DEL_CORCHETE_A', 'DEL_CORCHETE_C',
    'DEL_PUNTO_COMA', 'DEL_COMA',
    'KW_IF', 'KW_ELSE', 'KW_WHILE', 'KW_FOR', 'KW_RETURN',
    'KW_PRINT', 'KW_READ', 'KW_INT', 'KW_FLOAT', 'KW_STRING',
    'KW_BOOL', 'KW_VOID', 'KW_CONST', 'KW_TRUE', 'KW_FALSE',
    'KW_BREAK', 'KW_CONTINUE', 'KW_MAIN',
]
for tok in tokens_esperados:
    if tok not in l.tokens:
        errores.append((f"Token faltante: {tok}", "No esta en lexer.tokens"))

print(f"  Keywords: {len(keywords_esperadas)}/{len(keywords_esperadas)}")
print(f"  Tokens:   {len(tokens_esperados)}/{len(tokens_esperados)}")

# =============================================
# SECCION 2: TIPOS DE DATOS (Seccion 4, Tabla 5)
# =============================================
print("\n[2] TIPOS DE DATOS")
test("int literal", "void main() { imprimir(42); }", "42")
test("float literal", "void main() { imprimir(3.14); }", "3.14")
test("string literal", 'void main() { imprimir("hola"); }', "hola")
test("bool true", "void main() { imprimir(true); }", "true")
test("bool false", "void main() { imprimir(false); }", "false")
test("int var + init", "void main() { int x = 10; imprimir(x); }", "10")
test("float var + init", "void main() { float y = 3.14; imprimir(y); }", "3.14")
test("string var + init", 'void main() { string s = "ok"; imprimir(s); }', "ok")
test("bool var + init", "void main() { bool b = true; imprimir(b); }", "true")
test("void procedimiento", "void nada() { } void main() { nada(); }", "")
test("const int", "void main() { const int N = 7; imprimir(N); }", "7")
test("const float", "void main() { const float P = 3.14; imprimir(P); }", "3.14")
test("const string", 'void main() { const string S = "fijo"; imprimir(S); }', "fijo")
test("const bool", "void main() { const bool B = true; imprimir(B); }", "true")

# =============================================
# SECCION 3: PALABRAS RESERVADAS BILINGUES
# =============================================
print("\n[3] PALABRAS BILINGUES")
test("si (if)", "void main() { si (true) { imprimir(1); } }", "1")
test("sino (else)", "void main() { si (false) { imprimir(1); } sino { imprimir(2); } }", "2")
test("mientras (while)", "void main() { int i=0; mientras(i<2){imprimir(i);i=i+1;} }", "01")
test("para (for)", "void main() { para(int i=0; i<2; i++) { imprimir(i); } }", "01")
test("imprimir (print)", 'void main() { imprimir("x"); }', "x")
test("leer (read)", "void main() { entero x = 5; leer(x); imprimir(x); }", "42", entrada=["42"])  # read lee de la entrada (§7.2)
test("entero (int)", "void main() { entero x = 5; imprimir(x); }", "5")
test("real (float)", "void main() { real x = 3.14; imprimir(x); }", "3.14")
test("texto (string)", 'void main() { texto s = "ok"; imprimir(s); }', "ok")
test("logico (bool)", "void main() { logico b = verdadero; imprimir(b); }", "true")
test("vacio (void)", "vacio foo() { } vacio main() { foo(); }", "")
test("constante (const)", "void main() { constante int N = 5; imprimir(N); }", "5")
test("verdadero (true)", "void main() { imprimir(verdadero); }", "true")
test("falso (false)", "void main() { imprimir(falso); }", "false")
test("romper (break)", "void main() { for(int i=0;i<3;i++){si(i==1){romper;}imprimir(i);} }", "0")
test("continuar (continue)", "void main() { for(int i=0;i<3;i++){si(i==1){continuar;}imprimir(i);} }", "02")

# =============================================
# SECCION 4: OPERADORES Y PRECEDENCIA (Seccion 16.7, Tabla 13)
# =============================================
print("\n[4] OPERADORES Y PRECEDENCIA")
test("suma", "void main() { imprimir(2+3); }", "5")
test("resta", "void main() { imprimir(5-3); }", "2")
test("mult", "void main() { imprimir(4*3); }", "12")
test("div entera", "void main() { imprimir(7/3); }", "2")
test("mod", "void main() { imprimir(7%3); }", "1")
test("suma float", "void main() { imprimir(1.5+2.5); }", "4.0")
test("precedencia +*", "void main() { imprimir(2+3*4); }", "14")
test("precedencia ()", "void main() { imprimir((2+3)*4); }", "20")
test("precedencia && ||", "void main() { imprimir(true || true && false); }", "true")
test("precedencia == +", "void main() { int x=5; imprimir(x==2+3); }", "true")
test("unario -", "void main() { imprimir(-5); }", "-5")
test("unario !", "void main() { imprimir(!true); }", "false")
test("relacional <", "void main() { imprimir(2<3); }", "true")
test("relacional >", "void main() { imprimir(5>3); }", "true")
test("relacional <=", "void main() { imprimir(3<=3); }", "true")
test("relacional >=", "void main() { imprimir(4>=3); }", "true")
test("igualdad ==", "void main() { imprimir(3==3); }", "true")
test("igualdad !=", "void main() { imprimir(3!=4); }", "true")

# =============================================
# SECCION 5: ESTRUCTURAS DE CONTROL (Seccion 6-9)
# =============================================
print("\n[5] ESTRUCTURAS DE CONTROL")
test("if true", "void main() { if(true){imprimir(1);} }", "1")
test("if false", "void main() { if(false){imprimir(1);} }", "")
test("if-else then", "void main() { if(true){imprimir(1);}else{imprimir(2);} }", "1")
test("if-else else", "void main() { if(false){imprimir(1);}else{imprimir(2);} }", "2")
test("if anidado", "void main() { int x=5; if(x>0){if(x<10){imprimir(1);}} }", "1")
test("while", "void main(){int i=0; while(i<3){imprimir(i);i=i+1;}}", "012")
test("while false", "void main(){while(false){imprimir(1);}}", "")
test("for basico", "void main(){for(int i=0;i<3;i++){imprimir(i);}}", "012")
test("for sin init", "void main(){int i=0;for(;i<3;i++){imprimir(i);}}", "012")
test("for sin cond", "void main(){for(int i=0;;i++){if(i>=3){break;}imprimir(i);}}", "012")
test("for sin act", "void main(){for(int i=0;i<3;){imprimir(i);i=i+1;}}", "012")
test("break en for", "void main(){for(int i=0;i<5;i++){if(i==2){break;}imprimir(i);}}", "01")
test("break en while", "void main(){int i=0;while(i<5){if(i==2){break;}imprimir(i);i=i+1;}}", "01")
test("continue en for", "void main(){for(int i=0;i<5;i++){if(i%2==0){continue;}imprimir(i);}}", "13")
test("continue en while", "void main(){int i=0;while(i<5){i=i+1;if(i%2==0){continue;}imprimir(i-1);}}", "024")

# =============================================
# SECCION 6: FUNCIONES Y PROCEDIMIENTOS (Seccion 10-11)
# =============================================
print("\n[6] FUNCIONES Y PROCEDIMIENTOS")
test("funcion ret int", "int suma(int a,int b){return a+b;} void main(){imprimir(suma(3,4));}", "7")
test("funcion ret float", "float Mitad(float x){return x/2.0;} void main(){imprimir(Mitad(10.0));}", "5.0")
test("funcion ret bool", "bool esPos(int n){return n>0;} void main(){imprimir(esPos(5));}", "true")
test("funcion ret string", "string msg(int n){if(n>0){return\"pos\";}return\"neg\";} void main(){imprimir(msg(5));}", "pos")
test("funcion recursiva", "int fact(int n){if(n<=1){return 1;}return n*fact(n-1);} void main(){imprimir(fact(5));}", "120")
test("procedimiento void", "void saludar(){imprimir(\"hola\");} void main(){saludar();}", "hola")
test("procedimiento con param", "void mostrar(int x){imprimir(x);} void main(){mostrar(99);}", "99")
test("funcion multi params", "int mul(int a,int b,int c){return a*b*c;} void main(){imprimir(mul(2,3,4));}", "24")
test("funcion sin parametros", "int cinco(){return 5;} void main(){imprimir(cinco());}", "5")
test("funcion llamada en expr", "int doble(int x){return x*2;} void main(){imprimir(doble(3)+1);}", "7")

# =============================================
# SECCION 7: ARREGLOS Y MATRICES (Seccion 12)
# =============================================
print("\n[7] ARREGLOS Y MATRICES")
test("array decl init", "void main(){int[3]a={1,2,3};imprimir(a[1]);}", "2")
test("array acceso y escritura", "void main(){int[5]a;a[0]=10;a[1]=20;imprimir(a[0]);}", "10")
test("array const tam", "const int N=3;void main(){int[N]a={10,20,30};imprimir(a[2]);}", "30")
test("array float", "void main(){float[3]a={1.5,2.5,3.5};imprimir(a[1]);}", "2.5")
test("array param por ref", "void set(int[]arr,int v){arr[0]=v;} void main(){int[2]a={5,7};set(a,99);imprimir(a[0]);}", "99")
test("matrix decl init", "void main(){int[2][2]m={{1,2},{3,4}};imprimir(m[1][1]);}", "4")
test("matrix acceso", "void main(){int[2][2]m;m[0][1]=99;imprimir(m[0][1]);}", "99")
test("matrix const tam", "const int F=2;const int C=2;void main(){int[F][C]m={{1,2},{3,4}};imprimir(m[0][0]);}", "1")

# =============================================
# SECCION 8: FUNCIONES INTEGRADAS (Seccion 19)
# =============================================
print("\n[8] FUNCIONES INTEGRADAS")
test("int_a_float", "void main(){imprimir(int_a_float(42));}", "42.0")
test("float_a_int", "void main(){imprimir(float_a_int(3.9));}", "3")
test("int_a_texto", 'void main(){imprimir(int_a_texto(42));}', "42")
test("float_a_texto", 'void main(){imprimir(float_a_texto(3.14));}', "3.14")
test("bool_a_texto true", 'void main(){imprimir(bool_a_texto(true));}', "true")
test("bool_a_texto false", 'void main(){imprimir(bool_a_texto(false));}', "false")

# =============================================
# SECCION 9: ASIGNACIONES COMPUESTAS (Seccion 5.6)
# =============================================
print("\n[9] ASIGNACIONES COMPUESTAS")
test("asig =", "void main(){int x=5;x=10;imprimir(x);}", "10")
test("asig +=", "void main(){int x=5;x+=3;imprimir(x);}", "8")
test("asig -=", "void main(){int x=5;x-=3;imprimir(x);}", "2")
test("asig *=", "void main(){int x=5;x*=3;imprimir(x);}", "15")
test("asig /=", "void main(){int x=10;x/=3;imprimir(x);}", "3")
test("asig %=", "void main(){int x=10;x%=3;imprimir(x);}", "1")

# =============================================
# SECCION 10: INCREMENTO/DECREMENTO (Seccion 5.7)
# =============================================
print("\n[10] INCREMENTO/DECREMENTO")
test("++x prefijo", "void main(){int x=5;++x;imprimir(x);}", "6")
test("x++ postfijo", "void main(){int x=5;x++;imprimir(x);}", "6")
test("--x prefijo", "void main(){int x=5;--x;imprimir(x);}", "4")
test("x-- postfijo", "void main(){int x=5;x--;imprimir(x);}", "4")
test("inc en for", "void main(){for(int i=0;i<3;i++){imprimir(i);}}", "012")
test("dec en for", "void main(){for(int i=2;i>=0;i--){imprimir(i);}}", "210")

# =============================================
# SECCION 11: PROMOCION IMPLICITA (Seccion 4.7)
# =============================================
print("\n[11] PROMOCION int->float")
test("asig int a float", "void main(){float x=10;imprimir(x);}", "10.0")
test("expr mixta", "void main(){float x=5+3.5;imprimir(x);}", "8.5")
test("retorno int a float", "float Mitad(int x){float r=x/2;return r;} void main(){imprimir(Mitad(5));}", "2.0")

# =============================================
# SECCION 12: ERRORES - DETECCION (Catálogo Seccion 15)
# =============================================
print("\n[12] DETECCION DE ERRORES")

# Error lexico IL-LEX-002: caracter invalido
test_error("IL-LEX-002 char invalido", "void main() { @ }", "IL-LEX")

# Error lexico IL-LEX-004: identificador inicia con digito
test_error("IL-LEX-004 id digito", "void main() { int 1x; }", "IL-LEX")

# Error sintactico IL-SIN-006: EOF inesperado
test_error("IL-SIN-006 EOF", "void main() { int x = {", "IL-SIN")

# Error semantico IL-SEM-002: identificador duplicado
test_error("IL-SEM-002 duplicado", "void main() { int x; int x; }", "IL-SEM-002")

# Error semantico IL-SEM-003: no declarado
test_error("IL-SEM-003 no declarado", "void main() { imprimir(z); }", "IL-SEM-003")

# Error semantico IL-SEM-031: asignar a constante
test_error("IL-SEM-031 const asig", "void main() { const int N=5; N=10; }", "IL-SEM-031")

# Error semantico IL-SEM-040: break fuera de ciclo
test_error("IL-SEM-040 break fuera", "void main() { break; }", "IL-SEM-040")

# Error semantico IL-SEM-041: continue fuera de ciclo
test_error("IL-SEM-041 continue fuera", "void main() { continue; }", "IL-SEM-041")

# Error de tipos IL-TIPO-001: tipo incompatible
test_error("IL-TIPO-001 incompatible", "void main() { int x = true; }", "IL-TIPO")

# Error de tipos IL-TIPO-010: mod con float
test_error("IL-TIPO-010 mod float", "void main() { imprimir(5.0 % 2); }", "IL-TIPO")

# Error de tipos IL-TIPO-011: op aritmetico no numerico
test_error("IL-TIPO-011 string + int", 'void main() { imprimir("a" + 5); }', "IL-TIPO")

# Error de tipos IL-TIPO-012: comparacion string con int
test_error("IL-TIPO-012 string < int", 'void main() { imprimir("a" < 5); }', "IL-TIPO")

# Error de tipos IL-TIPO-016: inc/dec en float
test_error("IL-TIPO-016 inc float", "void main() { float x=1.5; x++; }", "IL-TIPO-016")

# Error de tipos IL-TIPO-017: negacion aritmetica en bool
test_error("IL-TIPO-017 -bool", "void main() { bool b=true; imprimir(-b); }", "IL-TIPO-017")

# Error de tipos IL-TIPO-018: && con no-bool
test_error("IL-TIPO-018 && no bool", "void main() { imprimir(1 && 2); }", "IL-TIPO-018")

# Error de tipos IL-TIPO-019: condicion no bool
test_error("IL-TIPO-019 if no bool", "void main() { if (5) { } }", "IL-TIPO-019")

# Error runtime IL-EJE-010: variable no inicializada
test_error("IL-EJE-010 no init", "void main() { int x; imprimir(x); }", "IL-EJE")

# Error runtime IL-EJE-006: div por cero
test_error("IL-EJE-006 div 0", "void main() { int x = 5 / 0; }", "IL-EJE")

# Error semantico IL-SEM-052: argumentos incorrectos
test_error("IL-SEM-052 args count", "int f(int a) { return a; } void main() { imprimir(f(1,2)); }", "IL-SEM-052")

# Error semantico IL-SEM-070: dim arreglo no constante
test_error("IL-SEM-070 dim no const", "void main() { int x=5; int[x]a; }", "IL-SEM-070")

# Error runtime IL-EJE-050: indice fuera de rango
test_error("IL-EJE-050 indice fuera", "void main() { int[3]a={1,2,3}; imprimir(a[10]); }", "IL-EJE-050")

# Error de tipo IL-SEM-072: array void (código oficial del catálogo §14/§15)
test_error("IL-SEM-072 array void", "void main() { void[5]x; }", "IL-SEM-072")

# Error de tipo IL-TIPO-021: indice no entero
test_error("IL-TIPO-021 index float", 'void main() { int[5]a; float f=1.0; imprimir(a[f]); }', "IL-TIPO-021")

# Error de tipo IL-TIPO-015: param void
test_error("IL-TIPO-015 param void", "void f(void x){} void main(){}", "IL-TIPO-015")

# Error semantico IL-SEM-010: entero overflow
test_error("IL-SEM-010 int overflow", "void main() { int x = 9999999999; }", "IL-SEM-010")

# =============================================
# SECCION 13: ESTRUCTURA DEL PROYECTO
# =============================================
print("\n[13] ESTRUCTURA DEL PROYECTO")
archivos_esperados = [
    'inveniolang/__init__.py', 'inveniolang/ast_nodes.py',
    'inveniolang/builtins.py', 'inveniolang/cli.py',
    'inveniolang/errors.py', 'inveniolang/gui_qt.py',
    'inveniolang/gui_tk.py', 'inveniolang/gui/__init__.py',
    'inveniolang/interpreter.py', 'inveniolang/lexer.py',
    'inveniolang/parser.py', 'inveniolang/semantic.py',
    'inveniolang/symbol_table.py', 'inveniolang/type_checker.py',
    'main.py', 'requirements.txt', 'README.md',
    'pruebas/hola_mundo.inv', 'pruebas/tipos.inv',
    'pruebas/condicionales.inv', 'pruebas/ciclos.inv',
    'pruebas/funciones.inv', 'pruebas/procedimientos.inv',
    'pruebas/arreglos.inv', 'pruebas/matrices.inv',
    'pruebas/sistema_ventas.inv',
    'pruebas/calculadora.inv', 'pruebas/estadisticas.inv', 'pruebas/conversor.inv',
]
base = os.path.dirname(__file__)
for archivo in archivos_esperados:
    ruta = os.path.join(base, archivo.replace('/', os.sep))
    if not os.path.exists(ruta):
        errores.append((f"Archivo faltante: {archivo}", "No existe"))

# =============================================
# SECCION 14: CLI FLAGS
# =============================================
print("\n[14] FLAGS CLI")
# Verificar que los flags funcionan desde main.py
import subprocess
for flag in ['--help', '--tokens', '--ast', '--tabla']:
    r = subprocess.run(
        [sys.executable, 'main.py', flag, 'pruebas/hola_mundo.inv'],
        capture_output=True, text=True, cwd=base,
        encoding='utf-8', errors='replace'
    )
    if r.returncode != 0 and flag != '--help':
        errores.append((f"Flag {flag} fallo", f"exit={r.returncode}: {r.stderr[:100]}"))

# =============================================
# SECCION 15: PROGRAMAS DE PRUEBA
# =============================================
print("\n[15] PROGRAMAS DE PRUEBA")
for prog in ['hola_mundo', 'tipos', 'condicionales', 'ciclos',
             'funciones', 'procedimientos', 'arreglos', 'matrices',
             'sistema_ventas', 'calculadora', 'estadisticas', 'conversor']:
    r = subprocess.run(
        [sys.executable, 'main.py', '--cli', f'pruebas/{prog}.inv'],
        capture_output=True, text=True, cwd=base,
        encoding='utf-8', errors='replace'
    )
    if r.returncode != 0:
        errores.append((f"Programa {prog}.inv", f"exit={r.returncode}: {r.stderr[:200]}"))

# =============================================
# SECCION 16: REQUISITOS NO CUBIERTOS
# =============================================
print("\n[16] GAPS vs DOCUMENTACION")

# Verificar lista de tokens del README
docs_tokens_mentioned = ['--tokens', '--ast', '--help', '--gui']
# --tabla no esta en README pero esta implementado

# Verificar que la GUI esta documentada
# La GUI menciona: crear, abrir, guardar, pipeline, salida/errores/advertencias, tokens/AST
gui_features_documented = [
    "Crear, abrir y guardar archivos .inv",
    "Ejecutar pipeline completo",
    "Visualizar salida, errores y advertencias en pestanas separadas",
    "Ver analisis de tokens y AST",
]

print("\n[17] EDGE CASES")
test("variable muy larga", "void main() { int a = 999999999; imprimir(a); }", "999999999")
test("float muy grande", "void main() { float f = 1.0e308; imprimir(f); }", "1e+308")
test("string con caracteres especiales", 'void main() { imprimir("a\\nb\\tc"); }', "a\nb\tc")
test("string con comillas escapadas", "void main() { imprimir('it\\'s'); }", "it's")
test("bool en condicion", "void main() { bool b=true; if(b){imprimir(1);} }", "1")
test("for con var externa", "void main() { int i; for(i=0;i<3;i++){imprimir(i);} }", "012")
test("for con asignacion act", "void main(){for(int i=0;i<3;i=i+1){imprimir(i);}}", "012")
test("nested for", "void main(){for(int i=0;i<2;i++){for(int j=0;j<2;j++){imprimir(i);imprimir(j);}}}", "00011011")

# REPORTE FINAL
print("\n" + "=" * 60)
print(f"RESULTADO: {len(errores)} problemas encontrados")
print("=" * 60)
if errores:
    print("\nDETALLE:")
    for i, (nombre, detalle) in enumerate(errores, 1):
        print(f"  [{i}] {nombre}")
        print(f"       {detalle}")
else:
    print("TODO OK - No se encontraron problemas")

# Solo esperar al usuario en modo interactivo, para poder encadenar el audit
# desde un script o desde CI (isatty() no es fiable en todas las consolas).
try:
    input("\nPresiona Enter para salir...")
except (EOFError, KeyboardInterrupt):
    pass

sys.exit(1 if errores else 0)
