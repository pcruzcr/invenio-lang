"""Auditoria completa: verifica cada requisito documentado vs codigo."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from inveniolang.errors import ErrorManager
from inveniolang.interpreter import Interpreter
from inveniolang.lexer import Lexer
from inveniolang.parser import Parser
from inveniolang.semantic import SemanticAnalyzer
from inveniolang.type_checker import TypeChecker

errores = []

def caso(nombre, codigo, esperado=None, error_esperado=None, entrada=None):
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

def caso_error(nombre, codigo, error_code):
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
        interp.interpretar(ast)
        for e in em.errores:
            if error_code in e.codigo:
                return
        errores.append((nombre, f"No se encontro error {error_code}. Errores: {[e.formato_oficial() for e in em.errores]}"))
    except Exception as e:
        errores.append((nombre, f"Excepcion: {type(e).__name__}: {e}"))


def main() -> int:
    """Ejecuta la auditoría completa y retorna el código de salida.

    Antes todo este cuerpo corría al IMPORTAR el módulo (y pytest lo importa
    porque `_audit.py` figuraba en `python_files`), terminando en un input()
    que rompía la recolección con "reading from stdin while output is
    captured".
    """
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
    lexer = Lexer(em)
    lexer.build()
    for kw in keywords_esperadas:
        if kw not in lexer.keywords:
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
        if tok not in lexer.tokens:
            errores.append((f"Token faltante: {tok}", "No esta en lexer.tokens"))

    print(f"  Keywords: {len(keywords_esperadas)}/{len(keywords_esperadas)}")
    print(f"  Tokens:   {len(tokens_esperados)}/{len(tokens_esperados)}")

    # =============================================
    # SECCION 2: TIPOS DE DATOS (Seccion 4, Tabla 5)
    # =============================================
    print("\n[2] TIPOS DE DATOS")
    caso("int literal", "void main() { imprimir(42); }", "42")
    caso("float literal", "void main() { imprimir(3.14); }", "3.14")
    caso("string literal", 'void main() { imprimir("hola"); }', "hola")
    caso("bool true", "void main() { imprimir(true); }", "true")
    caso("bool false", "void main() { imprimir(false); }", "false")
    caso("int var + init", "void main() { int x = 10; imprimir(x); }", "10")
    caso("float var + init", "void main() { float y = 3.14; imprimir(y); }", "3.14")
    caso("string var + init", 'void main() { string s = "ok"; imprimir(s); }', "ok")
    caso("bool var + init", "void main() { bool b = true; imprimir(b); }", "true")
    caso("void procedimiento", "void nada() { } void main() { nada(); }", "")
    caso("const int", "void main() { const int N = 7; imprimir(N); }", "7")
    caso("const float", "void main() { const float P = 3.14; imprimir(P); }", "3.14")
    caso("const string", 'void main() { const string S = "fijo"; imprimir(S); }', "fijo")
    caso("const bool", "void main() { const bool B = true; imprimir(B); }", "true")

    # =============================================
    # SECCION 3: PALABRAS RESERVADAS BILINGUES
    # =============================================
    print("\n[3] PALABRAS BILINGUES")
    caso("si (if)", "void main() { si (true) { imprimir(1); } }", "1")
    caso("sino (else)", "void main() { si (false) { imprimir(1); } sino { imprimir(2); } }", "2")
    caso("mientras (while)", "void main() { int i=0; mientras(i<2){imprimir(i);i=i+1;} }", "01")
    caso("para (for)", "void main() { para(int i=0; i<2; i++) { imprimir(i); } }", "01")
    caso("imprimir (print)", 'void main() { imprimir("x"); }', "x")
    caso("leer (read)", "void main() { entero x = 5; leer(x); imprimir(x); }", "42", entrada=["42"])  # read lee de la entrada (§7.2)
    caso("entero (int)", "void main() { entero x = 5; imprimir(x); }", "5")
    caso("real (float)", "void main() { real x = 3.14; imprimir(x); }", "3.14")
    caso("texto (string)", 'void main() { texto s = "ok"; imprimir(s); }', "ok")
    caso("logico (bool)", "void main() { logico b = verdadero; imprimir(b); }", "true")
    caso("vacio (void)", "vacio foo() { } vacio main() { foo(); }", "")
    caso("constante (const)", "void main() { constante int N = 5; imprimir(N); }", "5")
    caso("verdadero (true)", "void main() { imprimir(verdadero); }", "true")
    caso("falso (false)", "void main() { imprimir(falso); }", "false")
    caso("romper (break)", "void main() { for(int i=0;i<3;i++){si(i==1){romper;}imprimir(i);} }", "0")
    caso("continuar (continue)", "void main() { for(int i=0;i<3;i++){si(i==1){continuar;}imprimir(i);} }", "02")

    # =============================================
    # SECCION 4: OPERADORES Y PRECEDENCIA (Seccion 16.7, Tabla 13)
    # =============================================
    print("\n[4] OPERADORES Y PRECEDENCIA")
    caso("suma", "void main() { imprimir(2+3); }", "5")
    caso("resta", "void main() { imprimir(5-3); }", "2")
    caso("mult", "void main() { imprimir(4*3); }", "12")
    caso("div entera", "void main() { imprimir(7/3); }", "2")
    caso("mod", "void main() { imprimir(7%3); }", "1")
    caso("suma float", "void main() { imprimir(1.5+2.5); }", "4.0")
    caso("precedencia +*", "void main() { imprimir(2+3*4); }", "14")
    caso("precedencia ()", "void main() { imprimir((2+3)*4); }", "20")
    caso("precedencia && ||", "void main() { imprimir(true || true && false); }", "true")
    caso("precedencia == +", "void main() { int x=5; imprimir(x==2+3); }", "true")
    caso("unario -", "void main() { imprimir(-5); }", "-5")
    caso("unario !", "void main() { imprimir(!true); }", "false")
    caso("relacional <", "void main() { imprimir(2<3); }", "true")
    caso("relacional >", "void main() { imprimir(5>3); }", "true")
    caso("relacional <=", "void main() { imprimir(3<=3); }", "true")
    caso("relacional >=", "void main() { imprimir(4>=3); }", "true")
    caso("igualdad ==", "void main() { imprimir(3==3); }", "true")
    caso("igualdad !=", "void main() { imprimir(3!=4); }", "true")

    # =============================================
    # SECCION 5: ESTRUCTURAS DE CONTROL (Seccion 6-9)
    # =============================================
    print("\n[5] ESTRUCTURAS DE CONTROL")
    caso("if true", "void main() { if(true){imprimir(1);} }", "1")
    caso("if false", "void main() { if(false){imprimir(1);} }", "")
    caso("if-else then", "void main() { if(true){imprimir(1);}else{imprimir(2);} }", "1")
    caso("if-else else", "void main() { if(false){imprimir(1);}else{imprimir(2);} }", "2")
    caso("if anidado", "void main() { int x=5; if(x>0){if(x<10){imprimir(1);}} }", "1")
    caso("while", "void main(){int i=0; while(i<3){imprimir(i);i=i+1;}}", "012")
    caso("while false", "void main(){while(false){imprimir(1);}}", "")
    caso("for basico", "void main(){for(int i=0;i<3;i++){imprimir(i);}}", "012")
    caso("for sin init", "void main(){int i=0;for(;i<3;i++){imprimir(i);}}", "012")
    caso("for sin cond", "void main(){for(int i=0;;i++){if(i>=3){break;}imprimir(i);}}", "012")
    caso("for sin act", "void main(){for(int i=0;i<3;){imprimir(i);i=i+1;}}", "012")
    caso("break en for", "void main(){for(int i=0;i<5;i++){if(i==2){break;}imprimir(i);}}", "01")
    caso("break en while", "void main(){int i=0;while(i<5){if(i==2){break;}imprimir(i);i=i+1;}}", "01")
    caso("continue en for", "void main(){for(int i=0;i<5;i++){if(i%2==0){continue;}imprimir(i);}}", "13")
    caso("continue en while", "void main(){int i=0;while(i<5){i=i+1;if(i%2==0){continue;}imprimir(i-1);}}", "024")

    # =============================================
    # SECCION 6: FUNCIONES Y PROCEDIMIENTOS (Seccion 10-11)
    # =============================================
    print("\n[6] FUNCIONES Y PROCEDIMIENTOS")
    caso("funcion ret int", "int suma(int a,int b){return a+b;} void main(){imprimir(suma(3,4));}", "7")
    caso("funcion ret float", "float Mitad(float x){return x/2.0;} void main(){imprimir(Mitad(10.0));}", "5.0")
    caso("funcion ret bool", "bool esPos(int n){return n>0;} void main(){imprimir(esPos(5));}", "true")
    caso("funcion ret string", "string msg(int n){if(n>0){return\"pos\";}return\"neg\";} void main(){imprimir(msg(5));}", "pos")
    caso("funcion recursiva", "int fact(int n){if(n<=1){return 1;}return n*fact(n-1);} void main(){imprimir(fact(5));}", "120")
    caso("procedimiento void", "void saludar(){imprimir(\"hola\");} void main(){saludar();}", "hola")
    caso("procedimiento con param", "void mostrar(int x){imprimir(x);} void main(){mostrar(99);}", "99")
    caso("funcion multi params", "int mul(int a,int b,int c){return a*b*c;} void main(){imprimir(mul(2,3,4));}", "24")
    caso("funcion sin parametros", "int cinco(){return 5;} void main(){imprimir(cinco());}", "5")
    caso("funcion llamada en expr", "int doble(int x){return x*2;} void main(){imprimir(doble(3)+1);}", "7")

    # =============================================
    # SECCION 7: ARREGLOS Y MATRICES (Seccion 12)
    # =============================================
    print("\n[7] ARREGLOS Y MATRICES")
    caso("array decl init", "void main(){int[3]a={1,2,3};imprimir(a[1]);}", "2")
    caso("array acceso y escritura", "void main(){int[5]a;a[0]=10;a[1]=20;imprimir(a[0]);}", "10")
    caso("array const tam", "const int N=3;void main(){int[N]a={10,20,30};imprimir(a[2]);}", "30")
    caso("array float", "void main(){float[3]a={1.5,2.5,3.5};imprimir(a[1]);}", "2.5")
    caso("array param por ref", "void set(int[]arr,int v){arr[0]=v;} void main(){int[2]a={5,7};set(a,99);imprimir(a[0]);}", "99")
    caso("matrix decl init", "void main(){int[2][2]m={{1,2},{3,4}};imprimir(m[1][1]);}", "4")
    caso("matrix acceso", "void main(){int[2][2]m;m[0][1]=99;imprimir(m[0][1]);}", "99")
    caso("matrix const tam", "const int F=2;const int C=2;void main(){int[F][C]m={{1,2},{3,4}};imprimir(m[0][0]);}", "1")

    # =============================================
    # SECCION 8: FUNCIONES INTEGRADAS (Seccion 19)
    # =============================================
    print("\n[8] FUNCIONES INTEGRADAS")
    caso("int_a_float", "void main(){imprimir(int_a_float(42));}", "42.0")
    caso("float_a_int", "void main(){imprimir(float_a_int(3.9));}", "3")
    caso("int_a_texto", 'void main(){imprimir(int_a_texto(42));}', "42")
    caso("float_a_texto", 'void main(){imprimir(float_a_texto(3.14));}', "3.14")
    caso("bool_a_texto true", 'void main(){imprimir(bool_a_texto(true));}', "true")
    caso("bool_a_texto false", 'void main(){imprimir(bool_a_texto(false));}', "false")

    # =============================================
    # SECCION 9: ASIGNACIONES COMPUESTAS (Seccion 5.6)
    # =============================================
    print("\n[9] ASIGNACIONES COMPUESTAS")
    caso("asig =", "void main(){int x=5;x=10;imprimir(x);}", "10")
    caso("asig +=", "void main(){int x=5;x+=3;imprimir(x);}", "8")
    caso("asig -=", "void main(){int x=5;x-=3;imprimir(x);}", "2")
    caso("asig *=", "void main(){int x=5;x*=3;imprimir(x);}", "15")
    caso("asig /=", "void main(){int x=10;x/=3;imprimir(x);}", "3")
    caso("asig %=", "void main(){int x=10;x%=3;imprimir(x);}", "1")

    # =============================================
    # SECCION 10: INCREMENTO/DECREMENTO (Seccion 5.7)
    # =============================================
    print("\n[10] INCREMENTO/DECREMENTO")
    caso("++x prefijo", "void main(){int x=5;++x;imprimir(x);}", "6")
    caso("x++ postfijo", "void main(){int x=5;x++;imprimir(x);}", "6")
    caso("--x prefijo", "void main(){int x=5;--x;imprimir(x);}", "4")
    caso("x-- postfijo", "void main(){int x=5;x--;imprimir(x);}", "4")
    caso("inc en for", "void main(){for(int i=0;i<3;i++){imprimir(i);}}", "012")
    caso("dec en for", "void main(){for(int i=2;i>=0;i--){imprimir(i);}}", "210")

    # =============================================
    # SECCION 11: PROMOCION IMPLICITA (Seccion 4.7)
    # =============================================
    print("\n[11] PROMOCION int->float")
    caso("asig int a float", "void main(){float x=10;imprimir(x);}", "10.0")
    caso("expr mixta", "void main(){float x=5+3.5;imprimir(x);}", "8.5")
    caso("retorno int a float", "float Mitad(int x){float r=x/2;return r;} void main(){imprimir(Mitad(5));}", "2.0")

    # =============================================
    # SECCION 12: ERRORES - DETECCION (Catálogo Seccion 15)
    # =============================================
    print("\n[12] DETECCION DE ERRORES")

    # Error lexico IL-LEX-002: caracter invalido
    caso_error("IL-LEX-002 char invalido", "void main() { @ }", "IL-LEX")

    # Error lexico IL-LEX-004: identificador inicia con digito
    caso_error("IL-LEX-004 id digito", "void main() { int 1x; }", "IL-LEX")

    # Error sintactico IL-SIN-006: EOF inesperado
    caso_error("IL-SIN-006 EOF", "void main() { int x = {", "IL-SIN")

    # Error semantico IL-SEM-002: identificador duplicado
    caso_error("IL-SEM-002 duplicado", "void main() { int x; int x; }", "IL-SEM-002")

    # Error semantico IL-SEM-003: no declarado
    caso_error("IL-SEM-003 no declarado", "void main() { imprimir(z); }", "IL-SEM-003")

    # Error semantico IL-SEM-031: asignar a constante
    caso_error("IL-SEM-031 const asig", "void main() { const int N=5; N=10; }", "IL-SEM-031")

    # Error semantico IL-SEM-040: break fuera de ciclo
    caso_error("IL-SEM-040 break fuera", "void main() { break; }", "IL-SEM-040")

    # Error semantico IL-SEM-041: continue fuera de ciclo
    caso_error("IL-SEM-041 continue fuera", "void main() { continue; }", "IL-SEM-041")

    # Error de tipos IL-TIPO-001: tipo incompatible
    caso_error("IL-TIPO-001 incompatible", "void main() { int x = true; }", "IL-TIPO")

    # Error de tipos IL-TIPO-010: mod con float
    caso_error("IL-TIPO-010 mod float", "void main() { imprimir(5.0 % 2); }", "IL-TIPO")

    # Error de tipos IL-TIPO-011: op aritmetico no numerico
    caso_error("IL-TIPO-011 string + int", 'void main() { imprimir("a" + 5); }', "IL-TIPO")

    # Error de tipos IL-TIPO-012: comparacion string con int
    caso_error("IL-TIPO-012 string < int", 'void main() { imprimir("a" < 5); }', "IL-TIPO")

    # Error de tipos IL-TIPO-016: inc/dec en float
    caso_error("IL-TIPO-016 inc float", "void main() { float x=1.5; x++; }", "IL-TIPO-016")

    # Error de tipos IL-TIPO-017: negacion aritmetica en bool
    caso_error("IL-TIPO-017 -bool", "void main() { bool b=true; imprimir(-b); }", "IL-TIPO-017")

    # Error de tipos IL-TIPO-018: && con no-bool
    caso_error("IL-TIPO-018 && no bool", "void main() { imprimir(1 && 2); }", "IL-TIPO-018")

    # Error de tipos IL-TIPO-019: condicion no bool
    caso_error("IL-TIPO-019 if no bool", "void main() { if (5) { } }", "IL-TIPO-019")

    # Error runtime IL-EJE-010: variable no inicializada
    caso_error("IL-EJE-010 no init", "void main() { int x; imprimir(x); }", "IL-EJE")

    # Error runtime IL-EJE-006: div por cero
    caso_error("IL-EJE-006 div 0", "void main() { int x = 5 / 0; }", "IL-EJE")

    # Error semantico IL-SEM-052: argumentos incorrectos
    caso_error("IL-SEM-052 args count", "int f(int a) { return a; } void main() { imprimir(f(1,2)); }", "IL-SEM-052")

    # Error semantico IL-SEM-070: dim arreglo no constante
    caso_error("IL-SEM-070 dim no const", "void main() { int x=5; int[x]a; }", "IL-SEM-070")

    # Error runtime IL-EJE-050: indice fuera de rango
    caso_error("IL-EJE-050 indice fuera", "void main() { int[3]a={1,2,3}; imprimir(a[10]); }", "IL-EJE-050")

    # Error de tipo IL-SEM-072: array void (código oficial del catálogo §14/§15)
    caso_error("IL-SEM-072 array void", "void main() { void[5]x; }", "IL-SEM-072")

    # Error de tipo IL-TIPO-021: indice no entero
    caso_error("IL-TIPO-021 index float", 'void main() { int[5]a; float f=1.0; imprimir(a[f]); }', "IL-TIPO-021")

    # Error de tipo IL-TIPO-015: param void
    caso_error("IL-TIPO-015 param void", "void f(void x){} void main(){}", "IL-TIPO-015")

    # Error semantico IL-SEM-010: entero overflow
    caso_error("IL-SEM-010 int overflow", "void main() { int x = 9999999999; }", "IL-SEM-010")

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

    # INV-1030: estas dos listas se declaraban y no se comprobaban (F841).
    # Ahora sí: cada flag y cada función de la GUI deben figurar en el README.
    readme = open(os.path.join(base, 'README.md'), encoding='utf-8').read()
    for flag in ['--tokens', '--ast', '--help', '--gui']:
        if flag not in readme:
            errores.append((f"README no documenta {flag}", "Flag implementado sin documentar"))
    for funcion in [
        "Crear, abrir y guardar archivos",
        "Visualizar salida, errores y advertencias",
    ]:
        if funcion not in readme:
            errores.append((f"README no documenta: {funcion}", "Funcion de la GUI sin documentar"))

    print("\n[17] EDGE CASES")
    caso("variable muy larga", "void main() { int a = 999999999; imprimir(a); }", "999999999")
    caso("float muy grande", "void main() { float f = 1.0e308; imprimir(f); }", "1e+308")
    caso("string con caracteres especiales", 'void main() { imprimir("a\\nb\\tc"); }', "a\nb\tc")
    caso("string con comillas escapadas", "void main() { imprimir('it\\'s'); }", "it's")
    caso("bool en condicion", "void main() { bool b=true; if(b){imprimir(1);} }", "1")
    caso("for con var externa", "void main() { int i; for(i=0;i<3;i++){imprimir(i);} }", "012")
    caso("for con asignacion act", "void main(){for(int i=0;i<3;i=i+1){imprimir(i);}}", "012")
    caso("nested for", "void main(){for(int i=0;i<2;i++){for(int j=0;j<2;j++){imprimir(i);imprimir(j);}}}", "00011011")

    # INV-4409: restos de una copia vieja (módulos y carpetas retirados), con
    # la misma lista que scripts/limpiar_obsoletos.py y el motivo de cada uno.
    print("\n[18] RESTOS DE VERSIONES ANTERIORES")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "limpiar_obsoletos", os.path.join(base, "scripts", "limpiar_obsoletos.py"))
    limpiador = importlib.util.module_from_spec(spec)
    sys.modules["limpiar_obsoletos"] = limpiador  # dataclass necesita su módulo
    spec.loader.exec_module(limpiador)
    presentes = limpiador.encontrar(limpiador.Path(base))
    if presentes:
        errores.append(("Restos de versiones anteriores", limpiador.mensaje(presentes)))

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

    # Solo esperar al usuario en una consola interactiva (doble clic en
    # Windows): en CI, en un pipe o bajo pytest, input() bloqueaba o fallaba.
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nPresiona Enter para salir...")
        except (EOFError, KeyboardInterrupt):
            pass

    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
