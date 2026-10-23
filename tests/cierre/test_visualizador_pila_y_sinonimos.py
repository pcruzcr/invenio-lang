"""INV-4400 / INV-4401: pila sobre arreglo con índice de tope y sinónimos de "fin".

Antes la cima de una pila sobre arreglo se dibujaba SIEMPRE en la última
celda del arreglo: con ``entero [4] pila`` y ``tope = 1`` el estudiante veía
como cima un 0 (celda sin usar) y como elementos celdas que la pila no
contiene. Y en la lista doble del currículo en inglés (campo ``queue``, la
traducción de ``cola``) faltaba la flecha contenedor → último nodo, que en
español sí aparecía.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang.visualizacion import describir  # noqa: E402
from inveniolang.visualizacion.modelo import Estructura, a_json, desde_json  # noqa: E402
from inveniolang.visualizacion.render_texto import normalizar_paso, secuencia  # noqa: E402
from inveniolang.visualizacion.traza import trazar  # noqa: E402

CURRICULO = RAIZ / "curriculum"


def _pilas(traza):
    paso = traza.pasos[-1]
    return paso, [e for e in paso.estructuras if e.forma == "pila"]


def _valores(est: Estructura, paso) -> list:
    p = normalizar_paso(paso.a_dict())
    e = next(x for x in p["estructuras"] if x["raiz"] == est.raiz and x["forma"] == "pila")
    return [v["v"] for _, v in secuencia(e, p)]


GLOBAL_ES = """
constante entero CAP = 5;
entero [CAP] pila;
entero tope = -1;
vacio apilar(entero v) { tope++; pila[tope] = v; }
vacio main() {
    apilar(10); apilar(20); apilar(30);
    tope--;
    imprimir(tope);
}
"""


def test_pila_global_usa_la_variable_tope():
    paso, (pila,) = _pilas(trazar(GLOBAL_ES))
    assert pila.cima == 1
    assert _valores(pila, paso) == [20, 10]  # la cima es pila[tope], no pila[4]
    texto = describir(paso.a_dict(), "es")
    assert "20" in texto and "30" not in texto.split("pila")[1].split(".")[0]


GLOBAL_EN = """
const int CAP = 4;
int [CAP] stack;
int top = -1;
void main() {
    top++; stack[top] = 7;
    print(top);
}
"""


def test_pila_global_en_ingles_usa_top():
    paso, (pila,) = _pilas(trazar(GLOBAL_EN))
    assert pila.cima == 0
    assert _valores(pila, paso) == [7]


OBJETO_TAMANO = """
clase Pila {
    publico entero[] datos;
    publico entero tamano;
    Pila() { este.datos = nuevo entero[4]; este.tamano = 0; }
    publico vacio apilar(entero v) {
        este.datos[este.tamano] = v;
        este.tamano = este.tamano + 1;
    }
}
vacio main() {
    Pila p = nuevo Pila();
    p.apilar(4); p.apilar(5);
    imprimir(p.tamano);
}
"""


def test_objeto_pila_con_arreglo_y_tamano():
    paso, (pila,) = _pilas(trazar(OBJETO_TAMANO))
    assert pila.cima == 1
    assert _valores(pila, paso) == [5, 4]


OBJETO_TOP_EN = """
class Stack {
    public int[] data;
    public int top;
    Stack() { this.data = new int[3]; this.top = -1; }
}
void main() {
    Stack s = new Stack();
    print(s.top);
}
"""


def test_objeto_pila_vacia_no_muestra_celdas():
    paso, (pila,) = _pilas(trazar(OBJETO_TOP_EN))
    assert pila.cima == -1
    assert _valores(pila, paso) == []


def test_sin_tope_conocido_se_conserva_la_regla_anterior():
    codigo = "vacio main() { entero [3] pila = {1, 2, 3}; imprimir(pila[0]); }"
    paso, (pila,) = _pilas(trazar(codigo))
    assert pila.cima is None
    assert _valores(pila, paso) == [3, 2, 1]
    assert "cima" not in pila.a_dict()  # clave opcional: trazas antiguas siguen valiendo


def test_cima_viaja_en_el_json_ida_y_vuelta():
    traza = trazar(GLOBAL_ES)
    assert desde_json(a_json(traza)) == traza


@pytest.mark.parametrize(
    "relativa", ["es/nivel10/01_pila_con_arreglo.inv", "en/level10/01_array_stack.inv"]
)
def test_curriculo_pila_con_arreglo_marca_la_cima(relativa):
    traza = trazar((CURRICULO / relativa).read_text(encoding="utf-8"))
    cimas = {e.cima for p in traza.pasos for e in p.estructuras if e.forma == "pila"}
    assert {-1, 0, 3} <= cimas


@pytest.mark.parametrize(
    "relativa, campo",
    [("es/nivel10/08_lista_doble.inv", "cola"), ("en/level10/08_doubly_linked_list.inv", "queue")],
)
def test_lista_doble_marca_el_ultimo_nodo_en_ambos_idiomas(relativa, campo):
    traza = trazar((CURRICULO / relativa).read_text(encoding="utf-8"))
    etiquetas = {
        a[2]
        for p in traza.pasos
        for e in p.estructuras
        if e.forma == "lista_doble"
        for a in e.aristas
    }
    assert campo in etiquetas
