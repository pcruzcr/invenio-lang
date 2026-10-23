"""Clasificador de estructuras (INV-2002) sobre montículos construidos a mano.

Casos que los programas del currículo no cubren: ciclos, nombres engañosos,
listas vistas desde la mitad, árboles vistos desde un subárbol, determinismo.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang.visualizacion.clasificador import clasificar, palabras  # noqa: E402
from inveniolang.visualizacion.modelo import (  # noqa: E402
    Marco,
    NodoMonticulo,
    Valor,
    VariableMarco,
)

NULO = Valor.escalar("null", None)


def _ent(v: int) -> Valor:
    return Valor.escalar("int", v)


def _obj(nid: int, clase: str, **campos: Valor) -> NodoMonticulo:
    return NodoMonticulo(nid, "objeto", clase, (), dict(campos))


def _marco(**refs: int) -> tuple[Marco, ...]:
    variables = {k: VariableMarco("?", Valor.ref(v)) for k, v in refs.items()}
    return (Marco("<global>", 0), Marco("main", 1, variables))


def test_palabras_de_identificadores():
    assert palabras("PilaEnlazada") == {"pila", "enlazada"}
    assert palabras("adjacency_list") == {"adjacency", "list"}
    assert palabras("NodoCola") == {"nodo", "cola"}


def test_lista_ciclica_no_cuelga_y_se_ve_desde_la_mitad():
    m = {
        1: _obj(1, "Nodo", valor=_ent(1), siguiente=Valor.ref(2)),
        2: _obj(2, "Nodo", valor=_ent(2), siguiente=Valor.ref(3)),
        3: _obj(3, "Nodo", valor=_ent(3), siguiente=Valor.ref(1)),
    }
    (e,) = clasificar(_marco(actual=2), m)
    assert e.forma == "lista_enlazada" and sorted(e.nodos) == [1, 2, 3]


def test_lista_vista_desde_la_mitad_empieza_en_la_cabeza():
    m = {
        1: _obj(1, "ListNode", value=_ent(1), next=Valor.ref(2)),
        2: _obj(2, "ListNode", value=_ent(2), next=Valor.ref(3)),
        3: _obj(3, "ListNode", value=_ent(3), next=NULO),
    }
    estructuras = clasificar(_marco(current=3, head=1), m)
    assert len(estructuras) == 1
    (e,) = estructuras
    assert e.raiz == 1 and e.nodos == (1, 2, 3) and e.etiqueta == "head"
    assert e.aristas == ((1, 2, "next"), (2, 3, "next"))


def test_arbol_desde_subarbol_y_nombres_en_ingles():
    m = {
        1: _obj(1, "TreeNode", value=_ent(5), left=Valor.ref(2), right=Valor.ref(3)),
        2: _obj(2, "TreeNode", value=_ent(2), left=NULO, right=NULO),
        3: _obj(3, "TreeNode", value=_ent(9), left=NULO, right=NULO),
    }
    (e,) = clasificar(_marco(node=3), m)
    assert e.forma == "arbol_binario" and e.raiz == 1 and e.nodos == (1, 2, 3)
    assert e.aristas == ((1, 2, "left"), (1, 3, "right"))


def test_nombres_enganosos_no_son_colas_ni_pilas():
    m = {
        1: _obj(1, "Escolar", nota=_ent(9)),
        2: _obj(2, "NodoCola", valor=_ent(1), siguiente=NULO),
    }
    formas = [e.forma for e in clasificar(_marco(alumno=1, n=2), m)]
    assert formas == ["objeto", "lista_enlazada"]


def test_pila_vacia_y_cola_con_frente_y_final():
    m = {
        1: _obj(1, "Pila", cima=NULO, cantidad=_ent(0)),
        2: _obj(2, "Queue", front=Valor.ref(3), rear=Valor.ref(4), count=_ent(2)),
        3: _obj(3, "QueueNode", value=_ent(7), next=Valor.ref(4)),
        4: _obj(4, "QueueNode", value=_ent(8), next=NULO),
    }
    pila, cola = clasificar(_marco(p=1, q=2), m)
    # INV-2007: la raíz es el contenedor y no está en `nodos` (solo elementos).
    assert pila.forma == "pila" and pila.raiz == 1 and pila.nodos == () and pila.aristas == ()
    assert cola.forma == "cola" and cola.raiz == 2 and cola.nodos == (3, 4)
    assert set(cola.aristas) == {(2, 3, "front"), (3, 4, "next"), (2, 4, "rear")}


def test_grafo_con_campo_adjacency_matriz():
    fila = lambda *xs: tuple(_ent(x) for x in xs)  # noqa: E731
    m = {
        1: _obj(1, "Red", adjacency=Valor.ref(2)),
        2: NodoMonticulo(2, "matriz", None, (fila(0, 3), fila(0, 0))),
    }
    estructuras = clasificar(_marco(red=1), m)
    assert [(e.forma, e.raiz, e.nodos, e.aristas) for e in estructuras] == [
        ("grafo", 2, (), ((0, 1, "3"),))
    ]


def test_contenedor_con_arreglo_y_objeto_simple():
    m = {
        1: _obj(1, "Vector", datos=Valor.ref(2), cantidad=_ent(2)),
        2: NodoMonticulo(2, "arreglo", None, (_ent(4), _ent(5), _ent(0))),
        3: _obj(3, "Punto", x=_ent(1), y=_ent(2)),
    }
    estructuras = clasificar(_marco(v=1, p=3), m)
    assert [(e.forma, e.etiqueta) for e in estructuras] == [("arreglo", "v.datos"), ("objeto", "p")]


def test_determinista():
    m = {
        1: _obj(1, "Nodo", valor=_ent(1), izq=NULO, der=Valor.ref(2)),
        2: _obj(2, "Nodo", valor=_ent(2), izq=NULO, der=NULO),
        3: NodoMonticulo(3, "arreglo", None, (Valor.ref(1),)),
    }
    marcos = _marco(arboles=3, r=1)
    assert clasificar(marcos, m) == clasificar(marcos, m)
    formas = [e.forma for e in clasificar(marcos, m)]
    assert formas == ["arreglo", "arbol_binario"]


def test_lista_dentro_de_un_contenedor_tiene_al_contenedor_como_raiz():
    m = {
        1: _obj(1, "ListaDoble", cabeza=Valor.ref(2), cola=Valor.ref(3)),
        2: _obj(2, "NodoDoble", valor=_ent(1), anterior=NULO, siguiente=Valor.ref(3)),
        3: _obj(3, "NodoDoble", valor=_ent(2), anterior=Valor.ref(2), siguiente=NULO),
    }
    (e,) = clasificar(_marco(lista=1, actual=3), m)
    assert (e.forma, e.raiz, e.etiqueta, e.nodos) == ("lista_doble", 1, "lista", (2, 3))
    assert set(e.aristas) == {
        (1, 2, "cabeza"),
        (1, 3, "cola"),
        (2, 3, "siguiente"),
        (3, 2, "anterior"),
    }
