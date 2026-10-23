# Biblioteca estándar educativa (INV-1430)

Escrita en InvenioLang (`inveniolang/stdlib/`), comentada para estudiarla y
disponible en español e inglés. Se importa por nombre desde cualquier carpeta.
Los contenedores guardan enteros (los genéricos del lenguaje no admiten
nodos enlazados genéricos, ver `InvenioLang_2.0_POO.md` §9.5). Las operaciones
inválidas (desapilar una pila vacía, posición fuera de rango) lanzan
`IL-EJE-060` con `lanzar_error`, capturable con `intentar`/`capturar`.

| Español | Inglés | Contenido |
|---|---|---|
| `importar "estructuras/pila";` | `import "structures/stack";` | `Pila`: `apilar`, `desapilar`, `cima_valor`, `esta_vacia`, `tamano`, `a_texto` |
| `importar "estructuras/cola";` | `import "structures/queue";` | `Cola`: `encolar`, `desencolar`, `frente_valor`, `esta_vacia`, `tamano`, `a_texto` |
| `importar "estructuras/lista_enlazada";` | `import "structures/linked_list";` | `ListaEnlazada`: `agregar_al_inicio/final`, `insertar`, `eliminar_en`, `obtener`, `asignar`, `buscar`, `contiene`, `invertir`, ... |
| `importar "estructuras/lista_doble";` | `import "structures/doubly_linked_list";` | `ListaDoble`: `agregar_al_inicio/final`, `quitar_primero/ultimo`, `obtener`, `a_texto`, `a_texto_inverso` |
| `importar "estructuras/arbol_binario_busqueda";` | `import "structures/binary_search_tree";` | `ArbolBinarioBusqueda`: `insertar`, `contiene`, `eliminar`, `minimo`, `maximo`, `altura`, `inorden`, `preorden`, `postorden` |
| `importar "estructuras/grafo";` | `import "structures/graph";` | `Grafo` (lista de adyacencia, dirigido o no): `agregar_vertice`, `agregar_arista`, `bfs`, `dfs`, `distancia_minima` y `camino_minimo` (Dijkstra) |
| `importar "estructuras/vector";` | `import "structures/vector";` | `Vector` dinámico (capacidad que se duplica): `agregar`, `insertar`, `eliminar_en`, `obtener`, `asignar`, `capacidad` |
| `importar "algoritmos/ordenamiento";` | `import "algorithms/sorting";` | burbuja, selección, inserción, mezcla, rápido, montículo, `esta_ordenado` |
| `importar "algoritmos/busqueda";` | `import "algorithms/searching";` | lineal, binaria (iterativa y recursiva), posición del máximo/mínimo, `contar_apariciones` |
| `importar "algoritmos/matriz";` | `import "algorithms/matrix";` | llenar, identidad, suma, producto, transpuesta, traza, simetría, `matriz_a_texto` |

Cada módulo se ejercita desde un programa en `tests/stdlib/programas/` con su
salida esperada; `tests/test_stdlib.py` además traduce esos programas al
inglés y los corre contra la versión inglesa, y verifica token a token que
las dos versiones de cada módulo sean el mismo programa (glosario en
`tests/stdlib/glosario.py`).
