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

from inveniolang import flujo
from inveniolang import ir as ir_mod
from inveniolang import ll1 as ll1_demo
from inveniolang.errors import ErrorManager
from inveniolang.interpreter import Interpreter
from inveniolang.lexer import Lexer
from inveniolang.parser import Parser
from inveniolang.semantic import SemanticAnalyzer
from inveniolang.type_checker import TypeChecker

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
    # 'function'/'funcion' se activaron en la Etapa 12.5/12.6 (funciones de
    # primera clase) -- este caso ahora usa 'procedure', que sigue
    # reservada-futura (sin uso en la gramatica todavia).
    ('§2.5 LEX-006 reservada futura', 'IL-LEX-006', M % 'int procedure = 1;'),
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
    ('§7.2 EJE-021 entrada no convertible a float', 'IL-EJE-021', M % 'float f; leer(f); imprimir(f);'),

    # ---- Auditoria adicional: codigos de la libreria estandar sin caso
    # previo (Etapa 6/10), verificados uno a uno contra builtins.py ----
    ('§19 EST-010 subcadena con rango invalido', 'IL-EST-010',
     M % 'imprimir(subcadena("hola", 2, 10));'),
    ('§19 EST-011 caracter_en fuera de rango', 'IL-EST-011',
     M % 'imprimir(caracter_en("hola", 10));'),
    ('§19 EST-012 raiz_cuadrada de un negativo', 'IL-EST-012',
     M % 'imprimir(raiz_cuadrada(-4.0));'),
    ('§19 EST-013 elevar produce un resultado complejo', 'IL-EST-013',
     M % 'imprimir(elevar(-8.0, 0.5));'),
    ('§19 EST-014 azar con minimo mayor que maximo', 'IL-EST-014',
     M % 'imprimir(azar(10, 1));'),
    ('§10.3(E10) escribir_archivo con ruta invalida', 'IL-EST-016',
     M % 'imprimir(escribir_archivo("carpeta_inexistente_xyz/a.txt", "x"));'),
    ('§10.3(E10) agregar_archivo con ruta invalida', 'IL-EST-017',
     M % 'imprimir(agregar_archivo("carpeta_inexistente_xyz/a.txt", "x"));'),
]

# Los casos de lectura necesitan entrada simulada
ENTRADAS = {
    '§7.2 EJE-020 entrada no convertible a int': ['abc'],
    '§7.2 EJE-021 entrada no convertible a float': ['abc'],
}


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
# GRUPO 6 — POO / InvenioLang 2.0 (docs/InvenioLang_2.0_POO.md)
# Cada caso: (referencia, codigo IL-POO-* esperado O salida esperada, fuente)
# Mismo criterio que EJECUCION: si `esperado` empieza con "IL-" se busca ese
# codigo entre los diagnosticos; si no, se compara la salida producida.
# ============================================================================

CLASES = [
    ('§6 programa de referencia (Animal/Perro)', 'GuauRex',
     '''
clase Animal {
    privado texto nombre;
    publico entero edad;
    Animal(texto n, entero e) { this.nombre = n; this.edad = e; }
    publico texto obtener_nombre() { return this.nombre; }
    publico texto sonido() { return "..."; }
}
clase Perro hereda Animal {
    Perro(texto n, entero e) { super(n, e); }
    publico texto sonido() { return "Guau"; }
}
void main() {
    Animal a = nuevo Perro("Rex", 3);
    imprimir(a.sonido());
    imprimir(a.obtener_nombre());
}
'''),
    ('§8 despacho virtual con 3 niveles y super.metodo()', 'C-B-A',
     '''
clase A { publico texto f() { return "A"; } }
clase B hereda A { publico texto f() { return "B-" + super.f(); } }
clase C hereda B { publico texto f() { return "C-" + super.f(); } }
void main() { A x = nuevo C(); imprimir(x.f()); }
'''),
    ('§5 constructor implicito hereda del padre', '42',
     '''
clase A { publico entero v; A() { this.v = 42; } }
clase B hereda A { }
void main() { B b = nuevo B(); imprimir(entero_a_texto(b.v)); }
'''),
    ('§1 composicion (atributo de tipo clase)', '300',
     '''
clase Motor {
    publico entero hp;
    Motor(entero h) { this.hp = h; }
    publico entero obtener_hp() { return this.hp; }
}
clase Auto {
    privado Motor motor;
    Auto(entero h) { this.motor = nuevo Motor(h); }
    publico entero obtener_hp() { Motor m = this.motor; return m.obtener_hp(); }
}
void main() { Auto a = nuevo Auto(300); imprimir(entero_a_texto(a.obtener_hp())); }
'''),
    ('§4 imprimir un objeto (NombreClase(campo=valor,...))', 'Punto(x=1, y=2)',
     '''
clase Punto {
    publico entero x;
    publico entero y;
    Punto(entero a, entero b) { this.x = a; this.y = b; }
}
void main() { Punto p = nuevo Punto(1, 2); imprimir(p); }
'''),
    ('§4 atributo con inicializador y sin inicializador', '10',
     '''
clase X { publico entero contador = 10; publico texto etiqueta; }
void main() { X x = nuevo X(); imprimir(entero_a_texto(x.contador)); }
'''),
    ('§4 paso por referencia (igual que los arreglos, §12.2)', '99',
     '''
clase Caja { publico entero valor; }
void modificar(Caja c) { c.valor = 99; }
void main() {
    Caja a = nuevo Caja();
    a.valor = 1;
    modificar(a);
    imprimir(entero_a_texto(a.valor));
}
'''),
    ('§5 POO-001 clase duplicada', 'IL-POO-001',
     'clase A { }\nclase A { }\nvoid main() { }\n'),
    ('§3 POO-002 padre inexistente', 'IL-POO-002',
     'clase A hereda NoExiste { }\nvoid main() { }\n'),
    ('§3 POO-003 herencia circular', 'IL-POO-003',
     'clase A hereda B { }\nclase B hereda A { }\nvoid main() { }\n'),
    ('§5 POO-004 miembro duplicado', 'IL-POO-004',
     'clase A { publico entero x; publico entero x; }\nvoid main() { }\n'),
    ('§3 POO-005 acceso a privado desde fuera', 'IL-POO-005',
     '''
clase X { privado entero secreto; }
void main() { X x = nuevo X(); imprimir(entero_a_texto(x.secreto)); }
'''),
    ('§5 POO-006 miembro inexistente', 'IL-POO-006',
     '''
clase A { publico entero x; }
void main() { A a = nuevo A(); imprimir(entero_a_texto(a.y)); }
'''),
    ('§5 POO-007 aridad de constructor', 'IL-POO-007',
     'clase A { A(entero x) { this.v = x; } publico entero v; }\n'
     'void main() { A a = nuevo A(); }\n'),
    ('§5 POO-008 tipo de argumento de constructor', 'IL-POO-008',
     'clase A { A(entero x) { } }\nvoid main() { A a = nuevo A("no es entero"); }\n'),
    ('§5 POO-009 super(...) fuera de la primera instruccion', 'IL-POO-009',
     '''
clase A { A() { } }
clase B hereda A { B() { entero x; super(); } }
void main() { }
'''),
    ('§5 POO-010 super(...) en clase sin padre', 'IL-POO-010',
     'clase A { A() { super(); } }\nvoid main() { }\n'),
    ('§6 POO-011 este/this fuera de un metodo', 'IL-POO-011',
     'void main() { imprimir(entero_a_texto(this.x)); }\n'),
    ('§6 POO-012 padre/super en una clase sin padre', 'IL-POO-012',
     'clase A { publico entero f() { return padre.f(); } }\nvoid main() { }\n'),
    ('§5 POO-013 asignacion entre clases no emparentadas', 'IL-POO-013',
     'clase A { }\nclase B { }\nvoid main() { A a = nuevo B(); }\n'),
    ('§3 POO-014 sobrescritura con tipo de retorno distinto', 'IL-POO-014',
     'clase A { publico entero f() { return 1; } }\n'
     'clase B hereda A { publico texto f() { return "x"; } }\n'
     'void main() { }\n'),
    # Nota (Etapa 7 -- sobrecarga de métodos): antes de la Etapa 7 CUALQUIER
    # firma distinta en un método del mismo nombre en una subclase era
    # IL-POO-015 (no existía la sobrecarga). Con sobrecarga, una firma que
    # no coincide con NINGUNA del padre (ej. entero vs texto) ya no es un
    # intento de sobrescritura roto -- es una sobrecarga nueva, válida. El
    # código IL-POO-015 ahora es específico: firma "casi igual" salvo un
    # tipo compatible por promoción (real->entero), que sí cuenta como
    # intento de sobrescritura con parámetros incompatibles.
    ('§3 POO-015 sobrescritura con parametros distintos', 'IL-POO-015',
     'clase A { publico entero f(real x) { return 1; } }\n'
     'clase B hereda A { publico entero f(entero x) { return 1; } }\n'
     'void main() { }\n'),
    ('§3 sobrecarga real: firma sin relación no es sobrescritura rota', 'ok',
     'clase A { publico entero f(entero x) { return x; } }\n'
     'clase B hereda A { publico entero f(texto x) { return 1; } }\n'
     'void main() { imprimir("ok"); }\n'),
    ('§1 POO-016 tipo desconocido', 'IL-POO-016', 'void main() { NoExiste n; }\n'),
    ('§5 POO-017 aridad de metodo', 'IL-POO-017',
     'clase A { publico entero suma(entero x, entero y) { return x + y; } }\n'
     'void main() { A a = nuevo A(); imprimir(entero_a_texto(a.suma(1))); }\n'),
    ('§5 POO-018 tipo de argumento de metodo', 'IL-POO-018',
     'clase A { publico entero f(entero x) { return x; } }\n'
     'void main() { A a = nuevo A(); imprimir(entero_a_texto(a.f("no es entero"))); }\n'),
    ('§4 POO-019 constructor con nombre distinto a la clase', 'IL-POO-019',
     'clase A { Otro() { } }\nvoid main() { }\n'),

    # --- Arreglos de objetos y nulo (Estructuras de Datos) ---
    ('§1(ED) arreglo de objetos: declarar, asignar, acceder a miembro', '5',
     '''
clase P { publico entero v; }
void main() {
    P arr[2];
    arr[0] = nuevo P();
    arr[0].v = 5;
    imprimir(entero_a_texto(arr[0].v));
}
'''),
    ('§1(ED) arreglo de objetos: llamada a metodo sobre elemento', 'hola',
     '''
clase P { publico texto saludo() { return "hola"; } }
void main() {
    P arr[1];
    arr[0] = nuevo P();
    imprimir(arr[0].saludo());
}
'''),
    ('§1(ED) forma prefija con clase no soportada (limitacion deliberada)', 'IL-SIN-010',
     'clase P { }\nvoid main() { P[3] arr; }\n'),
    ('§1(ED) autorreferencia de clase (nodo enlazado)', 'true',
     '''
clase Nodo { publico entero v; publico Nodo siguiente; }
void main() {
    Nodo a = nuevo Nodo();
    Nodo b = nuevo Nodo();
    a.siguiente = b;
    imprimir(a.siguiente == b);
}
'''),
    ('§1(ED) nulo: variable de clase sin asignar es nulo, no error', 'true',
     'clase Nodo { }\nvoid main() { Nodo n; imprimir(n == nulo); }\n'),
    ('§1(ED) nulo: recorrer hasta nulo detecta el final', '2',
     '''
clase Nodo { publico entero v; publico Nodo siguiente; }
void main() {
    Nodo a = nuevo Nodo();
    Nodo b = nuevo Nodo();
    a.siguiente = b;
    entero pasos = 0;
    Nodo actual = a;
    mientras (actual != nulo) { pasos = pasos + 1; actual = actual.siguiente; }
    imprimir(entero_a_texto(pasos));
}
'''),
    ('§1(ED) nulo comparado con primitivo es invalido', 'IL-TIPO-012',
     'void main() { bool b = (5 == nulo); }'),
]


# ============================================================================
# GRUPO 9 — Etapa 7: POO completo (abstractas, estaticos, sobrecarga, genericos)
# Mismo criterio que CLASES: "IL-" busca el codigo, si no compara la salida.
# ============================================================================

POO_COMPLETO = [
    # ---- Clases abstractas ----
    ('§1(E7) instanciar clase abstracta', 'IL-POO-020',
     'abstracta clase Figura { publico abstracto entero area(); }\n'
     'void main() { Figura f = nuevo Figura(); }\n'),
    ('§1(E7) subclase no implementa metodo abstracto heredado', 'IL-POO-021',
     'abstracta clase Figura { publico abstracto entero area(); }\n'
     'clase Circulo hereda Figura { }\n'
     'void main() { }\n'),
    ('§1(E7) metodo abstracto con cuerpo', 'IL-POO-022',
     'abstracta clase Figura { publico abstracto entero area() { return 0; } }\n'
     'void main() { }\n'),
    ('§1(E7) "abstracto" no es valido en un atributo', 'IL-POO-023',
     'abstracta clase Figura { publico abstracto entero x; }\n'
     'void main() { }\n'),
    ('§1(E7) metodo abstracto fuera de clase abstracta', 'IL-POO-024',
     'clase Figura { publico abstracto entero area(); }\n'
     'void main() { }\n'),
    ('§1(E7) polimorfismo con clase abstracta', 'Area: 25',
     'abstracta clase Figura {\n'
     '    publico abstracto entero area();\n'
     '    publico texto describir() { return "Area: " + entero_a_texto(this.area()); }\n'
     '}\n'
     'clase Cuadrado hereda Figura {\n'
     '    privado entero lado;\n'
     '    Cuadrado(entero l) { this.lado = l; }\n'
     '    publico entero area() { return this.lado * this.lado; }\n'
     '}\n'
     'void main() { Figura f = nuevo Cuadrado(5); imprimir(f.describir()); }\n'),

    # ---- Miembros estaticos ----
    ('§2(E7) contador estatico compartido entre instancias', '3',
     'clase Contador {\n'
     '    publico estatico entero total;\n'
     '    Contador() { Contador.total = Contador.total + 1; }\n'
     '}\n'
     'void main() {\n'
     '    Contador a = nuevo Contador(); Contador b = nuevo Contador();\n'
     '    Contador c = nuevo Contador();\n'
     '    imprimir(entero_a_texto(Contador.total));\n'
     '}\n'),
    ('§2(E7) metodo estatico de utilidad', '49',
     'clase MathUtil { publico estatico entero cuadrado(entero x) { return x * x; } }\n'
     'void main() { imprimir(entero_a_texto(MathUtil.cuadrado(7))); }\n'),
    ('§2(E7) this dentro de metodo estatico', 'IL-POO-025',
     'clase A { publico entero x; publico estatico void f() { this.x = 1; } }\n'
     'void main() { }\n'),
    ('§2(E7) acceso a miembro no estatico via nombre de clase', 'IL-POO-026',
     'clase A { publico entero x; }\n'
     'void main() { imprimir(entero_a_texto(A.x)); }\n'),

    # ---- Sobrecarga de metodos ----
    ('§3(E7) sobrecarga por cantidad y tipo de parametros', '5 9 holamundo',
     'clase Calculadora {\n'
     '    publico entero sumar(entero a, entero b) { return a + b; }\n'
     '    publico entero sumar(entero a, entero b, entero c) { return a + b + c; }\n'
     '    publico texto sumar(texto a, texto b) { return a + b; }\n'
     '}\n'
     'void main() {\n'
     '    Calculadora c = nuevo Calculadora();\n'
     '    imprimir(entero_a_texto(c.sumar(2, 3)));\n'
     '    imprimir(" ");\n'
     '    imprimir(entero_a_texto(c.sumar(2, 3, 4)));\n'
     '    imprimir(" ");\n'
     '    imprimir(c.sumar("hola", "mundo"));\n'
     '}\n'),
    ('§3(E7) ninguna sobrecarga coincide con los tipos', 'IL-POO-027',
     'clase A {\n'
     '    publico texto f(entero x) { return "e"; }\n'
     '    publico texto f(texto x) { return "t"; }\n'
     '}\n'
     'void main() { A a = nuevo A(); imprimir(a.f(true)); }\n'),

    # ---- Genericos ----
    ('§4(E7) Caja<T> con dos tipos distintos en el mismo programa', 'llena:42 hola',
     'clase Caja<T> {\n'
     '    privado T contenido;\n'
     '    publico void guardar(T v) { this.contenido = v; }\n'
     '    publico T obtener() { return this.contenido; }\n'
     '}\n'
     'void main() {\n'
     '    Caja<entero> cn = nuevo Caja<entero>();\n'
     '    cn.guardar(42);\n'
     '    imprimir("llena:");\n'
     '    imprimir(entero_a_texto(cn.obtener()));\n'
     '    imprimir(" ");\n'
     '    Caja<texto> ct = nuevo Caja<texto>();\n'
     '    ct.guardar("hola");\n'
     '    imprimir(ct.obtener());\n'
     '}\n'),
    ('§4(E7) plantilla generica sin especializar no es una clase', 'IL-POO-016',
     'clase Caja<T> { privado T x; }\n'
     'void main() { Caja c = nuevo Caja(); }\n'),
]


# ============================================================================
# GRUPO 10 — Etapa 10: cierre de brechas de Fase 1/Fase 2
# Sobrecarga de constructores, imprimir(objeto) personalizable (aTexto()).
# ============================================================================

ETAPA10 = [
    # ---- Sobrecarga de constructores ----
    ('§1(E10) sobrecarga de constructor por aridad', 'x=0 y=5 z=5 5',
     'clase Punto {\n'
     '    publico entero x; publico entero y;\n'
     '    Punto() { this.x = 0; this.y = 0; }\n'
     '    Punto(entero v) { this.x = v; this.y = v; }\n'
     '    Punto(entero a, entero b) { this.x = a; this.y = b; }\n'
     '}\n'
     'void main() {\n'
     '    Punto p1 = nuevo Punto();\n'
     '    Punto p2 = nuevo Punto(5);\n'
     '    Punto p3 = nuevo Punto(2, 3);\n'
     '    imprimir("x="); imprimir(entero_a_texto(p1.x));\n'
     '    imprimir(" y="); imprimir(entero_a_texto(p2.y));\n'
     '    imprimir(" z="); imprimir(entero_a_texto(p2.x));\n'
     '    imprimir(" "); imprimir(entero_a_texto(p3.x + p3.y));\n'
     '}\n'),
    ('§1(E10) sobrecarga de constructor por tipo, elige la correcta', 'texto:hola numero:9',
     'clase Caja {\n'
     '    publico texto t; publico entero n;\n'
     '    Caja(texto v) { this.t = v; this.n = 0; }\n'
     '    Caja(entero v) { this.t = ""; this.n = v; }\n'
     '}\n'
     'void main() {\n'
     '    Caja c1 = nuevo Caja("hola");\n'
     '    Caja c2 = nuevo Caja(9);\n'
     '    imprimir("texto:"); imprimir(c1.t);\n'
     '    imprimir(" numero:"); imprimir(entero_a_texto(c2.n));\n'
     '}\n'),
    ('§1(E10) padre(...) elige la sobrecarga del padre por tipo', '5 10.5',
     'clase Base {\n'
     '    publico entero x;\n'
     '    Base(entero v) { this.x = v; }\n'
     '    Base(real v) { this.x = 0; }\n'
     '}\n'
     'clase Hija hereda Base {\n'
     '    publico real y;\n'
     '    Hija(entero v, real w) { padre(v); this.y = w; }\n'
     '}\n'
     'void main() {\n'
     '    Hija h = nuevo Hija(5, 10.5);\n'
     '    imprimir(entero_a_texto(h.x)); imprimir(" "); imprimir(real_a_texto(h.y));\n'
     '}\n'),
    ('§1(E10) constructor duplicado con la misma firma', 'IL-POO-019',
     'clase A {\n'
     '    A(entero x) { }\n'
     '    A(entero y) { }\n'
     '}\n'
     'void main() { }\n'),
    ('§1(E10) ninguna sobrecarga de constructor coincide con los tipos', 'IL-POO-029',
     'clase A {\n'
     '    A(entero x) { }\n'
     '    A(texto x) { }\n'
     '}\n'
     'void main() { A a = nuevo A(true); }\n'),
    ('§1(E10) padre sin constructor de 0 argumentos y sin padre(...) explicito', 'IL-POO-007',
     'clase A {\n'
     '    publico entero x;\n'
     '    A(entero v) { this.x = v; }\n'
     '    A(entero v, entero w) { this.x = v + w; }\n'
     '}\n'
     'clase B hereda A { B() { } }\n'
     'void main() { }\n'),

    # ---- imprimir(objeto) personalizable con aTexto()/toString() ----
    ('§2(E10) aTexto() personaliza imprimir(objeto)', '(3, 4)',
     'clase Punto {\n'
     '    publico entero x; publico entero y;\n'
     '    Punto(entero a, entero b) { this.x = a; this.y = b; }\n'
     '    publico texto aTexto() {\n'
     '        return "(" + entero_a_texto(this.x) + ", " + entero_a_texto(this.y) + ")";\n'
     '    }\n'
     '}\n'
     'void main() { Punto p = nuevo Punto(3, 4); imprimir(p); }\n'),
    ('§2(E10) sin aTexto(), formato automatico de siempre', 'Caja(valor=7)',
     'clase Caja { publico entero valor; Caja(entero v) { this.valor = v; } }\n'
     'void main() { Caja c = nuevo Caja(7); imprimir(c); }\n'),
    ('§2(E10) aTexto() con despacho virtual (subclase sobrescribe)', 'Derivada especifico',
     'clase Base { publico texto aTexto() { return "Base generico"; } }\n'
     'clase Derivada hereda Base { publico texto aTexto() { return "Derivada especifico"; } }\n'
     'void main() { Base b = nuevo Derivada(); imprimir(b); }\n'),
    ('§2(E10) alias en ingles toString() tambien funciona', 'punto(1,1)',
     'clase P { publico texto toString() { return "punto(1,1)"; } }\n'
     'void main() { P p = nuevo P(); imprimir(p); }\n'),

    # ---- Libreria estandar: invertir_texto (auditoria final) ----
    ('§3(E10) invertir_texto detecta palindromo', 'true false',
     'void main() {\n'
     '    imprimir(invertir_texto("reconocer") == "reconocer");\n'
     '    imprimir(" ");\n'
     '    imprimir(invertir_texto("hola") == "hola");\n'
     '}\n'),
]


# ============================================================================
# GRUPO 11 — Etapa 11: patrones de diseno + mejoras finales de Fase 2
# Visibilidad de constructores (Singleton real).
# ============================================================================

ETAPA11 = [
    # ---- Visibilidad de constructores ----
    ('§1(E11) Singleton: constructor privado, misma instancia', '42 true',
     'clase Config {\n'
     '    publico estatico Config instancia;\n'
     '    publico entero valor;\n'
     '    privado constructor Config() { this.valor = 42; }\n'
     '    publico estatico Config obtenerInstancia() {\n'
     '        si (Config.instancia == nulo) { Config.instancia = nuevo Config(); }\n'
     '        return Config.instancia;\n'
     '    }\n'
     '}\n'
     'void main() {\n'
     '    Config c1 = Config.obtenerInstancia();\n'
     '    Config c2 = Config.obtenerInstancia();\n'
     '    imprimir(entero_a_texto(c1.valor)); imprimir(" "); imprimir(c1 == c2);\n'
     '}\n'),
    ('§1(E11) constructor privado no instanciable desde afuera', 'IL-POO-030',
     'clase Config { privado constructor Config() { } }\n'
     'void main() { Config c = nuevo Config(); }\n'),
    ('§1(E11) constructor privado no instanciable desde una subclase (padre implicito)', 'IL-POO-030',
     'clase A { privado constructor A() { } }\n'
     'clase B hereda A { B() { } }\n'
     'void main() { }\n'),
    ('§1(E11) constructor privado no instanciable via padre(...) explicito', 'IL-POO-030',
     'clase A { privado constructor A(entero x) { } }\n'
     'clase B hereda A { B(entero x) { padre(x); } }\n'
     'void main() { }\n'),
    ('§1(E11) constructor publico explicito funciona igual que el implicito', '9',
     'clase P { publico constructor P(entero v) { this.v = v; } publico entero v; }\n'
     'void main() { P p = nuevo P(9); imprimir(entero_a_texto(p.v)); }\n'),

    # ---- esIgual()/equals() personalizable ----
    ('§2(E11) esIgual() compara por valor, no por identidad', 'true false true',
     'clase Punto {\n'
     '    publico entero x; publico entero y;\n'
     '    Punto(entero a, entero b) { this.x = a; this.y = b; }\n'
     '    publico bool esIgual(Punto otro) { return this.x == otro.x && this.y == otro.y; }\n'
     '}\n'
     'void main() {\n'
     '    Punto p1 = nuevo Punto(1, 2); Punto p2 = nuevo Punto(1, 2); Punto p3 = nuevo Punto(9, 9);\n'
     '    imprimir(p1 == p2); imprimir(" "); imprimir(p1 == p3); imprimir(" "); imprimir(p1 != p3);\n'
     '}\n'),
    ('§2(E11) sin esIgual(), == sigue siendo identidad de referencia', 'false true',
     'clase A { publico entero v; A(entero v) { this.v = v; } }\n'
     'void main() {\n'
     '    A a1 = nuevo A(5); A a2 = nuevo A(5);\n'
     '    imprimir(a1 == a2); imprimir(" "); imprimir(a1 == a1);\n'
     '}\n'),
    ('§2(E11) objeto == nulo no invoca esIgual() (no rompe el chequeo de nulidad)', 'false true',
     'clase Punto {\n'
     '    publico entero x;\n'
     '    Punto(entero v) { this.x = v; }\n'
     '    publico bool esIgual(Punto otro) { return this.x == otro.x; }\n'
     '}\n'
     'void main() {\n'
     '    Punto p = nuevo Punto(1); Punto n = nulo;\n'
     '    imprimir(p == nulo); imprimir(" "); imprimir(n == nulo);\n'
     '}\n'),

    # ---- Enumeraciones ----
    ('§3(E11) enum: valores en orden de declaracion (0,1,2,...)', '0 1 2',
     'enum Color { ROJO, VERDE, AZUL }\n'
     'void main() {\n'
     '    imprimir(Color.ROJO); imprimir(" ");\n'
     '    imprimir(Color.VERDE); imprimir(" ");\n'
     '    imprimir(Color.AZUL);\n'
     '}\n'),
    ('§3(E11) enum: tipo propio, distinto de entero (nominal typing)', 'IL-TIPO-012',
     'enum Color { ROJO, VERDE }\n'
     'void main() { imprimir(Color.ROJO == 0); }\n'),
    ('§3(E11) enum duplicado', 'IL-POO-001',
     'enum A { X }\n'
     'enum A { Y }\n'
     'void main() { }\n'),
    ('§3(E11) miembro duplicado dentro del mismo enum', 'IL-POO-031',
     'enum A { X, X }\n'
     'void main() { }\n'),
    ('§3(E11) nuevo sobre un enum es invalido', 'IL-POO-032',
     'enum A { X }\n'
     'void main() { A a = nuevo A(); }\n'),
    ('§3(E11) enum como tipo de atributo/parametro de clase', 'true',
     'enum Color { ROJO, VERDE }\n'
     'clase Figura {\n'
     '    publico Color color;\n'
     '    Figura(Color c) { this.color = c; }\n'
     '    publico bool esRoja() { return this.color == Color.ROJO; }\n'
     '}\n'
     'void main() { Figura f = nuevo Figura(Color.ROJO); imprimir(f.esRoja()); }\n'),

    # ---- Operadores bit a bit ----
    ('§4(E11) and, or, xor, not de bits', '8 14 6 -13',
     'void main() {\n'
     '    int a = 12; int b = 10;\n'
     '    imprimir(a & b); imprimir(" "); imprimir(a | b); imprimir(" ");\n'
     '    imprimir(a ^ b); imprimir(" "); imprimir(~a);\n'
     '}\n'),
    ('§4(E11) desplazamiento izquierda y derecha', '48 3',
     'void main() {\n'
     '    int a = 12;\n'
     '    imprimir(a << 2); imprimir(" "); imprimir(a >> 2);\n'
     '}\n'),
    ('§4(E11) precedencia: << antes que | y & antes que ==', '9 true',
     'void main() {\n'
     '    imprimir(1 << 3 | 1); imprimir(" ");\n'
     '    int flags = 5;\n'
     '    imprimir((flags & 1) == 1);\n'
     '}\n'),
    ('§4(E11) bit a bit solo entre enteros', 'IL-TIPO-010',
     'void main() { real x = 1.5; int y = x & 2; }\n'),

    # ---- const sobre arreglos ----
    ('§5(E11) arreglo constante: declarar, leer e iterar', '18',
     'void main() {\n'
     '    const int [3] DIAS = {5, 6, 7};\n'
     '    int suma = 0;\n'
     '    para (int i = 0; i < 3; i++) { suma = suma + DIAS[i]; }\n'
     '    imprimir(suma);\n'
     '}\n'),
    ('§5(E11) arreglo constante: reasignar un elemento es error', 'IL-SEM-031',
     'void main() {\n'
     '    const int [3] DIAS = {5, 6, 7};\n'
     '    DIAS[0] = 10;\n'
     '}\n'),
    ('§5(E11) arreglo normal (no const) sigue permitiendo reasignar', '99',
     'void main() {\n'
     '    int [3] arr = {1, 2, 3};\n'
     '    arr[0] = 99;\n'
     '    imprimir(arr[0]);\n'
     '}\n'),
]


# ============================================================================
# GRUPO 7 — Estructuras de Datos (programas de referencia completos)
# Con objetos (POO) y sin objetos (arreglos primitivos, ya v1.0).
# Cada caso: (archivo, lista de fragmentos que deben aparecer en la salida)
# ============================================================================

ESTRUCTURAS = [
    # Sin objetos
    ('pila_arreglo.inv', ['push 10', 'push 40', 'tope: 40',
                          'pop 40', 'pop 10', 'pila vacia: true']),
    ('cola_arreglo.inv', ['encolar 10', 'desencolar 10', 'desencolar 40',
                          'cola vacia: true']),
    # Con objetos
    ('lista_enlazada.inv', ['Lista: 10 20 30', 'Longitud: 3']),
    ('pila_enlazada.inv', ['3 2 1', 'vacia: true']),
    ('cola_enlazada.inv', ['10 20 30']),
    ('arbol_binario.inv', ['In-order: 20 30 40 50 60 70 80']),
    ('arreglo_objetos.inv', ['Ana (30)', 'Beto (25)', 'Cata (40)',
                             'Beto en posicion: 1']),

    # ---- Etapa 8: grafos, tablas hash y algoritmos ----
    # Sin objetos
    ('tabla_hash_arreglo.inv', ['insertar 5 -> indice 5', 'insertar 15 -> indice 6',
                                'insertar 25 -> indice 7', 'buscar 5 = 100',
                                'buscar 25 = 300', 'buscar 99: no encontrado']),
    ('grafo_matriz.inv', ['BFS desde 0: 0 1 2 3 4 5',
                          'DFS desde 0: 0 1 3 2 4 5']),
    ('ordenamiento_insercion.inv', ['Original:  [ 64, 25, 12, 22, 11, 90, 38 ]',
                                    'Ordenado:  [ 11, 12, 22, 25, 38, 64, 90 ]']),
    ('ordenamiento_seleccion.inv', ['Original:  [ 64, 25, 12, 22, 11, 90, 38 ]',
                                    'Ordenado:  [ 11, 12, 22, 25, 38, 64, 90 ]']),
    ('busqueda_binaria.inv', ['25 en posicion: 3', '11 en posicion: 0',
                              '90 en posicion: 6', '99 en posicion: -1']),
    ('quicksort.inv', ['Original:  [ 64, 25, 12, 22, 11, 90, 38 ]',
                       'Ordenado:  [ 11, 12, 22, 25, 38, 64, 90 ]']),
    ('mergesort.inv', ['Original:  [ 64, 25, 12, 22, 11, 90, 38 ]',
                       'Ordenado:  [ 11, 12, 22, 25, 38, 64, 90 ]']),
    # Etapa 10: monticulo (cola de prioridad) y heapsort
    ('monticulo.inv', ['insertar 8', 'insertar 3', 'insertar 10',
                       'extraer minimo: 1', 'extraer minimo: 3',
                       'extraer minimo: 6', 'extraer minimo: 8',
                       'extraer minimo: 10', 'monticulo vacio: true']),
    ('heapsort.inv', ['Original:  [ 64, 25, 12, 22, 11, 90, 38 ]',
                      'Ordenado:  [ 11, 12, 22, 25, 38, 64, 90 ]']),
    ('archivo_io.inv', ['existe antes: false', 'escritura ok: true',
                        'existe despues: true', 'primera linea',
                        'segunda linea', 'error controlado: IL-EST-015']),
    # Con objetos
    ('grafo_lista_adyacencia.inv', ['BFS desde 0: 0 2 1 3 4 5',
                                    'DFS desde 0: 0 2 3 4 5 1']),
    ('tabla_hash_encadenada.inv', ['insertar 5 -> cubeta 5', 'insertar 12 -> cubeta 5',
                                   'buscar 5 = 100', 'buscar 26 = 400',
                                   'buscar 99: no encontrado']),
]


# ============================================================================
# Ejecucion de la suite
# ============================================================================

class Resultados:
    """Acumula casos conformes y divergencias de la suite."""

    def __init__(self):
        self.ok = 0
        self.fallos = []

    def registrar(self, bien, referencia, esperado, obtenido):
        """Cuenta un caso conforme o guarda la divergencia."""
        if bien:
            self.ok += 1
        else:
            self.fallos.append((referencia, esperado, obtenido))

    @property
    def total(self):
        """Número total de casos ejecutados."""
        return self.ok + len(self.fallos)


def _sin_diagnosticos(codigos):
    return not codigos


# ============================================================================
# GRUPO 8 — Etapa 6: lenguaje estructurado completo
# (switch/do-while/ternario/try-catch + libreria estandar)
# Mismo criterio que CLASES: si `esperado` empieza con "IL-" se busca ese
# codigo entre los diagnosticos; si no, se compara la salida producida.
# ============================================================================

ESTRUCTURADO = [
    ('switch con fallthrough (case 2 cae a case 3)', 'dos tres',
     M % '''
    int x = 2;
    switch (x) {
        case 1: imprimir("uno"); break;
        case 2: imprimir("dos ");
        case 3: imprimir("tres"); break;
        default: imprimir("otro");
    }
'''),
    ('switch usa default cuando ningun case coincide', 'default',
     M % '''
    int x = 99;
    switch (x) {
        case 1: imprimir("uno");
        default: imprimir("default");
    }
'''),
    ('break dentro de switch no rompe el for envolvente', '0uno12',
     M % '''
    para (int i = 0; i < 3; i++) {
        switch (i) {
            case 1: imprimir("uno"); break;
        }
        imprimir(entero_a_texto(i));
    }
'''),
    ('do-while ejecuta el cuerpo al menos una vez', '10',
     M % '''
    int i = 10;
    hacer {
        imprimir(entero_a_texto(i));
        i = i + 1;
    } mientras (i < 5);
'''),
    ('ternario basico', 'si',
     M % 'int x = 5; imprimir(x > 3 ? "si" : "no");'),
    ('ternario anidado asociativo a la derecha', 'mediano',
     M % '''
    int x = 7;
    imprimir(x > 10 ? "grande" : x > 3 ? "mediano" : "chico");
'''),
    ('ternario no evalua la rama descartada', '100',
     '''
int falla() { return 5 / 0; }
void main() {
    int x = 1;
    int y = x > 0 ? 100 : falla();
    imprimir(entero_a_texto(y));
}
'''),
    # El texto esperado NO debe empezar con "IL-": el helper de este grupo
    # decide "buscar código" vs. "comparar salida" mirando ese prefijo, y
    # aquí el código aparece como TEXTO impreso por el programa (via
    # e.codigo), no como diagnóstico en `codigos` -- si empezara con "IL-"
    # el helper tomaría la rama equivocada.
    ('try/catch generico captura division por cero', 'codigo=IL-EJE-006 despues',
     M % '''
    try {
        int a = 5 / 0;
        imprimir("no deberia llegar");
    } catch (e) {
        imprimir("codigo=");
        imprimir(e.codigo);
        imprimir(" despues");
    }
'''),
    ('try/catch captura indice de arreglo fuera de rango', 'codigo=IL-EJE-050',
     M % '''
    int [3] arr = {1, 2, 3};
    try {
        imprimir(entero_a_texto(arr[10]));
    } catch (e) {
        imprimir("codigo=");
        imprimir(e.codigo);
    }
'''),
    ('break fuera de ciclo o switch', 'IL-SEM-040', M % 'break;'),
    ('continue dentro de switch sin ciclo envolvente', 'IL-SEM-041',
     M % '''
    int x = 1;
    switch (x) {
        case 1: continue;
    }
'''),
    ('switch sobre float no admitido', 'IL-EST-001',
     M % '''
    float x = 1.5;
    switch (x) {
        case 1: imprimir("uno");
    }
'''),
    ('case de tipo distinto al switch', 'IL-EST-002',
     M % '''
    int x = 1;
    switch (x) {
        case "hola": imprimir("no");
    }
'''),
    ('case duplicado', 'IL-EST-003',
     M % '''
    int x = 1;
    switch (x) {
        case 1: imprimir("a"); break;
        case 1: imprimir("b"); break;
    }
'''),
    ('ramas del ternario con tipos incompatibles', 'IL-EST-004',
     M % 'int x = 1; bool b = x > 0 ? "hola" : true;'),
    ('libreria estandar: cadenas', 'MUNDO-4',
     M % '''
    imprimir(mayusculas(subcadena("hola mundo", 5, 10)));
    imprimir("-");
    imprimir(entero_a_texto(longitud_texto(recortar("  hola  "))));
'''),
    ('libreria estandar: indice_de y caracter_en', '5-o',
     M % '''
    imprimir(entero_a_texto(indice_de("hola mundo", "mundo")));
    imprimir("-");
    imprimir(caracter_en("hola", 1));
'''),
    ('libreria estandar: matematica', '4.0-1024.0-3-4-7',
     M % '''
    imprimir(real_a_texto(raiz_cuadrada(16.0)));
    imprimir("-");
    imprimir(real_a_texto(elevar(2.0, 10.0)));
    imprimir("-");
    imprimir(entero_a_texto(piso(3.9)));
    imprimir("-");
    imprimir(entero_a_texto(techo(3.1)));
    imprimir("-");
    imprimir(entero_a_texto(absoluto(-7)));
'''),
    ('libreria estandar: azar con rango degenerado es determinista', '1',
     M % 'imprimir(entero_a_texto(azar(1, 1)));'),
]


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


def correr_estructuras(res, verboso):
    print('\n[7] ESTRUCTURAS DE DATOS (con y sin objetos)')
    for archivo, fragmentos in ESTRUCTURAS:
        if archivo == 'archivo_io.inv':
            # Etapa 10: archivo_io.inv tiene efectos de lado REALES sobre el
            # disco (a diferencia de todo lo demas en esta suite) -- crea
            # "ejemplo_archivo.tmp" en el directorio de trabajo y nunca lo
            # borra (InvenioLang no tiene un builtin de borrado). Sin este
            # cleanup, correr la suite dos veces seguidas hace que
            # "existe antes: false" falle en la segunda corrida.
            try:
                os.remove('ejemplo_archivo.tmp')
            except OSError:
                pass
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
        res.registrar(bien, archivo, 'ejecuta y produce la salida esperada',
                      errores or faltan)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {archivo}')
            if errores:
                print(f'         errores={errores}')
            if faltan:
                print(f'         faltan en la salida: {faltan}')


def correr_clases(res, verboso):
    print('\n[6] POO / INVENIOLANG 2.0 (docs/InvenioLang_2.0_POO.md)')
    for referencia, esperado, fuente in CLASES:
        codigos, salida = analizar(fuente, ejecutar=True)
        bien = esperado in codigos if esperado.startswith('IL-') else salida == esperado
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')


def correr_estructurado(res, verboso):
    print('\n[8] ETAPA 6: LENGUAJE ESTRUCTURADO COMPLETO')
    for referencia, esperado, fuente in ESTRUCTURADO:
        codigos, salida = analizar(fuente, ejecutar=True)
        bien = esperado in codigos if esperado.startswith('IL-') else salida == esperado
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')

    # Programa de referencia completo (§7 de InvenioLang_Etapa6_Estructurado.md)
    archivo = 'estructurado.inv'
    fragmentos = [
        '95: Excelente (aprobado)', '82: Muy bueno (aprobado)',
        '71: Bueno (aprobado)', '60: Insuficiente (aprobado)',
        '100: Excelente (aprobado)', 'Error controlado: IL-EJE-006', 'FIN',
    ]
    ruta = os.path.join(DIR_PRUEBAS, archivo)
    if not os.path.exists(ruta):
        res.registrar(False, archivo, 'el archivo debe existir', 'no encontrado')
        print(f'  FALLA {archivo}: no encontrado')
    else:
        with open(ruta, encoding='utf-8') as f:
            fuente = f.read()
        codigos, salida = analizar(fuente, ejecutar=True)
        errores = [c for c in codigos if '-WARN-' not in c]
        faltan = [t for t in fragmentos if t not in salida]
        bien = not errores and not faltan
        res.registrar(bien, archivo, 'ejecuta y produce la salida de §7', errores or faltan)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {archivo}')
            if errores:
                print(f'         errores={errores}')
            if faltan:
                print(f'         faltan en la salida: {faltan}')


def correr_poo_completo(res, verboso):
    print('\n[9] ETAPA 7: POO COMPLETO (abstractas, estaticos, sobrecarga, genericos)')
    for referencia, esperado, fuente in POO_COMPLETO:
        codigos, salida = analizar(fuente, ejecutar=True)
        bien = esperado in codigos if esperado.startswith('IL-') else salida == esperado
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')

    # Programa de referencia completo combinando las 4 caracteristicas
    archivo = 'poo_completo.inv'
    fragmentos = [
        'Area: 12.56', 'Area: 9.0', 'Instancias: 2', '5 4.0', '99',
    ]
    ruta = os.path.join(DIR_PRUEBAS, archivo)
    if not os.path.exists(ruta):
        res.registrar(False, archivo, 'el archivo debe existir', 'no encontrado')
        print(f'  FALLA {archivo}: no encontrado')
    else:
        with open(ruta, encoding='utf-8') as f:
            fuente = f.read()
        codigos, salida = analizar(fuente, ejecutar=True)
        errores = [c for c in codigos if '-WARN-' not in c]
        faltan = [t for t in fragmentos if t not in salida]
        bien = not errores and not faltan
        res.registrar(bien, archivo, 'ejecuta y combina las 4 caracteristicas de Etapa 7',
                      errores or faltan)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {archivo}')
            if errores:
                print(f'         errores={errores}')
            if faltan:
                print(f'         faltan en la salida: {faltan}')


def correr_etapa10(res, verboso):
    print('\n[10] ETAPA 10: CIERRE DE BRECHAS DE FASE 1/FASE 2')
    for referencia, esperado, fuente in ETAPA10:
        codigos, salida = analizar(fuente, ejecutar=True)
        bien = esperado in codigos if esperado.startswith('IL-') else salida == esperado
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')

    # Programa de referencia combinando sobrecarga de constructores + aTexto()
    archivo = 'poo_extendido.inv'
    fragmentos = ['(0, 0) (5, 5) (2, 7)', 'Circulo(radio=3.0)']
    ruta = os.path.join(DIR_PRUEBAS, archivo)
    if not os.path.exists(ruta):
        res.registrar(False, archivo, 'el archivo debe existir', 'no encontrado')
        print(f'  FALLA {archivo}: no encontrado')
    else:
        with open(ruta, encoding='utf-8') as f:
            fuente = f.read()
        codigos, salida = analizar(fuente, ejecutar=True)
        errores = [c for c in codigos if '-WARN-' not in c]
        faltan = [t for t in fragmentos if t not in salida]
        bien = not errores and not faltan
        res.registrar(bien, archivo,
                      'ejecuta y combina sobrecarga de constructores + aTexto()',
                      errores or faltan)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {archivo}')
            if errores:
                print(f'         errores={errores}')
            if faltan:
                print(f'         faltan en la salida: {faltan}')


PATRONES_DISENO = [
    ('patron_singleton.inv', ['misma instancia: true', 'accesos: 3']),
    ('patron_factory.inv', ['perro -> Hace: Guau', 'gato -> Hace: Miau',
                            'vaca -> Hace: Muu']),
    ('patron_observer.inv', ['[Pantalla] Temperatura actual: 22',
                             '[Registro] Guardada temperatura: 25']),
    ('patron_strategy.inv', ['sin descuento: 100.0', '20% off: 80.0',
                             '$15 off: 85.0']),
    ('patron_decorator.inv', ['Cafe: $1.5', 'Cafe + leche: $2.0',
                              'Cafe + leche + chocolate: $2.75']),
    # Algoritmos de grafos con peso (Etapa 11)
    ('dijkstra.inv', ['a 0: 0', 'a 1: 3', 'a 2: 1', 'a 3: 8', 'a 4: 11', 'a 5: 13']),
    ('kruskal.inv', ['arista 0-2 peso 1', 'arista 1-2 peso 2',
                     'arista 4-5 peso 2', 'peso total MST: 13']),
    ('orden_topologico.inv', ['Orden topologico: 4 5 0 2 3 1', 'orden valido']),
    # Backtracking y programacion dinamica (Etapa 11)
    ('n_reinas.inv', ['soluciones para N=6: 4']),
    ('permutaciones.inv', ['total de permutaciones: 24']),
    ('fibonacci_memo.inv', ['fib(10) = 55', 'fib(20) = 6765', 'fib(30) = 832040']),
    ('mochila.inv', ['valor maximo con capacidad 10: 13']),
    # Lista doblemente enlazada y deque (Etapa 11)
    ('lista_doble.inv', ['Adelante: 1 2 3 4', 'Atras:    4 3 2 1']),
    ('deque.inv', ['quitar frente: 1', 'quitar final: 4',
                   'cantidad restante: 0']),
    # Arbol AVL (Etapa 11)
    ('arbol_avl.inv', ['In-order: 10 20 30 40 50 60 70',
                       'Altura del arbol: 3', 'Raiz: 40']),
    # Enumeraciones (Etapa 11)
    ('enumeraciones.inv', ['hoy (ordinal): 2', 'es fin de semana: false',
                           'es fin de semana (sabado): true',
                           'figura es roja: true']),
    # Operadores bit a bit (Etapa 11)
    ('bit_a_bit.inv', ['puede leer: true', 'puede ejecutar: false',
                       'tras agregar ejecutar: true',
                       'tras quitar escribir: false',
                       'permisos (entero): 5',
                       'n*8 (n<<3): 40', 'n/2 (n>>1): 2']),
]


def correr_etapa11(res, verboso):
    print('\n[11] ETAPA 11: PATRONES DE DISEÑO Y MEJORAS FINALES DE FASE 2')
    for referencia, esperado, fuente in ETAPA11:
        codigos, salida = analizar(fuente, ejecutar=True)
        bien = esperado in codigos if esperado.startswith('IL-') else salida == esperado
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')

    for archivo, fragmentos in PATRONES_DISENO:
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
        res.registrar(bien, archivo, 'ejecuta y produce la salida esperada',
                      errores or faltan)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {archivo}')
            if errores:
                print(f'         errores={errores}')
            if faltan:
                print(f'         faltan en la salida: {faltan}')


ETAPA12 = [
    # ---- 12.1: para_cada / foreach ----
    ('§1(E12) para_cada suma los elementos de un arreglo', '100',
     'void main() {\n'
     '    int [4] nums = {10, 20, 30, 40};\n'
     '    int suma = 0;\n'
     '    para_cada (int x : nums) { suma = suma + x; }\n'
     '    imprimir(suma);\n'
     '}\n'),
    ('§1(E12) para_cada respeta romper/continuar', '1 2 4 ',
     'void main() {\n'
     '    int [5] nums = {1, 2, 3, 4, 5};\n'
     '    para_cada (int x : nums) {\n'
     '        si (x == 3) { continuar; }\n'
     '        si (x == 5) { romper; }\n'
     '        imprimir(x); imprimir(" ");\n'
     '    }\n'
     '}\n'),
    ('§1(E12) para_cada sobre un arreglo pasado por parametro', '7 8 9 ',
     'void recorrer(int[] arr) {\n'
     '    para_cada (int x : arr) { imprimir(x); imprimir(" "); }\n'
     '}\n'
     'void main() { int [3] a = {7, 8, 9}; recorrer(a); }\n'),
    ('§1(E12) para_cada sobre un arreglo de objetos (forma clase)', 'Ana Beto ',
     'clase Persona { publico texto nombre; Persona(texto n) { this.nombre = n; } }\n'
     'void main() {\n'
     '    Persona personas[2];\n'
     '    personas[0] = nuevo Persona("Ana"); personas[1] = nuevo Persona("Beto");\n'
     '    para_cada (Persona p : personas) { imprimir(p.nombre); imprimir(" "); }\n'
     '}\n'),
    ('§1(E12) para_cada exige un arreglo (no un escalar)', 'IL-TIPO-001',
     'void main() { int x = 5; para_cada (int y : x) { imprimir(y); } }\n'),
    ('§1(E12) para_cada exige tipo compatible con el elemento', 'IL-TIPO-001',
     'void main() { int [3] a = {1, 2, 3}; para_cada (texto s : a) { imprimir(s); } }\n'),
    # ---- Auditoria: parametros de PROCEDIMIENTO ahora se re-declaran en
    # el ambito del type checker (bug encontrado durante 12.1 -- antes,
    # cualquier error de tipos que involucrara solo un parametro de un
    # procedimiento (nunca una funcion) se saltaba en silencio) ----
    ('§1(E12) auditoria: tipo incompatible usando un parametro de PROCEDIMIENTO',
     'IL-TIPO-001',
     'void f(int x) { texto s = x; }\nvoid main() { f(5); }\n'),

    # ---- 12.2: acceso seguro ?. y coalescencia nula ?? ----
    ('§2(E12) ?. produce nulo en vez de lanzar IL-EJE-010', 'Ana desconocido',
     'clase Persona { publico texto nombre; Persona(texto n) { this.nombre = n; } }\n'
     'void main() {\n'
     '    Persona p1 = nuevo Persona("Ana"); Persona p2 = nulo;\n'
     '    imprimir(p1?.nombre ?? "desconocido"); imprimir(" ");\n'
     '    imprimir(p2?.nombre ?? "desconocido");\n'
     '}\n'),
    ('§2(E12) ?. sobre metodo, con y sin receptor nulo', 'hola Ana sin saludo',
     'clase Persona {\n'
     '    publico texto nombre; Persona(texto n) { this.nombre = n; }\n'
     '    publico texto saludo() { return "hola " + this.nombre; }\n'
     '}\n'
     'void main() {\n'
     '    Persona p1 = nuevo Persona("Ana"); Persona p2 = nulo;\n'
     '    imprimir(p1?.saludo() ?? "sin saludo"); imprimir(" ");\n'
     '    imprimir(p2?.saludo() ?? "sin saludo");\n'
     '}\n'),
    ('§2(E12) objeto?.metodo(); como instruccion no hace nada si es nulo', 'ok',
     'clase A { publico texto f() { return "x"; } }\n'
     'void main() { A a = nulo; a?.f(); imprimir("ok"); }\n'),
    ('§2(E12) ?? no evalua la derecha si la izquierda no es nula (cortocircuito)',
     'Ana',
     'clase P { publico texto nombre; P(texto n) { this.nombre = n; } }\n'
     'texto efecto() { imprimir("efecto "); return "nunca"; }\n'
     'void main() { P p = nuevo P("Ana"); imprimir(p?.nombre ?? efecto()); }\n'),
    ('§2(E12) ?? exige que la izquierda pueda ser nula', 'IL-TIPO-001',
     'void main() { int x = 5; int y = x ?? 10; imprimir(y); }\n'),
    ('§2(E12) ?? exige tipos compatibles', 'IL-TIPO-001',
     'clase A { }\nclase B { }\n'
     'void main() { A a = nulo; B b = nuevo B(); A r = a ?? b; }\n'),

    # ---- 12.3: interfaces multiples (implementa) ----
    ('§3(E12) clase implementa dos interfaces, despacho via variable de interfaz',
     '20 Pera: 80',
     'interfaz Comparable { publico abstracto entero comparar(Producto otro); }\n'
     'interfaz Imprimible { publico abstracto texto describir(); }\n'
     'clase Producto implementa Comparable, Imprimible {\n'
     '    publico texto nombre; publico entero precio;\n'
     '    Producto(texto n, entero p) { this.nombre = n; this.precio = p; }\n'
     '    publico entero comparar(Producto otro) { return this.precio - otro.precio; }\n'
     '    publico texto describir() { return this.nombre + ": " + entero_a_texto(this.precio); }\n'
     '}\n'
     'void main() {\n'
     '    Producto p1 = nuevo Producto("Manzana", 100);\n'
     '    Producto p2 = nuevo Producto("Pera", 80);\n'
     '    Comparable c = p1; Imprimible i = p2;\n'
     '    imprimir(c.comparar(p2)); imprimir(" "); imprimir(i.describir());\n'
     '}\n'),
    ('§3(E12) clase que no implementa un metodo de la interfaz', 'IL-POO-021',
     'interfaz I { publico abstracto entero f(); }\nclase C implementa I { }\nvoid main() { }\n'),
    ('§3(E12) implementa una interfaz inexistente', 'IL-POO-002',
     'clase C implementa NoExiste { }\nvoid main() { }\n'),
    ('§3(E12) implementa una clase no abstracta', 'IL-POO-033',
     'clase A { }\nclase C implementa A { }\nvoid main() { }\n'),
    ('§3(E12) interfaz no puede declarar atributos', 'IL-POO-034',
     'interfaz I { publico entero x; }\nvoid main() { }\n'),
    ('§3(E12) interfaz no puede declarar metodos con cuerpo', 'IL-POO-034',
     'interfaz I { publico entero f() { return 1; } }\nvoid main() { }\n'),
    ('§3(E12) interfaz no es instanciable', 'IL-POO-020',
     'interfaz I { publico abstracto entero f(); }\nvoid main() { I i = nuevo I(); }\n'),

    # ---- 12.5/12.6: funciones de primera clase (closures) ----
    ('§5(E12) declarar un valor-funcion y llamarlo', '7',
     'void main() {\n'
     '    funcion(entero a, entero b) entero operar;\n'
     '    operar = funcion(entero x, entero y) entero { return x + y; };\n'
     '    imprimir(operar(3, 4));\n'
     '}\n'),
    ('§5(E12) captura por referencia: el closure ve cambios posteriores',
     '10 99',
     'void main() {\n'
     '    int contador = 10;\n'
     '    funcion() entero leerContador;\n'
     '    si (contador > 0) { leerContador = funcion() entero { return contador; }; }\n'
     '    imprimir(leerContador()); imprimir(" ");\n'
     '    contador = 99;\n'
     '    imprimir(leerContador());\n'
     '}\n'),
    ('§5(E12) funcion de nivel superior pasada por nombre', '13 7',
     'int sumar(int a, int b) { return a + b; }\n'
     'int restar(int a, int b) { return a - b; }\n'
     'void main() {\n'
     '    funcion(entero a, entero b) entero operar;\n'
     '    operar = sumar; imprimir(operar(10, 3)); imprimir(" ");\n'
     '    operar = restar; imprimir(operar(10, 3));\n'
     '}\n'),
    ('§5(E12) closure recursivo via funcion de nivel superior', '55',
     'int fib(int n) { si (n <= 1) { return n; } return fib(n-1) + fib(n-2); }\n'
     'void main() { funcion(entero n) entero f; f = fib; imprimir(f(10)); }\n'),
    ('§5(E12) aridad incorrecta al llamar un closure', 'IL-SEM-052',
     'void main() {\n'
     '    funcion(entero a) entero f;\n'
     '    f = funcion(entero x) entero { return x; };\n'
     '    imprimir(f(1, 2));\n'
     '}\n'),
    ('§5(E12) tipo incompatible al asignar un valor-funcion', 'IL-TIPO-001',
     'int sumar(int a, int b) { return a + b; }\n'
     'void main() { funcion(entero a) entero f; f = sumar; }\n'),
    ('§5(E12) lambda sin return en todas las rutas', 'IL-SEM-050',
     'void main() {\n'
     '    funcion() entero f;\n'
     '    f = funcion() entero { si (verdadero) { return 1; } };\n'
     '}\n'),
    # ---- Auditoria: NINGUNA forma de subrutina validaba su propio tipo
    # de retorno contra lo que realmente hacia return -- hueco encontrado
    # al implementar el tipo de retorno de un lambda (Etapa 12.6) ----
    ('§5(E12) auditoria: tipo de retorno de una FUNCION nunca se validaba',
     'IL-TIPO-001',
     'int f() { return "no es entero"; }\nvoid main() { imprimir(f()); }\n'),
    ('§5(E12) auditoria: tipo de retorno de un METODO nunca se validaba',
     'IL-TIPO-001',
     'clase A { publico entero f() { return "x"; } }\nvoid main() { }\n'),
    ('§5(E12) tipo de retorno de un lambda si se valida ahora', 'IL-TIPO-001',
     'void main() {\n'
     '    funcion() entero f;\n'
     '    f = funcion() entero { return "no es entero"; };\n'
     '}\n'),

    # ---- 12.7: orden superior sobre arreglos (mapear/filtrar/reducir) ----
    ('§7(E12) mapear duplica cada elemento (funcion nombrada)', '2 4 6 8 10 ',
     'int doble(int n) { return n * 2; }\n'
     'void main() {\n'
     '    int [5] nums = {1, 2, 3, 4, 5}; int [5] dobles;\n'
     '    mapear(nums, dobles, doble);\n'
     '    para_cada (int x : dobles) { imprimir(x); imprimir(" "); }\n'
     '}\n'),
    ('§7(E12) filtrar retorna la cantidad y llena la salida', '2: 2 4',
     'bool esPar(int n) { return n % 2 == 0; }\n'
     'void main() {\n'
     '    int [5] nums = {1, 2, 3, 4, 5}; int [5] pares;\n'
     '    int n = filtrar(nums, pares, esPar);\n'
     '    imprimir(n); imprimir(": ");\n'
     '    int i = 0;\n'
     '    while (i < n) { imprimir(pares[i]); if (i < n - 1) { imprimir(" "); } i = i + 1; }\n'
     '}\n'),
    ('§7(E12) reducir con lambda inline', '15',
     'void main() {\n'
     '    int [5] nums = {1, 2, 3, 4, 5};\n'
     '    imprimir(reducir(nums, funcion(entero a, entero b) entero { return a + b; }, 0));\n'
     '}\n'),
    ('§7(E12) mapear con lambda inline', '30 60 90 120 ',
     'void main() {\n'
     '    int [4] nums = {10, 20, 30, 40}; int [4] triples;\n'
     '    mapear(nums, triples, funcion(entero n) entero { return n * 3; });\n'
     '    para_cada (int x : triples) { imprimir(x); imprimir(" "); }\n'
     '}\n'),
    ('§7(E12) aridad incorrecta al llamar reducir', 'IL-SEM-052',
     'void main() {\n'
     '    int [3] a = {1, 2, 3};\n'
     '    int r = reducir(a, funcion(entero p, entero q) entero { return p + q; });\n'
     '}\n'),

    # ---- 12.9/12.10: tipos suma (enum con carga) + pattern matching ----
    ('§9(E12) enum con carga: dispatch por variante liga los campos', '27 20 0 ',
     'enum Forma { Circulo(entero radio), Rectangulo(entero base, entero altura), Punto }\n'
     'entero area(Forma f) {\n'
     '    entero r = 0;\n'
     '    emparejar (f) {\n'
     '        caso Circulo(rad): r = 3 * rad * rad;\n'
     '        caso Rectangulo(b, h): r = b * h;\n'
     '        caso Punto: r = 0;\n'
     '    }\n'
     '    return r;\n'
     '}\n'
     'void main() {\n'
     '    Forma f1 = nuevo Circulo(3); Forma f2 = nuevo Rectangulo(4, 5); Forma f3 = nuevo Punto();\n'
     '    imprimir(area(f1)); imprimir(" "); imprimir(area(f2)); imprimir(" "); imprimir(area(f3)); imprimir(" ");\n'
     '}\n'),
    ('§9(E12) emparejar tambien funciona sobre un enum puro (Etapa 11.8, sin carga)',
     'verde',
     'enum Color { Rojo, Verde, Azul }\n'
     'void main() {\n'
     '    Color c = Color.Verde;\n'
     '    emparejar (c) {\n'
     '        caso Rojo: imprimir("rojo");\n'
     '        caso Verde: imprimir("verde");\n'
     '        caso Azul: imprimir("azul");\n'
     '    }\n'
     '}\n'),
    ('§9(E12) emparejar con comodin (default) cubre el resto', 'otro',
     'enum Forma { Circulo(entero radio), Rectangulo(entero base, entero altura), Punto }\n'
     'void main() {\n'
     '    Forma f = nuevo Punto();\n'
     '    emparejar (f) {\n'
     '        caso Circulo(r): imprimir("circulo");\n'
     '        default: imprimir("otro");\n'
     '    }\n'
     '}\n'),
    ('§9(E12) emparejar no exhaustivo sin comodin', 'IL-TIPO-022',
     'enum Forma { Circulo(entero radio), Punto }\n'
     'void main() {\n'
     '    Forma f = nuevo Punto();\n'
     '    emparejar (f) { caso Circulo(r): imprimir(r); }\n'
     '}\n'),
    ('§9(E12) emparejar no exhaustivo sobre enum puro', 'IL-TIPO-022',
     'enum Color { Rojo, Verde, Azul }\n'
     'void main() {\n'
     '    Color c = Color.Rojo;\n'
     '    emparejar (c) { caso Rojo: imprimir(1); caso Verde: imprimir(2); }\n'
     '}\n'),
    ('§9(E12) emparejar con aridad incorrecta en un caso', 'IL-TIPO-022',
     'enum Forma { Circulo(entero radio), Punto }\n'
     'void main() {\n'
     '    Forma f = nuevo Circulo(1);\n'
     '    emparejar (f) {\n'
     '        caso Circulo(r, extra): imprimir(r);\n'
     '        caso Punto: imprimir(0);\n'
     '    }\n'
     '}\n'),
    ('§9(E12) emparejar con una variante que no existe', 'IL-TIPO-022',
     'enum Forma { Circulo(entero radio), Punto }\n'
     'void main() {\n'
     '    Forma f = nuevo Circulo(1);\n'
     '    emparejar (f) {\n'
     '        caso Cuadrado(r): imprimir(r);\n'
     '        caso Punto: imprimir(0);\n'
     '    }\n'
     '}\n'),
    ('§9(E12) variante sin carga se construye con nuevo() sin argumentos', 'ok',
     'enum Forma { Circulo(entero radio), Punto }\n'
     'void main() { Forma f = nuevo Punto(); imprimir("ok"); }\n'),
]


REFERENCIA_ETAPA12 = [
    ('suma_cola.inv', ['suma 1..20 (con acumulador, cola): 210',
                       'suma 1..20 (sin acumulador, no es cola): 210']),
    ('tipos_suma.inv', ['Circulo de radio 2.0: area = 12.56',
                        'Rectangulo 3.0x4.0: area = 12.0',
                        'Punto (sin area): area = 0.0']),
]


# ---- 12.11: paridad entre el interprete de arbol y el codigo objetivo
# (ISA de juguete) -- misma idea que ya se uso para verificar ir.py/
# MaquinaTAC en la Etapa 5, pero automatizada como parte permanente de la
# suite en vez de una verificacion manual unica ----
PARIDAD_OBJETIVO = [
    ('recursion + aritmetica',
     'int fact(int n) {\n'
     '    if (n <= 1) { return 1; }\n'
     '    return n * fact(n - 1);\n'
     '}\n'
     'void main() {\n'
     '    int i = 0;\n'
     '    while (i < 5) { imprimir(fact(i)); imprimir(" "); i = i + 1; }\n'
     '    float x = 3;\n'
     '    imprimir(x / 2);\n'
     '}\n'),
    ('procedimiento void + resultado de funcion descartado',
     'void saludar(texto n) { imprimir("hola "); imprimir(n); }\n'
     'int suma(int a, int b) { return a + b; }\n'
     'void main() { saludar("mundo"); imprimir(suma(3, 4)); suma(1, 1); }\n'),
    ('switch + do-while',
     'void main() {\n'
     '    int n = 2;\n'
     '    switch (n) { case 1: imprimir("uno"); break; case 2: imprimir("dos"); break; default: imprimir("otro"); }\n'
     '    int i = 0;\n'
     '    do { imprimir(i); i = i + 1; } while (i < 3);\n'
     '}\n'),
]


# ---- 12.12: (referencia, fuente, k_registros) -- programas con mas
# valores simultaneamente vivos que `k_registros`, para forzar spill ----
PARIDAD_REGISTROS = [
    ('5 parametros + 4 sumas parciales, todos vivos al retornar, k=3',
     'int f(int a, int b, int c, int d, int e) {\n'
     '    int s1 = a + b;\n'
     '    int s2 = c + d;\n'
     '    int s3 = s1 + s2;\n'
     '    int s4 = s3 + e;\n'
     '    return s4 + a + b + c + d;\n'
     '}\n'
     'void main() { imprimir(f(1, 2, 3, 4, 5)); }\n', 3),
]


def _paridad_objetivo(fuente, k_registros=None):
    """Corre `fuente` por el interprete de arbol Y por el codigo objetivo.

    De juguete (Etapa 12.11: TAC optimizado -> InstrObjetivo ->
    MaquinaObjetivo), opcionalmente con asignacion de registros (Etapa
    12.12, linear-scan con `k_registros` registros). Retorna
    (salida_arbol, salida_objetivo, resumen_registros, error).
    """
    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(fuente, 't.inv')
    if em.hay_errores():
        return None, None, None, 'lexico: ' + str([e.codigo for e in em.errores])
    p = Parser(lx, em)
    ast, em = p.analizar(fuente, 't.inv')
    if ast is None or em.hay_errores():
        return None, None, None, 'sintactico: ' + str([e.codigo for e in em.errores])
    sem = SemanticAnalyzer(em)
    tabla = sem.analizar(ast)
    if em.hay_errores():
        return None, None, None, 'semantico: ' + str([e.codigo for e in em.errores])
    TypeChecker(em, tabla).verificar(ast)
    if em.hay_errores():
        return None, None, None, 'tipos: ' + str([e.codigo for e in em.errores])

    interp = Interpreter(em, tabla)
    salida_arbol = interp.interpretar(ast, [], usar_stdin=False)

    subrutinas, ir_globales = ir_mod.generar_programa(ast)
    subrutinas_opt, _ = ir_mod.optimizar_programa(subrutinas)
    objetivo, resumen_registros = ir_mod.generar_objetivo_programa(subrutinas_opt, k_registros)
    maquina = ir_mod.MaquinaObjetivo(objetivo, ir_globales)
    salida_objetivo = maquina.ejecutar()

    return salida_arbol, salida_objetivo, resumen_registros, None


def correr_etapa12(res, verboso):
    print('\n[12] ETAPA 12: PARADIGMA FUNCIONAL, TIPOS SUMA Y RIGOR DE COMPILADORES')
    for referencia, esperado, fuente in ETAPA12:
        codigos, salida = analizar(fuente, ejecutar=True)
        bien = esperado in codigos if esperado.startswith('IL-') else salida == esperado
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')

    for archivo, fragmentos in REFERENCIA_ETAPA12:
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
        res.registrar(bien, archivo, 'ejecuta y produce la salida esperada',
                      errores or faltan)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {archivo}')
            if errores:
                print(f'         errores={errores}')
            if faltan:
                print(f'         faltan en la salida: {faltan}')

    for referencia, fuente in PARIDAD_OBJETIVO:
        salida_arbol, salida_objetivo, _resumen, error = _paridad_objetivo(fuente)
        bien = error is None and salida_arbol == salida_objetivo
        res.registrar(bien, referencia, 'arbol y objetivo coinciden',
                      error or (salida_arbol, salida_objetivo))
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} (§11 objetivo) {referencia}')
            if not bien:
                print(f'         error={error} arbol={salida_arbol} objetivo={salida_objetivo}')

    # ---- 12.12: liveness + asignacion de registros -- misma paridad de
    # ejecucion que arriba, pero ahora con k_registros deliberadamente
    # pequeno para forzar al menos un spill (el criterio de verificacion
    # que pide el plan: "un programa con mas temporales vivos
    # simultaneamente que registros disponibles" produce un spill
    # correcto, resultado identico) ----
    for referencia, fuente, k in PARIDAD_REGISTROS:
        salida_arbol, salida_objetivo, resumen, error = _paridad_objetivo(fuente, k_registros=k)
        hubo_spill = any(spills for _asig, spills in (resumen or {}).values())
        bien = error is None and salida_arbol == salida_objetivo and hubo_spill
        res.registrar(bien, referencia, 'arbol y objetivo (con registros) coinciden + hubo spill',
                      error or (salida_arbol, salida_objetivo, hubo_spill))
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} (§12 registros) {referencia}')
            if not bien:
                print(f'         error={error} arbol={salida_arbol} objetivo={salida_objetivo} '
                      f'spill={hubo_spill} resumen={resumen}')

    # Rechazo limpio de arreglos/try-catch (fuera del alcance del generador
    # de codigo objetivo, ver ir.py seccion Etapa 12.11)
    fuente_arreglo = 'void main() { int [3] a = {1, 2, 3}; imprimir(a[0]); }\n'
    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(fuente_arreglo, 't.inv')
    p = Parser(lx, em)
    ast, em = p.analizar(fuente_arreglo, 't.inv')
    sem = SemanticAnalyzer(em)
    tabla = sem.analizar(ast)
    TypeChecker(em, tabla).verificar(ast)
    subrutinas, _ = ir_mod.generar_programa(ast)
    rechazado = False
    try:
        ir_mod.generar_objetivo_programa(subrutinas)
    except ir_mod.NoSoportadoObjetivo:
        rechazado = True
    res.registrar(rechazado, '§11(E12) objetivo rechaza arreglos limpiamente',
                  'NoSoportadoObjetivo', rechazado)
    if verboso or not rechazado:
        print(f'  {"ok  " if rechazado else "FALLA"} §11(E12) objetivo rechaza arreglos limpiamente')

    # ---- 12.13: parser LL(1) de comparacion -- mismas expresiones,
    # mismo resultado que el LALR(1) real (ver inveniolang/ll1_demo.py) ----
    ok_ll1, detalles_ll1 = ll1_demo.verificar_contra_lalr()
    res.registrar(ok_ll1, '§13(E12) parser LL(1) coincide con LALR(1) en todas las expresiones',
                  'todas coinciden', detalles_ll1 if not ok_ll1 else 'ok')
    if verboso or not ok_ll1:
        print(f'  {"ok  " if ok_ll1 else "FALLA"} §13(E12) parser LL(1) vs LALR(1)')
        if not ok_ll1:
            for d in detalles_ll1:
                print(f'         {d}')


def correr_etapa13(res, verboso):
    """Etapa 13: constructor de diagramas de flujo.

    INV-3007: los mismos 19 casos de siempre, ahora sobre el modelo de
    `inveniolang.flujo` (edición estructurada + generación de código), que
    sustituyó a flowchart_builder.py/flowchart.py -- sin Qt, igual que antes.
    """
    print('\n[13] ETAPA 13: CONSTRUCTOR DE DIAGRAMAS DE FLUJO')

    def _crear(tipo, **campos):
        try:
            return flujo.nuevo_nodo(tipo, **campos), []
        except flujo.ErrorFlujo as e:
            return None, [e.texto('es')]

    # ---- validación de fragmentos por forma (válidos e inválidos) ----
    casos_fragmentos = [
        ('§1(E13) declaración: declaración válida', lambda: _crear('declaracion', texto='entero x = 5'), True),
        ('§1(E13) proceso: no exige ";" final', lambda: _crear('proceso', texto='x = x + 1'), True),
        ('§1(E13) declaración: aridad incorrecta (2 instrucciones)',
         lambda: _crear('declaracion', texto='int a; int b'), False),
        ('§1(E13) proceso: error de sintaxis', lambda: _crear('proceso', texto='x = = 1'), False),
        ('§1(E13) entrada: identificador simple', lambda: _crear('leer', texto='n'), True),
        ('§1(E13) entrada: rechaza expresión (no identificador)',
         lambda: _crear('leer', texto='n + 1'), False),
        ('§1(E13) salida: expresión válida', lambda: _crear('escribir', texto='n * 2'), True),
        ('§1(E13) decisión: condición válida', lambda: _crear('si', condicion='n > 0'), True),
        ('§1(E13) decisión: condición vacía es error', lambda: _crear('si', condicion=''), False),
        ('§1(E13) mientras: condición válida', lambda: _crear('mientras', condicion='n < 10'), True),
        ('§1(E13) hacer-mientras: condición válida',
         lambda: _crear('hacer_mientras', condicion='n < 10'), True),
        ('§1(E13) para: cabecera válida',
         lambda: _crear('para', inicio='entero i = 0', condicion='i < 10', paso='i++'), True),
        ('§1(E13) para: condición inválida (operador incompleto)',
         lambda: _crear('para', inicio='entero i = 0', condicion='i <', paso='i++'), False),
    ]
    for referencia, llamada, valido_esperado in casos_fragmentos:
        nodo, errores = llamada()
        bien = (not errores) == valido_esperado and (nodo is not None) == valido_esperado
        res.registrar(bien, referencia, 'válido' if valido_esperado else 'inválido',
                      'válido' if not errores else errores)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')

    # ---- ida y vuelta: armar un diagrama anidado con las operaciones
    # estructuradas, generar el programa y correrlo con el pipeline REAL ----
    U = flujo.Ubicacion  # noqa: N806 - alias corto de la clase en la tabla de casos

    def _agregar(m, tipo, ubicacion=None, **campos):
        return flujo.insertar(m, 'main', ubicacion or U(), flujo.nuevo_nodo(tipo, **campos))

    def _ultimo(m):
        return m.diagrama('main').cuerpo[-1].id

    def _diagrama_acumulador_par():
        # entero suma = 0; para (i=0;i<5;i++) { si (i%2==0) { suma=suma+i; } } imprimir(suma);
        m = _agregar(flujo.nuevo_modelo('es'), 'declaracion', texto='entero suma = 0')
        m = _agregar(m, 'proceso', texto='suma = suma + i')
        m = flujo.envolver_en_si(m, 'main', [_ultimo(m)], 'i % 2 == 0')
        m = flujo.envolver_en_ciclo(m, 'main', [_ultimo(m)], 'para',
                                    inicio='entero i = 0', condicion='i < 5', paso='i++')
        return _agregar(m, 'escribir', texto='suma')

    def _diagrama_si_sino():
        # entero x = 7; si (x > 5) { imprimir("grande"); } sino { imprimir("chico"); }
        m = _agregar(flujo.nuevo_modelo('es'), 'declaracion', texto='entero x = 7')
        m = _agregar(m, 'si', condicion='x > 5')
        si_id = _ultimo(m)
        m = flujo.agregar_rama(m, 'main', si_id, 'sino')
        m = _agregar(m, 'escribir', U(si_id, 'rama:0'), texto='"grande"')
        return _agregar(m, 'escribir', U(si_id, 'sino'), texto='"chico"')

    def _diagrama_hacer_mientras():
        # entero n = 0; hacer { n = n + 1; imprimir(n); } mientras (n < 3);
        m = _agregar(flujo.nuevo_modelo('es'), 'declaracion', texto='entero n = 0')
        m = _agregar(m, 'hacer_mientras', condicion='n < 3')
        ciclo = _ultimo(m)
        m = _agregar(m, 'proceso', U(ciclo, 'cuerpo'), texto='n = n + 1')
        return _agregar(m, 'escribir', U(ciclo, 'cuerpo'), texto='n')

    diagramas_referencia = [
        ('§5(E13) ida y vuelta: para con decisión anidada (acumulador de pares)',
         _diagrama_acumulador_par(), '6'),
        ('§5(E13) ida y vuelta: si-sino', _diagrama_si_sino(), 'grande'),
        ('§5(E13) ida y vuelta: hacer-mientras', _diagrama_hacer_mientras(), '123'),
    ]
    for referencia, modelo, fragmento_esperado in diagramas_referencia:
        problemas = flujo.validar(modelo)
        texto = flujo.codigo_desde_modelo(modelo)
        em = ErrorManager()
        lx = Lexer(em)
        lx.tokenizar(texto, 't.inv')
        ast, em = Parser(lx, em).analizar(texto, 't.inv') if not em.hay_errores() else (None, em)
        salida_texto = ''
        if ast is not None and not em.hay_errores():
            tabla = SemanticAnalyzer(em).analizar(ast)
            if not em.hay_errores():
                TypeChecker(em, tabla).verificar(ast)
                if not em.hay_errores():
                    interp = Interpreter(em, tabla)
                    salida_texto = ''.join(interp.interpretar(ast, [], usar_stdin=False))
        bien = not problemas and not em.hay_errores() and fragmento_esperado in salida_texto
        res.registrar(bien, referencia, fragmento_esperado,
                      salida_texto if bien else ([p.texto() for p in problemas] or [e.codigo for e in em.errores]))
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         texto generado:\n{texto}')

    # ---- vista previa: el esquema dibujable acepta CUALQUIER diagrama armado ----
    for referencia, modelo, _ in diagramas_referencia:
        try:
            esquema = flujo.esquemas(modelo, 'main')[0]
            bien = len(esquema.nodos) > 0
        except Exception:  # pragma: no cover
            bien = False
            esquema = None
        res.registrar(bien, f'{referencia} (vista previa sin excepción)',
                      'diagrama con símbolos', esquema.nodos if esquema else 'EXCEPCION')
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia} (vista previa)')


# ============================================================================
# GRUPO 14 — InvenioLang 11: acceso a miembro encadenado (INV-4406)
# docs/InvenioLang_2.0_POO.md §14. Casos nuevos: los 391 anteriores no cambian.
# ============================================================================

_CLASES_CADENA = """clase Motor {
    publico entero potencia;
    Motor(entero p) { este.potencia = p; }
    publico entero doble() { retornar este.potencia * 2; }
}
clase Auto {
    publico Motor motor;
    publico entero[] km;
    privado Motor oculto;
    Auto(entero p) { este.motor = nuevo Motor(p); este.km = nuevo entero[3]; este.oculto = este.motor; }
    publico Motor getMotor() { retornar este.motor; }
    publico entero edad() { retornar 3; }
}
clase Garaje {
    publico Auto auto;
    Garaje() { este.auto = nuevo Auto(100); }
    publico vacio tunear() { este.auto.motor.potencia = este.auto.motor.potencia + 10; }
}
"""


def _cadena(cuerpo):
    return _CLASES_CADENA + 'vacio main() {\n    Garaje g = nuevo Garaje();\n' + cuerpo + '\n}\n'


ACCESO_ENCADENADO = [
    ('§14 lectura a.b.c', '100', _cadena('imprimir(g.auto.motor.potencia);')),
    ('§14 escritura a.b.c = v', '7', _cadena('g.auto.motor.potencia = 7; imprimir(g.auto.motor.potencia);')),
    ('§14 asignación compuesta a.b.c += v', '105',
     _cadena('g.auto.motor.potencia += 5; imprimir(g.auto.motor.potencia);')),
    ('§14 llamada al final a.b.m()', '200', _cadena('imprimir(g.auto.motor.doble());')),
    ('§14 la cadena sigue tras una llamada a.m().c', '100', _cadena('imprimir(g.auto.getMotor().potencia);')),
    ('§14 instrucción de llamada encadenada', '110', _cadena('g.tunear(); imprimir(g.auto.motor.potencia);')),
    ('§14 escritura tras una llamada a.m().c = v', '1',
     _cadena('g.auto.getMotor().potencia = 1; imprimir(g.auto.motor.potencia);')),
    ('§14 atributo arreglo al final a.b.c[i]', '7', _cadena('g.auto.km[1] = 7; imprimir(g.auto.km[1]);')),
    ('§14 receptor elemento de arreglo v[i].b.c', '9',
     _cadena('Auto autos[2]; autos[0] = nuevo Auto(9); imprimir(autos[0].motor.potencia);')),
    ('§14 método como instrucción a.b.m();', '200', _cadena('g.auto.motor.doble(); imprimir(g.auto.motor.doble());')),
    ('§14 IL-POO-006 eslabón que no es clase', 'IL-POO-006', _cadena('imprimir(g.auto.edad().x);')),
    ('§14 IL-POO-006 atributo inexistente', 'IL-POO-006', _cadena('imprimir(g.auto.rueda.x);')),
    ('§14 IL-POO-005 eslabón privado', 'IL-POO-005', _cadena('imprimir(g.auto.oculto.potencia);')),
    ('§14 IL-POO-013 tipo del último eslabón', 'IL-POO-013', _cadena('entero x = g.auto.motor;')),
    ('§14 IL-POO-017 aridad de la llamada final', 'IL-POO-017', _cadena('imprimir(g.auto.motor.doble(3));')),
    ('§14 IL-EJE-010 eslabón intermedio nulo', 'IL-EJE-010',
     _cadena('Garaje h = nuevo Garaje(); h.auto = nulo; imprimir(h.auto.motor.potencia);')),
    ('§14 ?. sigue siendo de un solo nivel', 'IL-SIN-010', _cadena('imprimir(g?.auto.motor);')),
]


def correr_inveniolang11(res, verboso):
    print('\n[14] INVENIOLANG 11: ACCESO A MIEMBRO ENCADENADO')
    for referencia, esperado, fuente in ACCESO_ENCADENADO:
        codigos, salida = analizar(fuente, ejecutar=True)
        bien = esperado in codigos if esperado.startswith('IL-') else salida == esperado and not [
            c for c in codigos if '-WARN-' not in c]
        res.registrar(bien, referencia, esperado, salida or codigos)
        if verboso or not bien:
            print(f'  {"ok  " if bien else "FALLA"} {referencia}')
            if not bien:
                print(f'         esperado={esperado!r}  obtenido={salida!r} {codigos}')


GRUPOS = {
    'catalogo': correr_catalogo,
    'expresiones': correr_expresiones,
    'ejecucion': correr_ejecucion,
    'codificacion': correr_codificacion,
    'referencia': correr_referencia,
    'clases': correr_clases,
    'estructuras': correr_estructuras,
    'estructurado': correr_estructurado,
    'poo_completo': correr_poo_completo,
    'etapa10': correr_etapa10,
    'etapa11': correr_etapa11,
    'etapa12': correr_etapa12,
    'etapa13': correr_etapa13,
    'inveniolang11': correr_inveniolang11,
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
