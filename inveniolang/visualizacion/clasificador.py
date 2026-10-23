"""Reconocimiento de estructuras de datos vivas a partir del montículo de un paso.

INV-2002: el montículo de la traza solo dice "arreglo", "matriz" u "objeto";
un estudiante quiere ver una PILA, una LISTA ENLAZADA, un ÁRBOL o un GRAFO.
Este módulo deduce la forma con reglas estructurales (qué campos
autorreferentes tiene un objeto, si una matriz es cuadrada) más nombres
significativos, y los nombres se buscan en UNA sola tabla bilingüe
(:data:`SINONIMOS`/:data:`CLASES`): ``siguiente``/``next``,
``izquierdo``/``left``, ``Pila``/``Stack``... Así un programa escrito en
inglés se reconoce igual que su traducción al español.

Reglas (en este orden, cada nodo pertenece a lo sumo a una estructura
compuesta):

* **pila / cola**: objeto cuya clase se llama Pila/Stack o Cola/Queue
  (``PilaEnlazada``, ``ColaCircular``... pero no ``NodoCola``) o arreglo
  guardado en una variable llamada así (``entero [4] pila``). La raíz es el
  contenedor y ``nodos`` lista los elementos del tope/frente al fondo/final.
  En una pila sobre arreglo, ``cima`` es el índice que marca el campo del
  objeto o la variable hermana ``tope``/``top``/``cima`` (o ``tamano``/
  ``size`` - 1); sin ese dato la cima es la última celda.
* **grafo**: clase Grafo/Graph, objeto con campo ``adyacencia``/``adjacency``,
  o matriz cuadrada en una variable ``adj``/``adyacencia``. Con vértices
  objeto (biblioteca estándar: lista de vértices con su lista de aristas),
  ``nodos`` son los vértices y las aristas unen ids del montículo. Si la
  adyacencia es una matriz o un arreglo de listas no hay objetos vértice:
  entonces ``raiz`` es ese arreglo/matriz y los extremos de cada arista son
  ÍNDICES de vértice ``0..n-1`` (documentado en ``docs/visualizacion.md``).
* **árbol binario**: objetos con dos enlaces izquierdo/derecho; se muestra
  desde la raíz real aunque la variable apunte a un subárbol.
* Convención única (INV-2007): ``nodos`` lista SOLO elementos; la raíz es el
  contenedor si existe (y no está en ``nodos``) o el primer nodo si una
  variable apunta directamente a él (y entonces sí está).
* **lista doble / enlazada**: objetos con enlace siguiente (y anterior); se
  muestra desde la cabeza real aunque la variable apunte a la mitad.
* **matriz / arreglo**: el resto de arreglos de variables o campos.
* **objeto**: un objeto de una variable que no forma parte de lo anterior.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence

from .modelo import Estructura, Marco, NodoMonticulo, Valor

__all__ = ["CLASES", "SINONIMOS", "clasificar", "palabras"]

# Única tabla de sinónimos (es/en). Las claves son ROLES; los valores, nombres
# normalizados (minúsculas, sin "_") que cumplen ese rol.
SINONIMOS: dict[str, frozenset[str]] = {
    "siguiente": frozenset(
        {"siguiente", "sig", "sgte", "proximo", "next", "nxt", "abajo", "below"}
    ),
    "anterior": frozenset({"anterior", "ant", "previo", "prev", "previous"}),
    "izquierdo": frozenset(
        {"izq", "izquierdo", "izquierda", "hijoizq", "hijoizquierdo", "left", "leftchild"}
    ),
    "derecho": frozenset(
        {"der", "derecho", "derecha", "hijoder", "hijoderecho", "right", "rightchild"}
    ),
    # Extremo por el que se entra a una secuencia (tope de pila, frente de cola).
    "inicio": frozenset(
        {"cabeza", "primero", "inicio", "tope", "cima", "frente", "raiz"}
        | {"head", "first", "top", "front", "root", "start"}
    ),
    # INV-4401: la traducción al inglés del currículo llama ``queue`` al extremo
    # final de la lista doble (``cola`` → ``queue``); sin estos sinónimos la
    # flecha contenedor → último nodo desaparecía solo en inglés.
    "fin": frozenset(
        {"final", "fin", "cola", "ultimo", "fondo"}
        | {"tail", "rear", "last", "end", "queue", "back", "bottom"}
    ),
    # INV-4400: índice entero de la celda cima de una pila sobre arreglo...
    "indice_tope": frozenset({"tope", "cima", "top", "stacktop", "sp"}),
    # ... o número de elementos guardados (la cima es tamaño - 1).
    # Solo se consulta en campos de un objeto Pila/Stack: como variable suelta,
    # "size" o "cantidad" pueden ser cualquier cosa.
    "tamano": frozenset(
        {"tamano", "tamaño", "cantidad", "numelementos"}
        | {"size", "count", "length", "numelements"}
    ),
    "adyacencia": frozenset(
        {"adyacencia", "ady", "matrizadyacencia", "listaadyacencia"}
        | {"adjacency", "adj", "adjacencymatrix", "adjacencylist"}
    ),
    "aristas": frozenset({"aristas", "adyacentes", "vecinos", "edges", "neighbors", "neighbours"}),
    "destino": frozenset({"destino", "hacia", "vertice", "target", "to", "vertex"}),
    "peso": frozenset({"peso", "costo", "weight", "cost"}),
    "id": frozenset({"id", "numero", "indice", "number", "index"}),
}

# Palabras de un nombre de clase (o de variable) que delatan su papel.
CLASES: dict[str, frozenset[str]] = {
    "pila": frozenset({"pila", "stack"}),
    "cola": frozenset({"cola", "queue"}),
    "grafo": frozenset({"grafo", "graph"}),
    # "NodoCola" o "EdgeNode" son PIEZAS de una estructura, no la estructura.
    "pieza": frozenset({"nodo", "node", "vertice", "vertex", "arista", "edge"}),
}

_PALABRA = re.compile(r"[A-ZÁÉÍÓÚÑ]?[a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]+(?![a-záéíóúñ])|\d+")


def palabras(nombre: str) -> set[str]:
    """Palabras de un identificador CamelCase o snake_case, en minúsculas."""
    return {p.lower() for p in _PALABRA.findall(nombre)}


def _norm(nombre: str) -> str:
    return nombre.lower().replace("_", "")


def _rol(campo: str, rol: str) -> bool:
    return _norm(campo) in SINONIMOS[rol]


def _clase_es(clase: str | None, papel: str) -> bool:
    if not clase:
        return False
    p = palabras(clase)
    return bool(p & CLASES[papel]) and not p & CLASES["pieza"]


def _es_enlace(valor: Valor) -> bool:
    """Un campo puede ser enlace si apunta a un nodo o está a nulo."""
    return valor.es_ref or (valor.tipo == "null")


class _Clasificador:
    def __init__(self, monticulo: Mapping[int, NodoMonticulo]):
        self.m = monticulo
        # Enteros visibles desde la variable que se está visitando (su marco y
        # el global): una pila sobre arreglo suele llevar su `tope` al lado.
        self.enteros_visibles: dict[str, int] = {}
        self.estructuras: list[Estructura] = []
        self.consumidos: set[int] = set()  # nodos ya dentro de una estructura compuesta
        self.emitidos: set[tuple[str, int]] = set()
        self.nombre_de: dict[int, str] = {}
        self._padres: dict[str, dict[int, int]] = {}

    # ---------------------------------------------------------------- utilidades

    def _emitir(
        self,
        forma: str,
        raiz: int,
        etiqueta: str,
        nodos: Sequence[int],
        aristas: Sequence[tuple[int, int, str]] = (),
        cima: int | None = None,
    ) -> None:
        if (forma, raiz) in self.emitidos:
            return
        self.emitidos.add((forma, raiz))
        self.estructuras.append(
            Estructura(forma, raiz, etiqueta, tuple(nodos), tuple(aristas), cima)
        )

    @staticmethod
    def _enteros(valores: Mapping[str, Valor]) -> dict[str, int]:
        """Escalares enteros de un objeto o de un marco, por nombre."""
        return {
            k: v.v
            for k, v in valores.items()
            if v.tipo == "int" and isinstance(v.v, int) and not isinstance(v.v, bool)
        }

    @staticmethod
    def _cima(
        forma: str, arreglo: NodoMonticulo, enteros: Mapping[str, int], con_tamano: bool
    ) -> int | None:
        """Índice de la cima de una pila sobre ``arreglo`` (INV-4400).

        Busca primero un índice explícito (``tope``/``top``/``cima``) y, en
        los campos de un objeto pila (``con_tamano``), un tamaño
        (``tamano``/``size``: la cima es tamaño - 1). Se acota a ``-1..len-1``
        para que un tope corrupto no rompa el dibujo.
        """
        if forma != "pila":
            return None
        cima = None
        roles = (("indice_tope", 0), ("tamano", -1)) if con_tamano else (("indice_tope", 0),)
        for rol, ajuste in roles:
            cima = next((v + ajuste for k, v in enteros.items() if _rol(k, rol)), None)
            if cima is not None:
                break
        if cima is None:
            return None
        return max(-1, min(cima, len(arreglo.elementos) - 1))

    def _objeto(self, nid: int | None) -> NodoMonticulo | None:
        nodo = self.m.get(nid) if nid is not None else None
        return nodo if nodo is not None and nodo.tipo == "objeto" else None

    def _campo_rol(self, nodo: NodoMonticulo, rol: str) -> tuple[str, Valor] | None:
        for campo, valor in nodo.campos.items():
            if _rol(campo, rol) and _es_enlace(valor):
                return campo, valor
        return None

    def _entero_rol(self, nodo: NodoMonticulo, rol: str) -> int | None:
        for campo, valor in nodo.campos.items():
            if _rol(campo, rol) and valor.tipo == "int" and isinstance(valor.v, int):
                return valor.v
        return None

    def _cadena(self, inicio: int | None, rol: str = "siguiente") -> Iterator[tuple[int, str]]:
        """Recorre los nodos enlazados por ``rol`` desde ``inicio`` (sin ciclos)."""
        vistos: set[int] = set()
        actual = inicio
        while actual is not None and actual not in vistos:
            nodo = self._objeto(actual)
            if nodo is None:
                return
            vistos.add(actual)
            enlace = self._campo_rol(nodo, rol)
            yield actual, (enlace[0] if enlace else "")
            actual = enlace[1].id if enlace and enlace[1].es_ref else None

    def _padres_por(self, roles: tuple[str, ...]) -> dict[int, int]:
        """Mapa hijo -> padre del montículo por los campos de ``roles`` (perezoso)."""
        clave = ",".join(roles)
        if clave not in self._padres:
            padres: dict[int, int] = {}
            for nid, nodo in self.m.items():
                if nodo.tipo != "objeto":
                    continue
                for rol in roles:
                    enlace = self._campo_rol(nodo, rol)
                    if enlace and enlace[1].es_ref and enlace[1].id != nid:
                        padres.setdefault(int(enlace[1].id or 0), nid)
            self._padres[clave] = padres
        return self._padres[clave]

    def _subir(self, nid: int, roles: tuple[str, ...]) -> int:
        """Primer antecesor sin padre (la cabeza/raíz real); a salvo de ciclos."""
        padres = self._padres_por(roles)
        vistos = {nid}
        while nid in padres and padres[nid] not in vistos:
            nid = padres[nid]
            vistos.add(nid)
        return nid

    # ---------------------------------------------------------------- formas

    def _es_arbol(self, nodo: NodoMonticulo) -> bool:
        return bool(self._campo_rol(nodo, "izquierdo") and self._campo_rol(nodo, "derecho"))

    def _es_lista(self, nodo: NodoMonticulo) -> bool:
        return self._campo_rol(nodo, "siguiente") is not None

    def _con_contenedor(
        self,
        forma: str,
        primero: int,
        etiqueta: str,
        nodos: list[int],
        aristas: list[tuple[int, int, str]],
        contenedor: tuple[int, str] | None,
    ) -> None:
        """Emite la estructura con el contenedor como raíz (si lo hay).

        INV-2007 (contrato unificado con VISTA): ``nodos`` lista SOLO los
        elementos; la raíz es el contenedor cuando existe (no es un elemento,
        no está en ``nodos``) y, si una variable apunta directamente a los
        nodos, la raíz es el primer elemento (y sí está en ``nodos``).
        """
        if contenedor is None:
            self._emitir(forma, primero, self.nombre_de.get(primero, etiqueta), nodos, aristas)
            return
        cid, campo = contenedor
        extra = [(cid, primero, campo)]
        dueno = self._objeto(cid)
        fin = self._campo_rol(dueno, "fin") if dueno else None
        if fin and fin[1].es_ref and fin[1].id in nodos and fin[1].id != primero:
            extra.append((cid, int(fin[1].id or 0), fin[0]))
        self.consumidos.add(cid)
        self._emitir(forma, cid, etiqueta, nodos, extra + aristas)

    def _arbol(self, nid: int, etiqueta: str, contenedor: tuple[int, str] | None = None) -> None:
        raiz = self._subir(nid, ("izquierdo", "derecho"))
        nodos: list[int] = []
        vistos: set[int] = set()
        aristas: list[tuple[int, int, str]] = []
        pendientes = [raiz]
        while pendientes:
            actual = pendientes.pop()
            nodo = self._objeto(actual)
            if nodo is None or actual in vistos:
                continue
            vistos.add(actual)
            nodos.append(actual)
            hijos = []
            for rol in ("izquierdo", "derecho"):
                enlace = self._campo_rol(nodo, rol)
                if enlace and enlace[1].es_ref and enlace[1].id is not None:
                    aristas.append((actual, enlace[1].id, enlace[0]))
                    hijos.append(enlace[1].id)
            pendientes.extend(reversed(hijos))  # preorden: izquierdo antes que derecho
        self.consumidos.update(nodos)
        self._con_contenedor("arbol_binario", raiz, etiqueta, nodos, aristas, contenedor)

    def _lista(self, nid: int, etiqueta: str, contenedor: tuple[int, str] | None = None) -> None:
        cabeza = self._subir(nid, ("siguiente",))
        cadena = list(self._cadena(cabeza))
        nodos = [n for n, _ in cadena]
        aristas = [(a, b, campo) for (a, campo), (b, _) in zip(cadena, cadena[1:], strict=False)]
        primero = self._objeto(cabeza)
        doble = primero is not None and self._campo_rol(primero, "anterior") is not None
        if doble:
            for n in nodos:
                nodo = self._objeto(n)
                enlace = self._campo_rol(nodo, "anterior") if nodo else None
                if enlace and enlace[1].es_ref and enlace[1].id is not None:
                    aristas.append((n, enlace[1].id, enlace[0]))
        self.consumidos.update(nodos)
        forma = "lista_doble" if doble else "lista_enlazada"
        self._con_contenedor(forma, cabeza, etiqueta, nodos, aristas, contenedor)

    def _contenedor_lineal(self, forma: str, nid: int, nodo: NodoMonticulo, etiqueta: str) -> None:
        """Pila o cola: elementos del tope/frente al fondo/final; la raíz es el contenedor."""
        nodos: list[int] = []
        aristas: list[tuple[int, int, str]] = []
        inicio = self._campo_rol(nodo, "inicio")
        if inicio and inicio[1].es_ref and inicio[1].id is not None:
            cadena = list(self._cadena(inicio[1].id))
            nodos.extend(n for n, _ in cadena if n not in nodos and n != nid)
            aristas.append((nid, inicio[1].id, inicio[0]))
            aristas.extend((a, b, c) for (a, c), (b, _) in zip(cadena, cadena[1:], strict=False))
            fin = self._campo_rol(nodo, "fin")
            if fin and fin[1].es_ref and fin[1].id is not None:
                aristas.append((nid, fin[1].id, fin[0]))
        elif inicio is None:
            # Pila/cola sobre un arreglo (campo datos/data/...): la raíz es el
            # arreglo y sus celdas son los elementos (INV-2007).
            for valor in nodo.campos.values():
                destino = self.m.get(valor.id) if valor.es_ref and valor.id else None
                if destino is not None and destino.tipo == "arreglo":
                    self.consumidos.update((nid, destino.id))
                    cima = self._cima(forma, destino, self._enteros(nodo.campos), True)
                    self._emitir(forma, destino.id, etiqueta, [], cima=cima)
                    return
        self.consumidos.add(nid)
        self.consumidos.update(nodos)
        self._emitir(forma, nid, etiqueta, nodos, aristas)

    def _grafo_indices(self, nid: int, etiqueta: str, extra: Sequence[int] = ()) -> bool:
        """Grafo cuya adyacencia es una matriz o un arreglo de listas (vértices = índices)."""
        nodo = self.m.get(nid)
        if nodo is None:
            return False
        aristas: list[tuple[int, int, str]] = []
        if nodo.tipo == "matriz":
            filas = nodo.elementos
            if not filas or any(len(f) != len(filas) for f in filas):
                return False
            for i, fila in enumerate(filas):
                for j, celda in enumerate(fila):
                    if celda.es_ref or celda.v in (None, 0, 0.0, False, ""):
                        continue
                    peso = "" if celda.v is True or celda.v == 1 else str(celda.v)
                    aristas.append((i, j, peso))
        elif nodo.tipo == "arreglo":
            consumidos: list[int] = []
            for i, celda in enumerate(nodo.elementos):
                if not celda.es_ref:
                    continue
                for n, _ in self._cadena(celda.id):
                    vecino = self._objeto(n)
                    destino = self._entero_rol(vecino, "destino") if vecino else None
                    if destino is None:
                        return False
                    costo = self._entero_rol(vecino, "peso") if vecino else None
                    aristas.append((i, destino, "" if costo is None else str(costo)))
                    consumidos.append(n)
            self.consumidos.update(consumidos)
        else:
            return False
        self.consumidos.add(nid)
        self.consumidos.update(extra)
        # Sin objetos vértice: `nodos` vacío y extremos = índices (INV-2007).
        self._emitir("grafo", nid, etiqueta, [], aristas)
        return True

    def _grafo_objeto(self, nid: int, nodo: NodoMonticulo, etiqueta: str) -> bool:
        """Grafo con vértices objeto (lista de vértices, cada uno con su lista de aristas)."""
        ady = self._campo_rol(nodo, "adyacencia")
        if ady is not None and ady[1].es_ref and ady[1].id is not None:
            return self._grafo_indices(ady[1].id, etiqueta, extra=(nid,))
        inicio = self._campo_rol(nodo, "inicio")
        if inicio is None or not inicio[1].es_ref:
            if _clase_es(nodo.clase, "grafo"):
                self.consumidos.add(nid)
                self._emitir("grafo", nid, etiqueta, [])  # grafo aún sin vértices
                return True
            return False
        vertices = [n for n, _ in self._cadena(inicio[1].id)]
        por_numero: dict[int, int] = {}
        for pos, v in enumerate(vertices):
            vnodo = self._objeto(v)
            numero = self._entero_rol(vnodo, "id") if vnodo else None
            por_numero[pos if numero is None else numero] = v
        aristas: list[tuple[int, int, str]] = []
        piezas: list[int] = []
        for v in vertices:
            vnodo = self._objeto(v)
            lista = self._campo_rol(vnodo, "aristas") if vnodo else None
            if lista is None or not lista[1].es_ref:
                continue
            for a, _ in self._cadena(lista[1].id):
                anodo = self._objeto(a)
                destino = self._entero_rol(anodo, "destino") if anodo else None
                if destino is None or destino not in por_numero:
                    continue
                peso = self._entero_rol(anodo, "peso") if anodo else None
                aristas.append((v, por_numero[destino], "" if peso is None else str(peso)))
                piezas.append(a)
        self.consumidos.update(vertices)
        self.consumidos.update(piezas)
        self.consumidos.add(nid)
        self._emitir("grafo", nid, etiqueta, vertices, aristas)
        return True

    # ---------------------------------------------------------------- recorrido

    def visitar(self, etiqueta: str, nid: int) -> None:
        """Clasifica lo que cuelga de una variable llamada ``etiqueta``."""
        nodo = self.m.get(nid)
        if nodo is None:
            return
        if nodo.tipo == "objeto":
            self._visitar_objeto(etiqueta, nid, nodo, permitir_objeto=True)
        else:
            self._visitar_arreglo(etiqueta, nid, nodo)

    def _visitar_arreglo(self, etiqueta: str, nid: int, nodo: NodoMonticulo) -> None:
        if nid in self.consumidos:
            return
        nombre = palabras(etiqueta.rsplit(".", 1)[-1])
        if nodo.tipo == "matriz":
            self._emitir("matriz", nid, etiqueta, [nid])
            if nombre & SINONIMOS["adyacencia"]:
                self._grafo_indices(nid, etiqueta)
            return
        if nombre & SINONIMOS["adyacencia"] and self._grafo_indices(nid, etiqueta):
            return
        forma = "arreglo"
        if nombre & CLASES["pila"]:
            forma = "pila"
        elif nombre & CLASES["cola"]:
            forma = "cola"
        # En una pila/cola sobre arreglo los elementos son las celdas: `nodos` vacío.
        # Solo una variable (no un campo `obj.pila`) tiene hermanas en el marco.
        hermanas = self.enteros_visibles if "." not in etiqueta else {}
        cima = self._cima(forma, nodo, hermanas, False)
        self._emitir(forma, nid, etiqueta, [nid] if forma == "arreglo" else [], cima=cima)
        for i, celda in enumerate(nodo.elementos):
            if celda.es_ref and celda.id is not None:
                hijo = self._objeto(celda.id)
                if hijo is not None:
                    self._visitar_objeto(f"{etiqueta}[{i}]", celda.id, hijo, permitir_objeto=False)

    def _visitar_objeto(
        self, etiqueta: str, nid: int, nodo: NodoMonticulo, permitir_objeto: bool
    ) -> None:
        if nid in self.consumidos:
            return
        if _clase_es(nodo.clase, "pila"):
            self._contenedor_lineal("pila", nid, nodo, etiqueta)
            return
        if _clase_es(nodo.clase, "cola"):
            self._contenedor_lineal("cola", nid, nodo, etiqueta)
            return
        if (
            _clase_es(nodo.clase, "grafo") or self._campo_rol(nodo, "adyacencia")
        ) and self._grafo_objeto(nid, nodo, etiqueta):
            return
        if self._es_arbol(nodo):
            self._arbol(nid, etiqueta)
            return
        if self._es_lista(nodo):
            self._lista(nid, etiqueta)
            return
        # Contenedor (ListaSimple, ArbolBB, Vector...): se muestra lo que guarda.
        contenido = False
        for campo, valor in nodo.campos.items():
            if not valor.es_ref or valor.id is None or valor.id in self.consumidos:
                continue
            destino = self.m.get(valor.id)
            if destino is None:
                continue
            sub = f"{etiqueta}.{campo}"
            if destino.tipo != "objeto":
                self._visitar_arreglo(sub, valor.id, destino)
                contenido = True
            elif self._es_arbol(destino) or self._es_lista(destino):
                # La primera lista/árbol que guarda el contenedor lo usa como
                # raíz (etiqueta = la variable); las siguientes van aparte.
                propia = None if nid in self.consumidos else (nid, campo)
                recorrer = self._arbol if self._es_arbol(destino) else self._lista
                recorrer(valor.id, etiqueta if propia else sub, propia)
                contenido = True
        if not contenido and permitir_objeto:
            self._emitir("objeto", nid, etiqueta, [nid])


def clasificar(
    marcos: Sequence[Marco], monticulo: Mapping[int, NodoMonticulo]
) -> tuple[Estructura, ...]:
    """Estructuras vivas del paso, en orden de aparición (marco base → tope).

    Determinista: el mismo montículo y los mismos marcos producen la misma
    lista. Cada estructura compuesta aparece una sola vez aunque varias
    variables apunten a ella; se etiqueta con la variable que apunta a su
    cabeza/raíz si existe.
    """
    c = _Clasificador(monticulo)
    raices: list[tuple[str, int, dict[str, int]]] = []
    globales = c._enteros({k: v.valor for k, v in marcos[0].variables.items()}) if marcos else {}
    for marco in marcos:
        enteros = {**globales, **c._enteros({k: v.valor for k, v in marco.variables.items()})}
        for nombre, variable in marco.variables.items():
            valor = variable.valor
            if valor.es_ref and valor.id is not None and valor.id in monticulo:
                raices.append((nombre, valor.id, enteros))
                c.nombre_de.setdefault(valor.id, nombre)
    for nombre, nid, enteros in raices:
        c.enteros_visibles = enteros
        c.visitar(nombre, nid)
    return tuple(c.estructuras)
