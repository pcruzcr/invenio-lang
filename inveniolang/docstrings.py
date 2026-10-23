"""Documentación y ejemplos embebidos para el menú Ayuda."""

# ============================================================
# Contenido de la documentación embebida (menú Ayuda)
# ============================================================

_DOC_GUIA = """INVENIOLANG 2.0 - GUÍA RÁPIDA
====================================

1) Escribir el programa en el editor (archivo .inv).

2) Todo archivo ejecutable DEBE tener la función main:
       void main() {
           imprimir("Hola, mundo!\\n");
       }

3) Ejecutar: botón "Ejecutar" o Ctrl+R.
   La consola usa palabras reservadas en inglés o español (equivalentes).

Palabras reservadas base (inglés | español):
  if|si  else|sino  while|mientras  for|para
  print|imprimir  read|leer  return|retornar
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

Esto es solo el núcleo estructurado (v1.0). InvenioLang 2.0 añade
control de flujo (switch/do-while/ternario/try-catch, ver §"Control de
flujo") y programación orientada a objetos completa (clases, herencia,
abstractas, estáticos, sobrecarga, genéricos — ver "Referencia del
lenguaje" y "Catálogo de errores" para el detalle).
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
  do/while (Etapa 6, cuerpo se ejecuta al menos una vez):
      hacer { ... } mientras (cond);
  switch/case (Etapa 6, con fallthrough como en C):
      segun (x) {
          caso 1: ...          // sin break: cae al siguiente caso
          caso 2: ...; romper;
          por_defecto: ...
      }
  ternario (Etapa 6, cortocircuito real -- solo evalúa la rama elegida):
      cond ? valor_si : valor_no
  try/catch (Etapa 6, genérico -- captura cualquier IL-EJE-*):
      intentar { ... } capturar (e) { imprimir(e.codigo); }
  break/continue (dentro de ciclos; break también sirve para switch,
  continue NUNCA se refiere al switch, solo al ciclo que lo contiene)

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
  Arreglo de objetos (Etapa 3, solo forma postfija):
      Persona personas[10];  personas[i].nombre

FUNCIONES Y PROCEDIMIENTOS
  int suma(int a, int b) { return a+b; }   // función (retorna valor)
  void mostrar(int x) { imprimir(x); }      // procedimiento (void)
  Parámetros por valor; arreglos/matrices por referencia.
  Recursión soportada (hasta 500 llamadas, luego IL-EJE-040).
  return / retornar son equivalentes.

ENTRADA / SALIDA
  imprimir(expr);   // no añade salto de línea automático
  leer(var);        // lee de stdin según el tipo de la variable

PROGRAMACIÓN ORIENTADA A OBJETOS (InvenioLang 2.0, Etapas 2 y 7)
Ver docs/InvenioLang_2.0_POO.md para la spec formal completa. Resumen:

  clase Animal {
      privado texto nombre;
      publico entero edad;
      Animal(texto n, entero e) { this.nombre = n; this.edad = e; }
      publico texto sonido() { return "..."; }
  }
  clase Perro hereda Animal {         // herencia simple
      Perro(texto n, entero e) { super(n, e); }
      publico texto sonido() { return "Guau"; }   // sobrescritura virtual
  }
  Animal a = nuevo Perro("Rex", 3);   // upcasting
  imprimir(a.sonido());               // "Guau" -- despacho virtual

  Palabras clave: class|clase  extends|hereda  new|nuevo  this|este
  super|padre  public|publico  private|privado  null|nulo

  Clases y métodos abstractos (Etapa 7, hacen de "interfaz"):
      abstracta clase Figura { abstracto real area(); }
      Una subclase concreta DEBE implementar todo método abstracto
      heredado; nuevo sobre una clase abstracta es error (IL-POO-020).

  Miembros estáticos (Etapa 7, una sola copia compartida por clase):
      estatico entero contador;   // atributo
      NombreClase.contador        // acceso (también permitido vía instancia)

  Sobrecarga de métodos (Etapa 7, misma clase, distinta firma):
      publico void sumar(entero a) { ... }
      publico void sumar(entero a, entero b) { ... }
      Convive con el despacho virtual: la sobrecarga se resuelve por
      firma en compilación, la sobrescritura por la clase real en ejecución.

  Genéricos (Etapa 7, sustitución sintáctica al estilo template de C++):
      clase Caja<T> { publico T valor; }
      Caja<entero> c = nuevo Caja<entero>();
      Un solo parámetro de tipo, sin anidar ni combinar con herencia.
"""

_DOC_FUNCIONES = """FUNCIONES INTEGRADAS
====================================

--- Conversión de tipo (v1.0, §4/§19) ---
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

Errores: IL-EJE-003 desborde float->int   IL-EJE-004/005 texto->numerico inválido

--- Cadenas (Etapa 6) ---
  longitud_texto(s) / text_length     -> int, cantidad de caracteres
  subcadena(s,i,f) / substring        -> string, rango [inicio,fin)  (IL-EST-010)
  mayusculas(s) / to_upper            -> string
  minusculas(s) / to_lower            -> string
  caracter_en(s,i) / char_at          -> string, 1 carácter  (IL-EST-011)
  indice_de(s,sub) / index_of         -> int, posición o -1
  recortar(s) / trim                  -> string, sin espacios extremos

--- Matemática (Etapa 6) ---
  raiz_cuadrada(x) / sqrt             -> float  (IL-EST-012 si x<0)
  elevar(base,exp) / pow              -> float  (IL-EST-013 si resultado no es real)
  absoluto(n) / abs                   -> int
  piso(x) / floor                     -> int
  techo(x) / ceil                     -> int
  azar(min,max) / random              -> int uniforme en [min,max]  (IL-EST-014)

No hay maximo/minimo: con el operador ternario, "a > b ? a : b" los
vuelve triviales sin arriesgar colisión con variables de los programas
de referencia que ya usan esos nombres (ver builtins.py).

--- Cadenas y archivos (Etapa 10) ---
  invertir_texto(s) / reverse_string    -> string, cadena invertida
  existe_archivo(ruta) / file_exists    -> bool
  leer_archivo(ruta) / read_file        -> string, contenido completo (IL-EST-015)
  escribir_archivo(ruta,s) / write_file -> bool, reemplaza el archivo (IL-EST-016)
  agregar_archivo(ruta,s) / append_file -> bool, agrega al final (IL-EST-017)

Archivos: texto plano completo por llamada, siempre UTF-8 (sin lectura
línea a línea ni un tipo "manejador de archivo" nuevo).

Instrucciones integradas (no son funciones comunes):
  imprimir(expr) / print(expr)
  leer(var)      / read(var)

imprimir(objeto) personalizable (Etapa 10): si la clase declara
públicamente aTexto()/toString() (sin parámetros, retorna texto), se usa
esa representación en vez del formato automático Clase(campo=valor, ...).
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

POO — InvenioLang 2.0 (IL-POO) — docs/InvenioLang_2.0_POO.md
  001 Clase duplicada                    002 Clase padre inexistente
  003 Herencia circular                  004 Miembro duplicado en la clase
  005 Acceso a miembro privado           006 Miembro inexistente
  007 Constructor: aridad/tipos          008 super() fuera de constructor
  009 this/super fuera de un método      010 Asignación de tipo incompatible
  014/015 Sobrescritura con firma distinta al padre
  020 nuevo sobre clase abstracta        021 Método abstracto sin implementar
  022 abstract/static mal aplicado       023 abstracto sobre un atributo
  024 Clase abstracta con miembro inválido
  025 this/super en método estático      026 Acceso estático inválido
  027 Ninguna sobrecarga coincide con los argumentos
  029 Ninguna sobrecarga de CONSTRUCTOR coincide con los argumentos (E10)
  (019 ampliado en Etapa 10: también dos constructores con la misma firma)

ESTRUCTURADO — Etapa 6 (IL-EST) — docs/InvenioLang_Etapa6_Estructurado.md
  001 switch: expresión no es int/string/bool
  002 case no coincide con el tipo del switch
  003 Valor de case duplicado            004 Ramas del ternario incompatibles
  010 subcadena: rango inválido          011 caracter_en: índice fuera de rango
  012 raiz_cuadrada: argumento negativo  013 elevar: resultado no es real
  014 azar: mínimo mayor que máximo
  015 leer_archivo: no se pudo leer (E10)
  016 escribir_archivo: no se pudo escribir (E10)
  017 agregar_archivo: no se pudo escribir (E10)
  (IL-SEM-040/041 break/continue se reutilizan sin cambios; ahora
  break también es válido dentro de un switch)
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
    "hola_mundo",
    "tipos",
    "condicionales",
    "ciclos",
    "funciones",
    "procedimientos",
    "arreglos",
    "matrices",
    "sistema_ventas",
    "calculadora",
    "estadisticas",
    "conversor",
    # Apendice E (Seccion 17): faltaban en el menu, ya cubiertos por
    # conformidad.py::REFERENCIA desde la v1.0
    "escapes",
    "calculadora_es",
    "guardia",
    "hanoi",
    # Estructuras de Datos (InvenioLang 2.0): sin objetos y con objetos
    "pila_arreglo",
    "cola_arreglo",
    "lista_enlazada",
    "pila_enlazada",
    "cola_enlazada",
    "arbol_binario",
    "arreglo_objetos",
    # Etapa 6: lenguaje estructurado completo
    "estructurado",
    # Etapa 7: POO completo (abstractas, estaticos, sobrecarga, genericos)
    "poo_completo",
    # Etapa 8: mas estructuras de datos y algoritmos, sin y con objetos
    "tabla_hash_arreglo",
    "grafo_matriz",
    "ordenamiento_insercion",
    "ordenamiento_seleccion",
    "busqueda_binaria",
    "quicksort",
    "mergesort",
    "grafo_lista_adyacencia",
    "tabla_hash_encadenada",
    # Etapa 10: cierre de brechas de Fase 1/Fase 2 (sobrecarga de
    # constructores, aTexto()/toString(), monticulo, archivos)
    "poo_extendido",
    "monticulo",
    "heapsort",
    "archivo_io",
    # Etapa 11: patrones de diseño (visibilidad de constructores + esIgual())
    "patron_singleton",
    "patron_factory",
    "patron_observer",
    "patron_strategy",
    "patron_decorator",
    # Etapa 11: algoritmos de grafos con peso
    "dijkstra",
    "kruskal",
    "orden_topologico",
    # Etapa 11: backtracking y programacion dinamica
    "n_reinas",
    "permutaciones",
    "fibonacci_memo",
    "mochila",
    # Etapa 11: lista doblemente enlazada y deque
    "lista_doble",
    "deque",
    # Etapa 11: arbol AVL
    "arbol_avl",
    # Etapa 11: enumeraciones
    "enumeraciones",
    # Etapa 11: operadores bit a bit
    "bit_a_bit",
    # Etapa 12: recursion de cola (TCO) -- ver comentarios del archivo
    # para el experimento con --run-ir-opt (fuera del alcance de un
    # ejemplo que solo se ejecuta desde el menu)
    "suma_cola",
    # Etapa 12.9/12.10: tipos suma (enum con carga) + pattern matching
    "tipos_suma",
]
