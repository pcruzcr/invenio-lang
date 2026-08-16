"""Documentación y ejemplos embebidos para el menú Ayuda."""
# ============================================================
# Contenido de la documentación embebida (menú Ayuda)
# ============================================================

_DOC_GUIA = """INVENIOLANG 1.0 - GUÍA RÁPIDA
====================================

1) Escribir el programa en el editor (archivo .inv).

2) Todo archivo ejecutable DEBE tener la función main:
       void main() {
           imprimir("Hola, mundo!\\n");
       }

3) Ejecutar: botón "Ejecutar" o Ctrl+R.
   La consola usa palabras reservadas en inglés o español (equivalentes).

Palabras reservadas (inglés | español):
  if|si  else|sino  while|mientras  for|para
  print|imprimir  read|leer  return
  int|entero  float|real  string|texto  bool|logico  void|vacio
  const|constante  break|romper  continue|continuar
  true|verdadero  false|falso  main

Tipos de datos:
  int (entero, 32 bits)   float (real, doble precisión)
  string (texto)          bool (lógico)          void (vacío, solo subrutinas)

Ejemplo:
  int factorial(int n) {
      si (n <= 1) { return 1; }
      return n * factorial(n - 1);
  }
  void main() {
      imprimir(factorial(5));   // 120
  }
"""

_DOC_REFERENCIA = """REFERENCIA DEL LENGUAJE
====================================

OPERADORES
  Aritmeticos:  +  -  *  /  %   (int+int=int, / trunca hacia cero)
  Relacionales: ==  !=  <  >  <=  >=   (resultado siempre bool)
  Logicos:      &&  ||  !   (evaluación en cortocircuito)
  Asignacion:   =  +=  -=  *=  /=  %=
  Incr/decr:    ++  --   (solo sobre int)

PRECEDENCIA (de menor a mayor)
  ||  ->  &&  ->  ==,!=  ->  <,>,<=,>=  ->  +,-  ->  *,/,%  ->  unario -,!,++,--

ESTRUCTURAS DE CONTROL
  if/else:
      if (cond) { ... } sino { ... }
  while:
      mientras (cond) { ... }
  for:
      para (int i=0; i<n; i++) { ... }
  break/continue (solo dentro de ciclos)

VARIABLES Y CONSTANTES
  int x = 10;             // variable
  const float PI = 3.14;  // constante (no modificable)
  Declaración múltiple con coma NO permitida (int a, b; es inválido).

ARREGLOS Y MATRICES
  int[5] arr = {1,2,3,4,5};       // arreglo (forma canónica, prefija)
  int[2][3] m = {{1,2,3},{4,5,6}}; // matriz
  arr[i]   m[f][c]                // acceso (índices desde 0)
  Verificación de límites en ejecución (IL-EJE-050).
  La forma postfija (int arr[5];) se acepta pero avisa con IL-WARN-040.
  No se puede copiar un arreglo entero con = (IL-SIN-070): copie elemento
  a elemento. Una matriz requiere siempre dos índices (IL-SIN-080).

FUNCIONES Y PROCEDIMIENTOS
  int suma(int a, int b) { return a+b; }   // función (retorna valor)
  void mostrar(int x) { imprimir(x); }      // procedimiento (void)
  Parámetros por valor; arreglos/matrices por referencia.
  Recursión soportada (hasta 500 llamadas, luego IL-EJE-040).
  return / retornar son equivalentes.

ENTRADA / SALIDA
  imprimir(expr);   // no añade salto de línea automático
  leer(var);        // lee de stdin según el tipo de la variable
"""

_DOC_FUNCIONES = """FUNCIONES INTEGRADAS (8 conversiones)
====================================

Cada función tiene 3 formas equivalentes: canónica (§4), inglés (§19) y español (§19).

int  ->  float
  int_a_float(n) / int_to_float / entero_a_real

float  ->  int   (trunca hacia cero)
  float_a_int(f) / float_to_int / real_a_entero

int  ->  string
  int_a_texto(n) / int_to_string / entero_a_texto

float  ->  string
  float_a_texto(f) / float_to_string / real_a_texto

string  ->  int
  texto_a_int(s) / string_to_int / texto_a_entero

string  ->  float
  texto_a_float(s) / string_to_float / texto_a_real

bool  ->  string   (\\"true\\" / \\"false\\")
  bool_a_texto(b) / bool_to_string / logico_a_texto

string  ->  bool
  texto_a_bool(s) / string_to_bool / texto_a_logico

Instrucciones integradas (no son funciones comunes):
  imprimir(expr) / print(expr)
  leer(var)      / read(var)

Errores en ejecución:
  IL-EJE-003 desborde float->int   IL-EJE-004/005 texto->numerico inválido
"""

_DOC_ERRORES = """CATÁLOGO DE ERRORES (completo)
====================================
Formato oficial (§15.8.1):
  [CÓDIGO] archivo:línea:columna — mensaje

Prioridad entre fases: léxico > sintáctico > semántico > tipos > ejecución.

LÉXICOS (IL-LEX)
  001 Codificación inválida (no UTF-8)   002 Carácter inválido (@ # $ ^)
  003 Carácter de control inválido       004 Identificador inicia con dígito
  005 Carácter ilegal en identificador   006 Es una palabra reservada
  007 Subrayado en entero (1_000)        008 Base no decimal (0xFF)
  009 Real mal formado (.5  5.  1e10)    010 Salto de línea en literal
  011 Secuencia de escape desconocida    012 Literal de texto no terminado
  013 Delimitadores no coinciden         014 Comentario de bloque sin cerrar

SINTÁCTICOS (IL-SIN)
  005 Llave de cierre sin apertura       006 EOF con bloques sin cerrar
  010 Falta el punto y coma              011 Punto y coma tras bloque
  012 Punto y coma aislado               015 Declaración múltiple (int a,b;)
  020 Asignación encadenada (a=b=c)      025 print sin argumentos
  026 print con varios argumentos        027 read con expresión, no variable
  030 Condición de if sin paréntesis     031 Cuerpo sin llaves { }
  032 else sin if previo                 035 Condición de while sin paréntesis
  040 Faltan los ; del encabezado for    050 Subrutina dentro de un bloque
  070 Asignar un arreglo completo        080 Matriz con un solo índice
  081 Tres o más dimensiones

SEMÁNTICOS (IL-SEM)
  002 Identificador duplicado            003 Identificador no declarado
  004 Autorreferencia en inicialización  005 Lvalue inválido (5 = x)
  010 Literal entero fuera de rango      020 Falta la función main
  021 main con tipo distinto de void     022 main con parámetros
  023 return con valor dentro de main    030 Constante sin inicializar
  031 Asignación a constante             032 Init de constante no constante
  040 break fuera de ciclo               041 continue fuera de ciclo
  050 Ruta de ejecución sin return       052 Número de argumentos
  053 return sin expresión en función    060 Procedimiento en una expresión
  061 return con valor en procedimiento  070 Dimensión definida por variable
  071 Dimensión cero o negativa          072 Arreglo o matriz de tipo void
  073 Número de inicializadores          080 Redefinir función integrada
  081 Tipo de argumento en integrada

TIPOS (IL-TIPO)
  001 Tipo incompatible                  010 % sobre float
  011 - * / % sobre string               012 Orden (< >) sobre string o bool
  013 Aritmética sobre bool              014 Conversión bool <-> numérico
  015 void en contexto de valor          016 ++ / -- sobre no entero
  017 Unario sobre tipo incompatible     018 && o || con operando no bool
  019 Condición que no es bool           020 print de un valor void
  021 Índice de arreglo no entero

EJECUCIÓN (IL-EJE)
  001 Desbordamiento de int (32 bits)    002 División real entre cero
  003 Desborde en float_to_int           004 Texto no convertible a entero
  005 Texto no convertible a real        006 División entera entre cero
  010 Variable local sin inicializar     020 Entrada no convertible a int
  021 Entrada no convertible a float     022 Entrada no convertible a bool
  030 Ciclo infinito (límite superado)   040 Recursión demasiado profunda
  050 Índice fuera de rango

ADVERTENCIAS (IL-WARN) — no impiden la ejecución
  001 Oculta un identificador externo    002 Puede leerse sin inicializar
  003 Divisor es el literal cero         010 while(true) sin break alcanzable
  020 Se descarta el valor de retorno    030 Índice literal fuera de rango
  040 Declaración postfija de arreglo
"""

_DOC_ATAJOS = """ATAJOS DE TECLADO
====================================
  Ctrl+N   Nuevo archivo
  Ctrl+O   Abrir archivo
  Ctrl+S   Guardar archivo
  Ctrl+R   Ejecutar el programa
  Ctrl+Espacio  Autocompletado (sugerido)
  Ctrl+G   Ir a línea
  F8       Siguiente error   (Shift+F8 = error anterior)
  F1       Ayuda / documentación
  Tab      Insertar 4 espacios
"""

# Ejemplos cargables desde la carpeta pruebas/
EJEMPLOS = [
    'hola_mundo', 'tipos', 'condicionales', 'ciclos', 'funciones',
    'procedimientos', 'arreglos', 'matrices', 'sistema_ventas',
    'calculadora', 'estadisticas', 'conversor',
]


