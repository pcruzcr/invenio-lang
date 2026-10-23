"""Integración TRAZA + VISTA sobre todo el currículo (INV-2010).

Cada ejercicio de ``curriculum/es`` y ``curriculum/en`` se traza (con su
``.entrada``) y se renderiza con lo que ve el estudiante: ``svg_paso`` y
``describir`` en el idioma del programa sobre una muestra amplia de pasos
(primero, último y uno de cada diez) y ``html_traza`` de la traza completa.
En los casos clave (burbuja, pila, cola, lista, ABB, BFS) se comprueba además
que cada estructura se DIBUJA con el número de elementos que dice el contrato.
Antes de la integración estas pruebas no podían existir; con el contrato sin
unificar fallaban (una lista sin contenedor perdía su cabeza en el dibujo y un
grafo de matriz de adyacencia rotulaba sus vértices con nodos ajenos).
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang.visualizacion import describir, html_traza, svg_paso  # noqa: E402
from inveniolang.visualizacion.modelo import Estructura, Paso  # noqa: E402
from inveniolang.visualizacion.traza import trazar  # noqa: E402

CURRICULO = RAIZ / "curriculum"
NS = "{http://www.w3.org/2000/svg}"
PROGRAMAS = sorted(CURRICULO.glob("*/*/*.inv"))
PASOS_MUESTRA = 120


def _trazar(ruta: Path, max_pasos: int):
    entrada = ruta.with_suffix(".entrada")
    lineas = tuple(entrada.read_text(encoding="utf-8").splitlines()) if entrada.exists() else ()
    codigo = ruta.read_text(encoding="utf-8")
    return trazar(
        codigo, ruta=ruta.name, entrada=lineas, max_pasos=max_pasos, ruta_fuente=str(ruta)
    )


def _muestra(n: int) -> list[int]:
    return sorted({0, n - 1, *range(0, n, 10)}) if n else []


def test_el_curriculo_completo_esta_cubierto():
    assert len(PROGRAMAS) == 266
    assert {p.parts[-3] for p in PROGRAMAS} == {"es", "en"}


@pytest.mark.parametrize("ruta", PROGRAMAS, ids=lambda r: f"{r.parts[-3]}/{r.parent.name}/{r.stem}")
def test_trazar_y_renderizar(ruta):
    traza = _trazar(ruta, PASOS_MUESTRA)
    idioma = ruta.parts[-3]
    assert traza.error is None and traza.pasos
    assert traza.idioma == idioma  # deducido de las palabras clave del programa
    prefijo = "Paso" if idioma == "es" else "Step"
    for i in _muestra(len(traza.pasos)):
        paso = traza.pasos[i].a_dict()
        svg = ET.fromstring(svg_paso(paso, idioma))
        assert svg.tag == NS + "svg"
        assert svg.find(NS + "title") is not None and svg.find(NS + "desc") is not None
        texto = describir(paso, idioma)
        assert texto.startswith(f"{prefijo} {paso['n']},")
    html = html_traza(traza, idioma)
    assert html.lower().startswith("<!doctype html>")
    assert not re.search(r"""(src|href)=["']https?://""", html)


# ----------------------------------------------------------------- casos clave


def _paneles(svg: str) -> dict[str, list[str]]:
    """``etiqueta · Forma`` -> rótulos de los grupos de elementos del panel."""
    paneles: dict[str, list[str]] = {}
    for g in ET.fromstring(svg).iter(NS + "g"):
        rotulo = g.get("aria-label") or ""
        if g.get("role") == "group" and " · " in rotulo:
            paneles[rotulo] = [
                h.get("aria-label") or ""
                for h in g.iter(NS + "g")
                if h is not g and h.get("role") == "group"
            ]
    return paneles


def _dibujados(forma: str, rotulos: list[str]) -> int:
    if forma in ("pila", "cola", "lista_enlazada", "lista_doble"):
        # Cada elemento se rotula "k: valor" (a veces en dos grupos anidados).
        return len({r.split(":", 1)[0] for r in rotulos if re.match(r"\d+:", r)})
    return len(rotulos)


def _esperados(est: Estructura, paso: Paso) -> int:
    nodo = paso.monticulo.get(est.raiz)
    if est.forma == "grafo":
        # Matriz/arreglo de adyacencia: vértices = índices 0..n-1 (INV-2007).
        por_indices = nodo is not None and nodo.tipo in ("matriz", "arreglo")
        return len(nodo.elementos) if por_indices and nodo else len(est.nodos)
    if est.forma == "matriz":
        return sum(len(f) for f in nodo.elementos) if nodo else 0
    if est.forma == "pila" and est.cima is not None:
        return est.cima + 1  # INV-4400: solo las celdas hasta la cima
    if est.forma == "arreglo" or (not est.nodos and nodo is not None and nodo.tipo == "arreglo"):
        return len(nodo.elementos) if nodo else 0
    return len(est.nodos)


CLAVE = {
    "burbuja": ("es/nivel05/01_burbuja.inv", "en/level05/01_bubble_sort.inv", {"arreglo"}),
    "pila": ("es/nivel10/02_pila_enlazada.inv", "en/level10/02_linked_stack.inv", {"pila"}),
    "pila_arreglo": (
        "es/nivel10/01_pila_con_arreglo.inv",
        "en/level10/01_array_stack.inv",
        {"pila"},
    ),
    "cola": ("es/nivel10/06_cola_enlazada.inv", "en/level10/06_linked_queue.inv", {"cola"}),
    "lista": (
        "es/nivel10/07_lista_simple.inv",
        "en/level10/07_singly_linked_list.inv",
        {"lista_enlazada"},
    ),
    "lista_doble": (
        "es/nivel10/08_lista_doble.inv",
        "en/level10/08_doubly_linked_list.inv",
        {"lista_doble"},
    ),
    "abb": (
        "es/nivel11/01_abb_insercion.inv",
        "en/level11/01_bst_insertion.inv",
        {"arbol_binario"},
    ),
    "bfs": ("es/nivel12/03_bfs.inv", "en/level12/03_bfs.inv", {"grafo", "matriz", "cola"}),
}


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("caso", sorted(CLAVE))
def test_cada_forma_se_dibuja_con_sus_elementos(caso, idioma):
    es, en, formas = CLAVE[caso]
    ruta = CURRICULO / (es if idioma == "es" else en)
    traza = _trazar(ruta, 5000)
    assert traza.error is None and not traza.truncada
    vistas: set[str] = set()
    maximo = 0
    for i in _muestra(len(traza.pasos)):
        paso = traza.pasos[i]
        paneles = _paneles(svg_paso(paso.a_dict(), idioma))
        for est in paso.estructuras:
            if est.forma not in formas:
                continue
            rotulo = next(r for r in paneles if r.startswith(f"{est.etiqueta} · "))
            if est.forma == "grafo":
                rotulo = next(
                    r
                    for r in paneles
                    if r.startswith(est.etiqueta) and r.endswith(("Grafo", "Graph"))
                )
            elif est.forma == "matriz":
                rotulo = next(
                    r
                    for r in paneles
                    if r.startswith(est.etiqueta) and r.endswith(("Matriz", "Matrix"))
                )
            esperado = _esperados(est, paso)
            assert _dibujados(est.forma, paneles[rotulo]) == esperado, (i, est)
            vistas.add(est.forma)
            maximo = max(maximo, esperado)
    assert vistas == formas and maximo >= 3


def test_lista_sin_contenedor_conserva_la_cabeza():
    """INV-2007: si la variable apunta al primer nodo, la raíz ES un elemento."""
    codigo = (
        "clase Nodo {\n    publico entero valor;\n    publico Nodo siguiente;\n"
        "    Nodo(entero v) { este.valor = v; }\n}\n"
        "vacio main() {\n    Nodo cabeza = nuevo Nodo(1);\n"
        "    cabeza.siguiente = nuevo Nodo(2);\n    imprimir(cabeza.valor);\n}\n"
    )
    traza = trazar(codigo)
    paso = traza.pasos[-1]
    (lista,) = [e for e in paso.estructuras if e.forma == "lista_enlazada"]
    assert lista.raiz == lista.nodos[0] and len(lista.nodos) == 2
    rotulos = _paneles(svg_paso(paso.a_dict(), "es"))["cabeza · Lista enlazada"]
    assert _dibujados("lista_enlazada", rotulos) == 2
    assert "con 2 nodos: 1 → 2 → nulo" in describir(paso.a_dict(), "es")
