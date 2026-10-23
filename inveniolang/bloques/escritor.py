"""Bloques → textos InvenioLang y nodos del diagrama de flujo (INV-4003).

Es la inversa de ``lector.py``: cada bloque de valor se escribe con la
gramática de ``parser.py`` poniendo paréntesis **sólo** donde la precedencia
o la asociatividad los exigen (el lector no guarda los paréntesis como
bloques: el anidamiento ya fija el orden de evaluación). Las palabras clave
se escriben en el idioma del modelo; nombres, tipos y literales se copian
tal cual.

Las instrucciones se convierten en nodos de ``inveniolang.flujo`` con el
mismo id, y la generación del programa la hace ``flujo.generacion``: no hay
un segundo generador de código.
"""

from __future__ import annotations

from ..flujo import modelo as F  # noqa: N812 - alias corto del modelo de flujo
from ..flujo.generacion import generar
from ..traductor import PALABRAS_CLAVE
from .lector import NIVELES
from .modelo import Bloque

__all__ = ["Escritor", "PRECEDENCIA"]

# Precedencia de cada operador binario (mayor = liga más fuerte). 1 es la
# ternaria y 2 la coalescencia «??» (asociativa por la derecha).
PRECEDENCIA: dict[str, int] = {"??": 2}
for _k, _nivel in enumerate(NIVELES):
    for _op in _nivel.values():
        PRECEDENCIA[_op] = 3 + _k
_UNARIA = 3 + len(NIVELES)
_POSTFIJA = _UNARIA + 1
_KW_NEUTRAL = {es: tipo for tipo, (es, _en) in PALABRAS_CLAVE.items()}


class Escritor:
    """Escribe bloques como texto en ``idioma``."""

    def __init__(self, idioma: str):
        self.idioma = idioma
        self._k = 0 if idioma == "es" else 1

    def kw(self, tipo_token: str) -> str:
        """Palabra clave en el idioma del escritor."""
        return PALABRAS_CLAVE[tipo_token][self._k]

    def neutral(self, valor: str) -> str:
        """Palabra clave guardada en forma neutral → idioma del escritor."""
        if valor == "abstracto":
            return "abstracto" if self._k == 0 else "abstract"
        return self.kw(_KW_NEUTRAL[valor]) if valor in _KW_NEUTRAL else valor

    # ------------------------------------------------------------ expresiones

    def expresion(self, b: Bloque | None) -> str:
        """Texto de un bloque de valor (``""`` para un hueco vacío)."""
        return self._expr(b)[0]

    def _envolver(self, b: Bloque | None, minimo: int) -> str:
        texto, prec = self._expr(b)
        return f"({texto})" if b is not None and prec < minimo else texto

    def _args(self, bloques: list[Bloque]) -> str:
        return ", ".join(self.expresion(x) for x in bloques)

    def _expr(self, b: Bloque | None) -> tuple[str, int]:
        if b is None:
            return "", _POSTFIJA
        c, h = b.campos, b.huecos
        t = b.tipo
        if t in ("numero", "texto"):
            return c["valor"], _POSTFIJA
        if t == "logico":
            return self.neutral(c["valor"]), _POSTFIJA
        if t in ("nulo", "este", "padre"):
            token = {"nulo": "KW_NULL", "este": "KW_THIS", "padre": "KW_SUPER"}[t]
            return self.kw(token), _POSTFIJA
        if t == "variable":
            return c["nombre"], _POSTFIJA
        if t == "binaria":
            p = PRECEDENCIA[c["op"]]
            if c["op"] == "??":  # asociativa por la derecha
                izq, der = self._envolver(h["izquierda"], p + 1), self._envolver(h["derecha"], p)
            else:
                izq, der = self._envolver(h["izquierda"], p), self._envolver(h["derecha"], p + 1)
            return f"{izq} {c['op']} {der}", p
        if t == "unaria":
            interior = self._envolver(h["valor"], _UNARIA)
            if c["op"] == "-" and interior.startswith("-"):
                interior = f"({interior})"  # «- -x» no debe leerse como «--x»
            return f"{c['op']}{interior}", _UNARIA
        if t == "ternaria":
            cond = self._envolver(h["condicion"], 2)
            return (
                f"{cond} ? {self.expresion(h['si_verdadero'])} : {self.expresion(h['si_falso'])}",
                1,
            )
        if t == "incremento":
            objetivo = self._envolver(h["objetivo"], _POSTFIJA)
            if c["posicion"] == "prefijo":
                return f"{c['op']}{objetivo}", _UNARIA
            return f"{objetivo}{c['op']}", _UNARIA
        if t == "llamada":
            return f"{c['nombre']}({self._args(b.listas['argumentos'])})", _POSTFIJA
        if t in ("propiedad", "llamada_metodo"):
            obj = self._envolver(h["objeto"], _POSTFIJA)
            if h["objeto"] is not None and h["objeto"].tipo == "numero":
                obj = f"({obj})"  # «0.m()» se leería como un real mal formado
            punto = "?." if c["seguro"] else "."
            texto = f"{obj}{punto}{c['nombre']}"
            if t == "llamada_metodo":
                texto += f"({self._args(b.listas['argumentos'])})"
            return texto, _POSTFIJA
        if t == "indice":
            col = self._envolver(h["coleccion"], _POSTFIJA)
            return f"{col}[{self.expresion(h['posicion'])}]", _POSTFIJA
        if t == "nuevo":
            gen = f"<{c['generico']}>" if c["generico"] else ""
            args = self._args(b.listas["argumentos"])
            return f"{self.kw('KW_NEW')} {c['clase']}{gen}({args})", _POSTFIJA
        if t == "nuevo_arreglo":
            return (
                f"{self.kw('KW_NEW')} {c['tipo']}[{self.expresion(h['tamano'])}]",
                _POSTFIJA,
            )
        if t == "lambda":
            params = self.parametros(b.listas["parametros"])
            cuerpo = " ".join(self.lineas(b.listas["cuerpo"]))
            cuerpo = f" {cuerpo} " if cuerpo else " "
            return f"{self.kw('KW_FUNCION')}({params}) {c['retorno']} {{{cuerpo}}}", _POSTFIJA
        raise AssertionError(f"bloque de valor sin escritura: {t}")

    def parametros(self, params: list[Bloque]) -> str:
        """``tipo nombre, …``."""
        return ", ".join(f"{p.campos['tipo']} {p.campos['nombre']}" for p in params)

    # ------------------------------------------------------------ declaraciones

    def declaracion(self, b: Bloque) -> str:
        """Texto (sin ``;``) de ``declarar`` o ``arreglo``."""
        c = b.campos
        const = f"{self.kw('KW_CONST')} " if c["constante"] else ""
        if b.tipo == "declarar":
            texto = f"{const}{c['tipo']} {c['nombre']}"
            if b.huecos["valor"] is not None:
                texto += f" = {self.expresion(b.huecos['valor'])}"
            return texto
        dims = "".join(f"[{d.strip()}]" for d in str(c["dimensiones"]).split(","))
        if c["estilo"] == "nombre":
            texto = f"{const}{c['tipo']} {c['nombre']}{dims}"
        else:
            texto = f"{const}{c['tipo']}{dims} {c['nombre']}"
        if b.listas["filas"]:
            filas = ", ".join(
                "{" + self._args(f.listas["valores"]) + "}" for f in b.listas["filas"]
            )
            texto += " = {" + filas + "}"
        elif b.listas["valores"]:
            texto += " = {" + self._args(b.listas["valores"]) + "}"
        return texto

    def proceso(self, b: Bloque) -> str:
        """Texto de ``asignar`` o ``incrementar``."""
        if b.tipo == "incrementar":
            objetivo = self.expresion(b.huecos["objetivo"])
            op = b.campos["op"]
            return f"{op}{objetivo}" if b.campos["posicion"] == "prefijo" else f"{objetivo}{op}"
        destino = self.expresion(b.huecos["destino"])
        return f"{destino} {b.campos['op']} {self.expresion(b.huecos['valor'])}"

    def literal_caso(self, valor: str) -> str:
        """Valor de un ``caso`` (``verdadero``/``falso`` se escriben en el idioma)."""
        return self.neutral(valor) if valor in ("verdadero", "falso") else valor

    # ------------------------------------------------------------ definiciones

    def firma(self, b: Bloque) -> str:
        """Firma de ``subrutina``, ``metodo`` o ``constructor`` (sin cuerpo)."""
        c = b.campos
        params = self.parametros(b.listas["parametros"])
        if b.tipo == "constructor":
            if c["visibilidad"]:
                vis = self.neutral(c["visibilidad"])
                return f"{vis} {self.kw('KW_CONSTRUCTOR')} {c['nombre']}({params})"
            return f"{c['nombre']}({params})"
        cabeza = f"{c['retorno']} {c['nombre']}({params})"
        if b.tipo == "metodo":
            mod = f"{self.neutral(c['modificador'])} " if c["modificador"] else ""
            cabeza = f"{self.neutral(c['visibilidad'])} {mod}{cabeza}"
        return cabeza

    def cabecera(self, b: Bloque) -> str:
        """Cabecera de ``clase`` o ``interfaz`` (sin la llave)."""
        c = b.campos
        if b.tipo == "interfaz":
            return f"{self.kw('KW_INTERFACE')} {c['nombre']}"
        abstracta = ("abstracta " if self._k == 0 else "abstract ") if c["abstracta"] else ""
        texto = f"{abstracta}{self.kw('KW_CLASS')} {c['nombre']}"
        if c["generico"]:
            texto += f"<{c['generico']}>"
        if c["hereda"]:
            texto += f" {self.kw('KW_EXTENDS')} {c['hereda']}"
        if c["implementa"]:
            texto += f" {self.kw('KW_IMPLEMENTS')} {c['implementa']}"
        return texto

    def codigo(self, b: Bloque) -> str:
        """Texto completo (con ``;`` o ``}``) de un elemento sin diagrama de flujo."""
        c = b.campos
        if b.tipo == "importar":
            return f"{self.kw('KW_IMPORT')} {c['ruta']};"
        if b.tipo == "enumeracion":
            miembros = []
            for m in b.listas["miembros"]:
                texto = m.campos["nombre"]
                if m.campos["con_parametros"]:
                    texto += f"({self.parametros(m.listas['parametros'])})"
                miembros.append(texto)
            return f"{self.kw('KW_ENUM')} {c['nombre']} {{ {', '.join(miembros)} }}"
        if b.tipo == "atributo":
            mod = f"{self.neutral(c['modificador'])} " if c["modificador"] else ""
            texto = f"{self.neutral(c['visibilidad'])} {mod}{c['tipo']} {c['nombre']}"
            if b.huecos["valor"] is not None:
                texto += f" = {self.expresion(b.huecos['valor'])}"
            return texto + ";"
        if b.tipo == "metodo":
            return self.firma(b) + ";"
        return self.declaracion(b) + ";"

    # ------------------------------------------------------------ instrucciones → flujo

    def nodos(self, bloques: list[Bloque]) -> list[F.Nodo]:
        """Nodos del diagrama de flujo de una pila de instrucciones (mismos ids)."""
        return [self.nodo(b) for b in bloques]

    def nodo(self, b: Bloque) -> F.Nodo:
        """Nodo del diagrama de flujo de una instrucción."""
        t, h, c = b.tipo, b.huecos, b.campos
        n = F.Nodo(b.id, t, linea=b.linea)
        if t in ("asignar", "incrementar"):
            n.tipo, n.texto = "proceso", self.proceso(b)
        elif t in ("declarar", "arreglo"):
            n.tipo, n.texto = "declaracion", self.declaracion(b)
        elif t == "llamar":
            n.tipo, n.texto = "llamada", self.expresion(h["llamada"])
        elif t == "llamar_padre":
            n.tipo = "llamada"
            n.texto = f"{self.kw('KW_SUPER')}({self._args(b.listas['argumentos'])})"
        elif t == "leer":
            n.texto = self.expresion(h["destino"])
        elif t == "imprimir":
            n.tipo, n.texto = "escribir", self.expresion(h["valor"])
        elif t == "retornar":
            n.texto = self.expresion(h["valor"])
        elif t == "si":
            n.ramas = [
                F.Rama(self.expresion(r.huecos["condicion"]), self.nodos(r.listas["cuerpo"]))
                for r in b.listas["ramas"]
            ]
            n.alterno = self.nodos(b.listas["sino"]) if c["tiene_sino"] else None
        elif t in ("segun", "coincidir"):
            n.texto = self.expresion(h["expresion"])
            for caso in b.listas["casos"]:
                if t == "segun":
                    etiqueta = self.literal_caso(caso.campos["valor"])
                else:
                    etiqueta = caso.campos["nombre"]
                    if caso.campos["variables"]:
                        etiqueta += f"({caso.campos['variables']})"
                n.ramas.append(F.Rama(etiqueta, self.nodos(caso.listas["cuerpo"])))
            n.alterno = self.nodos(b.listas["por_defecto"]) if c["tiene_defecto"] else None
        elif t in ("mientras", "hacer_mientras"):
            n.texto = self.expresion(h["condicion"])
            n.cuerpo = self.nodos(b.listas["cuerpo"])
        elif t == "para":
            inicio = b.listas["inicio"]
            paso = b.listas["paso"]
            n.inicio = self._parte_para(inicio[0]) if inicio else ""
            n.texto = self.expresion(h["condicion"])
            n.paso = self._parte_para(paso[0]) if paso else ""
            n.cuerpo = self.nodos(b.listas["cuerpo"])
        elif t == "para_cada":
            n.variable = f"{c['tipo']} {c['variable']}"
            n.texto = self.expresion(h["coleccion"])
            n.cuerpo = self.nodos(b.listas["cuerpo"])
        elif t == "intentar":
            n.variable = c["variable"]
            n.cuerpo = self.nodos(b.listas["cuerpo"])
            n.alterno = self.nodos(b.listas["captura"])
        elif t not in ("romper", "continuar"):
            raise AssertionError(f"bloque {t} no es una instrucción")
        return n

    def _parte_para(self, b: Bloque) -> str:
        return self.declaracion(b) if b.tipo in ("declarar", "arreglo") else self.proceso(b)

    def lineas(self, bloques: list[Bloque]) -> list[str]:
        """Código de una pila de instrucciones (una línea por renglón, sin sangría).

        Lo usa el cuerpo de las funciones anónimas, que se escriben en una sola
        línea dentro de su expresión.
        """
        d = F.Diagrama("main", "main", "main", f"{self.kw('KW_VOID')} main()")
        d.cuerpo = self.nodos(bloques)
        generado = generar(F.ModeloFlujo(self.idioma, [F.Elemento("subrutina", diagrama=d)]))
        return [linea.strip() for linea in generado.lineas[1:-1]]
