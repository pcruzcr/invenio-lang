# Módulo de Verificación de Tipos de InvenioLang 1.0
# Implementa el sistema de tipos de la Sección 4 y las reglas de la Sección 14
# Verifica compatibilidad de tipos en todas las operaciones

from .ast_nodes import *
from .symbol_table import TipoSimbolo
from .builtins import es_built_in


class TypeChecker:
    """Verificador de tipos de InvenioLang 1.0.

    Recorre el AST anotado por el analizador semántico y verifica:
    - Compatibilidad de tipos en asignaciones (IL-TIPO-001)
    - Operadores aritméticos sobre tipos válidos (IL-TIPO-010, IL-TIPO-011, IL-TIPO-013)
    - Operadores relacionales sobre tipos válidos (IL-TIPO-012)
    - Operadores lógicos sobre bool (IL-TIPO-018)
    - Condiciones de tipo bool (IL-TIPO-019)
    - ++/-- sobre int (IL-TIPO-016)
    - Unarios sobre tipos compatibles (IL-TIPO-017)
    - Índices de tipo int (IL-TIPO-021)
    - Promoción implícita int -> float
    """

    def __init__(self, error_manager, tabla_simbolos):
        self.error_manager = error_manager
        self.tabla = tabla_simbolos

    def verificar(self, ast):
        """Verifica tipos en el AST completo."""
        if ast is None:
            return
        self._visitar_programa(ast)

    def _visitar_programa(self, nodo):
        """Visita el programa completo."""
        for d in nodo.declaraciones_globales:
            self._visitar_declaracion(d)
        for d in nodo.declaraciones_posteriores:
            self._visitar_declaracion(d)
        if nodo.main:
            self.tabla.entrar_ambito()
            self._visitar_bloque(nodo.main.bloque)
            self.tabla.salir_ambito()
        for sub in nodo.subrutinas:
            self._visitar_subrutina(sub)

    def _visitar_subrutina(self, nodo):
        """Visita una subrutina."""
        if isinstance(nodo, FunctionDecl):
            self._visitar_funcion(nodo)
        elif isinstance(nodo, ProcedureDecl):
            self._visitar_bloque(nodo.bloque)

    def _visitar_funcion(self, nodo):
        """Visita una función verificando tipos."""
        from .symbol_table import TipoSimbolo
        self.tabla.entrar_ambito()
        for p in nodo.parametros:
            # Re-declarar parámetros en el nuevo ámbito del type checker
            ts = TipoSimbolo.PARAMETRO
            if p.es_matriz:
                ts = TipoSimbolo.PARAM_MATRIZ
            elif p.es_arreglo:
                ts = TipoSimbolo.PARAM_ARREGLO
            entrada = self.tabla.declarar(p.nombre, ts, p.tipo, p.linea, p.columna)
            if entrada:
                entrada.inicializado = True
        self._visitar_bloque(nodo.bloque)
        self.tabla.salir_ambito()

    def _visitar_bloque(self, bloque):
        """Visita un bloque."""
        if bloque is None:
            return
        for elem in bloque.elementos:
            if isinstance(elem, (VarDecl, ConstDecl, ArrayDecl, MatrixDecl)):
                self._visitar_declaracion(elem)
            else:
                self._visitar_instruccion(elem)

    def _visitar_declaracion(self, nodo):
        """Verifica tipos en declaraciones."""
        if isinstance(nodo, VarDecl):
            self.tabla.declarar(nodo.nombre, TipoSimbolo.VARIABLE,
                                nodo.tipo, nodo.linea, nodo.columna)
            if nodo.init_expr:
                tipo_expr = self._obtener_tipo(nodo.init_expr)
                if tipo_expr and not self._compatible(nodo.tipo, tipo_expr):
                    self.error_manager.error_tipo(
                        self._codigo_incompatibilidad(nodo.tipo, tipo_expr),
                        f'Tipo incompatible: variable "{nodo.nombre}" es {nodo.tipo}, '
                        f'pero la expresión es {tipo_expr}',
                        nodo.linea, nodo.columna
                    )
        elif isinstance(nodo, ConstDecl):
            self.tabla.declarar(nodo.nombre, TipoSimbolo.CONSTANTE,
                                nodo.tipo, nodo.linea, nodo.columna)
            tipo_expr = self._obtener_tipo(nodo.init_expr)
            if tipo_expr and not self._compatible(nodo.tipo, tipo_expr):
                self.error_manager.error_tipo(
                    self._codigo_incompatibilidad(nodo.tipo, tipo_expr),
                    f'Tipo incompatible: constante "{nodo.nombre}" es {nodo.tipo}, '
                    f'pero la expresión es {tipo_expr}',
                    nodo.linea, nodo.columna
                )
        elif isinstance(nodo, ArrayDecl):
            entry = self.tabla.declarar(nodo.nombre, TipoSimbolo.ARREGLO,
                                        nodo.tipo, nodo.linea, nodo.columna)
            if entry and isinstance(nodo.tam, int):
                entry.tam_arreglo = nodo.tam
            for e in nodo.init_exprs:
                tipo_e = self._obtener_tipo(e)
                if tipo_e and not self._compatible(nodo.tipo, tipo_e):
                    self.error_manager.error_tipo(
                        'IL-TIPO-001',
                        f'Tipo incompatible en inicializador de arreglo '
                        f'"{nodo.nombre}"',
                        e.linea, e.columna
                    )
        elif isinstance(nodo, MatrixDecl):
            entry = self.tabla.declarar(nodo.nombre, TipoSimbolo.MATRIZ,
                                        nodo.tipo, nodo.linea, nodo.columna)
            if entry:
                if isinstance(nodo.filas, int):
                    entry.filas_matriz = nodo.filas
                if isinstance(nodo.cols, int):
                    entry.cols_matriz = nodo.cols
            for fila in nodo.init_filas:
                for e in fila:
                    tipo_e = self._obtener_tipo(e)
                    if tipo_e and not self._compatible(nodo.tipo, tipo_e):
                        self.error_manager.error_tipo(
                            'IL-TIPO-001',
                            f'Tipo incompatible en inicializador de matriz '
                            f'"{nodo.nombre}"',
                            e.linea, e.columna
                        )

    def _visitar_instruccion(self, nodo):
        """Verifica tipos en instrucciones."""
        if isinstance(nodo, AssignStmt):
            self._visitar_asignacion(nodo)
        elif isinstance(nodo, IncDecStmt):
            self._verificar_inc_dec(nodo)
        elif isinstance(nodo, PrintStmt):
            self._verificar_print(nodo)
        elif isinstance(nodo, ReadStmt):
            self._verificar_read(nodo)
        elif isinstance(nodo, IfStmt):
            self._verificar_condicion(nodo.condicion, nodo.linea, nodo.columna)
            self._visitar_bloque(nodo.bloque_then)
            if nodo.bloque_else:
                self._visitar_bloque(nodo.bloque_else)
        elif isinstance(nodo, WhileStmt):
            self._verificar_condicion(nodo.condicion, nodo.linea, nodo.columna)
            self._visitar_bloque(nodo.bloque)
        elif isinstance(nodo, ForStmt):
            if nodo.init_stmt and isinstance(nodo.init_stmt, ForInitVar):
                pass
            if nodo.cond_expr:
                self._verificar_condicion(nodo.cond_expr, nodo.linea, nodo.columna)
            if nodo.act_stmt and isinstance(nodo.act_stmt, ForInitAsig):
                tipo_lv = self._obtener_tipo_lvalue(nodo.act_stmt.lvalue)
                tipo_ex = self._obtener_tipo(nodo.act_stmt.expr)
                if tipo_lv and tipo_ex and not self._compatible(tipo_lv, tipo_ex):
                    self.error_manager.error_tipo(
                        'IL-TIPO-001',
                        f'Tipo incompatible en acción de for',
                        nodo.linea, nodo.columna
                    )
            self._visitar_bloque(nodo.bloque)
        elif isinstance(nodo, ReturnStmt):
            if nodo.expr:
                self._obtener_tipo(nodo.expr)
        elif isinstance(nodo, CallStmt):
            self._verificar_llamada(nodo.nombre, nodo.argumentos, nodo)
        elif isinstance(nodo, FunctionCall):
            self._verificar_llamada(nodo.nombre, nodo.argumentos, nodo)

    def _visitar_asignacion(self, nodo):
        """Verifica tipos en asignación, simple y compuesta (§5.3)."""
        tipo_lvalue = self._obtener_tipo_lvalue(nodo.lvalue)
        tipo_expr = self._obtener_tipo(nodo.expr)

        if not (tipo_lvalue and tipo_expr):
            return

        # Asignación compuesta: los tipos deben admitir además la operación
        # subyacente (§5.3.2). `x op= e` equivale a `x = x op e`.
        if nodo.operador != '=':
            if not self._verificar_op_compuesta(nodo.operador, tipo_lvalue,
                                                tipo_expr, nodo):
                return

        if not self._compatible(tipo_lvalue, tipo_expr):
            self.error_manager.error_tipo(
                self._codigo_incompatibilidad(tipo_lvalue, tipo_expr),
                f'Tipo incompatible en asignación: se esperaba {tipo_lvalue}, '
                f'se encontró {tipo_expr}',
                nodo.linea, nodo.columna
            )

    def _verificar_op_compuesta(self, operador, tipo_lv, tipo_ex, nodo):
        """Verifica los tipos de un operador de asignación compuesta (§5.3.2).

        Retorna False si ya se reportó un error, para no encadenar un
        IL-TIPO-001 redundante sobre el mismo nodo.
        """
        tipos = (tipo_lv, tipo_ex)

        # %= sólo entre enteros (§5.3.2, IL-TIPO-010)
        if operador == '%=':
            if 'float' in tipos:
                self.error_manager.error_tipo(
                    'IL-TIPO-010',
                    'El operador %= no está definido para float',
                    nodo.linea, nodo.columna
                )
                return False

        # -=, *=, /=, %= no aplicables a string (IL-TIPO-011)
        if operador in ('-=', '*=', '/=', '%=') and 'string' in tipos:
            self.error_manager.error_tipo(
                'IL-TIPO-011',
                f'El operador {operador} no está definido para string',
                nodo.linea, nodo.columna
            )
            return False

        # Ningún operador compuesto es aplicable a bool (IL-TIPO-013)
        if 'bool' in tipos:
            self.error_manager.error_tipo(
                'IL-TIPO-013',
                f'El operador {operador} no está definido para bool',
                nodo.linea, nodo.columna
            )
            return False

        return True

    def _obtener_tipo_lvalue(self, lvalue):
        """Obtiene el tipo de un lvalue."""
        if isinstance(lvalue, VarLValue):
            entrada = self.tabla.buscar(lvalue.nombre)
            return entrada.tipo_dato if entrada else None
        elif isinstance(lvalue, ArrayLValue):
            entrada = self.tabla.buscar(lvalue.nombre)
            if entrada:
                return entrada.tipo_dato  # El tipo base del arreglo
            return None
        elif isinstance(lvalue, MatrixLValue):
            entrada = self.tabla.buscar(lvalue.nombre)
            if entrada:
                return entrada.tipo_dato  # El tipo base de la matriz
            return None
        return None

    def _verificar_inc_dec(self, nodo):
        """Verifica ++/--: solo aplicable a int (IL-TIPO-016)."""
        entrada = self.tabla.buscar(nodo.nombre)
        if entrada and entrada.tipo_dato != 'int':
            self.error_manager.error_tipo(
                'IL-TIPO-016',
                f'Operador {nodo.operador} no aplicable a tipo {entrada.tipo_dato}',
                nodo.linea, nodo.columna
            )

    def _verificar_print(self, nodo):
        """Verifica print: no acepta void (IL-TIPO-020)."""
        tipo = self._obtener_tipo(nodo.expr)
        if tipo == 'void':
            self.error_manager.error_tipo(
                'IL-TIPO-020',
                'print/imprimir no acepta argumento de tipo void',
                nodo.linea, nodo.columna
            )

    def _verificar_read(self, nodo):
        """Verifica read: la variable debe existir."""
        entrada = self.tabla.buscar(nodo.nombre)
        if entrada and entrada.tipo_dato == 'void':
            self.error_manager.error_tipo(
                'IL-TIPO-015',
                f'No se puede leer en variable de tipo void',
                nodo.linea, nodo.columna
            )

    def _verificar_condicion(self, expr, linea, columna):
        """Verifica que la condición sea bool (IL-TIPO-019)."""
        tipo = self._obtener_tipo(expr)
        if tipo and tipo != 'bool':
            self.error_manager.error_tipo(
                'IL-TIPO-019',
                'La condición debe ser de tipo bool',
                linea, columna
            )

    def _verificar_llamada(self, nombre, argumentos, nodo):
        """Verifica tipos en llamada a función."""
        entrada = self.tabla.buscar_funcion(nombre)
        es_builtin = es_built_in(nombre)
        if entrada and entrada.params:
            for i, (arg, param_tipo) in enumerate(zip(argumentos, entrada.params)):
                tipo_arg = self._obtener_tipo(arg)
                # Paso por referencia de arreglos/matrices (§12.2.1, §13.2.1):
                # al parámetro '[]'/'[][]' se le pasa el identificador del arreglo/matriz.
                if param_tipo.endswith(']') and isinstance(arg, Identifier):
                    e_arg = self.tabla.buscar(arg.nombre)
                    if e_arg and e_arg.tipo_simbolo in (TipoSimbolo.ARREGLO, TipoSimbolo.MATRIZ,
                                                        TipoSimbolo.PARAM_ARREGLO,
                                                        TipoSimbolo.PARAM_MATRIZ):
                        continue
                if tipo_arg and not self._compatible(param_tipo, tipo_arg):
                    if es_builtin:
                        # IL-SEM-081: tipo de argumento de función integrada (§19.11)
                        self.error_manager.error_tipo(
                            'IL-SEM-081',
                            f'Tipo de argumento incompatible en función integrada '
                            f'"{nombre}": se esperaba {param_tipo}, se encontró {tipo_arg}',
                            arg.linea if hasattr(arg, 'linea') else nodo.linea,
                            arg.columna if hasattr(arg, 'columna') else nodo.columna
                        )
                    else:
                        self.error_manager.error_tipo(
                            'IL-TIPO-001',
                            f'Tipo incompatible en argumento {i+1} de "{nombre}": '
                            f'se esperaba {param_tipo}, se encontró {tipo_arg}',
                            arg.linea if hasattr(arg, 'linea') else nodo.linea,
                            arg.columna if hasattr(arg, 'columna') else nodo.columna
                        )

    def _obtener_tipo(self, nodo):
        """Determina el tipo de una expresión.

        Retorna el nombre del tipo ('int', 'float', 'string', 'bool', 'void')
        o None si no se puede determinar.
        """
        if nodo is None:
            return None

        if isinstance(nodo, Literal):
            return nodo.tipo_literal

        if isinstance(nodo, Identifier):
            entrada = self.tabla.buscar(nodo.nombre)
            if entrada:
                return entrada.tipo_dato
            return None

        if isinstance(nodo, ArrayAccess):
            tipo_idx = self._obtener_tipo(nodo.indice)
            if tipo_idx and tipo_idx != 'int':
                self.error_manager.error_tipo(
                    'IL-TIPO-021',
                    f'Índice de arreglo debe ser int, no {tipo_idx}',
                    nodo.indice.linea if hasattr(nodo.indice, 'linea') else 0,
                    nodo.indice.columna if hasattr(nodo.indice, 'columna') else 0
                )
            entrada = self.tabla.buscar(nodo.nombre)
            # IL-WARN-030: índice literal fuera de rango (§12.4)
            if (entrada and isinstance(entrada.tam_arreglo, int)
                    and isinstance(nodo.indice, Literal)
                    and isinstance(nodo.indice.valor, int)):
                if nodo.indice.valor < 0 or nodo.indice.valor >= entrada.tam_arreglo:
                    self.error_manager.advertencia(
                        'IL-WARN-030',
                        f'Índice literal {nodo.indice.valor} fuera de rango '
                        f'[0,{entrada.tam_arreglo - 1}] en arreglo "{nodo.nombre}"',
                        nodo.indice.linea, nodo.indice.columna
                    )
            if entrada:
                return entrada.tipo_dato
            return None

        if isinstance(nodo, MatrixAccess):
            tipo_f = self._obtener_tipo(nodo.fila)
            tipo_c = self._obtener_tipo(nodo.columna)
            if tipo_f and tipo_f != 'int':
                self.error_manager.error_tipo(
                    'IL-TIPO-021',
                    f'Índice de fila de matriz debe ser int, no {tipo_f}',
                    nodo.fila.linea if hasattr(nodo.fila, 'linea') else 0,
                    nodo.fila.columna if hasattr(nodo.fila, 'columna') else 0
                )
            if tipo_c and tipo_c != 'int':
                self.error_manager.error_tipo(
                    'IL-TIPO-021',
                    f'Índice de columna de matriz debe ser int, no {tipo_c}',
                    nodo.columna.linea if hasattr(nodo.columna, 'linea') else 0,
                    nodo.columna.columna if hasattr(nodo.columna, 'columna') else 0
                )
            entrada = self.tabla.buscar(nodo.nombre)
            # IL-WARN-030: índices literales fuera de rango (§13.4)
            if entrada and isinstance(entrada.filas_matriz, int) \
                    and isinstance(nodo.fila, Literal) and isinstance(nodo.fila.valor, int):
                if nodo.fila.valor < 0 or nodo.fila.valor >= entrada.filas_matriz:
                    self.error_manager.advertencia(
                        'IL-WARN-030',
                        f'Índice de fila literal {nodo.fila.valor} fuera de rango '
                        f'[0,{entrada.filas_matriz - 1}] en matriz "{nodo.nombre}"',
                        nodo.fila.linea, nodo.fila.columna
                    )
            if entrada and isinstance(entrada.cols_matriz, int) \
                    and isinstance(nodo.columna, Literal) and isinstance(nodo.columna.valor, int):
                if nodo.columna.valor < 0 or nodo.columna.valor >= entrada.cols_matriz:
                    self.error_manager.advertencia(
                        'IL-WARN-030',
                        f'Índice de columna literal {nodo.columna.valor} fuera de rango '
                        f'[0,{entrada.cols_matriz - 1}] en matriz "{nodo.nombre}"',
                        nodo.columna.linea, nodo.columna.columna
                    )
            if entrada:
                return entrada.tipo_dato
            return None

        if isinstance(nodo, FunctionCall):
            entrada = self.tabla.buscar_funcion(nodo.nombre)
            # Verificar tipos de argumentos (IL-TIPO-001 / IL-SEM-081)
            self._verificar_llamada(nodo.nombre, nodo.argumentos, nodo)
            if entrada and entrada.tipo_simbolo == TipoSimbolo.FUNCION:
                return entrada.tipo_retorno
            return 'void' if entrada else None

        if isinstance(nodo, BinaryOp):
            return self._tipo_binario(nodo)

        if isinstance(nodo, UnaryOp):
            return self._tipo_unario(nodo)

        return None

    def _tipo_binario(self, nodo):
        """Determina el tipo resultante de una operación binaria.

        Verifica compatibilidad de operandos según las reglas de la Sección 4.
        """
        t_left = self._obtener_tipo(nodo.izquierda)
        t_right = self._obtener_tipo(nodo.derecha)

        if t_left is None or t_right is None:
            return None

        op = nodo.operador

        # IL-WARN-003: divisor literal cero (§6.6)
        if op in ('/', '%') and isinstance(nodo.derecha, Literal) and nodo.derecha.valor == 0:
            self.error_manager.advertencia(
                'IL-WARN-003',
                'Divisor literal cero',
                nodo.derecha.linea, nodo.derecha.columna
            )

        # Operadores lógicos: &&, || (IL-TIPO-018)
        if op in ('&&', '||'):
            if t_left != 'bool' or t_right != 'bool':
                self.error_manager.error_tipo(
                    'IL-TIPO-018',
                    f'Operador {op} requiere operandos bool',
                    nodo.linea, nodo.columna
                )
            return 'bool'

        # Operadores relacionales: ==, !=, <, >, <=, >=
        if op in ('==', '!='):
            # Compatibles: int con int, float con float, string con string, bool con bool
            if t_left != t_right and not (t_left == 'int' and t_right == 'float') \
                    and not (t_left == 'float' and t_right == 'int'):
                self.error_manager.error_tipo(
                    'IL-TIPO-012',
                    f'Tipos incomparables: {t_left} y {t_right}',
                    nodo.linea, nodo.columna
                )
            return 'bool'

        if op in ('<', '>', '<=', '>='):
            # Solo int y float (IL-TIPO-012)
            if t_left not in ('int', 'float') or t_right not in ('int', 'float'):
                self.error_manager.error_tipo(
                    'IL-TIPO-012',
                    f'Operador {op} no aplicable a {t_left} y {t_right}',
                    nodo.linea, nodo.columna
                )
            return 'bool'

        # Operadores aritméticos: +, -, *, /, %
        if op == '+':
            # IL-TIPO-013: aritmética sobre bool
            if t_left == 'bool' or t_right == 'bool':
                self.error_manager.error_tipo(
                    'IL-TIPO-013',
                    f'Operador + no aplicable a operandos de tipo bool',
                    nodo.linea, nodo.columna
                )
                return None
            # Suma: int+int= int, float+float=float, int+float=float,
            #        float+int=float, string+string=string
            if t_left == 'string' and t_right == 'string':
                return 'string'
            if t_left in ('int', 'float') and t_right in ('int', 'float'):
                if t_left == 'float' or t_right == 'float':
                    return 'float'
                return 'int'
            self.error_manager.error_tipo(
                'IL-TIPO-011',
                f'Operador + no aplicable a {t_left} y {t_right}',
                nodo.linea, nodo.columna
            )
            return None

        if op in ('-', '*', '/'):
            if t_left == 'bool' or t_right == 'bool':
                self.error_manager.error_tipo(
                    'IL-TIPO-013',
                    f'Operador {op} no aplicable a operandos de tipo bool',
                    nodo.linea, nodo.columna
                )
                return None
            if t_left in ('int', 'float') and t_right in ('int', 'float'):
                if t_left == 'float' or t_right == 'float':
                    return 'float'
                return 'int'
            self.error_manager.error_tipo(
                'IL-TIPO-011',
                f'Operador {op} no aplicable a {t_left} y {t_right}',
                nodo.linea, nodo.columna
            )
            return None

        if op == '%':
            # IL-TIPO-013: aritmética sobre bool
            if t_left == 'bool' or t_right == 'bool':
                self.error_manager.error_tipo(
                    'IL-TIPO-013',
                    f'Operador % no aplicable a operandos de tipo bool',
                    nodo.linea, nodo.columna
                )
                return None
            # Módulo: solo int (IL-TIPO-010)
            if t_left == 'int' and t_right == 'int':
                return 'int'
            if t_left == 'float' or t_right == 'float':
                self.error_manager.error_tipo(
                    'IL-TIPO-010',
                    f'Operador % no aplicable a tipo float',
                    nodo.linea, nodo.columna
                )
            else:
                self.error_manager.error_tipo(
                    'IL-TIPO-011',
                    f'Operador % no aplicable a {t_left} y {t_right}',
                    nodo.linea, nodo.columna
                )
            return None

        return None

    def _tipo_unario(self, nodo):
        """Determina el tipo resultante de una operación unaria."""
        t_oper = self._obtener_tipo(nodo.operando)
        if t_oper is None:
            return None

        op = nodo.operador

        if op == '-':
            # Negación aritmética: solo int/float (IL-TIPO-017)
            if t_oper not in ('int', 'float'):
                self.error_manager.error_tipo(
                    'IL-TIPO-017',
                    f'Negación aritmética no aplicable a {t_oper}',
                    nodo.linea, nodo.columna
                )
            return t_oper

        if op == '!':
            # Negación lógica: solo bool (IL-TIPO-017)
            if t_oper != 'bool':
                self.error_manager.error_tipo(
                    'IL-TIPO-017',
                    f'Negación lógica no aplicable a {t_oper}',
                    nodo.linea, nodo.columna
                )
            return 'bool'

        if op in ('++', '--'):
            # Inc/dec: solo int (IL-TIPO-016)
            if t_oper != 'int':
                self.error_manager.error_tipo(
                    'IL-TIPO-016',
                    f'Operador {op} no aplicable a {t_oper}',
                    nodo.linea, nodo.columna
                )
            return 'int'

        return t_oper

    def _compatible(self, tipo_esperado, tipo_real):
        """Verifica compatibilidad de tipos.

        Reglas:
        - Tipos iguales son compatibles
        - int es compatible con float (promoción implícita §4.7)
        """
        if tipo_esperado == tipo_real:
            return True
        # Promoción implícita: int -> float
        if tipo_esperado == 'float' and tipo_real == 'int':
            return True
        return False

    def _codigo_incompatibilidad(self, tipo_esperado, tipo_real):
        """Elige el código del catálogo para una incompatibilidad de tipos.

        La conversión implícita entre bool y numérico tiene código propio
        (IL-TIPO-014, §4.5); el resto es IL-TIPO-001.
        """
        numericos = ('int', 'float')
        if tipo_real == 'bool' and tipo_esperado in numericos:
            return 'IL-TIPO-014'
        if tipo_esperado == 'bool' and tipo_real in numericos:
            return 'IL-TIPO-014'
        return 'IL-TIPO-001'
