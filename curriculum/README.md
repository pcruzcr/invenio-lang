# Currículo InvenioLang (es)

*[English version](README.en.md)*

Currículo progresivo de **13 niveles y 133 ejercicios** que cubre Programación I,
arreglos y matrices, cadenas, Programación II (POO y patrones de diseño),
estructuras de datos (pilas, colas, listas, árboles, montículos, tablas hash y
grafos) y complejidad algorítmica. Cada ejercicio existe **dos veces**: con las
palabras clave en español (`es/nivelNN/`) y con las palabras clave en inglés
(`en/levelNN/`). Las dos versiones producen exactamente la misma salida (INV-1200).

## Estructura

```
curriculum/
  runner.py                 ejecutor y verificador (ambos idiomas)
  es/nivel01 … es/nivel13   versión con palabras clave en español
  en/level01 … en/level13   versión con palabras clave en inglés
    nivel.json              título, descripción y temas del nivel
    NN_nombre.inv           solución de referencia comentada
    NN_nombre.expected      salida exacta esperada
    NN_nombre.json          id, título, enunciado, objetivos, pistas graduadas, conceptos
    NN_nombre.entrada       (opcional) una línea por cada leer
```

Las parejas se reconocen por el `id` del JSON (`N04-E05` es el ejercicio 5 del
nivel 4 en ambos idiomas). El enunciado, los objetivos y las pistas están
escritos en el idioma de la carpeta; los textos que imprimen los programas son
los mismos en ambas versiones (por eso usan rótulos neutros como `sum =`,
`max =` o `BFS:`), de modo que un solo `.expected` sirve para comparar las dos.

Cada `.inv` empieza con una cabecera de título y objetivos y está comentado
para explicar el *porqué* de cada paso. Las **pistas son graduadas**: la
primera orienta, la segunda acerca a la idea clave y la tercera casi da la
solución.

## Ejecutar y verificar

```bash
python curriculum/runner.py                       # todo el currículo, ambas versiones
python curriculum/runner.py 4 nivel5              # solo los niveles 4 y 5
python curriculum/runner.py --version es          # solo la versión en español
python curriculum/runner.py --idioma en           # mensajes, enunciados y pistas en inglés
python curriculum/runner.py --ejercicio N04-E05 --enunciado --pistas 3
```

El ejecutor compara la salida **exacta** (solo tolera `\r\n` y saltos de línea
finales), comprueba que la versión `es` y la `en` produzcan lo mismo, muestra
en caso de fallo el enunciado, los objetivos y las pistas pedidas, y termina
con código 0 si todo pasa, 1 si algo falla y 2 si no hay nada que ejecutar.
Los ejercicios con `leer` reciben su `.entrada`; nunca se espera teclado.
Las pruebas `tests/test_curriculum.py` ejecutan TODO el currículo en ambos
idiomas y validan la estructura; el paso «Curriculum» del CI ejecuta el runner.

## Añadir un ejercicio

1. Escribe `es/nivelNN/MM_nombre.inv` y su `.expected` (y `.entrada` si lee datos).
2. Escribe la versión inglesa `en/levelNN/MM_name.inv` con las mismas
   instrucciones, identificadores y comentarios en inglés y **la misma salida**.
3. Crea los dos `.json` con el mismo `id` (`NNN-EMM`), cada uno en su idioma,
   con al menos tres pistas graduadas.
4. Ejecuta `python curriculum/runner.py NN` y `pytest tests/test_curriculum.py`.

## Construcciones que el currículo evita (y por qué)

Al escribir los ejercicios se encontraron estos límites del lenguaje actual;
los programas los esquivan sin perder valor didáctico:

- Acceso a miembros de un solo nivel: `a.sig.valor` no es válido; se usa
  `Nodo s = a.sig; s.valor` (documentado en `docs/InvenioLang_2.0_POO.md` §8).
- Las clases no tienen atributos de tipo arreglo: las pilas/colas con arreglo y
  las tablas hash usan arreglos globales o pasados por parámetro.
- `leer` solo acepta una variable (no `leer(a[i])`), `a[i]++` no existe y no se
  puede encadenar una llamada sobre `nuevo C()`.
- Los parámetros no pueden ser de tipo función: el comparador intercambiable
  (N05-E09) usa una variable global de tipo `funcion`.
- Defectos del intérprete pendientes de corrección en el núcleo (ver el informe
  de la Fase 1): `i += 2` en la actualización de un `para` asigna en vez de
  sumar; una declaración local dentro de un bloque con el mismo nombre que una
  global sobrescribe la global; y una función que lee una global ve la local
  homónima de quien la llama. Los ejercicios usan `i = i + 2` y evitan
  sombrear globales desde `main`.

## Mapa del currículo
### Nivel 1 — Fundamentos: variables, tipos, operadores y E/S

Primeros programas: mostrar datos, guardar valores en variables, operar con ellos y leer datos del usuario.

**Temas:** salida con imprimir; variables y constantes; tipos entero, real, texto y logico; operadores aritméticos, relacionales y lógicos; entrada con leer; conversiones de tipo.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N01-E01 | Hola, mundo | [`01_hola_mundo.inv`](es/nivel01/01_hola_mundo.inv) | programa, main, salida |
| N01-E02 | Variables y asignación | [`02_variables.inv`](es/nivel01/02_variables.inv) | variable, asignación, intercambio |
| N01-E03 | Tipos de datos | [`03_tipos_de_datos.inv`](es/nivel01/03_tipos_de_datos.inv) | entero, real, texto, logico |
| N01-E04 | Constantes | [`04_constantes.inv`](es/nivel01/04_constantes.inv) | constante, expresión |
| N01-E05 | Operadores aritméticos | [`05_operadores_aritmeticos.inv`](es/nivel01/05_operadores_aritmeticos.inv) | división entera, módulo, división real |
| N01-E06 | Precedencia de operadores | [`06_precedencia.inv`](es/nivel01/06_precedencia.inv) | precedencia, asociatividad, paréntesis |
| N01-E07 | Operadores relacionales y lógicos | [`07_relacionales_y_logicos.inv`](es/nivel01/07_relacionales_y_logicos.inv) | comparación, conjunción, disyunción, negación |
| N01-E08 | Entrada de datos | [`08_entrada_de_datos.inv`](es/nivel01/08_entrada_de_datos.inv) | entrada, leer |
| N01-E09 | Conversión de tipos | [`09_conversiones.inv`](es/nivel01/09_conversiones.inv) | conversión, truncamiento, concatenación |
| N01-E10 | Cadenas básicas | [`10_cadenas_basicas.inv`](es/nivel01/10_cadenas_basicas.inv) | cadena, índice, subcadena |
| N01-E11 | Incremento y asignación compuesta | [`11_incremento_y_asignacion_compuesta.inv`](es/nivel01/11_incremento_y_asignacion_compuesta.inv) | incremento, asignación compuesta |
| N01-E12 | Conversor de temperatura | [`12_conversor_temperatura.inv`](es/nivel01/12_conversor_temperatura.inv) | entrada-proceso-salida, fórmula |

### Nivel 2 — Control de flujo: decisiones y ciclos

Programación estructurada: elegir entre caminos (si, segun, ternario) y repetir (mientras, hacer-mientras, para, para_cada).

**Temas:** si / sino y cadenas si-sino-si; segun / caso; operador ternario; mientras, hacer-mientras, para; romper y continuar; ciclos anidados; acumuladores y contadores.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N02-E01 | Par o impar | [`01_par_o_impar.inv`](es/nivel02/01_par_o_impar.inv) | condicional, si/sino, módulo |
| N02-E02 | Calificación con si-sino-si | [`02_calificacion_con_si_sino_si.inv`](es/nivel02/02_calificacion_con_si_sino_si.inv) | si-sino-si, condiciones excluyentes |
| N02-E03 | Selección múltiple con segun | [`03_segun_caso.inv`](es/nivel02/03_segun_caso.inv) | segun, caída en cascada, romper |
| N02-E04 | Operador ternario | [`04_operador_ternario.inv`](es/nivel02/04_operador_ternario.inv) | ternario, expresión condicional |
| N02-E05 | Ciclo mientras | [`05_ciclo_mientras.inv`](es/nivel02/05_ciclo_mientras.inv) | mientras, condición de parada, contador |
| N02-E06 | hacer-mientras: validar la entrada | [`06_hacer_mientras_validacion.inv`](es/nivel02/06_hacer_mientras_validacion.inv) | hacer-mientras, validación |
| N02-E07 | Ciclo para: tabla de multiplicar | [`07_ciclo_para_tabla.inv`](es/nivel02/07_ciclo_para_tabla.inv) | para, variable de control |
| N02-E08 | Ciclos anidados: figuras | [`08_ciclos_anidados.inv`](es/nivel02/08_ciclos_anidados.inv) | ciclos anidados, patrones |
| N02-E09 | romper y continuar | [`09_romper_y_continuar.inv`](es/nivel02/09_romper_y_continuar.inv) | romper, continuar |
| N02-E10 | Acumuladores y contadores | [`10_acumuladores_y_contadores.inv`](es/nivel02/10_acumuladores_y_contadores.inv) | acumulador, contador, máximo |
| N02-E11 | Dígitos de un número | [`11_digitos_de_un_numero.inv`](es/nivel02/11_digitos_de_un_numero.inv) | descomposición en dígitos, mientras |
| N02-E12 | Números primos | [`12_numeros_primos.inv`](es/nivel02/12_numeros_primos.inv) | bandera, ciclos anidados, primalidad |
| N02-E13 | Recorrido con para_cada | [`13_para_cada.inv`](es/nivel02/13_para_cada.inv) | para_cada, recorrido |

### Nivel 3 — Funciones, procedimientos y recursión

Descomponer un problema en subprogramas reutilizables, pasar parámetros y resolver problemas que se definen en términos de sí mismos.

**Temas:** funciones con retorno; procedimientos (vacio); paso por valor y por referencia (arreglos); alcance de variables; recursión: caso base y caso recursivo; funciones como valores.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N03-E01 | Funciones con retorno | [`01_funciones.inv`](es/nivel03/01_funciones.inv) | función, parámetro, retornar |
| N03-E02 | Procedimientos | [`02_procedimientos.inv`](es/nivel03/02_procedimientos.inv) | procedimiento, reutilización |
| N03-E03 | Paso por valor y por referencia | [`03_paso_de_parametros.inv`](es/nivel03/03_paso_de_parametros.inv) | paso por valor, paso por referencia |
| N03-E04 | Alcance de variables | [`04_alcance_de_variables.inv`](es/nivel03/04_alcance_de_variables.inv) | alcance, variable global, ocultamiento |
| N03-E05 | Funciones lógicas | [`05_funciones_logicas.inv`](es/nivel03/05_funciones_logicas.inv) | función lógica, año bisiesto |
| N03-E06 | Factorial recursivo | [`06_factorial_recursivo.inv`](es/nivel03/06_factorial_recursivo.inv) | recursión, caso base, pila de llamadas |
| N03-E07 | Fibonacci: recursivo e iterativo | [`07_fibonacci.inv`](es/nivel03/07_fibonacci.inv) | recursión múltiple, iteración, costo exponencial |
| N03-E08 | Potencia rápida | [`08_potencia_rapida.inv`](es/nivel03/08_potencia_rapida.inv) | divide y vencerás, recursión |
| N03-E09 | Máximo común divisor (Euclides) | [`09_mcd_euclides.inv`](es/nivel03/09_mcd_euclides.inv) | algoritmo de Euclides, recursión |
| N03-E10 | Torres de Hanói | [`10_torres_de_hanoi.inv`](es/nivel03/10_torres_de_hanoi.inv) | recursión, divide y vencerás |
| N03-E11 | Recursión con cadenas y dígitos | [`11_recursion_con_cadenas.inv`](es/nivel03/11_recursion_con_cadenas.inv) | recursión, palíndromo, base 2 |
| N03-E12 | Funciones como valores | [`12_funciones_como_valores.inv`](es/nivel03/12_funciones_como_valores.inv) | función de primera clase, orden superior, lambda |

### Nivel 4 — Arreglos y vectores: recorridos y búsqueda

Guardar colecciones de datos del mismo tipo, recorrerlas, buscar en ellas y transformarlas en el lugar.

**Temas:** declaración e inicialización de arreglos; recorridos; máximos, mínimos y promedios; búsqueda lineal y binaria; conteo de frecuencias; transformaciones en el lugar.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N04-E01 | Declarar y recorrer un arreglo | [`01_declarar_y_recorrer.inv`](es/nivel04/01_declarar_y_recorrer.inv) | arreglo, índice, recorrido |
| N04-E02 | Suma, promedio y valores sobre el promedio | [`02_suma_y_promedio.inv`](es/nivel04/02_suma_y_promedio.inv) | arreglo, acumulador, dos pasadas |
| N04-E03 | Máximo, mínimo y sus posiciones | [`03_maximo_y_minimo.inv`](es/nivel04/03_maximo_y_minimo.inv) | máximo, mínimo, posición |
| N04-E04 | Búsqueda lineal | [`04_busqueda_lineal.inv`](es/nivel04/04_busqueda_lineal.inv) | búsqueda lineal, centinela, O(n) |
| N04-E05 | Búsqueda binaria | [`05_busqueda_binaria.inv`](es/nivel04/05_busqueda_binaria.inv) | búsqueda binaria, divide y vencerás, O(log n) |
| N04-E06 | Búsqueda binaria recursiva | [`06_busqueda_binaria_recursiva.inv`](es/nivel04/06_busqueda_binaria_recursiva.inv) | recursión, búsqueda binaria |
| N04-E07 | Invertir en el lugar | [`07_invertir_en_el_lugar.inv`](es/nivel04/07_invertir_en_el_lugar.inv) | dos punteros, intercambio, en el lugar |
| N04-E08 | Conteo de frecuencias | [`08_conteo_de_frecuencias.inv`](es/nivel04/08_conteo_de_frecuencias.inv) | arreglo de contadores, histograma, moda |
| N04-E09 | Rotar un arreglo | [`09_rotar_arreglo.inv`](es/nivel04/09_rotar_arreglo.inv) | rotación, subrango |
| N04-E10 | Eliminar duplicados de un arreglo ordenado | [`10_eliminar_duplicados.inv`](es/nivel04/10_eliminar_duplicados.inv) | tamaño lógico, dos índices |
| N04-E11 | Sumas prefijas | [`11_sumas_prefijas.inv`](es/nivel04/11_sumas_prefijas.inv) | suma prefija, precálculo |
| N04-E12 | Mezclar dos arreglos ordenados | [`12_mezclar_ordenados.inv`](es/nivel04/12_mezclar_ordenados.inv) | mezcla, O(n + m) |

### Nivel 5 — Algoritmos de ordenamiento

Ordenar datos con algoritmos clásicos (burbuja, selección, inserción, mezcla, rápido y conteo), seguir su funcionamiento paso a paso y comparar su trabajo.

**Temas:** burbuja; selección; inserción; merge sort; quick sort; ordenamiento por conteo; estabilidad y criterios de orden.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N05-E01 | Ordenamiento burbuja | [`01_burbuja.inv`](es/nivel05/01_burbuja.inv) | burbuja, comparación, O(n²) |
| N05-E02 | Burbuja optimizada | [`02_burbuja_optimizada.inv`](es/nivel05/02_burbuja_optimizada.inv) | bandera, mejor caso, peor caso |
| N05-E03 | Ordenamiento por selección | [`03_seleccion.inv`](es/nivel05/03_seleccion.inv) | selección, invariante |
| N05-E04 | Ordenamiento por inserción | [`04_insercion.inv`](es/nivel05/04_insercion.inv) | inserción, desplazamiento |
| N05-E05 | Merge sort (ordenamiento por mezcla) | [`05_merge_sort.inv`](es/nivel05/05_merge_sort.inv) | merge sort, divide y vencerás, O(n log n) |
| N05-E06 | Quick sort (ordenamiento rápido) | [`06_quick_sort.inv`](es/nivel05/06_quick_sort.inv) | quick sort, pivote, partición |
| N05-E07 | Ordenamiento por conteo | [`07_ordenamiento_por_conteo.inv`](es/nivel05/07_ordenamiento_por_conteo.inv) | conteo, O(n + k) |
| N05-E08 | Ordenar registros con arreglos paralelos | [`08_ordenar_registros.inv`](es/nivel05/08_ordenar_registros.inv) | arreglos paralelos, estabilidad, orden descendente |
| N05-E09 | Criterio de orden intercambiable | [`09_criterio_de_orden.inv`](es/nivel05/09_criterio_de_orden.inv) | función como valor, comparador |

### Nivel 6 — Matrices

Arreglos bidimensionales: recorridos por filas y columnas, operaciones de álgebra lineal y problemas sobre tablas.

**Temas:** declaración y recorrido por filas/columnas; suma y producto de matrices; transpuesta; diagonales; propiedades: simetría, identidad; matrices como tablas de datos.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N06-E01 | Recorrer una matriz | [`01_recorrido_de_matriz.inv`](es/nivel06/01_recorrido_de_matriz.inv) | matriz, fila, columna |
| N06-E02 | Tabla de ventas: totales por fila y columna | [`02_tabla_de_ventas.inv`](es/nivel06/02_tabla_de_ventas.inv) | totales por fila, totales por columna |
| N06-E03 | Suma de matrices | [`03_suma_de_matrices.inv`](es/nivel06/03_suma_de_matrices.inv) | suma de matrices, parámetro matriz |
| N06-E04 | Producto de matrices | [`04_producto_de_matrices.inv`](es/nivel06/04_producto_de_matrices.inv) | producto de matrices, producto punto, O(n³) |
| N06-E05 | Matriz transpuesta | [`05_transpuesta.inv`](es/nivel06/05_transpuesta.inv) | transpuesta, en el lugar |
| N06-E06 | Diagonales | [`06_diagonales.inv`](es/nivel06/06_diagonales.inv) | diagonal principal, diagonal secundaria, triángulo superior |
| N06-E07 | Propiedades: simétrica e identidad | [`07_propiedades_de_matrices.inv`](es/nivel06/07_propiedades_de_matrices.inv) | matriz simétrica, matriz identidad, contraejemplo |
| N06-E08 | Triángulo de Pascal | [`08_triangulo_de_pascal.inv`](es/nivel06/08_triangulo_de_pascal.inv) | programación dinámica, coeficientes binomiales |
| N06-E09 | Rotar una matriz 90 grados | [`09_rotar_matriz.inv`](es/nivel06/09_rotar_matriz.inv) | rotación, composición |

### Nivel 7 — Cadenas de caracteres

Procesar texto carácter a carácter: contar, buscar, transformar, cifrar y comprimir cadenas.

**Temas:** recorrido carácter a carácter; búsqueda de subcadenas; transformaciones (mayúsculas, inversión); palabras y separadores; cifrado César; conversión número-texto; compresión RLE.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N07-E01 | Contar vocales, consonantes y espacios | [`01_contar_caracteres.inv`](es/nivel07/01_contar_caracteres.inv) | recorrido de cadena, clasificación |
| N07-E02 | Invertir y detectar palíndromos | [`02_palindromos.inv`](es/nivel07/02_palindromos.inv) | concatenación, normalización, palíndromo |
| N07-E03 | Capitalizar palabras | [`03_capitalizar_palabras.inv`](es/nivel07/03_capitalizar_palabras.inv) | máquina de estados, palabras |
| N07-E04 | Buscar una subcadena | [`04_buscar_subcadena.inv`](es/nivel07/04_buscar_subcadena.inv) | búsqueda de patrones, solapamiento |
| N07-E05 | Cifrado César | [`05_cifrado_cesar.inv`](es/nivel07/05_cifrado_cesar.inv) | cifrado, aritmética modular |
| N07-E06 | Convertir entre números y texto | [`06_numeros_y_texto.inv`](es/nivel07/06_numeros_y_texto.inv) | base 2, esquema de Horner, conversión |
| N07-E07 | Anagramas | [`07_anagramas.inv`](es/nivel07/07_anagramas.inv) | anagrama, arreglo de conteo |
| N07-E08 | Compresión RLE | [`08_compresion_rle.inv`](es/nivel07/08_compresion_rle.inv) | RLE, corrida, compresión |

### Nivel 8 — POO I: clases y objetos

Programación II: modelar entidades con clases, proteger su estado (encapsulamiento), construir objetos de varias formas y combinarlos.

**Temas:** clases, atributos y métodos; encapsulamiento: publico/privado; constructores y sobrecarga; aTexto/toString y esIgual/equals; miembros estáticos; composición; arreglos de objetos; referencias y nulo; enumeraciones.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N08-E01 | Mi primera clase | [`01_primera_clase.inv`](es/nivel08/01_primera_clase.inv) | clase, objeto, método, constructor |
| N08-E02 | Encapsulamiento: cuenta bancaria | [`02_encapsulamiento.inv`](es/nivel08/02_encapsulamiento.inv) | encapsulamiento, privado, invariante, getter |
| N08-E03 | Sobrecarga de constructores | [`03_constructores.inv`](es/nivel08/03_constructores.inv) | sobrecarga, constructor |
| N08-E04 | Fracciones: aTexto y objetos inmutables | [`04_fracciones_y_atexto.inv`](es/nivel08/04_fracciones_y_atexto.inv) | aTexto/toString, inmutabilidad |
| N08-E05 | Miembros estáticos | [`05_miembros_estaticos.inv`](es/nivel08/05_miembros_estaticos.inv) | estatico, atributo de clase |
| N08-E06 | Composición: un auto tiene un motor | [`06_composicion.inv`](es/nivel08/06_composicion.inv) | composición, delegación, tiene-un |
| N08-E07 | Arreglo de objetos | [`07_arreglo_de_objetos.inv`](es/nivel08/07_arreglo_de_objetos.inv) | arreglo de objetos, recorrido |
| N08-E08 | Referencias, nulo e igualdad | [`08_referencias_e_igualdad.inv`](es/nivel08/08_referencias_e_igualdad.inv) | referencia, alias, nulo, igualdad |
| N08-E09 | Enumeraciones | [`09_enumeraciones.inv`](es/nivel08/09_enumeraciones.inv) | enumeración, emparejar, exhaustividad |

### Nivel 9 — POO II: herencia, polimorfismo y patrones de diseño

Reutilizar y extender comportamiento con herencia, programar contra abstracciones (clases abstractas e interfaces) y aplicar patrones de diseño clásicos.

**Temas:** herencia y padre/super; sobrescritura y polimorfismo; clases abstractas; interfaces; sobrecarga y genéricos; patrones: Strategy, Observer, Factory, Singleton, Template Method, Decorator; tipos suma y emparejar.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N09-E01 | Herencia | [`01_herencia.inv`](es/nivel09/01_herencia.inv) | herencia, es-un, padre/super |
| N09-E02 | Polimorfismo | [`02_polimorfismo.inv`](es/nivel09/02_polimorfismo.inv) | polimorfismo, sobrescritura, despacho dinámico |
| N09-E03 | Clases abstractas | [`03_clase_abstracta.inv`](es/nivel09/03_clase_abstracta.inv) | clase abstracta, método abstracto, contrato |
| N09-E04 | Interfaces | [`04_interfaces.inv`](es/nivel09/04_interfaces.inv) | interfaz, implementa, capacidad |
| N09-E05 | Sobrecarga de métodos y genéricos | [`05_sobrecarga_y_genericos.inv`](es/nivel09/05_sobrecarga_y_genericos.inv) | sobrecarga, genéricos, parámetro de tipo |
| N09-E06 | Patrón Strategy | [`06_patron_strategy.inv`](es/nivel09/06_patron_strategy.inv) | Strategy, composición, abierto/cerrado |
| N09-E07 | Patrón Observer | [`07_patron_observer.inv`](es/nivel09/07_patron_observer.inv) | Observer, evento, bajo acoplamiento |
| N09-E08 | Patrón Factory | [`08_patron_factory.inv`](es/nivel09/08_patron_factory.inv) | Factory, creación de objetos |
| N09-E09 | Patrón Singleton | [`09_patron_singleton.inv`](es/nivel09/09_patron_singleton.inv) | Singleton, constructor privado, inicialización perezosa |
| N09-E10 | Patrón Template Method | [`10_patron_template_method.inv`](es/nivel09/10_patron_template_method.inv) | Template Method, gancho |
| N09-E11 | Patrón Decorator | [`11_patron_decorator.inv`](es/nivel09/11_patron_decorator.inv) | Decorator, envoltura, composición |
| N09-E12 | Tipos suma y emparejar | [`12_tipos_suma.inv`](es/nivel09/12_tipos_suma.inv) | tipo suma, emparejar, desestructuración |

### Nivel 10 — Estructuras de datos lineales: pilas, colas y listas

Implementar pilas y colas con arreglos y con nodos enlazados, listas simples y dobles, y usarlas para resolver problemas clásicos.

**Temas:** pila con arreglo y enlazada; cola circular y enlazada; lista simplemente enlazada; lista doblemente enlazada; aplicaciones: paréntesis, postfija, Josefo.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N10-E01 | Pila con arreglo | [`01_pila_con_arreglo.inv`](es/nivel10/01_pila_con_arreglo.inv) | pila, LIFO, desbordamiento |
| N10-E02 | Pila enlazada | [`02_pila_enlazada.inv`](es/nivel10/02_pila_enlazada.inv) | pila, nodo, lista enlazada |
| N10-E03 | Paréntesis balanceados | [`03_parentesis_balanceados.inv`](es/nivel10/03_parentesis_balanceados.inv) | pila, análisis sintáctico, balanceo |
| N10-E04 | Evaluar expresiones postfijas | [`04_evaluacion_postfija.inv`](es/nivel10/04_evaluacion_postfija.inv) | notación postfija, pila |
| N10-E05 | Cola circular con arreglo | [`05_cola_circular.inv`](es/nivel10/05_cola_circular.inv) | cola, FIFO, buffer circular |
| N10-E06 | Cola enlazada: simulación de turnos | [`06_cola_enlazada.inv`](es/nivel10/06_cola_enlazada.inv) | cola, FIFO, simulación |
| N10-E07 | Lista simplemente enlazada | [`07_lista_simple.inv`](es/nivel10/07_lista_simple.inv) | lista enlazada, nodo, enlace |
| N10-E08 | Lista doblemente enlazada | [`08_lista_doble.inv`](es/nivel10/08_lista_doble.inv) | lista doble, recorrido inverso |
| N10-E09 | Lista ordenada | [`09_lista_ordenada.inv`](es/nivel10/09_lista_ordenada.inv) | invariante, inserción ordenada |
| N10-E10 | Problema de Josefo con lista circular | [`10_problema_de_josefo.inv`](es/nivel10/10_problema_de_josefo.inv) | lista circular, simulación |

### Nivel 11 — Árboles, montículos y tablas hash

Estructuras no lineales y de acceso rápido: árboles binarios de búsqueda (inserción, recorridos, altura, eliminación), AVL, montículos y tablas hash.

**Temas:** árbol binario de búsqueda; recorridos pre/in/post/niveles; altura y conteos recursivos; eliminación en ABB; árbol AVL y rotaciones; montículo binario; tablas hash: sondeo lineal y encadenamiento.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N11-E01 | Árbol binario de búsqueda: inserción | [`01_abb_insercion.inv`](es/nivel11/01_abb_insercion.inv) | ABB, recursión, en orden |
| N11-E02 | Recorridos de un árbol | [`02_abb_recorridos.inv`](es/nivel11/02_abb_recorridos.inv) | preorden, en orden, postorden |
| N11-E03 | Búsqueda, mínimo y máximo en un ABB | [`03_abb_busqueda.inv`](es/nivel11/03_abb_busqueda.inv) | búsqueda en ABB, camino, O(h) |
| N11-E04 | Altura, nodos y hojas | [`04_abb_altura_y_conteos.inv`](es/nivel11/04_abb_altura_y_conteos.inv) | altura, hoja, árbol degenerado |
| N11-E05 | Eliminación en un ABB | [`05_abb_eliminacion.inv`](es/nivel11/05_abb_eliminacion.inv) | eliminación, sucesor en orden |
| N11-E06 | Recorrido por niveles (BFS en árboles) | [`06_recorrido_por_niveles.inv`](es/nivel11/06_recorrido_por_niveles.inv) | recorrido por niveles, BFS, cola |
| N11-E07 | Montículo mínimo (cola de prioridad) | [`07_monticulo_minimo.inv`](es/nivel11/07_monticulo_minimo.inv) | montículo, cola de prioridad, O(log n) |
| N11-E08 | Árbol AVL: inserción con rotaciones | [`08_arbol_avl.inv`](es/nivel11/08_arbol_avl.inv) | AVL, rotación, factor de balance |
| N11-E09 | Tabla hash con sondeo lineal | [`09_hash_sondeo_lineal.inv`](es/nivel11/09_hash_sondeo_lineal.inv) | tabla hash, colisión, sondeo lineal |
| N11-E10 | Tabla hash con encadenamiento | [`10_hash_encadenada.inv`](es/nivel11/10_hash_encadenada.inv) | encadenamiento, diccionario, función hash |

### Nivel 12 — Grafos

Representar relaciones con matrices y listas de adyacencia, recorrerlas (BFS, DFS) y resolver problemas clásicos: caminos mínimos, componentes, orden topológico y ciclos.

**Temas:** matriz de adyacencia; lista de adyacencia; BFS y DFS; camino mínimo sin pesos; componentes conexas; Dijkstra; orden topológico; detección de ciclos.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N12-E01 | Matriz de adyacencia | [`01_matriz_de_adyacencia.inv`](es/nivel12/01_matriz_de_adyacencia.inv) | grafo, matriz de adyacencia, grado |
| N12-E02 | Lista de adyacencia | [`02_lista_de_adyacencia.inv`](es/nivel12/02_lista_de_adyacencia.inv) | lista de adyacencia, grafo disperso |
| N12-E03 | Recorrido en anchura (BFS) | [`03_bfs.inv`](es/nivel12/03_bfs.inv) | BFS, cola, distancia |
| N12-E04 | Recorrido en profundidad (DFS) | [`04_dfs.inv`](es/nivel12/04_dfs.inv) | DFS, recursión, pila |
| N12-E05 | Reconstruir el camino más corto | [`05_camino_mas_corto_bfs.inv`](es/nivel12/05_camino_mas_corto_bfs.inv) | predecesor, camino mínimo, BFS |
| N12-E06 | Componentes conexas | [`06_componentes_conexas.inv`](es/nivel12/06_componentes_conexas.inv) | componente conexa, DFS |
| N12-E07 | Caminos mínimos con pesos: Dijkstra | [`07_dijkstra.inv`](es/nivel12/07_dijkstra.inv) | Dijkstra, relajación, algoritmo voraz |
| N12-E08 | Orden topológico (Kahn) | [`08_orden_topologico.inv`](es/nivel12/08_orden_topologico.inv) | orden topológico, grafo dirigido acíclico, grado de entrada |
| N12-E09 | Detección de ciclos en grafos dirigidos | [`09_deteccion_de_ciclos.inv`](es/nivel12/09_deteccion_de_ciclos.inv) | ciclo, arista de retroceso, DFS |

### Nivel 13 — Complejidad algorítmica

Medir el trabajo de los algoritmos contando operaciones y relacionarlo con la notación O: O(1), O(log n), O(n), O(n log n), O(n²) y O(2^n).

**Temas:** conteo de operaciones; órdenes de crecimiento; mejor, peor y caso promedio; O(n²) frente a O(n log n); memoización; rediseñar un algoritmo para bajar su orden.

| # | Ejercicio | Archivo | Conceptos |
|---|---|---|---|
| N13-E01 | Órdenes de crecimiento | [`01_ordenes_de_crecimiento.inv`](es/nivel13/01_ordenes_de_crecimiento.inv) | notación O, O(log n), O(n²) |
| N13-E02 | Búsqueda lineal frente a binaria | [`02_lineal_vs_binaria.inv`](es/nivel13/02_lineal_vs_binaria.inv) | peor caso, O(n), O(log n) |
| N13-E03 | O(n²) frente a O(n log n): burbuja y merge sort | [`03_burbuja_vs_merge.inv`](es/nivel13/03_burbuja_vs_merge.inv) | O(n²), O(n log n), análisis empírico |
| N13-E04 | De exponencial a lineal: memoización | [`04_memoizacion.inv`](es/nivel13/04_memoizacion.inv) | memoización, programación dinámica, O(2^n) |
| N13-E05 | Mejor, peor y caso promedio: inserción | [`05_mejor_y_peor_caso.inv`](es/nivel13/05_mejor_y_peor_caso.inv) | mejor caso, peor caso, caso promedio |
| N13-E06 | Subarreglo de suma máxima: O(n²) frente a O(n) | [`06_subarreglo_maximo.inv`](es/nivel13/06_subarreglo_maximo.inv) | Kadane, O(n), O(n²) |
| N13-E07 | Par con suma dada: O(n²) frente a O(n) | [`07_dos_sumas.inv`](es/nivel13/07_dos_sumas.inv) | dos punteros, O(n), O(n²) |
| N13-E08 | Quick sort: el peor caso importa | [`08_quicksort_peor_caso.inv`](es/nivel13/08_quicksort_peor_caso.inv) | quick sort, peor caso, pivote |
