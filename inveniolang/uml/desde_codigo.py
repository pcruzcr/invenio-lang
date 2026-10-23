"""Código → modelo UML: clases, interfaces, enumeraciones y todas sus relaciones.

INV-3202: se construye desde el AST **antes** del análisis semántico (fase
``modulos``): el semántico reemplaza cada clase genérica por sus copias
especializadas (``Caja<entero>``) y convierte los tipos suma en clases, y el
diagrama debe mostrar lo que el estudiante escribió, no esa expansión
interna. Quien llama valida antes el programa completo (ver
:func:`inveniolang.uml.analizar`).

Criterio de las relaciones (documentado en ``docs/uml.md``):

* **herencia** (``hereda``) y **realización** (``implementa``).
* **composición**: un atributo de tipo ``T`` que la propia clase crea con
  ``nuevo T(...)`` en un constructor o en su inicialización: el todo crea a
  la parte y la parte vive con él.
* **agregación**: un atributo que recibe un objeto que llega como parámetro
  de un constructor o de un método (``este.motor = m``): la parte existe
  fuera del todo y puede compartirse.
* **asociación**: cualquier otro atributo cuyo tipo es un clasificador.
  Multiplicidad ``0..1`` para una referencia, ``0..*`` para un arreglo.
* **dependencia**: el clasificador aparece en una firma (parámetro o
  retorno) o en un cuerpo (variable local, ``nuevo``, acceso estático,
  ``emparejar``) sin que exista ya una de las relaciones anteriores.

La composición tiene prioridad sobre la agregación y esta sobre la
asociación.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from ..ast_nodes import (
    ArrayDecl,
    AssignStmt,
    ASTNode,
    CasoMatch,
    ClassDecl,
    EnumDecl,
    ForEachStmt,
    ForInitVar,
    Identifier,
    LambdaExpr,
    Literal,
    MatrixDecl,
    MemberAccess,
    MemberLValue,
    MethodCallExpr,
    MethodCallStmt,
    NewExpr,
    NullExpr,
    Parametro,
    ThisExpr,
    UnaryOp,
    VarDecl,
    VarLValue,
)
from . import modelo as m
from .reglas import multiplicidad_de, normalizar, tipo_base

__all__ = ["modelo_desde_ast"]


def _tipo_parametro(p: Parametro) -> str:
    return str(p.tipo) + ("[][]" if p.es_matriz else "[]" if p.es_arreglo else "")


def _parametros(params: list[Parametro]) -> tuple[m.Parametro, ...]:
    return tuple(m.Parametro(p.nombre, _tipo_parametro(p)) for p in params)


def _visibilidad(v: str) -> str:
    return "+" if v == "publico" else "-"


def _valor_inicial(expr: Any) -> m.ValorInicial | None:
    """Solo literales: lo demás depende de código que el diagrama no tiene."""
    if isinstance(expr, NullExpr):
        return m.ValorInicial("null", None)
    negativo = (
        isinstance(expr, UnaryOp)
        and expr.operador == "-"
        and isinstance(expr.operando, Literal)
        and expr.operando.tipo_literal in ("int", "float")
    )
    if negativo:
        lit = expr.operando
        return m.ValorInicial(lit.tipo_literal, -lit.valor)
    if isinstance(expr, Literal) and expr.tipo_literal in ("int", "float", "string", "bool"):
        valor = float(expr.valor) if expr.tipo_literal == "float" else expr.valor
        return m.ValorInicial(expr.tipo_literal, valor)
    return None


def _nodos(obj: Any, vistos: set[int] | None = None) -> Iterator[ASTNode]:
    """Recorre un subárbol completo (vía ``vars``), sin repetir nodos compartidos."""
    if vistos is None:
        vistos = set()
    pila = [obj]
    while pila:
        actual = pila.pop()
        if isinstance(actual, ASTNode):
            if id(actual) in vistos:
                continue
            vistos.add(id(actual))
            yield actual
            pila.extend(reversed(list(vars(actual).values())))
        elif isinstance(actual, (list, tuple)):
            pila.extend(reversed(actual))


def _locales(cuerpo: Any, params: list[Parametro]) -> set[str]:
    """Nombres que un cuerpo declara (para no confundir ``x.f()`` con un acceso estático)."""
    nombres = {p.nombre for p in params}
    for n in _nodos(cuerpo):
        if isinstance(n, (VarDecl, ArrayDecl, MatrixDecl, ForInitVar, ForEachStmt, Parametro)):
            nombres.add(n.nombre)
        elif isinstance(n, CasoMatch):
            nombres.update(n.ligaduras)
    return nombres


class _Constructor:
    """Arma el modelo de un programa (Builder)."""

    def __init__(self, ast: Any, idioma: str):
        self.ast = ast
        self.idioma = idioma
        decls: list[Any] = list(ast.clases) + list(ast.enums)
        # Orden estable: primero los módulos importados (en el orden en que se
        # enlazaron), después el programa, cada grupo por posición en su archivo.
        archivos: list[str] = []
        for d in decls:
            origen = getattr(d, "archivo_origen", None)
            if origen is not None and origen not in archivos:
                archivos.append(origen)

        def clave(d: Any) -> tuple[int, int, int]:
            origen = getattr(d, "archivo_origen", None)
            grupo = archivos.index(origen) if origen is not None else len(archivos)
            return grupo, d.linea, d.columna

        self.decls = sorted(decls, key=clave)
        self.nombres = {d.nombre for d in self.decls}
        # Variante de tipo suma → su enumeración (nuevo Circulo(2) usa Forma).
        self.variantes = {
            v.nombre: e.nombre for e in ast.enums for v in e.valores if isinstance(e, EnumDecl)
        }
        self.relaciones: list[m.Relacion] = []

    def construir(self) -> m.DiagramaClases:
        clasificadores = [self._clasificador(d) for d in self.decls]
        for d in self.decls:
            if isinstance(d, ClassDecl):
                self._jerarquia(d)
        for d in self.decls:
            if isinstance(d, ClassDecl):
                self._estructurales(d)
        for d in self.decls:
            if isinstance(d, ClassDecl):
                self._dependencias(d)
        modelo = m.DiagramaClases(tuple(clasificadores), tuple(self.relaciones), self.idioma)
        return normalizar(modelo)

    # ------------------------------------------------------------ clasificadores

    def _clasificador(self, d: Any) -> m.Clasificador:
        modulo = getattr(d, "archivo_origen", None)
        if isinstance(d, EnumDecl):
            literales = tuple(m.Literal(v.nombre, _parametros(v.parametros)) for v in d.valores)
            return m.Clasificador(d.nombre, "enumeracion", literales=literales, modulo=modulo)
        tipo = "interfaz" if d.es_interfaz else "abstracta" if d.es_abstracta else "clase"
        atributos = tuple(
            m.Atributo(
                a.nombre,
                str(a.tipo),
                _visibilidad(a.visibilidad),
                bool(a.es_estatico),
                False,
                _valor_inicial(a.init_expr),
            )
            for a in d.atributos
        )
        constructores = tuple(
            m.Constructor(_visibilidad(c.visibilidad), _parametros(c.parametros))
            for c in d.constructores
        )
        metodos = tuple(
            m.Metodo(
                x.nombre,
                str(x.tipo_retorno),
                _visibilidad(x.visibilidad),
                _parametros(x.parametros),
                bool(x.es_estatico),
                bool(x.es_abstracto),
            )
            for x in d.metodos
        )
        parametros_tipo = (d.parametro_tipo,) if d.parametro_tipo else ()
        return m.Clasificador(
            d.nombre, tipo, parametros_tipo, atributos, constructores, metodos, modulo=modulo
        )

    # ------------------------------------------------------------ relaciones

    def _agregar(self, r: m.Relacion) -> None:
        if r not in self.relaciones:
            self.relaciones.append(r)

    def _jerarquia(self, d: ClassDecl) -> None:
        if d.padre and d.padre in self.nombres:
            self._agregar(m.Relacion("herencia", d.nombre, d.padre))
        for interfaz in d.interfaces:
            if interfaz in self.nombres:
                self._agregar(m.Relacion("realizacion", d.nombre, interfaz))

    @staticmethod
    def _miembros_con_cuerpo(d: ClassDecl) -> Iterator[tuple[Any, bool]]:
        """(miembro, es_constructor) de todo constructor y método con cuerpo."""
        for c in d.constructores:
            yield c, True
        for x in d.metodos:
            if x.bloque is not None:
                yield x, False

    @staticmethod
    def _asigna_atributo(n: AssignStmt, atributo: str, locales: set[str]) -> bool:
        """``n`` asigna ``este.atributo`` (o ``atributo`` a secas si no lo tapa un local)."""
        if n.operador != "=":
            return False
        lv = n.lvalue
        if isinstance(lv, MemberLValue):
            return isinstance(lv.receptor, ThisExpr) and lv.nombre_miembro == atributo
        return isinstance(lv, VarLValue) and lv.nombre == atributo and atributo not in locales

    def _estructurales(self, d: ClassDecl) -> None:
        for a in d.atributos:
            base = tipo_base(str(a.tipo))
            if base not in self.nombres or base == d.parametro_tipo:
                continue
            compone = isinstance(a.init_expr, NewExpr) and a.init_expr.nombre_clase == base
            agrega = False
            for miembro, es_ctor in self._miembros_con_cuerpo(d):
                params = {p.nombre for p in miembro.parametros}
                locales = _locales(miembro.bloque, miembro.parametros) - params
                for n in _nodos(miembro.bloque):
                    if not isinstance(n, AssignStmt) or not self._asigna_atributo(
                        n, a.nombre, locales
                    ):
                        continue
                    expr = n.expr
                    if es_ctor and isinstance(expr, NewExpr) and expr.nombre_clase == base:
                        compone = True
                    elif isinstance(expr, Identifier) and expr.nombre in params:
                        agrega = True
            tipo = "composicion" if compone else "agregacion" if agrega else "asociacion"
            self._agregar(m.Relacion(tipo, d.nombre, base, a.nombre, multiplicidad_de(a.tipo)))

    def _usos(self, d: ClassDecl) -> list[str]:
        """Clasificadores que ``d`` menciona en firmas y cuerpos, en orden de aparición."""
        usados: list[str] = []

        def anotar(tipo: Any) -> None:
            if not isinstance(tipo, str):
                return
            for pieza in re.split(r"[<>,()\-]", tipo):
                base = tipo_base(pieza)
                base = self.variantes.get(base, base)
                if base in self.nombres and base != d.nombre and base != d.parametro_tipo:
                    if base not in usados:
                        usados.append(base)

        for x in d.metodos:
            anotar(x.tipo_retorno)
            for p in x.parametros:
                anotar(p.tipo)
        for c in d.constructores:
            for p in c.parametros:
                anotar(p.tipo)
        for miembro, _ in self._miembros_con_cuerpo(d):
            locales = _locales(miembro.bloque, miembro.parametros)
            for n in _nodos(miembro.bloque):
                if isinstance(n, (VarDecl, ArrayDecl, MatrixDecl, ForInitVar, ForEachStmt)):
                    anotar(n.tipo)
                elif isinstance(n, Parametro):
                    anotar(n.tipo)
                elif isinstance(n, LambdaExpr):
                    anotar(n.tipo_retorno)
                elif isinstance(n, NewExpr):
                    anotar(n.nombre_clase)
                elif isinstance(n, CasoMatch):
                    anotar(n.nombre_variante)
                elif isinstance(n, (MemberAccess, MethodCallExpr, MethodCallStmt)):
                    r = n.receptor
                    if isinstance(r, Identifier) and r.nombre not in locales:
                        anotar(r.nombre)
        for a in d.atributos:
            if a.init_expr is not None:
                for n in _nodos(a.init_expr):
                    if isinstance(n, NewExpr):
                        anotar(n.nombre_clase)
        return usados

    def _dependencias(self, d: ClassDecl) -> None:
        for destino in self._usos(d):
            self._agregar(m.Relacion("dependencia", d.nombre, destino))


def modelo_desde_ast(ast: Any, idioma: str = "es") -> m.DiagramaClases:
    """Modelo UML del programa ``ast`` (AST de la fase ``modulos``)."""
    return _Constructor(ast, idioma).construir()
