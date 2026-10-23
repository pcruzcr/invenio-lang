"""Análisis estático de complejidad temporal (cota superior didáctica).

INV-1015: la versión anterior solo contaba la profundidad de bucles, devolvía
``O(n log n)`` si el texto del árbol contenía la palabra "merge" y añadía un
campo ``empirico`` con una frase fija. Ahora el análisis es real:

* **Bucles**: cada ciclo multiplica por ``n``; si el ciclo actualiza su
  variable de control con ``*`` o ``/`` (``i = i * 2``, ``n /= 2``) multiplica
  por ``log n``; si itera entre literales (``para (i = 0; i < 10; i++)``) es
  ``O(1)``.
* **Llamadas**: el costo de una subrutina llamada se compone con el del
  contexto (dentro de dos ciclos, una llamada ``O(n)`` aporta ``O(n³)``).
* **Recursión** (directa o mutua, por componentes fuertemente conexas del
  grafo de llamadas): se cuenta cuántas llamadas recursivas se ejecutan en un
  mismo camino y cómo cambia el argumento. ``n - 1`` con una llamada →
  ``n·f(n)``; con dos o más → ``O(2^n)``; ``n / 2`` → teorema maestro
  (búsqueda binaria ``O(log n)``, mergesort ``O(n log n)``). Una llamada
  recursiva dentro de un ciclo (backtracking) se marca exponencial.
* **Memoización** (INV-4405): si antes de la primera llamada recursiva un
  ``si`` consulta una tabla indexada por los parámetros y retorna (``si
  (calculado[n]) { retornar memo[n]; }``), y la subrutina guarda en esa tabla
  con los mismos índices, cada subproblema se resuelve una vez: el costo es
  (número de estados ``n^d``, d = dimensiones de la tabla) × (trabajo propio
  de una llamada). Fibonacci memoizado deja de salir ``O(2^n)`` y es ``O(n)``.
* **Ciclos amortizados** (INV-4405): un ``mientras`` dentro de otro ciclo cuya
  variable de control se declara FUERA del ciclo externo, nunca se reinicia
  en él (solo se incrementa) y dentro del ``mientras`` solo avanza en un
  sentido (KMP: ``k = pi[k - 1]``; dos punteros: ``j++``) suma O(n) vueltas
  EN TOTAL, no por cada vuelta externa: aporta ×1 y KMP queda ``O(n)``. En
  el caso KMP se ASUME que el ciclo interno hace bajar la variable (la tabla
  no se analiza); la nota lo dice.

Límites (también en la salida al estudiante, clave ``COMP.limites``): no se
conocen los valores reales ni el tamaño de la entrada, todos los tamaños se
llaman ``n``, la memoización solo se reconoce con tablas indexadas
directamente por los parámetros y un patrón no reconocido da una cota MAYOR
que la real (nunca menor, salvo las suposiciones marcadas).

Es una COTA estimada para enseñar a razonar, no una prueba: cada resultado
lleva las notas (es/en) que explican de dónde sale.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .ast_nodes import (
    ArrayAccess,
    ArrayLValue,
    AssignStmt,
    ASTNode,
    BinaryOp,
    CallStmt,
    DoWhileStmt,
    ForEachStmt,
    ForInitAsig,
    ForInitIncDec,
    ForInitVar,
    ForStmt,
    FunctionCall,
    Identifier,
    IfStmt,
    IncDecStmt,
    Literal,
    MatrixAccess,
    MatrixLValue,
    ReadStmt,
    ReturnStmt,
    SwitchStmt,
    TernaryExpr,
    UnaryOp,
    VarDecl,
    WhileStmt,
)
from .i18n import t

__all__ = ["Costo", "ResultadoComplejidad", "analizar_complejidad", "describir", "hijos"]

_BUCLES = (ForStmt, WhileStmt, DoWhileStmt, ForEachStmt)
_COMPARADORES = {"<", "<=", ">", ">=", "!="}


def hijos(nodo: Any) -> Iterator[ASTNode]:
    """Hijos directos de un nodo del AST (en orden de declaración de atributos).

    Recorre genéricamente los atributos del nodo, incluidas listas anidadas
    (``init_filas`` de una matriz), para no depender de una lista de nombres
    que se desactualiza al añadir nodos al lenguaje.
    """
    pendientes = list(vars(nodo).values()) if hasattr(nodo, "__dict__") else []
    while pendientes:
        valor = pendientes.pop(0)
        if isinstance(valor, ASTNode):
            yield valor
        elif isinstance(valor, (list, tuple)):
            pendientes[0:0] = list(valor)


def recorrer(nodo: Any) -> Iterator[ASTNode]:
    """Recorrido en preorden de ``nodo`` y todos sus descendientes."""
    pila = [nodo]
    while pila:
        actual = pila.pop()
        if isinstance(actual, ASTNode):
            yield actual
            pila.extend(reversed(list(hijos(actual))))


@dataclass(frozen=True, order=True)
class Costo:
    """Cota ``O(2^n)`` si ``exponencial``; si no ``O(n^grado · log^log n)``."""

    exponencial: bool = False
    grado: float = 0
    log: int = 0

    def por(self, otro: Costo) -> Costo:
        """Producto de costos (anidamiento)."""
        if self.exponencial or otro.exponencial:
            return EXPONENCIAL
        return Costo(False, self.grado + otro.grado, self.log + otro.log)

    def __str__(self) -> str:
        if self.exponencial:
            return "O(2^n)"
        partes = []
        if self.grado:
            g = int(self.grado) if float(self.grado).is_integer() else round(self.grado, 2)
            sup = {1: "", 2: "²", 3: "³"}.get(g, f"^{g}") if isinstance(g, int) else f"^{g}"
            partes.append(f"n{sup}")
        if self.log:
            partes.append("log n" if self.log == 1 else f"log^{self.log} n")
        return f"O({' '.join(partes) or '1'})"


CONSTANTE = Costo()
LINEAL = Costo(grado=1)
LOGARITMICO = Costo(log=1)
EXPONENCIAL = Costo(exponencial=True)

# Las notas se presentan con el catálogo i18n (claves COMP.<clave>), el
# mecanismo único de idioma del proyecto (INV-1400).


@dataclass
class ResultadoComplejidad:
    """Estimación de una subrutina con la explicación de su origen."""

    subrutina: str
    costo: Costo
    recursiva: bool = False
    notas: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    @property
    def estimado(self) -> str:
        """Cota en notación O, p. ej. ``O(n log n)``."""
        return str(self.costo)


def _subrutinas(ast: Any) -> dict[str, Any]:
    subs: dict[str, Any] = {s.nombre: s for s in ast.subrutinas}
    if ast.main is not None:
        subs["main"] = ast.main
    for clase in ast.clases:
        for met in clase.metodos:
            if met.bloque is not None:
                subs[f"{clase.nombre}.{met.nombre}"] = met
    return subs


def _llamadas(nodo: Any, nombres: set[str]) -> set[str]:
    return {
        n.nombre
        for n in recorrer(nodo)
        if isinstance(n, (FunctionCall, CallStmt)) and n.nombre in nombres
    }


def _componentes(grafo: dict[str, set[str]]) -> dict[str, frozenset[str]]:
    """Componente fuertemente conexa de cada nodo (Tarjan iterativo simple)."""
    indice: dict[str, int] = {}
    bajo: dict[str, int] = {}
    pila: list[str] = []
    en_pila: set[str] = set()
    comp: dict[str, frozenset[str]] = {}
    contador = 0

    def visitar(v: str) -> None:
        nonlocal contador
        indice[v] = bajo[v] = contador
        contador += 1
        pila.append(v)
        en_pila.add(v)
        for w in sorted(grafo[v]):
            if w not in indice:
                visitar(w)
                bajo[v] = min(bajo[v], bajo[w])
            elif w in en_pila:
                bajo[v] = min(bajo[v], indice[w])
        if bajo[v] == indice[v]:
            miembros = []
            while True:
                w = pila.pop()
                en_pila.discard(w)
                miembros.append(w)
                if w == v:
                    break
            for w in miembros:
                comp[w] = frozenset(miembros)

    for v in sorted(grafo):
        if v not in indice:
            visitar(v)
    return comp


def _variables(expr: Any) -> set[str]:
    return {n.nombre for n in recorrer(expr) if isinstance(n, Identifier)}


def _escala_variable(stmt: Any, variables: set[str]) -> bool:
    """True si ``stmt`` multiplica o divide una de ``variables``."""
    if isinstance(stmt, (AssignStmt, ForInitAsig)):
        nombre = getattr(stmt.lvalue, "nombre", None)
        if nombre not in variables:
            return False
        if stmt.operador in ("*=", "/="):
            return True
        expr = stmt.expr
        return (
            isinstance(expr, BinaryOp)
            and expr.operador in ("*", "/", ">>", "<<")
            and nombre in _variables(expr)
        )
    return False


def _factor_bucle(bucle: Any) -> tuple[Costo, str]:
    if isinstance(bucle, ForEachStmt):
        return LINEAL, "bucle"
    cond = bucle.cond_expr if isinstance(bucle, ForStmt) else bucle.condicion
    variables = _variables(cond) if cond is not None else set()
    if isinstance(bucle, ForStmt) and _limites_literales(bucle):
        return CONSTANTE, "bucle_cte"
    nodos = [
        n for parte in (bucle.bloque, getattr(bucle, "act_stmt", None)) for n in recorrer(parte)
    ]
    if any(_escala_variable(n, variables) for n in nodos):
        return LOGARITMICO, "bucle_log"
    # Búsqueda binaria (`medio = (ini + fin) / 2; ini = medio + 1`) o montículo
    # (`hijo = 2 * i + 1; ...; i = mayor`): la variable de control se escala
    # a través de variables intermedias. Se propaga el "escalado" por las
    # asignaciones hasta un punto fijo.
    asignaciones = list(_asignaciones(nodos))
    escaladas = {nombre for nombre, expr in asignaciones if _escala(expr)}
    cambio = True
    while cambio:
        cambio = False
        for nombre, expr in asignaciones:
            if nombre not in escaladas and _variables(expr) & escaladas:
                escaladas.add(nombre)
                cambio = True
    if not variables:
        # `mientras (verdadero) { ... romper; }`: controlan las condiciones internas.
        variables = {v for n in nodos if isinstance(n, IfStmt) for v in _variables(n.condicion)}
    if variables & escaladas:
        return LOGARITMICO, "bucle_log"
    return LINEAL, "bucle"


def _asignaciones(nodos: list[Any]) -> Iterator[tuple[str | None, Any]]:
    """Pares (variable, expresión) de declaraciones con valor y asignaciones."""
    for n in nodos:
        if isinstance(n, VarDecl) and n.init_expr is not None:
            yield n.nombre, n.init_expr
        elif isinstance(n, AssignStmt):
            yield getattr(n.lvalue, "nombre", None), n.expr


def _limites_literales(bucle: ForStmt) -> bool:
    """``para (i = 0; i < 10; ...)``: inicio y límite literales."""
    init, cond = bucle.init_stmt, bucle.cond_expr
    inicio = getattr(init, "init_expr", None) if isinstance(init, ForInitVar) else None
    if isinstance(init, ForInitAsig):
        inicio = init.expr
    if not isinstance(inicio, Literal) or not isinstance(cond, BinaryOp):
        return False
    return cond.operador in _COMPARADORES and (
        isinstance(cond.izquierda, Literal) or isinstance(cond.derecha, Literal)
    )


class _Analizador:
    """Calcula el costo de cada subrutina con memoización sobre el grafo de llamadas."""

    def __init__(self, ast: Any) -> None:
        self.subs = _subrutinas(ast)
        nombres = set(self.subs)
        self.grafo = {n: _llamadas(s.bloque, nombres) for n, s in self.subs.items()}
        self.scc = _componentes(self.grafo)
        self.resultados: dict[str, ResultadoComplejidad] = {}

    def costo_de(self, nombre: str) -> ResultadoComplejidad:
        if nombre not in self.resultados:
            res = ResultadoComplejidad(nombre, CONSTANTE)
            self.resultados[nombre] = res  # corta ciclos durante el cálculo
            self._calcular(res)
        return self.resultados[nombre]

    def _recursivos(self, nombre: str) -> frozenset[str]:
        grupo = self.scc.get(nombre, frozenset())
        if len(grupo) > 1 or nombre in self.grafo.get(nombre, set()):
            return grupo
        return frozenset()

    def _calcular(self, res: ResultadoComplejidad) -> None:
        sub = self.subs[res.subrutina]
        grupo = self._recursivos(res.subrutina)
        local = self._costo(sub.bloque, grupo, res.notas)
        if not grupo:
            res.costo = local
            return
        res.recursiva = True
        for otro in sorted(grupo - {res.subrutina}):
            res.notas.append(("rec_mutua", {"nombre": otro}))
        memo = _memoizada(sub, grupo)
        if memo is not None:
            tabla, dims = memo
            estados = Costo(grado=dims)
            res.notas.append(("rec_memo", {"tabla": tabla, "estados": str(estados)}))
            res.costo = estados.por(local)
            return
        if any(
            self._rec_en_bucle(b, grupo) for b in recorrer(sub.bloque) if isinstance(b, _BUCLES)
        ):
            res.notas.append(("rec_en_bucle", {}))
            res.costo = EXPONENCIAL
            return
        k = max(1, self._llamadas_por_camino(sub.bloque, grupo))
        forma = self._forma(sub, grupo)
        if forma == "otro" and k >= 2:
            res.notas.append(("rec_supuesta", {}))
            forma = "division"
        if forma == "division":
            res.notas.append(("rec_division", {"k": k}))
            res.costo = _maestro(k, local)
        else:
            res.notas.append(("rec_resta", {"k": k}))
            res.costo = EXPONENCIAL if k >= 2 else local.por(LINEAL)

    def _costo(self, nodo: Any, grupo: frozenset[str], notas: list, externo: Any = None) -> Costo:
        """Costo de ejecutar ``nodo`` una vez (máximo sobre sus partes).

        ``externo`` es el ciclo más interno que contiene a ``nodo`` (para
        reconocer ciclos amortizados, INV-4405).
        """
        if nodo is None:
            return CONSTANTE
        if isinstance(nodo, _BUCLES):
            factor, clave = _factor_bucle(nodo)
            datos: dict[str, Any] = {"linea": nodo.linea}
            variable = _amortizada(nodo, externo) if externo is not None else None
            if variable is not None:
                factor, clave = CONSTANTE, "bucle_amortizado"
                datos["var"] = variable
            notas.append((clave, datos))
            interior = max(
                (self._costo(h, grupo, notas, nodo) for h in hijos(nodo)), default=CONSTANTE
            )
            return factor.por(interior)
        costo = CONSTANTE
        if isinstance(nodo, (FunctionCall, CallStmt)) and nodo.nombre in self.subs:
            if nodo.nombre not in grupo:
                llamado = self.costo_de(nodo.nombre)
                notas.append(("llamada", {"nombre": nodo.nombre, "costo": llamado.estimado}))
                costo = llamado.costo
        for h in hijos(nodo):
            costo = max(costo, self._costo(h, grupo, notas, externo))
        return costo

    def _rec_en_bucle(self, bucle: Any, grupo: frozenset[str]) -> bool:
        return bool(_llamadas(bucle.bloque, set(grupo)))

    def _llamadas_por_camino(self, nodo: Any, grupo: frozenset[str]) -> int:
        """Máximo de llamadas recursivas que se ejecutan en un mismo camino."""
        if isinstance(nodo, (IfStmt, TernaryExpr, SwitchStmt)):
            cond = getattr(nodo, "condicion", None) or getattr(nodo, "expr", None)
            ramas = [h for h in hijos(nodo) if h is not cond]
            base = self._llamadas_por_camino(cond, grupo) if cond is not None else 0
            return base + max((self._llamadas_por_camino(r, grupo) for r in ramas), default=0)
        propio = 1 if isinstance(nodo, (FunctionCall, CallStmt)) and nodo.nombre in grupo else 0
        return propio + sum(self._llamadas_por_camino(h, grupo) for h in hijos(nodo))

    def _forma(self, sub: Any, grupo: frozenset[str]) -> str:
        """``division`` si el argumento se divide, ``resta`` si decrece, ``otro`` si no se sabe."""
        divididas = {
            nombre for nombre, expr in _asignaciones(list(recorrer(sub.bloque))) if _divide(expr)
        }
        params = {p.nombre for p in sub.parametros}
        forma = "otro"
        for n in recorrer(sub.bloque):
            if isinstance(n, (FunctionCall, CallStmt)) and n.nombre in grupo:
                for arg in n.argumentos:
                    if _divide(arg) or (isinstance(arg, Identifier) and arg.nombre in divididas):
                        return "division"
                    # Solo `parametro - k` es una reducción constante del tamaño;
                    # `p - 1` con p calculado (pivote de quicksort) no lo es.
                    if any(
                        isinstance(b, BinaryOp)
                        and b.operador == "-"
                        and isinstance(b.izquierda, Identifier)
                        and b.izquierda.nombre in params
                        for b in recorrer(arg)
                    ):
                        forma = "resta"
        return forma


def _modifica(n: Any, var: str) -> bool:
    """True si el nodo cambia el valor de la variable simple ``var``."""
    if isinstance(n, (AssignStmt, ForInitAsig)):
        return getattr(n.lvalue, "nombre", None) == var and not isinstance(
            n.lvalue, (ArrayLValue, MatrixLValue)
        )
    if isinstance(n, (IncDecStmt, ForInitIncDec, ReadStmt)):
        return bool(n.nombre == var)
    if isinstance(n, UnaryOp) and n.operador in ("++", "--"):
        return isinstance(n.operando, Identifier) and n.operando.nombre == var
    return False


def _incrementa(n: Any, var: str) -> bool:
    """True si el nodo suma una constante positiva a ``var`` (``k++``, ``k = k + 1``)."""
    if isinstance(n, (IncDecStmt, ForInitIncDec)):
        return bool(n.nombre == var and n.operador == "++")
    if isinstance(n, UnaryOp):
        return n.operador == "++" and _modifica(n, var)
    if not isinstance(n, (AssignStmt, ForInitAsig)) or not _modifica(n, var):
        return False
    e = n.expr
    if n.operador == "+=":
        return isinstance(e, Literal) and isinstance(e.valor, int) and e.valor > 0
    if n.operador != "=" or not isinstance(e, BinaryOp) or e.operador != "+":
        return False
    lados = (e.izquierda, e.derecha)
    return any(isinstance(x, Identifier) and x.nombre == var for x in lados) and any(
        isinstance(x, Literal) and isinstance(x.valor, int) and x.valor > 0 for x in lados
    )


def _amortizada(interno: Any, externo: Any) -> str | None:
    """Variable que hace amortizado al ``mientras`` ``interno`` dentro de ``externo``.

    La variable aparece en la condición del ciclo interno, se declara fuera
    del externo, el interno la cambia siempre en un mismo sentido (solo
    incrementos, o ningún incremento) y el resto del externo solo la
    incrementa, fuera de otros ciclos. Entonces sus cambios suman O(n) a lo
    largo de TODAS las vueltas externas (método del potencial).
    """
    if not isinstance(interno, WhileStmt):
        return None
    del_externo = list(recorrer(externo))
    declaradas = {n.nombre for n in del_externo if isinstance(n, (VarDecl, ForInitVar))}
    ids_interno = {id(n) for n in recorrer(interno)}
    otros_ciclos = [
        b
        for b in del_externo
        if isinstance(b, _BUCLES) and b is not externo and id(b) not in ids_interno
    ]
    for var in sorted(_variables(interno.condicion) - declaradas):
        cambios = [n for n in recorrer(interno.bloque) if _modifica(n, var)]
        sube = [n for n in cambios if _incrementa(n, var)]
        if not cambios or 0 < len(sube) < len(cambios):
            continue
        resto = [n for n in del_externo if id(n) not in ids_interno and _modifica(n, var)]
        if any(not _incrementa(n, var) for n in resto):
            continue
        if any(_modifica(n, var) for b in otros_ciclos for n in recorrer(b)):
            continue
        return var
    return None


def _tabla_indexada(n: Any, params: set[str]) -> tuple[str, int] | None:
    """(tabla, dimensiones) si ``n`` lee o escribe ``t[..]`` con índices de los parámetros."""
    if isinstance(n, (ArrayAccess, ArrayLValue)):
        indices = [n.indice]
    elif isinstance(n, (MatrixAccess, MatrixLValue)):
        indices = [n.fila, n.columna]
    else:
        return None
    if all(_variables(i) & params for i in indices):
        return str(n.nombre), len(indices)
    return None


def _memoizada(sub: Any, grupo: frozenset[str]) -> tuple[str, int] | None:
    """Tabla de memoización de una subrutina recursiva, si la usa (INV-4405).

    Se exige el patrón completo: antes de la primera llamada recursiva un
    ``si`` que consulta ``tabla[parámetros]`` y retorna, y una asignación a la
    misma tabla con índices de los parámetros. Sin la consulta previa no hay
    memoización (la tabla solo se rellena) y sin el guardado nunca acierta.
    """
    params = {p.nombre for p in sub.parametros}
    nodos = list(recorrer(sub.bloque))
    primera = next(
        (
            i
            for i, n in enumerate(nodos)
            if isinstance(n, (FunctionCall, CallStmt)) and n.nombre in grupo
        ),
        None,
    )
    if primera is None:
        return None
    consultadas: dict[str, int] = {}
    for n in nodos[:primera]:
        if isinstance(n, IfStmt) and any(
            isinstance(r, ReturnStmt) for r in recorrer(n.bloque_then)
        ):
            for acceso in recorrer(n.condicion):
                tabla = _tabla_indexada(acceso, params)
                if tabla is not None:
                    consultadas[tabla[0]] = tabla[1]
    for n in nodos:
        if isinstance(n, AssignStmt):
            tabla = _tabla_indexada(n.lvalue, params)
            if tabla is not None and tabla[0] in consultadas:
                return tabla[0], consultadas[tabla[0]]
    return None


def _escala(expr: Any) -> bool:
    return any(
        isinstance(b, BinaryOp) and b.operador in ("*", "/", ">>", "<<") for b in recorrer(expr)
    )


def _divide(expr: Any) -> bool:
    return any(isinstance(b, BinaryOp) and b.operador in ("/", ">>") for b in recorrer(expr))


def _maestro(a: int, f: Costo) -> Costo:
    """T(n) = a·T(n/2) + f(n), con f = n^d·log^l n."""
    if f.exponencial:
        return f
    critico = math.log2(a)
    if math.isclose(f.grado, critico):
        return Costo(False, f.grado, f.log + 1)
    if f.grado > critico:
        return f
    return Costo(False, critico, 0)


def analizar_complejidad(ast: Any) -> dict[str, ResultadoComplejidad]:
    """Estima la complejidad de cada subrutina, ``main`` y métodos de un programa ya parseado."""
    analizador = _Analizador(ast)
    return {nombre: analizador.costo_de(nombre) for nombre in analizador.subs}


def describir(resultados: dict[str, ResultadoComplejidad], idioma: str | None = None) -> list[str]:
    """Informe legible con la cota y el porqué de cada subrutina.

    ``idioma`` (``"es"``/``"en"``; ``None`` = idioma actual) se resuelve con el
    catálogo i18n.
    """
    lineas = []
    for nombre, res in resultados.items():
        lineas.append(f"{nombre}: {res.estimado}")
        vistas: set[str] = set()
        for clave, datos in res.notas:
            texto = t(f"COMP.{clave}", idioma, **datos)
            if texto not in vistas:
                vistas.add(texto)
                lineas.append(f"  - {texto}")
    if lineas:
        # INV-4405: el estudiante debe saber cómo se obtuvo la cota y qué no ve.
        lineas.append(t("COMP.metodo", idioma))
        lineas.append(t("COMP.limites", idioma))
    return lineas
