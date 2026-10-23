"""Modelo de datos de la traza paso a paso (contrato JSON compartido, versión 1).

INV-2001: el trazador (equipo TRAZA) y los renderizadores de texto, SVG, HTML
y la GUI (equipo VISTA) se escriben en paralelo. Para que ninguno dependa de
los objetos internos del intérprete, ambos hablan este único formato: valores
inmutables (``dataclass(frozen=True)``, secuencias como tuplas) que se
convierten a ``dict``/JSON y vuelven **exactamente** iguales
(``desde_json(a_json(t)) == t``).

Forma JSON (ver ``docs/visualizacion.md``):

* ``Valor``: ``{"t":"escalar","tipo":str,"v":int|float|str|bool|None}`` o
  ``{"t":"ref","id":int}`` (referencia a un nodo del montículo).
* ``NodoMonticulo``: ``{"id","tipo":"arreglo"|"matriz"|"objeto","clase",
  "elementos","campos"}``; en una matriz ``elementos`` es una lista de filas.
* ``Acceso``: ``{"op":"lee"|"escribe","var","nodo","indices","campo"}``.
* ``Marco``: ``{"subrutina","linea","variables":{nombre:{"tipo","valor"}}}``.
* ``Paso``: ``{"n","linea","columna","marcos","monticulo":{id:nodo},
  "accesos","salida_nueva","estructuras"}``.
* ``Estructura``: ``{"forma","raiz","etiqueta","nodos","aristas":[[a,b,etq]]}``
  y, opcional, ``"cima"`` (índice de la cima de una pila sobre arreglo).
* ``Traza``: ``{"version":1,"idioma","fuente","pasos","truncada","error","salida"}``.

JSON solo admite claves de texto: los ids del montículo viajan como
``"3"`` y ``desde_json`` los devuelve a ``int``. Los reales no finitos
(``inf``/``nan``) no existen en JSON estándar; el trazador ya los guarda como
texto (``"inf"``) con ``tipo`` ``"float"``, así que nunca llegan aquí.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "VERSION",
    "FORMAS",
    "Acceso",
    "Estructura",
    "Marco",
    "NodoMonticulo",
    "Paso",
    "Traza",
    "Valor",
    "VariableMarco",
    "a_dict",
    "a_json",
    "desde_dict",
    "desde_json",
]

VERSION = 1

Escalar = int | float | str | bool | None

TIPOS_NODO = ("arreglo", "matriz", "objeto")
OPERACIONES = ("lee", "escribe")
FORMAS = (
    "arreglo",
    "matriz",
    "pila",
    "cola",
    "lista_enlazada",
    "lista_doble",
    "arbol_binario",
    "grafo",
    "objeto",
)
IDIOMAS_TRAZA = ("es", "en")


class _ErrorContrato(ValueError):
    """JSON que no cumple el contrato de la traza (mensaje con la ruta del dato)."""


def _exigir(condicion: bool, ruta: str, detalle: str) -> None:
    if not condicion:
        raise _ErrorContrato(f"traza inválida en {ruta}: {detalle}")


def _entero(dato: Any, ruta: str) -> int:
    _exigir(isinstance(dato, int) and not isinstance(dato, bool), ruta, "se esperaba un entero")
    return int(dato)


def _texto(dato: Any, ruta: str) -> str:
    _exigir(isinstance(dato, str), ruta, "se esperaba texto")
    return str(dato)


def _texto_o_nulo(dato: Any, ruta: str) -> str | None:
    return None if dato is None else _texto(dato, ruta)


def _entero_o_nulo(dato: Any, ruta: str) -> int | None:
    return None if dato is None else _entero(dato, ruta)


def _lista(dato: Any, ruta: str) -> list[Any]:
    _exigir(isinstance(dato, list), ruta, "se esperaba una lista")
    return list(dato)


def _objeto(dato: Any, ruta: str, claves: tuple[str, ...]) -> Mapping[str, Any]:
    _exigir(isinstance(dato, dict), ruta, "se esperaba un objeto")
    faltan = [c for c in claves if c not in dato]
    _exigir(not faltan, ruta, f"faltan las claves {faltan}")
    return dict(dato)


@dataclass(frozen=True)
class Valor:
    """Un valor del programa: escalar (``t="escalar"``) o referencia (``t="ref"``)."""

    t: str
    tipo: str | None = None
    v: Escalar = None
    id: int | None = None

    @classmethod
    def escalar(cls, tipo: str, v: Escalar) -> Valor:
        """Valor escalar con el tipo del lenguaje (``int``, ``float``, ``string``...)."""
        return cls("escalar", tipo, v, None)

    @classmethod
    def ref(cls, id_nodo: int) -> Valor:
        """Referencia al nodo ``id_nodo`` del montículo."""
        return cls("ref", None, None, id_nodo)

    @property
    def es_ref(self) -> bool:
        """True si apunta a un nodo del montículo."""
        return self.t == "ref"

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        if self.t == "ref":
            return {"t": "ref", "id": self.id}
        return {"t": "escalar", "tipo": self.tipo, "v": self.v}

    @classmethod
    def desde_dict(cls, d: Any, ruta: str = "valor") -> Valor:
        """Reconstruye un valor validando el contrato."""
        _exigir(isinstance(d, dict) and "t" in d, ruta, "se esperaba un valor con 't'")
        if d["t"] == "ref":
            return cls.ref(_entero(d.get("id"), ruta + ".id"))
        _exigir(d["t"] == "escalar", ruta, f"'t' desconocido {d['t']!r}")
        datos = _objeto(d, ruta, ("tipo", "v"))
        v = datos["v"]
        _exigir(
            v is None or isinstance(v, (bool, int, float, str)), ruta + ".v", "escalar inválido"
        )
        return cls.escalar(_texto(datos["tipo"], ruta + ".tipo"), v)


@dataclass(frozen=True)
class NodoMonticulo:
    """Arreglo, matriz u objeto vivo; ``id`` es estable durante toda la traza."""

    id: int
    tipo: str
    clase: str | None = None
    elementos: tuple[Any, ...] = ()
    campos: dict[str, Valor] = field(default_factory=dict)

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato (matriz: ``elementos`` es lista de filas)."""
        if self.tipo == "matriz":
            elementos: list[Any] = [[v.a_dict() for v in fila] for fila in self.elementos]
        else:
            elementos = [v.a_dict() for v in self.elementos]
        return {
            "id": self.id,
            "tipo": self.tipo,
            "clase": self.clase,
            "elementos": elementos,
            "campos": {k: v.a_dict() for k, v in self.campos.items()},
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str = "nodo") -> NodoMonticulo:
        """Reconstruye un nodo validando el contrato."""
        datos = _objeto(d, ruta, ("id", "tipo", "clase", "elementos", "campos"))
        tipo = _texto(datos["tipo"], ruta + ".tipo")
        _exigir(tipo in TIPOS_NODO, ruta + ".tipo", f"tipo de nodo desconocido {tipo!r}")
        crudos = _lista(datos["elementos"], ruta + ".elementos")
        elementos: tuple[Any, ...]
        if tipo == "matriz":
            elementos = tuple(
                tuple(
                    Valor.desde_dict(v, f"{ruta}.elementos[{i}][{j}]")
                    for j, v in enumerate(_lista(fila, f"{ruta}.elementos[{i}]"))
                )
                for i, fila in enumerate(crudos)
            )
        else:
            elementos = tuple(
                Valor.desde_dict(v, f"{ruta}.elementos[{i}]") for i, v in enumerate(crudos)
            )
        campos_crudos = _objeto(datos["campos"], ruta + ".campos", ())
        return cls(
            _entero(datos["id"], ruta + ".id"),
            tipo,
            _texto_o_nulo(datos["clase"], ruta + ".clase"),
            elementos,
            {
                _texto(k, ruta + ".campos"): Valor.desde_dict(v, f"{ruta}.campos.{k}")
                for k, v in campos_crudos.items()
            },
        )


@dataclass(frozen=True)
class Acceso:
    """Lectura o escritura de una variable, una celda (``indices``) o un ``campo``."""

    op: str
    var: str | None = None
    nodo: int | None = None
    indices: tuple[int, ...] = ()
    campo: str | None = None

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "op": self.op,
            "var": self.var,
            "nodo": self.nodo,
            "indices": list(self.indices),
            "campo": self.campo,
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str = "acceso") -> Acceso:
        """Reconstruye un acceso validando el contrato."""
        datos = _objeto(d, ruta, ("op", "var", "nodo", "indices", "campo"))
        op = _texto(datos["op"], ruta + ".op")
        _exigir(op in OPERACIONES, ruta + ".op", f"operación desconocida {op!r}")
        return cls(
            op,
            _texto_o_nulo(datos["var"], ruta + ".var"),
            _entero_o_nulo(datos["nodo"], ruta + ".nodo"),
            tuple(
                _entero(i, f"{ruta}.indices") for i in _lista(datos["indices"], ruta + ".indices")
            ),
            _texto_o_nulo(datos["campo"], ruta + ".campo"),
        )


@dataclass(frozen=True)
class VariableMarco:
    """Tipo declarado (o deducido) y valor de una variable de un marco."""

    tipo: str
    valor: Valor

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {"tipo": self.tipo, "valor": self.valor.a_dict()}

    @classmethod
    def desde_dict(cls, d: Any, ruta: str = "variable") -> VariableMarco:
        """Reconstruye una variable validando el contrato."""
        datos = _objeto(d, ruta, ("tipo", "valor"))
        return cls(_texto(datos["tipo"], ruta + ".tipo"), Valor.desde_dict(datos["valor"], ruta))


@dataclass(frozen=True)
class Marco:
    """Activación de una subrutina (o el ámbito global) con sus variables visibles."""

    subrutina: str
    linea: int
    variables: dict[str, VariableMarco] = field(default_factory=dict)

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "subrutina": self.subrutina,
            "linea": self.linea,
            "variables": {k: v.a_dict() for k, v in self.variables.items()},
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str = "marco") -> Marco:
        """Reconstruye un marco validando el contrato."""
        datos = _objeto(d, ruta, ("subrutina", "linea", "variables"))
        variables = _objeto(datos["variables"], ruta + ".variables", ())
        return cls(
            _texto(datos["subrutina"], ruta + ".subrutina"),
            _entero(datos["linea"], ruta + ".linea"),
            {
                _texto(k, ruta + ".variables"): VariableMarco.desde_dict(v, f"{ruta}.{k}")
                for k, v in variables.items()
            },
        )


@dataclass(frozen=True)
class Estructura:
    """Estructura de datos reconocida en el montículo (ver ``clasificador.py``)."""

    forma: str
    raiz: int
    etiqueta: str
    nodos: tuple[int, ...] = ()
    aristas: tuple[tuple[int, int, str], ...] = ()
    # INV-4400: en una pila sobre arreglo la cima NO es la última celda del
    # arreglo (ahí suele haber basura o ceros), sino la que marca el campo o la
    # variable tope/top/cima (o tamaño - 1). ``cima`` guarda ese índice (-1 =
    # pila vacía); ``None`` si el programa no lo marca. Clave opcional del
    # JSON: las trazas anteriores siguen siendo válidas.
    cima: int | None = None

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato (``cima`` solo si se conoce)."""
        d: dict[str, Any] = {
            "forma": self.forma,
            "raiz": self.raiz,
            "etiqueta": self.etiqueta,
            "nodos": list(self.nodos),
            "aristas": [[a, b, e] for a, b, e in self.aristas],
        }
        if self.cima is not None:
            d["cima"] = self.cima
        return d

    @classmethod
    def desde_dict(cls, d: Any, ruta: str = "estructura") -> Estructura:
        """Reconstruye una estructura validando el contrato."""
        datos = _objeto(d, ruta, ("forma", "raiz", "etiqueta", "nodos", "aristas"))
        forma = _texto(datos["forma"], ruta + ".forma")
        _exigir(forma in FORMAS, ruta + ".forma", f"forma desconocida {forma!r}")
        aristas = []
        for i, a in enumerate(_lista(datos["aristas"], ruta + ".aristas")):
            r = f"{ruta}.aristas[{i}]"
            _exigir(
                isinstance(a, list) and len(a) == 3, r, "se esperaba [origen, destino, etiqueta]"
            )
            aristas.append((_entero(a[0], r), _entero(a[1], r), _texto(a[2], r)))
        return cls(
            forma,
            _entero(datos["raiz"], ruta + ".raiz"),
            _texto(datos["etiqueta"], ruta + ".etiqueta"),
            tuple(_entero(n, ruta + ".nodos") for n in _lista(datos["nodos"], ruta + ".nodos")),
            tuple(aristas),
            _entero_o_nulo(datos.get("cima"), ruta + ".cima"),
        )


@dataclass(frozen=True)
class Paso:
    """Estado DESPUÉS de ejecutar la instrucción de ``linea`` y lo que ella hizo."""

    n: int
    linea: int
    columna: int
    marcos: tuple[Marco, ...] = ()
    monticulo: dict[int, NodoMonticulo] = field(default_factory=dict)
    accesos: tuple[Acceso, ...] = ()
    salida_nueva: tuple[str, ...] = ()
    estructuras: tuple[Estructura, ...] = ()

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato (claves del montículo como texto)."""
        return {
            "n": self.n,
            "linea": self.linea,
            "columna": self.columna,
            "marcos": [m.a_dict() for m in self.marcos],
            "monticulo": {str(k): v.a_dict() for k, v in self.monticulo.items()},
            "accesos": [a.a_dict() for a in self.accesos],
            "salida_nueva": list(self.salida_nueva),
            "estructuras": [e.a_dict() for e in self.estructuras],
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str = "paso") -> Paso:
        """Reconstruye un paso validando el contrato."""
        claves = ("n", "linea", "columna", "marcos", "monticulo", "accesos")
        datos = _objeto(d, ruta, claves + ("salida_nueva", "estructuras"))
        monticulo: dict[int, NodoMonticulo] = {}
        for k, v in _objeto(datos["monticulo"], ruta + ".monticulo", ()).items():
            _exigir(str(k).isdigit(), ruta + ".monticulo", f"id no numérico {k!r}")
            nodo = NodoMonticulo.desde_dict(v, f"{ruta}.monticulo.{k}")
            _exigir(nodo.id == int(k), f"{ruta}.monticulo.{k}", "el id no coincide con su clave")
            monticulo[int(k)] = nodo
        return cls(
            _entero(datos["n"], ruta + ".n"),
            _entero(datos["linea"], ruta + ".linea"),
            _entero(datos["columna"], ruta + ".columna"),
            tuple(
                Marco.desde_dict(m, f"{ruta}.marcos[{i}]")
                for i, m in enumerate(_lista(datos["marcos"], ruta + ".marcos"))
            ),
            monticulo,
            tuple(
                Acceso.desde_dict(a, f"{ruta}.accesos[{i}]")
                for i, a in enumerate(_lista(datos["accesos"], ruta + ".accesos"))
            ),
            tuple(
                _texto(s, ruta + ".salida_nueva")
                for s in _lista(datos["salida_nueva"], ruta + ".salida_nueva")
            ),
            tuple(
                Estructura.desde_dict(e, f"{ruta}.estructuras[{i}]")
                for i, e in enumerate(_lista(datos["estructuras"], ruta + ".estructuras"))
            ),
        )


@dataclass(frozen=True)
class Traza:
    """Traza completa de una ejecución (o parcial: ``truncada``/``error``)."""

    idioma: str
    fuente: str
    pasos: tuple[Paso, ...] = ()
    truncada: bool = False
    error: str | None = None
    salida: tuple[str, ...] = ()
    version: int = VERSION

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "version": self.version,
            "idioma": self.idioma,
            "fuente": self.fuente,
            "pasos": [p.a_dict() for p in self.pasos],
            "truncada": self.truncada,
            "error": self.error,
            "salida": list(self.salida),
        }

    @classmethod
    def desde_dict(cls, d: Any) -> Traza:
        """Reconstruye una traza validando el contrato y su versión."""
        claves = ("version", "idioma", "fuente", "pasos", "truncada", "error", "salida")
        datos = _objeto(d, "traza", claves)
        version = _entero(datos["version"], "traza.version")
        _exigir(version == VERSION, "traza.version", f"versión {version} no soportada")
        idioma = _texto(datos["idioma"], "traza.idioma")
        _exigir(idioma in IDIOMAS_TRAZA, "traza.idioma", f"idioma desconocido {idioma!r}")
        _exigir(isinstance(datos["truncada"], bool), "traza.truncada", "se esperaba un lógico")
        return cls(
            idioma,
            _texto(datos["fuente"], "traza.fuente"),
            tuple(
                Paso.desde_dict(p, f"traza.pasos[{i}]")
                for i, p in enumerate(_lista(datos["pasos"], "traza.pasos"))
            ),
            bool(datos["truncada"]),
            _texto_o_nulo(datos["error"], "traza.error"),
            tuple(_texto(s, "traza.salida") for s in _lista(datos["salida"], "traza.salida")),
            version,
        )


def a_dict(traza: Traza) -> dict[str, Any]:
    """La traza como ``dict`` del contrato (lo que consumen los renderizadores)."""
    return traza.a_dict()


def desde_dict(datos: Mapping[str, Any]) -> Traza:
    """Traza a partir de un ``dict`` del contrato; ``ValueError`` si no lo cumple."""
    return Traza.desde_dict(dict(datos))


def a_json(traza: Traza, indent: int | None = None) -> str:
    """Serializa la traza a JSON (UTF-8 sin escapar; ``allow_nan=False``)."""
    return json.dumps(traza.a_dict(), ensure_ascii=False, indent=indent, allow_nan=False)


def desde_json(texto: str) -> Traza:
    """Traza a partir de su JSON; ``ValueError`` si el texto no cumple el contrato."""
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise _ErrorContrato(f"JSON inválido: {e}") from e
    return desde_dict(datos)
