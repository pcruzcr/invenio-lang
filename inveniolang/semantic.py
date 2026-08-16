# Módulo de Análisis Semántico de InvenioLang 1.0
# Implementa las reglas semánticas de la Sección 14
# Construye la tabla de símbolos y verifica reglas de alcance, declaración y uso

from .ast_nodes import *
from .symbol_table import SymbolTable, TipoSimbolo
from .builtins import FUNCIONES_BUILT_IN


class SemanticAnalyzer:
    """Analizador semántico de InvenioLang 1.0.

    Recorre el AST y construye la tabla de símbolos verificando:
    - Declaración antes de uso (IL-SEM-003)
    - Identificadores duplicados (IL-SEM-002)
    - Constantes no modificadas (IL-SEM-031)
    - Break/continue dentro de bucles (IL-SEM-040, IL-SEM-041)
    - Return en funciones (IL-SEM-050, IL-SEM-053)
    - Procedimientos como expresiones (IL-SEM-060)
    - Argumentos correctos (IL-SEM-052)
    - main válido (IL-SEM-020, IL-SEM-021, IL-SEM-022, IL-SEM-023)
    """

    def __init__(self, error_manager):
        self.error_manager = error_manager
        self.tabla = SymbolTable()
        self._registrar_builtins()

    def _registrar_builtins(self):
        """Registra las funciones integradas en la tabla de símbolos."""
        from .symbol_table import TipoSimbolo
        for nombre, (func, tipo_ret, tipos_params) in FUNCIONES_BUILT_IN.items():
            entrada = self.tabla.declarar(nombre, TipoSimbolo.FUNCION, tipo_ret, 0, 0)
            if entrada:
                entrada.params = tipos_params
                entrada.tipo_retorno = tipo_ret
        self.funcion_actual = None  # Nombre de la función/procedimiento actual
        self.tipo_retorno_actual = None
        self.en_funcion = False
        self.en_procedimiento = False
        self.en_main = False
        self.tiene_return = False
        # Variables ya avisadas con IL-WARN-002 (una advertencia por nombre)
        self._avisadas_sin_init = set()

    def analizar(self, ast):
        """Analiza semánticamente el AST completo."""
        if ast is None:
            return self.tabla
        self._visitar_programa(ast)
        return self.tabla

    def _visitar_programa(self, nodo):
        """Visita el nodo Programa."""
        # Registrar funciones y procedimientos primero (forward reference)
        for sub in nodo.subrutinas:
            self._declarar_subrutina(sub)

        # Declaraciones globales (deben ir antes de visitar cuerpos de funciones)
        for d in nodo.declaraciones_globales:
            self._visitar_declaracion(d)

        for d in nodo.declaraciones_posteriores:
            self._visitar_declaracion(d)

        # Visitar cuerpos de funciones y procedimientos
        for sub in nodo.subrutinas:
            self._visitar_subrutina(sub)

        # Verificar main
        if nodo.main is None:
            self.error_manager.error_semantico(
                'IL-SEM-020', 'No se encontró la función main en el archivo fuente',
                0, 0
            )
        else:
            self._visitar_main(nodo.main)

    def _declarar_subrutina(self, nodo):
        """Registra una función o procedimiento en la tabla de símbolos."""
        if isinstance(nodo, FunctionDecl):
            ts = TipoSimbolo.FUNCION
            tipo_ret = nodo.tipo_retorno
        elif isinstance(nodo, ProcedureDecl):
            ts = TipoSimbolo.PROCEDIMIENTO
            tipo_ret = 'void'
        else:
            return

        entrada = self._declarar_simbolo(nodo.nombre, ts, tipo_ret, nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        # Guardar tipos de parámetros
        entrada.params = [self._tipo_parametro(p) for p in nodo.parametros]
        if isinstance(nodo, FunctionDecl):
            entrada.tipo_retorno = nodo.tipo_retorno

    def _tipo_parametro(self, param):
        """Retorna la representación del tipo de un parámetro."""
        if param.es_matriz:
            return f'{param.tipo}[][]'
        if param.es_arreglo:
            return f'{param.tipo}[]'
        return param.tipo

    def _declarar_simbolo(self, nombre, tipo_simbolo, tipo_dato, linea, columna):
        """Declara un símbolo y emite IL-WARN-001 cuando oculta uno externo
        (§3.5.3, §14.16). Retorna la entrada o None si ya existe (duplicado)."""
        # Los nombres de funciones integradas están reservados en TODO ámbito,
        # no sólo en el global (§19.1). Se rechaza aquí y el reporte lo emite
        # `_manejar_duplicado`, que ya distingue IL-SEM-080 de IL-SEM-002.
        if nombre in FUNCIONES_BUILT_IN:
            return None
        entrada = self.tabla.declarar(nombre, tipo_simbolo, tipo_dato, linea, columna)
        if entrada is None:
            return None
        if self.tabla.profundidad_ambito() > 1 and self.tabla.hay_externo(nombre):
            self.error_manager.advertencia(
                'IL-WARN-001',
                f'"{nombre}" oculta un identificador externo del mismo nombre',
                linea, columna
            )
        return entrada

    def _manejar_duplicado(self, nombre, linea, columna):
        """Reporta un identificador duplicado. Si el nombre es de una función
        integrada, se emite IL-SEM-080 (§19.11); en caso contrario IL-SEM-002."""
        if nombre in FUNCIONES_BUILT_IN:
            self.error_manager.error_semantico(
                'IL-SEM-080',
                f'El nombre "{nombre}" está reservado por una función integrada',
                linea, columna
            )
        else:
            self.error_manager.error_semantico(
                'IL-SEM-002',
                f'Identificador duplicado: "{nombre}"',
                linea, columna
            )

    def _es_expr_constante(self, expr):
        """Indica si una expresión es constante (literales, constantes y
        operaciones sobre ellas). Se usa para IL-SEM-032 (§5.3)."""
        if isinstance(expr, Literal):
            return True
        if isinstance(expr, Identifier):
            e = self.tabla.buscar(expr.nombre)
            return e is not None and e.tipo_simbolo == TipoSimbolo.CONSTANTE
        if isinstance(expr, BinaryOp):
            return self._es_expr_constante(expr.izquierda) and self._es_expr_constante(expr.derecha)
        if isinstance(expr, UnaryOp):
            return self._es_expr_constante(expr.operando)
        return False

    def _es_true_constante(self, expr):
        """Indica si una expresión es constantemente verdadera (§9.1.3).

        Se usa para IL-WARN-010. Comprueba el VALOR de la constante, no sólo
        que sea de tipo bool: `const bool SALIR = false;` no debe advertir.
        """
        if isinstance(expr, Literal) and expr.tipo_literal == 'bool' and expr.valor is True:
            return True
        if isinstance(expr, Identifier):
            e = self.tabla.buscar(expr.nombre)
            if e is None or e.tipo_simbolo != TipoSimbolo.CONSTANTE:
                return False
            if e.tipo_dato != 'bool':
                return False
            return getattr(e, 'valor_constante', None) is True
        return False

    def _siempre_retorna(self, elems):
        """Indica si una lista de instrucciones retorna por todas sus rutas.

        Implementa IL-SEM-050 (§10.4): una función es correcta sólo si toda
        ruta de ejecución alcanza un `return`. Reglas:
          - `return` cierra la ruta.
          - un `if` la cierra sólo si tiene `else` Y ambas ramas la cierran.
          - un ciclo NO la cierra: su cuerpo puede no ejecutarse nunca.
        """
        for e in elems:
            if isinstance(e, ReturnStmt):
                return True
            if isinstance(e, IfStmt):
                if e.bloque_else is None:
                    continue
                if (self._siempre_retorna(e.bloque_then.elementos)
                        and self._siempre_retorna(e.bloque_else.elementos)):
                    return True
        return False

    def _bloque_tiene_break(self, elems):
        """Indica si existe una instrucción break alcanzable en una lista de
        elementos (recorre if/while/for para detectar break anidados)."""
        for e in elems:
            if isinstance(e, BreakStmt):
                return True
            if isinstance(e, IfStmt):
                if self._bloque_tiene_break(e.bloque_then.elementos):
                    return True
                if e.bloque_else and self._bloque_tiene_break(e.bloque_else.elementos):
                    return True
            if isinstance(e, WhileStmt) and self._bloque_tiene_break(e.bloque.elementos):
                return True
            if isinstance(e, ForStmt) and self._bloque_tiene_break(e.bloque.elementos):
                return True
        return False

    def _visitar_main(self, nodo):
        """Verifica la función main y visita su bloque."""
        # main debe ser void (es garantizado por la gramática)
        if not self.tabla.buscar_funcion('main'):
            entrada = self._declarar_simbolo('main', TipoSimbolo.FUNCION, 'void',
                                             nodo.linea, nodo.columna)
            if entrada:
                entrada.params = []

        self.tabla.entrar_ambito()
        self.funcion_actual = 'main'
        self.tipo_retorno_actual = 'void'
        self.en_funcion = False
        # main no es un procedimiento: un return con valor en su interior es
        # IL-SEM-023, no IL-SEM-061 (§3.2).
        self.en_procedimiento = False
        self.en_main = True
        self.tiene_return = False

        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        self.tabla.salir_ambito()
        self.funcion_actual = None
        self.en_main = False

    def _visitar_subrutina(self, nodo):
        """Visita una subrutina registrada."""
        if isinstance(nodo, FunctionDecl):
            self._visitar_funcion(nodo)
        elif isinstance(nodo, ProcedureDecl):
            self._visitar_procedimiento(nodo)

    def _visitar_funcion(self, nodo):
        """Visita una función."""
        entrada = self.tabla.buscar_funcion(nodo.nombre)
        if entrada and entrada.params:
            # Verificar que los parámetros tengan longitud correcta
            pass

        self.tabla.entrar_ambito()
        self.funcion_actual = nodo.nombre
        self.tipo_retorno_actual = nodo.tipo_retorno
        self.en_funcion = True
        self.en_procedimiento = False
        self.tiene_return = False

        # Declarar parámetros
        for p in nodo.parametros:
            self._declarar_parametro(p)

        # Visitar cuerpo
        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        # IL-SEM-050: toda ruta de ejecución debe alcanzar un return (§10.4)
        if nodo.tipo_retorno != 'void' and not self._siempre_retorna(nodo.bloque.elementos):
            self.error_manager.error_semantico(
                'IL-SEM-050',
                f'La función "{nodo.nombre}" tiene al menos una ruta de '
                f'ejecución que no alcanza ningún return',
                nodo.linea, nodo.columna
            )

        self.tabla.salir_ambito()
        self.funcion_actual = None
        self.en_funcion = False

    def _visitar_procedimiento(self, nodo):
        """Analiza el cuerpo de un procedimiento."""
        self.tabla.entrar_ambito()
        self.funcion_actual = nodo.nombre
        self.tipo_retorno_actual = 'void'
        self.en_funcion = False
        self.en_procedimiento = True
        self.tiene_return = False

        for p in nodo.parametros:
            self._declarar_parametro(p)

        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        self.tabla.salir_ambito()
        self.funcion_actual = None
        self.en_procedimiento = False

    def _declarar_parametro(self, param):
        """Declara un parámetro en la tabla de símbolos."""
        if param.tipo == 'void':
            self.error_manager.error_tipo(
                'IL-TIPO-015',
                f'Parámetro "{param.nombre}" no puede ser de tipo void',
                param.linea, param.columna
            )
        if param.es_matriz:
            ts = TipoSimbolo.PARAM_MATRIZ
        elif param.es_arreglo:
            ts = TipoSimbolo.PARAM_ARREGLO
        else:
            ts = TipoSimbolo.PARAMETRO

        entrada = self._declarar_simbolo(param.nombre, ts, param.tipo,
                                         param.linea, param.columna)
        if entrada is None:
            self._manejar_duplicado(param.nombre, param.linea, param.columna)
        else:
            entrada.inicializado = True  # Los parámetros están siempre inicializados
            if param.es_matriz:
                entrada.es_parametro_matriz = True
            elif param.es_arreglo:
                entrada.es_parametro_arreglo = True

    def _visitar_elemento_bloque(self, elem):
        """Visita un elemento de bloque (declaración o instrucción)."""
        if isinstance(elem, (VarDecl, ConstDecl, ArrayDecl, MatrixDecl)):
            self._visitar_declaracion(elem)
        elif isinstance(elem, FunctionDecl):
            # Función declarada localmente - error sintáctico/semántico
            self.error_manager.error_sintactico(
                'IL-SIN-050',
                'No se permite declarar funciones dentro de bloques locales',
                elem.linea, elem.columna
            )
        else:
            self._visitar_instruccion(elem)

    def _visitar_declaracion(self, nodo):
        """Visita una declaración y la registra en la tabla de símbolos."""
        if isinstance(nodo, VarDecl):
            self._visitar_var_decl(nodo)
        elif isinstance(nodo, ConstDecl):
            self._visitar_const_decl(nodo)
        elif isinstance(nodo, ArrayDecl):
            self._visitar_array_decl(nodo)
        elif isinstance(nodo, MatrixDecl):
            self._visitar_matrix_decl(nodo)

    def _visitar_var_decl(self, nodo):
        """Declara una variable."""
        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-TIPO-015',
                f'Variable "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )
        ts = TipoSimbolo.VARIABLE
        entrada = self._declarar_simbolo(nodo.nombre, ts, nodo.tipo,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        if not entrada:
            return
        if nodo.init_expr is not None:
            entrada.inicializado = True
            # Verificar autorreferencia
            self._verificar_autoref(nodo.nombre, nodo.init_expr)
            self._visitar_expresion(nodo.init_expr)
        # Sin inicializador no se advierte aquí: IL-WARN-002 se emite en el
        # punto de LECTURA, si es que la variable llega a leerse sin asignar
        # (§5.2.2). Las globales sí reciben valor por defecto (§5.2.3).

    def _verificar_autoref(self, nombre, expr):
        """Verifica IL-SEM-004: autorreferencia en inicialización (§5.1.3).

        Recorre la expresión completa, no sólo su raíz: `int x = x + 1;` es
        tan autorreferente como `int x = x;`.
        """
        if expr is None:
            return
        if isinstance(expr, Identifier) and expr.nombre == nombre:
            self.error_manager.error_semantico(
                'IL-SEM-004',
                f'Autorreferencia en inicialización de "{nombre}"',
                expr.linea, expr.columna
            )
            return
        if isinstance(expr, BinaryOp):
            self._verificar_autoref(nombre, expr.izquierda)
            self._verificar_autoref(nombre, expr.derecha)
        elif isinstance(expr, UnaryOp):
            self._verificar_autoref(nombre, expr.operando)
        elif isinstance(expr, FunctionCall):
            for a in expr.argumentos:
                self._verificar_autoref(nombre, a)
        elif isinstance(expr, ArrayAccess):
            if expr.nombre == nombre:
                self.error_manager.error_semantico(
                    'IL-SEM-004',
                    f'Autorreferencia en inicialización de "{nombre}"',
                    expr.linea, expr.columna
                )
                return
            self._verificar_autoref(nombre, expr.indice)
        elif isinstance(expr, MatrixAccess):
            if expr.nombre == nombre:
                self.error_manager.error_semantico(
                    'IL-SEM-004',
                    f'Autorreferencia en inicialización de "{nombre}"',
                    expr.linea, expr.columna
                )
                return
            self._verificar_autoref(nombre, expr.fila)
            self._verificar_autoref(nombre, expr.columna)

    def _visitar_const_decl(self, nodo):
        """Declara una constante."""
        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-TIPO-015',
                f'Constante "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )
        ts = TipoSimbolo.CONSTANTE
        entrada = self._declarar_simbolo(nodo.nombre, ts, nodo.tipo,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        entrada.inicializado = True
        # Recordar el valor si es un literal, para IL-WARN-010 (§9.1.3)
        if isinstance(nodo.init_expr, Literal):
            entrada.valor_constante = nodo.init_expr.valor
        # IL-SEM-032: la inicialización de una constante debe ser constante
        if not self._es_expr_constante(nodo.init_expr):
            self.error_manager.error_semantico(
                'IL-SEM-032',
                f'La constante "{nodo.nombre}" debe inicializarse con una '
                f'expresión constante',
                nodo.init_expr.linea, nodo.init_expr.columna
            )
        self._visitar_expresion(nodo.init_expr)

    def _visitar_array_decl(self, nodo):
        """Declara un arreglo."""
        ts = TipoSimbolo.ARREGLO
        entrada = self._declarar_simbolo(nodo.nombre, ts, nodo.tipo,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        # Verificar tamaño
        if isinstance(nodo.tam, int):
            if nodo.tam <= 0:
                self.error_manager.error_semantico(
                    'IL-SEM-071',
                    f'Dimensión de arreglo "{nodo.nombre}" debe ser positiva',
                    nodo.linea, nodo.columna
                )
            else:
                entrada.tam_arreglo = nodo.tam
        else:
            # IDENTIFICADOR - debe ser una constante
            const_entry = self.tabla.buscar(nodo.tam)
            if const_entry and const_entry.tipo_simbolo == TipoSimbolo.CONSTANTE:
                entrada.tam_arreglo = nodo.tam  # Guardar nombre de la constante
            else:
                self.error_manager.error_semantico(
                    'IL-SEM-070',
                    f'Dimensión de arreglo "{nodo.nombre}" debe ser una constante',
                    nodo.linea, nodo.columna
                )

        # Verificar void como tipo base (IL-SEM-072, §12/§14)
        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-SEM-072',
                f'Arreglo "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )

        if nodo.init_exprs:
            entrada.inicializado = True
            for e in nodo.init_exprs:
                self._visitar_expresion(e)
            if isinstance(entrada.tam_arreglo, int) and len(nodo.init_exprs) != entrada.tam_arreglo:
                self.error_manager.error_semantico(
                    'IL-SEM-073',
                    f'Arreglo "{nodo.nombre}" esperaba {entrada.tam_arreglo} elementos, '
                    f'pero se proporcionaron {len(nodo.init_exprs)}',
                    nodo.linea, nodo.columna
                )

    def _visitar_matrix_decl(self, nodo):
        """Declara una matriz."""
        ts = TipoSimbolo.MATRIZ
        entrada = self._declarar_simbolo(nodo.nombre, ts, nodo.tipo,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        if isinstance(nodo.filas, int):
            if nodo.filas <= 0:
                self.error_manager.error_semantico(
                    'IL-SEM-071',
                    f'Dimensión de matriz "{nodo.nombre}" debe ser positiva',
                    nodo.linea, nodo.columna
                )
            else:
                entrada.filas_matriz = nodo.filas
        else:
            const_entry = self.tabla.buscar(nodo.filas)
            if const_entry and const_entry.tipo_simbolo == TipoSimbolo.CONSTANTE:
                entrada.filas_matriz = nodo.filas
            else:
                self.error_manager.error_semantico(
                    'IL-SEM-070',
                    f'Dimensión de matriz "{nodo.nombre}" debe ser una constante',
                    nodo.linea, nodo.columna
                )
        if isinstance(nodo.cols, int):
            if nodo.cols <= 0:
                self.error_manager.error_semantico(
                    'IL-SEM-071',
                    f'Dimensión de matriz "{nodo.nombre}" debe ser positiva',
                    nodo.linea, nodo.columna
                )
            else:
                entrada.cols_matriz = nodo.cols
        else:
            const_entry = self.tabla.buscar(nodo.cols)
            if const_entry and const_entry.tipo_simbolo == TipoSimbolo.CONSTANTE:
                entrada.cols_matriz = nodo.cols
            else:
                self.error_manager.error_semantico(
                    'IL-SEM-070',
                    f'Dimensión de matriz "{nodo.nombre}" debe ser una constante',
                    nodo.linea, nodo.columna
                )

        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-SEM-072',
                f'Matriz "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )

        if nodo.init_filas:
            entrada.inicializado = True
            for fila in nodo.init_filas:
                for e in fila:
                    self._visitar_expresion(e)
            filas_ok = isinstance(entrada.filas_matriz, int)
            cols_ok = isinstance(entrada.cols_matriz, int)
            if filas_ok and len(nodo.init_filas) != entrada.filas_matriz:
                self.error_manager.error_semantico(
                    'IL-SEM-073',
                    f'Matriz "{nodo.nombre}" esperaba {entrada.filas_matriz} filas, '
                    f'pero se proporcionaron {len(nodo.init_filas)}',
                    nodo.linea, nodo.columna
                )
            if cols_ok:
                for i, fila in enumerate(nodo.init_filas):
                    if len(fila) != entrada.cols_matriz:
                        self.error_manager.error_semantico(
                            'IL-SEM-073',
                            f'Matriz "{nodo.nombre}" fila {i} esperaba {entrada.cols_matriz} columnas, '
                            f'pero se proporcionaron {len(fila)}',
                            nodo.linea, nodo.columna
                        )

    def _visitar_instruccion(self, nodo):
        """Visita una instrucción."""
        if isinstance(nodo, AssignStmt):
            self._visitar_asignacion(nodo)
        elif isinstance(nodo, IncDecStmt):
            self._visitar_inc_dec(nodo)
        elif isinstance(nodo, PrintStmt):
            # Un procedimiento como argumento directo de print corresponde a
            # IL-TIPO-020 (§7.1), que emite el verificador de tipos; no se
            # adelanta aquí IL-SEM-060 para no ocultarlo.
            if isinstance(nodo.expr, FunctionCall):
                self._visitar_llamada(nodo.expr.nombre, nodo.expr.argumentos, nodo.expr)
            else:
                self._visitar_expresion(nodo.expr)
        elif isinstance(nodo, ReadStmt):
            self._visitar_read(nodo)
        elif isinstance(nodo, IfStmt):
            self._visitar_if(nodo)
        elif isinstance(nodo, WhileStmt):
            self._visitar_while(nodo)
        elif isinstance(nodo, ForStmt):
            self._visitar_for(nodo)
        elif isinstance(nodo, ReturnStmt):
            self._visitar_return(nodo)
        elif isinstance(nodo, BreakStmt):
            self._visitar_break(nodo)
        elif isinstance(nodo, ContinueStmt):
            self._visitar_continue(nodo)
        elif isinstance(nodo, (CallStmt, FunctionCall)):
            # El parser construye CallStmt para toda llamada en posición de
            # instrucción; FunctionCall se acepta por robustez.
            self._visitar_llamada(nodo.nombre, nodo.argumentos, nodo)
            # IL-WARN-020: se descarta el valor de retorno (§10.5)
            entrada = self.tabla.buscar_funcion(nodo.nombre)
            if entrada and entrada.tipo_retorno and entrada.tipo_retorno != 'void':
                self.error_manager.advertencia(
                    'IL-WARN-020',
                    f'Se descarta el valor de retorno de la función "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )

    def _visitar_asignacion(self, nodo):
        """Verifica asignación."""
        # Verificar que el lvalue sea válido
        if isinstance(nodo.lvalue, VarLValue):
            entrada = self.tabla.buscar(nodo.lvalue.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Identificador no declarado: "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            elif entrada.tipo_simbolo == TipoSimbolo.CONSTANTE:
                self.error_manager.error_semantico(
                    'IL-SEM-031',
                    f'No se puede asignar a la constante "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            elif entrada.tipo_simbolo in (TipoSimbolo.ARREGLO, TipoSimbolo.MATRIZ,
                                          TipoSimbolo.PARAM_ARREGLO,
                                          TipoSimbolo.PARAM_MATRIZ):
                # IL-SIN-070: no se puede asignar un arreglo/matriz completo
                # con "="; la copia debe ser elemento a elemento (§12.6).
                self.error_manager.error_sintactico(
                    'IL-SIN-070',
                    f'No se puede asignar el arreglo o matriz completo '
                    f'"{nodo.lvalue.nombre}"; copie elemento a elemento',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            else:
                entrada.inicializado = True
        elif isinstance(nodo.lvalue, ArrayLValue):
            entrada = self.tabla.buscar(nodo.lvalue.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Arreglo no declarado: "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            else:
                self._verificar_indices_matriz(entrada, nodo.lvalue)
                entrada.inicializado = True
            self._visitar_expresion(nodo.lvalue.indice)
        elif isinstance(nodo.lvalue, MatrixLValue):
            entrada = self.tabla.buscar(nodo.lvalue.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Matriz no declarada: "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            else:
                entrada.inicializado = True
            self._visitar_expresion(nodo.lvalue.fila)
            self._visitar_expresion(nodo.lvalue.columna)

        self._visitar_expresion(nodo.expr)

    def _verificar_indices_matriz(self, entrada, nodo):
        """IL-SIN-080: una matriz debe indexarse con dos índices (§13.4)."""
        if entrada.tipo_simbolo in (TipoSimbolo.MATRIZ, TipoSimbolo.PARAM_MATRIZ):
            self.error_manager.error_sintactico(
                'IL-SIN-080',
                f'La matriz "{nodo.nombre}" requiere dos índices: '
                f'{nodo.nombre}[fila][columna]',
                nodo.linea, nodo.columna
            )

    def _visitar_inc_dec(self, nodo):
        """Verifica incremento/decremento."""
        entrada = self.tabla.buscar(nodo.nombre)
        if entrada is None:
            self.error_manager.error_semantico(
                'IL-SEM-003',
                f'Identificador no declarado: "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
        elif entrada.tipo_simbolo == TipoSimbolo.CONSTANTE:
            self.error_manager.error_semantico(
                'IL-SEM-031',
                f'No se puede modificar la constante "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
        else:
            entrada.inicializado = True

    def _visitar_read(self, nodo):
        """Verifica instrucción read/leer."""
        entrada = self.tabla.buscar(nodo.nombre)
        if entrada is None:
            self.error_manager.error_semantico(
                'IL-SEM-003',
                f'Identificador no declarado: "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
        elif entrada.tipo_simbolo == TipoSimbolo.CONSTANTE:
            self.error_manager.error_semantico(
                'IL-SEM-031',
                f'No se puede leer en la constante "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
        else:
            entrada.inicializado = True

    def _visitar_if(self, nodo):
        """Verifica instrucción if."""
        self._visitar_expresion(nodo.condicion)
        self.tabla.entrar_ambito()
        for elem in nodo.bloque_then.elementos:
            self._visitar_elemento_bloque(elem)
        self.tabla.salir_ambito()

        if nodo.bloque_else:
            self.tabla.entrar_ambito()
            for elem in nodo.bloque_else.elementos:
                self._visitar_elemento_bloque(elem)
            self.tabla.salir_ambito()

    def _visitar_while(self, nodo):
        """Verifica instrucción while."""
        self._visitar_expresion(nodo.condicion)
        # IL-WARN-010: while infinito (condición literal true) sin break (§9.1.3)
        if self._es_true_constante(nodo.condicion) and not self._bloque_tiene_break(nodo.bloque.elementos):
            self.error_manager.advertencia(
                'IL-WARN-010',
                'Ciclo while con condición constantemente true sin break alcanzable',
                nodo.linea, nodo.columna
            )
        self.tabla.loop_actual += 1
        self.tabla.entrar_ambito()
        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)
        self.tabla.salir_ambito()
        self.tabla.loop_actual -= 1

    def _visitar_for(self, nodo):
        """Verifica instrucción for."""
        # Crear ámbito para el for (init, cond, act y cuerpo comparten ámbito)
        self.tabla.loop_actual += 1
        self.tabla.entrar_ambito()

        # Inicialización
        if nodo.init_stmt:
            if isinstance(nodo.init_stmt, ForInitVar):
                ts = TipoSimbolo.VARIABLE
                entrada = self._declarar_simbolo(nodo.init_stmt.nombre, ts,
                                                 nodo.init_stmt.tipo,
                                                 nodo.init_stmt.linea,
                                                 nodo.init_stmt.columna)
                if entrada is None:
                    self._manejar_duplicado(nodo.init_stmt.nombre,
                                            nodo.init_stmt.linea,
                                            nodo.init_stmt.columna)
                elif nodo.init_stmt.init_expr:
                    entrada.inicializado = True
                    self._visitar_expresion(nodo.init_stmt.init_expr)
            elif isinstance(nodo.init_stmt, ForInitAsig):
                self._visitar_lvalue_simple(nodo.init_stmt.lvalue)
                self._visitar_expresion(nodo.init_stmt.expr)

        # Condición
        if nodo.cond_expr:
            self._visitar_expresion(nodo.cond_expr)

        # Acción
        if nodo.act_stmt:
            if isinstance(nodo.act_stmt, ForInitAsig):
                self._visitar_lvalue_simple(nodo.act_stmt.lvalue)
                self._visitar_expresion(nodo.act_stmt.expr)
            elif isinstance(nodo.act_stmt, ForInitIncDec):
                entrada = self.tabla.buscar(nodo.act_stmt.nombre)
                if entrada is None:
                    self.error_manager.error_semantico(
                        'IL-SEM-003',
                        f'Identificador no declarado: "{nodo.act_stmt.nombre}"',
                        nodo.act_stmt.linea, nodo.act_stmt.columna
                    )

        # Cuerpo
        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        self.tabla.salir_ambito()
        self.tabla.loop_actual -= 1

    def _visitar_lvalue_simple(self, lvalue):
        """Visita un lvalue en contexto de for."""
        if isinstance(lvalue, VarLValue):
            entrada = self.tabla.buscar(lvalue.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Identificador no declarado: "{lvalue.nombre}"',
                    lvalue.linea, lvalue.columna
                )
        elif isinstance(lvalue, ArrayLValue):
            self._visitar_expresion(lvalue.indice)
        elif isinstance(lvalue, MatrixLValue):
            self._visitar_expresion(lvalue.fila)
            self._visitar_expresion(lvalue.columna)

    def _visitar_return(self, nodo):
        """Verifica instrucción return."""
        if self.en_funcion:
            if nodo.expr is None:
                self.error_manager.error_semantico(
                    'IL-SEM-053',
                    f'La función "{self.funcion_actual}" requiere return con expresión',
                    nodo.linea, nodo.columna
                )
            else:
                self._visitar_expresion(nodo.expr)
                self.tiene_return = True
        elif self.en_procedimiento:
            if nodo.expr is not None:
                self.error_manager.error_semantico(
                    'IL-SEM-061',
                    f'Procedimiento "{self.funcion_actual}" no puede retornar valor',
                    nodo.linea, nodo.columna
                )
            else:
                self.tiene_return = True
        else:
            # return en main
            if nodo.expr is not None:
                self.error_manager.error_semantico(
                    'IL-SEM-023',
                    'main no debe retornar valor',
                    nodo.linea, nodo.columna
                )

    def _visitar_break(self, nodo):
        """Verifica break."""
        if not self.tabla.esta_en_loop():
            self.error_manager.error_semantico(
                'IL-SEM-040',
                'break solo puede usarse dentro de un ciclo',
                nodo.linea, nodo.columna
            )

    def _visitar_continue(self, nodo):
        """Verifica continue."""
        if not self.tabla.esta_en_loop():
            self.error_manager.error_semantico(
                'IL-SEM-041',
                'continue solo puede usarse dentro de un ciclo',
                nodo.linea, nodo.columna
            )

    def _visitar_expresion(self, nodo):
        """Visita una expresión (análisis semántico básico)."""
        if nodo is None:
            return

        if isinstance(nodo, BinaryOp):
            self._visitar_expresion(nodo.izquierda)
            self._visitar_expresion(nodo.derecha)
        elif isinstance(nodo, UnaryOp):
            self._visitar_expresion(nodo.operando)
        elif isinstance(nodo, Literal):
            # IL-SEM-010: verificar desbordamiento de enteros
            if isinstance(nodo.valor, int) and not isinstance(nodo.valor, bool):
                if nodo.valor > 2147483647 or nodo.valor < -2147483648:
                    self.error_manager.error_semantico(
                        'IL-SEM-010',
                        f'Literal entero fuera de rango: {nodo.valor}',
                        nodo.linea, nodo.columna
                    )
        elif isinstance(nodo, Identifier):
            entrada = self.tabla.buscar(nodo.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Identificador no declarado: "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )
            elif (entrada.tipo_simbolo == TipoSimbolo.VARIABLE
                    and not entrada.inicializado
                    and not self.tabla.es_global(nodo.nombre)):
                # IL-WARN-002: lectura de una local posiblemente sin inicializar
                # (§5.2.2). Se avisa una sola vez por variable.
                if nodo.nombre not in self._avisadas_sin_init:
                    self._avisadas_sin_init.add(nodo.nombre)
                    self.error_manager.advertencia(
                        'IL-WARN-002',
                        f'"{nodo.nombre}" puede leerse antes de ser inicializada',
                        nodo.linea, nodo.columna
                    )
            elif entrada.tipo_simbolo == TipoSimbolo.PROCEDIMIENTO:
                self.error_manager.error_semantico(
                    'IL-SEM-060',
                    f'Procedimiento "{nodo.nombre}" usado como expresión',
                    nodo.linea, nodo.columna
                )
        elif isinstance(nodo, ArrayAccess):
            entrada = self.tabla.buscar(nodo.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Arreglo no declarado: "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )
            else:
                self._verificar_indices_matriz(entrada, nodo)
            self._visitar_expresion(nodo.indice)
        elif isinstance(nodo, MatrixAccess):
            entrada = self.tabla.buscar(nodo.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Matriz no declarada: "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )
            self._visitar_expresion(nodo.fila)
            self._visitar_expresion(nodo.columna)
        elif isinstance(nodo, FunctionCall):
            callee = self.tabla.buscar_funcion(nodo.nombre)
            if callee and callee.tipo_simbolo == TipoSimbolo.PROCEDIMIENTO:
                # IL-SEM-060: procedimiento usado en una expresión (§11.4.1)
                self.error_manager.error_semantico(
                    'IL-SEM-060',
                    f'Procedimiento "{nodo.nombre}" usado como expresión',
                    nodo.linea, nodo.columna
                )
            self._visitar_llamada(nodo.nombre, nodo.argumentos, nodo)

    def _visitar_llamada(self, nombre, argumentos, nodo):
        """Verifica una llamada a función/procedimiento."""
        entrada = self.tabla.buscar_funcion(nombre)
        if entrada is None:
            # Podría ser una función definida después
            self.error_manager.error_semantico(
                'IL-SEM-003',
                f'Función o procedimiento no declarado: "{nombre}"',
                nodo.linea, nodo.columna
            )
        else:
            # Verificar número de argumentos
            num_params = len(entrada.params)
            num_args = len(argumentos)
            if num_params != num_args:
                self.error_manager.error_semantico(
                    'IL-SEM-052',
                    f'Llamada a "{nombre}": esperados {num_params} argumentos, recibidos {num_args}',
                    nodo.linea, nodo.columna
                )

        for arg in argumentos:
            self._visitar_expresion(arg)
