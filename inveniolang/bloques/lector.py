r"""Textos del diagrama de flujo → bloques anidados (INV-4002).

El diagrama de flujo (``inveniolang.flujo``) ya separa el programa en
subrutinas, clases e instrucciones estructuradas, pero cada caja guarda su
contenido como **texto** (``"suma = suma + v[i]"``). Para que el estudiante
pueda arrastrar una expresión dentro de otra, este módulo descompone esos
textos en bloques: expresiones con huecos tipados, declaraciones, firmas de
subrutinas y cabeceras de clase.

Trabaja sobre los **tokens del lexer real** (``flujo.extraccion.tokens_fuente``)
con la gramática de ``parser.py`` (misma precedencia y asociatividad de
operadores) y conserva exactamente cómo escribió el estudiante cada literal
(``1.50``, ``"a\n"``). Los textos que recibe ya pasaron el compilador
completo (salen de un programa válido) o los acaba de escribir el
estudiante en el editor; en el segundo caso un texto mal formado produce
``ErrorBloques`` con el motivo y la validación final la hace siempre el
compilador real (``edicion.validar``).
"""

from __future__ import annotations

from collections.abc import Callable

from ..flujo import modelo as F  # noqa: N812 - alias corto del modelo de flujo
from ..flujo.extraccion import Tok, nodos_de_bloque, tokens_fuente
from ..traductor import PALABRAS_CLAVE
from .catalogo import TIPOS
from .modelo import Bloque, ErrorBloques

__all__ = ["Ids", "Lector", "neutral"]

_PALABRA = ("IDENTIFICADOR", "ENTERO_LIT", "REAL_LIT", "TEXTO_LIT")
_TIPOS_PRIMITIVOS = ("KW_INT", "KW_FLOAT", "KW_STRING", "KW_BOOL")
_ASIGNACION = {
    "OP_ASIG": "=",
    "OP_ASIG_SUMA": "+=",
    "OP_ASIG_RESTA": "-=",
    "OP_ASIG_MULT": "*=",
    "OP_ASIG_DIV": "/=",
    "OP_ASIG_MOD": "%=",
}
# Niveles binarios de menor a mayor precedencia (gramática de parser.py,
# reglas expr_or … expr_mul; todos asociativos por la izquierda).
NIVELES: tuple[dict[str, str], ...] = (
    {"OP_OR": "||"},
    {"OP_AND": "&&"},
    {"OP_BITOR": "|"},
    {"OP_BITXOR": "^"},
    {"OP_BITAND": "&"},
    {"OP_IGUAL": "==", "OP_DISTINTO": "!="},
    {"OP_MENOR": "<", "OP_MAYOR": ">", "OP_MENOR_IGUAL": "<=", "OP_MAYOR_IGUAL": ">="},
    {"OP_SHL": "<<", "OP_SHR": ">>"},
    {"OP_SUMA": "+", "OP_RESTA": "-"},
    {"OP_MULT": "*", "OP_DIV": "/", "OP_MOD": "%"},
)
_UNARIOS = {"OP_RESTA": "-", "OP_NOT": "!", "OP_BITNOT": "~"}


def neutral(tipo_token: str) -> str:
    """Forma neutral (española canónica) de una palabra clave por su tipo de token."""
    return PALABRAS_CLAVE[tipo_token][0]


class Ids:
    """Generador de ids únicos (``b1``, ``b2``…) que respeta los ya usados."""

    def __init__(self, usados: set[str] | None = None):
        self.usados: set[str] = set(usados or ())
        self._n = 0

    def nuevo(self) -> str:
        """Un id que nadie usa todavía."""
        while True:
            self._n += 1
            ident = f"b{self._n}"
            if ident not in self.usados:
                self.usados.add(ident)
                return ident

    def reservar(self, ident: str) -> str:
        """Usa ``ident`` si está libre; si no, uno nuevo."""
        if ident and ident not in self.usados:
            self.usados.add(ident)
            return ident
        return self.nuevo()


def nuevo_bloque(ids: Ids, tipo: str, linea: int = 0, ident: str | None = None) -> Bloque:
    """Bloque ``tipo`` con los valores por defecto del catálogo y huecos/listas vacíos."""
    desc = TIPOS[tipo]
    return Bloque(
        ids.reservar(ident) if ident else ids.nuevo(),
        tipo,
        linea,
        {c.nombre: c.defecto for c in desc.campos},
        {h.nombre: None for h in desc.huecos},
        {x.nombre: [] for x in desc.listas},
    )


class _Fragmento:
    """Cursor sobre los tokens de un texto."""

    def __init__(self, texto: str):
        self.texto = texto
        self.toks: list[Tok] = tokens_fuente(texto)
        self.i = 0

    def tipo(self, k: int = 0) -> str:
        j = self.i + k
        return self.toks[j].tipo if j < len(self.toks) else ""

    def lexema(self, k: int = 0) -> str:
        t = self.toks[self.i + k]
        return self.texto[t.ini : t.fin]

    def fallo(self) -> ErrorBloques:
        cerca = self.lexema() if self.i < len(self.toks) else "∅"
        return ErrorBloques("BLQ.error.sintaxis", texto=self.texto, cerca=cerca)

    def tomar(self, *tipos: str) -> str:
        if self.tipo() not in tipos:
            raise self.fallo()
        lex = self.lexema()
        self.i += 1
        return lex

    def hay(self, *tipos: str) -> bool:
        if self.tipo() in tipos:
            self.i += 1
            return True
        return False

    def fin(self) -> None:
        if self.i != len(self.toks):
            raise self.fallo()

    def unir(self, a: int, b: int) -> str:
        """Texto canónico de los tokens ``[a, b)`` (espacio sólo donde separa palabras)."""
        partes: list[str] = []
        previo = ""
        for t in self.toks[a:b]:
            palabra = t.tipo in _PALABRA or t.tipo.startswith("KW_")
            if partes and (
                (palabra and (previo in _PALABRA or previo.startswith("KW_")))
                or previo == "DEL_COMA"
                or (palabra and previo == "DEL_PAREN_C")
            ):
                partes.append(" ")
            partes.append(self.texto[t.ini : t.fin])
            previo = t.tipo
        return "".join(partes)


class Lector:
    """Convierte textos del modelo de flujo (en ``idioma``) en bloques."""

    def __init__(self, idioma: str, ids: Ids, linea: int = 0):
        self.idioma = idioma
        self.ids = ids
        self.linea = linea
        self.f = _Fragmento("")
        self._conservar = True

    # ------------------------------------------------------------ utilidades

    def _nuevo(self, tipo: str, ident: str | None = None) -> Bloque:
        return nuevo_bloque(self.ids, tipo, self.linea, ident)

    def _con(self, texto: str, regla: Callable[[], Bloque]) -> Bloque:
        """Aplica ``regla`` a ``texto`` completo (sin ``;`` final)."""
        anterior = self.f
        self.f = _Fragmento(texto)
        if self.f.toks and self.f.toks[-1].tipo == "DEL_PUNTO_COMA":
            self.f.toks.pop()
        try:
            b = regla()
            self.f.fin()
            return b
        finally:
            self.f = anterior

    # ------------------------------------------------------------ tipos

    def _tipo(self, retorno: bool = False) -> str:
        """Tipo como texto canónico: primitivo, clase, genérico, función y ``[]``."""
        f = self.f
        a = f.i
        if f.tipo() == "KW_VOID":
            f.i += 1
        elif f.tipo() in _TIPOS_PRIMITIVOS:
            f.i += 1
        elif f.tipo() == "IDENTIFICADOR":
            f.i += 1
            if f.tipo() == "OP_MENOR":
                f.i += 1
                self._tipo()
                f.tomar("OP_MAYOR")
        elif f.tipo() == "KW_FUNCION":
            f.i += 1
            f.tomar("DEL_PAREN_A")
            self._parametros()
            f.tomar("DEL_PAREN_C")
            self._tipo(retorno=True)
        else:
            raise f.fallo()
        while f.tipo() == "DEL_CORCHETE_A" and f.tipo(1) == "DEL_CORCHETE_C":
            f.i += 2
        return f.unir(a, f.i)

    def _es_tipo_inicio(self) -> bool:
        """¿Empieza aquí una declaración ``tipo nombre``?"""
        f = self.f
        if f.tipo() in _TIPOS_PRIMITIVOS or f.tipo() in ("KW_VOID", "KW_FUNCION", "KW_CONST"):
            return True
        if f.tipo() != "IDENTIFICADOR":
            return False
        if f.tipo(1) == "IDENTIFICADOR":
            return True
        if f.tipo(1) == "OP_MENOR":
            # Pila<entero> p  frente a  a < b: tras «<» y su argumento viene «>».
            return f.tipo(3) == "OP_MAYOR" and f.tipo(4) == "IDENTIFICADOR"
        return (
            f.tipo(1) == "DEL_CORCHETE_A"
            and f.tipo(2) == "DEL_CORCHETE_C"
            and f.tipo(3) == "IDENTIFICADOR"
        )

    def _parametros(self) -> list[Bloque]:
        """``tipo nombre, …`` hasta el ``)`` (no lo consume)."""
        f = self.f
        salida: list[Bloque] = []
        while f.tipo() != "DEL_PAREN_C":
            p = self._nuevo("parametro")
            p.campos["tipo"] = self._tipo()
            p.campos["nombre"] = f.tomar("IDENTIFICADOR")
            salida.append(p)
            if not f.hay("DEL_COMA"):
                break
        return salida

    def _identificadores(self) -> str:
        f = self.f
        nombres = [f.tomar("IDENTIFICADOR")]
        while f.hay("DEL_COMA"):
            nombres.append(f.tomar("IDENTIFICADOR"))
        return ", ".join(nombres)

    # ------------------------------------------------------------ expresiones

    def expresion(self) -> Bloque:
        """``expresion`` de la gramática (incluye la ternaria)."""
        f = self.f
        c = self._coalesce()
        if f.hay("DEL_INTERROGACION"):
            t = self._nuevo("ternaria")
            t.huecos["condicion"] = c
            t.huecos["si_verdadero"] = self.expresion()
            f.tomar("DEL_DOSPUNTOS")
            t.huecos["si_falso"] = self.expresion()
            return t
        return c

    def _binaria(self, op: str, izq: Bloque, der: Bloque) -> Bloque:
        b = self._nuevo("binaria")
        b.campos["op"] = op
        b.huecos["izquierda"] = izq
        b.huecos["derecha"] = der
        return b

    def _coalesce(self) -> Bloque:
        izq = self._nivel(0)
        if self.f.hay("OP_COALESCENCIA"):
            return self._binaria("??", izq, self._coalesce())
        return izq

    def _nivel(self, k: int) -> Bloque:
        if k == len(NIVELES):
            return self._unaria()
        izq = self._nivel(k + 1)
        while self.f.tipo() in NIVELES[k]:
            op = NIVELES[k][self.f.tipo()]
            self.f.i += 1
            izq = self._binaria(op, izq, self._nivel(k + 1))
        return izq

    def _incremento(self, tipo: str, op: str, posicion: str, objetivo: Bloque) -> Bloque:
        b = self._nuevo(tipo)
        b.campos["op"] = op
        b.campos["posicion"] = posicion
        b.huecos["objetivo"] = objetivo
        return b

    def _unaria(self) -> Bloque:
        f = self.f
        if f.tipo() in _UNARIOS:
            b = self._nuevo("unaria")
            b.campos["op"] = _UNARIOS[f.tipo()]
            f.i += 1
            b.huecos["valor"] = self._unaria()
            return b
        if f.tipo() in ("OP_INC", "OP_DEC"):
            op = "++" if f.tipo() == "OP_INC" else "--"
            f.i += 1
            return self._incremento("incremento", op, "prefijo", self.postfija())
        base = self.postfija()
        if f.tipo() in ("OP_INC", "OP_DEC"):
            op = "++" if f.tipo() == "OP_INC" else "--"
            f.i += 1
            return self._incremento("incremento", op, "sufijo", base)
        return base

    def _argumentos(self) -> list[Bloque]:
        """``( e, … )`` consumiendo ambos paréntesis."""
        f = self.f
        f.tomar("DEL_PAREN_A")
        args: list[Bloque] = []
        if f.tipo() != "DEL_PAREN_C":
            args.append(self.expresion())
            while f.hay("DEL_COMA"):
                args.append(self.expresion())
        f.tomar("DEL_PAREN_C")
        return args

    def postfija(self) -> Bloque:
        """Primaria seguida de ``[i]``, ``.campo``, ``?.campo`` y llamadas a método."""
        f = self.f
        if f.tipo() == "IDENTIFICADOR" and f.tipo(1) == "DEL_PAREN_A":
            b = self._nuevo("llamada")
            b.campos["nombre"] = f.tomar("IDENTIFICADOR")
            b.listas["argumentos"] = self._argumentos()
        else:
            b = self._primaria()
        while f.tipo() in ("DEL_CORCHETE_A", "DEL_PUNTO", "OP_ACCESO_SEGURO"):
            if f.hay("DEL_CORCHETE_A"):
                idx = self._nuevo("indice")
                idx.huecos["coleccion"] = b
                idx.huecos["posicion"] = self.expresion()
                f.tomar("DEL_CORCHETE_C")
                b = idx
                continue
            seguro = f.tomar("DEL_PUNTO", "OP_ACCESO_SEGURO") == "?."
            nombre = f.tomar("IDENTIFICADOR")
            if f.tipo() == "DEL_PAREN_A":
                m = self._nuevo("llamada_metodo")
                m.listas["argumentos"] = self._argumentos()
            else:
                m = self._nuevo("propiedad")
            m.campos["nombre"] = nombre
            m.campos["seguro"] = seguro
            m.huecos["objeto"] = b
            b = m
        return b

    def _primaria(self) -> Bloque:
        f = self.f
        t = f.tipo()
        if t in ("ENTERO_LIT", "REAL_LIT", "TEXTO_LIT"):
            b = self._nuevo("texto" if t == "TEXTO_LIT" else "numero")
            b.campos["valor"] = f.tomar(t)
            return b
        if t in ("KW_TRUE", "KW_FALSE"):
            b = self._nuevo("logico")
            b.campos["valor"] = neutral(t)
            f.i += 1
            return b
        simples = {"KW_NULL": "nulo", "KW_THIS": "este", "KW_SUPER": "padre"}
        if t in simples:
            f.i += 1
            return self._nuevo(simples[t])
        if t == "IDENTIFICADOR":
            b = self._nuevo("variable")
            b.campos["nombre"] = f.tomar(t)
            return b
        if f.hay("DEL_PAREN_A"):
            # Los paréntesis no son un bloque: el anidamiento ya fija el orden
            # y el escritor los repone sólo donde la precedencia los exige.
            e = self.expresion()
            f.tomar("DEL_PAREN_C")
            return e
        if t == "KW_NEW":
            return self._nuevo_objeto()
        if t == "KW_FUNCION":
            return self._lambda()
        raise f.fallo()

    def _nuevo_objeto(self) -> Bloque:
        f = self.f
        f.tomar("KW_NEW")
        if f.tipo(1) == "DEL_CORCHETE_A":
            b = self._nuevo("nuevo_arreglo")
            b.campos["tipo"] = f.tomar("IDENTIFICADOR", *_TIPOS_PRIMITIVOS)
            f.tomar("DEL_CORCHETE_A")
            b.huecos["tamano"] = self.expresion()
            f.tomar("DEL_CORCHETE_C")
            return b
        b = self._nuevo("nuevo")
        b.campos["clase"] = f.tomar("IDENTIFICADOR")
        if f.hay("OP_MENOR"):
            b.campos["generico"] = self._tipo()
            f.tomar("OP_MAYOR")
        b.listas["argumentos"] = self._argumentos()
        return b

    def _lambda(self) -> Bloque:
        f = self.f
        b = self._nuevo("lambda")
        f.tomar("KW_FUNCION")
        f.tomar("DEL_PAREN_A")
        b.listas["parametros"] = self._parametros()
        f.tomar("DEL_PAREN_C")
        b.campos["retorno"] = self._tipo(retorno=True)
        f.tomar("DEL_LLAVE_A")
        a = f.i
        prof = 0
        while not (f.tipo() == "DEL_LLAVE_C" and prof == 0):
            if not f.tipo():
                raise f.fallo()
            prof += {"DEL_LLAVE_A": 1, "DEL_LLAVE_C": -1}.get(f.tipo(), 0)
            f.i += 1
        cuerpo = f.texto[f.toks[a].ini : f.toks[f.i - 1].fin] if f.i > a else ""
        f.tomar("DEL_LLAVE_C")
        try:
            nodos = nodos_de_bloque(cuerpo, self.idioma)
        except F.ErrorFlujo as e:
            raise ErrorBloques("BLQ.error.sintaxis", texto=cuerpo, cerca="{") from e
        conservar, self._conservar = self._conservar, False
        try:
            b.listas["cuerpo"] = self.instrucciones(nodos)
        finally:
            self._conservar = conservar
        return b

    # ------------------------------------------------------------ instrucciones simples

    def _declaracion(self) -> Bloque:
        """Variable, constante, varias variables, arreglo o matriz."""
        f = self.f
        constante = f.hay("KW_CONST")
        tipo = self._tipo()
        dims: list[str] = []
        estilo = "tipo"
        while f.hay("DEL_CORCHETE_A"):
            dims.append(f.tomar("ENTERO_LIT", "IDENTIFICADOR"))
            f.tomar("DEL_CORCHETE_C")
        nombre = f.tomar("IDENTIFICADOR")
        if not dims and f.tipo() == "DEL_CORCHETE_A":
            estilo = "nombre"
            while f.hay("DEL_CORCHETE_A"):
                dims.append(f.tomar("ENTERO_LIT", "IDENTIFICADOR"))
                f.tomar("DEL_CORCHETE_C")
        if dims:
            b = self._nuevo("arreglo")
            b.campos.update(
                constante=constante,
                tipo=tipo,
                nombre=nombre,
                dimensiones=", ".join(dims),
                estilo=estilo,
            )
            if f.hay("OP_ASIG"):
                f.tomar("DEL_LLAVE_A")
                if f.tipo() == "DEL_LLAVE_A":
                    filas = [self._fila()]
                    while f.hay("DEL_COMA"):
                        filas.append(self._fila())
                    b.listas["filas"] = filas
                else:
                    b.listas["valores"] = self._lista_valores()
                f.tomar("DEL_LLAVE_C")
            return b
        b = self._nuevo("declarar")
        b.campos.update(constante=constante, tipo=tipo, nombre=nombre)
        if f.hay("OP_ASIG"):
            b.huecos["valor"] = self.expresion()
        return b

    def _lista_valores(self) -> list[Bloque]:
        valores = [self.expresion()]
        while self.f.hay("DEL_COMA"):
            valores.append(self.expresion())
        return valores

    def _fila(self) -> Bloque:
        fila = self._nuevo("fila")
        self.f.tomar("DEL_LLAVE_A")
        fila.listas["valores"] = self._lista_valores()
        self.f.tomar("DEL_LLAVE_C")
        return fila

    def _proceso(self) -> Bloque:
        """Asignación (``=``, ``+=``…) o ``x++``/``++x``."""
        f = self.f
        if f.tipo() in ("OP_INC", "OP_DEC"):
            op = "++" if f.tipo() == "OP_INC" else "--"
            f.i += 1
            return self._incremento("incrementar", op, "prefijo", self._variable())
        a = f.i
        destino = self.postfija()
        if f.tipo() in ("OP_INC", "OP_DEC"):
            if destino.tipo != "variable":
                f.i = a
                raise f.fallo()
            op = "++" if f.tipo() == "OP_INC" else "--"
            f.i += 1
            return self._incremento("incrementar", op, "sufijo", destino)
        if f.tipo() not in _ASIGNACION:
            raise f.fallo()
        b = self._nuevo("asignar")
        b.campos["op"] = _ASIGNACION[f.tipo()]
        f.i += 1
        b.huecos["destino"] = destino
        b.huecos["valor"] = self.expresion()
        return b

    def _variable(self) -> Bloque:
        b = self._nuevo("variable")
        b.campos["nombre"] = self.f.tomar("IDENTIFICADOR")
        return b

    def _llamada(self) -> Bloque:
        f = self.f
        if f.tipo() == "KW_SUPER" and f.tipo(1) == "DEL_PAREN_A":
            f.i += 1
            b = self._nuevo("llamar_padre")
            b.listas["argumentos"] = self._argumentos()
            return b
        b = self._nuevo("llamar")
        llamada = self.postfija()
        if llamada.tipo not in ("llamada", "llamada_metodo"):
            raise f.fallo()
        b.huecos["llamada"] = llamada
        return b

    def _inicio_para(self) -> list[Bloque]:
        if not self.f.toks:
            return []
        return [self._declaracion() if self._es_tipo_inicio() else self._proceso()]

    # ------------------------------------------------------------ API de textos

    def texto_expresion(self, texto: str) -> Bloque:
        """Una expresión completa."""
        return self._con(texto, self.expresion)

    def texto_opcional(self, texto: str) -> Bloque | None:
        """Expresión o ``None`` si el texto está vacío."""
        return self.texto_expresion(texto) if texto.strip() else None

    def texto_declaracion(self, texto: str) -> Bloque:
        """Declaración (local o global)."""
        return self._con(texto, self._declaracion)

    def texto_proceso(self, texto: str) -> Bloque:
        """Asignación o incremento."""
        return self._con(texto, self._proceso)

    def texto_llamada(self, texto: str) -> Bloque:
        """Llamada usada como instrucción."""
        return self._con(texto, self._llamada)

    def texto_para(self, texto: str, parte: str) -> list[Bloque]:
        """``inicio`` o ``paso`` de un ``para`` (lista de 0 o 1 bloques)."""
        if not texto.strip():
            return []
        regla = (lambda: self._inicio_para()[0]) if parte == "inicio" else self._proceso
        return [self._con(texto, regla)]

    def texto_variable_para_cada(self, texto: str) -> tuple[str, str]:
        """``entero d`` → (tipo, nombre)."""
        partes: list[str] = []

        def regla() -> Bloque:
            partes.append(self._tipo())
            partes.append(self.f.tomar("IDENTIFICADOR"))
            return self._nuevo("variable")

        self._con(texto, regla)
        return partes[0], partes[1]

    def texto_identificador(self, texto: str) -> str:
        """Un solo identificador."""
        return self._con(texto, self._variable).campos["nombre"]

    def texto_caso(self, texto: str) -> str:
        """Valor de ``caso`` de un ``segun``: entero (con signo), texto o lógico."""
        nombre: list[str] = []

        def regla() -> Bloque:
            f = self.f
            if f.tipo() in ("KW_TRUE", "KW_FALSE"):
                nombre.append(neutral(f.tipo()))
                f.i += 1
            else:
                a = f.i
                if f.hay("OP_RESTA"):
                    f.tomar("ENTERO_LIT")
                else:
                    f.tomar("ENTERO_LIT", "TEXTO_LIT")
                nombre.append(f.unir(a, f.i))
            return self._nuevo("variable")

        self._con(texto, regla)
        return nombre[0]

    def texto_patron(self, texto: str) -> tuple[str, str]:
        """``Circulo(r)`` → (``Circulo``, ``r``); ``Vacio`` → (``Vacio``, ``""``)."""
        partes: list[str] = []

        def regla() -> Bloque:
            f = self.f
            partes.append(f.tomar("IDENTIFICADOR"))
            if f.hay("DEL_PAREN_A"):
                partes.append(self._identificadores())
                f.tomar("DEL_PAREN_C")
            else:
                partes.append("")
            return self._nuevo("variable")

        self._con(texto, regla)
        return partes[0], partes[1]

    # ------------------------------------------------------------ definiciones

    def texto_firma(self, texto: str, tipo: str, ident: str | None = None) -> Bloque:
        """Firma de subrutina, método o constructor → bloque de definición (sin cuerpo)."""

        def regla() -> Bloque:
            f = self.f
            if tipo == "constructor":
                b = self._nuevo("constructor", ident)
                b.campos["visibilidad"] = ""
                if f.tipo() in ("KW_PUBLIC", "KW_PRIVATE"):
                    b.campos["visibilidad"] = neutral(f.tipo())
                    f.i += 1
                    f.tomar("KW_CONSTRUCTOR")
            elif tipo == "metodo":
                b = self._nuevo("metodo", ident)
                self._modificadores(b)
                b.campos["retorno"] = self._tipo(retorno=True)
            else:
                b = self._nuevo("subrutina", ident)
                b.campos["retorno"] = self._tipo(retorno=True)
            b.campos["nombre"] = f.tomar("IDENTIFICADOR", "KW_MAIN")
            f.tomar("DEL_PAREN_A")
            b.listas["parametros"] = self._parametros()
            f.tomar("DEL_PAREN_C")
            return b

        return self._con(texto, regla)

    def _modificadores(self, b: Bloque) -> None:
        f = self.f
        if f.tipo() not in ("KW_PUBLIC", "KW_PRIVATE"):
            raise f.fallo()
        b.campos["visibilidad"] = neutral(f.tipo())
        f.i += 1
        b.campos["modificador"] = ""
        if f.tipo() in ("KW_STATIC", "KW_ABSTRACT"):
            b.campos["modificador"] = neutral(f.tipo())
            f.i += 1

    def texto_cabecera(self, texto: str) -> Bloque:
        """``[abstracta] clase X [<T>] [hereda Y] [implementa A, B]`` o ``interfaz X``."""

        def regla() -> Bloque:
            f = self.f
            if f.hay("KW_INTERFACE"):
                b = self._nuevo("interfaz")
                b.campos["nombre"] = f.tomar("IDENTIFICADOR")
                return b
            b = self._nuevo("clase")
            b.campos["abstracta"] = f.hay("KW_ABSTRACT")
            f.tomar("KW_CLASS")
            b.campos["nombre"] = f.tomar("IDENTIFICADOR")
            if f.hay("OP_MENOR"):
                b.campos["generico"] = f.tomar("IDENTIFICADOR")
                f.tomar("OP_MAYOR")
            if f.hay("KW_EXTENDS"):
                b.campos["hereda"] = f.tomar("IDENTIFICADOR")
            if f.hay("KW_IMPLEMENTS"):
                b.campos["implementa"] = self._identificadores()
            return b

        return self._con(texto, regla)

    def texto_codigo(self, texto: str, en_clase: bool) -> Bloque:
        """Elemento ``codigo`` del flujo: importar, enumeración, global o miembro sin cuerpo."""

        def regla() -> Bloque:
            f = self.f
            if en_clase:
                return self._miembro_sin_cuerpo()
            if f.hay("KW_IMPORT"):
                b = self._nuevo("importar")
                b.campos["ruta"] = f.tomar("TEXTO_LIT")
                return b
            if f.hay("KW_ENUM"):
                return self._enumeracion()
            return self._declaracion()

        return self._con(texto, regla)

    def _enumeracion(self) -> Bloque:
        f = self.f
        b = self._nuevo("enumeracion")
        b.campos["nombre"] = f.tomar("IDENTIFICADOR")
        f.tomar("DEL_LLAVE_A")
        while True:
            m = self._nuevo("miembro_enum")
            m.campos["nombre"] = f.tomar("IDENTIFICADOR")
            if f.hay("DEL_PAREN_A"):
                m.campos["con_parametros"] = True
                m.listas["parametros"] = self._parametros()
                f.tomar("DEL_PAREN_C")
            b.listas["miembros"].append(m)
            if not f.hay("DEL_COMA"):
                break
        f.tomar("DEL_LLAVE_C")
        return b

    def _miembro_sin_cuerpo(self) -> Bloque:
        """Atributo o método sin cuerpo (abstracto o de interfaz)."""
        f = self.f
        inicio = f.i
        b = self._nuevo("atributo")
        self._modificadores(b)
        tipo = self._tipo(retorno=True)
        nombre = f.tomar("IDENTIFICADOR")
        if f.tipo() == "DEL_PAREN_A":
            f.i = inicio
            m = self._nuevo("metodo", b.id)
            self._modificadores(m)
            m.campos["retorno"] = self._tipo(retorno=True)
            m.campos["nombre"] = f.tomar("IDENTIFICADOR")
            f.tomar("DEL_PAREN_A")
            m.listas["parametros"] = self._parametros()
            f.tomar("DEL_PAREN_C")
            m.campos["con_cuerpo"] = False
            return m
        b.campos["tipo"] = tipo
        b.campos["nombre"] = nombre
        if f.hay("OP_ASIG"):
            b.huecos["valor"] = self.expresion()
        return b

    # ------------------------------------------------------------ nodos del flujo

    def instrucciones(self, nodos: list[F.Nodo]) -> list[Bloque]:
        """Bloques de instrucción de una secuencia del diagrama de flujo.

        Cada instrucción lleva el id de su nodo (así el diagrama y los bloques
        se señalan mutuamente); el llamador reserva antes esos ids en
        ``self.ids``. Las del cuerpo de una función anónima no son nodos del
        diagrama y reciben ids nuevos.
        """
        return [self.instruccion(n) for n in nodos]

    def instruccion(self, n: F.Nodo) -> Bloque:
        """Bloque de un nodo del diagrama (y de sus secuencias)."""
        anterior = self.linea
        self.linea = n.linea
        try:
            b = _INSTRUCCION[n.tipo](self, n)
        finally:
            self.linea = anterior
        if self._conservar and b.id != n.id:
            self.ids.usados.discard(b.id)
            b.id = n.id
            self.ids.usados.add(n.id)
        return b

    def _n_proceso(self, n: F.Nodo) -> Bloque:
        return self.texto_proceso(n.texto)

    def _n_declaracion(self, n: F.Nodo) -> Bloque:
        return self.texto_declaracion(n.texto)

    def _n_llamada(self, n: F.Nodo) -> Bloque:
        return self.texto_llamada(n.texto)

    def _n_leer(self, n: F.Nodo) -> Bloque:
        b = self._nuevo("leer")
        b.huecos["destino"] = self.texto_expresion(n.texto)
        return b

    def _n_escribir(self, n: F.Nodo) -> Bloque:
        b = self._nuevo("imprimir")
        b.huecos["valor"] = self.texto_expresion(n.texto)
        return b

    def _n_retornar(self, n: F.Nodo) -> Bloque:
        b = self._nuevo("retornar")
        b.huecos["valor"] = self.texto_opcional(n.texto)
        return b

    def _n_salto(self, n: F.Nodo) -> Bloque:
        return self._nuevo(n.tipo)

    def _n_si(self, n: F.Nodo) -> Bloque:
        b = self._nuevo("si")
        for rama in n.ramas:
            r = self._nuevo("rama_si")
            r.huecos["condicion"] = self.texto_expresion(rama.etiqueta)
            r.listas["cuerpo"] = self.instrucciones(rama.cuerpo)
            b.listas["ramas"].append(r)
        b.campos["tiene_sino"] = n.alterno is not None
        b.listas["sino"] = self.instrucciones(n.alterno or [])
        return b

    def _n_casos(self, n: F.Nodo) -> Bloque:
        b = self._nuevo(n.tipo)
        b.huecos["expresion"] = self.texto_expresion(n.texto)
        for rama in n.ramas:
            if n.tipo == "segun":
                c = self._nuevo("caso")
                c.campos["valor"] = self.texto_caso(rama.etiqueta)
            else:
                c = self._nuevo("caso_patron")
                c.campos["nombre"], c.campos["variables"] = self.texto_patron(rama.etiqueta)
            c.listas["cuerpo"] = self.instrucciones(rama.cuerpo)
            b.listas["casos"].append(c)
        b.campos["tiene_defecto"] = n.alterno is not None
        b.listas["por_defecto"] = self.instrucciones(n.alterno or [])
        return b

    def _n_ciclo(self, n: F.Nodo) -> Bloque:
        b = self._nuevo(n.tipo)
        b.huecos["condicion"] = self.texto_expresion(n.texto)
        b.listas["cuerpo"] = self.instrucciones(n.cuerpo)
        return b

    def _n_para(self, n: F.Nodo) -> Bloque:
        b = self._nuevo("para")
        b.listas["inicio"] = self.texto_para(n.inicio, "inicio")
        b.huecos["condicion"] = self.texto_opcional(n.texto)
        b.listas["paso"] = self.texto_para(n.paso, "paso")
        b.listas["cuerpo"] = self.instrucciones(n.cuerpo)
        return b

    def _n_para_cada(self, n: F.Nodo) -> Bloque:
        b = self._nuevo("para_cada")
        b.campos["tipo"], b.campos["variable"] = self.texto_variable_para_cada(n.variable)
        b.huecos["coleccion"] = self.texto_expresion(n.texto)
        b.listas["cuerpo"] = self.instrucciones(n.cuerpo)
        return b

    def _n_intentar(self, n: F.Nodo) -> Bloque:
        b = self._nuevo("intentar")
        b.campos["variable"] = self.texto_identificador(n.variable)
        b.listas["cuerpo"] = self.instrucciones(n.cuerpo)
        b.listas["captura"] = self.instrucciones(n.alterno or [])
        return b


# Tabla tipo de nodo de flujo -> conversión (patrón Strategy, como en flujo).
_INSTRUCCION: dict[str, Callable[[Lector, F.Nodo], Bloque]] = {
    "proceso": Lector._n_proceso,
    "declaracion": Lector._n_declaracion,
    "llamada": Lector._n_llamada,
    "leer": Lector._n_leer,
    "escribir": Lector._n_escribir,
    "retornar": Lector._n_retornar,
    "romper": Lector._n_salto,
    "continuar": Lector._n_salto,
    "si": Lector._n_si,
    "segun": Lector._n_casos,
    "coincidir": Lector._n_casos,
    "mientras": Lector._n_ciclo,
    "hacer_mientras": Lector._n_ciclo,
    "para": Lector._n_para,
    "para_cada": Lector._n_para_cada,
    "intentar": Lector._n_intentar,
}
