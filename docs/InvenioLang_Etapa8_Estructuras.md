# InvenioLang — Etapa 8: Más Estructuras de Datos y Algoritmos

Documento formal de la Etapa 8 (Fase 1 + Fase 2), con el mismo nivel de
rigor que `docs/InvenioLang_Etapa6_Estructurado.md`. A diferencia de las
Etapas 6 y 7, esta etapa **no toca el lenguaje**: es puramente un conjunto
de programas de referencia en `pruebas/*.inv` — verificados contra
`pruebas/conformidad.py` (grupo `estructuras`, ver §4) — que cierran los
huecos de cobertura de grafos, tablas hash y algoritmos de ordenamiento/
búsqueda identificados al comparar Fase 1/Fase 2 contra los temarios de
Estructuras de Datos y Algoritmos.

## 0. Por qué esta etapa

Antes de la Etapa 8, `pruebas/` cubría pilas, colas, listas enlazadas y
árboles binarios (Etapa 3), pero **nada** de grafos ni tablas hash, y solo
burbuja + búsqueda lineal en algoritmos. El usuario confirmó el alcance:
las estructuras nuevas se implementan **en InvenioLang**, con las
herramientas que el lenguaje ya tiene (clases desde la Etapa 2, arreglos y
arreglos de objetos desde las Etapas 1 y 3) — no como tipos nativos nuevos
del intérprete. Esto es deliberado: el valor pedagógico de una tabla hash o
un grafo está en programarlos, no en invocar un tipo ya resuelto.

## 1. Limitación de lenguaje que moldeó el diseño

InvenioLang no soporta **atributos de arreglo** dentro de una clase (solo
atributos escalares — confirmado revisando las producciones de
`miembro_clase` en `parser.py`; es una limitación real y preexistente, no
algo que esta etapa quitó). Esto descarta, por ejemplo, una clase `Grafo`
con un atributo `NodoAdj[] cabezas;`, o una clase `TablaHash` con un
atributo `int[] claves;`.

**Patrón de solución, reutilizado en todos los archivos "con objetos" de
esta etapa**: el arreglo (de cabezas de lista de adyacencia, de cubetas de
una tabla hash, etc.) vive como **variable local** — un "arreglo de
objetos", totalmente soportado desde la Etapa 3 — y procedimientos/
funciones libres (no métodos de una clase contenedora) operan sobre él
como parámetro. Es el mismo patrón que ya usaba `arreglo_objetos.inv`
(Etapa 3) para un arreglo de `Persona` sin una clase envolvente.

## 2. Programas de referencia

### 2.1 Sin objetos (arreglos primitivos)

| Archivo | Estructura / algoritmo | Notas de diseño |
|---|---|---|
| [`tabla_hash_arreglo.inv`](../pruebas/tabla_hash_arreglo.inv) | Tabla hash con sondeo lineal | Arreglos paralelos `claves`/`valores`/`ocupado` |
| [`grafo_matriz.inv`](../pruebas/grafo_matriz.inv) | Grafo con matriz de adyacencia | `int[N][N] adj` local en `main`, BFS/DFS con cola/pila de arreglo |
| [`ordenamiento_insercion.inv`](../pruebas/ordenamiento_insercion.inv) | Ordenamiento por inserción | |
| [`ordenamiento_seleccion.inv`](../pruebas/ordenamiento_seleccion.inv) | Ordenamiento por selección | |
| [`busqueda_binaria.inv`](../pruebas/busqueda_binaria.inv) | Búsqueda binaria | Requiere el arreglo ya ordenado |
| [`quicksort.inv`](../pruebas/quicksort.inv) | Quicksort (partición de Lomuto) | Recursivo |
| [`mergesort.inv`](../pruebas/mergesort.inv) | Mergesort | Recursivo, arreglo temporal de tamaño fijo (`const int MAXN`) |

### 2.2 Con objetos (clases, Etapa 2)

| Archivo | Estructura | Notas de diseño |
|---|---|---|
| [`grafo_lista_adyacencia.inv`](../pruebas/grafo_lista_adyacencia.inv) | Grafo con lista de adyacencia | `NodoAdj` enlazado por vértice; BFS con una `Cola` enlazada (mismo patrón que `cola_enlazada.inv`); DFS recursivo. `cabezas[N]` es variable local en `main` (ver §1) |
| [`tabla_hash_encadenada.inv`](../pruebas/tabla_hash_encadenada.inv) | Tabla hash con encadenamiento | `NodoHash` enlazado por cubeta; `cubetas[CAP]` es variable local en `main` (ver §1) |

Ambos grupos comparten los mismos algoritmos base (BFS/DFS,
ordenamiento/búsqueda) para que el estudiante compare directamente la
versión "con arreglos" contra la versión "con objetos" del mismo problema
— mismo criterio pedagógico que ya separa `pila_arreglo.inv`/
`pila_enlazada.inv` desde la Etapa 3.

## 3. Salidas de referencia

```
$ python main.py pruebas/tabla_hash_arreglo.inv
insertar 5 -> indice 5
insertar 15 -> indice 6
insertar 25 -> indice 7
insertar 3 -> indice 3
buscar 5 = 100
buscar 15 = 200
buscar 25 = 300
buscar 3 = 400
buscar 99: no encontrado

$ python main.py pruebas/grafo_matriz.inv
BFS desde 0: 0 1 2 3 4 5
DFS desde 0: 0 1 3 2 4 5

$ python main.py pruebas/grafo_lista_adyacencia.inv
BFS desde 0: 0 2 1 3 4 5
DFS desde 0: 0 2 3 4 5 1
```

El orden de recorrido de `grafo_lista_adyacencia.inv` difiere del de
`grafo_matriz.inv` porque cada `agregarArista` **antepone** el nuevo nodo a
la cabeza de la lista de adyacencia (inserción O(1) en la cabeza, patrón
estándar de lista enlazada) — el grafo es el mismo, el orden en que BFS/DFS
visitan los vecinos de cada vértice no. Es una diferencia esperada, no un
error: ambas exploraciones son BFS/DFS válidos del mismo grafo no dirigido
de 6 vértices.

```
$ python main.py pruebas/ordenamiento_insercion.inv
Original:  [ 64, 25, 12, 22, 11, 90, 38 ]
Ordenado:  [ 11, 12, 22, 25, 38, 64, 90 ]
```
(La misma entrada/salida se usa en `ordenamiento_seleccion.inv`,
`quicksort.inv` y `mergesort.inv`, para comparar los cuatro algoritmos
sobre el mismo caso de prueba.)

```
$ python main.py pruebas/busqueda_binaria.inv
25 en posicion: 3
11 en posicion: 0
90 en posicion: 6
99 en posicion: -1

$ python main.py pruebas/tabla_hash_encadenada.inv
insertar 5 -> cubeta 5
insertar 12 -> cubeta 5
insertar 19 -> cubeta 5
insertar 26 -> cubeta 5
buscar 5 = 100
buscar 12 = 200
buscar 19 = 300
buscar 26 = 400
buscar 99: no encontrado
```
(Las claves 5, 12, 19 y 26 caen deliberadamente todas en la cubeta 5 —
`clave % 7` — para demostrar la resolución de colisiones por
encadenamiento, a diferencia del sondeo lineal de `tabla_hash_arreglo.inv`.)

## 4. Verificación

- `pruebas/conformidad.py`, grupo `estructuras`: cada uno de los 9 archivos
  tiene un caso que ejecuta el programa completo y confirma, por
  subcadena, los fragmentos clave de la salida de arriba. Suite completa en
  258/258 (`python pruebas/conformidad.py`).
- Cada archivo fue ejecutado individualmente
  (`python main.py pruebas/<archivo>.inv`) y su salida verificada a mano
  contra el resultado esperado antes de incorporarse a la suite.
- Ningún archivo de esta etapa toca `lexer.py`, `parser.py`, `semantic.py`,
  `type_checker.py`, `interpreter.py` ni `ir.py` — el backend de código
  intermedio (`--run-ir`, Etapa 5) ya los soporta sin cambios, al ser
  programas puramente del subconjunto estructurado (o, para los dos "con
  objetos", del subconjunto POO ya soportado por el intérprete de árbol;
  `ir.py` sigue sin cubrir POO, ver `docs/InvenioLang_Etapa6_Estructurado.md`
  §8).
- Cargables desde el menú **Ayuda → Ejemplos** de la GUI
  (`inveniolang/docstrings.py::EJEMPLOS`).
