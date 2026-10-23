"""Descripción textual y accesible de un paso de una Traza (equipo VISTA).

INV-2200: el estudiante que usa lector de pantalla (o que simplemente
prefiere leer) debe poder seguir la ejecución igual que quien mira el
dibujo. :func:`describir` convierte un ``Paso`` del contrato JSON de la
Fase 2 en frases completas en español o inglés: qué línea se ejecuta, qué
celdas se leyeron y escribieron, qué se imprimió, la pila de llamadas y el
estado de cada estructura viva. El SVG (``render_svg``) usa este mismo
texto como ``<desc>`` y el reproductor HTML como región ``aria-live``.

Este módulo también reúne la lectura del contrato que comparten los tres
renderizadores (normalizar el JSON, formatear valores, recorrer pilas,
colas, listas, árboles y grafos) para que el texto y el dibujo nunca
discrepen sobre qué hay en memoria.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import math
from collections.abc import Iterable, Mapping
from typing import Any

from .. import i18n

# Formas que el contrato admite en ``Estructura.forma``.
FORMAS: tuple[str, ...] = (
    "arreglo",
    "matriz",
    "pila",
    "cola",
    "lista_enlazada",
    "lista_doble",
    "arbol_binario",
    "grafo",
    "indice_cima",
    "objeto",
)

# INV-2202: tablas de sinónimos bilingües en un solo sitio. El clasificador
# de TRAZA decide la forma; aquí sólo hace falta reconocer qué campo de un
# nodo es su "valor" y qué arista es el hijo izquierdo/derecho, en es y en.
CAMPOS_VALOR: tuple[str, ...] = (
    "valor",
    "value",
    "dato",
    "data",
    "clave",
    "key",
    "info",
    "elemento",
    "item",
    "id",
    "nombre",
    "name",
)
ENLACES_IZQ: frozenset[str] = frozenset({"izq", "izquierdo", "izquierda", "left", "l"})
ENLACES_DER: frozenset[str] = frozenset({"der", "derecho", "derecha", "right", "r"})
CAMPOS_VISITADO: frozenset[str] = frozenset({"visitado", "visited", "visto", "seen"})
TIPOS_TEXTO: frozenset[str] = frozenset({"texto", "cadena", "string", "str"})
TIPOS_CARACTER: frozenset[str] = frozenset({"caracter", "carácter", "char"})

# Cuántos elementos se enumeran en una frase antes de resumir con "y N más":
# una descripción de 500 números es inútil para un lector de pantalla.
MAX_EN_FRASE = 12


class TrazaInvalida(ValueError):
    """La traza o el paso no cumplen el contrato JSON de la Fase 2."""


# ----------------------------------------------------------------- contrato


def _falla(ruta: str, esperado: str, idioma: str) -> TrazaInvalida:
    motivo = i18n.t("VIS.error.motivo.tipo", idioma, esperado=esperado)
    return TrazaInvalida(i18n.t("VIS.error.traza_invalida", idioma, ruta=ruta, motivo=motivo))


def _entero(valor: Any, ruta: str, idioma: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise _falla(ruta, "int", idioma)
    try:
        return int(valor)
    except ValueError as e:
        raise _falla(ruta, "int", idioma) from e


def _lista(valor: Any, ruta: str, idioma: str) -> list[Any]:
    if valor is None:
        return []
    if not isinstance(valor, (list, tuple)):
        raise _falla(ruta, "list", idioma)
    return list(valor)


def _dic(valor: Any, ruta: str, idioma: str) -> dict[Any, Any]:
    if valor is None:
        return {}
    if not isinstance(valor, dict):
        raise _falla(ruta, "dict", idioma)
    return valor


def normalizar_paso(paso: Mapping[str, Any], idioma: str = "es") -> dict[str, Any]:
    """Valida un ``Paso`` del contrato y devuelve una copia con claves enteras.

    El JSON convierte las claves del montículo en cadenas (``"3"``); el
    contrato las define como ``int``. Normalizar aquí, una vez, evita que cada
    renderizador tenga que probar las dos formas. Es idempotente.
    """
    p = _dic(paso, "paso", idioma)
    monticulo: dict[int, dict[str, Any]] = {}
    for clave, nodo in _dic(p.get("monticulo"), "monticulo", idioma).items():
        ident = _entero(clave, f"monticulo[{clave!r}]", idioma)
        nodo = _dic(nodo, f"monticulo[{ident}]", idioma)
        monticulo[ident] = {
            "id": ident,
            "tipo": str(nodo.get("tipo", "objeto")),
            "clase": nodo.get("clase"),
            "elementos": _lista(nodo.get("elementos"), f"monticulo[{ident}].elementos", idioma),
            "campos": _dic(nodo.get("campos"), f"monticulo[{ident}].campos", idioma),
        }
    estructuras = []
    for i, est in enumerate(_lista(p.get("estructuras"), "estructuras", idioma)):
        est = _dic(est, f"estructuras[{i}]", idioma)
        aristas = []
        for j, a in enumerate(_lista(est.get("aristas"), f"estructuras[{i}].aristas", idioma)):
            a = _lista(a, f"estructuras[{i}].aristas[{j}]", idioma)
            if len(a) < 2:
                raise _falla(f"estructuras[{i}].aristas[{j}]", "[int, int, str]", idioma)
            ruta_a = f"estructuras[{i}].aristas[{j}]"
            etiqueta = "" if len(a) < 3 or a[2] is None else str(a[2])
            aristas.append((_entero(a[0], ruta_a, idioma), _entero(a[1], ruta_a, idioma), etiqueta))
        forma = str(est.get("forma", "objeto"))
        if forma not in FORMAS:
            raise _falla(f"estructuras[{i}].forma", " | ".join(FORMAS), idioma)
        estructuras.append(
            {
                "forma": forma,
                "raiz": _entero(est.get("raiz"), f"estructuras[{i}].raiz", idioma),
                "etiqueta": str(est.get("etiqueta") or ""),
                "nodos": [
                    _entero(n, f"estructuras[{i}].nodos", idioma)
                    for n in _lista(est.get("nodos"), f"estructuras[{i}].nodos", idioma)
                ],
                "aristas": aristas,
                # INV-4400: índice de la cima de una pila sobre arreglo (opcional).
                "cima": (
                    None
                    if est.get("cima") is None
                    else _entero(est.get("cima"), f"estructuras[{i}].cima", idioma)
                ),
            }
        )
    marcos = []
    for i, m in enumerate(_lista(p.get("marcos"), "marcos", idioma)):
        m = _dic(m, f"marcos[{i}]", idioma)
        variables = _dic(m.get("variables"), f"marcos[{i}].variables", idioma)
        marcos.append(
            {
                "subrutina": str(m.get("subrutina") or "?"),
                "linea": _entero(m.get("linea", 0), f"marcos[{i}].linea", idioma),
                "variables": {
                    str(k): _dic(v, f"marcos[{i}].variables[{k!r}]", idioma)
                    for k, v in variables.items()
                },
            }
        )
    accesos = []
    for i, a in enumerate(_lista(p.get("accesos"), "accesos", idioma)):
        a = _dic(a, f"accesos[{i}]", idioma)
        op = a.get("op")
        if op not in ("lee", "escribe"):
            raise _falla(f"accesos[{i}].op", "lee | escribe", idioma)
        nodo = a.get("nodo")
        accesos.append(
            {
                "op": op,
                "var": None if a.get("var") is None else str(a.get("var")),
                "nodo": None if nodo is None else _entero(nodo, f"accesos[{i}].nodo", idioma),
                "indices": [
                    _entero(x, f"accesos[{i}].indices", idioma)
                    for x in _lista(a.get("indices"), f"accesos[{i}].indices", idioma)
                ],
                "campo": None if a.get("campo") is None else str(a.get("campo")),
            }
        )
    return {
        "n": _entero(p.get("n", 0), "n", idioma),
        "linea": _entero(p.get("linea", 0), "linea", idioma),
        "columna": _entero(p.get("columna", 0), "columna", idioma),
        "marcos": marcos,
        "monticulo": monticulo,
        "accesos": accesos,
        "salida_nueva": [str(s) for s in _lista(p.get("salida_nueva"), "salida_nueva", idioma)],
        "estructuras": estructuras,
    }


def normalizar_traza(traza: Any) -> dict[str, Any]:
    """Acepta una Traza como ``dict``, texto JSON o dataclass y la valida.

    INV-2203: los renderizadores consumen el contrato, no la implementación
    de TRAZA. Un objeto ``Traza`` (dataclass de ``modelo.py``) se convierte
    con su propio ``a_json`` —importado de forma perezosa— para no duplicar
    su serialización ni depender de él cuando la traza llega como JSON.
    """
    if isinstance(traza, (bytes, bytearray)):
        traza = traza.decode("utf-8")
    if isinstance(traza, str):
        try:
            traza = json.loads(traza)
        except json.JSONDecodeError as e:
            raise _falla("json", f"JSON ({e.msg})", "es") from e
    elif dataclasses.is_dataclass(traza) and not isinstance(traza, type):
        try:
            modelo = importlib.import_module(f"{__package__}.modelo")
        except ModuleNotFoundError as e:
            if e.name != f"{__package__}.modelo":
                raise
            raise TrazaInvalida(i18n.t("VIS.error.sin_modelo")) from e
        traza = json.loads(modelo.a_json(traza))
    t = _dic(traza, "traza", "es")
    idioma = i18n.normalizar_idioma(str(t.get("idioma") or "es"), estricto=False)
    version = t.get("version", 1)
    if version != 1:
        motivo = i18n.t("VIS.error.motivo.version", idioma, version=version)
        raise TrazaInvalida(
            i18n.t("VIS.error.traza_invalida", idioma, ruta="version", motivo=motivo)
        )
    pasos = [
        normalizar_paso(_dic(p, f"pasos[{i}]", idioma), idioma)
        for i, p in enumerate(_lista(t.get("pasos"), "pasos", idioma))
    ]
    error = t.get("error")
    return {
        "version": 1,
        "idioma": idioma,
        "fuente": str(t.get("fuente") or ""),
        "pasos": pasos,
        "truncada": bool(t.get("truncada", False)),
        "error": None if error is None else str(error),
        "salida": [str(s) for s in _lista(t.get("salida"), "salida", idioma)],
    }


# ----------------------------------------------------------------- valores


def _numero(v: float) -> str:
    if math.isnan(v) or math.isinf(v):
        return str(v)
    if v == int(v) and abs(v) < 1e15:
        return f"{v:.1f}"
    return repr(v)


def valor_texto(valor: Any, idioma: str, nombres: Mapping[int, str] | None = None) -> str:
    """Texto corto de un ``Valor`` del contrato (escalar o referencia)."""
    if not isinstance(valor, Mapping):
        return _escalar_texto(valor, "", idioma)
    if valor.get("t") == "ref":
        ident = valor.get("id")
        if ident is None:
            return i18n.t("VIS.valor.nulo", idioma)
        destino = (nombres or {}).get(int(ident), f"#{ident}")
        return i18n.t("VIS.valor.ref", idioma, destino=destino)
    return _escalar_texto(valor.get("v"), str(valor.get("tipo") or ""), idioma)


def _escalar_texto(v: Any, tipo: str, idioma: str) -> str:
    if v is None:
        return i18n.t("VIS.valor.nulo", idioma)
    if isinstance(v, bool):
        return i18n.t("VIS.valor.verdadero" if v else "VIS.valor.falso", idioma)
    if isinstance(v, float):
        return _numero(v)
    if isinstance(v, str):
        if tipo.lower() in TIPOS_CARACTER:
            return "'" + v + "'"
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def es_ref(valor: Any) -> bool:
    """Indica si un ``Valor`` es una referencia no nula a un nodo."""
    return isinstance(valor, Mapping) and valor.get("t") == "ref" and valor.get("id") is not None


def valor_de_nodo(nodo: Mapping[str, Any] | None) -> Any:
    """``Valor`` que representa a un nodo enlazado (su campo ``valor``/``dato``…).

    Si el objeto no tiene un campo con nombre de valor, se usa su primer
    campo escalar: así un nodo ``{"edad": 7, "sig": ref}`` sigue mostrando 7.
    """
    if not nodo:
        return None
    campos = nodo.get("campos") or {}
    for nombre in CAMPOS_VALOR:
        if nombre in campos:
            return campos[nombre]
    for valor in campos.values():
        if not (isinstance(valor, Mapping) and valor.get("t") == "ref"):
            return valor
    return None


def nombres_de_nodos(paso: Mapping[str, Any], idioma: str = "es") -> dict[int, str]:
    """Nombre legible de cada nodo: ``m[1]``, ``t``, ``actual`` o ``nodo 40 de t``.

    INV-2204: "#104.izquierdo" no le dice nada a un estudiante. La prioridad
    va de lo más preciso a lo más genérico: fila de una matriz, etiqueta de
    la estructura, variable que lo referencia y, por último, el nodo descrito
    por su valor dentro de la estructura a la que pertenece.
    """
    nombres: dict[int, str] = {}
    for est in paso["estructuras"]:
        etiqueta = est["etiqueta"] or f"#{est['raiz']}"
        if est["forma"] == "grafo":
            if grafo_por_indices(est, paso) is not None:
                continue  # sus vértices son índices, no nodos del montículo
            miembros = grafo(est, paso)[0]
        elif est["forma"] == "arbol_binario":
            raiz, hijos = arbol(est, paso)
            miembros = [n for nivel in niveles_arbol(raiz, hijos) for n in nivel]
        else:
            miembros = [n for n, _ in secuencia(est, paso) if n is not None]
        for n in miembros:
            if n == est["raiz"]:
                continue
            if est["forma"] == "grafo":
                valor = etiqueta_vertice(n, paso, idioma)
            else:
                valor = valor_texto(valor_de_nodo(paso["monticulo"].get(n)), idioma)
            nombres[n] = i18n.t("VIS.nombre.nodo", idioma, valor=valor, etiqueta=etiqueta)
    for marco in paso["marcos"]:
        for nombre, var in marco["variables"].items():
            valor = var.get("valor")
            if es_ref(valor):
                nombres[int(valor["id"])] = nombre
    for est in paso["estructuras"]:
        etiqueta = est["etiqueta"] or f"#{est['raiz']}"
        nombres[est["raiz"]] = etiqueta
        if est["forma"] == "matriz":
            for fila, i in filas_matriz(est, paso)[1].items():
                nombres[fila] = f"{etiqueta}[{i}]"
    return nombres


def unir(partes: Iterable[str], idioma: str, maximo: int = MAX_EN_FRASE) -> str:
    """Une textos con comas y resume el exceso con "y N más"."""
    lista = list(partes)
    sep = i18n.t("VIS.sep", idioma)
    if len(lista) <= maximo:
        return sep.join(lista)
    resto = i18n.t("VIS.y_mas", idioma, n=len(lista) - maximo)
    return sep.join(lista[:maximo]) + sep + resto


# ----------------------------------------------------------------- estructuras


def secuencia(est: Mapping[str, Any], paso: Mapping[str, Any]) -> list[tuple[int | None, Any]]:
    """Elementos de una pila, cola o lista en orden (cima/frente/cabeza primero).

    Contrato unificado (INV-2007, docs/visualizacion.md): ``nodos`` lista
    SOLO los nodos-elemento, en el orden del recorrido. La raíz es el
    contenedor (``Pila``, ``ListaEnlazada``…) y entonces NO está en
    ``nodos``; si una variable apunta directamente al primer nodo, la raíz es
    ese nodo y sí está en ``nodos``. Antes se descartaba siempre la raíz, y
    una lista sin contenedor perdía su cabeza. Si no hay nodos y la raíz es
    un arreglo, los elementos son sus celdas: en una pila, de la celda
    ``cima`` (la que marca su tope, INV-4400) hacia la 0, o de la última si
    el programa no marca el tope. Devuelve pares (id del nodo o None, Valor).
    """
    monticulo = paso["monticulo"]
    if est["nodos"]:
        return [(n, valor_de_nodo(monticulo.get(n))) for n in est["nodos"]]
    raiz = monticulo.get(est["raiz"])
    if raiz is not None and raiz["tipo"] == "arreglo":
        celdas: list[tuple[int | None, Any]] = [(None, v) for v in raiz["elementos"]]
        if est["forma"] != "pila":
            return celdas
        return celdas[: indice_cima(est, paso) + 1][::-1]
    return []


def indice_cima(est: Mapping[str, Any], paso: Mapping[str, Any]) -> int:
    """Índice de la celda cima de una pila sobre arreglo (-1 si está vacía)."""
    raiz = paso["monticulo"].get(est["raiz"])
    total = len(raiz["elementos"]) if raiz is not None else 0
    cima = est.get("cima")
    return total - 1 if cima is None else max(-1, min(int(cima), total - 1))


def _lado(etiqueta: str) -> str | None:
    e = etiqueta.strip().lower()
    if e in ENLACES_IZQ:
        return "izq"
    if e in ENLACES_DER:
        return "der"
    return None


def arbol(
    est: Mapping[str, Any], paso: Mapping[str, Any]
) -> tuple[int | None, dict[int, dict[str, int]]]:
    """Raíz y mapa ``padre -> {"izq": hijo, "der": hijo}`` de un árbol binario.

    El lado de cada arista sale de su etiqueta (izq/der, left/right…); si la
    etiqueta no lo dice, del nombre del campo del padre que apunta al hijo.
    Las aristas que no son izquierda/derecha (p. ej. contenedor → raíz) no
    forman parte del árbol dibujado. Los ciclos se descartan: un árbol
    corrupto no debe colgar el dibujo.
    """
    monticulo = paso["monticulo"]
    hijos: dict[int, dict[str, int]] = {}
    con_padre: set[int] = set()
    for origen, destino, etiqueta in est["aristas"]:
        lado = _lado(etiqueta)
        if lado is None:
            padre = monticulo.get(origen) or {}
            for campo, v in (padre.get("campos") or {}).items():
                if es_ref(v) and int(v["id"]) == destino and _lado(campo):
                    lado = _lado(campo)
        if lado is None or destino in con_padre or destino == origen:
            continue
        hijos.setdefault(origen, {})[lado] = destino
        con_padre.add(destino)
    en_arbol = {n for par in hijos.items() for n in (par[0], *par[1].values())}
    # INV-2007: `nodos` son solo los nodos del árbol (preorden); la raíz de
    # la estructura puede ser el contenedor, que no es un nodo del árbol.
    candidatos = [n for n in est["nodos"] if n in en_arbol] or list(est["nodos"])
    raices = [n for n in candidatos if n not in con_padre]
    if est["raiz"] in candidatos and (est["raiz"] in raices or not raices):
        return est["raiz"], hijos  # sin contenedor: la raíz es el primer nodo
    return (raices[0] if raices else None), hijos


def niveles_arbol(raiz: int | None, hijos: Mapping[int, Mapping[str, int]]) -> list[list[int]]:
    """Nodos por nivel (recorrido en anchura), sin repetir nodos."""
    if raiz is None:
        return []
    niveles: list[list[int]] = []
    actual, vistos = [raiz], {raiz}
    while actual:
        niveles.append(actual)
        siguiente = []
        for n in actual:
            for lado in ("izq", "der"):
                h = hijos.get(n, {}).get(lado)
                if h is not None and h not in vistos:
                    vistos.add(h)
                    siguiente.append(h)
        actual = siguiente
    return niveles


def grafo_por_indices(est: Mapping[str, Any], paso: Mapping[str, Any]) -> int | None:
    """Número de vértices si el grafo es una matriz/arreglo de adyacencia, si no None.

    INV-2007: sin objetos vértice, los extremos de las aristas son ÍNDICES
    ``0..n-1`` (no ids del montículo) y ``nodos`` está vacío.
    """
    if est["forma"] != "grafo":
        return None
    raiz = paso["monticulo"].get(est["raiz"])
    if raiz is None or raiz["tipo"] not in ("matriz", "arreglo"):
        return None
    return len(raiz["elementos"])


def grafo(
    est: Mapping[str, Any], paso: Mapping[str, Any]
) -> tuple[list[int], list[tuple[int, int, str, bool]]]:
    """Vértices en orden estable y aristas ``(u, v, peso, dirigida)``.

    Un par ``u→v`` y ``v→u`` con la misma etiqueta es una arista no dirigida
    (así guarda la biblioteca un grafo no dirigido) y se dibuja una sola vez.
    """
    extremos = [n for a in est["aristas"] for n in a[:2]]
    n_indices = grafo_por_indices(est, paso)
    vertices: list[int] = [] if n_indices is None else list(range(n_indices))
    for n in [*est["nodos"], *extremos]:
        if n not in vertices:
            vertices.append(n)
    vistas: set[tuple[int, int, str]] = set()
    pares = {(u, v, e) for u, v, e in est["aristas"]}
    aristas: list[tuple[int, int, str, bool]] = []
    for u, v, e in est["aristas"]:
        if (u, v, e) in vistas:
            continue
        reciproca = (v, u, e) in pares and u != v
        vistas.add((u, v, e))
        if reciproca:
            vistas.add((v, u, e))
        aristas.append((u, v, e, not reciproca))
    return vertices, aristas


def etiqueta_vertice(
    ident: int, paso: Mapping[str, Any], idioma: str, por_indices: bool = False
) -> str:
    """Rótulo de un vértice: su campo ``id``/``valor`` o el propio número."""
    if por_indices:
        return str(ident)
    nodo = paso["monticulo"].get(ident)
    if nodo is None:
        return str(ident)
    campos = nodo.get("campos") or {}
    for nombre in ("id", "nombre", "name", "etiqueta", "label", *CAMPOS_VALOR):
        if nombre in campos and not es_ref(campos[nombre]):
            return valor_texto(campos[nombre], idioma)
    valor = valor_de_nodo(nodo)
    return str(ident) if valor is None else valor_texto(valor, idioma)


def visitado(ident: int, paso: Mapping[str, Any], por_indices: bool = False) -> bool:
    """Si el vértice tiene un campo ``visitado``/``visited`` verdadero."""
    if por_indices:
        return False  # un índice no es un objeto: no tiene campos
    nodo = paso["monticulo"].get(ident) or {}
    for nombre, valor in (nodo.get("campos") or {}).items():
        if nombre.lower() in CAMPOS_VISITADO and isinstance(valor, Mapping):
            if valor.get("v") is True:
                return True
    return False


def filas_matriz(
    est: Mapping[str, Any], paso: Mapping[str, Any]
) -> tuple[list[list[Any]], dict[int, int]]:
    """Filas de una matriz y, si las filas son nodos propios, ``id_fila -> i``.

    El contrato admite las dos representaciones: un nodo ``matriz`` cuyos
    ``elementos`` son filas, o un ``arreglo`` de referencias a arreglos.
    """
    monticulo = paso["monticulo"]
    nodo = monticulo.get(est["raiz"])
    if nodo is None:
        return [], {}
    filas: list[list[Any]] = []
    ids_fila: dict[int, int] = {}
    for i, fila in enumerate(nodo["elementos"]):
        if isinstance(fila, list):
            filas.append(fila)
        elif es_ref(fila) and int(fila["id"]) in monticulo:
            ids_fila[int(fila["id"])] = i
            filas.append(list(monticulo[int(fila["id"])]["elementos"]))
        else:
            filas.append([fila])
    return filas, ids_fila


# ----------------------------------------------------------------- accesos


def estado_accesos(paso: Mapping[str, Any]) -> dict[tuple[Any, ...], str]:
    """Mapa ``clave -> "lee" | "escribe" | "ambos"`` de lo tocado en el paso.

    Claves: ``("celda", nodo, i, j…)``, ``("campo", nodo, campo)``,
    ``("nodo", nodo)`` (cualquier acceso al nodo) y ``("var", nombre)``.
    """
    estados: dict[tuple[Any, ...], str] = {}

    def marcar(clave: tuple[Any, ...], op: str) -> None:
        previo = estados.get(clave)
        estados[clave] = op if previo in (None, op) else "ambos"

    for a in paso["accesos"]:
        if a["nodo"] is not None:
            marcar(("nodo", a["nodo"]), a["op"])
            if a["indices"]:
                marcar(("celda", a["nodo"], *a["indices"]), a["op"])
            if a["campo"] is not None:
                marcar(("campo", a["nodo"], a["campo"]), a["op"])
        elif a["var"] is not None:
            marcar(("var", a["var"]), a["op"])
    return estados


def _valor_accedido(acceso: Mapping[str, Any], paso: Mapping[str, Any]) -> Any:
    monticulo = paso["monticulo"]
    if acceso["nodo"] is not None:
        nodo = monticulo.get(acceso["nodo"])
        if nodo is None:
            return None
        if acceso["campo"] is not None:
            return nodo["campos"].get(acceso["campo"])
        actual: Any = nodo["elementos"]
        for i in acceso["indices"]:
            if es_ref(actual) and int(actual["id"]) in monticulo:
                actual = monticulo[int(actual["id"])]["elementos"]
            if not isinstance(actual, list) or not 0 <= i < len(actual):
                return None
            actual = actual[i]
        return None if isinstance(actual, list) else actual
    for marco in reversed(paso["marcos"]):
        if acceso["var"] in marco["variables"]:
            return marco["variables"][acceso["var"]].get("valor")
    return None


def destino_acceso(
    acceso: Mapping[str, Any], nombres: Mapping[int, str], idioma: str = "es"
) -> str:
    """``a[2]``, ``m[1][0]``, ``actual.siguiente``, ``x`` o "el campo izq del nodo 7 de t"."""
    nodo = acceso["nodo"]
    nombre_nodo = nombres.get(nodo) if nodo is not None else None
    if nombre_nodo is not None and nombre_nodo.endswith("]"):
        base = nombre_nodo  # fila de una matriz: m[1] + [2]
    elif acceso["var"] is not None:
        base = acceso["var"]
    elif nombre_nodo is not None:
        base = nombre_nodo
    else:
        base = f"#{nodo}" if nodo is not None else "?"
    texto = base + "".join(f"[{i}]" for i in acceso["indices"])
    if acceso["campo"] is not None:
        if " " in base:
            return i18n.t("VIS.desc.campo_de", idioma, campo=acceso["campo"], nodo=texto)
        texto += "." + acceso["campo"]
    return texto


# ----------------------------------------------------------------- frases


def _frase_estructura(est: Mapping[str, Any], paso: Mapping[str, Any], idioma: str) -> str:
    forma = est["forma"]
    etiqueta = est["etiqueta"] or f"#{est['raiz']}"
    nombres = nombres_de_nodos(paso, idioma)
    vt = lambda v: valor_texto(v, idioma, nombres)  # noqa: E731 - atajo local
    nombre_forma = i18n.t(f"VIS.forma.{forma}", idioma)
    vacia = (
        "VIS.desc.vacia"
        if forma in ("matriz", "pila", "cola", "lista_enlazada", "lista_doble")
        else "VIS.desc.vacio"
    )
    monticulo = paso["monticulo"]
    if forma == "arreglo":
        nodo = monticulo.get(est["raiz"])
        elementos = nodo["elementos"] if nodo else []
        if not elementos:
            return i18n.t(vacia, idioma, forma=nombre_forma, etiqueta=etiqueta)
        valores = unir((vt(v) for v in elementos), idioma)
        return i18n.t(
            "VIS.desc.arreglo", idioma, etiqueta=etiqueta, n=len(elementos), valores=valores
        )
    if forma == "matriz":
        filas, _ = filas_matriz(est, paso)
        if not filas:
            return i18n.t(vacia, idioma, forma=nombre_forma, etiqueta=etiqueta)
        contenido = "; ".join(
            i18n.t("VIS.desc.fila", idioma, i=i, valores=unir((vt(v) for v in fila), idioma))
            for i, fila in enumerate(filas[:MAX_EN_FRASE])
        )
        if len(filas) > MAX_EN_FRASE:
            contenido += "; " + i18n.t("VIS.y_mas", idioma, n=len(filas) - MAX_EN_FRASE)
        columnas = max(len(f) for f in filas)
        return i18n.t(
            "VIS.desc.matriz",
            idioma,
            etiqueta=etiqueta,
            filas=len(filas),
            columnas=columnas,
            contenido=contenido,
        )
    if forma in ("pila", "cola", "lista_enlazada", "lista_doble"):
        elems = [vt(v) for _, v in secuencia(est, paso)]
        if not elems:
            return i18n.t(vacia, idioma, forma=nombre_forma, etiqueta=etiqueta)
        if forma == "pila":
            return i18n.t(
                "VIS.desc.pila_est",
                idioma,
                etiqueta=etiqueta,
                n=len(elems),
                tope=elems[0],
                valores=unir(elems, idioma),
            )
        if forma == "cola":
            return i18n.t(
                "VIS.desc.cola",
                idioma,
                etiqueta=etiqueta,
                n=len(elems),
                frente=elems[0],
                final=elems[-1],
                valores=unir(elems, idioma),
            )
        flecha = " → " if forma == "lista_enlazada" else " ⇄ "
        valores = flecha.join(elems[:MAX_EN_FRASE])
        if len(elems) > MAX_EN_FRASE:
            valores += flecha + i18n.t("VIS.y_mas", idioma, n=len(elems) - MAX_EN_FRASE)
        clave = "VIS.desc.lista" if forma == "lista_enlazada" else "VIS.desc.lista_doble"
        return i18n.t(clave, idioma, etiqueta=etiqueta, n=len(elems), valores=valores)
    if forma == "arbol_binario":
        raiz, hijos = arbol(est, paso)
        niveles = niveles_arbol(raiz, hijos)
        if raiz is None:
            return i18n.t(vacia, idioma, forma=nombre_forma, etiqueta=etiqueta)
        texto_nodo = lambda n: vt(valor_de_nodo(monticulo.get(n)))  # noqa: E731
        por_nivel = "; ".join(
            i18n.t(
                "VIS.desc.nivel", idioma, i=i, valores=unir((texto_nodo(n) for n in nivel), idioma)
            )
            for i, nivel in enumerate(niveles)
        )
        return i18n.t(
            "VIS.desc.arbol",
            idioma,
            etiqueta=etiqueta,
            n=sum(len(x) for x in niveles),
            altura=len(niveles) - 1,
            raiz=texto_nodo(raiz),
            niveles=por_nivel,
        )
    if forma == "grafo":
        return _frase_grafo(est, paso, idioma, etiqueta, nombre_forma, vacia)
    nodo = monticulo.get(est["raiz"]) or {"campos": {}, "clase": None}
    campos = unir((f"{k} = {vt(v)}" for k, v in nodo["campos"].items()), idioma)
    return i18n.t(
        "VIS.desc.objeto", idioma, etiqueta=etiqueta, clase=nodo.get("clase") or "?", campos=campos
    )


def _frase_grafo(
    est: Mapping[str, Any],
    paso: Mapping[str, Any],
    idioma: str,
    etiqueta: str,
    nombre_forma: str,
    vacia: str,
) -> str:
    vertices, aristas = grafo(est, paso)
    if not vertices:
        return i18n.t(vacia, idioma, forma=nombre_forma, etiqueta=etiqueta)
    indices = grafo_por_indices(est, paso) is not None
    rot = {v: etiqueta_vertice(v, paso, idioma, indices) for v in vertices}
    if not aristas:
        frase = i18n.t(
            "VIS.desc.grafo_sin_aristas",
            idioma,
            etiqueta=etiqueta,
            n=len(vertices),
            vertices=unir((rot[v] for v in vertices), idioma),
        )
    else:
        textos = []
        for u, v, peso, dirigida in aristas:
            clave = "VIS.desc.arista_dirigida" if dirigida else "VIS.desc.arista_no_dirigida"
            arista = i18n.t(clave, idioma, origen=rot[u], destino=rot[v])
            textos.append(
                i18n.t("VIS.desc.peso", idioma, arista=arista, peso=peso) if peso else arista
            )
        frase = i18n.t(
            "VIS.desc.grafo",
            idioma,
            etiqueta=etiqueta,
            n=len(vertices),
            m=len(aristas),
            aristas=unir(textos, idioma),
        )
    vistos = [rot[v] for v in vertices if visitado(v, paso, indices)]
    if vistos:
        frase += " " + i18n.t("VIS.desc.visitados", idioma, vertices=unir(vistos, idioma))
    return frase


def valor_variable(
    nombre: str, valor: Any, paso: Mapping[str, Any], idioma: str, nombres: Mapping[int, str]
) -> str:
    """Valor de una variable para la descripción.

    Una referencia que se llamaría como la propia variable ("primero = →
    primero") se describe por su contenido.
    """
    if es_ref(valor) and nombres.get(int(valor["id"])) == nombre:
        nodo = paso["monticulo"].get(int(valor["id"]))
        if nodo is not None:
            contenido = valor_de_nodo(nodo)
            clase = nodo.get("clase") or i18n.t(f"VIS.forma.{nodo['tipo']}", idioma).lower()
            if contenido is None:
                return i18n.t("VIS.valor.ref", idioma, destino=clase)
            return i18n.t(
                "VIS.valor.ref_nodo", idioma, clase=clase, valor=valor_texto(contenido, idioma)
            )
    return valor_texto(valor, idioma, nombres)


def describir(paso: Mapping[str, Any], idioma: str = "es") -> str:
    """Descripción accesible de un paso: qué se ejecutó, qué cambió y qué hay.

    Orden pensado para lector de pantalla: primero lo nuevo (línea, accesos,
    salida) y después el estado completo (pila de llamadas, variables y
    estructuras), de modo que quien avanza paso a paso oye primero el cambio.
    """
    idioma = i18n.normalizar_idioma(idioma)
    p = normalizar_paso(paso, idioma)
    nombres = nombres_de_nodos(p, idioma)
    frases = [i18n.t("VIS.desc.paso", idioma, n=p["n"], linea=p["linea"])]
    for a in p["accesos"]:
        clave = "VIS.desc.lee" if a["op"] == "lee" else "VIS.desc.escribe"
        valor = valor_texto(_valor_accedido(a, p), idioma, nombres)
        frases.append(
            i18n.t(clave, idioma, destino=destino_acceso(a, nombres, idioma), valor=valor)
        )
    for linea in p["salida_nueva"]:
        frases.append(
            i18n.t("VIS.desc.salida", idioma, texto=json.dumps(linea, ensure_ascii=False))
        )
    marcos = p["marcos"]
    if marcos:
        tope = marcos[-1]
        frases.append(
            i18n.t(
                "VIS.desc.subrutina", idioma, subrutina=tope["subrutina"], profundidad=len(marcos)
            )
        )
        if len(marcos) > 1:
            pila = " → ".join(
                i18n.t("VIS.desc.marco", idioma, subrutina=m["subrutina"], linea=m["linea"])
                for m in marcos
            )
            frases.append(i18n.t("VIS.desc.pila", idioma, marcos=pila))
        raices = {e["raiz"]: e["etiqueta"] for e in p["estructuras"]}
        variables = [
            f"{nombre} = {valor_variable(nombre, var.get('valor'), p, idioma, nombres)}"
            for nombre, var in tope["variables"].items()
            # una variable que sólo nombra a una estructura ya descrita abajo
            # con ese mismo nombre ("a = → a") no aporta nada al oyente
            if not (es_ref(var.get("valor")) and raices.get(int(var["valor"]["id"])) == nombre)
        ]
        if variables:
            frases.append(
                i18n.t(
                    "VIS.desc.variables",
                    idioma,
                    subrutina=tope["subrutina"],
                    lista=unir(variables, idioma),
                )
            )
        elif not tope["variables"]:
            frases.append(i18n.t("VIS.desc.sin_variables", idioma, subrutina=tope["subrutina"]))
    if p["estructuras"]:
        frases.extend(_frase_estructura(e, p, idioma) for e in p["estructuras"])
    else:
        frases.append(i18n.t("VIS.desc.sin_estructuras", idioma))
    return " ".join(frases)


__all__ = [
    "FORMAS",
    "TrazaInvalida",
    "arbol",
    "describir",
    "destino_acceso",
    "estado_accesos",
    "etiqueta_vertice",
    "filas_matriz",
    "grafo",
    "indice_cima",
    "niveles_arbol",
    "nombres_de_nodos",
    "normalizar_paso",
    "normalizar_traza",
    "secuencia",
    "unir",
    "valor_de_nodo",
    "valor_texto",
    "valor_variable",
    "visitado",
]
