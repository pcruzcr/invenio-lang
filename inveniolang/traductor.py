"""Traductor de código fuente InvenioLang español ⇄ inglés (INV-1404).

El lenguaje ya aceptaba palabras clave en ambos idiomas (``si``/``if`` producen
el mismo token), pero un programa escrito en uno no se podía *mostrar* en el
otro: un estudiante angloparlante recibía ejemplos con ``mientras`` y
``imprimir``. Este módulo traduce un programa **por tokens**:

* solo se reescriben los lexemas de palabras clave, los nombres de funciones
  integradas (tabla bilingüe de builtins.py) y los campos ``codigo``/``mensaje``
  de la variable de un ``capturar``; todo lo demás (comentarios, literales de
  texto y números, espacios, saltos de línea, identificadores del estudiante)
  se copia byte a byte desde el original, porque el traductor trabaja sobre
  posiciones del texto y no regenera el código desde el AST;
* el resultado produce exactamente la misma secuencia de tokens (mismos tipos)
  y, por tanto, el mismo programa y la misma salida (lo comprueba
  tests/test_traductor.py sobre todos los programas de pruebas/);
* traducir a ``es`` normaliza también los programas mixtos (``void main`` →
  ``vacio main``), así que es → en → es devuelve un programa *equivalente* que
  es punto fijo: volver a traducirlo da el mismo texto.

Casos que exigen contexto (y por eso no es una simple tabla de palabras):

* ``abstract`` → ``abstracta`` delante de ``clase`` y ``abstracto`` delante de un
  método (concordancia de género);
* un identificador igual a un builtin solo se traduce si es una *llamada*
  (``nombre(``) que no es acceso a miembro (``obj.trim(`` puede ser un método
  del estudiante) ni la declaración de un método (``texto trim(``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .builtins import PARES_BUILT_IN, PARES_ORDEN_SUPERIOR
from .errors import ErrorManager
from .i18n import normalizar_idioma
from .lexer import Lexer

# Tipo de token -> (español, inglés). La forma española es la canónica que
# se escribe al traducir hacia "es" (el lexer admite además variantes como
# "abstracta"/"abstracto", tratadas aparte).
PALABRAS_CLAVE: dict[str, tuple[str, str]] = {
    "KW_IF": ("si", "if"),
    "KW_ELSE": ("sino", "else"),
    "KW_WHILE": ("mientras", "while"),
    "KW_FOR": ("para", "for"),
    "KW_FOREACH": ("para_cada", "foreach"),
    "KW_FUNCION": ("funcion", "function"),
    "KW_RETURN": ("retornar", "return"),
    "KW_PRINT": ("imprimir", "print"),
    "KW_READ": ("leer", "read"),
    "KW_INT": ("entero", "int"),
    "KW_FLOAT": ("real", "float"),
    "KW_STRING": ("texto", "string"),
    "KW_BOOL": ("logico", "bool"),
    "KW_VOID": ("vacio", "void"),
    "KW_CONST": ("constante", "const"),
    "KW_TRUE": ("verdadero", "true"),
    "KW_FALSE": ("falso", "false"),
    "KW_BREAK": ("romper", "break"),
    "KW_CONTINUE": ("continuar", "continue"),
    "KW_MAIN": ("main", "main"),
    "KW_CLASS": ("clase", "class"),
    "KW_EXTENDS": ("hereda", "extends"),
    "KW_IMPLEMENTS": ("implementa", "implements"),
    "KW_INTERFACE": ("interfaz", "interface"),
    "KW_NEW": ("nuevo", "new"),
    "KW_THIS": ("este", "this"),
    "KW_SUPER": ("padre", "super"),
    "KW_PUBLIC": ("publico", "public"),
    "KW_PRIVATE": ("privado", "private"),
    "KW_NULL": ("nulo", "null"),
    "KW_SWITCH": ("segun", "switch"),
    "KW_CASE": ("caso", "case"),
    "KW_DEFAULT": ("por_defecto", "default"),
    "KW_MATCH": ("emparejar", "match"),
    "KW_DO": ("hacer", "do"),
    "KW_TRY": ("intentar", "try"),
    "KW_CATCH": ("capturar", "catch"),
    "KW_ABSTRACT": ("abstracto", "abstract"),
    "KW_STATIC": ("estatico", "static"),
    "KW_CONSTRUCTOR": ("constructor", "constructor"),
    "KW_ENUM": ("enumeracion", "enum"),
    "KW_IMPORT": ("importar", "import"),
}

# Campos de la excepción ligada por capturar/catch (symbol_table.py).
CAMPOS_EXCEPCION: dict[str, tuple[str, str]] = {
    "codigo": ("codigo", "code"),
    "code": ("codigo", "code"),
    "mensaje": ("mensaje", "message"),
    "message": ("mensaje", "message"),
}

# Tokens tras los cuales un identificador seguido de "(" es el NOMBRE de una
# declaración (método, función) y no una llamada a un builtin.
_PRECEDE_DECLARACION = {
    "KW_INT",
    "KW_FLOAT",
    "KW_STRING",
    "KW_BOOL",
    "KW_VOID",
    "IDENTIFICADOR",
    "OP_MAYOR",
    "DEL_CORCHETE_C",
    "DEL_PUNTO",
    "OP_ACCESO_SEGURO",
}


@dataclass(frozen=True)
class _Token:
    tipo: str
    lexema: str
    pos: int


def tokens_con_posicion(codigo: str) -> tuple[list[_Token], ErrorManager]:
    """Tokens del lexer real con su posición en el texto (y los errores léxicos)."""
    em = ErrorManager()
    lexer = Lexer(em)
    lexer.build()
    motor = lexer.lexer_obj
    assert motor is not None  # build() siempre lo construye
    motor.input(codigo)
    motor.lineno = 1
    resultado = []
    while True:
        tok = motor.token()
        if tok is None:
            break
        if tok.type == "IDENTIFICADOR" or tok.type.startswith("KW_"):
            resultado.append(_Token(tok.type, tok.value, tok.lexpos))
        else:
            # Para el resto basta el tipo: su texto nunca se reescribe.
            resultado.append(_Token(tok.type, "", tok.lexpos))
    return resultado, em


class TraductorFuente:
    """Reescribe los lexemas traducibles de un programa hacia ``destino``."""

    def __init__(self, destino: str):
        self.destino = normalizar_idioma(destino)
        self._i = 0 if self.destino == "es" else 1

    def traducir(self, codigo: str) -> str:
        """Programa traducido (mismo texto salvo los lexemas traducibles)."""
        tokens, _ = tokens_con_posicion(codigo)
        reemplazos: list[tuple[int, int, str]] = []
        capturas: list[tuple[str, int]] = []  # (variable de catch, profundidad de llaves)
        profundidad = 0
        for k, tok in enumerate(tokens):
            anterior = tokens[k - 1] if k > 0 else None
            siguiente = tokens[k + 1] if k + 1 < len(tokens) else None
            if tok.tipo == "DEL_LLAVE_A":
                profundidad += 1
            elif tok.tipo == "DEL_LLAVE_C":
                profundidad -= 1
                while capturas and capturas[-1][1] > profundidad:
                    capturas.pop()
            receptor = tokens[k - 2] if k > 1 else None
            nuevo = self._traducir_token(tok, anterior, siguiente, receptor, capturas)
            if tok.tipo == "KW_CATCH":
                variable = self._variable_de_captura(tokens, k)
                if variable is not None:
                    capturas.append((variable, profundidad + 1))
            if nuevo is not None and nuevo != tok.lexema:
                reemplazos.append((tok.pos, tok.pos + len(tok.lexema), nuevo))
        partes = []
        cursor = 0
        for ini, fin, texto in reemplazos:
            partes.append(codigo[cursor:ini])
            partes.append(texto)
            cursor = fin
        partes.append(codigo[cursor:])
        return "".join(partes)

    @staticmethod
    def _variable_de_captura(tokens, k):
        """`capturar ( e ) {` -> "e"."""
        tipos = [t.tipo for t in tokens[k + 1 : k + 5]]
        if tipos == ["DEL_PAREN_A", "IDENTIFICADOR", "DEL_PAREN_C", "DEL_LLAVE_A"]:
            return tokens[k + 2].lexema
        return None

    def _traducir_token(self, tok, anterior, siguiente, receptor, capturas):
        if tok.tipo == "KW_ABSTRACT":
            if self.destino == "en":
                return "abstract"
            # Concordancia: "abstracta clase", "abstracto metodo".
            return (
                "abstracta"
                if siguiente is not None and siguiente.tipo == "KW_CLASS"
                else "abstracto"
            )
        if tok.tipo in PALABRAS_CLAVE:
            return PALABRAS_CLAVE[tok.tipo][self._i]
        if tok.tipo != "IDENTIFICADOR":
            return None
        if (
            anterior is not None
            and anterior.tipo == "DEL_PUNTO"
            and tok.lexema in CAMPOS_EXCEPCION
            and receptor is not None
            and receptor.tipo == "IDENTIFICADOR"
            and receptor.lexema in {v for v, _ in capturas}
        ):
            # Solo `e.mensaje` con `e` la variable de un capturar visible: un
            # objeto del estudiante puede tener su propio campo "mensaje".
            return CAMPOS_EXCEPCION[tok.lexema][self._i]
        es_llamada = siguiente is not None and siguiente.tipo == "DEL_PAREN_A"
        es_declaracion = anterior is not None and anterior.tipo in _PRECEDE_DECLARACION
        if es_llamada and not es_declaracion:
            par = PARES_BUILT_IN.get(tok.lexema) or PARES_ORDEN_SUPERIOR.get(tok.lexema)
            if par is not None:
                return par[self._i]
        return None


def traducir(codigo: str, destino: str) -> str:
    """Traduce ``codigo`` al idioma ``destino`` ("es" o "en")."""
    return TraductorFuente(destino).traducir(codigo)
