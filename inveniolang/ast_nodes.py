# Módulo de nodos del Árbol de Sintaxis Abstracta (AST) de InvenioLang 1.0
# Define todas las clases de nodos utilizadas en el AST

class ASTNode:
    """Clase base para todos los nodos del AST."""

    def __init__(self, linea=1, columna=1):
        self.linea = linea
        self.columna = columna

    def __repr__(self):
        return f"{self.__class__.__name__}()"


# ============================================================
# Nodos del programa
# ============================================================

class Program(ASTNode):
    """Nodo raiz del AST. Representa un programa completo.

    Atributos:
        declaraciones_globales: Lista de declaraciones globales (antes de main)
        main: Nodo de la funcion main
        declaraciones_posteriores: Lista de declaraciones globales (despues de main)
        subrutinas: Lista de funciones y procedimientos
    """

    def __init__(self, linea=1, columna=1):
        super().__init__(linea, columna)
        self.declaraciones_globales = []
        self.subrutinas = []
        self.main = None
        self.declaraciones_posteriores = []

    def __repr__(self):
        return f"Program(main={self.main is not None}, subrutinas={len(self.subrutinas)})"


# ============================================================
# Nodos de tipos
# ============================================================

class TipoNodo(ASTNode):
    """Representa un tipo de dato."""

    def __init__(self, nombre_tipo, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre_tipo = nombre_tipo  # 'int', 'float', 'string', 'bool', 'void'

    def __repr__(self):
        return f"TipoNodo({self.nombre_tipo})"


# ============================================================
# Nodos de declaraciones
# ============================================================

class Declaracion(ASTNode):
    """Clase base para declaraciones."""


class VarDecl(Declaracion):
    """Declaracion de variable: tipo nombre [= expresion]"""

    def __init__(self, tipo, nombre, init_expr=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.tipo = tipo
        self.nombre = nombre
        self.init_expr = init_expr

    def __repr__(self):
        return f"VarDecl({self.nombre}: {self.tipo})"


class ConstDecl(Declaracion):
    """Declaracion de constante: const tipo nombre = expresion"""

    def __init__(self, tipo, nombre, init_expr, linea=1, columna=1):
        super().__init__(linea, columna)
        self.tipo = tipo
        self.nombre = nombre
        self.init_expr = init_expr

    def __repr__(self):
        return f"ConstDecl({self.nombre}: {self.tipo})"


class ArrayDecl(Declaracion):
    """Declaracion de arreglo: tipo[tam] nombre [= { ... }]"""

    def __init__(self, tipo, tam, nombre, init_exprs=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.tipo = tipo
        self.tam = tam
        self.nombre = nombre
        self.init_exprs = init_exprs if init_exprs else []

    def __repr__(self):
        return f"ArrayDecl({self.nombre}: {self.tipo}[{self.tam}])"


class MatrixDecl(Declaracion):
    """Declaracion de matriz: tipo[filas][cols] nombre [= { {...}, ... }]"""

    def __init__(self, tipo, filas, cols, nombre, init_filas=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.tipo = tipo
        self.filas = filas
        self.cols = cols
        self.nombre = nombre
        self.init_filas = init_filas if init_filas else []

    def __repr__(self):
        return f"MatrixDecl({self.nombre}: {self.tipo}[{self.filas}][{self.cols}])"


# ============================================================
# Nodos de funciones y procedimientos
# ============================================================

class Parametro(ASTNode):
    """Parametro de funcion o procedimiento."""

    def __init__(self, tipo, nombre, es_arreglo=False, es_matriz=False, linea=1, columna=1):
        super().__init__(linea, columna)
        self.tipo = tipo
        self.nombre = nombre
        self.es_arreglo = es_arreglo
        self.es_matriz = es_matriz

    def __repr__(self):
        if self.es_matriz:
            return f"Param({self.nombre}: {self.tipo}[][])"
        if self.es_arreglo:
            return f"Param({self.nombre}: {self.tipo}[])"
        return f"Param({self.nombre}: {self.tipo})"


class Subrutina(ASTNode):
    """Clase base para funciones y procedimientos."""


class FunctionDecl(Subrutina):
    """Declaracion de funcion: tipo_retorno nombre(params) { bloque }"""

    def __init__(self, tipo_retorno, nombre, parametros, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.tipo_retorno = tipo_retorno
        self.nombre = nombre
        self.parametros = parametros
        self.bloque = bloque

    def __repr__(self):
        return f"FunctionDecl({self.nombre}: {self.tipo_retorno}, params={len(self.parametros)})"


class ProcedureDecl(Subrutina):
    """Declaracion de procedimiento: void nombre(params) { bloque }"""

    def __init__(self, nombre, parametros, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.parametros = parametros
        self.bloque = bloque
        self.tipo_retorno = 'void'

    def __repr__(self):
        return f"ProcedureDecl({self.nombre}, params={len(self.parametros)})"


class MainDecl(Subrutina):
    """Declaracion de la funcion main: void main() { bloque }"""

    def __init__(self, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = 'main'
        self.bloque = bloque
        self.parametros = []
        self.tipo_retorno = 'void'

    def __repr__(self):
        return "MainDecl()"


# ============================================================
# Nodos de bloques e instrucciones
# ============================================================

class Bloque(ASTNode):
    """Bloque de codigo: { elemento* }"""

    def __init__(self, elementos=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.elementos = elementos if elementos else []

    def __repr__(self):
        return f"Bloque(elementos={len(self.elementos)})"


class Instruccion(ASTNode):
    """Clase base para instrucciones."""


class AssignStmt(Instruccion):
    """Instruccion de asignacion: lvalue op_asig expresion"""

    def __init__(self, lvalue, operador, expr, linea=1, columna=1):
        super().__init__(linea, columna)
        self.lvalue = lvalue
        self.operador = operador  # '=', '+=', '-=', '*=', '/=', '%='
        self.expr = expr

    def __repr__(self):
        return f"AssignStmt({self.lvalue} {self.operador} ...)"


class IncDecStmt(Instruccion):
    """Instruccion de incremento/decremento: ++id, id++, --id, id--"""

    def __init__(self, nombre, operador, es_prefijo, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.operador = operador  # '++' o '--'
        self.es_prefijo = es_prefijo

    def __repr__(self):
        prefix = "pre" if self.es_prefijo else "post"
        return f"IncDecStmt({prefix}{self.operador}{self.nombre})"


class PrintStmt(Instruccion):
    """Instruccion de salida: print(expresion)"""

    def __init__(self, expr, linea=1, columna=1):
        super().__init__(linea, columna)
        self.expr = expr

    def __repr__(self):
        return "PrintStmt(...)"


class ReadStmt(Instruccion):
    """Instruccion de entrada: read(identificador)"""

    def __init__(self, nombre, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre

    def __repr__(self):
        return f"ReadStmt({self.nombre})"


class IfStmt(Instruccion):
    """Instruccion condicional: if(cond) { then } [ else { sino } ]"""

    def __init__(self, condicion, bloque_then, bloque_else=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.condicion = condicion
        self.bloque_then = bloque_then
        self.bloque_else = bloque_else

    def __repr__(self):
        return f"IfStmt(else={self.bloque_else is not None})"


class WhileStmt(Instruccion):
    """Instruccion while: while(cond) { bloque }"""

    def __init__(self, condicion, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.condicion = condicion
        self.bloque = bloque

    def __repr__(self):
        return "WhileStmt(...)"


class ForStmt(Instruccion):
    """Instruccion for: for(init; cond; act) { bloque }"""

    def __init__(self, init_stmt, cond_expr, act_stmt, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.init_stmt = init_stmt
        self.cond_expr = cond_expr
        self.act_stmt = act_stmt
        self.bloque = bloque

    def __repr__(self):
        return "ForStmt(...)"


class ReturnStmt(Instruccion):
    """Instruccion return: return [expresion]"""

    def __init__(self, expr=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.expr = expr

    def __repr__(self):
        return f"ReturnStmt(expr={self.expr is not None})"


class BreakStmt(Instruccion):
    """Instruccion break / romper."""

    def __repr__(self):
        return "BreakStmt()"


class ContinueStmt(Instruccion):
    """Instruccion continue / continuar."""

    def __repr__(self):
        return "ContinueStmt()"


class CallStmt(Instruccion):
    """Llamada a subrutina como instruccion."""

    def __init__(self, nombre, argumentos, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.argumentos = argumentos

    def __repr__(self):
        return f"CallStmt({self.nombre}, args={len(self.argumentos)})"


# ============================================================
# Nodos de expresiones
# ============================================================

class Expresion(ASTNode):
    """Clase base para expresiones."""


class ForInit(ASTNode):
    """Inicializador del for: puede ser declaracion, asignacion o vacio."""


class ForInitVar(ForInit):
    """Declaracion de variable en for: tipo nombre [= expr]"""

    def __init__(self, tipo, nombre, init_expr=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.tipo = tipo
        self.nombre = nombre
        self.init_expr = init_expr


class ForInitAsig(ForInit):
    """Asignacion en for: lvalue operador expresion"""

    def __init__(self, lvalue, operador, expr, linea=1, columna=1):
        super().__init__(linea, columna)
        self.lvalue = lvalue
        self.operador = operador
        self.expr = expr


class ForInitIncDec(ForInit):
    """Incremento/decremento en for."""

    def __init__(self, nombre, operador, es_prefijo, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.operador = operador
        self.es_prefijo = es_prefijo


class BinaryOp(Expresion):
    """Operacion binaria: izquierda operador derecha"""

    def __init__(self, operador, izquierda, derecha, linea=1, columna=1):
        super().__init__(linea, columna)
        self.operador = operador
        self.izquierda = izquierda
        self.derecha = derecha

    def __repr__(self):
        return f"BinaryOp({self.operador})"


class UnaryOp(Expresion):
    """Operacion unaria: operador operando (prefija o postfija)"""

    def __init__(self, operador, operando, es_prefijo=True, linea=1, columna=1):
        super().__init__(linea, columna)
        self.operador = operador
        self.operando = operando
        self.es_prefijo = es_prefijo

    def __repr__(self):
        return f"UnaryOp({self.operador})"


class Literal(Expresion):
    """Literal: valor constante con tipo."""

    def __init__(self, valor, tipo_literal, linea=1, columna=1):
        super().__init__(linea, columna)
        self.valor = valor
        self.tipo_literal = tipo_literal  # 'int', 'float', 'string', 'bool'

    def __repr__(self):
        return f"Literal({self.valor}: {self.tipo_literal})"


class Identifier(Expresion):
    """Identificador: referencia a una variable, constante, arreglo o matriz."""

    def __init__(self, nombre, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre

    def __repr__(self):
        return f"Identifier({self.nombre})"


class ArrayAccess(Expresion):
    """Acceso a arreglo: nombre[indice]"""

    def __init__(self, nombre, indice, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.indice = indice

    def __repr__(self):
        return f"ArrayAccess({self.nombre}[...])"


class MatrixAccess(Expresion):
    """Acceso a matriz: nombre[fila][columna]"""

    def __init__(self, nombre, fila, columna, linea=1, col=1):
        super().__init__(linea, col)
        self.nombre = nombre
        self.fila = fila
        self.columna = columna

    def __repr__(self):
        return f"MatrixAccess({self.nombre}[...][...])"


class FunctionCall(Expresion):
    """Llamada a funcion como expresion."""

    def __init__(self, nombre, argumentos, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.argumentos = argumentos

    def __repr__(self):
        return f"FunctionCall({self.nombre}, args={len(self.argumentos)})"


# ============================================================
# Nodos de L-value
# ============================================================

class LValue(ASTNode):
    """Clase base para L-values (lado izquierdo de asignacion)."""


class VarLValue(LValue):
    """L-value de variable simple."""

    def __init__(self, nombre, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre

    def __repr__(self):
        return f"VarLValue({self.nombre})"


class ArrayLValue(LValue):
    """L-value de acceso a arreglo."""

    def __init__(self, nombre, indice, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.indice = indice

    def __repr__(self):
        return f"ArrayLValue({self.nombre}[...])"


class MatrixLValue(LValue):
    """L-value de acceso a matriz."""

    def __init__(self, nombre, fila, columna, linea=1, col=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.fila = fila
        self.columna = columna

    def __repr__(self):
        return f"MatrixLValue({self.nombre}[...][...])"
