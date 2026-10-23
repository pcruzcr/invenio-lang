"""Lector de un subconjunto documentado de PlantUML → modelo UML.

INV-3205: hasta ahora el diagrama solo podía *salir* del código; un docente
que dibuja el diseño en PlantUML (o un estudiante que lo copia de un libro)
no tenía cómo convertirlo en un esqueleto de programa. Este lector acepta
el subconjunto descrito en ``docs/uml.md``:

* ``class``, ``abstract class``/``abstract``, ``interface`` y ``enum``, con
  genérico ``<T>``, ``extends``/``implements`` y estereotipos
  ``<<interface>>``/``<<abstract>>``/``<<enumeration>>``;
* atributos ``[vis] [{static}] nombre : Tipo [= literal] [{readOnly}]`` (o
  ``Tipo nombre``), métodos ``[vis] [{static}|{abstract}] nombre(p : T) : R``
  (o ``R nombre(T p)``) y constructores (``<<create>> Clase(...)`` o un
  método con el nombre de la clase);
* literales de enumeración, con carga opcional ``Circulo(radio : entero)``;
* relaciones ``<|--``, ``<|..``, ``*--``, ``o--``, ``-->``, ``--``, ``..>``
  (y sus inversas), con multiplicidad entre comillas y rol tras ``:``.

Los tipos se aceptan en español, en inglés o con los nombres habituales de
UML/Java (``Integer``, ``String``, ``boolean``…) y se guardan en forma
canónica. Cualquier línea fuera del subconjunto es un error con su número
de línea, en el idioma del estudiante: mejor que ignorarla en silencio y
generar un esqueleto distinto del diagrama.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import replace

from .modelo import (
    ESTRUCTURALES,
    Atributo,
    Clasificador,
    Constructor,
    DiagramaClases,
    ErrorUML,
    Literal,
    Metodo,
    Parametro,
    Relacion,
    ValorInicial,
)
from .reglas import error_linea, normalizar

__all__ = ["leer_plantuml"]

_TIPOS = {
    "int": ("entero", "int", "integer", "long", "short", "byte"),
    "float": ("real", "float", "double", "decimal", "number"),
    "string": ("texto", "string", "str", "char"),
    "bool": ("logico", "lógico", "bool", "boolean"),
    "void": ("vacio", "vacío", "void"),
}
_CANONICO = {alias: canon for canon, alias_ in _TIPOS.items() for alias in alias_}
_ESPANOL = {"entero", "real", "texto", "logico", "lógico", "vacio", "vacío"}
_INGLES = {"int", "float", "string", "bool", "void", "integer", "boolean", "double"}

_IGNORADAS = re.compile(
    r"^(@startuml|@enduml|skinparam\b|hide\b|show\b|title\b|scale\b|!|left to right|"
    r"top to bottom|caption\b|header\b|footer\b|legend\b|end ?legend)",
    re.IGNORECASE,
)
_DECL = re.compile(
    r"^(?P<palabra>abstract\s+class|abstract|class|interface|enum)\s+"
    r"(?P<nombre>[A-Za-z_]\w*)\s*(?:<(?P<gen>[^>]*)>)?\s*(?P<resto>.*?)\s*$"
)
_REL = re.compile(
    r'^(?P<a>[A-Za-z_]\w*)\s*(?:"(?P<ma>[^"]*)")?\s*(?P<flecha>[<|*o.\-]*[.\-][.\->|*o]*)\s*'
    r'(?:"(?P<mb>[^"]*)")?\s*(?P<b>[A-Za-z_]\w*)\s*(?::\s*(?P<etiqueta>.*))?$'
)
_IDENT = re.compile(r"[A-Za-z_]\w*\Z")


def _tipo(texto: str, n: int) -> str:
    """Tipo tal como se escribió (sin espacios); se resuelve al final con :func:`_resolver`."""
    t = texto.strip().replace(" ", "")
    base = t
    while base.endswith("[]"):
        base = base[:-2]
    if not base or not _IDENT.match(base):
        raise error_linea(n, "UML.puml.tipo", tipo=texto.strip())
    return t


def _resolver(tipo: str, clases: set[str]) -> str:
    """Tipo canónico: una clase del diagrama gana a un alias (``Texto`` puede ser una clase)."""
    base = tipo.replace("[]", "")
    if base in clases:
        return tipo
    return _CANONICO.get(base.lower(), base) + "[]" * tipo.count("[]")


def _partir_comas(texto: str) -> list[str]:
    """Divide por comas de primer nivel (ignora las de ``<...>``)."""
    partes, nivel, actual = [], 0, ""
    for ch in texto:
        if ch == "<":
            nivel += 1
        elif ch == ">":
            nivel -= 1
        if ch == "," and nivel == 0:
            partes.append(actual)
            actual = ""
        else:
            actual += ch
    if actual.strip():
        partes.append(actual)
    return [p.strip() for p in partes if p.strip()]


def _nombre_y_tipo(texto: str, n: int, que: str) -> tuple[str, str]:
    """``nombre : Tipo`` (UML) o ``Tipo nombre`` (Java)."""
    if ":" in texto:
        nombre, tipo = (x.strip() for x in texto.split(":", 1))
    else:
        piezas = texto.split()
        if len(piezas) != 2:
            raise error_linea(n, "UML.puml.miembro", texto=texto, que=que)
        tipo, nombre = piezas
    if not _IDENT.match(nombre):
        raise error_linea(n, "UML.puml.miembro", texto=texto, que=que)
    return nombre, _tipo(tipo, n)


def _parametros(texto: str, n: int) -> tuple[Parametro, ...]:
    return tuple(Parametro(*_nombre_y_tipo(p, n, "parametro")) for p in _partir_comas(texto))


def _valor(texto: str, n: int) -> ValorInicial:
    t = texto.strip()
    bajo = t.lower()
    if bajo in ("null", "nulo"):
        return ValorInicial("null", None)
    if bajo in ("true", "verdadero", "false", "falso"):
        return ValorInicial("bool", bajo in ("true", "verdadero"))
    if re.fullmatch(r"-?\d+", t):
        return ValorInicial("int", int(t))
    if re.fullmatch(r"-?\d+\.\d+([eE][+-]?\d+)?", t):
        return ValorInicial("float", float(t))
    if len(t) >= 2 and t[0] == t[-1] == '"':
        try:
            return ValorInicial("string", str(json.loads(t)))
        except json.JSONDecodeError:
            pass
    raise error_linea(n, "UML.puml.valor", valor=t)


class _Lector:
    """Recorre el texto línea a línea (con su número) y arma el modelo."""

    def __init__(self, texto: str):
        self.lineas = list(self._limpias(texto))
        self.pos = 0
        self.clasificadores: dict[str, dict] = {}
        self.orden: list[str] = []
        self.relaciones: list[Relacion] = []
        self.palabras_es = 0
        self.palabras_en = 0

    @staticmethod
    def _limpias(texto: str) -> Iterator[tuple[int, str]]:
        en_comentario = False
        for n, cruda in enumerate(texto.splitlines(), 1):
            linea = cruda.strip()
            if en_comentario:
                if "'/" in linea:
                    en_comentario = False
                continue
            if linea.startswith("/'"):
                en_comentario = "'/" not in linea[2:]
                continue
            if not linea or linea.startswith("'") or _IGNORADAS.match(linea):
                continue
            yield n, linea

    def _anotar_idioma(self, tipo: str) -> None:
        base = tipo.replace("[]", "")
        if base in self.clasificadores:
            return
        self.palabras_es += base.lower() in _ESPANOL
        self.palabras_en += base.lower() in _INGLES

    def _nuevo(self, nombre: str, tipo: str, n: int, declara: bool = False) -> dict:
        """Datos del clasificador ``nombre``; una mención (relación, ``extends``) lo crea."""
        if declara and nombre in self.clasificadores and self.clasificadores[nombre]["declarado"]:
            raise error_linea(n, "UML.puml.repetido", nombre=nombre)
        datos = self.clasificadores.get(nombre)
        if datos is None:
            datos = {
                "nombre": nombre,
                "tipo": tipo,
                "genericos": (),
                "atributos": [],
                "constructores": [],
                "metodos": [],
                "literales": [],
                "declarado": False,
            }
            self.clasificadores[nombre] = datos
            self.orden.append(nombre)
        return datos

    def leer(self) -> None:
        while self.pos < len(self.lineas):
            n, linea = self.lineas[self.pos]
            self.pos += 1
            if linea.startswith("note ") or linea == "note":
                self._saltar_nota(linea)
                continue
            decl = _DECL.match(linea)
            if decl:
                self._declaracion(decl, n)
                continue
            rel = _REL.match(linea)
            if rel:
                self._relacion(rel, n)
                continue
            raise error_linea(n, "UML.puml.linea", texto=linea)

    def _saltar_nota(self, linea: str) -> None:
        if ":" in linea:
            return  # nota de una sola línea
        while self.pos < len(self.lineas):
            _, otra = self.lineas[self.pos]
            self.pos += 1
            if otra.lower().startswith("end note") or otra.lower() == "endnote":
                return

    def _declaracion(self, decl: re.Match, n: int) -> None:
        palabra = " ".join(decl.group("palabra").split())
        tipo = {
            "abstract class": "abstracta",
            "abstract": "abstracta",
            "class": "clase",
            "interface": "interfaz",
            "enum": "enumeracion",
        }[palabra]
        resto = decl.group("resto")
        abre = resto.endswith("{") or resto.endswith("{}") or resto.endswith("{ }")
        cierra_misma = re.search(r"\{\s*\}$", resto) is not None
        resto = re.sub(r"\{\s*\}?$", "", resto).strip()
        for estereotipo in re.findall(r"<<\s*(\w+)\s*>>", resto):
            tipo = {
                "interface": "interfaz",
                "abstract": "abstracta",
                "enumeration": "enumeracion",
                "enum": "enumeracion",
            }.get(estereotipo.lower(), tipo)
        resto = re.sub(r"<<[^>]*>>", "", resto).strip()
        datos = self._nuevo(decl.group("nombre"), tipo, n, declara=True)
        datos["tipo"] = tipo
        datos["declarado"] = True
        if decl.group("gen"):
            datos["genericos"] = tuple(g.strip() for g in decl.group("gen").split(",") if g.strip())
        herencia = re.match(
            r"^(?:extends\s+(?P<padre>\w+))?\s*(?:implements\s+(?P<ifs>[\w\s,]+))?$", resto
        )
        if herencia is None:
            raise error_linea(n, "UML.puml.linea", texto=decl.group(0))
        nombre = datos["nombre"]
        if herencia.group("padre"):
            self._nuevo(herencia.group("padre"), "clase", n)
            self.relaciones.append(Relacion("herencia", nombre, herencia.group("padre")))
        for interfaz in _partir_comas(herencia.group("ifs") or ""):
            self._nuevo(interfaz, "interfaz", n)
            self.relaciones.append(Relacion("realizacion", nombre, interfaz))
        if abre and not cierra_misma:
            self._cuerpo(datos, n)

    def _cuerpo(self, datos: dict, inicio: int) -> None:
        while self.pos < len(self.lineas):
            n, linea = self.lineas[self.pos]
            self.pos += 1
            if linea == "}":
                return
            if re.fullmatch(r"(--|==|\.\.|__)(.*\1)?", linea):
                continue  # separadores de compartimento
            if datos["tipo"] == "enumeracion":
                self._literales(datos, linea, n)
            else:
                self._miembro(datos, linea, n)
        raise error_linea(inicio, "UML.puml.sin_cierre", nombre=datos["nombre"])

    def _literales(self, datos: dict, linea: str, n: int) -> None:
        for pieza in _partir_comas(linea) if "(" not in linea else [linea]:
            m = re.fullmatch(r"([A-Za-z_]\w*)\s*(?:\((.*)\))?", pieza.strip())
            if m is None:
                raise error_linea(n, "UML.puml.miembro", texto=pieza, que="literal")
            params = _parametros(m.group(2) or "", n)
            datos["literales"].append(Literal(m.group(1), params))

    def _miembro(self, datos: dict, linea: str, n: int) -> None:
        texto = linea
        visibilidad = "+" if "(" in texto else "-"
        if texto[:1] in "+-#~":
            visibilidad = "+" if texto[0] == "~" else texto[0]
            texto = texto[1:].strip()
        estatico = abstracto = constante = creador = False
        while True:
            mod = re.match(r"^(\{(static|classifier|abstract)\}|<<create>>)\s*", texto)
            if mod is None:
                break
            estatico = estatico or mod.group(2) in ("static", "classifier")
            abstracto = abstracto or mod.group(2) == "abstract"
            creador = creador or mod.group(1) == "<<create>>"
            texto = texto[mod.end() :]
        if texto.endswith("{readOnly}") or texto.endswith("{final}"):
            constante = True
            texto = texto.rsplit("{", 1)[0].strip()
        if "(" in texto:
            self._operacion(datos, texto, visibilidad, estatico, abstracto, creador, n)
            return
        inicial = None
        if "=" in texto:
            texto, valor = (x.strip() for x in texto.split("=", 1))
            inicial = _valor(valor, n)
        nombre, tipo = _nombre_y_tipo(texto, n, "atributo")
        datos["atributos"].append(Atributo(nombre, tipo, visibilidad, estatico, constante, inicial))

    def _operacion(
        self,
        datos: dict,
        texto: str,
        vis: str,
        estatico: bool,
        abstracto: bool,
        creador: bool,
        n: int,
    ) -> None:
        m = re.fullmatch(
            r"(?:(?P<ret1>[\w\[\]]+)\s+)?(?P<nombre>[A-Za-z_]\w*)\s*\((?P<params>.*)\)"
            r"\s*(?::\s*(?P<ret2>[\w\[\]]+))?",
            texto,
        )
        if m is None:
            raise error_linea(n, "UML.puml.miembro", texto=texto, que="metodo")
        params = _parametros(m.group("params"), n)
        nombre = m.group("nombre")
        if creador or (nombre == datos["nombre"] and not m.group("ret1") and not m.group("ret2")):
            datos["constructores"].append(Constructor(vis, params))
            return
        retorno = _tipo(m.group("ret2") or m.group("ret1") or "void", n)
        datos["metodos"].append(Metodo(nombre, retorno, vis, params, estatico, abstracto))

    def _relacion(self, rel: re.Match, n: int) -> None:
        a, b = rel.group("a"), rel.group("b")
        flecha = re.sub(r"(up|down|left|right)", "", rel.group("flecha"))
        flecha = re.sub(r"-+", "-", re.sub(r"\.+", ".", flecha))
        tipos = {
            "<|-": ("herencia", b, a),
            "-|>": ("herencia", a, b),
            "<|.": ("realizacion", b, a),
            ".|>": ("realizacion", a, b),
            "*-": ("composicion", a, b),
            "-*": ("composicion", b, a),
            "o-": ("agregacion", a, b),
            "-o": ("agregacion", b, a),
            "->": ("asociacion", a, b),
            "<-": ("asociacion", b, a),
            "-": ("asociacion", a, b),
            ".>": ("dependencia", a, b),
            "<.": ("dependencia", b, a),
            ".": ("dependencia", a, b),
        }
        if flecha not in tipos:
            raise error_linea(n, "UML.puml.flecha", flecha=rel.group("flecha"))
        tipo, origen, destino = tipos[flecha]
        for nombre in (a, b):
            self._nuevo(nombre, "clase", n)
        if tipo not in ESTRUCTURALES:
            self.relaciones.append(Relacion(tipo, origen, destino))
            return
        cerca_destino = rel.group("mb") if destino == b else rel.group("ma")
        mult = "0..*" if cerca_destino and re.search(r"\*|\bn\b|many", cerca_destino) else "0..1"
        rol = (rel.group("etiqueta") or "").strip().strip("<>").strip()
        if not rol:
            rol = destino[0].lower() + destino[1:]
        if not _IDENT.match(rol):
            raise error_linea(n, "UML.puml.rol", rol=rol)
        self.relaciones.append(Relacion(tipo, origen, destino, rol, mult))

    def modelo(self, idioma: str) -> DiagramaClases:
        for d in self.clasificadores.values():
            for x in d["atributos"]:
                self._anotar_idioma(x.tipo)
            for x in d["metodos"]:
                self._anotar_idioma(x.retorno)
                for p in x.parametros:
                    self._anotar_idioma(p.tipo)
            for x in d["constructores"] + d["literales"]:
                for p in x.parametros:
                    self._anotar_idioma(p.tipo)
        if self.palabras_es != self.palabras_en:
            idioma = "es" if self.palabras_es > self.palabras_en else "en"
        nombres = set(self.clasificadores)

        def params(ps: tuple[Parametro, ...]) -> tuple[Parametro, ...]:
            return tuple(replace(p, tipo=_resolver(p.tipo, nombres)) for p in ps)

        clasificadores = tuple(
            Clasificador(
                d["nombre"],
                d["tipo"],
                d["genericos"],
                tuple(replace(a, tipo=_resolver(a.tipo, nombres)) for a in d["atributos"]),
                tuple(replace(k, parametros=params(k.parametros)) for k in d["constructores"]),
                tuple(
                    replace(
                        x, retorno=_resolver(x.retorno, nombres), parametros=params(x.parametros)
                    )
                    for x in d["metodos"]
                ),
                tuple(replace(x, parametros=params(x.parametros)) for x in d["literales"]),
            )
            for d in (self.clasificadores[k] for k in self.orden)
        )
        return normalizar(DiagramaClases(clasificadores, tuple(self.relaciones), idioma))


def leer_plantuml(texto: str, idioma: str = "es") -> DiagramaClases:
    """Modelo UML a partir de texto PlantUML; :class:`ErrorUML` con la línea si no se entiende.

    ``idioma`` es el idioma del modelo si los tipos escritos no lo delatan
    (``entero`` → es, ``int`` → en).
    """
    lector = _Lector(texto)
    lector.leer()
    if not lector.orden:
        raise ErrorUML("UML.puml.vacio")
    return lector.modelo(idioma)
