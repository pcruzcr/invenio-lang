# Módulo del Analizador Léxico (Lexer) de InvenioLang 1.0
# Implementado con PLY (Python Lex-Yacc) - Sección 2 de la especificación
# Reconocimiento de tokens, palabras reservadas bilingües, literales, operadores
# Patrones: Factory (tokens), Strategy (manejo de errores léxicos), Singleton
# (instancia lexer PLY cacheada), Decorator (validación)
from __future__ import annotations

import ply.lex as lex

from .errors import ErrorManager
from .i18n import M
from .patterns import RegistryFactory, Strategy


class LexicalErrorStrategy(Strategy):
    """Strategy para clasificación de errores léxicos — intercambiable."""

    def execute(self, char: str, *args, **kwargs) -> str:
        """Clasifica un carácter inválido en su código IL-LEX."""
        if char in "\"'":
            return "IL-LEX-010/012/013"
        if char.isdigit():
            return "IL-LEX-004"
        if char in "@#$`":
            return "IL-LEX-002"
        return "IL-LEX-005"


class Lexer:
    """Analizador léxico de InvenioLang 1.0.

    Transforma una secuencia de caracteres UTF-8 en una secuencia de tokens.
    Soporta palabras reservadas en inglés y español, literales, operadores
    y gestión de errores léxicos.

    Patrones: Factory (t_DEL_*), Strategy (errores), Singleton (instancia).
    Optimización: tabla de keywords O(1), regex precompilados.
    """

    # ---- Palabras reservadas bilingües (Inglés | Español) ----
    # Ambos idiomas producen el MISMO token interno
    keywords = {
        # Control de flujo
        "if": "KW_IF",
        "si": "KW_IF",
        "else": "KW_ELSE",
        "sino": "KW_ELSE",
        # Iteración
        "while": "KW_WHILE",
        "mientras": "KW_WHILE",
        "for": "KW_FOR",
        "para": "KW_FOR",
        # foreach (Etapa 12.1): azúcar sobre un recorrido de arreglo
        "foreach": "KW_FOREACH",
        "para_cada": "KW_FOREACH",
        # Funciones de primera clase (Etapa 12.5/12.6) -- activa las
        # palabras 'function'/'funcion', reservadas desde la v1.0
        # (Apéndice A) pero sin uso hasta ahora.
        "function": "KW_FUNCION",
        "funcion": "KW_FUNCION",
        # Función. La forma española se admite conforme a §2.5.2 y al
        # Apéndice E.3, que la usan; §16.11, el Apéndice A y §18.3.1 la daban
        # por inexistente en la 1.0 (véase docs/ERRATAS.md).
        "return": "KW_RETURN",
        "retornar": "KW_RETURN",
        # E/S
        "print": "KW_PRINT",
        "imprimir": "KW_PRINT",
        "read": "KW_READ",
        "leer": "KW_READ",
        # Tipos
        "int": "KW_INT",
        "entero": "KW_INT",
        "float": "KW_FLOAT",
        "real": "KW_FLOAT",
        "string": "KW_STRING",
        "texto": "KW_STRING",
        "bool": "KW_BOOL",
        "logico": "KW_BOOL",
        "void": "KW_VOID",
        "vacio": "KW_VOID",
        # Modificador
        "const": "KW_CONST",
        "constante": "KW_CONST",
        # Literales lógicos
        "true": "KW_TRUE",
        "verdadero": "KW_TRUE",
        "false": "KW_FALSE",
        "falso": "KW_FALSE",
        # Control de ciclo
        "break": "KW_BREAK",
        "romper": "KW_BREAK",
        "continue": "KW_CONTINUE",
        "continuar": "KW_CONTINUE",
        # Función main
        "main": "KW_MAIN",
        # POO (InvenioLang 2.0, docs/InvenioLang_2.0_POO.md)
        "class": "KW_CLASS",
        "clase": "KW_CLASS",
        "extends": "KW_EXTENDS",
        "hereda": "KW_EXTENDS",
        # Interfaces (Etapa 12.3): 'implementa' admite VARIAS a la vez,
        # a diferencia de 'hereda' (siempre un solo padre).
        "implements": "KW_IMPLEMENTS",
        "implementa": "KW_IMPLEMENTS",
        "interface": "KW_INTERFACE",
        "interfaz": "KW_INTERFACE",
        "new": "KW_NEW",
        "nuevo": "KW_NEW",
        "this": "KW_THIS",
        "este": "KW_THIS",
        "super": "KW_SUPER",
        "padre": "KW_SUPER",
        "public": "KW_PUBLIC",
        "publico": "KW_PUBLIC",
        "private": "KW_PRIVATE",
        "privado": "KW_PRIVATE",
        "null": "KW_NULL",
        "nulo": "KW_NULL",
        # Estructurado completo (Etapa 6)
        "switch": "KW_SWITCH",
        "segun": "KW_SWITCH",
        "case": "KW_CASE",
        "caso": "KW_CASE",
        "default": "KW_DEFAULT",
        "por_defecto": "KW_DEFAULT",
        # Pattern matching (Etapa 12.9/12.10): reutiliza KW_CASE/KW_DEFAULT
        # de switch -- mismo vocabulario, construccion nueva y separada.
        "match": "KW_MATCH",
        "emparejar": "KW_MATCH",
        "do": "KW_DO",
        "hacer": "KW_DO",
        "try": "KW_TRY",
        "intentar": "KW_TRY",
        "catch": "KW_CATCH",
        "capturar": "KW_CATCH",
        # POO completo (Etapa 7)
        # Concordancia de genero en espanol: "clase abstracta" (femenino)
        # pero "metodo abstracto" (masculino) -- ambas formas al mismo token.
        "abstract": "KW_ABSTRACT",
        "abstracta": "KW_ABSTRACT",
        "abstracto": "KW_ABSTRACT",
        "static": "KW_STATIC",
        "estatico": "KW_STATIC",
        # Cierre de brechas de POO (Etapa 11): 'constructor' es la misma
        # palabra en ambos idiomas -- una sola entrada, no un par.
        "constructor": "KW_CONSTRUCTOR",
        "enum": "KW_ENUM",
        "enumeracion": "KW_ENUM",
        # Modulos (INV-1420): `importar "ruta";` / `import "path";`
        "import": "KW_IMPORT",
        "importar": "KW_IMPORT",
    }

    # Palabras reservadas sin producción propia en la gramática de la 1.0
    # (Apéndice A: "reservada futura"). No pueden usarse como identificadores,
    # pero tampoco participan en ninguna regla sintáctica: al reconocerlas se
    # emite IL-LEX-006 y se entregan al parser como identificadores para no
    # provocar además una cascada de errores sintácticos.
    # 'function'/'funcion' se activan en la Etapa 12.5/12.6 (funciones de
    # primera clase) -- se retiran de este conjunto y pasan a `keywords`.
    reservadas_futuras = {"procedure", "procedimiento"}

    # Lista de todos los tokens (nombres únicos)
    tokens = [
        # Identificadores y literales
        "IDENTIFICADOR",
        "ENTERO_LIT",
        "REAL_LIT",
        "TEXTO_LIT",
        # Operadores aritméticos
        "OP_SUMA",
        "OP_RESTA",
        "OP_MULT",
        "OP_DIV",
        "OP_MOD",
        # Operadores relacionales
        "OP_IGUAL",
        "OP_DISTINTO",
        "OP_MENOR",
        "OP_MAYOR",
        "OP_MENOR_IGUAL",
        "OP_MAYOR_IGUAL",
        # Operadores lógicos
        "OP_AND",
        "OP_OR",
        "OP_NOT",
        # Bit a bit (Etapa 11)
        "OP_BITAND",
        "OP_BITOR",
        "OP_BITXOR",
        "OP_BITNOT",
        "OP_SHL",
        "OP_SHR",
        # Operadores de asignación
        "OP_ASIG",
        "OP_ASIG_SUMA",
        "OP_ASIG_RESTA",
        "OP_ASIG_MULT",
        "OP_ASIG_DIV",
        "OP_ASIG_MOD",
        # Operadores de incremento/decremento
        "OP_INC",
        "OP_DEC",
        # Delimitadores
        "DEL_LLAVE_A",
        "DEL_LLAVE_C",
        "DEL_PAREN_A",
        "DEL_PAREN_C",
        "DEL_CORCHETE_A",
        "DEL_CORCHETE_C",
        "DEL_PUNTO_COMA",
        "DEL_COMA",
        "DEL_PUNTO",
        "DEL_DOSPUNTOS",
        "DEL_INTERROGACION",
        # Seguridad nula (Etapa 12.2)
        "OP_ACCESO_SEGURO",
        "OP_COALESCENCIA",
    ] + list(set(keywords.values()))

    # ---- Reglas de expresión regular para tokens ----
    # Delimitadores (orden: los más largos/complejos primero)
    t_DEL_LLAVE_A = r"\{"
    t_DEL_LLAVE_C = r"\}"
    t_DEL_PAREN_A = r"\("
    t_DEL_PAREN_C = r"\)"
    t_DEL_CORCHETE_A = r"\["
    t_DEL_CORCHETE_C = r"\]"
    t_DEL_PUNTO_COMA = r";"
    t_DEL_COMA = r","
    t_DEL_DOSPUNTOS = r":"
    t_DEL_INTERROGACION = r"\?"

    # Operadores de 2 caracteres (maximal munch: deben ir antes que los de 1)
    t_OP_ASIG_SUMA = r"\+="
    t_OP_ASIG_RESTA = r"-="
    t_OP_ASIG_MULT = r"\*="
    t_OP_ASIG_DIV = r"/="
    t_OP_ASIG_MOD = r"%="
    t_OP_INC = r"\+\+"
    t_OP_DEC = r"--"
    t_OP_IGUAL = r"=="
    t_OP_DISTINTO = r"!="
    t_OP_MENOR_IGUAL = r"<="
    t_OP_MAYOR_IGUAL = r">="
    t_OP_AND = r"&&"
    t_OP_OR = r"\|\|"
    # Desplazamiento de bits (Etapa 11) -- PLY ordena las reglas de cadena
    # por longitud de patrón (mayor primero), así que '<<'/'>>' ya ganan
    # automáticamente sobre '<'/'>' sin importar el orden de declaración
    # aquí; se colocan junto a <=/>= solo por legibilidad.
    t_OP_SHL = r"<<"
    t_OP_SHR = r">>"
    # Seguridad nula (Etapa 12.2): '?.' y '??' -- PLY ordena por longitud de
    # patrón, así que ganan automáticamente sobre '?' (ternario, 1 char) sin
    # ambigüedad; InvenioLang nunca tiene una expresión que empiece con '.'
    # bare (todo acceso a miembro exige receptor), así que "? ." nunca debe
    # leerse como dos tokens separados de un ternario.
    t_OP_ACCESO_SEGURO = r"\?\."
    t_OP_COALESCENCIA = r"\?\?"

    # Operadores de 1 carácter
    t_OP_SUMA = r"\+"
    t_OP_RESTA = r"-"
    t_OP_MULT = r"\*"
    t_OP_DIV = r"/"
    t_OP_MOD = r"%"
    t_OP_ASIG = r"="
    t_OP_MENOR = r"<"
    t_OP_MAYOR = r">"
    t_OP_NOT = r"!"
    # Bit a bit (Etapa 11): & | ^ ~ -- and/or/xor/not de bits, distintos de
    # los logicos &&/||/!  que ya existen.
    t_OP_BITAND = r"&"
    t_OP_BITOR = r"\|"
    t_OP_BITXOR = r"\^"
    t_OP_BITNOT = r"~"

    # Caracteres ignorados (espacios en blanco, §2.3): espacio, tabulador
    # horizontal, retorno de carro y tabulador vertical (U+000B).
    t_ignore = " \t\r\v"

    def __init__(self, error_manager=None):
        """Inicializa el lexer con un gestor de errores opcional."""
        self.error_manager = error_manager or ErrorManager()
        self.lexer_obj = None

    def build(self, **kwargs):
        """Construye el lexer con PLY."""
        self.lexer_obj = lex.lex(module=self, **kwargs)

    def t_newline(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    def t_TEXTO_LIT(self, t):
        r'"[^"\\\n]*(?:\\.[^"\\\n]*)*"|\'[^\'\\\n]*(?:\\.[^\'\\\n]*)*\' '
        # El regex solo captura strings correctamente cerrados
        # sin saltos de linea y con delimitadores coincidentes
        valor = t.value[1:-1]  # Quitar comillas delimitadoras
        t.value = self._procesar_escapes(valor, t)
        return t

    def _t_error_string(self, t):
        """Procesa errores en literales de texto mal formados (IL-LEX-010,
        IL-LEX-012, IL-LEX-013) segun el catalogo Sec.2.14.

        Escanea el literal y reporta UN solo codigo segun como termina:
          - Comilla de cierre distinta a la de apertura -> IL-LEX-013.
          - Cierra correctamente tras un salto de linea no escapado -> IL-LEX-010.
          - Fin de linea o de archivo sin cierre -> IL-LEX-012.

        Retorna el numero de caracteres a consumir (para t.lexer.skip), de
        forma que el lexer no re-procese el contenido del literal danado.
        """
        opening = t.value[0]
        pos = t.lexer.lexpos  # posicion de la comilla inicial
        data = t.lexer.lexdata
        col = self._calc_col(t.lexer, pos)

        i = pos + 1
        hay_salto = False
        while i < len(data):
            ch = data[i]
            if ch == opening:
                # Cierre correcto; no hay error salvo que hubiera salto dentro
                if hay_salto:
                    self.error_manager.error_lexico(
                        "IL-LEX-010",
                        M("IL-LEX-010.salto_linea_dentro_literal"),
                        t.lexer.lineno,
                        col,
                    )
                return (i + 1) - pos
            if ch in "\"'":  # comilla distinta a la de apertura -> IL-LEX-013
                self.error_manager.error_lexico(
                    "IL-LEX-013",
                    M("IL-LEX-013.delimitadores_string_no_coinciden", opening=opening, ch=ch),
                    t.lexer.lineno,
                    col,
                )
                return (i + 1) - pos
            if ch == chr(92) and i + 1 < len(data):
                i += 2  # Saltar caracter escapado
                continue
            if ch == chr(10) or ch == chr(13):
                hay_salto = True
            i += 1

        # Fin de linea/archivo sin encontrar cierre -> IL-LEX-012
        self.error_manager.error_lexico(
            "IL-LEX-012", M("IL-LEX-012.literal_texto_no_terminado"), t.lexer.lineno, col
        )
        return len(data) - pos

    def _procesar_escapes(self, s, t):
        """Procesa secuencias de escape reconocidas en literales de texto."""
        escapes = {
            "n": "\n",
            "t": "\t",
            "r": "\r",
            '"': '"',
            "'": "'",
            "\\": "\\",
        }
        resultado = []
        i = 0
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                if s[i + 1] in escapes:
                    resultado.append(escapes[s[i + 1]])
                    i += 2
                else:
                    # IL-LEX-011: Secuencia de escape desconocida
                    col = self._calc_col(t.lexer, t.lexpos)
                    self.error_manager.error_lexico(
                        "IL-LEX-011",
                        M("IL-LEX-011.secuencia_escape_desconocida", s_i=s[i + 1]),
                        t.lexer.lineno,
                        col,
                    )
                    resultado.append(s[i + 1])
                    i += 2
            else:
                resultado.append(s[i])
                i += 1
        return "".join(resultado)

    def t_REAL_LIT(self, t):
        r"\d+\.\d+([eE][+-]?\d+)?"
        pos = t.lexer.lexpos
        if pos < len(t.lexer.lexdata):
            nxt = t.lexer.lexdata[pos]
            if nxt in "eE":
                # Exponente sin dígitos tras el marcador (1.0e, 1.0e+)
                end = pos + 1
                if end < len(t.lexer.lexdata) and t.lexer.lexdata[end] in "+-":
                    end += 1
                if end >= len(t.lexer.lexdata) or not t.lexer.lexdata[end].isdigit():
                    bad_lit = t.lexer.lexdata[t.lexpos : end]
                    self.error_manager.error_lexico(
                        "IL-LEX-009",
                        M("IL-LEX-009.literal_real_mal_formado_4", bad_lit=bad_lit),
                        t.lexer.lineno,
                        self._calc_col(t.lexer, t.lexpos),
                    )
                    t.lexer.skip(len(bad_lit) - len(t.value))
                    return
        t.value = float(t.value)
        return t

    def t_ENTERO_LIT(self, t):
        r"\d+"
        pos = t.lexer.lexpos
        if pos < len(t.lexer.lexdata):
            nxt = t.lexer.lexdata[pos]
            col = self._calc_col(t.lexer, t.lexpos)
            # IL-LEX-007: Subrayado en entero (ej: 1_000)
            if nxt == "_":
                end = pos
                while end < len(t.lexer.lexdata) and (
                    t.lexer.lexdata[end].isalnum() or t.lexer.lexdata[end] == "_"
                ):
                    end += 1
                bad_lit = t.lexer.lexdata[t.lexpos : end]
                self.error_manager.error_lexico(
                    "IL-LEX-007",
                    M("IL-LEX-007.subrayado_no_permitido_literal", bad_lit=bad_lit),
                    t.lexer.lineno,
                    col,
                )
                t.lexer.skip(len(bad_lit) - len(t.value))
                return
            # IL-LEX-008: Base no soportada (ej: 0xFF, 0b101, 0o77)
            if nxt in "xXbBoO" and t.value == "0":
                end = pos + 1
                while end < len(t.lexer.lexdata) and (
                    t.lexer.lexdata[end].isalnum() or t.lexer.lexdata[end] == "_"
                ):
                    end += 1
                bad_lit = t.lexer.lexdata[t.lexpos : end]
                self.error_manager.error_lexico(
                    "IL-LEX-008",
                    M("IL-LEX-008.base_no_soportada", bad_lit=bad_lit),
                    t.lexer.lineno,
                    col,
                )
                t.lexer.skip(len(bad_lit) - len(t.value))
                return
            # IL-LEX-009: 5. (falta digito despues del punto)
            if nxt == ".":
                bad_lit = t.lexer.lexdata[t.lexpos : pos + 1]  # "5."
                self.error_manager.error_lexico(
                    "IL-LEX-009",
                    M("IL-LEX-009.literal_real_mal_formado_2", bad_lit=bad_lit),
                    t.lexer.lineno,
                    col,
                )
                t.lexer.skip(1)  # consumir el '.'
                return
            # IL-LEX-009: 1e10 (real sin punto decimal)
            if nxt in "eE":
                end = pos + 1
                if end < len(t.lexer.lexdata) and t.lexer.lexdata[end] in "+-":
                    end += 1
                while end < len(t.lexer.lexdata) and t.lexer.lexdata[end].isdigit():
                    end += 1
                bad_lit = t.lexer.lexdata[t.lexpos : end]
                self.error_manager.error_lexico(
                    "IL-LEX-009",
                    M("IL-LEX-009.literal_real_mal_formado_3", bad_lit=bad_lit),
                    t.lexer.lineno,
                    col,
                )
                t.lexer.skip(len(bad_lit) - len(t.value))
                return
            # IL-LEX-004: Identificador inicia con digito
            if nxt.isalpha() or nxt == "_":
                end = pos
                while end < len(t.lexer.lexdata) and (
                    t.lexer.lexdata[end].isalnum() or t.lexer.lexdata[end] == "_"
                ):
                    end += 1
                bad_id = t.lexer.lexdata[t.lexpos : end]
                self.error_manager.error_lexico(
                    "IL-LEX-004",
                    M("IL-LEX-004.identificador_inicia_digito", bad_id=bad_id),
                    t.lexer.lineno,
                    col,
                )
                t.lexer.skip(len(bad_id) - len(t.value))
                return
        t.value = int(t.value)
        return t

    def t_DEL_PUNTO(self, t):
        r"\."
        # Debe ser función (no regla de string) para poder interceptar aquí
        # el caso ".5" -- real mal formado, IL-LEX-009 -- antes de que se
        # confunda con un punto suelto de acceso a miembro (POO, v2.0).
        pos = t.lexer.lexpos
        data = t.lexer.lexdata
        if pos < len(data) and data[pos].isdigit():
            col = self._calc_col(t.lexer, t.lexpos)
            i = pos
            while i < len(data) and data[i].isdigit():
                i += 1
            malformed = data[t.lexpos : i]
            self.error_manager.error_lexico(
                "IL-LEX-009",
                M("IL-LEX-009.literal_real_mal_formado", malformed=malformed),
                t.lexer.lineno,
                col,
            )
            t.lexer.skip(len(malformed) - 1)
            return
        return t

    def t_IDENTIFICADOR(self, t):
        r"[A-Za-z_][A-Za-z0-9_]*"
        # Verificar si es palabra reservada (case-sensitive)
        if t.value in self.reservadas_futuras:
            # IL-LEX-006: el lexema coincide con una palabra reservada (§2.5.1,
            # Apéndice A). Reservada para versiones futuras del lenguaje.
            self.error_manager.error_lexico(
                "IL-LEX-006",
                M("IL-LEX-006.palabra_reservada_lenguaje_no", value=t.value),
                t.lexer.lineno,
                self._calc_col(t.lexer, t.lexpos),
            )
            t.type = "IDENTIFICADOR"
            return t
        t.type = self.keywords.get(t.value, "IDENTIFICADOR")
        return t

    # ---- Comentarios ----
    def t_COMENTARIO_LINEA(self, t):
        r"//[^\n]*"
        pass  # Descartar

    def t_COMENTARIO_BLOQUE(self, t):
        r"/\*[\s\S]*?\*/"
        t.lexer.lineno += t.value.count("\n")

    def t_COMENTARIO_BLOQUE_NO_TERMINADO(self, t):
        r"/\*[\s\S]*"
        # IL-LEX-014: Comentario de bloque sin cerrar (llega a EOF)
        col = self._calc_col(t.lexer, t.lexpos)
        self.error_manager.error_lexico(
            "IL-LEX-014", M("IL-LEX-014.comentario_bloque_no_terminado"), t.lexer.lineno, col
        )
        t.lexer.lineno += t.value.count("\n")

    # ---- Manejo de errores léxicos ----
    def t_error(self, t):
        """Maneja caracteres inválidos según el catálogo de errores §2.14."""
        char = t.value[0]
        col = self._calc_col(t.lexer, t.lexpos)

        # Detectar inicio de literal de texto mal formado
        if char in "\"'":
            n = self._t_error_string(t)
            t.lexer.skip(n)
        elif char.isdigit():
            # IL-LEX-004: Identificador inicia con dígito
            resto = t.value[0]
            for i in range(1, len(t.value)):
                if t.value[i].isalnum() or t.value[i] == "_":
                    resto += t.value[i]
                else:
                    break
            self.error_manager.error_lexico(
                "IL-LEX-004",
                M("IL-LEX-004.identificador_inicia_digito_2", resto=resto),
                t.lexer.lineno,
                col,
            )
            t.lexer.skip(len(resto) - 1)
        elif char in "@#$`":
            # IL-LEX-002: caracteres nunca válidos en InvenioLang.
            # Nota Etapa 11: '&', '|', '^', '~', '%', '<', '>', '!' son
            # operadores válidos (bit a bit / relacionales / lógicos) y
            # NO deben caer aquí; si llegan a t_error es porque el
            # contexto es realmente inválido, pero se reporta como
            # IL-LEX-005 para no confundir al estudiante con "carácter
            # inválido" cuando el carácter sí existe en el lenguaje.
            self.error_manager.error_lexico(
                "IL-LEX-002", M("IL-LEX-002.caracter_invalido", char=char), t.lexer.lineno, col
            )
            t.lexer.skip(1)
        elif ord(char) < 32 and char not in "\n\r\t":
            self.error_manager.error_lexico(
                "IL-LEX-003",
                M("IL-LEX-003.caracter_control_invalido_x", ord_char=ord(char)),
                t.lexer.lineno,
                col,
            )
            t.lexer.skip(1)
        else:
            self.error_manager.error_lexico(
                "IL-LEX-005",
                M("IL-LEX-005.caracter_ilegal_identificador", char=char),
                t.lexer.lineno,
                col,
            )
            t.lexer.skip(1)

    def _calc_col(self, lexer_obj, lexpos):
        """Calcula el número de columna (base 1) desde la posición en el input."""
        if hasattr(lexer_obj, "lexdata") and lexer_obj.lexdata:
            data = lexer_obj.lexdata
            inicio = 0
            if "\n" in data[:lexpos]:
                inicio = data.rfind("\n", 0, lexpos) + 1
            return lexpos - inicio + 1
        return 1

    def tokenizar(self, codigo, archivo="<desconocido>"):
        """Tokeniza una cadena de código fuente.

        Args:
            codigo: Código fuente como string
            archivo: Nombre del archivo (para reporte de errores)

        Retorna:
            Lista de tuplas (tipo, valor, linea, columna)
        """
        self.error_manager.set_archivo(archivo)

        if not self.lexer_obj:
            self.build()

        self.lexer_obj.input(codigo)
        self.lexer_obj.lineno = 1

        tokens = []
        while True:
            tok = self.lexer_obj.token()
            if not tok:
                break
            col = self._calc_col(self.lexer_obj, tok.lexpos)
            tokens.append((tok.type, tok.value, tok.lineno, col))

        return tokens


class TokenFactory(RegistryFactory):
    """Factory para tokens — centraliza tipos y validación."""

    _default: TokenFactory | None = None

    @classmethod
    def get_default(cls) -> TokenFactory:
        """Retorna la factoría compartida (Singleton)."""
        if cls._default is None:
            cls._default = cls()
        return cls._default
