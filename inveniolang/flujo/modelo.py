"""Modelo del diagrama de flujo estructurado (contrato JSON, versión 1).

INV-3000: antes el diagrama solo existía como cajas ya dibujadas
(``flowchart.py``) o como un ``Bloque`` del AST mutado a mano
(``flowchart_builder.py``); ninguno se podía guardar, intercambiar con la web
ni convertir de vuelta en el programa completo. Este módulo define el
**único** formato que comparten la extracción (código → diagrama), la
generación (diagrama → código), los renderizadores (SVG, Mermaid, texto), la
edición estructurada, la API, la CLI y la GUI.

Decisiones:

* El diagrama es un **árbol estructurado**, no un grafo libre: cada nodo
  compuesto (``si``, ``mientras``…) contiene sus secuencias. Así nunca se
  puede representar un salto arbitrario (InvenioLang no tiene ``goto``) y la
  vuelta a código es directa y exacta. El grafo con flechas y conectores se
  *deriva* (``esquema.py``) para dibujarlo.
* Un ``ModeloFlujo`` describe el **programa completo**: un diagrama por
  subrutina, ``main``, método y constructor, más los elementos que no son
  flujo (importaciones, enumeraciones, atributos, globales, cabeceras de
  clase) como texto. Por eso ``código → modelo → código`` reproduce el mismo
  programa.
* Los textos de las cajas son fragmentos InvenioLang en el idioma del modelo
  (``idioma``), sin el ``;`` final.
* Ida y vuelta exacta del JSON: ``desde_json(a_json(m)) == m``.

Forma JSON (detalle en ``docs/diagramas_de_flujo.md``)::

    {"formato": "inveniolang-flujo", "version": 1, "idioma": "es",
     "elementos": [{"tipo": "codigo", "texto": "..."} |
                   {"tipo": "subrutina", "diagrama": DIAGRAMA} |
                   {"tipo": "clase", "cabecera": "...", "miembros": [...]}]}
    DIAGRAMA = {"clave", "nombre", "tipo", "clase", "firma", "linea", "cuerpo": [NODO]}
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from .. import i18n

__all__ = [
    "FORMATO",
    "VERSION",
    "TIPOS",
    "TIPOS_CICLO",
    "SIMBOLO",
    "Diagrama",
    "Elemento",
    "ErrorFlujo",
    "ModeloFlujo",
    "Nodo",
    "Rama",
    "a_dict",
    "a_json",
    "desde_dict",
    "desde_json",
    "recorrer",
]

FORMATO = "inveniolang-flujo"
VERSION = 1

# Tipos de nodo. Las hojas son una instrucción; los compuestos contienen
# secuencias (ver ``_ESQUEMA``).
TIPOS_HOJA = (
    "proceso",
    "declaracion",
    "leer",
    "escribir",
    "llamada",
    "retornar",
    "romper",
    "continuar",
)
TIPOS_COMPUESTOS = (
    "si",
    "segun",
    "coincidir",
    "mientras",
    "hacer_mientras",
    "para",
    "para_cada",
    "intentar",
)
TIPOS = TIPOS_HOJA + TIPOS_COMPUESTOS
TIPOS_CICLO = ("mientras", "hacer_mientras", "para", "para_cada")
TIPOS_DIAGRAMA = ("main", "funcion", "procedimiento", "metodo", "constructor")

# Símbolo ISO 5807 con el que se dibuja cada tipo (correspondencia
# documentada en docs/diagramas_de_flujo.md). ``intentar`` no tiene símbolo
# propio en la norma: es un proceso que abre dos caminos (normal / error).
SIMBOLO: dict[str, str] = {
    "proceso": "proceso",
    "declaracion": "proceso",
    "leer": "datos",
    "escribir": "datos",
    "llamada": "predefinido",
    "retornar": "terminal",
    "romper": "conector",
    "continuar": "conector",
    "si": "decision",
    "segun": "decision",
    "coincidir": "decision",
    "mientras": "decision",
    "hacer_mientras": "decision",
    "para": "decision",
    "para_cada": "decision",
    "intentar": "proceso",
}

# Campos de texto que el JSON lleva por tipo: (clave JSON, atributo de Nodo).
CAMPOS_TEXTO: dict[str, tuple[tuple[str, str], ...]] = {
    "proceso": (("texto", "texto"),),
    "declaracion": (("texto", "texto"),),
    "leer": (("texto", "texto"),),
    "escribir": (("texto", "texto"),),
    "llamada": (("texto", "texto"),),
    "retornar": (("texto", "texto"),),
    "romper": (),
    "continuar": (),
    "si": (),
    "segun": (("expresion", "texto"),),
    "coincidir": (("expresion", "texto"),),
    "mientras": (("condicion", "texto"),),
    "hacer_mientras": (("condicion", "texto"),),
    "para": (("inicio", "inicio"), ("condicion", "texto"), ("paso", "paso")),
    "para_cada": (("variable", "variable"), ("coleccion", "texto")),
    "intentar": (("variable", "variable"),),
}
# Secuencias que lleva cada compuesto en el JSON:
#   "cuerpo"  -> Nodo.cuerpo (lista)
#   "ramas"   -> Nodo.ramas, cada rama {etiqueta_json: str, "cuerpo": [...]}
#   "alterno" -> Nodo.alterno (lista o null) con su nombre JSON.
_RAMAS: dict[str, tuple[str, str]] = {
    "si": ("ramas", "condicion"),
    "segun": ("casos", "valor"),
    "coincidir": ("casos", "patron"),
}
_ALTERNO: dict[str, str] = {
    "si": "sino",
    "segun": "por_defecto",
    "coincidir": "por_defecto",
    "intentar": "captura",
}
_CON_CUERPO = frozenset(TIPOS_CICLO + ("intentar",))


class ErrorFlujo(ValueError):
    """Error del diagrama de flujo con mensaje bilingüe del catálogo ``FLU.*``.

    ``diagnosticos`` lleva, si los hay, los diagnósticos oficiales del
    compilador que lo causaron (programa inválido).
    """

    def __init__(self, clave_mensaje: str, /, diagnosticos: tuple[str, ...] = (), **args: Any):
        self.clave_mensaje = clave_mensaje
        self.args_mensaje = dict(args)
        self.diagnosticos = tuple(diagnosticos)
        super().__init__(self.texto())

    def texto(self, idioma: str | None = None) -> str:
        """Mensaje en ``idioma`` (o en el idioma actual del proceso)."""
        args = {
            k: (v.texto(idioma) if isinstance(v, ErrorFlujo) else v)
            for k, v in self.args_mensaje.items()
        }
        return i18n.t(self.clave_mensaje, idioma, **args)


@dataclass
class Rama:
    """Una salida etiquetada de un compuesto: condición, valor de caso o patrón."""

    etiqueta: str
    cuerpo: list[Nodo] = field(default_factory=list)


@dataclass
class Nodo:
    """Un símbolo del diagrama (ver ``CAMPOS_TEXTO`` para el uso de cada campo)."""

    id: str
    tipo: str
    texto: str = ""
    linea: int = 0
    inicio: str = ""
    paso: str = ""
    variable: str = ""
    cuerpo: list[Nodo] = field(default_factory=list)
    ramas: list[Rama] = field(default_factory=list)
    alterno: list[Nodo] | None = None

    def secuencias(self) -> Iterator[tuple[str, list[Nodo]]]:
        """Pares (parte, secuencia) de los hijos, en orden de dibujo.

        ``parte`` es el nombre con el que la edición los direcciona:
        ``cuerpo``, ``rama:K``/``caso:K``, ``sino``, ``por_defecto``, ``captura``.
        """
        if self.tipo in _RAMAS:
            prefijo = "rama" if self.tipo == "si" else "caso"
            for k, rama in enumerate(self.ramas):
                yield f"{prefijo}:{k}", rama.cuerpo
        if self.tipo in _CON_CUERPO:
            yield "cuerpo", self.cuerpo
        if self.tipo in _ALTERNO and self.alterno is not None:
            yield _ALTERNO[self.tipo], self.alterno


@dataclass
class Diagrama:
    """Diagrama de una subrutina, ``main``, método o constructor."""

    clave: str
    nombre: str
    tipo: str
    firma: str
    clase: str | None = None
    linea: int = 0
    cuerpo: list[Nodo] = field(default_factory=list)


@dataclass
class Elemento:
    """Pieza del programa en su orden original.

    ``codigo``: declaración completa sin flujo (``texto``); ``subrutina``:
    ``diagrama``; ``clase``: ``texto`` es la cabecera (``clase A hereda B``) y
    ``miembros`` sus atributos (``codigo``) y métodos/constructores (``subrutina``).
    """

    tipo: str
    texto: str = ""
    diagrama: Diagrama | None = None
    miembros: list[Elemento] = field(default_factory=list)


@dataclass
class ModeloFlujo:
    """Programa completo como diagramas de flujo (contrato v1)."""

    idioma: str
    elementos: list[Elemento] = field(default_factory=list)

    def diagramas(self) -> list[Diagrama]:
        """Todos los diagramas en orden del programa."""
        salida: list[Diagrama] = []
        for el in self.elementos:
            for pieza in [el, *el.miembros]:
                if pieza.diagrama is not None:
                    salida.append(pieza.diagrama)
        return salida

    def diagrama(self, clave: str | None = None) -> Diagrama:
        """El diagrama ``clave`` (``None``: ``main`` o, si no hay, el primero)."""
        todos = self.diagramas()
        if not todos:
            raise ErrorFlujo("FLU.error.sin_diagramas")
        if clave is None:
            return next((d for d in todos if d.tipo == "main"), todos[0])
        for d in todos:
            if d.clave == clave:
                return d
        raise ErrorFlujo(
            "FLU.error.subrutina_desconocida",
            subrutina=clave,
            validas=", ".join(d.clave for d in todos),
        )


def recorrer(nodos: list[Nodo]) -> Iterator[Nodo]:
    """Todos los nodos de ``nodos`` y sus descendientes, en preorden."""
    for n in nodos:
        yield n
        for _, sec in n.secuencias():
            yield from recorrer(sec)


# ====================================================================== JSON


def _nodo_a_dict(n: Nodo) -> dict[str, Any]:
    d: dict[str, Any] = {"id": n.id, "tipo": n.tipo, "linea": n.linea}
    for clave, attr in CAMPOS_TEXTO[n.tipo]:
        d[clave] = getattr(n, attr)
    if n.tipo in _RAMAS:
        nombre, etiqueta = _RAMAS[n.tipo]
        d[nombre] = [
            {etiqueta: r.etiqueta, "cuerpo": [_nodo_a_dict(x) for x in r.cuerpo]} for r in n.ramas
        ]
    if n.tipo in _CON_CUERPO:
        d["cuerpo"] = [_nodo_a_dict(x) for x in n.cuerpo]
    if n.tipo in _ALTERNO:
        alt = n.alterno
        if n.tipo == "intentar" and alt is None:
            alt = []
        d[_ALTERNO[n.tipo]] = None if alt is None else [_nodo_a_dict(x) for x in alt]
    return d


def _diagrama_a_dict(d: Diagrama) -> dict[str, Any]:
    return {
        "clave": d.clave,
        "nombre": d.nombre,
        "tipo": d.tipo,
        "clase": d.clase,
        "firma": d.firma,
        "linea": d.linea,
        "cuerpo": [_nodo_a_dict(n) for n in d.cuerpo],
    }


def _elemento_a_dict(e: Elemento) -> dict[str, Any]:
    if e.tipo == "codigo":
        return {"tipo": "codigo", "texto": e.texto}
    if e.tipo == "subrutina":
        assert e.diagrama is not None  # garantizado por desde_dict y la extracción
        return {"tipo": "subrutina", "diagrama": _diagrama_a_dict(e.diagrama)}
    return {
        "tipo": "clase",
        "cabecera": e.texto,
        "miembros": [_elemento_a_dict(m) for m in e.miembros],
    }


def a_dict(modelo: ModeloFlujo) -> dict[str, Any]:
    """El modelo como ``dict`` JSON-serializable (contrato v1)."""
    return {
        "formato": FORMATO,
        "version": VERSION,
        "idioma": modelo.idioma,
        "elementos": [_elemento_a_dict(e) for e in modelo.elementos],
    }


def a_json(modelo: ModeloFlujo, sangria: int | None = 2) -> str:
    """El modelo como texto JSON (UTF-8 legible, claves en orden estable)."""
    return json.dumps(a_dict(modelo), ensure_ascii=False, indent=sangria)


class _Lector:
    """Convierte un ``dict`` en modelo validando cada dato con su ruta."""

    def __init__(self) -> None:
        self.ids: set[str] = set()
        self.claves: set[str] = set()

    @staticmethod
    def falla(ruta: str, detalle: str, **args: Any) -> ErrorFlujo:
        return ErrorFlujo("FLU.error.contrato", ruta=ruta, detalle=ErrorFlujo(detalle, **args))

    def objeto(self, dato: Any, ruta: str, claves: tuple[str, ...]) -> Mapping[str, Any]:
        if not isinstance(dato, dict):
            raise self.falla(ruta, "FLU.contrato.objeto")
        faltan = [c for c in claves if c not in dato]
        if faltan:
            raise self.falla(ruta, "FLU.contrato.faltan", claves=", ".join(faltan))
        sobran = sorted(set(dato) - set(claves))
        if sobran:
            raise self.falla(ruta, "FLU.contrato.sobran", claves=", ".join(sobran))
        return dato

    def texto(self, dato: Any, ruta: str) -> str:
        if not isinstance(dato, str):
            raise self.falla(ruta, "FLU.contrato.texto")
        return dato

    def entero(self, dato: Any, ruta: str) -> int:
        if not isinstance(dato, int) or isinstance(dato, bool) or dato < 0:
            raise self.falla(ruta, "FLU.contrato.entero")
        return dato

    def lista(self, dato: Any, ruta: str) -> list[Any]:
        if not isinstance(dato, list):
            raise self.falla(ruta, "FLU.contrato.lista")
        return dato

    def opcion(self, dato: Any, ruta: str, validas: tuple[str, ...]) -> str:
        valor = self.texto(dato, ruta)
        if valor not in validas:
            raise self.falla(ruta, "FLU.contrato.opcion", valor=valor, validas=", ".join(validas))
        return valor

    def secuencia(self, dato: Any, ruta: str) -> list[Nodo]:
        return [self.nodo(x, f"{ruta}[{k}]") for k, x in enumerate(self.lista(dato, ruta))]

    def nodo(self, dato: Any, ruta: str) -> Nodo:
        if not isinstance(dato, dict):
            raise self.falla(ruta, "FLU.contrato.objeto")
        tipo = self.opcion(dato.get("tipo"), f"{ruta}.tipo", TIPOS)
        claves = ["id", "tipo", "linea"] + [c for c, _ in CAMPOS_TEXTO[tipo]]
        if tipo in _RAMAS:
            claves.append(_RAMAS[tipo][0])
        if tipo in _CON_CUERPO:
            claves.append("cuerpo")
        if tipo in _ALTERNO:
            claves.append(_ALTERNO[tipo])
        d = self.objeto(dato, ruta, tuple(claves))
        ident = self.texto(d["id"], f"{ruta}.id")
        if not ident or ident in self.ids:
            raise self.falla(f"{ruta}.id", "FLU.contrato.id_repetido", id=ident)
        self.ids.add(ident)
        n = Nodo(ident, tipo, linea=self.entero(d["linea"], f"{ruta}.linea"))
        for clave, attr in CAMPOS_TEXTO[tipo]:
            setattr(n, attr, self.texto(d[clave], f"{ruta}.{clave}"))
        if tipo in _RAMAS:
            nombre, etiqueta = _RAMAS[tipo]
            for k, r in enumerate(self.lista(d[nombre], f"{ruta}.{nombre}")):
                rr = f"{ruta}.{nombre}[{k}]"
                rd = self.objeto(r, rr, (etiqueta, "cuerpo"))
                n.ramas.append(
                    Rama(
                        self.texto(rd[etiqueta], f"{rr}.{etiqueta}"),
                        self.secuencia(rd["cuerpo"], f"{rr}.cuerpo"),
                    )
                )
            if tipo == "si" and not n.ramas:
                raise self.falla(f"{ruta}.{nombre}", "FLU.contrato.sin_ramas")
        if tipo in _CON_CUERPO:
            n.cuerpo = self.secuencia(d["cuerpo"], f"{ruta}.cuerpo")
        if tipo in _ALTERNO:
            nombre_alt = _ALTERNO[tipo]
            alt = d[nombre_alt]
            if alt is None and tipo == "intentar":
                raise self.falla(f"{ruta}.{nombre_alt}", "FLU.contrato.lista")
            n.alterno = None if alt is None else self.secuencia(alt, f"{ruta}.{nombre_alt}")
        return n

    def diagrama(self, dato: Any, ruta: str) -> Diagrama:
        d = self.objeto(
            dato, ruta, ("clave", "nombre", "tipo", "clase", "firma", "linea", "cuerpo")
        )
        clave = self.texto(d["clave"], f"{ruta}.clave")
        if not clave or clave in self.claves:
            raise self.falla(f"{ruta}.clave", "FLU.contrato.clave_repetida", nombre=clave)
        self.claves.add(clave)
        clase = d["clase"]
        return Diagrama(
            clave=clave,
            nombre=self.texto(d["nombre"], f"{ruta}.nombre"),
            tipo=self.opcion(d["tipo"], f"{ruta}.tipo", TIPOS_DIAGRAMA),
            firma=self.texto(d["firma"], f"{ruta}.firma"),
            clase=None if clase is None else self.texto(clase, f"{ruta}.clase"),
            linea=self.entero(d["linea"], f"{ruta}.linea"),
            cuerpo=self.secuencia(d["cuerpo"], f"{ruta}.cuerpo"),
        )

    def elemento(self, dato: Any, ruta: str, en_clase: bool = False) -> Elemento:
        if not isinstance(dato, dict):
            raise self.falla(ruta, "FLU.contrato.objeto")
        validos = ("codigo", "subrutina") if en_clase else ("codigo", "subrutina", "clase")
        tipo = self.opcion(dato.get("tipo"), f"{ruta}.tipo", validos)
        if tipo == "codigo":
            d = self.objeto(dato, ruta, ("tipo", "texto"))
            return Elemento("codigo", texto=self.texto(d["texto"], f"{ruta}.texto"))
        if tipo == "subrutina":
            d = self.objeto(dato, ruta, ("tipo", "diagrama"))
            return Elemento("subrutina", diagrama=self.diagrama(d["diagrama"], f"{ruta}.diagrama"))
        d = self.objeto(dato, ruta, ("tipo", "cabecera", "miembros"))
        miembros = self.lista(d["miembros"], f"{ruta}.miembros")
        return Elemento(
            "clase",
            texto=self.texto(d["cabecera"], f"{ruta}.cabecera"),
            miembros=[
                self.elemento(m, f"{ruta}.miembros[{k}]", True) for k, m in enumerate(miembros)
            ],
        )


def desde_dict(dato: Any) -> ModeloFlujo:
    """Reconstruye y valida un modelo; ``ErrorFlujo`` con la ruta del dato inválido."""
    lector = _Lector()
    d = lector.objeto(dato, "$", ("formato", "version", "idioma", "elementos"))
    if d["formato"] != FORMATO:
        raise lector.falla("$.formato", "FLU.contrato.formato", formato=FORMATO)
    if d["version"] != VERSION:
        raise lector.falla("$.version", "FLU.contrato.version", version=str(d["version"]))
    idioma = lector.opcion(d["idioma"], "$.idioma", i18n.IDIOMAS)
    elementos = lector.lista(d["elementos"], "$.elementos")
    return ModeloFlujo(
        idioma, [lector.elemento(e, f"$.elementos[{k}]") for k, e in enumerate(elementos)]
    )


def desde_json(texto: str) -> ModeloFlujo:
    """Lee un modelo desde texto JSON (``ErrorFlujo`` si no es JSON o no cumple v1)."""
    try:
        dato = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorFlujo("FLU.error.json", detalle=str(e)) from e
    return desde_dict(dato)
