"""Suite de conformidad de InvenioLang 1.0.

Cada caso proviene de un ejemplo o de un valor esperado NORMATIVO de la
especificacion (docs/*.docx). La Seccion 18.1 declara que los codigos de error
del catalogo son estables entre versiones y que los programas de referencia de
la Seccion 17 son casos de prueba permanentes: esta suite es la red que hace
cumplir ambas garantias.

Uso:
    python pruebas/conformidad.py            # todo
    python pruebas/conformidad.py catalogo   # solo un grupo
    python pruebas/conformidad.py -v         # detalle de los casos que pasan

Codigo de salida 0 si todo conforma, 1 si hay divergencias.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang.lexer import Lexer
from inveniolang.parser import Parser
from inveniolang.errors import ErrorManager
from inveniolang.semantic import SemanticAnalyzer
from inveniolang.type_checker import TypeChecker
from inveniolang.interpreter import Interpreter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_PRUEBAS = os.path.join(RAIZ, 'pruebas')

# Envoltorio para casos que solo necesitan un cuerpo de main
M = 'void main() {\n%s\n}\n'


def analizar(codigo, ejecutar=False, entrada=None):
    """Corre el pipeline y devuelve (codigos, salida).

    `codigos` reune errores y advertencias de todas las fases alcanzadas. El
    pipeline se detiene en la primera fase con errores, conforme a la regla de
    prioridad de la Seccion 15.8.2 (lexico > sintactico > semantico > tipos).
    """
    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(codigo, 't.inv')
    salida = ''
    if not em.hay_errores():
        p = Parser(lx, em)
        ast, em = p.analizar(codigo, 't.inv')
        if ast is not None and not em.hay_errores():
            sem = SemanticAnalyzer(em)
            tabla = sem.analizar(ast)
            if not em.hay_errores():
                TypeChecker(em, tabla).verificar(ast)
                if ejecutar and not em.hay_errores():
                    interp = Interpreter(em, tabla)
                    interp.max_iteraciones = 100000
                    try:
                        salida = ''.join(
                            interp.interpretar(ast, entrada, usar_stdin=False))
                    except Exception as e:          # pragma: no cover
                        return ['EXCEPCION:' + type(e).__name__], ''
    codigos = [e.codigo for e in em.errores] + [w.codigo for w in em.warnings]
    return codigos, salida


# ============================================================================
# GRUPO 1 — Catalogo de errores (Seccion 15)
# Cada caso: (referencia, codigo esperado, fuente)
# "OK" significa que el programa debe analizarse sin errores ni advertencias.
# ============================================================================

CATALOGO = [
    # --- Lexicos (Seccion 2.14 / 15.2) ---
    ('§2.14 LEX-002 caracter invalido', 'IL-LEX-002', M % 'int x = 1 @ 2;'),
    ('§2.4 LEX-004 ident inicia con digito', 'IL-LEX-004', M % 'int 1contador = 1;'),
    ('§2.4 LEX-005 caracter no ASCII', 'IL-LEX-005', M % 'int a\u00f1o = 1;'),
    ('§2.5 LEX-006 palabra reservada', 'IL-LEX-006', M % 'int while = 1;'),
    ('§2.5 LEX-006 reservada futura', 'IL-LEX-006', M % 'int function = 1;'),
    ('§2.6 LEX-007 subrayado en entero', 'IL-LEX-007', M % 'int x = 1_000;'),
    ('§2.6 LEX-008 base no decimal', 'IL-LEX-008', M % 'int x = 0xFF;'),
    ('§2.7 LEX-009 real .5', 'IL-LEX-009', M % 'float x = .5;'),
    ('§2.7 LEX-009 real 5.', 'IL-LEX-009', M % 'float x = 5.;'),
    ('§2.7 LEX-009 real 1e10', 'IL-LEX-009', M % 'float x = 1e10;'),
    ('§2.7 LEX-009 exponente vacio', 'IL-LEX-009', M % 'float x = 1.0e;'),
    ('§2.8 LEX-011 escape desconocido', 'IL-LEX-011', M % 'string s = "mal \\q escape";'),
    ('§2.8 LEX-012 texto no terminado', 'IL-LEX-012', M % 'string s = "sin cerrar'),
    ('§2.8 LEX-013 delimitadores distintos', 'IL-LEX-013', M % 'string s = "abre doble\';'),
    ('§2.12 LEX-014 comentario sin cerrar', 'IL-LEX-014', 'void main(){}\n/* sin cerrar'),
    ('§2.3 tab vertical es espacio', 'OK', 'void main(){\x0bint x = 1;\x0b}'),
    ('§2.1 UTF-8 en literal', 'OK', M % 'imprimir("\u00c1\u00d1O \u2713");'),
    ('§2.2 mayusculas: IF no es if', 'OK', M % 'int IF = 1; imprimir(IF);'),

    # --- Sintacticos (Seccion 15.3) ---
    ('§3.3 SIN-005 llave sobrante', 'IL-SIN-005', 'void main(){\n int x=1;\n}\n}\n'),
    ('§3.3 SIN-006 llave sin cerrar', 'IL-SIN-006', 'void main(){\n if(true){\n imprimir("ok");\n'),
    ('§3.4 SIN-010 falta punto y coma', 'IL-SIN-010', M % 'int y = 5\nimprimir(y);'),
    ('§3.4 SIN-011 ; tras bloque', 'IL-SIN-011', M % 'if (true) {\nimprimir("ok");\n};'),
    ('§3.4 SIN-012 ; aislado', 'IL-SIN-012', M % ';'),
    ('§5.1 SIN-015 declaracion multiple', 'IL-SIN-015', M % 'int a, b;'),
    ('§5.3 SIN-020 asignacion encadenada', 'IL-SIN-020', M % 'int a; int b; int c; a = b = c;'),
    ('§7.1 SIN-025 print sin argumentos', 'IL-SIN-025', M % 'imprimir();'),
    ('§7.1 SIN-026 print con varios args', 'IL-SIN-026', M % 'imprimir("a", "b");'),
    ('§7.2 SIN-027 read con expresion', 'IL-SIN-027', M % 'int x; leer(x + 1);'),
    ('§8.1 SIN-030 if sin parentesis', 'IL-SIN-030', M % 'int x=1; if x > 0 { }'),
    ('§8.1 SIN-031 if sin llaves', 'IL-SIN-031', M % 'int x=1; if (x>0) x++;'),
    ('§8.2 SIN-032 else huerfano', 'IL-SIN-032', M % 'sino { }'),
    ('§8.2 SIN-032 else sin if previo', 'IL-SIN-032', M % 'int x=1; sino { }'),
    ('§8.2 SIN-033 instruccion entre then y else', 'IL-SIN-033',
     M % 'int x=1; si(x>0){ imprimir(1); } x=1; sino { imprimir(2); }'),
    ('§8.2 if-else valido no dispara nada', 'OK',
     M % 'int x=1; si(x>0){ imprimir(1); } sino { imprimir(2); }'),
    ('§9.1 SIN-035 while sin parentesis', 'IL-SIN-035', M % 'int x=1; while x < 5 { }'),
    ('§9.2 SIN-040 for sin separadores', 'IL-SIN-040', M % 'for (int i=0  i<5; i++) { }'),
    ('§10.2 SIN-050 subrutina local', 'IL-SIN-050', 'void main(){ void g(){} }'),
    ('§12.6 SIN-070 asignar arreglo entero', 'IL-SIN-070', M % 'int[3] a; int[3] b; b = a;'),
    ('§13.4 SIN-080 matriz con un indice', 'IL-SIN-080', M % 'int[2][2] m; int x = m[1];'),
    ('§13.6 SIN-081 tres dimensiones', 'IL-SIN-081', M % 'int[2][2][2] cubo;'),

    # --- Semanticos (Seccion 15.4) ---
    ('§3.5 SEM-002 identificador duplicado', 'IL-SEM-002', M % 'int c = 0;\nint c = 1;'),
    ('§3.2 SEM-002 main duplicada', 'IL-SEM-002', 'void main(){}\nvoid main(){}'),
    ('§14.1 SEM-003 no declarado', 'IL-SEM-003', M % 'int y; y = z + 1;'),
    ('§5.1 SEM-004 autorreferencia', 'IL-SEM-004', M % 'int x = x + 1;'),
    ('§14.4 SEM-005 lvalue invalido', 'IL-SEM-005', 'void main(){ int x; 5 = x; }'),
    ('§4.2 SEM-010 literal fuera de rango', 'IL-SEM-010', M % 'int x = 99999999999;'),
    ('§3.2 SEM-020 main ausente', 'IL-SEM-020', 'void calcular(){ imprimir("x"); }'),
    ('§3.2 SEM-021 main con tipo', 'IL-SEM-021', 'int main() { return 0; }'),
    ('§3.2 SEM-022 main con parametros', 'IL-SEM-022', 'void main(int argc) { imprimir(argc); }'),
    ('§3.2 SEM-023 return con valor en main', 'IL-SEM-023', 'void main() { return 0; }'),
    ('§5.4 SEM-030 constante sin init', 'IL-SEM-030', M % 'const int N;'),
    ('§5.4 SEM-031 asignar a constante', 'IL-SEM-031', M % 'const int MAX = 10; MAX = 5;'),
    ('§5.4 SEM-031 ++ sobre constante', 'IL-SEM-031', M % 'const int MAX = 1; MAX++;'),
    ('§5.4 SEM-032 init no constante', 'IL-SEM-032',
     'int f(){return 1;}\nvoid main(){ const int N = f(); }'),
    ('§9.4 SEM-040 break fuera de ciclo', 'IL-SEM-040', M % 'break;'),
    ('§9.4 SEM-041 continue fuera de ciclo', 'IL-SEM-041', M % 'continue;'),
    ('§10.4 SEM-050 ruta sin return', 'IL-SEM-050',
     'int f(bool c){ if(c) { return 1; } }\nvoid main(){ imprimir(f(true)); }'),
    ('§10.2 SEM-051 void usada como funcion', 'IL-SEM-051',
     'void f(){ return 1; }\nvoid main(){ int x = f(); }'),
    ('§11.5 SEM-061 void como instruccion', 'IL-SEM-061',
     'void f(){ return 1; }\nvoid main(){ f(); }'),
    ('§11.4 SEM-060 void sin valor en expresion', 'IL-SEM-060',
     'void p(){ imprimir(1); }\nvoid main(){ int x; x = p() + 1; }'),
    ('§10.5 SEM-052 argumentos incorrectos', 'IL-SEM-052',
     'int f(int a,int b){return a;}\nvoid main(){ imprimir(f(1,2,3)); }'),
    ('§10.4 SEM-053 return sin expresion', 'IL-SEM-053',
     'int f(){ return; }\nvoid main(){ imprimir(f()); }'),
    ('§11.4 SEM-060 procedimiento en expresion', 'IL-SEM-060',
     'void p(){}\nvoid main(){ int x; x = p() + 1; }'),
    ('§11.5 SEM-061 return con valor en proc', 'IL-SEM-061',
     'void p(int n){ return n; }\nvoid main(){ p(1); }'),
    ('§12.2 SEM-070 dimension por variable', 'IL-SEM-070', M % 'int n = 5; int[n] arr;'),
    ('§12.2 SEM-071 dimension cero', 'IL-SEM-071', M % 'int[0] arr;'),
    ('§12.2 SEM-072 arreglo de void', 'IL-SEM-072', M % 'void[5] arr;'),
    ('§12.3 SEM-073 inicializadores incorrectos', 'IL-SEM-073', M % 'int[4] a = {1,2};'),
    ('§19.11 SEM-080 redefinir integrada', 'IL-SEM-080',
     'int int_to_string(int n){ return n; }\nvoid main(){ }'),
    ('§19.1 SEM-080 integrada como local', 'IL-SEM-080', M % 'int int_to_string = 1;'),
    ('§19.11 SEM-081 argumento incompatible', 'IL-SEM-081', M % 'int x = string_to_int(true);'),

    # --- Tipos (Seccion 15.5) ---
    ('§4.7 TIPO-001 incompatible', 'IL-TIPO-001', M % 'int x = "hola";'),
    ('§4.9 TIPO-001 float a int', 'IL-TIPO-001', M % 'float c = 3.14; int d = c;'),
    ('§4.3 TIPO-010 modulo sobre float', 'IL-TIPO-010', M % 'float r = 7.5 % 2.0;'),
    ('§5.3 TIPO-010 %= sobre float', 'IL-TIPO-010', M % 'float f = 7.5; f %= 2.0;'),
    ('§4.4 TIPO-011 aritmetica sobre string', 'IL-TIPO-011', M % 'string e = "hola" - "ho";'),
    ('§5.3 TIPO-011 -= sobre string', 'IL-TIPO-011', M % 'string s = "hola"; s -= "la";'),
    ('§4.4 TIPO-012 orden sobre string', 'IL-TIPO-012', M % 'bool o = "abc" < "def";'),
    ('§4.5 TIPO-013 aritmetica sobre bool', 'IL-TIPO-013', M % 'bool e = true + false;'),
    ('§4.5 TIPO-014 bool a numerico', 'IL-TIPO-014', M % 'int n = true;'),
    ('§4.6 TIPO-015 variable void', 'IL-TIPO-015', M % 'void resultado;'),
    ('§5.3 TIPO-016 ++ sobre float', 'IL-TIPO-016', M % 'float f = 1.0; f++;'),
    ('§6.1 TIPO-017 ! sobre int', 'IL-TIPO-017', M % 'bool b = !5;'),
    ('§6.3 TIPO-018 && con no bool', 'IL-TIPO-018', M % 'bool b = 1 && 2;'),
    ('§6.6 TIPO-019 condicion no bool', 'IL-TIPO-019', M % 'if (5) { }'),
    ('§7.1 TIPO-020 print de void', 'IL-TIPO-020', 'void p(){}\nvoid main(){ imprimir(p()); }'),
    ('§12.4 TIPO-021 indice no entero', 'IL-TIPO-021', M % 'int[3] a; int x = a[2.5];'),

    # --- Advertencias (Seccion 15.7) ---
    ('§3.5 WARN-001 ocultamiento', 'IL-WARN-001',
     'int x = 100;\nvoid main(){ int x = 200; imprimir(x); }'),
    ('§5.2 WARN-002 lectura sin inicializar', 'IL-WARN-002', M % 'int x; imprimir(x);'),
    ('§5.2 WARN-002 no avisa si se asigna', 'OK', M % 'int x; x = 5; imprimir(x);'),
    ('§6.6 WARN-003 divisor literal cero', 'IL-WARN-003', M % 'int x = 5 / 0;'),
    ('§9.1 WARN-010 while(true) sin break', 'IL-WARN-010', M % 'while (true) { }'),
    ('§9.1 WARN-010 no avisa si hay break', 'OK', M % 'while (true) { break; }'),
    ('§9.1 WARN-010 no avisa con const false', 'OK',
     'const bool SALIR = false;\nvoid main(){ while (SALIR) { } }'),
    ('§10.5 WARN-020 retorno descartado', 'IL-WARN-020',
     'int calcular(int n){ return n; }\nvoid main(){ calcular(5); }'),
    ('§12.4 WARN-030 indice literal fuera de rango', 'IL-WARN-030',
     M % 'int[5] a; int x = a[10];'),
    ('§17.3 WARN-040 declaracion postfija', 'IL-WARN-040',
     M % 'float temps[5] = {1.0,2.0,3.0,4.0,5.0};'),

    # --- Bilinguismo (Seccion 2.5, erratas de docs/ERRATAS.md) ---
    ('§2.5.2 retornar es palabra reservada', 'OK',
     'int f(){ retornar 1; }\nvoid main(){ imprimir(f()); }'),
    ('§2.5.3 mezcla de idiomas', 'OK',
     M % 'entero x = 1; si (x > 0) { imprimir("ok"); } sino { imprimir("no"); }'),
    ('§16.11 main no es reservada', 'OK', M % 'int principal = 1; imprimir(principal);'),
]


# ============================================================================
# GRUPO 2 — Semantica de expresiones (Secciones 4, 5.3, 6)
# Cada caso: (referencia, fuente, salida esperada)
# ============================================================================

EXPRESIONES = [
    ('§4.2 division trunca hacia cero',
     M % 'imprimir(7/2);imprimir(" ");imprimir(-7/2);imprimir(" ");'
         'imprimir(7/-2);imprimir(" ");imprimir(-7/-2);', '3 -3 -3 3'),
    ('§6.1 modulo con signo del dividendo',
     M % 'imprimir(7%3);imprimir(" ");imprimir(-7%3);imprimir(" ");imprimir(7%-3);', '1 -1 1'),
    ('§4.9 promocion int a float', M % 'int a=5; float b=2.0; imprimir(a+b);', '7.0'),
    ('§4.9 argumento int a parametro float',
     'float f(float x){ return x; }\nvoid main(){ imprimir(f(3)); }', '3.0'),
    ('§5.3.3 postfijo b = a++', M % 'int a=3; int b=a++; imprimir(b);imprimir(" ");imprimir(a);', '3 4'),
    ('§5.3.3 prefijo c = ++a', M % 'int a=4; int c=++a; imprimir(c);imprimir(" ");imprimir(a);', '5 5'),
    ('§5.3.3 ++ como instruccion', M % 'int i=5; i++; ++i; i--; imprimir(i);', '6'),
    ('§5.3.2 compuestos sobre int', M % 'int s=10;s+=5;s-=3;s*=2;s/=4;s%=4;imprimir(s);', '2'),
    ('§5.3.2 += concatena texto', M % 'string m="Hola"; m+=", mundo"; imprimir(m);', 'Hola, mundo'),
    ('§5.3.2 += sobre elemento de arreglo',
     M % 'int[3] v={1,2,3}; v[0]+=10; imprimir(v[0]);', '11'),
    ('§5.3.2 *= sobre elemento de matriz',
     M % 'int[2][2] m={{1,2},{3,4}}; m[0][0]*=5; imprimir(m[0][0]);', '5'),
    ('§6.3.1 cortocircuito && evita division',
     M % 'int d=0; bool s=(d!=0)&&(10/d>1); imprimir(s);', 'false'),
    ('§6.3.1 cortocircuito || no evalua derecha',
     'int g=0;\nint f(){ g=1; return 1; }\nvoid main(){ bool b=verdadero||(f()==1); imprimir(g); }', '0'),
    ('§6.3.1 && no evalua derecha si izq falso',
     'int g=0;\nint f(){ g=1; return 1; }\nvoid main(){ bool b=falso&&(f()==1); imprimir(g); }', '0'),
    ('§6.3.2 doble negacion', M % 'bool a=verdadero; imprimir(!!a);', 'true'),
    ('§6.4 precedencia * sobre +', M % 'imprimir(2+3*4);', '14'),
    ('§6.4 parentesis alteran el orden', M % 'imprimir((2+3)*4);', '20'),
    ('§6.4 && precede a ||', M % 'imprimir(verdadero || falso && falso);', 'true'),
    ('§6.4 negacion de relacional', M % 'imprimir(!(3>5) && (2<4));', 'true'),
    ('§6.5 asociatividad izquierda resta', M % 'imprimir(10-3-2);', '5'),
    ('§6.5 asociatividad izquierda division', M % 'imprimir(16/4/2);', '2'),
    ('§6.5 doble negacion unaria', M % 'int c=5; imprimir(- -c);', '5'),
    ('§6.5 misma precedencia izq a der', M % 'imprimir(1 < 2 == verdadero);', 'true'),
    ('§6.6.1 orden de evaluacion izq a der',
     'int g=0;\nint inc(){ g+=1; return g; }\nvoid main(){ imprimir(inc()+inc()); }', '3'),
    ('§6.6.3 argumentos izq a der',
     'int sumar(int a,int b){return a+b;}\nvoid main(){ int x=3; imprimir(sumar(x+1,x*2)); }', '10'),
    ('§7.1.2 imprimir bool en ingles', M % 'imprimir(verdadero);', 'true'),
    ('§4.4 concatenacion de texto', M % 'imprimir("Hola, " + "mundo");', 'Hola, mundo'),
    ('§5.4 constantes encadenadas',
     'const int BASE=10;\nconst int DOBLE=BASE*2;\nconst string P="INV-";\n'
     'const string C=P+"001";\nvoid main(){ imprimir(DOBLE); imprimir(" "); imprimir(C); }',
     '20 INV-001'),
    ('§5.6 locales no persisten entre llamadas',
     'int contador(){ int n=0; n+=1; return n; }\n'
     'void main(){ imprimir(contador());imprimir(contador());imprimir(contador()); }', '111'),
    ('§12.2 arreglos se pasan por referencia',
     'void mod(int[] a){ a[0]=99; }\nvoid main(){ int[3] x={1,2,3}; mod(x); imprimir(x[0]); }', '99'),
    ('§5.2.3 global int por defecto 0', 'int g;\nvoid main(){ imprimir(g); }', '0'),
    ('§5.2.3 global string por defecto vacio',
     'string s;\nvoid main(){ imprimir("["); imprimir(s); imprimir("]"); }', '[]'),
]


# ============================================================================
# GRUPO 3 — Errores de ejecucion y funciones integradas (Secciones 4.2, 9.1, 19)
# Cada caso: (referencia, codigo o salida esperada, fuente)
# ============================================================================

EJECUCION = [
    ('§4.2 EJE-001 desbordamiento de int', 'IL-EJE-001',
     M % 'int a=2000000000; imprimir(a*2);'),
    ('§4.2 el maximo de int es valido', '2147483647', M % 'imprimir(2147483647);'),
    ('§4.3 EJE-002 division real entre cero', 'IL-EJE-002', M % 'float a=1.0; float b=0.0; imprimir(a/b);'),
    ('§6.6.4 EJE-006 division entera entre cero', 'IL-EJE-006',
     M % 'int a=10; int b=0; imprimir(a/b);'),
    ('§19.4 EJE-003 float_to_int desborda', 'IL-EJE-003', M % 'imprimir(float_to_int(9.0e18));'),
    ('§19.4 float_to_int acepta el minimo', '-2147483648',
     M % 'imprimir(float_to_int(-2147483648.0));'),
    ('§19.4 float_to_int trunca hacia cero', '-3', M % 'imprimir(float_to_int(-3.7));'),
    ('§19.7 EJE-004 texto no numerico', 'IL-EJE-004', M % 'imprimir(string_to_int("abc"));'),
    ('§19.7 EJE-004 fuera del rango de int', 'IL-EJE-004', M % 'imprimir(string_to_int("99999999999"));'),
    ('§19.7 EJE-004 subrayado no admitido', 'IL-EJE-004', M % 'imprimir(string_to_int("1_000"));'),
    ('§19.7 signo y espacios admitidos', '7', M % 'imprimir(string_to_int("  +7 "));'),
    ('§19.8 EJE-005 real no convertible', 'IL-EJE-005', M % 'imprimir(string_to_float("abc"));'),
    ('§19.8 notacion exponencial', '1500.0', M % 'imprimir(string_to_float("1.5e3"));'),
    ('§19.10 EJE-022 "1" no es booleano', 'IL-EJE-022', M % 'imprimir(string_to_bool("1"));'),
    ('§19.10 EJE-022 "si" no es booleano', 'IL-EJE-022', M % 'imprimir(string_to_bool("si"));'),
    ('§19.10 acepta la forma espanola', 'true', M % 'imprimir(string_to_bool("verdadero"));'),
    ('§19.9 bool_to_string siempre en ingles', 'true', M % 'imprimir(bool_to_string(verdadero));'),
    ('§5.2.2 EJE-010 local sin inicializar', 'IL-EJE-010', M % 'int x; imprimir(x);'),
    ('§9.1 EJE-030 ciclo infinito while', 'IL-EJE-030', M % 'while(verdadero){ int z=1; }'),
    ('§9.2 EJE-030 ciclo infinito for', 'IL-EJE-030', M % 'para(;;){ int z=1; }'),
    ('§10.6 EJE-040 recursion sin caso base', 'IL-EJE-040',
     'int f(int n){ return f(n+1); }\nvoid main(){ imprimir(f(1)); }'),
    ('§12.4 EJE-050 indice fuera de rango', 'IL-EJE-050',
     M % 'int[5] a; int i=10; a[i]=1;'),
    ('§12.4 EJE-050 a traves de parametro', 'IL-EJE-050',
     'void f(int[] a){ imprimir(a[99]); }\nvoid main(){ int[3] x={1,2,3}; f(x); }'),
    ('§13.4 EJE-050 en matriz', 'IL-EJE-050',
     M % 'int[2][2] m={{1,2},{3,4}}; int i=5; imprimir(m[i][0]);'),
    ('§7.2 EJE-020 entrada no convertible a int', 'IL-EJE-020', M % 'int n; leer(n); imprimir(n);'),
]

# El caso de lectura necesita entrada simulada
ENTRADAS = {'§7.2 EJE-020 entrada no convertible a int': ['abc']}


# ============================================================================
# GRUPO 4 — Programas de referencia (Seccion 17 y Apendice E)
# La Seccion 18.1 los declara casos de prueba permanentes.
# Cada caso: (archivo, lista de fragmentos que deben aparecer en la salida)
# ============================================================================

REFERENCIA = [
    ('hola_mundo.inv', ['Hola, mundo!']),
    ('tipos.inv', ['Entero:  42', 'Real:    3.14', 'Texto:   InvenioLang',
                   'Logico:  true', 'Promovido: 42.0', 'Como texto: 42', 'PI: 3.14159']),
    ('condicionales.inv', ['-5.0 grados: Bajo cero', '10.0 grados: Frio',
                           '20.0 grados: Templado', '30.0 grados: Calido',
                           '40.0 grados: Muy caliente', 'Temperatura ideal']),
    ('ciclos.inv', ['Cuenta: 5 4 3 2 1', 'Suma cuadrados 1-5: 55',
                    'Impares: 1 3 5 7 9', 'Primer múltiplo de 7: 7']),
    ('funciones.inv', ['0! = 1', '5! = 120', '7! = 5040',
                       'Primos hasta 20: 2 3 5 7 11 13 17 19',
                       '2^10 = 1024.0', '7 es impar']),
    ('procedimientos.inv', ['Reporte de Calificaciones', '[APROBADO]  Ana',
                            '[REPROBADO] Carlos', '[APROBADO]  María']),
    ('arreglos.inv', ['Original:  [ 64, 25, 12, 22, 11, 90, 38 ]',
                      'Ordenado:  [ 11, 12, 22, 25, 38, 64, 90 ]',
                      '25 en posición: 3', '99 en posición: -1']),
    ('matrices.inv', ['Matriz original:', 'Suma fila 0: 6', 'Suma fila 1: 15',
                      'Suma fila 2: 24', 'Matriz transpuesta:']),
    ('sistema_ventas.inv', ['ANÁLISIS DE VENTAS ANUALES', 'Enero: 10200.0 ✓',
                            'Febrero: 9400.0', 'Meses sobre meta: 11',
                            'Mejor mes:        Diciembre (22200.0)',
                            'Estado: AÑO EXITOSO']),
    ('calculadora.inv', []),
    ('estadisticas.inv', ['Estadísticas:']),
    ('conversor.inv', []),
    # Apendice E
    ('escapes.inv', ['Tabulador: A\tB', 'Comilla doble: "hola"',
                     "Comilla simple: 'hola'", 'Barra invertida: C:\\ruta']),
    ('calculadora_es.inv', ['Máximo: 30', 'Suma: 42', 'Producto: 360']),
    ('guardia.inv', ['5.0', 'Error: división por cero', 'Negativa', 'Adulto']),
    ('hanoi.inv', ['Mover disco 1 de 1 a 3', 'Mover disco 3 de 1 a 3',
                   'Total de movimientos: 7']),
]


# ============================================================================
# Ejecucion de la suite
# ============================================================================

class Resultados:
    def __init__(self):
        self.ok = 0
        self.fallos = []

    def registrar(self, bien, referencia, esperado, obtenido):
        if bien:
            self.ok += 1
        else:
            self.fallos.append((referencia, esperado, obtenido))

    @property
    def total(self):
        return self.ok + len(self.fallos)


def _sin_diagnosticos(codigos):
    return not codigos


def correr_catalogo(res, verboso):
    print('\n[1] CATALOGO DE ERRORES (§15)')
    for referencia, esperado, fuente in CATALOGO:
        codigos, _ = analizar(fuente)
        bien = _sin_diagnosticos(codigos) if esperado == 'OK' else esperado in codigos
        res.registrar(bien, referencia, esperado, codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado}  obtenido={codigos}')


def correr_expresiones(res, verboso):
    print('\n[2] SEMANTICA DE EXPRESIONES (§4, §5.3, §6)')
    for referencia, fuente, esperado in EXPRESIONES:
        codigos, salida = analizar(fuente, ejecutar=True)
        bien = salida == esperado and not [c for c in codigos if '-WARN-' not in c]
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')


def correr_ejecucion(res, verboso):
    print('\n[3] EJECUCION Y FUNCIONES INTEGRADAS (§4.2, §9.1, §19)')
    for referencia, esperado, fuente in EJECUCION:
        entrada = ENTRADAS.get(referencia)
        codigos, salida = analizar(fuente, ejecutar=True, entrada=entrada)
        bien = esperado in codigos if esperado.startswith('IL-') else salida == esperado
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')


def correr_codificacion(res, verboso):
    """IL-LEX-001: un archivo que no sea UTF-8 valido debe rechazarse (§2.1).

    Se prueba sobre un archivo real porque el error ocurre al leerlo, antes de
    que el lexer vea un solo caracter.
    """
    import tempfile
    from inveniolang.cli import leer_fuente

    print('\n[5] CODIFICACION DEL ARCHIVO FUENTE (§2.1)')
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, 'binario.inv')
        with open(ruta, 'wb') as f:
            f.write(b'void main(){ imprimir("\xff\xfe\xff"); }')

        em = ErrorManager()
        codigo, fallo = leer_fuente(ruta, em)
        codigos = [e.codigo for e in em.errores]
        bien = codigo is None and fallo == 1 and 'IL-LEX-001' in codigos
        res.registrar(bien, '§2.1 LEX-001 archivo no UTF-8', 'IL-LEX-001', codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} §2.1 LEX-001 archivo no UTF-8')

        # Un archivo UTF-8 con caracteres fuera de ASCII SI debe leerse
        ruta_ok = os.path.join(tmp, 'acentos.inv')
        with open(ruta_ok, 'w', encoding='utf-8') as f:
            f.write('void main(){ imprimir("ÁÑO ✓"); }')
        em2 = ErrorManager()
        codigo2, fallo2 = leer_fuente(ruta_ok, em2)
        bien2 = codigo2 is not None and fallo2 is None and not em2.errores
        res.registrar(bien2, '§2.1 UTF-8 con no-ASCII es valido', 'sin error',
                      [e.codigo for e in em2.errores])
        if verboso or not bien2:
            print(f'  {"ok  " if bien2 else "FALLA"} §2.1 UTF-8 con no-ASCII es valido')


def correr_referencia(res, verboso):
    print('\n[4] PROGRAMAS DE REFERENCIA (§17, Apendice E)')
    for archivo, fragmentos in REFERENCIA:
        ruta = os.path.join(DIR_PRUEBAS, archivo)
        if not os.path.exists(ruta):
            res.registrar(False, archivo, 'el archivo debe existir', 'no encontrado')
            print(f'  FALLA {archivo}: no encontrado')
            continue
        with open(ruta, encoding='utf-8') as f:
            fuente = f.read()
        codigos, salida = analizar(fuente, ejecutar=True)
        errores = [c for c in codigos if '-WARN-' not in c]
        faltan = [t for t in fragmentos if t not in salida]
        bien = not errores and not faltan
        res.registrar(bien, archivo, 'ejecuta y produce la salida de §17',
                      errores or faltan)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {archivo}')
            if errores:
                print(f'         errores={errores}')
            if faltan:
                print(f'         faltan en la salida: {faltan}')


GRUPOS = {
    'catalogo': correr_catalogo,
    'expresiones': correr_expresiones,
    'ejecucion': correr_ejecucion,
    'codificacion': correr_codificacion,
    'referencia': correr_referencia,
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    verboso = '-v' in sys.argv or '--verbose' in sys.argv
    grupos = args or list(GRUPOS)

    desconocidos = [g for g in grupos if g not in GRUPOS]
    if desconocidos:
        print(f'Grupo desconocido: {", ".join(desconocidos)}')
        print(f'Disponibles: {", ".join(GRUPOS)}')
        return 2

    print('=' * 64)
    print('SUITE DE CONFORMIDAD - InvenioLang 1.0')
    print('=' * 64)

    res = Resultados()
    for nombre in grupos:
        GRUPOS[nombre](res, verboso)

    print('\n' + '=' * 64)
    if res.fallos:
        print(f'DIVERGENCIAS: {len(res.fallos)} de {res.total} casos')
        print('=' * 64)
        for referencia, esperado, obtenido in res.fallos:
            print(f'  {referencia}')
            print(f'     esperado: {esperado}')
            print(f'     obtenido: {obtenido}')
        return 1

    print(f'CONFORME - {res.ok} de {res.total} casos')
    print('=' * 64)
    return 0


if __name__ == '__main__':
    sys.exit(main())
