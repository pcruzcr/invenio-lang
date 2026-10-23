"""Reglas del diagrama de clases: normalización y validación para generar código.

INV-3201: un diagrama llega de tres fuentes (el analizador de código, un
JSON escrito a mano o por otra herramienta, y PlantUML) y no todas dicen lo
mismo con el mismo detalle: PlantUML suele dibujar una asociación sin
declarar el atributo, o declarar el atributo sin la flecha; un JSON puede
traer ``sobrescribe`` desactualizado. :func:`normalizar` completa esas
piezas de forma determinista (y es idempotente: un modelo que sale del
código ya está normalizado). :func:`validar_generable` comprueba, antes de
escribir una sola línea, que InvenioLang puede expresar el diagrama, y
explica en el idioma del estudiante qué no se puede y por qué, en vez de
generar código que luego no compila.
"""

from __future__ import annotations

import re
from dataclasses import replace

from ..i18n import M
from ..lexer import Lexer
from .modelo import (
    ESTRUCTURALES,
    JERARQUICAS,
    PRIMITIVOS,
    Atributo,
    Clasificador,
    DiagramaClases,
    ErrorUML,
    Metodo,
    Relacion,
)

__all__ = ["abstractos_pendientes", "error_linea", "normalizar", "tipo_base", "validar_generable"]

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
# Palabras que no pueden nombrar nada: las reservadas de ambos idiomas, las
# reservadas futuras y `main` (KW_MAIN).
RESERVADAS = frozenset(Lexer.keywords) | frozenset(Lexer.reservadas_futuras)


def tipo_base(tipo: str) -> str:
    """Nombre del tipo sin ``[]`` ni argumentos genéricos (``Caja<entero>`` → ``Caja``)."""
    return tipo.split("<", 1)[0].replace("[]", "").strip()


def multiplicidad_de(tipo: str) -> str:
    """``0..*`` para un arreglo de objetos, ``0..1`` para una sola referencia."""
    return "0..*" if tipo.endswith("[]") else "0..1"


def _sobrescribe(modelo: DiagramaClases, clase: Clasificador, metodo: Metodo) -> bool:
    if metodo.estatico or clase.tipo == "interfaz":
        return False
    for nombre in modelo.supertipos(clase.nombre):
        sup = modelo.clasificador(nombre)
        if sup is None:
            continue
        for otro in sup.metodos:
            if not otro.estatico and otro.firma == metodo.firma:
                return True
    return False


def normalizar(modelo: DiagramaClases) -> DiagramaClases:
    """Completa y hace coherente un diagrama (idempotente).

    * Los métodos de una interfaz son abstractos.
    * Cada atributo cuyo tipo es otro clasificador tiene una relación
      estructural con ``rol`` = su nombre (asociación si no se indicó otra);
      su multiplicidad sale del tipo del atributo (``[]`` → ``0..*``).
    * Una relación estructural cuyo ``rol`` no es un atributo crea ese
      atributo (privado, del tipo destino).
    * Se quitan relaciones repetidas y las dependencias que ya expresa una
      relación más fuerte entre los mismos clasificadores.
    * ``sobrescribe`` se recalcula.
    """
    nombres = {c.nombre for c in modelo.clasificadores}
    relaciones: list[Relacion] = []
    for r in modelo.relaciones:
        if r not in relaciones:
            relaciones.append(r)
    clasificadores: list[Clasificador] = []
    for c in modelo.clasificadores:
        atributos = list(c.atributos)
        propios = [r for r in relaciones if r.origen == c.nombre and r.tipo in ESTRUCTURALES]
        for r in propios:
            if all(a.nombre != r.rol for a in atributos) and r.rol is not None:
                sufijo = "[]" if r.multiplicidad == "0..*" else ""
                atributos.append(Atributo(r.rol, r.destino + sufijo))
        for a in atributos:
            base = tipo_base(a.tipo)
            if base not in nombres or base in c.parametros_tipo:
                continue
            mult = multiplicidad_de(a.tipo)
            existentes = [r for r in propios if r.rol == a.nombre]
            if not existentes:
                nueva = Relacion("asociacion", c.nombre, base, a.nombre, mult)
                relaciones.append(nueva)
                propios.append(nueva)
                continue
            for r in existentes:
                arreglada = replace(r, destino=base, multiplicidad=mult)
                if arreglada != r:
                    relaciones[relaciones.index(r)] = arreglada
        metodos = c.metodos
        if c.tipo == "interfaz":
            metodos = tuple(replace(m, abstracto=True, estatico=False) for m in metodos)
        clasificadores.append(replace(c, atributos=tuple(atributos), metodos=metodos))
    # Un atributo con el mismo rol no puede tener dos relaciones estructurales.
    vistos_rol: set[tuple[str, str | None]] = set()
    depuradas: list[Relacion] = []
    for r in relaciones:
        if r.tipo in ESTRUCTURALES:
            clave = (r.origen, r.rol)
            if clave in vistos_rol:
                continue
            vistos_rol.add(clave)
        depuradas.append(r)
    fuertes = {
        (r.origen, r.destino) for r in depuradas if r.tipo in ESTRUCTURALES or r.tipo in JERARQUICAS
    }
    depuradas = [
        r
        for r in depuradas
        if r.tipo != "dependencia"
        or ((r.origen, r.destino) not in fuertes and r.origen != r.destino)
    ]
    previo = replace(modelo, clasificadores=tuple(clasificadores), relaciones=tuple(depuradas))
    finales = tuple(
        replace(
            c,
            metodos=tuple(replace(m, sobrescribe=_sobrescribe(previo, c, m)) for m in c.metodos),
        )
        for c in previo.clasificadores
    )
    return replace(previo, clasificadores=finales)


# ----------------------------------------------------------------- validación


class _Validador:
    """Acumula todos los problemas (no solo el primero) para explicarlos juntos."""

    def __init__(self, modelo: DiagramaClases):
        self.m = modelo
        self.errores: list[ErrorUML] = []
        self.tipos = {c.nombre: c.tipo for c in modelo.clasificadores}

    def error(self, clave: str, **args: object) -> None:
        self.errores.append(ErrorUML(clave, **args))

    def nombre(self, nombre: str, donde: str) -> None:
        if not _IDENT.match(nombre):
            self.error("UML.val.identificador", nombre=nombre, donde=donde)
        elif nombre in RESERVADAS:
            self.error("UML.val.reservada", nombre=nombre, donde=donde)

    def tipo(self, tipo: str, donde: str, clase: Clasificador, contexto: str) -> None:
        """``contexto``: atributo, parametro, retorno o carga (cada uno admite tipos distintos)."""
        dims = tipo.count("[]")
        base = tipo.replace("[]", "")
        if "<" in tipo or not _IDENT.match(base) or not tipo.endswith("[]" * dims):
            self.error("UML.val.tipo_invalido", tipo=tipo, donde=donde)
            return
        if base == "void":
            if contexto != "retorno" or dims:
                self.error("UML.val.void", donde=donde)
            return
        conocido = base in PRIMITIVOS or base in self.tipos or base in clase.parametros_tipo
        if not conocido:
            self.error("UML.val.tipo_desconocido", tipo=tipo, donde=donde)
            return
        es_objeto = base not in PRIMITIVOS
        permitido = {
            "atributo": dims == 0 or (dims == 1 and not es_objeto),
            "parametro": dims <= 1 or (dims == 2 and not es_objeto),
            "retorno": dims == 0,
            "carga": dims == 0,
        }[contexto]
        if not permitido:
            clave = (
                "UML.val.arreglo_objetos"
                if es_objeto and contexto == "atributo"
                else ("UML.val.arreglo_no_admitido")
            )
            self.error(clave, tipo=tipo, donde=donde)

    def parametros(self, params: tuple, donde: str, clase: Clasificador, contexto: str) -> None:
        nombres: list[str] = []
        for p in params:
            self.nombre(p.nombre, donde)
            if p.nombre in nombres:
                self.error("UML.val.parametro_repetido", nombre=p.nombre, donde=donde)
            nombres.append(p.nombre)
            self.tipo(p.tipo, f"{donde} · {p.nombre}", clase, contexto)

    def clasificador(self, c: Clasificador) -> None:
        self.nombre(c.nombre, c.nombre)
        for t_param in c.parametros_tipo:
            self.nombre(t_param, c.nombre)
            if t_param in self.tipos:
                self.error("UML.val.parametro_tipo_choca", nombre=t_param, clase=c.nombre)
        if len(c.parametros_tipo) > 1:
            self.error("UML.val.un_parametro_tipo", clase=c.nombre)
        if c.parametros_tipo and c.tipo != "clase":
            self.error("UML.val.generico_solo_clase", clase=c.nombre)
        if c.tipo == "enumeracion":
            self.enumeracion(c)
            return
        if c.literales:
            self.error("UML.val.literales_fuera_de_enum", clase=c.nombre)
        vistos: list[str] = []
        for a in c.atributos:
            donde = f"{c.nombre}.{a.nombre}"
            self.nombre(a.nombre, donde)
            if a.nombre in vistos:
                self.error("UML.val.atributo_repetido", nombre=a.nombre, clase=c.nombre)
            vistos.append(a.nombre)
            self.tipo(a.tipo, donde, c, "atributo")
        firmas: list[tuple[str, ...]] = []
        for ctor in c.constructores:
            donde = f"{c.nombre}({', '.join(p.tipo for p in ctor.parametros)})"
            self.parametros(ctor.parametros, donde, c, "parametro")
            firma = tuple(p.tipo for p in ctor.parametros)
            if firma in firmas:
                self.error("UML.val.constructor_repetido", donde=donde)
            firmas.append(firma)
        metodos: list[tuple[str, tuple[str, ...]]] = []
        for m in c.metodos:
            donde = f"{c.nombre}.{m.nombre}"
            self.nombre(m.nombre, donde)
            self.parametros(m.parametros, donde, c, "parametro")
            self.tipo(m.retorno, donde, c, "retorno")
            if m.firma in metodos:
                self.error("UML.val.metodo_repetido", donde=donde)
            if m.nombre in vistos:
                self.error("UML.val.miembro_repetido", nombre=m.nombre, clase=c.nombre)
            metodos.append(m.firma)
            if m.abstracto and m.estatico:
                self.error("UML.val.abstracto_estatico", donde=donde)
            if m.abstracto and c.tipo == "clase":
                self.error("UML.val.abstracto_en_concreta", donde=donde, clase=c.nombre)
        if c.tipo == "interfaz":
            if c.atributos:
                self.error("UML.val.interfaz_atributos", clase=c.nombre)
            if c.constructores:
                self.error("UML.val.interfaz_constructores", clase=c.nombre)
            for m in c.metodos:
                if m.visibilidad != "+":
                    self.error("UML.val.interfaz_publica", donde=f"{c.nombre}.{m.nombre}")

    def enumeracion(self, c: Clasificador) -> None:
        if not c.literales:
            self.error("UML.val.enum_vacia", clase=c.nombre)
        if c.atributos or c.constructores or c.metodos:
            self.error("UML.val.enum_miembros", clase=c.nombre)
        vistos: list[str] = []
        for lit in c.literales:
            donde = f"{c.nombre}.{lit.nombre}"
            self.nombre(lit.nombre, donde)
            if lit.nombre in vistos or lit.nombre in self.tipos:
                self.error("UML.val.literal_repetido", nombre=lit.nombre, clase=c.nombre)
            vistos.append(lit.nombre)
            self.parametros(lit.parametros, donde, c, "carga")

    def relaciones(self) -> None:
        padres: dict[str, str] = {}
        for r in self.m.relaciones:
            origen, destino = self.tipos.get(r.origen), self.tipos.get(r.destino)
            if r.tipo == "herencia":
                if origen not in ("clase", "abstracta") or destino not in ("clase", "abstracta"):
                    self.error("UML.val.herencia_tipos", origen=r.origen, destino=r.destino)
                if r.origen in padres:
                    self.error("UML.val.herencia_multiple", clase=r.origen)
                padres[r.origen] = r.destino
                for nombre in (r.origen, r.destino):
                    c = self.m.clasificador(nombre)
                    if c is not None and c.parametros_tipo:
                        self.error("UML.val.generico_sin_herencia", clase=nombre)
            elif r.tipo == "realizacion":
                if origen not in ("clase", "abstracta") or destino != "interfaz":
                    self.error("UML.val.realizacion_tipos", origen=r.origen, destino=r.destino)
                c = self.m.clasificador(r.origen)
                if c is not None and c.parametros_tipo:
                    self.error("UML.val.generico_sin_herencia", clase=r.origen)
        for inicio in padres:
            visto = {inicio}
            actual = padres.get(inicio)
            while actual is not None:
                if actual in visto:
                    self.error("UML.val.ciclo_herencia", clase=inicio)
                    break
                visto.add(actual)
                actual = padres.get(actual)


def validar_generable(modelo: DiagramaClases) -> list[ErrorUML]:
    """Problemas que impiden generar código InvenioLang que compile (lista vacía si ninguno)."""
    v = _Validador(modelo)
    if not modelo.clasificadores:
        v.error("UML.val.vacio")
    for c in modelo.clasificadores:
        v.clasificador(c)
    v.relaciones()
    # Mismo mensaje dos veces (p. ej. un tipo desconocido repetido) no ayuda.
    unicos: list[ErrorUML] = []
    textos: set[str] = set()
    for e in v.errores:
        if str(e) not in textos:
            textos.add(str(e))
            unicos.append(e)
    return unicos


def abstractos_pendientes(modelo: DiagramaClases, clase: Clasificador) -> list[tuple[str, Metodo]]:
    """Métodos abstractos heredados que ``clase`` (concreta) aún no implementa.

    Recorre la cadena de superclases y todas las interfaces (también las de
    los ancestros); un método cuenta como implementado si la propia clase o
    una superclase declara la misma firma sin ``abstracto``.
    """
    concretos: set[tuple[str, tuple[str, ...]]] = set()
    cadena: list[Clasificador] = [clase]
    actual = modelo.padre(clase.nombre)
    while actual is not None and len(cadena) < len(modelo.clasificadores) + 1:
        c = modelo.clasificador(actual)
        if c is None:
            break
        cadena.append(c)
        actual = modelo.padre(actual)
    for c in cadena:
        concretos.update(m.firma for m in c.metodos if not m.abstracto and not m.estatico)
    faltan: list[tuple[str, Metodo]] = []
    for nombre in modelo.supertipos(clase.nombre):
        sup = modelo.clasificador(nombre)
        if sup is None:
            continue
        for m in sup.metodos:
            if m.abstracto and m.firma not in concretos:
                concretos.add(m.firma)
                faltan.append((nombre, m))
    return faltan


# Errores de una sola pieza reutilizados por el lector de PlantUML.
def error_linea(linea: int, clave: str, **args: object) -> ErrorUML:
    """Error de PlantUML situado en ``linea`` (el detalle es otro mensaje del catálogo)."""
    return ErrorUML("UML.puml.error", linea=linea, detalle=M(clave, **args))
