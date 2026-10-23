"""Descripción accesible y lectura del contrato (INV-2200..INV-2204)."""

from __future__ import annotations

import copy
import dataclasses
import json

import pytest
from vis_comun import NOMBRES, cargar

from inveniolang.visualizacion import TrazaInvalida, describir, normalizar_traza
from inveniolang.visualizacion import render_texto as rt


@pytest.mark.parametrize("nombre", NOMBRES)
def test_cada_fixture_cumple_el_contrato(nombre):
    t = normalizar_traza(cargar(nombre))
    assert t["version"] == 1 and t["idioma"] == nombre.rsplit("_", 1)[1]
    assert t["pasos"], nombre
    for paso in t["pasos"]:
        assert all(isinstance(k, int) for k in paso["monticulo"])
        # idempotente: normalizar lo ya normalizado no cambia nada
        assert rt.normalizar_paso(paso) == paso


def test_json_dict_y_bytes_dan_lo_mismo():
    d = cargar("pila_es")
    texto = json.dumps(d)
    assert normalizar_traza(d) == normalizar_traza(texto) == normalizar_traza(texto.encode())


@pytest.mark.parametrize("nombre", NOMBRES)
def test_describir_cada_paso_en_su_idioma(nombre):
    t = normalizar_traza(cargar(nombre))
    for paso in t["pasos"]:
        texto = describir(paso, t["idioma"])
        inicio = "Paso " if t["idioma"] == "es" else "Step "
        assert texto.startswith(f"{inicio}{paso['n']}, ")
        assert str(paso["linea"]) in texto


ESPERADO = {
    "arreglo": ("Arreglo a con 4 elementos: 1, 2, 4, 5.", "Array a with 4 elements: 1, 2, 4, 5."),
    "matriz": ("fila 1: 3, 4, 5", "row 1: 3, 4, 5"),
    "pila": (
        "Pila p con 2 elementos; tope: 20. Del tope a la base: 20, 10.",
        "Stack s with 2 elements; top: 20.",
    ),
    "cola": (
        "Cola c con 2 elementos; frente: 8, final: 9.",
        "Queue q with 2 elements; front: 8, rear: 9.",
    ),
    "lista_enlazada": (
        "Lista enlazada l con 3 nodos: 3 → 6 → 9 → nulo.",
        "Linked list l with 3 nodes: 3 → 6 → 9 → null.",
    ),
    "lista_doble": (
        'nulo ⇄ "cora" ⇄ "ana" ⇄ "beto" ⇄ nulo',
        'null ⇄ "cora" ⇄ "ana" ⇄ "ben" ⇄ null',
    ),
    "arbol": ("Por niveles: nivel 0: 50; nivel 1: 30, 70; nivel 2: 20, 40, 60, 80.", "level 3: 35"),
    "grafo": ("0 → 2 (peso 1)", "0 — 1 (weight 7)"),
    "recursion": ('Se imprime: "6".', 'Prints: "6".'),
    "escalares": ("mayor = falso, inicial = 'A'", "adult = false, initial = 'A'"),
}


@pytest.mark.parametrize("forma", sorted(ESPERADO))
def test_frases_de_cada_forma_en_es_y_en(forma):
    for idioma, esperado in zip(("es", "en"), ESPERADO[forma], strict=True):
        t = normalizar_traza(cargar(f"{forma}_{idioma}"))
        assert esperado in describir(t["pasos"][-1], idioma)


def test_accesos_lectura_y_escritura_con_nombres_legibles():
    t = normalizar_traza(cargar("arreglo_es"))
    assert "Se lee a[0], que vale 5. Se lee a[1], que vale 1." in describir(t["pasos"][1], "es")
    assert "Se escribe a[0], que ahora vale 1." in describir(t["pasos"][3], "es")
    arbol = normalizar_traza(cargar("arbol_es"))["pasos"][1]
    texto = describir(arbol, "es")
    # INV-2204: nada de "#102.derecho"
    assert "Se escribe el campo derecho del nodo 70 de t, que ahora vale → nodo 80 de t." in texto
    assert "#" not in texto
    en = describir(normalizar_traza(cargar("arbol_en"))["pasos"][1], "en")
    assert "Writes field left of node 40 in t, which now holds → node 35 in t." in en


def test_fila_de_matriz_como_nodo_propio_se_nombra_con_dos_indices():
    t = normalizar_traza(cargar("matriz_en"))
    assert "Writes m[1][1], which now holds 4." in describir(t["pasos"][0], "en")


def test_la_pila_de_llamadas_recursiva_se_describe_completa():
    t = normalizar_traza(cargar("recursion_es"))
    texto = describir(t["pasos"][3], "es")
    assert "profundidad de la pila de llamadas: 4" in texto
    assert (
        "main (línea 9) → factorial (línea 5) → factorial (línea 5) → factorial (línea 3)" in texto
    )
    assert "Variables de factorial: n = 1." in texto


def test_el_mismo_paso_cambia_de_idioma():
    paso = normalizar_traza(cargar("pila_es"))["pasos"][-1]
    es, en = describir(paso, "es"), describir(paso, "en")
    assert es != en and "Se imprime" in es and "Prints" in en and "Se " not in en


def test_listas_largas_se_resumen():
    assert rt.unir([str(i) for i in range(20)], "es", 3) == "0, 1, 2, y 17 más"
    assert rt.unir([str(i) for i in range(20)], "en", 3) == "0, 1, 2, and 17 more"


def test_valores_escalares_por_tipo():
    def e(v, tipo):
        return {"t": "escalar", "tipo": tipo, "v": v}

    assert rt.valor_texto(e(None, "nulo"), "es") == "nulo"
    assert rt.valor_texto(e(True, "logico"), "en") == "true"
    assert rt.valor_texto(e(2.0, "real"), "es") == "2.0"
    assert rt.valor_texto(e('di "hola"', "texto"), "es") == '"di \\"hola\\""'
    assert rt.valor_texto(e("x", "char"), "en") == "'x'"
    assert rt.valor_texto({"t": "ref", "id": 3}, "es", {3: "lista"}) == "→ lista"


@pytest.mark.parametrize(
    "romper, ruta",
    [
        (lambda t: t.update(version=2), "version"),
        (lambda t: t["pasos"][0]["accesos"].append({"op": "borra"}), "accesos"),
        (lambda t: t["pasos"][0]["estructuras"][0].update(forma="hexagono"), "forma"),
        (lambda t: t["pasos"][0].update(monticulo=[]), "monticulo"),
        (lambda t: t["pasos"][0]["estructuras"][0].update(aristas=[[1]]), "aristas"),
    ],
)
def test_traza_invalida_dice_donde(romper, ruta):
    t = copy.deepcopy(cargar("arreglo_es"))
    romper(t)
    with pytest.raises(TrazaInvalida, match=ruta):
        normalizar_traza(t)


def test_json_roto_es_traza_invalida():
    with pytest.raises(TrazaInvalida):
        normalizar_traza("{no es json")


def test_objeto_traza_sin_modelo_lo_explica(monkeypatch):
    """Sin modelo.py (lo entrega TRAZA) un dataclass no se adivina: se explica."""
    import sys

    monkeypatch.setitem(sys.modules, "inveniolang.visualizacion.modelo", None)

    @dataclasses.dataclass(frozen=True)
    class Traza:
        version: int = 1

    with pytest.raises(TrazaInvalida, match="modelo"):
        normalizar_traza(Traza())


def test_objeto_traza_usa_a_json_del_modelo(monkeypatch):
    import sys
    import types

    modelo = types.ModuleType("inveniolang.visualizacion.modelo")
    modelo.a_json = lambda traza: json.dumps(cargar("cola_en"))
    monkeypatch.setitem(sys.modules, "inveniolang.visualizacion.modelo", modelo)

    @dataclasses.dataclass(frozen=True)
    class Traza:
        version: int = 1

    assert normalizar_traza(Traza()) == normalizar_traza(cargar("cola_en"))


def test_arbol_con_ciclo_no_cuelga():
    paso = rt.normalizar_paso(
        {
            "monticulo": {
                "1": {
                    "tipo": "objeto",
                    "campos": {"valor": {"t": "escalar", "tipo": "entero", "v": 1}},
                },
                "2": {
                    "tipo": "objeto",
                    "campos": {"valor": {"t": "escalar", "tipo": "entero", "v": 2}},
                },
            },
            "estructuras": [
                {
                    "forma": "arbol_binario",
                    "raiz": 1,
                    "etiqueta": "t",
                    "nodos": [1, 2],
                    "aristas": [[1, 2, "izq"], [2, 1, "der"]],
                }
            ],
        }
    )
    raiz, hijos = rt.arbol(paso["estructuras"][0], paso)
    assert raiz == 1 and rt.niveles_arbol(raiz, hijos) == [[1], [2]]
