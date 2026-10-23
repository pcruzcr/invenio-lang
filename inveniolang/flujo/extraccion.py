"""Código InvenioLang → modelo de diagrama de flujo (INV-3001).

El texto de cada caja sale **del propio código del estudiante** (los tokens
del lexer real, con los comentarios quitados y los espacios normalizados),
no de reimprimir el AST: así una expresión conserva exactamente sus
paréntesis, literales y escapes, y la vuelta a código produce el mismo
programa. El AST del parser real decide la *forma* de cada instrucción (qué
nodo es, qué ramas tiene); un cursor sobre los tokens avanza a la par y
delimita el texto de cada parte. No hay un segundo analizador: si el AST y
los tokens no casaran, se lanza ``AssertionError`` (error interno, cubierto
por la prueba de ida y vuelta sobre todo el currículo).

Por qué no se usan ``linea``/``columna`` del AST para delimitar: el parser
fija la posición de una declaración en su *nombre* (``entero x`` apunta a
``x``) y la de algunas asignaciones a matriz no coincide con ningún token;
el cursor no depende de ellas.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .. import ast_nodes as A  # noqa: N812 - alias corto del módulo de nodos
from ..core.compiler import analizar_fuente
from ..errors import ErrorManager
from ..i18n import normalizar_idioma
from ..lexer import Lexer
from ..modulos import CargadorModulos
from ..traductor import traducir
from ..visualizacion.traza import detectar_idioma
from .modelo import Diagrama, Elemento, ErrorFlujo, ModeloFlujo, Nodo, Rama

__all__ = ["Tok", "modelo_desde_codigo", "nodos_de_bloque", "tokens_fuente"]

_ABRE = frozenset({"DEL_PAREN_A", "DEL_CORCHETE_A", "DEL_LLAVE_A"})
_CIERRA = frozenset({"DEL_PAREN_C", "DEL_CORCHETE_C", "DEL_LLAVE_C"})
_CLASE = frozenset({"KW_CLASS", "KW_ABSTRACT", "KW_INTERFACE"})


@dataclass(frozen=True)
class Tok:
    """Token del lexer real: tipo y extensión ``[ini, fin)`` en el texto."""

    tipo: str
    ini: int
    fin: int


def tokens_fuente(codigo: str) -> list[Tok]:
    """Tokens del lexer real con su extensión ``[ini, fin)`` en el texto.

    INV-4002: público para que el lector de bloques (``bloques/lector.py``)
    trabaje sobre exactamente los mismos tokens que la extracción del
    diagrama, en vez de repetir el recorrido del lexer.
    """
    lexer = Lexer(ErrorManager())
    lexer.build()
    motor = lexer.lexer_obj
    assert motor is not None  # build() siempre lo construye
    motor.input(codigo)
    motor.lineno = 1
    salida: list[Tok] = []
    while True:
        tok = motor.token()
        if tok is None:
            return salida
        salida.append(Tok(tok.type, tok.lexpos, motor.lexpos))


class _Cursor:
    """Avanza sobre los tokens a la par que el recorrido del AST."""

    def __init__(self, codigo: str, toks: list[Tok], i: int = 0):
        self.codigo = codigo
        self.toks = toks
        self.i = i

    def tipo(self, k: int = 0) -> str:
        j = self.i + k
        return self.toks[j].tipo if j < len(self.toks) else ""

    def esperar(self, tipo: str) -> None:
        assert self.tipo() == tipo, f"se esperaba {tipo} y llegó {self.tipo()} en {self.i}"
        self.i += 1

    def texto(self, a: int, b: int) -> str:
        """Texto de los tokens ``[a, b)``.

        Texto de los tokens ``[a, b)``: cualquier separación (espacios o comentarios) entre dos
        tokens queda como un único espacio.
        """
        partes: list[str] = []
        for k in range(a, b):
            t = self.toks[k]
            if k > a and t.ini > self.toks[k - 1].fin:
                partes.append(" ")
            partes.append(self.codigo[t.ini : t.fin])
        return "".join(partes)

    def hasta(self, separadores: frozenset[str]) -> tuple[int, int]:
        """Rango desde el cursor hasta el primer separador a profundidad 0.

        El separador no se consume. También se detiene ante un cierre que
        baja de la profundidad 0 (el ``)`` que cierra la parte actual).
        """
        a = self.i
        prof = 0
        while True:
            tipo = self.tipo()
            assert tipo, "fin inesperado de los tokens"
            if prof == 0 and (tipo in separadores or tipo in _CIERRA):
                return a, self.i
            if tipo in _ABRE:
                prof += 1
            elif tipo in _CIERRA:
                prof -= 1
            self.i += 1

    def parte(self, separadores: frozenset[str]) -> str:
        a, b = self.hasta(separadores)
        return self.texto(a, b)

    def parentesis(self) -> str:
        """``( texto )``: devuelve el interior y consume ambos paréntesis."""
        self.esperar("DEL_PAREN_A")
        interior = self.parte(frozenset())
        self.esperar("DEL_PAREN_C")
        return interior

    def instruccion(self) -> str:
        """Texto hasta el ``;`` (que se consume)."""
        texto = self.parte(frozenset({"DEL_PUNTO_COMA"}))
        self.esperar("DEL_PUNTO_COMA")
        return texto

    def segmentos(self, fin: int) -> list[tuple[int, int]]:
        """Divide ``[i, fin)`` en declaraciones de nivel superior.

        Una declaración termina en ``;`` a profundidad 0, o en la ``}`` que
        cierra un cuerpo de definición: clase/interfaz/enumeración, o una
        llave abierta justo tras ``)`` (subrutina, método, constructor). La
        llave de un lambda (``funcion(...) entero { }``) va tras un tipo y no
        termina la declaración que la contiene.
        """
        salida: list[tuple[int, int]] = []
        while self.i < fin:
            a = self.i
            definicion = self.tipo() in _CLASE or self.tipo() == "KW_ENUM"
            parentesis = llaves = 0
            while True:
                t = self.tipo()
                self.i += 1
                if t in ("DEL_PAREN_A", "DEL_CORCHETE_A"):
                    parentesis += 1
                elif t in ("DEL_PAREN_C", "DEL_CORCHETE_C"):
                    parentesis -= 1
                elif t == "DEL_LLAVE_A":
                    if (
                        llaves == 0
                        and parentesis == 0
                        and self.toks[self.i - 2].tipo == "DEL_PAREN_C"
                    ):
                        definicion = True
                    llaves += 1
                elif t == "DEL_LLAVE_C":
                    llaves -= 1
                    if llaves == 0 and parentesis == 0 and definicion:
                        break
                elif t == "DEL_PUNTO_COMA" and llaves == 0 and parentesis == 0:
                    break
            salida.append((a, self.i))
        return salida


class _Colas:
    """Declaraciones del AST por nombre, en el orden de sus listas."""

    def __init__(self) -> None:
        self._colas: dict[str, deque[Any]] = defaultdict(deque)

    def poner(self, nombre: str, nodo: Any) -> None:
        self._colas[nombre].append(nodo)

    def sacar(self, nombre: str) -> Any:
        assert self._colas[nombre], f"sin declaración en el AST para {nombre!r}"
        return self._colas[nombre].popleft()


class _Extractor:
    """Recorre el programa (AST + tokens) y arma el ``ModeloFlujo``."""

    def __init__(self, codigo: str, ast: A.Program, idioma: str):
        self.cur = _Cursor(codigo, tokens_fuente(codigo))
        self.ast = ast
        self.idioma = idioma
        self._siguiente = 0
        self._claves: dict[str, int] = {}

    # ---------------------------------------------------------------- ids

    def _id(self) -> str:
        self._siguiente += 1
        return f"n{self._siguiente}"

    def _clave(self, base: str) -> str:
        """Clave única: las sobrecargas repetidas llevan ``#2``, ``#3``, etc."""
        n = self._claves.get(base, 0) + 1
        self._claves[base] = n
        return base if n == 1 else f"{base}#{n}"

    # ---------------------------------------------------------------- programa

    def modelo(self) -> ModeloFlujo:
        subrutinas = _Colas()
        if self.ast.main is not None:
            subrutinas.poner("main", self.ast.main)
        for sub in self.ast.subrutinas:
            subrutinas.poner(sub.nombre, sub)
        clases = _Colas()
        for clase in self.ast.clases:
            clases.poner(clase.nombre, clase)
        elementos: list[Elemento] = []
        cur = self.cur
        for a, b in cur.segmentos(len(cur.toks)):
            primero = cur.toks[a].tipo
            if primero in _CLASE:
                elementos.append(self._clase(a, b, clases))
            elif primero in ("KW_IMPORT", "KW_ENUM") or cur.toks[b - 1].tipo != "DEL_LLAVE_C":
                elementos.append(Elemento("codigo", texto=cur.texto(a, b)))
            else:
                cur.i = a
                firma, nombre = self._cabecera()
                decl = subrutinas.sacar(nombre)
                tipo = (
                    "main"
                    if isinstance(decl, A.MainDecl)
                    else "funcion" if isinstance(decl, A.FunctionDecl) else "procedimiento"
                )
                elementos.append(self._subrutina(firma, nombre, tipo, None, decl))
                assert cur.i == b
        return ModeloFlujo(self.idioma, elementos)

    def _cabecera(self) -> tuple[str, str]:
        """Firma hasta la ``{`` del cuerpo y nombre (token antes del primer ``(``)."""
        cur = self.cur
        a, b = cur.hasta(frozenset({"DEL_LLAVE_A"}))
        k = next(j for j in range(a, b) if cur.toks[j].tipo == "DEL_PAREN_A") - 1
        tok = cur.toks[k]
        return cur.texto(a, b), cur.codigo[tok.ini : tok.fin]

    def _subrutina(
        self, firma: str, nombre: str, tipo: str, clase: str | None, decl: Any
    ) -> Elemento:
        base = nombre if clase is None else f"{clase}.{nombre}"
        diagrama = Diagrama(
            clave=self._clave(base),
            nombre=nombre,
            tipo=tipo,
            firma=firma,
            clase=clase,
            linea=decl.linea,
        )
        diagrama.cuerpo = self._bloque(decl.bloque)
        return Elemento("subrutina", diagrama=diagrama)

    def _clase(self, a: int, b: int, clases: _Colas) -> Elemento:
        cur = self.cur
        cur.i = a
        ca, cb = cur.hasta(frozenset({"DEL_LLAVE_A"}))
        cabecera = cur.texto(ca, cb)
        # Nombre: primer identificador de la cabecera (clase/interfaz X ...).
        k = next(j for j in range(ca, cb) if cur.toks[j].tipo == "IDENTIFICADOR")
        nombre = cur.codigo[cur.toks[k].ini : cur.toks[k].fin]
        decl = clases.sacar(nombre)
        cuerpos = _Colas()
        for m in decl.metodos:
            if m.bloque is not None:
                cuerpos.poner(m.nombre, m)
        for c in decl.constructores:
            cuerpos.poner(c.nombre, c)
        cur.esperar("DEL_LLAVE_A")
        miembros: list[Elemento] = []
        for ma, mb in cur.segmentos(b - 1):
            if cur.toks[mb - 1].tipo != "DEL_LLAVE_C":
                miembros.append(Elemento("codigo", texto=cur.texto(ma, mb)))
                continue
            cur.i = ma
            firma, nombre_m = self._cabecera()
            m = cuerpos.sacar(nombre_m)
            tipo = "constructor" if isinstance(m, A.ConstructorDecl) else "metodo"
            miembros.append(self._subrutina(firma, nombre_m, tipo, nombre, m))
            assert cur.i == mb
        cur.esperar("DEL_LLAVE_C")
        assert cur.i == b
        return Elemento("clase", texto=cabecera, miembros=miembros)

    # ---------------------------------------------------------------- instrucciones

    def _bloque(self, bloque: A.Bloque) -> list[Nodo]:
        self.cur.esperar("DEL_LLAVE_A")
        nodos = self._elementos(bloque.elementos)
        self.cur.esperar("DEL_LLAVE_C")
        return nodos

    def _elementos(self, elementos: list[Any]) -> list[Nodo]:
        return [self._instruccion(e) for e in elementos]

    def _instruccion(self, e: Any) -> Nodo:
        manejador = _MANEJADORES.get(type(e))
        assert manejador is not None, f"instrucción sin representación: {type(e).__name__}"
        return manejador(self, e)

    def _con_palabra(self, e: Any, tipo: str, palabra: str) -> Nodo:
        """``leer(x);``/``imprimir(e);``: el texto es el interior de los paréntesis."""
        cur = self.cur
        cur.esperar(palabra)
        texto = cur.parentesis()
        cur.esperar("DEL_PUNTO_COMA")
        return Nodo(self._id(), tipo, texto=texto, linea=e.linea)

    def _leer(self, e: A.ReadStmt) -> Nodo:
        return self._con_palabra(e, "leer", "KW_READ")

    def _escribir(self, e: A.PrintStmt) -> Nodo:
        return self._con_palabra(e, "escribir", "KW_PRINT")

    def _retornar(self, e: A.ReturnStmt) -> Nodo:
        self.cur.esperar("KW_RETURN")
        return Nodo(self._id(), "retornar", texto=self.cur.instruccion(), linea=e.linea)

    def _salto(self, e: Any) -> Nodo:
        tipo = "romper" if isinstance(e, A.BreakStmt) else "continuar"
        self.cur.esperar("KW_BREAK" if tipo == "romper" else "KW_CONTINUE")
        self.cur.esperar("DEL_PUNTO_COMA")
        return Nodo(self._id(), tipo, linea=e.linea)

    def _si(self, e: A.IfStmt) -> Nodo:
        cur = self.cur
        n = Nodo(self._id(), "si", linea=e.linea)
        cur.esperar("KW_IF")
        condicion = cur.parentesis()
        n.ramas.append(Rama(condicion, self._bloque(e.bloque_then)))
        if e.bloque_else is not None:
            cur.esperar("KW_ELSE")
            interior = e.bloque_else.elementos
            if len(interior) == 1 and isinstance(interior[0], A.IfStmt):
                # `sino { si (...) ... }`: es la cadena «sino si» (el lenguaje
                # exige llaves en el sino); se aplana en ramas del mismo nodo y
                # la generación vuelve a escribir exactamente este anidamiento.
                cur.esperar("DEL_LLAVE_A")
                anidado = self._si(interior[0])
                cur.esperar("DEL_LLAVE_C")
                n.ramas.extend(anidado.ramas)
                n.alterno = anidado.alterno
            else:
                n.alterno = self._bloque(e.bloque_else)
        return n

    def _mientras(self, e: A.WhileStmt) -> Nodo:
        self.cur.esperar("KW_WHILE")
        n = Nodo(self._id(), "mientras", texto=self.cur.parentesis(), linea=e.linea)
        n.cuerpo = self._bloque(e.bloque)
        return n

    def _hacer(self, e: A.DoWhileStmt) -> Nodo:
        cur = self.cur
        cur.esperar("KW_DO")
        n = Nodo(self._id(), "hacer_mientras", linea=e.linea)
        n.cuerpo = self._bloque(e.bloque)
        cur.esperar("KW_WHILE")
        n.texto = cur.parentesis()
        cur.esperar("DEL_PUNTO_COMA")
        return n

    def _para(self, e: A.ForStmt) -> Nodo:
        cur = self.cur
        pc = frozenset({"DEL_PUNTO_COMA"})
        cur.esperar("KW_FOR")
        cur.esperar("DEL_PAREN_A")
        n = Nodo(self._id(), "para", linea=e.linea)
        n.inicio = cur.parte(pc)
        cur.esperar("DEL_PUNTO_COMA")
        n.texto = cur.parte(pc)
        cur.esperar("DEL_PUNTO_COMA")
        n.paso = cur.parte(frozenset())
        cur.esperar("DEL_PAREN_C")
        n.cuerpo = self._bloque(e.bloque)
        return n

    def _para_cada(self, e: A.ForEachStmt) -> Nodo:
        cur = self.cur
        cur.esperar("KW_FOREACH")
        cur.esperar("DEL_PAREN_A")
        n = Nodo(self._id(), "para_cada", linea=e.linea)
        n.variable = cur.parte(frozenset({"DEL_DOSPUNTOS"}))
        cur.esperar("DEL_DOSPUNTOS")
        n.texto = cur.parte(frozenset())
        cur.esperar("DEL_PAREN_C")
        n.cuerpo = self._bloque(e.bloque)
        return n

    def _casos(self, n: Nodo, casos: list[Any], defecto: A.Bloque | None) -> None:
        """Cuerpo ``{ caso X: ... por_defecto: ... }`` de segun/emparejar."""
        cur = self.cur
        dos_puntos = frozenset({"DEL_DOSPUNTOS"})
        cur.esperar("DEL_LLAVE_A")
        for caso in casos:
            cur.esperar("KW_CASE")
            etiqueta = cur.parte(dos_puntos)
            cur.esperar("DEL_DOSPUNTOS")
            n.ramas.append(Rama(etiqueta, self._elementos(caso.bloque.elementos)))
        if defecto is not None:
            cur.esperar("KW_DEFAULT")
            cur.esperar("DEL_DOSPUNTOS")
            n.alterno = self._elementos(defecto.elementos)
        cur.esperar("DEL_LLAVE_C")

    def _segun(self, e: A.SwitchStmt) -> Nodo:
        self.cur.esperar("KW_SWITCH")
        n = Nodo(self._id(), "segun", texto=self.cur.parentesis(), linea=e.linea)
        self._casos(n, e.casos, e.bloque_default)
        return n

    def _coincidir(self, e: A.MatchStmt) -> Nodo:
        self.cur.esperar("KW_MATCH")
        n = Nodo(self._id(), "coincidir", texto=self.cur.parentesis(), linea=e.linea)
        self._casos(n, e.casos, e.caso_comodin)
        return n

    def _intentar(self, e: A.TryStmt) -> Nodo:
        cur = self.cur
        cur.esperar("KW_TRY")
        n = Nodo(self._id(), "intentar", linea=e.linea)
        n.cuerpo = self._bloque(e.bloque_try)
        cur.esperar("KW_CATCH")
        n.variable = cur.parentesis()
        n.alterno = self._bloque(e.bloque_catch)
        return n


def _hoja(tipo: str) -> Callable[[_Extractor, Any], Nodo]:
    """Instrucción simple: su texto completo hasta el ``;``."""

    def manejar(ex: _Extractor, e: Any) -> Nodo:
        return Nodo(ex._id(), tipo, texto=ex.cur.instruccion(), linea=e.linea)

    return manejar


# Tabla tipo de AST -> constructor del nodo (patrón Strategy por tipo).
_MANEJADORES: dict[type, Callable[[_Extractor, Any], Nodo]] = {
    A.AssignStmt: _hoja("proceso"),
    A.IncDecStmt: _hoja("proceso"),
    A.VarDecl: _hoja("declaracion"),
    A.ConstDecl: _hoja("declaracion"),
    A.ArrayDecl: _hoja("declaracion"),
    A.MatrixDecl: _hoja("declaracion"),
    A.CallStmt: _hoja("llamada"),
    A.MethodCallStmt: _hoja("llamada"),
    A.SuperCallStmt: _hoja("llamada"),
    A.ReadStmt: _Extractor._leer,
    A.PrintStmt: _Extractor._escribir,
    A.ReturnStmt: _Extractor._retornar,
    A.BreakStmt: _Extractor._salto,
    A.ContinueStmt: _Extractor._salto,
    A.IfStmt: _Extractor._si,
    A.WhileStmt: _Extractor._mientras,
    A.DoWhileStmt: _Extractor._hacer,
    A.ForStmt: _Extractor._para,
    A.ForEachStmt: _Extractor._para_cada,
    A.SwitchStmt: _Extractor._segun,
    A.MatchStmt: _Extractor._coincidir,
    A.TryStmt: _Extractor._intentar,
}


def modelo_desde_codigo(
    codigo: str,
    idioma: str | None = None,
    *,
    ruta: str = "<memoria>",
    cargador: CargadorModulos | None = None,
    ruta_fuente: str | None = None,
) -> ModeloFlujo:
    """Modelo de diagrama de flujo de un programa **válido**.

    ``idioma`` (``"es"``/``"en"``) es el idioma de las palabras clave de los
    textos del diagrama: el programa se traduce antes (``traductor.py``), así
    que un programa en español se puede diagramar en inglés. ``None`` lo
    deduce de las palabras clave (empate → español). Si el programa no
    compila se lanza ``ErrorFlujo`` con los diagnósticos oficiales.
    """
    idioma = normalizar_idioma(idioma) if idioma is not None else detectar_idioma(codigo) or "es"
    fuente = traducir(codigo, idioma)
    analisis = analizar_fuente(
        fuente, ruta, hasta="tipos", idioma=idioma, cargador=cargador, ruta_fuente=ruta_fuente
    )
    if not analisis.ok:
        raise ErrorFlujo(
            "FLU.error.compilacion", diagnosticos=tuple(analisis.errores.obtener_reportes())
        )
    # El semántico expande genéricos y el enlazador añade los módulos sobre el
    # AST: para casarlo con los tokens de ESTE archivo hace falta el del parser.
    crudo = analizar_fuente(fuente, ruta, hasta="parser")
    return _Extractor(fuente, crudo.ast, idioma).modelo()


def nodos_de_bloque(cuerpo: str, idioma: str) -> list[Nodo]:
    """Nodos de las instrucciones de ``cuerpo`` (texto de un bloque sin llaves).

    INV-4002: el cuerpo de una función anónima (``funcion(entero x) entero
    { … }``) va dentro de una expresión; el editor de bloques lo muestra como
    una pila de instrucciones más, así que se diagrama con este mismo
    extractor dentro de un ``main`` mínimo. Sólo se analiza la sintaxis (el
    cuerpo usa variables de fuera que aquí no existen). ``ErrorFlujo`` si el
    texto no es una secuencia de instrucciones válida.
    """
    fuente = f"vacio main() {{\n{cuerpo}\n}}\n"
    crudo = analizar_fuente(fuente, "<fragmento>", hasta="parser", idioma=idioma)
    if not crudo.ok or crudo.ast is None or crudo.ast.main is None:
        raise ErrorFlujo(
            "FLU.error.compilacion", diagnosticos=tuple(crudo.errores.obtener_reportes())
        )
    extractor = _Extractor(fuente, crudo.ast, idioma)
    modelo = extractor.modelo()
    if len(modelo.elementos) != 1 or modelo.elementos[0].diagrama is None:
        raise ErrorFlujo("FLU.val.una_instruccion")
    return modelo.elementos[0].diagrama.cuerpo
