"""Trazador paso a paso (INV-2000, INV-2003, INV-2004, INV-2005).

Programas del currículo en español y en inglés: burbuja, búsqueda binaria,
pila, cola, lista enlazada, ABB, BFS, factorial y Hanói; más la biblioteca
estándar, errores, truncado, límites y el coste cero con la traza apagada.
Fallan contra el árbol anterior: no existían ni el trazador ni el registro de
accesos, y las asignaciones no tenían línea (INV-2004).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import api  # noqa: E402
from inveniolang.core import analizar_fuente  # noqa: E402
from inveniolang.interpreter import Interpreter  # noqa: E402
from inveniolang.visualizacion import traza as modulo_traza  # noqa: E402
from inveniolang.visualizacion.modelo import Paso, Traza  # noqa: E402
from inveniolang.visualizacion.traza import (  # noqa: E402
    MAX_PASOS_TRAZA,
    detectar_idioma,
    trazar,
)

CURRICULO = RAIZ / "curriculum"


def _programa(relativa: str) -> tuple[str, tuple[str, ...]]:
    ruta = CURRICULO / relativa
    entrada = ruta.with_suffix(".entrada")
    lineas = tuple(entrada.read_text(encoding="utf-8").splitlines()) if entrada.exists() else ()
    return ruta.read_text(encoding="utf-8"), lineas


def _trazar(relativa: str, **kw) -> Traza:
    codigo, entrada = _programa(relativa)
    return trazar(codigo, ruta=os.path.basename(relativa), entrada=entrada, **kw)


def _escrituras(paso: Paso) -> list[tuple]:
    return [(a.var, a.indices, a.campo) for a in paso.accesos if a.op == "escribe"]


def _lecturas(paso: Paso) -> list[tuple]:
    return [(a.var, a.indices, a.campo) for a in paso.accesos if a.op == "lee"]


def _estructuras(traza: Traza, forma: str):
    return [(p, e) for p in traza.pasos for e in p.estructuras if e.forma == forma]


def _valores_arreglo(paso: Paso, nid: int) -> list:
    return [v.v for v in paso.monticulo[nid].elementos]


# ---------------------------------------------------------------- algoritmos sobre arreglos


@pytest.mark.parametrize("relativa", ["es/nivel05/01_burbuja.inv", "en/level05/01_bubble_sort.inv"])
def test_burbuja_accesos_e_ids_estables(relativa):
    traza = _trazar(relativa)
    assert traza.error is None and not traza.truncada
    esperado = (CURRICULO / relativa).with_suffix(".expected").read_text(encoding="utf-8")
    assert "".join(traza.salida) == esperado
    # El arreglo de main conserva su id en TODOS los pasos (se puede animar).
    ids = {
        m.variables["a"].valor.id
        for p in traza.pasos
        for m in p.marcos
        if m.subrutina == "main" and "a" in m.variables
    }
    assert len(ids) == 1
    (nid,) = ids
    # Comparación: lee a[j] y a[j+1] en la misma instrucción.
    comparaciones = [p for p in traza.pasos if [x[1] for x in _lecturas(p)] == [(0,), (1,)]]
    assert comparaciones and all(a.nodo == nid for a in comparaciones[0].accesos)
    # El intercambio escribe celdas del MISMO nodo a través del parámetro.
    escrituras = [a for p in traza.pasos for a in p.accesos if a.op == "escribe" and a.indices]
    assert escrituras and {a.nodo for a in escrituras} == {nid}
    assert _valores_arreglo(traza.pasos[-1], nid) == [11, 12, 22, 25, 34, 64, 90]
    # Cada paso es un arreglo: forma reconocida y etiqueta "a".
    assert all(e.etiqueta == "a" for _, e in _estructuras(traza, "arreglo"))


@pytest.mark.parametrize(
    "relativa", ["es/nivel04/05_busqueda_binaria.inv", "en/level04/05_binary_search.inv"]
)
def test_busqueda_binaria_lee_la_celda_del_medio(relativa):
    traza = _trazar(relativa)
    assert traza.error is None
    lecturas = [a for p in traza.pasos for a in p.accesos if a.op == "lee" and a.indices]
    # 23 está en la posición 5: la búsqueda lee a[4] y luego a[7], a[5].
    assert [a.indices[0] for a in lecturas][:4] == [4, 4, 7, 7]
    assert all(a.var == "a" for a in lecturas)
    # Dentro de la función hay dos marcos vivos: main y la búsqueda.
    profundas = [p for p in traza.pasos if len(p.marcos) == 3]
    assert profundas and profundas[0].marcos[2].subrutina in ("busquedaBinaria", "binarySearch")


# ---------------------------------------------------------------- recursión


@pytest.mark.parametrize(
    "relativa", ["es/nivel03/06_factorial_recursivo.inv", "en/level03/06_recursive_factorial.inv"]
)
def test_factorial_recursivo_pila_de_llamadas(relativa):
    traza = _trazar(relativa)
    assert traza.error is None
    profundidad = max(len(p.marcos) for p in traza.pasos)
    assert profundidad >= 6  # global + main + varias activaciones del factorial
    # Cada activación tiene su propio n (marcos independientes).
    paso = next(p for p in traza.pasos if len(p.marcos) == profundidad)
    valores_n = [m.variables["n"].valor.v for m in paso.marcos[2:] if "n" in m.variables]
    assert valores_n == sorted(valores_n, reverse=True) and len(set(valores_n)) == len(valores_n)
    # Tras cada retorno hay un paso de "regreso" en la línea del llamador con
    # un marco menos.
    regresos = [
        (a, b) for a, b in zip(traza.pasos, traza.pasos[1:], strict=False) if len(b.marcos) == len(a.marcos) - 1
    ]
    assert regresos


@pytest.mark.parametrize(
    "relativa", ["es/nivel03/10_torres_de_hanoi.inv", "en/level03/10_towers_of_hanoi.inv"]
)
def test_hanoi_se_trunca_y_detiene_el_programa(relativa):
    traza = _trazar(relativa, max_pasos=120)
    assert traza.truncada and len(traza.pasos) == 120 and traza.error is None
    completo = (CURRICULO / relativa).with_suffix(".expected").read_text(encoding="utf-8")
    # La ejecución se detuvo: solo hay parte de la salida.
    assert completo.startswith("".join(traza.salida)) and "".join(traza.salida) != completo
    assert "".join(s for p in traza.pasos for s in p.salida_nueva) == "".join(traza.salida)
    assert [p.n for p in traza.pasos] == list(range(1, 121))
    assert max(len(p.marcos) for p in traza.pasos) >= 5  # hanoi(3) -> hanoi(2) -> ...


# ---------------------------------------------------------------- estructuras del currículo


@pytest.mark.parametrize(
    ("relativa", "etiqueta"),
    [("es/nivel10/02_pila_enlazada.inv", "p"), ("en/level10/02_linked_stack.inv", "p")],
)
def test_pila_enlazada(relativa, etiqueta):
    traza = _trazar(relativa)
    pilas = _estructuras(traza, "pila")
    assert pilas
    paso, pila = next((p, e) for p, e in pilas if len(e.nodos) == 6)  # tras apilar 1..6
    assert pila.etiqueta == etiqueta
    valores = [
        paso.monticulo[n].campos["valor" if relativa.startswith("es") else "value"].v
        for n in pila.nodos
    ]
    assert valores == [6, 5, 4, 3, 2, 1]  # del tope al fondo
    assert pila.aristas[0][0] == pila.raiz  # el contenedor apunta al tope


@pytest.mark.parametrize(
    "relativa", ["es/nivel10/05_cola_circular.inv", "en/level10/05_circular_queue.inv"]
)
def test_cola_circular_sobre_arreglo(relativa):
    traza = _trazar(relativa)
    colas = _estructuras(traza, "cola")
    assert colas and all(e.etiqueta in ("cola", "queue") for _, e in colas)
    assert all(p.monticulo[e.raiz].tipo == "arreglo" for p, e in colas)


@pytest.mark.parametrize(
    "relativa", ["es/nivel10/07_lista_simple.inv", "en/level10/07_singly_linked_list.inv"]
)
def test_lista_enlazada(relativa):
    traza = _trazar(relativa)
    listas = _estructuras(traza, "lista_enlazada")
    assert listas
    paso, lista = max(listas, key=lambda pe: len(pe[1].nodos))
    assert len(lista.nodos) >= 3
    # La raíz es el contenedor (no es un elemento) y apunta a la cabeza; las
    # demás aristas siguen el orden de los nodos: cabeza -> ... -> último.
    assert lista.raiz not in lista.nodos
    assert lista.aristas[0][:2] == (lista.raiz, lista.nodos[0])
    enlaces = [(a, b) for a, b, _ in lista.aristas if a != lista.raiz]
    assert enlaces == list(zip(lista.nodos, lista.nodos[1:], strict=False))


@pytest.mark.parametrize(
    "relativa", ["es/nivel10/08_lista_doble.inv", "en/level10/08_doubly_linked_list.inv"]
)
def test_lista_doble(relativa):
    traza = _trazar(relativa)
    paso, lista = max(_estructuras(traza, "lista_doble"), key=lambda pe: len(pe[1].nodos))
    etiquetas = {e for a, _, e in lista.aristas if a != lista.raiz}  # sin las del contenedor
    assert etiquetas == (
        {"siguiente", "anterior"} if relativa.startswith("es") else {"next", "prev"}
    )


@pytest.mark.parametrize(
    "relativa", ["es/nivel11/01_abb_insercion.inv", "en/level11/01_bst_insertion.inv"]
)
def test_abb(relativa):
    traza = _trazar(relativa)
    paso, arbol = max(_estructuras(traza, "arbol_binario"), key=lambda pe: len(pe[1].nodos))
    assert arbol.etiqueta in ("raiz", "root")
    campo = "valor" if relativa.startswith("es") else "value"
    valores = [paso.monticulo[n].campos[campo].v for n in arbol.nodos]
    assert valores[0] == 50 and sorted(valores) == [20, 30, 40, 50, 60, 70, 80]
    # Mientras la recursión apunta a un subárbol, se sigue dibujando desde la raíz.
    raices = {e.raiz for _, e in _estructuras(traza, "arbol_binario") if len(e.nodos) > 1}
    assert raices == {arbol.raiz}


@pytest.mark.parametrize("relativa", ["es/nivel12/03_bfs.inv", "en/level12/03_bfs.inv"])
def test_bfs_con_matriz_de_adyacencia(relativa):
    traza = _trazar(relativa)
    ultimo = traza.pasos[-1]
    grafo = next(e for e in ultimo.estructuras if e.forma == "grafo")
    assert ultimo.monticulo[grafo.raiz].tipo == "matriz"
    # Aristas por ÍNDICE de vértice; no dirigido: cada arista en ambos sentidos.
    pares = {(a, b) for a, b, _ in grafo.aristas}
    assert {(0, 1), (1, 0), (0, 2), (3, 4), (4, 5)} <= pares and len(pares) == 12
    assert any(e.forma == "matriz" and e.raiz == grafo.raiz for e in ultimo.estructuras)
    assert any(e.forma == "cola" for e in ultimo.estructuras)


# ---------------------------------------------------------------- biblioteca estándar

PILA_COLA_ES = """
importar "estructuras/pila";
importar "estructuras/cola";
vacio main() {
    Pila p = nuevo Pila();
    Cola c = nuevo Cola();
    para (entero i = 1; i <= 3; i++) {
        p.apilar(i);
        c.encolar(i * 10);
    }
    imprimir(p.desapilar());
}
"""
PILA_COLA_EN = """
import "structures/stack";
import "structures/queue";
void main() {
    Stack p = new Stack();
    Queue c = new Queue();
    for (int i = 1; i <= 3; i++) {
        p.push(i);
        c.enqueue(i * 10);
    }
    print(p.pop());
}
"""


@pytest.mark.parametrize("codigo", [PILA_COLA_ES, PILA_COLA_EN])
def test_pila_y_cola_de_la_biblioteca(codigo):
    traza = trazar(codigo)
    assert traza.error is None and "".join(traza.salida) == "3"
    lineas = len(codigo.splitlines())
    # El código de la biblioteca es de OTRO archivo: no aparece como pasos.
    assert all(0 < p.linea <= lineas for p in traza.pasos)
    paso = traza.pasos[-2]  # tras el último encolar
    formas = {e.forma: e for e in paso.estructuras}
    campo = "valor" if "importar" in codigo else "value"
    pila = formas["pila"]
    assert [paso.monticulo[n].campos[campo].v for n in pila.nodos] == [3, 2, 1]
    cola = formas["cola"]
    assert [paso.monticulo[n].campos[campo].v for n in cola.nodos] == [10, 20, 30]
    assert {e for _, _, e in cola.aristas} >= (
        {"frente", "final"} if campo == "valor" else {"front", "rear"}
    )
    # La llamada p.apilar(i) agrupa las escrituras internas en su paso.
    assert any(
        ("este" if campo == "valor" else "this", (), "cantidad" if campo == "valor" else "count")
        in _escrituras(p)
        for p in traza.pasos
    )


GRAFO_ES = """
importar "estructuras/grafo";
vacio main() {
    Grafo g = nuevo Grafo(falso);
    para (entero i = 0; i < 4; i++) {
        g.agregar_vertice();
    }
    g.agregar_arista(0, 1, 4);
    g.agregar_arista(0, 2, 1);
    g.agregar_arista(2, 3, 5);
    imprimir(g.bfs(0));
}
"""


def test_grafo_de_la_biblioteca_con_vertices_objeto():
    for codigo in (GRAFO_ES, api_traducir(GRAFO_ES)):
        traza = trazar(codigo)
        assert traza.error is None and "".join(traza.salida) == "0 1 2 3"
        paso = traza.pasos[-1]
        grafo = next(e for e in paso.estructuras if e.forma == "grafo")
        assert paso.monticulo[grafo.raiz].tipo == "objeto" and len(grafo.nodos) == 4
        numero = {
            n: next(v.v for k, v in paso.monticulo[n].campos.items() if k == "id")
            for n in grafo.nodos
        }
        aristas = {(numero[a], numero[b], p) for a, b, p in grafo.aristas}
        assert aristas == {
            (0, 1, "4"),
            (1, 0, "4"),
            (0, 2, "1"),
            (2, 0, "1"),
            (2, 3, "5"),
            (3, 2, "5"),
        }


def api_traducir(codigo: str) -> str:
    from inveniolang.traductor import traducir

    return (
        traducir(codigo, "en")
        .replace('"estructuras/grafo"', '"structures/graph"')
        .replace("agregar_vertice", "add_vertex")
        .replace("agregar_arista", "add_edge")
        .replace("Grafo", "Graph")
    )


# ---------------------------------------------------------------- errores y límites


def test_error_de_ejecucion_deja_la_traza_parcial():
    codigo = "vacio main() {\n    entero [3] a = {1, 2, 3};\n    a[1] = 9;\n    a[5] = 4;\n    imprimir(1);\n}\n"
    traza = trazar(codigo, ruta="t.inv")
    assert traza.error is not None and "IL-EJE-050" in traza.error and "t.inv:4" in traza.error
    assert not traza.truncada and traza.pasos[-1].linea == 4
    assert traza.salida == ()
    # La escritura válida anterior sí quedó registrada y visible.
    nid = traza.pasos[-1].marcos[-1].variables["a"].valor.id
    assert _valores_arreglo(traza.pasos[-1], nid) == [1, 9, 3]


def test_error_dentro_de_una_funcion_termina_en_su_linea():
    codigo = (
        "entero f(entero [] a) {\n    retornar a[7];\n}\n"
        "vacio main() {\n    entero [2] a = {1, 2};\n    imprimir(f(a));\n}\n"
    )
    traza = trazar(codigo)
    assert "IL-EJE-050" in (traza.error or "")
    ultimo = traza.pasos[-1]
    assert ultimo.linea == 2 and [m.subrutina for m in ultimo.marcos] == ["<global>", "main", "f"]


def test_error_de_compilacion_sin_pasos():
    traza = trazar('vacio main() { entero x = "hola"; }', idioma="en")
    assert traza.pasos == () and traza.error and "IL-" in traza.error
    assert traza.idioma == "en"


def test_max_pasos_validado():
    with pytest.raises(ValueError):
        trazar("vacio main() { }", max_pasos=0)
    with pytest.raises(ValueError):
        trazar("vacio main() { }", max_pasos=MAX_PASOS_TRAZA + 1)
    with pytest.raises(ValueError):
        trazar("vacio main() { }", max_pasos=True)


def test_recursion_infinita_da_il_eje_040_y_no_recursionerror():
    codigo = "entero f(entero n) { retornar f(n + 1); }\nvacio main() { imprimir(f(0)); }\n"
    traza = trazar(codigo, max_pasos=MAX_PASOS_TRAZA)
    assert "IL-EJE-040" in (traza.error or "")


def test_ciclo_infinito_respeta_el_limite_de_iteraciones(monkeypatch):
    monkeypatch.setattr(Interpreter, "MAX_RECURSION", Interpreter.MAX_RECURSION)
    codigo = "vacio main() { entero x = 0; mientras (verdadero) { x = x + 1; } }"
    traza = trazar(codigo, max_pasos=50)
    assert traza.truncada and len(traza.pasos) == 50


def test_presupuesto_de_celdas_trunca(monkeypatch):
    monkeypatch.setattr(modulo_traza, "MAX_CELDAS_TRAZA", 150)
    codigo = (
        "vacio main() {\n    entero [100] a;\n"
        "    para (entero i = 0; i < 100; i++) { a[i] = i; }\n}\n"
    )
    traza = trazar(codigo)
    assert traza.truncada and 0 < len(traza.pasos) < 100 and traza.error is None


def test_modulos_en_memoria():
    codigo = 'importar "util";\nvacio main() { imprimir(doble(4)); }\n'
    traza = trazar(
        codigo,
        ruta="/tmp/x/main.inv",
        modulos={"util.inv": "entero doble(entero x) { retornar x * 2; }"},
    )
    assert traza.error is None and traza.salida == ("8",)
    assert all(p.linea <= 2 for p in traza.pasos)


# ---------------------------------------------------------------- objetos y accesos a campos


def test_accesos_a_campos_y_este():
    codigo = (
        "clase Contador {\n    publico entero n;\n"
        "    publico vacio sumar() { este.n = este.n + 1; }\n}\n"
        "vacio main() {\n    Contador c = nuevo Contador();\n    c.sumar();\n    c.n = 5;\n    imprimir(c.n);\n}\n"
    )
    traza = trazar(codigo)
    accesos = [(a.op, a.var, a.campo) for p in traza.pasos for a in p.accesos if a.campo]
    assert ("lee", "este", "n") in accesos and ("escribe", "este", "n") in accesos
    assert ("escribe", "c", "n") in accesos and ("lee", "c", "n") in accesos
    metodo = next(p for p in traza.pasos if p.marcos[-1].subrutina == "Contador.sumar")
    assert metodo.marcos[-1].variables["este"].tipo == "Contador"
    objeto = next(e for e in traza.pasos[-1].estructuras if e.forma == "objeto")
    assert objeto.etiqueta == "c"


def test_lambda_y_mapear_registran_celdas():
    codigo = (
        "vacio main() {\n    entero [3] a = {1, 2, 3};\n    entero [3] b;\n"
        "    mapear(a, b, funcion(entero x) entero { retornar x * x; });\n    imprimir(b[2]);\n}\n"
    )
    traza = trazar(codigo)
    assert traza.error is None and traza.salida == ("9",)
    linea4 = [p for p in traza.pasos if p.linea == 4]
    b = linea4[0].marcos[1].variables["b"].valor.id
    escrituras = {(a.nodo, a.indices) for p in linea4 for a in p.accesos if a.op == "escribe"}
    assert {e for e in escrituras if e[1]} == {
        (b, (0,)),
        (b, (1,)),
        (b, (2,)),
    }
    lambda_activa = [p for p in traza.pasos if p.marcos[-1].subrutina == "<lambda>"]
    assert lambda_activa and "x" in lambda_activa[0].marcos[-1].variables


# ---------------------------------------------------------------- equivalencia y montículo incremental


_NIVELES = ("03", "04", "05", "10", "11", "12")


def _curriculo():
    for idioma, prefijo in (("es", "nivel"), ("en", "level")):
        for nivel in _NIVELES:
            yield from sorted((CURRICULO / idioma / f"{prefijo}{nivel}").glob("*.inv"))


@pytest.mark.parametrize("ruta", list(_curriculo()), ids=lambda r: f"{r.parent.name}/{r.stem}")
def test_la_traza_no_cambia_la_semantica(ruta):
    """Misma salida que la ejecución normal (cuando la traza no se trunca)."""
    codigo, entrada = _programa(str(ruta.relative_to(CURRICULO)))
    traza = trazar(codigo, entrada=entrada, ruta_fuente=str(ruta))
    assert traza.error is None
    if not traza.truncada:
        assert "".join(traza.salida) == ruta.with_suffix(".expected").read_text(encoding="utf-8")


def test_monticulo_incremental_igual_a_reconstruirlo_entero(monkeypatch):
    original = modulo_traza._Monticulo.instantanea
    diferencias = []

    def comprobada(self, raices):
        raices = list(raices)
        incremental = original(self, raices)
        fresco = modulo_traza._Monticulo()
        fresco._ids = self._ids  # mismos ids, sin copias previas
        if original(fresco, raices) != incremental:
            diferencias.append(1)
        return incremental

    monkeypatch.setattr(modulo_traza._Monticulo, "instantanea", comprobada)
    for relativa in (
        "es/nivel05/01_burbuja.inv",
        "en/level05/06_quick_sort.inv",
        "es/nivel06/09_rotar_matriz.inv",
        "en/level10/08_doubly_linked_list.inv",
        "es/nivel11/05_abb_eliminacion.inv",
        "en/level12/02_adjacency_list.inv",
        "es/nivel08/07_arreglo_de_objetos.inv",
        "es/nivel13/02_lineal_vs_binaria.inv",
    ):
        _trazar(relativa, max_pasos=1500)
    assert diferencias == []


# ---------------------------------------------------------------- idioma y descripción


def test_idioma_deducido_del_programa():
    es, _ = _programa("es/nivel05/01_burbuja.inv")
    en, _ = _programa("en/level05/01_bubble_sort.inv")
    assert detectar_idioma(es) == "es" and detectar_idioma(en) == "en"
    assert detectar_idioma("") is None
    assert trazar(en).idioma == "en" and trazar(en, idioma="es").idioma == "es"
    errores_en = trazar("void main() { int x = 1 / 0; }").error or ""
    assert "IL-EJE" in errores_en and "división" not in errores_en.lower()


def test_describir_bilingue_de_una_traza_real():
    """INV-2009: la descripción accesible (render_texto.describir) de pasos reales."""
    from inveniolang.visualizacion import describir

    traza = _trazar("es/nivel05/01_burbuja.inv", max_pasos=12)
    paso = next(p for p in traza.pasos if _escrituras(p) and _escrituras(p)[0][1])
    es = describir(paso.a_dict(), "es")
    en = describir(paso.a_dict(), "en")
    assert "Se escribe a[0]" in es and "Writes a[0]" in en
    assert "Arreglo a con 7 elementos" in es and "intercambiar" in es


# ---------------------------------------------------------------- coste cero con la traza apagada


def test_registro_apagado_por_defecto_y_sin_coste(monkeypatch):
    """Una ejecución normal no construye instantáneas ni llama al registro."""
    analisis = analizar_fuente("vacio main() { entero [2] a = {1, 2}; a[0] = a[1]; }")
    interp = Interpreter(analisis.errores, analisis.tabla)
    assert interp.registro_accesos is None and interp.debug is False
    assert interp.debug_on_statement is None

    def prohibido(*_a, **_k):
        raise AssertionError("la ejecución normal no debe tocar el trazador")

    monkeypatch.setattr(Interpreter, "_snapshot_debug", prohibido)
    monkeypatch.setattr(Interpreter, "_registrar_escritura", prohibido)
    codigo, entrada = _programa("es/nivel05/01_burbuja.inv")
    resultado = api.ejecutar(codigo, entrada=entrada)
    assert resultado.ok


def test_registro_de_accesos_del_interprete():
    """INV-2000: el intérprete avisa cada lectura/escritura de celda y campo."""
    codigo = (
        "clase P { publico entero x; }\n"
        "vacio main() {\n    entero [2][2] m;\n    m[1][0] = 3;\n    m[1][0] += m[1][0];\n"
        "    P p = nuevo P();\n    p.x = m[1][0];\n}\n"
    )
    analisis = analizar_fuente(codigo)
    interp = Interpreter(analisis.errores, analisis.tabla)
    vistos = []
    interp.registro_accesos = lambda op, var, obj, ind, campo: vistos.append((op, var, ind, campo))
    interp.interpretar(analisis.ast, usar_stdin=False)
    assert vistos == [
        ("escribe", "m", (1, 0), None),
        ("lee", "m", (1, 0), None),
        ("lee", "m", (1, 0), None),
        ("escribe", "m", (1, 0), None),
        ("lee", "m", (1, 0), None),
        ("escribe", "p", (), "x"),
    ]


def test_asignacion_con_linea_real():
    """INV-2004: antes toda asignación tenía línea 0 (y su error decía L0)."""
    codigo = "vacio main() {\n    entero [2] a = {1, 2};\n\n    a[3] = 1;\n}\n"
    r = api.ejecutar(codigo, ruta="p.inv")
    assert not r.ok and "p.inv:4:5" in r.errores[0]
    analisis = analizar_fuente(
        "vacio main() {\n  entero x;\n  x = 1;\n  entero [2][2] m;\n  m[0][1] = 2;\n}"
    )
    asignaciones = [
        e for e in analisis.ast.main.bloque.elementos if type(e).__name__ == "AssignStmt"
    ]
    assert [(a.linea, a.columna) for a in asignaciones] == [(3, 3), (5, 0)]


def test_api_trazar_es_la_fachada():
    codigo, _ = _programa("es/nivel05/01_burbuja.inv")
    assert api.trazar(codigo, max_pasos=30) == trazar(codigo, max_pasos=30)


def test_api_traza_html_y_traza_svg_desde_codigo_o_traza():
    """INV-2009: la fachada exporta HTML/SVG a partir de código o de una Traza."""
    import xml.etree.ElementTree as ET

    codigo, _ = _programa("en/level05/01_bubble_sort.inv")
    traza = api.trazar(codigo, max_pasos=20)
    assert api.traza_html(codigo, max_pasos=20) == api.traza_html(traza)
    assert api.traza_html(traza.a_dict()) == api.traza_html(traza)
    svg = api.traza_svg(codigo, 3, max_pasos=20)
    assert svg == api.traza_svg(traza, 3)
    raiz = ET.fromstring(svg)
    assert raiz.get("data-paso") == "4"  # posición 3 = paso número 4
    with pytest.raises(IndexError):
        api.traza_svg(traza, 20)
