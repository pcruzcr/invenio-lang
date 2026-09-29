# Módulo de nodos del Árbol de Sintaxis Abstracta (AST) de InvenioLang 1.0
# Define todas las clases de nodos utilizadas en el AST
# Patrones aplicados: Composite (jerarquía AST), Visitor (doble despacho),
# Factory (creación centralizada), Memento (snapshot para debug)
from __future__ import annotations
from typing import Any, Optional, Dict, Callable

from .patterns import Visitor, Visitable, RegistryFactory


class ASTNode(Visitable):
    """Clase base para todos los nodos del AST. Composite + Visitable."""

    def __init__(self, linea=1, columna=1):
        self.linea = linea
        self.columna = columna

    def accept(self, visitor: Visitor) -> Any:
        """Visitor — doble despacho optimizado (evita isinstance en analizadores)."""
        return visitor.visit(self)

    def to_dict(self) -> Dict[str, Any]:
        """Memento ligero — serialización para debug/snapshot."""
        return {"type": self.__class__.__name__, "linea": self.linea, "columna": self.columna}

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
        clases: Lista de declaraciones de clase (POO, InvenioLang 2.0)
        enums: Lista de declaraciones de enumeracion (Etapa 11)
    """

    def __init__(self, linea=1, columna=1):
        super().__init__(linea, columna)
        self.declaraciones_globales = []
        self.subrutinas = []
        self.main = None
        self.declaraciones_posteriores = []
        self.clases = []
        self.enums = []

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
    """Declaracion de arreglo: tipo[tam] nombre [= { ... }]

    `es_constante` (Etapa 11): const tipo[tam] nombre = { ... } -- un
    arreglo inmutable, sus elementos no se pueden reasignar despues de la
    inicializacion (IL-SEM-031, mismo codigo que una constante escalar).
    """

    def __init__(self, tipo, tam, nombre, init_exprs=None, linea=1, columna=1, es_constante=False):
        # `es_constante` va AL FINAL a propósito: p_decl_arreglo/
        # p_decl_arreglo_postfijo/p_decl_arreglo_clase ya construyen
        # ArrayDecl posicionalmente como (tipo, tam, nombre, init_exprs,
        # linea, columna) -- insertar un parámetro nuevo ANTES de esos dos
        # últimos desalinearía esas llamadas existentes (linea/columna
        # terminarían asignados a otra cosa). Solo la forma const
        # (Etapa 11) lo pasa, y lo hace por nombre.
        super().__init__(linea, columna)
        self.tipo = tipo
        self.tam = tam
        self.nombre = nombre
        self.init_exprs = init_exprs if init_exprs else []
        self.es_constante = es_constante

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
        self.tipo_retorno = "void"

    def __repr__(self):
        return f"ProcedureDecl({self.nombre}, params={len(self.parametros)})"


class MainDecl(Subrutina):
    """Declaracion de la funcion main: void main() { bloque }"""

    def __init__(self, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = "main"
        self.bloque = bloque
        self.parametros = []
        self.tipo_retorno = "void"

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


class ForEachStmt(Instruccion):
    """Instruccion foreach/para_cada (Etapa 12.1):
    para_cada (tipo nombre : arreglo) { bloque }

    Recorre `arreglo` de principio a fin, ligando `nombre` (declarado con
    `tipo`) al elemento actual en cada iteracion, dentro de un ambito
    propio por iteracion (igual que el cuerpo de cualquier ciclo). No es
    azucar sintactica desarmada en el parser -- se ejecuta con un helper
    dedicado en cada capa (ver interpreter.py::_ejecutar_foreach,
    flowchart.py, ir.py) porque desazucararlo de verdad requeriria una
    forma de conocer en tiempo de ejecucion la longitud de un arreglo
    pasado por referencia (un parametro), que hoy no existe como
    expresion de InvenioLang -- mas simple y de igual riesgo mantenerlo
    como una instruccion propia que reutiliza `_entrar_marco`/
    `_salir_marco` (o `entrar_ambito`/`salir_ambito` en semantic.py) igual
    que cualquier otro bloque.
    """

    def __init__(self, tipo, nombre, arreglo, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.tipo = tipo
        self.nombre = nombre
        self.arreglo = arreglo  # Expresion (tipicamente Identifier)
        self.bloque = bloque

    def __repr__(self):
        return f"ForEachStmt({self.tipo} {self.nombre} : ...)"


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


class MemberLValue(LValue):
    """L-value de acceso a miembro: receptor.nombre (POO, InvenioLang 2.0).

    `receptor` es un Identifier, ThisExpr o SuperExpr (ver docs/
    InvenioLang_2.0_POO.md, receptor ::= IDENTIFICADOR | "este" | "padre").
    """

    def __init__(self, receptor, nombre_miembro, linea=1, columna=1):
        super().__init__(linea, columna)
        self.receptor = receptor
        self.nombre_miembro = nombre_miembro

    def __repr__(self):
        return f"MemberLValue(...->{self.nombre_miembro})"


# ============================================================
# Nodos de POO (InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md)
# ============================================================


class AttrDecl(ASTNode):
    """Declaracion de atributo dentro de una clase:
    visibilidad [estatico] tipo nombre [= expr]; (estatico: Etapa 7)"""

    def __init__(self, visibilidad, tipo, nombre, init_expr=None, es_estatico=False, linea=1, columna=1):
        super().__init__(linea, columna)
        self.visibilidad = visibilidad  # 'publico' | 'privado'
        self.tipo = tipo
        self.nombre = nombre
        self.init_expr = init_expr
        self.es_estatico = es_estatico

    def __repr__(self):
        prefijo = "estatico " if self.es_estatico else ""
        return f"AttrDecl({self.visibilidad} {prefijo}{self.nombre}: {self.tipo})"


class MethodDecl(ASTNode):
    """Declaracion de metodo: visibilidad [estatico|abstracto] tipo_retorno
    nombre(params) { bloque } -- `bloque` es None solo si `es_abstracto`
    (entonces la declaracion termina en ';', sin cuerpo). `estatico` y
    `abstracto` son mutuamente excluyentes (Etapa 7)."""

    def __init__(
        self,
        visibilidad,
        tipo_retorno,
        nombre,
        parametros,
        bloque,
        es_estatico=False,
        es_abstracto=False,
        linea=1,
        columna=1,
    ):
        super().__init__(linea, columna)
        self.visibilidad = visibilidad
        self.tipo_retorno = tipo_retorno
        self.nombre = nombre
        self.parametros = parametros
        self.bloque = bloque
        self.es_estatico = es_estatico
        self.es_abstracto = es_abstracto

    def __repr__(self):
        prefijo = "estatico " if self.es_estatico else "abstracto " if self.es_abstracto else ""
        return f"MethodDecl({self.visibilidad} {prefijo}{self.nombre}: {self.tipo_retorno})"


class ConstructorDecl(ASTNode):
    """Constructor: mismo nombre que la clase, sin tipo de retorno.

    `nombre` es el identificador tal como se escribió; el analizador
    semantico valida que coincida con el nombre de la clase (IL-POO-019).
    Una clase puede declarar VARIOS constructores con distinta aridad/tipos
    de parametros (Etapa 10: sobrecarga de constructores, mismo mecanismo
    que la sobrecarga de metodos de la Etapa 7) -- ClassDecl.constructores
    es una lista, no un solo ConstructorDecl.

    `visibilidad` (Etapa 11): 'publico' (por defecto, forma sin prefijo,
    compatibilidad con todo el codigo anterior) o 'privado' -- necesario
    para el patron Singleton (constructor no accesible desde fuera de la
    clase, ver IL-POO-030).
    """

    def __init__(self, nombre, parametros, bloque, visibilidad="publico", linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.parametros = parametros
        self.bloque = bloque
        self.visibilidad = visibilidad

    def __repr__(self):
        return f"ConstructorDecl({self.nombre}, params={len(self.parametros)})"


class ClassDecl(ASTNode):
    """Declaracion de clase: [abstracta] clase Nombre[<T>] [hereda Padre] { miembro* }
    (abstracta: Etapa 7 -- no instanciable, puede tener metodos sin cuerpo).

    `parametro_tipo` (Etapa 7, genericos): nombre del parametro de tipo
    (p.ej. 'T') si la clase es una PLANTILLA generica, o None si es una
    clase normal. Una plantilla nunca llega a semantic.py/interpreter.py
    tal cual -- `SemanticAnalyzer._expandir_genericos` la reemplaza por una
    copia especializada por cada combinacion (Clase, tipo_concreto) que el
    programa realmente usa, antes de cualquier otra validacion (ver
    semantic.py). Una plantilla generica no admite herencia (`padre` es
    siempre None si `parametro_tipo` no lo es) -- alcance deliberadamente
    acotado, ver docs/InvenioLang_2.0_POO.md.
    """

    def __init__(
        self,
        nombre,
        padre,
        atributos,
        metodos,
        constructores,
        es_abstracta=False,
        parametro_tipo=None,
        linea=1,
        columna=1,
        interfaces=None,
        es_interfaz=False,
    ):
        # `interfaces`/`es_interfaz` van AL FINAL a proposito (Etapa 12.3) --
        # mismo criterio documentado en ArrayDecl.__init__ (symbol_table.py/
        # ir.py): insertar parametros nuevos antes de linea/columna
        # desalinearia cualquier llamada posicional existente.
        super().__init__(linea, columna)
        self.nombre = nombre
        self.padre = padre  # str o None (herencia simple, sin cambios)
        self.atributos = atributos  # list[AttrDecl]
        self.metodos = metodos  # list[MethodDecl]
        self.constructores = constructores  # list[ConstructorDecl] (Etapa 10: sobrecarga)
        self.es_abstracta = es_abstracta
        self.parametro_tipo = parametro_tipo
        self.interfaces = interfaces if interfaces else []  # list[str] (Etapa 12.3)
        self.es_interfaz = es_interfaz  # Etapa 12.3: 'interfaz X {...}' (alias de "abstracta clase" con todos los metodos abstractos, solo para mensajes mas claros)

    def __repr__(self):
        prefijo = "interfaz " if self.es_interfaz else "abstracta " if self.es_abstracta else ""
        generico = f"<{self.parametro_tipo}>" if self.parametro_tipo else ""
        implementa = f' implementa {",".join(self.interfaces)}' if self.interfaces else ""
        return f"ClassDecl({prefijo}{self.nombre}{generico}, hereda={self.padre}{implementa})"


class EnumDecl(ASTNode):
    """Declaracion de enumeracion (Etapa 11): enum Nombre { A, B, C }.

    Cada miembro sin carga recibe un valor entero implicito por su
    posicion (0, 1, 2, ...) -- InvenioLang no admite asignar valores
    explicitos, a diferencia de C/Java (alcance deliberadamente acotado:
    cubre el caso de uso pedagogico real -- "un conjunto cerrado de
    nombres con significado", sin la complejidad de valores
    personalizados/con huecos). Un enum asi ("puro") se registra
    internamente como una clase (ClaseInfo con es_enum=True, ver
    symbol_table.py) para reutilizar TODO el mecanismo de acceso a
    miembro estatico ya existente (NombreEnum.MIEMBRO) sin duplicar codigo.

    Etapa 12.9/12.10: un miembro puede en cambio llevar carga (campos),
    convirtiendo el enum en un tipo suma -- ver EnumMiembro. Un enum con
    AL MENOS un miembro con carga usa un mecanismo distinto (clases
    internas por variante, ver semantic.py::_declarar_enum) -- nunca se
    mezclan ambas representaciones dentro del mismo enum.
    """

    def __init__(self, nombre, valores, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.valores = valores  # list[EnumMiembro], en orden de declaracion

    def __repr__(self):
        return f"EnumDecl({self.nombre}, valores={self.valores})"


class EnumMiembro(ASTNode):
    """Un miembro de un enum (Etapa 12.9/12.10): bare (`Rojo`, sin carga,
    forma de la Etapa 11.8 sin cambios) o con carga (`Circulo(entero
    radio)`, tipo suma -- parametros no vacio)."""

    def __init__(self, nombre, parametros=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.parametros = parametros or []  # list[Parametro]

    @property
    def tiene_carga(self):
        return len(self.parametros) > 0

    def __repr__(self):
        if self.parametros:
            return f"EnumMiembro({self.nombre}, params={self.parametros})"
        return f"EnumMiembro({self.nombre})"


class ThisExpr(Expresion):
    """Referencia a la instancia actual: este / this."""

    def __repr__(self):
        return "ThisExpr()"


class NullExpr(Expresion):
    """Referencia nula: nulo / null -- ausencia de objeto (Estructuras de
    Datos, InvenioLang 2.0). Solo asignable/comparable contra un tipo de
    clase, nunca contra un primitivo."""

    def __repr__(self):
        return "NullExpr()"


class SuperExpr(Expresion):
    """Marcador de receptor 'padre'/'super' -- solo valido como receptor de
    un acceso a miembro (padre.metodo(...) / padre.campo), nunca como valor
    independiente. No confundir con SuperCallStmt (llamada al constructor
    del padre)."""

    def __repr__(self):
        return "SuperExpr()"


class NewExpr(Expresion):
    """Instanciacion: nuevo/new NombreClase(argumentos)"""

    def __init__(self, nombre_clase, argumentos, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre_clase = nombre_clase
        self.argumentos = argumentos

    def __repr__(self):
        return f"NewExpr({self.nombre_clase}, args={len(self.argumentos)})"


class MemberAccess(Expresion):
    """Acceso a miembro como expresion: receptor.nombre_miembro (o
    receptor?.nombre_miembro, Etapa 12.2: acceso seguro -- si el receptor
    es nulo, toda la expresion vale nulo en vez de lanzar IL-EJE-010).

    `es_seguro` va AL FINAL de la firma a proposito (ver ir.py/
    symbol_table.py::SymbolEntry -- la Etapa 11.10 dejo documentado por
    que: insertar un parametro nuevo en medio desalinea las llamadas
    posicionales existentes)."""

    def __init__(self, receptor, nombre_miembro, linea=1, columna=1, es_seguro=False):
        super().__init__(linea, columna)
        self.receptor = receptor
        self.nombre_miembro = nombre_miembro
        self.es_seguro = es_seguro

    def __repr__(self):
        return f"MemberAccess(...->{self.nombre_miembro}, seguro={self.es_seguro})"


class MethodCallExpr(Expresion):
    """Llamada a metodo como expresion: receptor.nombre_metodo(argumentos)
    (o receptor?.nombre_metodo(...), Etapa 12.2)."""

    def __init__(self, receptor, nombre_metodo, argumentos, linea=1, columna=1, es_seguro=False):
        super().__init__(linea, columna)
        self.receptor = receptor
        self.nombre_metodo = nombre_metodo
        self.argumentos = argumentos
        self.es_seguro = es_seguro

    def __repr__(self):
        return f"MethodCallExpr(...->{self.nombre_metodo}, args={len(self.argumentos)}, seguro={self.es_seguro})"


class MethodCallStmt(Instruccion):
    """Llamada a metodo como instruccion: receptor.nombre_metodo(argumentos);
    (o receptor?.nombre_metodo(...), Etapa 12.2)."""

    def __init__(self, receptor, nombre_metodo, argumentos, linea=1, columna=1, es_seguro=False):
        super().__init__(linea, columna)
        self.receptor = receptor
        self.nombre_metodo = nombre_metodo
        self.argumentos = argumentos
        self.es_seguro = es_seguro

    def __repr__(self):
        return f"MethodCallStmt(...->{self.nombre_metodo}, args={len(self.argumentos)}, seguro={self.es_seguro})"


class SuperCallStmt(Instruccion):
    """Llamada al constructor del padre: padre/super(argumentos); -- solo
    valida como primera instruccion de un constructor (§5 de la spec de
    POO)."""

    def __init__(self, argumentos, linea=1, columna=1):
        super().__init__(linea, columna)
        self.argumentos = argumentos

    def __repr__(self):
        return f"SuperCallStmt(args={len(self.argumentos)})"


# ============================================================
# Nodos de Etapa 6 (lenguaje estructurado completo)
# ============================================================


class Caso(ASTNode):
    """Un case dentro de un switch: case valor: bloque (sin break implicito
    -- cae al siguiente case si el bloque no termina en break/return)."""

    def __init__(self, valor, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.valor = valor  # Literal (constante)
        self.bloque = bloque

    def __repr__(self):
        return f"Caso({self.valor})"


class SwitchStmt(Instruccion):
    """Instruccion switch/segun: switch(expr) { case v: ... [default: ...] }"""

    def __init__(self, expr, casos, bloque_default=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.expr = expr
        self.casos = casos  # list[Caso]
        self.bloque_default = bloque_default  # Bloque o None

    def __repr__(self):
        return f"SwitchStmt(casos={len(self.casos)}, default={self.bloque_default is not None})"


class CasoMatch(ASTNode):
    """Un caso dentro de emparejar/match (Etapa 12.9/12.10):
    `caso Variante: bloque` (enum puro o variante sin carga) o
    `caso Variante(id1, id2): bloque` (liga cada campo de la variante a un
    nombre nuevo, con alcance propio, dentro del bloque). A diferencia de
    Caso (switch), NO hay fallthrough -- cada caso de emparejar es
    exhaustivo y excluyente por construccion (instanceof de la variante),
    asi que no hace falta -- ni existe -- un break implicito o explicito."""

    def __init__(self, nombre_variante, ligaduras, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.nombre_variante = nombre_variante
        self.ligaduras = ligaduras  # list[str] de nombres a ligar, [] si no hay carga
        self.bloque = bloque

    def __repr__(self):
        return f"CasoMatch({self.nombre_variante}, ligaduras={self.ligaduras})"


class MatchStmt(Instruccion):
    """Instruccion emparejar/match (Etapa 12.9/12.10): pattern matching
    sobre un valor de tipo enum (puro o tipo suma con carga). Construccion
    deliberadamente SEPARADA de switch (ver docs/InvenioLang_GramaticaFormal.md
    -- mezclar destructuring de tipos suma con la semantica de fallthrough
    de switch/case seria confuso). semantic.py valida exhaustividad: deben
    cubrirse todas las variantes declaradas del enum, o existir un
    caso_comodin (`caso _:`)."""

    def __init__(self, expr, casos, caso_comodin=None, linea=1, columna=1):
        super().__init__(linea, columna)
        self.expr = expr
        self.casos = casos  # list[CasoMatch]
        self.caso_comodin = caso_comodin  # Bloque o None

    def __repr__(self):
        return f"MatchStmt(casos={len(self.casos)}, comodin={self.caso_comodin is not None})"


class DoWhileStmt(Instruccion):
    """Instruccion do/hacer ... while/mientras: do { bloque } while(cond);"""

    def __init__(self, bloque, condicion, linea=1, columna=1):
        super().__init__(linea, columna)
        self.bloque = bloque
        self.condicion = condicion

    def __repr__(self):
        return "DoWhileStmt(...)"


class TernaryExpr(Expresion):
    """Operador ternario: condicion ? si_verdadero : si_falso"""

    def __init__(self, condicion, si_verdadero, si_falso, linea=1, columna=1):
        super().__init__(linea, columna)
        self.condicion = condicion
        self.si_verdadero = si_verdadero
        self.si_falso = si_falso

    def __repr__(self):
        return "TernaryExpr(...)"


class LambdaExpr(Expresion):
    """Funcion de primera clase / lambda (Etapa 12.6):
    funcion(tipo1 nombre1, tipo2 nombre2) tipoRetorno { bloque }

    `tipo_retorno` es 'void' o un tipo primitivo/clase, igual que
    `FunctionDecl.tipo_retorno`/`ProcedureDecl`. `parametros` reutiliza
    `Parametro` (el mismo nodo que ya usan funciones/procedimientos y
    metodos) -- un lambda es, en todo salvo poder anidarse dentro de una
    expresion y capturar su entorno lexico, identico a una funcion.
    Representa un TIPO estructural (no nominal, la unica excepcion
    deliberada en un lenguaje nominal en todo lo demas): dos valores
    funcion son de "el mismo tipo" si coinciden exactamente en tipos de
    parametro y de retorno -- ver type_checker.py::_tipo_funcion_str."""

    def __init__(self, parametros, tipo_retorno, bloque, linea=1, columna=1):
        super().__init__(linea, columna)
        self.parametros = parametros  # list[Parametro]
        self.tipo_retorno = tipo_retorno
        self.bloque = bloque

    def __repr__(self):
        tipos = ",".join(p.tipo for p in self.parametros)
        return f"LambdaExpr(({tipos}) -> {self.tipo_retorno})"


class TryStmt(Instruccion):
    """Manejo de excepciones generico: try/intentar { bloque } catch/capturar
    (nombre) { bloque_catch } -- `nombre` queda ligado a una instancia
    sintetica de la clase Excepcion (campos codigo/mensaje) si el bloque try
    levanta un error de ejecucion del catalogo IL-EJE-*."""

    def __init__(self, bloque_try, nombre_catch, bloque_catch, linea=1, columna=1):
        super().__init__(linea, columna)
        self.bloque_try = bloque_try
        self.nombre_catch = nombre_catch
        self.bloque_catch = bloque_catch

    def __repr__(self):
        return f"TryStmt(catch={self.nombre_catch})"


# ============================================================
# Visitor base para AST — Template para semantic/type_checker/interpreter
# ============================================================


class ASTVisitor(Visitor):
    """Visitor base optimizado para recorridos AST. Cada visit_* es Strategy
    intercambiable; agregar nueva operación no modifica nodos (OCP)."""

    def visit_Program(self, node: "Program") -> Any:
        return self.generic_visit(node)

    def visit_Bloque(self, node: "Bloque") -> Any:
        return self.generic_visit(node)

    def visit_VarDecl(self, node: "VarDecl") -> Any:
        return self.generic_visit(node)

    def visit_ConstDecl(self, node: "ConstDecl") -> Any:
        return self.generic_visit(node)

    def visit_ArrayDecl(self, node: "ArrayDecl") -> Any:
        return self.generic_visit(node)

    def visit_MatrixDecl(self, node: "MatrixDecl") -> Any:
        return self.generic_visit(node)

    def visit_FunctionDecl(self, node: "FunctionDecl") -> Any:
        return self.generic_visit(node)

    def visit_ProcedureDecl(self, node: "ProcedureDecl") -> Any:
        return self.generic_visit(node)

    def visit_MainDecl(self, node: "MainDecl") -> Any:
        return self.generic_visit(node)

    def visit_ClassDecl(self, node: "ClassDecl") -> Any:
        return self.generic_visit(node)

    def visit_EnumDecl(self, node: "EnumDecl") -> Any:
        return self.generic_visit(node)


# ============================================================
# Factory — Creación centralizada de nodos AST (optimiza validación
# y permite pooling futuro; evita new disperso en parser)
# ============================================================


class ASTFactory(RegistryFactory):
    """Factory Registry para nodos AST. Uso:
    factory = ASTFactory.get_default()
    node = factory.create('VarDecl', tipo='int', nombre='x', linea=1)
    """

    _default: Optional["ASTFactory"] = None

    @classmethod
    def get_default(cls) -> "ASTFactory":
        if cls._default is None:
            cls._default = cls()
            cls._default._register_defaults()
        return cls._default

    def _register_defaults(self) -> None:
        self.register("Program", lambda **k: Program(**k))
        self.register("VarDecl", lambda **k: VarDecl(**k))
        self.register("ConstDecl", lambda **k: ConstDecl(**k))
        self.register("ArrayDecl", lambda **k: ArrayDecl(**k))
        self.register("MatrixDecl", lambda **k: MatrixDecl(**k))
        self.register("Bloque", lambda **k: Bloque(**k))
        self.register("IfStmt", lambda **k: IfStmt(**k))
        self.register("WhileStmt", lambda **k: WhileStmt(**k))
        self.register("ForStmt", lambda **k: ForStmt(**k))
        self.register("ReturnStmt", lambda **k: ReturnStmt(**k))
        self.register("BinaryOp", lambda **k: BinaryOp(**k))
        self.register("Literal", lambda **k: Literal(**k))
        self.register("Identifier", lambda **k: Identifier(**k))


# ============================================================
# Composite helper — utilidades para recorrer/optimizar árbol
# ============================================================


class ASTWalker:
    """Walker genérico optimizado con iteración sin recursión profunda
    (evita RecursionError en árboles muy profundos)."""

    @staticmethod
    def walk(node: ASTNode, func: Callable[[ASTNode], None]) -> None:
        stack = [node]
        visited = set()
        while stack:
            cur = stack.pop()
            if id(cur) in visited:
                continue
            visited.add(id(cur))
            func(cur)
            for attr in (
                "elementos",
                "bloque",
                "bloque_then",
                "bloque_else",
                "subrutinas",
                "clases",
                "enums",
                "main",
                "declaraciones_globales",
                "declaraciones_posteriores",
            ):
                val = getattr(cur, attr, None)
                if isinstance(val, list):
                    stack.extend(reversed(val))
                elif isinstance(val, ASTNode):
                    stack.append(val)

    @staticmethod
    def count_nodes(node: ASTNode) -> int:
        c = [0]
        ASTWalker.walk(node, lambda n: c.__setitem__(0, c[0] + 1))
        return c[0]
