# Módulo del Intérprete de Árbol de InvenioLang 1.0
# Implementa el recorrido y ejecución del AST verificado
# Soporta: variables, constantes, arreglos, matrices, funciones, procedimientos

import sys
import time

from .ast_nodes import *
from .symbol_table import TipoSimbolo
from .builtins import (BuiltInError, es_built_in, obtener_built_in,
                       ejecutar_built_in)


class ReturnException(Exception):
    """Excepción para manejar retornos de funciones."""

    def __init__(self, valor=None):
        self.valor = valor


class BreakException(Exception):
    """Excepción para manejar break en bucles."""


class ContinueException(Exception):
    """Excepción para manejar continue en bucles."""


class RuntimeError_(Exception):
    """Error de ejecución de InvenioLang."""

    def __init__(self, codigo, mensaje, linea, columna):
        self.codigo = codigo
        self.mensaje = mensaje
        self.linea = linea
        self.columna = columna
        super().__init__(f"[{codigo}] L{linea}:C{columna} - {mensaje}")


class DebugStopped(Exception):
    """Señala la detención de una ejecución en modo depuración."""


class ExecutionCancelled(Exception):
    """Señala que la ejecución fue cancelada desde fuera del intérprete.

    La lanza `_comprobar_cancelacion` cuando el consumidor (por ejemplo el
    botón Detener de la IDE) activa la bandera de cancelación. Es distinta de
    IL-EJE-030: no es un error del programa del estudiante, sino una decisión
    del usuario, y por eso no se registra en el catálogo de errores.
    """


class Interpreter:
    """Intérprete de árbol para InvenioLang 1.0.

    Recorre el AST verificando y ejecutando las instrucciones.
    Mantiene un entorno con marcos de pila para el manejo de ámbitos.
    """

    def __init__(self, error_manager, tabla_simbolos):
        self.error_manager = error_manager
        self.tabla = tabla_simbolos
        # Entorno de ejecución: pila de marcos (cada marco es un dict)
        self.pila_marcos = [{}]
        # Tipos de las variables conocidos en ejecución (por nombre).
        # Se usa porque en tiempo de ejecución los ámbitos locales ya fueron
        # desapilados de la tabla de símbolos, y `read` necesita conocer el tipo.
        self.tipos_variables = {}
        # Para funciones: tabla de nodos AST
        self.funciones_ast = {}
        self.procedimientos_ast = {}
        # Entrada/salida capturable
        self.salida = []
        self.entrada = []
        # Limites de ejecucion (§9.1, IL-EJE-030). None desactiva cada uno.
        # El limite de iteraciones acota los ciclos triviales; el de tiempo
        # acota tambien los que hacen trabajo pesado en cada vuelta, y es el
        # que da una garantia de respuesta constante en la GUI.
        self.max_iteraciones = 1_000_000
        self.max_segundos = 5.0
        self._t_inicio = None
        # Cancelacion cooperativa: el consumidor asigna aqui un callable sin
        # argumentos que retorne True cuando quiera detener la ejecucion (por
        # ejemplo el boton Detener de la IDE). Se consulta en cada vuelta de
        # ciclo y en cada llamada a subrutina.
        self.cancelado = None
        # Modo depuración / traza (para depurador y seguimiento de algoritmos)
        self.debug = False
        self.debug_breakpoints = set()
        self.debug_step = False
        self.debug_detener = False
        self.debug_on_statement = None   # callable(snapshot) -> int (0 pausa)
        self.debug_wait = None           # callable() -> bloquea hasta reanudar
        self._pila_subrutinas = []

    def _snapshot_debug(self, nodo):
        """Construye una instantánea del estado para depuración/traza."""
        visibles = {}
        for marco in reversed(self.pila_marcos):
            for k, v in marco.items():
                if k not in visibles:
                    visibles[k] = v
        variables = []
        for k, v in visibles.items():
            tipo = self.tipos_variables.get(k)
            if tipo is None:
                e = self.tabla.buscar(k)
                tipo = e.tipo_dato if e else type(v).__name__
            variables.append({'nombre': k, 'tipo': tipo, 'valor': v})
        return {
            'linea': getattr(nodo, 'linea', 0),
            'columna': getattr(nodo, 'columna', 0),
            'variables': variables,
            'pila': list(self._pila_subrutinas),
            'salida': list(self.salida),
        }

    def _debug_ejecucion(self, nodo):
        """Hook de depuración invocado antes de ejecutar cada elemento.

        `debug_on_statement(snap, pausar)` se llama en cada instrucción (útil
        para traza); retorna True si el consumidor desea bloquear aquí. Se
        bloquea si el consumidor lo pide o si es punto de paso/breakpoint.
        """
        if not self.debug or self.debug_on_statement is None:
            return
        snap = self._snapshot_debug(nodo)
        pausar = self.debug_step or (nodo.linea in self.debug_breakpoints)
        accion = pausar or bool(self.debug_on_statement(snap, pausar))
        if accion:
            self.debug_step = False   # consume el "paso"
            if self.debug_wait is not None:
                self.debug_wait(snap)
        if self.debug_detener:
            raise DebugStopped()

    def registrar_subrutinas(self, ast):
        """Registra todas las subrutinas del AST."""
        for sub in ast.subrutinas:
            if isinstance(sub, FunctionDecl):
                self.funciones_ast[sub.nombre] = sub
            elif isinstance(sub, ProcedureDecl):
                self.procedimientos_ast[sub.nombre] = sub
        if ast.main:
            self.funciones_ast['main'] = ast.main

    def interpretar(self, ast, entrada_usuario=None, usar_stdin=True):
        """Interpreta (ejecuta) un programa InvenioLang.

        Args:
            ast: Nodo Program del AST
            entrada_usuario: Lista de strings para simular entrada estándar
            usar_stdin: Si True, `read` lee de la entrada estándar cuando no
                hay entrada simulada (CLI/consola). Si False (GUI), no se
                bloquea: una lectura sin entrada produce error de conversión.

        Retorna:
            Lista de strings con la salida del programa
        """
        if ast is None:
            return []

        self.salida = []
        self.entrada = list(entrada_usuario) if entrada_usuario else []
        self.usar_stdin = usar_stdin
        self.pila_marcos = [{}]
        self.tipos_variables = {}
        self.debug_detener = False
        self._pila_subrutinas = []
        self._profundidad_llamadas = 0
        self._t_inicio = time.monotonic()

        # Dar holgura al limite de Python para que IL-EJE-040 se dispare antes
        # que RecursionError (véase MAX_RECURSION).
        margen = self.MAX_RECURSION * self.MARCOS_PYTHON_POR_LLAMADA + 1000
        limite_previo = sys.getrecursionlimit()
        if limite_previo < margen:
            sys.setrecursionlimit(margen)

        self.registrar_subrutinas(ast)

        # Inicializar variables globales (reciben valor por defecto, §5.2.3)
        for d in ast.declaraciones_globales:
            self._ejecutar_declaracion(d, es_global=True)
        for d in ast.declaraciones_posteriores:
            self._ejecutar_declaracion(d, es_global=True)

        # Ejecutar main
        try:
            self._ejecutar_subrutina('main', [])
        except ReturnException as e:
            pass  # main no retorna valor
        except RuntimeError_ as e:
            self.error_manager.error_ejecucion(
                e.codigo, e.mensaje, e.linea, e.columna
            )
        except ExecutionCancelled:
            raise  # decision del usuario, no un error del programa
        except BreakException:
            # break/continue fuera de ciclo es un error semantico (§9.4); si
            # llega hasta aqui es que el analisis no lo detecto.
            self.error_manager.error_ejecucion(
                'IL-SEM-040', 'break fuera de un ciclo', 0, 0
            )
        except ContinueException:
            self.error_manager.error_ejecucion(
                'IL-SEM-041', 'continue fuera de un ciclo', 0, 0
            )

        return self.salida

    def _marco_actual(self):
        """Retorna el marco de ejecución actual."""
        return self.pila_marcos[-1]

    def _entrar_marco(self):
        """Crea un nuevo marco de ejecución."""
        self.pila_marcos.append({})

    def _salir_marco(self):
        """Elimina el marco de ejecución actual."""
        self.pila_marcos.pop()

    def _declarar_variable(self, nombre, valor):
        """Declara una variable en el marco actual (no busca en marcos superiores)."""
        self._marco_actual()[nombre] = valor

    def _asignar_variable(self, nombre, valor):
        """Asigna un valor a una variable en el marco actual o superiores."""
        # Buscar en la pila de marcos (de adentro hacia afuera)
        for marco in reversed(self.pila_marcos):
            if nombre in marco:
                marco[nombre] = valor
                return
        # Si no existe, crear en el marco actual
        self._marco_actual()[nombre] = valor

    def _obtener_variable(self, nombre):
        """Obtiene el valor de una variable desde la pila de marcos."""
        for marco in reversed(self.pila_marcos):
            if nombre in marco:
                return marco[nombre]

        entrada = self.tabla.buscar(nombre)
        if entrada and entrada.inicializado:
            return None  # Variable declarada pero sin valor de inicialización
        raise RuntimeError_(
            'IL-EJE-010',
            f'Variable "{nombre}" no inicializada',
            0, 0
        )

    def _existe_en_marco(self, nombre):
        """Verifica si una variable existe en algún marco visible."""
        for marco in reversed(self.pila_marcos):
            if nombre in marco:
                return True
        return False

    def _resolver_dimension(self, dim):
        """Resuelve una dimensión que puede ser int o nombre de constante."""
        if isinstance(dim, int):
            return dim
        valor = self._obtener_valor_variable(dim)
        return valor if valor is not None else 0

    def _promover_si_float(self, valor, tipo_esperado):
        """Promueve int a float si el tipo esperado es float."""
        if tipo_esperado == 'float' and isinstance(valor, int) and not isinstance(valor, bool):
            return float(valor)
        return valor

    # Valores por defecto de las variables globales (§5.2.3, Apendice D).
    # Las locales NO reciben valor por defecto: leerlas sin inicializar es
    # IL-EJE-010.
    VALORES_POR_DEFECTO = {'int': 0, 'float': 0.0, 'string': '', 'bool': False}

    def _ejecutar_declaracion(self, nodo, es_global=False):
        """Ejecuta una declaración, inicializando variables."""
        if isinstance(nodo, VarDecl):
            self.tipos_variables[nodo.nombre] = nodo.tipo
            valor = None
            if nodo.init_expr:
                valor = self._evaluar_expresion(nodo.init_expr)
            elif es_global:
                valor = self.VALORES_POR_DEFECTO.get(nodo.tipo)
            valor = self._promover_si_float(valor, nodo.tipo)
            self._declarar_variable(nodo.nombre, valor)
        elif isinstance(nodo, ConstDecl):
            self.tipos_variables[nodo.nombre] = nodo.tipo
            valor = self._evaluar_expresion(nodo.init_expr)
            valor = self._promover_si_float(valor, nodo.tipo)
            self._declarar_variable(nodo.nombre, valor)
        elif isinstance(nodo, ArrayDecl):
            if nodo.init_exprs:
                valores = [self._evaluar_expresion(e) for e in nodo.init_exprs]
                self._declarar_variable(nodo.nombre, valores)
            else:
                tam = self._resolver_dimension(nodo.tam)
                self._declarar_variable(nodo.nombre, [None] * tam)
        elif isinstance(nodo, MatrixDecl):
            if nodo.init_filas:
                matriz = []
                for fila in nodo.init_filas:
                    matriz.append([self._evaluar_expresion(e) for e in fila])
                self._declarar_variable(nodo.nombre, matriz)
            else:
                filas = self._resolver_dimension(nodo.filas)
                cols = self._resolver_dimension(nodo.cols)
                self._declarar_variable(nodo.nombre, [[None] * cols for _ in range(filas)])

    def _invocar_built_in(self, nombre, argumentos, nodo=None):
        """Invoca una función integrada traduciendo sus fallos al catálogo.

        Sin esta traducción, un fallo de conversión escaparía como excepción
        del lenguaje de implementación y el estudiante vería un mensaje sin
        código, línea ni columna (§19.1).
        """
        try:
            return ejecutar_built_in(nombre, argumentos)
        except BuiltInError as e:
            raise RuntimeError_(
                e.codigo, e.mensaje,
                getattr(nodo, 'linea', 0), getattr(nodo, 'columna', 0)
            )

    def _ejecutar_subrutina(self, nombre, argumentos, nodo=None):
        """Ejecuta una función o procedimiento por nombre."""
        # Verificar si es built-in
        if es_built_in(nombre):
            return self._invocar_built_in(nombre, argumentos, nodo)

        if nombre in self.funciones_ast:
            nodo = self.funciones_ast[nombre]
            return self._ejecutar_funcion(nodo, argumentos)
        elif nombre in self.procedimientos_ast:
            nodo = self.procedimientos_ast[nombre]
            self._ejecutar_procedimiento(nodo, argumentos)
            return None

        raise RuntimeError_(
            'IL-SEM-003',
            f'Función no encontrada: "{nombre}"',
            0, 0
        )

    # Profundidad maxima de recursion de InvenioLang (§10.6, IL-EJE-040).
    # Cada llamada consume varios marcos de Python, asi que el limite del
    # intérprete anfitrion se eleva en proporcion para que sea SIEMPRE este
    # contador el que se dispare primero y produzca un error del catalogo en
    # lugar de un RecursionError sin codigo ni linea.
    MAX_RECURSION = 500
    MARCOS_PYTHON_POR_LLAMADA = 12
    _profundidad_llamadas = 0

    def _ejecutar_funcion(self, nodo, argumentos):
        """Ejecuta una función y retorna su valor."""
        self._comprobar_cancelacion()
        self._profundidad_llamadas += 1
        if self._profundidad_llamadas > self.MAX_RECURSION:
            self._profundidad_llamadas -= 1
            raise RuntimeError_(
                'IL-EJE-040',
                'Desbordamiento de pila de llamadas (recursión demasiado profunda)',
                nodo.linea, nodo.columna
            )
        self._entrar_marco()
        self._pila_subrutinas.append(nodo.nombre)

        try:
            # Asignar parámetros
            for param, arg in zip(nodo.parametros, argumentos):
                self.tipos_variables[param.nombre] = param.tipo
                self._declarar_variable(param.nombre, arg)

            try:
                for elem in nodo.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except ReturnException as e:
                valor = e.valor
                if nodo.tipo_retorno == 'float' and isinstance(valor, int):
                    valor = float(valor)
                return valor

            return None
        finally:
            if self._pila_subrutinas:
                self._pila_subrutinas.pop()
            self._salir_marco()
            self._profundidad_llamadas -= 1

    def _ejecutar_procedimiento(self, nodo, argumentos):
        """Ejecuta un procedimiento (no retorna valor)."""
        self._profundidad_llamadas += 1
        self._entrar_marco()
        self._pila_subrutinas.append(nodo.nombre)

        try:
            for param, arg in zip(nodo.parametros, argumentos):
                self.tipos_variables[param.nombre] = param.tipo
                self._declarar_variable(param.nombre, arg)

            try:
                for elem in nodo.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except ReturnException:
                pass  # Return sin valor en procedimiento
        finally:
            if self._pila_subrutinas:
                self._pila_subrutinas.pop()
            self._salir_marco()
            self._profundidad_llamadas -= 1

    def _ejecutar_elemento(self, nodo):
        """Ejecuta un elemento de bloque."""
        self._debug_ejecucion(nodo)
        if isinstance(nodo, (VarDecl, ConstDecl, ArrayDecl, MatrixDecl)):
            self._ejecutar_declaracion(nodo)
        elif isinstance(nodo, AssignStmt):
            self._ejecutar_asignacion(nodo)
        elif isinstance(nodo, IncDecStmt):
            self._ejecutar_inc_dec(nodo)
        elif isinstance(nodo, PrintStmt):
            self._ejecutar_print(nodo)
        elif isinstance(nodo, ReadStmt):
            self._ejecutar_read(nodo)
        elif isinstance(nodo, IfStmt):
            self._ejecutar_if(nodo)
        elif isinstance(nodo, WhileStmt):
            self._ejecutar_while(nodo)
        elif isinstance(nodo, ForStmt):
            self._ejecutar_for(nodo)
        elif isinstance(nodo, ReturnStmt):
            self._ejecutar_return(nodo)
        elif isinstance(nodo, BreakStmt):
            raise BreakException()
        elif isinstance(nodo, ContinueStmt):
            raise ContinueException()
        elif isinstance(nodo, CallStmt):
            self._ejecutar_llamada(nodo.nombre, nodo.argumentos, nodo)
        elif isinstance(nodo, FunctionCall):
            self._ejecutar_llamada(nodo.nombre, nodo.argumentos, nodo)

    def _promover_valor(self, valor, nombre):
        """Promueve el valor según el tipo de la variable destino."""
        tipo = self.tipos_variables.get(nombre)
        if tipo is None:
            entrada = self.tabla.buscar(nombre)
            tipo = entrada.tipo_dato if entrada else None
        return self._promover_si_float(valor, tipo)

    def _combinar_compuesto(self, operador, actual, valor, nodo):
        """Calcula el resultado de una asignación compuesta (§5.3.2).

        `x op= e` equivale a `x = x op e`. Aplica a todo destino asignable
        (variable simple, elemento de arreglo o de matriz) y a todo tipo para
        el que el operador esté definido, incluida la concatenación de texto
        con `+=`.
        """
        if operador == '=':
            return valor
        if actual is None:
            raise RuntimeError_(
                'IL-EJE-010',
                'Asignación compuesta sobre un destino no inicializado',
                nodo.linea, nodo.columna
            )
        if operador == '+=':
            return actual + valor
        if operador == '-=':
            return actual - valor
        if operador == '*=':
            return actual * valor
        if operador == '/=':
            if valor == 0:
                raise self._error_division_cero(actual, valor, nodo)
            if isinstance(actual, int) and isinstance(valor, int):
                return self._div_entero(actual, valor)
            return actual / valor
        if operador == '%=':
            if valor == 0:
                raise RuntimeError_('IL-EJE-006', 'División por cero en módulo',
                                    nodo.linea, nodo.columna)
            if isinstance(actual, int) and isinstance(valor, int):
                return self._mod_entero(actual, valor)
            return actual % valor
        return valor

    def _ejecutar_asignacion(self, nodo):
        """Ejecuta una asignación."""
        valor = self._evaluar_expresion(nodo.expr)

        if isinstance(nodo.lvalue, VarLValue):
            nombre = nodo.lvalue.nombre
            valor = self._promover_valor(valor, nombre)
            actual = self._obtener_valor_variable(nombre)
            resultado = self._combinar_compuesto(nodo.operador, actual, valor, nodo)
            resultado = self._promover_valor(resultado, nombre)
            self._asignar_variable(nombre, self._verificar_rango_int(resultado, nodo))

        elif isinstance(nodo.lvalue, ArrayLValue):
            nombre = nodo.lvalue.nombre
            idx = self._evaluar_expresion(nodo.lvalue.indice)
            arreglo = self._obtener_valor_variable(nombre)
            if arreglo is None:
                raise RuntimeError_('IL-EJE-010', f'Arreglo "{nombre}" no inicializado',
                                    nodo.linea, nodo.columna)
            if idx < 0 or idx >= len(arreglo):
                raise RuntimeError_('IL-EJE-050', f'Índice {idx} fuera de rango en "{nombre}"',
                                    nodo.linea, nodo.columna)
            resultado = self._combinar_compuesto(nodo.operador, arreglo[idx], valor, nodo)
            arreglo[idx] = self._verificar_rango_int(resultado, nodo)

        elif isinstance(nodo.lvalue, MatrixLValue):
            nombre = nodo.lvalue.nombre
            fila = self._evaluar_expresion(nodo.lvalue.fila)
            col = self._evaluar_expresion(nodo.lvalue.columna)
            matriz = self._obtener_valor_variable(nombre)
            if matriz is None:
                raise RuntimeError_('IL-EJE-010', f'Matriz "{nombre}" no inicializada',
                                    nodo.linea, nodo.columna)
            if fila < 0 or fila >= len(matriz):
                raise RuntimeError_('IL-EJE-050', f'Índice de fila {fila} fuera de rango',
                                    nodo.linea, nodo.columna)
            if col < 0 or col >= len(matriz[fila]):
                raise RuntimeError_('IL-EJE-050', f'Índice de columna {col} fuera de rango',
                                    nodo.linea, nodo.columna)
            resultado = self._combinar_compuesto(nodo.operador, matriz[fila][col], valor, nodo)
            matriz[fila][col] = self._verificar_rango_int(resultado, nodo)

    def _obtener_valor_variable(self, nombre):
        """Obtiene el valor de una variable desde los marcos."""
        for marco in reversed(self.pila_marcos):
            if nombre in marco:
                return marco[nombre]
        return None

    def _ejecutar_inc_dec(self, nodo):
        """Ejecuta incremento/decremento."""
        actual = self._obtener_valor_variable(nodo.nombre)
        if actual is None:
            raise RuntimeError_('IL-EJE-010', f'Variable "{nodo.nombre}" no inicializada',
                                nodo.linea, nodo.columna)

        if nodo.operador == '++':
            self._asignar_variable(nodo.nombre, actual + 1)
        elif nodo.operador == '--':
            self._asignar_variable(nodo.nombre, actual - 1)

    def _ejecutar_print(self, nodo):
        """Ejecuta print/imprimir."""
        valor = self._evaluar_expresion(nodo.expr)
        self._escribir_salida(valor)

    def _escribir_salida(self, valor):
        """Convierte un valor a string y lo agrega a la salida."""
        if isinstance(valor, bool):
            s = "true" if valor else "false"
        elif isinstance(valor, float):
            s = str(valor)
        elif valor is None:
            s = "void"
        else:
            s = str(valor)
        self.salida.append(s)

    def _ejecutar_read(self, nodo):
        """Ejecuta read/leer.

        Si hay entrada simulada (CLI args / GUI) se consume de la cola.
        En caso contrario se lee de forma bloqueante de la entrada
        estándar, tal como exige la Sección 7.2.
        """
        if self.entrada:
            valor_str = self.entrada.pop(0)
        elif getattr(self, 'usar_stdin', True):
            # CLI/consola: lectura bloqueante desde la entrada estándar (§7.2)
            try:
                valor_str = input()
            except EOFError:
                valor_str = ""
        else:
            # GUI: sin entrada simulada no se bloquea; se tratará como EOF
            valor_str = ""

        tipo = self.tipos_variables.get(nodo.nombre)
        if tipo is None:
            e_tabla = self.tabla.buscar(nodo.nombre)
            tipo = e_tabla.tipo_dato if e_tabla else None

        if tipo:
            try:
                if tipo == 'int':
                    valor = int(valor_str.strip())
                elif tipo == 'float':
                    valor = float(valor_str.strip())
                elif tipo == 'bool':
                    v = valor_str.strip().lower()
                    if v in ('true', 'verdadero', '1'):
                        valor = True
                    elif v in ('false', 'falso', '0'):
                        valor = False
                    else:
                        raise ValueError()
                else:
                    valor = valor_str
                self._asignar_variable(nodo.nombre, valor)
            except ValueError:
                cod = {'int': 'IL-EJE-020', 'float': 'IL-EJE-021', 'bool': 'IL-EJE-022'}
                raise RuntimeError_(
                    cod.get(tipo, 'IL-EJE-020'),
                    f'Entrada no convertible a {tipo}',
                    nodo.linea, nodo.columna
                )

    def _ejecutar_if(self, nodo):
        """Ejecuta if/si."""
        cond = self._evaluar_expresion(nodo.condicion)
        if cond:
            try:
                for elem in nodo.bloque_then.elementos:
                    self._ejecutar_elemento(elem)
            except (BreakException, ContinueException):
                raise  # Propagar hacia arriba
        elif nodo.bloque_else:
            try:
                for elem in nodo.bloque_else.elementos:
                    self._ejecutar_elemento(elem)
            except (BreakException, ContinueException):
                raise

    def _comprobar_cancelacion(self):
        """Aborta si el consumidor pidió detener la ejecución."""
        if self.cancelado is not None and self.cancelado():
            raise ExecutionCancelled()

    def _guardia_iteraciones(self, n, nodo):
        """Detiene un ciclo que excede los límites de ejecución (§9.1, IL-EJE-030).

        Protege el entorno de aula: un ciclo sin terminación aborta con un
        diagnóstico del catálogo en lugar de colgar el proceso. Se comprueban
        dos límites, ambos configurables (`max_iteraciones` y `max_segundos`);
        el de tiempo sólo se consulta cada 2000 vueltas para no penalizar el
        caso normal con una llamada al reloj por iteración.
        """
        if self.max_iteraciones and n > self.max_iteraciones:
            raise RuntimeError_(
                'IL-EJE-030',
                f'Posible ciclo infinito: se superaron '
                f'{self.max_iteraciones:,} iteraciones sin terminar'.replace(',', ' '),
                nodo.linea, nodo.columna
            )
        if self.max_segundos and n % 2000 == 0 and self._t_inicio is not None:
            transcurrido = time.monotonic() - self._t_inicio
            if transcurrido > self.max_segundos:
                raise RuntimeError_(
                    'IL-EJE-030',
                    f'Posible ciclo infinito: el programa lleva '
                    f'{transcurrido:.1f} s sin terminar',
                    nodo.linea, nodo.columna
                )

    def _ejecutar_while(self, nodo):
        """Ejecuta while/mientras."""
        vueltas = 0
        while True:
            cond = self._evaluar_expresion(nodo.condicion)
            if not cond:
                break
            vueltas += 1
            self._guardia_iteraciones(vueltas, nodo)
            self._comprobar_cancelacion()
            try:
                for elem in nodo.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except BreakException:
                break
            except ContinueException:
                continue

    def _ejecutar_for(self, nodo):
        """Ejecuta for/para."""
        # Inicialización
        if nodo.init_stmt:
            if isinstance(nodo.init_stmt, ForInitVar):
                valor = None
                if nodo.init_stmt.init_expr:
                    valor = self._evaluar_expresion(nodo.init_stmt.init_expr)
                self._declarar_variable(nodo.init_stmt.nombre, valor)
            elif isinstance(nodo.init_stmt, ForInitAsig):
                val = self._evaluar_expresion(nodo.init_stmt.expr)
                self._asignar_variable(nodo.init_stmt.lvalue.nombre, val)

        vueltas = 0
        while True:
            # Condición
            if nodo.cond_expr:
                cond = self._evaluar_expresion(nodo.cond_expr)
                if not cond:
                    break
            else:
                pass  # Sin condición = bucle infinito

            vueltas += 1
            self._guardia_iteraciones(vueltas, nodo)
            self._comprobar_cancelacion()

            try:
                for elem in nodo.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except BreakException:
                break
            except ContinueException:
                pass  # Continuar con la acción

            # Acción
            if nodo.act_stmt:
                if isinstance(nodo.act_stmt, ForInitAsig):
                    val = self._evaluar_expresion(nodo.act_stmt.expr)
                    if isinstance(nodo.act_stmt.lvalue, VarLValue):
                        self._asignar_variable(nodo.act_stmt.lvalue.nombre, val)
                elif isinstance(nodo.act_stmt, ForInitIncDec):
                    nombre = nodo.act_stmt.nombre
                    actual = self._obtener_valor_variable(nombre)
                    if actual is not None:
                        if nodo.act_stmt.operador == '++':
                            self._asignar_variable(nombre, actual + 1)
                        elif nodo.act_stmt.operador == '--':
                            self._asignar_variable(nombre, actual - 1)
                elif isinstance(nodo.act_stmt, IncDecNode):
                    nombre = nodo.act_stmt.nombre
                    actual = self._obtener_valor_variable(nombre)
                    if actual is not None:
                        if nodo.act_stmt.operador == '++':
                            self._asignar_variable(nombre, actual + 1)
                        elif nodo.act_stmt.operador == '--':
                            self._asignar_variable(nombre, actual - 1)
                else:
                    self._evaluar_expresion(nodo.act_stmt)

    def _ejecutar_return(self, nodo):
        """Ejecuta return."""
        if nodo.expr:
            valor = self._evaluar_expresion(nodo.expr)
            raise ReturnException(valor)
        raise ReturnException(None)

    def _ejecutar_llamada(self, nombre, argumentos, nodo):
        """Ejecuta una llamada a subrutina."""
        args_eval = [self._evaluar_expresion(a) for a in argumentos]

        if es_built_in(nombre):
            return self._invocar_built_in(nombre, args_eval, nodo)

        if nombre in self.funciones_ast:
            return self._ejecutar_subrutina(nombre, args_eval, nodo)
        elif nombre in self.procedimientos_ast:
            self._ejecutar_subrutina(nombre, args_eval, nodo)
            return None

        raise RuntimeError_(
            'IL-SEM-003',
            f'Subrutina no encontrada: "{nombre}"',
            nodo.linea, nodo.columna
        )

    def _evaluar_expresion(self, nodo):
        """Evalúa una expresión y retorna su valor."""
        if nodo is None:
            return None

        if isinstance(nodo, Literal):
            return nodo.valor

        if isinstance(nodo, Identifier):
            valor = self._obtener_valor_variable(nodo.nombre)
            if valor is None:
                raise RuntimeError_('IL-EJE-010', f'Variable "{nodo.nombre}" no inicializada',
                                    nodo.linea, nodo.columna)
            return valor

        if isinstance(nodo, ArrayAccess):
            arreglo = self._obtener_valor_variable(nodo.nombre)
            if arreglo is None:
                raise RuntimeError_('IL-EJE-010', f'Arreglo "{nodo.nombre}" no inicializado',
                                    nodo.linea, nodo.columna)
            idx = self._evaluar_expresion(nodo.indice)
            if idx < 0 or idx >= len(arreglo):
                raise RuntimeError_('IL-EJE-050', f'Índice {idx} fuera de rango en "{nodo.nombre}"',
                                    nodo.linea, nodo.columna)
            return arreglo[idx]

        if isinstance(nodo, MatrixAccess):
            matriz = self._obtener_valor_variable(nodo.nombre)
            if matriz is None:
                raise RuntimeError_('IL-EJE-010', f'Matriz "{nodo.nombre}" no inicializada',
                                    nodo.linea, nodo.columna)
            fila = self._evaluar_expresion(nodo.fila)
            col = self._evaluar_expresion(nodo.columna)
            if fila < 0 or fila >= len(matriz):
                raise RuntimeError_('IL-EJE-050', f'Fila {fila} fuera de rango',
                                    nodo.linea, nodo.columna)
            if col < 0 or col >= len(matriz[fila]):
                raise RuntimeError_('IL-EJE-050', f'Columna {col} fuera de rango',
                                    nodo.linea, nodo.columna)
            return matriz[fila][col]

        if isinstance(nodo, FunctionCall):
            args = [self._evaluar_expresion(a) for a in nodo.argumentos]
            return self._ejecutar_subrutina(nodo.nombre, args, nodo)

        if isinstance(nodo, BinaryOp):
            # Cortocircuito garantizado por §6.3.1: el operando derecho NO se
            # evalua cuando el izquierdo ya determina el resultado. Debe
            # resolverse aqui, antes de evaluar la derecha.
            if nodo.operador == '&&':
                if self._evaluar_expresion(nodo.izquierda) is not True:
                    return False
                return self._evaluar_expresion(nodo.derecha)
            if nodo.operador == '||':
                if self._evaluar_expresion(nodo.izquierda) is True:
                    return True
                return self._evaluar_expresion(nodo.derecha)
            left = self._evaluar_expresion(nodo.izquierda)
            right = self._evaluar_expresion(nodo.derecha)
            return self._aplicar_binario(nodo.operador, left, right, nodo)

        if isinstance(nodo, UnaryOp):
            # ++ / -- en expresion modifican la variable (§5.3.3). El operando
            # es siempre un lvalue simple, garantizado por la gramatica.
            if nodo.operador in ('++', '--'):
                return self._aplicar_inc_dec_expr(nodo)
            oper = self._evaluar_expresion(nodo.operando)
            return self._aplicar_unario(nodo.operador, oper, nodo.es_prefijo, nodo)

        return None

    def _aplicar_inc_dec_expr(self, nodo):
        """Aplica ++/-- usado dentro de una expresion (§5.3.3).

        Prefijo: modifica primero y retorna el valor nuevo.
        Postfijo: retorna el valor previo y luego modifica.
        """
        destino = nodo.operando
        if not isinstance(destino, Identifier):
            # La gramatica solo admite expr_primaria; si no es un identificador
            # no hay donde escribir de vuelta.
            valor = self._evaluar_expresion(destino)
            delta = 1 if nodo.operador == '++' else -1
            return valor + delta if nodo.es_prefijo else valor

        nombre = destino.nombre
        actual = self._obtener_valor_variable(nombre)
        if actual is None:
            raise RuntimeError_('IL-EJE-010', f'Variable "{nombre}" no inicializada',
                                nodo.linea, nodo.columna)
        nuevo = actual + 1 if nodo.operador == '++' else actual - 1
        nuevo = self._verificar_rango_int(nuevo, nodo)
        self._asignar_variable(nombre, nuevo)
        return nuevo if nodo.es_prefijo else actual

    # Rango del tipo int / entero: 32 bits con signo (§4.2.1, Apendice D)
    INT_MIN = -2147483648
    INT_MAX = 2147483647

    def _verificar_rango_int(self, valor, nodo):
        """Verifica que un resultado entero quepa en 32 bits (§4.2.1).

        Python usa enteros de precision arbitraria, asi que el desbordamiento
        debe comprobarse explicitamente para producir IL-EJE-001 como exige el
        catalogo (§15.6). Los valores no enteros pasan sin cambios.
        """
        if isinstance(valor, bool) or not isinstance(valor, int):
            return valor
        if valor < self.INT_MIN or valor > self.INT_MAX:
            raise RuntimeError_(
                'IL-EJE-001',
                f'Desbordamiento de entero: {valor} excede el rango '
                f'[{self.INT_MIN}, {self.INT_MAX}]',
                getattr(nodo, 'linea', 0), getattr(nodo, 'columna', 0)
            )
        return valor

    def _error_division_cero(self, izq, der, nodo):
        """Devuelve el error de división entre cero que corresponda.

        La división real produce un valor especial de IEEE 754 y le corresponde
        IL-EJE-002 (§4.3, §15.6); la división entera, IL-EJE-006 (§6.6.4).
        """
        es_real = isinstance(izq, float) or isinstance(der, float)
        if es_real:
            return RuntimeError_(
                'IL-EJE-002',
                'Operación de punto flotante inválida: división entre 0.0',
                nodo.linea, nodo.columna
            )
        return RuntimeError_('IL-EJE-006', 'División por cero',
                             nodo.linea, nodo.columna)

    def _div_entero(self, a, b):
        """División entera con truncamiento hacia cero (§4.2.2).
        Ej: 7/2=3 y -7/2=-3 (a diferencia del operador // de Python que
        redondea hacia -infinito)."""
        q = abs(a) // abs(b)
        return -q if (a < 0) != (b < 0) else q

    def _mod_entero(self, a, b):
        """Módulo entero con el signo del dividendo (estilo C), consistente
        con la división que trunca hacia cero."""
        r = abs(a) % abs(b)
        return -r if a < 0 else r

    def _aplicar_binario(self, op, left, right, nodo):
        """Aplica un operador binario."""
        if op == '||':
            return left or right
        if op == '&&':
            return left and right
        if op == '==':
            return left == right
        if op == '!=':
            return left != right
        if op == '<':
            return left < right
        if op == '>':
            return left > right
        if op == '<=':
            return left <= right
        if op == '>=':
            return left >= right
        if op == '+':
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            return self._verificar_rango_int(left + right, nodo)
        if op == '-':
            return self._verificar_rango_int(left - right, nodo)
        if op == '*':
            return self._verificar_rango_int(left * right, nodo)
        if op == '/':
            if right == 0:
                raise self._error_division_cero(left, right, nodo)
            if isinstance(left, int) and isinstance(right, int):
                return self._div_entero(left, right)  # Trunca hacia cero (§4.2.2)
            return left / right
        if op == '%':
            if right == 0:
                raise RuntimeError_('IL-EJE-006', 'División por cero en módulo',
                                    nodo.linea, nodo.columna)
            if isinstance(left, int) and isinstance(right, int):
                return self._mod_entero(left, right)
            return left % right
        raise RuntimeError_('IL-EJE-001', f'Operador desconocido: {op}',
                            nodo.linea, nodo.columna)

    def _aplicar_unario(self, op, oper, es_prefijo, nodo):
        """Aplica un operador unario."""
        if op == '-':
            return -oper
        if op == '!':
            return not oper
        if op == '++':
            # En expresiones, el valor retornado depende de si es prefijo o postfijo
            # Para simplificar: retornamos el valor y el efecto se aplica en la instrucción
            if es_prefijo:
                return oper + 1
            return oper  # Postfijo retorna el valor original
        if op == '--':
            if es_prefijo:
                return oper - 1
            return oper
        return oper
