"""Modelo UML de clases serializable (contrato JSON, versión 1).

INV-3200: antes ``uml.py`` recorría el AST y escribía directamente texto
PlantUML/Mermaid, sin un modelo intermedio: no había forma de leer un
diagrama, de generar código desde él ni de dibujarlo sin volver a analizar
el programa, y se perdían interfaces, enumeraciones, constructores,
genéricos y todas las relaciones salvo la herencia. Ahora todo pasa por
este modelo inmutable (``dataclass(frozen=True)``, secuencias como tuplas)
que se convierte a ``dict``/JSON y vuelve **exactamente** igual
(``desde_json(a_json(m)) == m``). Lo producen el analizador de código
(:mod:`.desde_codigo`) y el lector de PlantUML (:mod:`.plantuml`); lo
consumen los exportadores, el SVG, la descripción textual y el generador de
código.

Convenciones del contrato (ver ``docs/uml.md``):

* Los tipos se guardan en forma **canónica e independiente del idioma**:
  ``int``, ``float``, ``string``, ``bool``, ``void``, un nombre de clase,
  un parámetro de tipo (``T``) y el sufijo ``[]``/``[][]`` para arreglos.
  Los renderizadores los muestran en español o en inglés.
* La herencia y la realización viven **solo** en ``relaciones``; los
  atributos cuyo tipo es otro clasificador tienen además una relación
  estructural (asociación, agregación o composición) con ``rol`` = nombre
  del atributo.
* ``valor_inicial`` solo guarda literales (número, texto, lógico o nulo):
  es lo único que se puede reproducir sin el resto del programa.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..i18n import M, Mensaje
from ..i18n import t as _t

__all__ = [
    "Atributo",
    "Clasificador",
    "Constructor",
    "DiagramaClases",
    "ErrorUML",
    "Literal",
    "Metodo",
    "Parametro",
    "Relacion",
    "ValorInicial",
    "a_json",
    "desde_json",
]

VERSION = 1
TIPOS_CLASIFICADOR = ("clase", "abstracta", "interfaz", "enumeracion")
VISIBILIDADES = ("+", "-", "#")
TIPOS_RELACION = (
    "herencia",
    "realizacion",
    "composicion",
    "agregacion",
    "asociacion",
    "dependencia",
)
# Relaciones que nacen de un atributo (llevan ``rol`` y ``multiplicidad``).
ESTRUCTURALES = ("composicion", "agregacion", "asociacion")
JERARQUICAS = ("herencia", "realizacion")
PRIMITIVOS = ("int", "float", "string", "bool")
TIPOS_LITERAL = ("int", "float", "string", "bool", "null")
MULTIPLICIDADES = ("0..1", "0..*")


class ErrorUML(ValueError):
    """Error de un diagrama UML con mensaje bilingüe diferido.

    Guarda la clave del catálogo y sus argumentos (que pueden ser a su vez
    :class:`~inveniolang.i18n.Mensaje`) y se presenta en el idioma que pida
    quien lo muestra (``texto(idioma)``), igual que los diagnósticos del
    compilador.
    """

    def __init__(self, clave: str, **args: Any):
        self.mensaje = M(clave, **args)
        super().__init__(self.texto())

    def texto(self, idioma: str | None = None) -> str:
        """Mensaje en ``idioma`` (los argumentos ``Mensaje`` también se traducen)."""
        args = {
            k: (v.texto(idioma) if isinstance(v, Mensaje) else v)
            for k, v in self.mensaje.args.items()
        }
        return _t(self.mensaje.clave, idioma, **args)


def _falla(ruta: str, motivo: str, **args: Any) -> ErrorUML:
    return ErrorUML("UML.json.invalido", ruta=ruta, motivo=M(motivo, **args))


def _exigir(condicion: bool, ruta: str, motivo: str, **args: Any) -> None:
    if not condicion:
        raise _falla(ruta, motivo, **args)


def _objeto(dato: Any, ruta: str, claves: tuple[str, ...]) -> Mapping[str, Any]:
    _exigir(isinstance(dato, dict), ruta, "UML.json.objeto")
    faltan = [c for c in claves if c not in dato]
    _exigir(not faltan, ruta, "UML.json.faltan", claves=", ".join(faltan))
    return dict(dato)


def _texto(dato: Any, ruta: str) -> str:
    _exigir(isinstance(dato, str) and bool(dato), ruta, "UML.json.texto")
    return str(dato)


def _texto_o_nulo(dato: Any, ruta: str) -> str | None:
    return None if dato is None else _texto(dato, ruta)


def _logico(dato: Any, ruta: str) -> bool:
    _exigir(isinstance(dato, bool), ruta, "UML.json.logico")
    return bool(dato)


def _lista(dato: Any, ruta: str) -> list[Any]:
    _exigir(isinstance(dato, list), ruta, "UML.json.lista")
    return list(dato)


def _opcion(dato: Any, ruta: str, validas: tuple[str, ...]) -> str:
    _exigir(dato in validas, ruta, "UML.json.opcion", validas=" | ".join(validas))
    return str(dato)


@dataclass(frozen=True)
class ValorInicial:
    """Literal con que se inicializa un atributo (``tipo`` ∈ int, float, string, bool, null)."""

    tipo: str
    v: int | float | str | bool | None = None

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {"tipo": self.tipo, "v": self.v}

    @classmethod
    def desde_dict(cls, d: Any, ruta: str) -> ValorInicial:
        """Reconstruye el literal validando que ``v`` concuerde con ``tipo``."""
        datos = _objeto(d, ruta, ("tipo", "v"))
        tipo = _opcion(datos["tipo"], ruta + ".tipo", TIPOS_LITERAL)
        v = datos["v"]
        esperado: tuple[type, ...] = {
            "int": (int,),
            "float": (float, int),
            "string": (str,),
            "bool": (bool,),
            "null": (type(None),),
        }[tipo]
        valido = isinstance(v, esperado) and (tipo == "bool" or not isinstance(v, bool))
        _exigir(valido, ruta + ".v", "UML.json.literal", tipo=tipo)
        return cls(tipo, float(v) if tipo == "float" else v)


@dataclass(frozen=True)
class Parametro:
    """Parámetro de un constructor, método o literal de enumeración con carga."""

    nombre: str
    tipo: str

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {"nombre": self.nombre, "tipo": self.tipo}

    @classmethod
    def desde_dict(cls, d: Any, ruta: str) -> Parametro:
        """Reconstruye un parámetro validando el contrato."""
        datos = _objeto(d, ruta, ("nombre", "tipo"))
        return cls(_texto(datos["nombre"], ruta + ".nombre"), _texto(datos["tipo"], ruta + ".tipo"))


def _parametros(dato: Any, ruta: str) -> tuple[Parametro, ...]:
    return tuple(Parametro.desde_dict(p, f"{ruta}[{i}]") for i, p in enumerate(_lista(dato, ruta)))


@dataclass(frozen=True)
class Atributo:
    """Atributo con visibilidad (``+`` público, ``-`` privado, ``#`` protegido)."""

    nombre: str
    tipo: str
    visibilidad: str = "-"
    estatico: bool = False
    constante: bool = False
    valor_inicial: ValorInicial | None = None

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "nombre": self.nombre,
            "tipo": self.tipo,
            "visibilidad": self.visibilidad,
            "estatico": self.estatico,
            "constante": self.constante,
            "valor_inicial": None if self.valor_inicial is None else self.valor_inicial.a_dict(),
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str) -> Atributo:
        """Reconstruye un atributo validando el contrato."""
        claves = ("nombre", "tipo", "visibilidad", "estatico", "constante", "valor_inicial")
        datos = _objeto(d, ruta, claves)
        inicial = datos["valor_inicial"]
        return cls(
            _texto(datos["nombre"], ruta + ".nombre"),
            _texto(datos["tipo"], ruta + ".tipo"),
            _opcion(datos["visibilidad"], ruta + ".visibilidad", VISIBILIDADES),
            _logico(datos["estatico"], ruta + ".estatico"),
            _logico(datos["constante"], ruta + ".constante"),
            None if inicial is None else ValorInicial.desde_dict(inicial, ruta + ".valor_inicial"),
        )


@dataclass(frozen=True)
class Constructor:
    """Constructor (en UML, una operación «create» con el nombre de la clase)."""

    visibilidad: str = "+"
    parametros: tuple[Parametro, ...] = ()

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "visibilidad": self.visibilidad,
            "parametros": [p.a_dict() for p in self.parametros],
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str) -> Constructor:
        """Reconstruye un constructor validando el contrato."""
        datos = _objeto(d, ruta, ("visibilidad", "parametros"))
        return cls(
            _opcion(datos["visibilidad"], ruta + ".visibilidad", VISIBILIDADES),
            _parametros(datos["parametros"], ruta + ".parametros"),
        )


@dataclass(frozen=True)
class Metodo:
    """Operación: firma, visibilidad y modificadores.

    ``sobrescribe`` es un dato **derivado** (otro supertipo declara la misma
    firma); quien construye el modelo lo calcula y ``normalizar`` lo
    recalcula, así que nunca contradice al resto del diagrama.
    """

    nombre: str
    retorno: str = "void"
    visibilidad: str = "+"
    parametros: tuple[Parametro, ...] = ()
    estatico: bool = False
    abstracto: bool = False
    sobrescribe: bool = False

    @property
    def firma(self) -> tuple[str, tuple[str, ...]]:
        """Nombre y tipos de parámetros: lo que distingue una sobrecarga."""
        return self.nombre, tuple(p.tipo for p in self.parametros)

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "nombre": self.nombre,
            "retorno": self.retorno,
            "visibilidad": self.visibilidad,
            "parametros": [p.a_dict() for p in self.parametros],
            "estatico": self.estatico,
            "abstracto": self.abstracto,
            "sobrescribe": self.sobrescribe,
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str) -> Metodo:
        """Reconstruye un método validando el contrato."""
        claves = ("nombre", "retorno", "visibilidad", "parametros", "estatico", "abstracto")
        datos = _objeto(d, ruta, claves + ("sobrescribe",))
        return cls(
            _texto(datos["nombre"], ruta + ".nombre"),
            _texto(datos["retorno"], ruta + ".retorno"),
            _opcion(datos["visibilidad"], ruta + ".visibilidad", VISIBILIDADES),
            _parametros(datos["parametros"], ruta + ".parametros"),
            _logico(datos["estatico"], ruta + ".estatico"),
            _logico(datos["abstracto"], ruta + ".abstracto"),
            _logico(datos["sobrescribe"], ruta + ".sobrescribe"),
        )


@dataclass(frozen=True)
class Literal:
    """Valor de una enumeración; con ``parametros`` es una variante con carga (tipo suma)."""

    nombre: str
    parametros: tuple[Parametro, ...] = ()

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {"nombre": self.nombre, "parametros": [p.a_dict() for p in self.parametros]}

    @classmethod
    def desde_dict(cls, d: Any, ruta: str) -> Literal:
        """Reconstruye un literal validando el contrato."""
        datos = _objeto(d, ruta, ("nombre", "parametros"))
        return cls(
            _texto(datos["nombre"], ruta + ".nombre"),
            _parametros(datos["parametros"], ruta + ".parametros"),
        )


@dataclass(frozen=True)
class Clasificador:
    """Clase, clase abstracta, interfaz o enumeración.

    ``modulo`` es el archivo importado de donde viene (``None`` si se
    declaró en el propio programa).
    """

    nombre: str
    tipo: str = "clase"
    parametros_tipo: tuple[str, ...] = ()
    atributos: tuple[Atributo, ...] = ()
    constructores: tuple[Constructor, ...] = ()
    metodos: tuple[Metodo, ...] = ()
    literales: tuple[Literal, ...] = ()
    modulo: str | None = None

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "nombre": self.nombre,
            "tipo": self.tipo,
            "parametros_tipo": list(self.parametros_tipo),
            "atributos": [a.a_dict() for a in self.atributos],
            "constructores": [c.a_dict() for c in self.constructores],
            "metodos": [m.a_dict() for m in self.metodos],
            "literales": [x.a_dict() for x in self.literales],
            "modulo": self.modulo,
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str) -> Clasificador:
        """Reconstruye un clasificador validando el contrato."""
        claves = ("nombre", "tipo", "parametros_tipo", "atributos", "constructores", "metodos")
        datos = _objeto(d, ruta, claves + ("literales", "modulo"))
        return cls(
            _texto(datos["nombre"], ruta + ".nombre"),
            _opcion(datos["tipo"], ruta + ".tipo", TIPOS_CLASIFICADOR),
            tuple(
                _texto(p, f"{ruta}.parametros_tipo[{i}]")
                for i, p in enumerate(_lista(datos["parametros_tipo"], ruta + ".parametros_tipo"))
            ),
            tuple(
                Atributo.desde_dict(a, f"{ruta}.atributos[{i}]")
                for i, a in enumerate(_lista(datos["atributos"], ruta + ".atributos"))
            ),
            tuple(
                Constructor.desde_dict(c, f"{ruta}.constructores[{i}]")
                for i, c in enumerate(_lista(datos["constructores"], ruta + ".constructores"))
            ),
            tuple(
                Metodo.desde_dict(m, f"{ruta}.metodos[{i}]")
                for i, m in enumerate(_lista(datos["metodos"], ruta + ".metodos"))
            ),
            tuple(
                Literal.desde_dict(x, f"{ruta}.literales[{i}]")
                for i, x in enumerate(_lista(datos["literales"], ruta + ".literales"))
            ),
            _texto_o_nulo(datos["modulo"], ruta + ".modulo"),
        )


@dataclass(frozen=True)
class Relacion:
    """Relación entre dos clasificadores.

    * ``herencia``: ``origen`` (subclase) hereda de ``destino``.
    * ``realizacion``: ``origen`` implementa la interfaz ``destino``.
    * ``composicion``/``agregacion``/``asociacion``: ``origen`` tiene el
      atributo ``rol`` de tipo ``destino`` con ``multiplicidad`` ``0..1``
      (un objeto) o ``0..*`` (un arreglo de objetos).
    * ``dependencia``: ``origen`` usa ``destino`` (parámetros, retorno,
      variables locales, ``nuevo``, miembros estáticos).
    """

    tipo: str
    origen: str
    destino: str
    rol: str | None = None
    multiplicidad: str | None = None

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "tipo": self.tipo,
            "origen": self.origen,
            "destino": self.destino,
            "rol": self.rol,
            "multiplicidad": self.multiplicidad,
        }

    @classmethod
    def desde_dict(cls, d: Any, ruta: str) -> Relacion:
        """Reconstruye una relación validando el contrato."""
        datos = _objeto(d, ruta, ("tipo", "origen", "destino", "rol", "multiplicidad"))
        tipo = _opcion(datos["tipo"], ruta + ".tipo", TIPOS_RELACION)
        rol = _texto_o_nulo(datos["rol"], ruta + ".rol")
        mult = datos["multiplicidad"]
        if tipo in ESTRUCTURALES:
            _exigir(rol is not None, ruta + ".rol", "UML.json.texto")
            mult = _opcion(mult, ruta + ".multiplicidad", MULTIPLICIDADES)
        else:
            _exigir(rol is None and mult is None, ruta, "UML.json.sin_rol")
        return cls(
            tipo,
            _texto(datos["origen"], ruta + ".origen"),
            _texto(datos["destino"], ruta + ".destino"),
            rol,
            mult,
        )


@dataclass(frozen=True)
class DiagramaClases:
    """Diagrama de clases completo; ``idioma`` es el de presentación por defecto."""

    clasificadores: tuple[Clasificador, ...] = ()
    relaciones: tuple[Relacion, ...] = ()
    idioma: str = "es"
    version: int = VERSION

    def clasificador(self, nombre: str) -> Clasificador | None:
        """Clasificador llamado ``nombre`` (o ``None``)."""
        for c in self.clasificadores:
            if c.nombre == nombre:
                return c
        return None

    def padre(self, nombre: str) -> str | None:
        """Superclase de ``nombre`` según sus relaciones de herencia."""
        for r in self.relaciones:
            if r.tipo == "herencia" and r.origen == nombre:
                return r.destino
        return None

    def interfaces(self, nombre: str) -> tuple[str, ...]:
        """Interfaces que ``nombre`` implementa directamente, en orden."""
        return tuple(
            r.destino for r in self.relaciones if r.tipo == "realizacion" and r.origen == nombre
        )

    def supertipos(self, nombre: str) -> list[str]:
        """Todos los supertipos (clases e interfaces) de ``nombre``, sin repetir."""
        vistos: list[str] = []
        pendientes = [nombre]
        while pendientes:
            actual = pendientes.pop(0)
            directos = ([self.padre(actual)] if self.padre(actual) else []) + list(
                self.interfaces(actual)
            )
            for s in directos:
                if s is not None and s not in vistos and s != nombre:
                    vistos.append(s)
                    pendientes.append(s)
        return vistos

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del contrato."""
        return {
            "version": self.version,
            "tipo": "diagrama_clases",
            "idioma": self.idioma,
            "clasificadores": [c.a_dict() for c in self.clasificadores],
            "relaciones": [r.a_dict() for r in self.relaciones],
        }

    @classmethod
    def desde_dict(cls, d: Any) -> DiagramaClases:
        """Reconstruye el diagrama validando forma, versión y referencias."""
        datos = _objeto(d, "uml", ("version", "tipo", "idioma", "clasificadores", "relaciones"))
        version = datos["version"]
        _exigir(
            isinstance(version, int) and not isinstance(version, bool) and version == VERSION,
            "uml.version",
            "UML.json.version",
            version=version,
        )
        _exigir(datos["tipo"] == "diagrama_clases", "uml.tipo", "UML.json.tipo_documento")
        idioma = _opcion(datos["idioma"], "uml.idioma", ("es", "en"))
        clasificadores = tuple(
            Clasificador.desde_dict(c, f"uml.clasificadores[{i}]")
            for i, c in enumerate(_lista(datos["clasificadores"], "uml.clasificadores"))
        )
        nombres = [c.nombre for c in clasificadores]
        for i, n in enumerate(nombres):
            _exigir(n not in nombres[:i], f"uml.clasificadores[{i}]", "UML.json.repetido", nombre=n)
        relaciones = tuple(
            Relacion.desde_dict(r, f"uml.relaciones[{i}]")
            for i, r in enumerate(_lista(datos["relaciones"], "uml.relaciones"))
        )
        for i, r in enumerate(relaciones):
            for extremo in (r.origen, r.destino):
                _exigir(
                    extremo in nombres,
                    f"uml.relaciones[{i}]",
                    "UML.json.desconocido",
                    nombre=extremo,
                )
        return cls(clasificadores, relaciones, idioma, version)


def a_json(modelo: DiagramaClases, indent: int | None = 2) -> str:
    """Serializa el diagrama a JSON (UTF-8 sin escapar; ``allow_nan=False``)."""
    return json.dumps(modelo.a_dict(), ensure_ascii=False, indent=indent, allow_nan=False)


def desde_json(texto: str) -> DiagramaClases:
    """Diagrama a partir de su JSON; :class:`ErrorUML` si no cumple el contrato."""
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorUML("UML.json.sintaxis", detalle=f"{e.msg} ({e.lineno}:{e.colno})") from e
    return DiagramaClases.desde_dict(datos)
