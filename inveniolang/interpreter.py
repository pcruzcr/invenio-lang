# Módulo del Intérprete de Árbol de InvenioLang 1.0
# Implementa el recorrido y ejecución del AST verificado
# Soporta: variables, constantes, arreglos, matrices, funciones, procedimientos
# Patrones aplicados: Visitor (recorrido AST sin isinstance disperso),
# Strategy (operaciones aritméticas intercambiables), Command (debug),
# Memento (snapshot), Observer (eventos de ejecución), Template Method
from __future__ import annotations

import sys
import time
from typing import Any

from .ast_nodes import (
    ArrayAccess,
    ArrayDecl,
    ArrayLValue,
    AssignStmt,
    ASTVisitor,
    BinaryOp,
    BreakStmt,
    Callable,
    CallStmt,
    ConstDecl,
    ContinueStmt,
    DoWhileStmt,
    ForEachStmt,
    ForInitAsig,
    ForInitIncDec,
    ForInitVar,
    ForStmt,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStmt,
    IncDecStmt,
    LambdaExpr,
    Literal,
    MatchStmt,
    MatrixAccess,
    MatrixDecl,
    MatrixLValue,
    MemberAccess,
    MemberLValue,
    MethodCallExpr,
    MethodCallStmt,
    NewExpr,
    NullExpr,
    PrintStmt,
    ProcedureDecl,
    ReadStmt,
    ReturnStmt,
    SuperCallStmt,
    SuperExpr,
    SwitchStmt,
    TernaryExpr,
    ThisExpr,
    TryStmt,
    UnaryOp,
    VarDecl,
    VarLValue,
    WhileStmt,
)
from .builtins import BuiltInError, ejecutar_built_in, es_built_in
from .patterns import Caretaker, Strategy, StrategyContext, Subject

# Orden superior sobre arreglos (Etapa 12.7) -- ver semantic.py::
# _ORDEN_SUPERIOR para el diseño completo (monomórfico sobre entero,
# mapear/filtrar escriben en un arreglo de salida por referencia).
_NOMBRES_ORDEN_SUPERIOR = {"reducir", "reduce", "mapear", "map", "filtrar", "filter"}


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


class InstanciaObjeto:
    """Instancia de una clase de InvenioLang 2.0 (POO).

    Guarda el nombre de la clase REAL (dinámica) del objeto -- es lo que
    hace posible el despacho virtual: buscar un método a partir de
    `instancia.clase` (no del tipo estático de la variable que la referencia)
    siempre encuentra la sobrescritura más derivada. Los campos viven en un
    dict plano porque InvenioLang 2.0 no permite redeclarar un atributo
    heredado (IL-POO-004), así que no hace falta un dict por nivel.

    Al ser un objeto de Python normal, asignar o pasar una instancia como
    argumento copia la REFERENCIA, no el objeto -- igual que ya ocurre con
    los arreglos (§12.2 de la v1.0) -- y la igualdad `==`/`!=` por defecto
    de Python ya es por identidad, tal como pide §3 regla 9 de la spec de
    POO, sin necesidad de sobrescribir __eq__.
    """

    __slots__ = ("clase", "campos")

    def __init__(self, clase):
        self.clase = clase
        self.campos = {}

    def __repr__(self):
        pares = ", ".join(f"{k}={v!r}" for k, v in self.campos.items())
        return f"{self.clase}({pares})"


class _AccesoEstatico:
    """Marcador de receptor 'NombreClase' (acceso estático, Etapa 7) -- NO.

    es una instancia. `_resolver_receptor` lo devuelve cuando el receptor
    de un acceso a miembro es el nombre de una clase (no una variable), y
    el resto del intérprete lo usa para enrutar lectura/escritura de
    atributos a `ClaseInfo.estado_estatico` en vez de `InstanciaObjeto.
    campos`. La propiedad `clase` deja que `_ejecutar_metodo` (bookkeeping
    de pila de llamadas, `_pila_instancias`) trate una llamada a método
    estático igual que una de instancia, sin ramas especiales -- un método
    estático simplemente no debe usar `this`/`super` (se bloquea en
    semantic.py, IL-POO-025).
    """

    __slots__ = ("nombre_clase",)

    def __init__(self, nombre_clase):
        self.nombre_clase = nombre_clase

    @property
    def clase(self):
        """Nombre de la clase para despacho."""
        return self.nombre_clase


class ValorFuncion:
    """Valor función de primera clase (Etapa 12.6). Envuelve EXACTAMENTE.

    una de dos cosas:
      - `lambda_nodo` + `marcos_capturados`: un lambda creado en tiempo de
        ejecución, con una referencia (no copia) a la pila de marcos
        vigente en el momento de crearlo -- es lo que hace que capture
        variables del entorno léxico por referencia (si esa variable
        cambia después de crear el lambda, el lambda ve el cambio; y si
        el marco que la contiene se modifica, también). Ver
        `Interpreter._invocar_valor_funcion`.
      - `nombre_subrutina`: el nombre de una función/procedimiento de
        nivel superior pasado por referencia (`operar = sumar;`) -- no
        necesita marcos capturados, ya se ejecuta con su propio marco
        aislado de siempre (`_ejecutar_funcion`/`_ejecutar_procedimiento`).
    """

    __slots__ = ("lambda_nodo", "marcos_capturados", "nombre_subrutina")

    def __init__(self, lambda_nodo=None, marcos_capturados=None, nombre_subrutina=None):
        self.lambda_nodo = lambda_nodo
        self.marcos_capturados = marcos_capturados
        self.nombre_subrutina = nombre_subrutina

    def __repr__(self):
        if self.nombre_subrutina is not None:
            return f"ValorFuncion({self.nombre_subrutina})"
        tipos = ",".join(p.tipo for p in self.lambda_nodo.parametros)
        return f"ValorFuncion(lambda({tipos}) -> {self.lambda_nodo.tipo_retorno})"


class ExecutionCancelled(Exception):
    """Señala que la ejecución fue cancelada desde fuera del intérprete.

    La lanza `_comprobar_cancelacion` cuando el consumidor (por ejemplo el
    botón Detener de la IDE) activa la bandera de cancelación. Es distinta de
    IL-EJE-030: no es un error del programa del estudiante, sino una decisión
    del usuario, y por eso no se registra en el catálogo de errores.
    """


class ExecutionStrategy(Strategy):
    """Strategy para operaciones — permite intercambiar algoritmos (int vs float)."""

    def execute(self, a: Any, b: Any, *args, **kwargs) -> Any:
        """Ejecuta la operación."""
        raise NotImplementedError


class Interpreter(ASTVisitor, Subject):
    """Intérprete de árbol para InvenioLang 1.0.

    Recorre el AST verificando y ejecutando las instrucciones.
    Mantiene un entorno con marcos de pila para el manejo de ámbitos.

    Patrones: Visitor (visit_*), Strategy (operaciones), Subject/Observer
    (eventos ejecución para IDE), Command (debug), Memento (snapshot).
    Optimización: despacho Visitor O(1) vs isinstance chain, caché de
    operaciones, notificación desacoplada.
    """

    def __init__(self, error_manager, tabla_simbolos):
        Subject.__init__(self)
        self.error_manager = error_manager
        self.tabla = tabla_simbolos
        self._strategy_ctx = StrategyContext()
        self._caretaker = Caretaker(max_mementos=30)
        self._op_cache: dict[str, Callable] = {}
        # Entorno de ejecución: pila de marcos (cada marco es un dict)
        self.pila_marcos = [{}]
        # Tipos de las variables conocidos en ejecución (por nombre).
        # Se usa porque en tiempo de ejecución los ámbitos locales ya fueron
        # desapilados de la tabla de símbolos, y `read` necesita conocer el tipo.
        self.tipos_variables = {}
        # Para funciones: tabla de nodos AST
        self.funciones_ast = {}
        self.procedimientos_ast = {}
        # POO (InvenioLang 2.0): nodos ClassDecl por nombre (para ejecutar
        # cuerpos de constructor/método -- self.tabla.clases solo tiene
        # metadatos de firma, no los bloques ejecutables).
        self.clases_ast = {}
        # Pila de instancias 'este'/this: el tope es la instancia sobre la
        # que corre el método/constructor actual (None fuera de ambos).
        self._pila_instancias = []
        # Pila de la clase donde fue DECLARADO el método/constructor actual
        # (distinta de instancia.clase, la clase dinámica): es el punto de
        # partida de padre/super, que debe saltarse el despacho virtual.
        self._pila_clase_definicion = []
        # Entrada/salida capturable
        self.salida = []
        self.entrada = []
        # Ganchos opcionales para la terminal integrada del IDE (Etapa 9),
        # mismo criterio que los ganchos debug_* de la Etapa 1: por defecto
        # `None`, cero cambio de comportamiento para CLI/conformidad.py/el
        # resto de la GUI, que nunca los configuran.
        # `on_salida(str)`: se invoca ademas de acumular en `self.salida`,
        # para transmitir la salida EN VIVO (linea a linea) en vez de
        # esperar a que termine toda la ejecucion.
        self.on_salida = None
        # `leer_interactivo() -> str`: si esta definido y no hay entrada
        # simulada en la cola ni `usar_stdin`, se usa para pedir la entrada
        # de forma bloqueante (p.ej. la GUI puede implementarlo con un
        # threading.Event, igual que ya hace debug_wait para pausar en un
        # breakpoint) en vez de tratarlo como fin de archivo.
        self.leer_interactivo = None
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
        self.debug_on_statement = None  # callable(snapshot) -> int (0 pausa)
        self.debug_wait = None  # callable() -> bloquea hasta reanudar
        self._pila_subrutinas = []

    def _snapshot_debug(self, nodo):
        """Construye una instantánea del estado para depuración/traza."""
        visibles = {}
        for marco in reversed(self.pila_marcos):
            for k, v in marco.items():
                if k not in visibles:
                    visibles[k] = v
        variables = []
        instancia = self._instancia_actual()
        if instancia is not None:
            variables.append({"nombre": "este", "tipo": instancia.clase, "valor": instancia})
        for k, v in visibles.items():
            tipo = self.tipos_variables.get(k)
            if tipo is None:
                e = self.tabla.buscar(k)
                tipo = e.tipo_dato if e else type(v).__name__
            variables.append({"nombre": k, "tipo": tipo, "valor": v})
        return {
            "linea": getattr(nodo, "linea", 0),
            "columna": getattr(nodo, "columna", 0),
            "variables": variables,
            "pila": list(self._pila_subrutinas),
            "salida": list(self.salida),
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
            self.debug_step = False  # consume el "paso"
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
            self.funciones_ast["main"] = ast.main
        self.clases_ast = {c.nombre: c for c in ast.clases}

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
        self._pila_instancias = []
        self._pila_clase_definicion = []
        self._profundidad_llamadas = 0
        self._t_inicio = time.monotonic()

        # Dar holgura al limite de Python para que IL-EJE-040 se dispare antes
        # que RecursionError (véase MAX_RECURSION).
        margen = self.MAX_RECURSION * self.MARCOS_PYTHON_POR_LLAMADA + 1000
        limite_previo = sys.getrecursionlimit()
        if limite_previo < margen:
            sys.setrecursionlimit(margen)

        self.registrar_subrutinas(ast)
        self._inicializar_estaticos(ast)

        # Inicializar variables globales (reciben valor por defecto, §5.2.3)
        for d in ast.declaraciones_globales:
            self._ejecutar_declaracion(d, es_global=True)
        for d in ast.declaraciones_posteriores:
            self._ejecutar_declaracion(d, es_global=True)

        # Ejecutar main
        try:
            self._ejecutar_subrutina("main", [])
        except ReturnException:
            pass  # main no retorna valor
        except RuntimeError_ as e:
            self.error_manager.error_ejecucion(e.codigo, e.mensaje, e.linea, e.columna)
        except ExecutionCancelled:
            raise  # decision del usuario, no un error del programa
        except BreakException:
            # break/continue fuera de ciclo es un error semantico (§9.4); si
            # llega hasta aqui es que el analisis no lo detecto.
            self.error_manager.error_ejecucion("IL-SEM-040", "break fuera de un ciclo", 0, 0)
        except ContinueException:
            self.error_manager.error_ejecucion("IL-SEM-041", "continue fuera de un ciclo", 0, 0)

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
        raise RuntimeError_("IL-EJE-010", f'Variable "{nombre}" no inicializada', 0, 0)

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
        if tipo_esperado == "float" and isinstance(valor, int) and not isinstance(valor, bool):
            return float(valor)
        return valor

    # Valores por defecto de las variables globales (§5.2.3, Apendice D).
    # Las locales NO reciben valor por defecto: leerlas sin inicializar es
    # IL-EJE-010.
    VALORES_POR_DEFECTO = {"int": 0, "float": 0.0, "string": "", "bool": False}

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
            # Hardening: límite de memoria en ejecución (coherente con semantic.py)
            _max_ejec_tam = 100000
            if nodo.init_exprs:
                if len(nodo.init_exprs) > _max_ejec_tam:
                    raise RuntimeError_(
                        "IL-EJE-050",
                        f'Arreglo "{nodo.nombre}" excede límite de {_max_ejec_tam} elementos',
                        nodo.linea,
                        nodo.columna,
                    )
                valores = [self._evaluar_expresion(e) for e in nodo.init_exprs]
                self._declarar_variable(nodo.nombre, valores)
            else:
                tam = self._resolver_dimension(nodo.tam)
                if tam > _max_ejec_tam:
                    raise RuntimeError_(
                        "IL-EJE-050",
                        f'Arreglo "{nodo.nombre}" excede límite de {_max_ejec_tam} elementos',
                        nodo.linea,
                        nodo.columna,
                    )
                self._declarar_variable(nodo.nombre, [None] * tam)
        elif isinstance(nodo, MatrixDecl):
            _max_ejec_dim = 10000
            if nodo.init_filas:
                matriz = []
                for fila in nodo.init_filas:
                    matriz.append([self._evaluar_expresion(e) for e in fila])
                self._declarar_variable(nodo.nombre, matriz)
            else:
                filas = self._resolver_dimension(nodo.filas)
                cols = self._resolver_dimension(nodo.cols)
                if filas > _max_ejec_dim or cols > _max_ejec_dim or filas * cols > 200000:
                    raise RuntimeError_(
                        "IL-EJE-050",
                        f'Matriz "{nodo.nombre}" excede límites de memoria ({filas}x{cols})',
                        nodo.linea,
                        nodo.columna,
                    )
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
                e.codigo, e.mensaje, getattr(nodo, "linea", 0), getattr(nodo, "columna", 0)
            ) from e

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

        raise RuntimeError_("IL-SEM-003", f'Función no encontrada: "{nombre}"', 0, 0)

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
                "IL-EJE-040",
                "Desbordamiento de pila de llamadas (recursión demasiado profunda)",
                nodo.linea,
                nodo.columna,
            )
        self._entrar_marco()
        self._pila_subrutinas.append(nodo.nombre)

        try:
            # Asignar parámetros
            for param, arg in zip(nodo.parametros, argumentos, strict=True):
                self.tipos_variables[param.nombre] = param.tipo
                self._declarar_variable(param.nombre, arg)

            try:
                for elem in nodo.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except ReturnException as e:
                valor = e.valor
                if nodo.tipo_retorno == "float" and isinstance(valor, int):
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
            for param, arg in zip(nodo.parametros, argumentos, strict=True):
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

    def _resolver_valor_funcion_variable(self, nombre):
        """Si `nombre` es una variable local que guarda un ValorFuncion.

        (Etapa 12.6), lo retorna; si no, None. Usado en los puntos de
        llamada (`_ejecutar_llamada`, `FunctionCall`) para decidir, con la
        MISMA sintaxis de llamada que una función/procedimiento normal
        (`llamada_funcion : IDENTIFICADOR '(' args ')'`), si se está
        invocando un closure guardado en variable en vez de una subrutina
        de nivel superior -- el punto de decisión es semántico (ver
        checkpoint 12.5), no gramatical.
        """
        valor = self._obtener_valor_variable(nombre)
        return valor if isinstance(valor, ValorFuncion) else None

    def _invocar_valor_funcion(self, vf, argumentos, nodo):
        """Invoca un ValorFuncion (Etapa 12.6): delega en.

        `_ejecutar_subrutina` si envuelve una función/procedimiento de
        nivel superior, o ejecuta el lambda con sus marcos capturados
        restaurados temporalmente en `self.pila_marcos` -- el mecanismo de
        captura léxica completo: `vf.marcos_capturados` es una lista de
        REFERENCIAS a los mismos diccionarios que existían cuando se creó
        el lambda (ver LambdaExpr en _evaluar_expresion), así que una
        variable capturada que cambia después de crear el closure (o que
        el propio closure reasigna) se sigue viendo actualizada la
        próxima vez que se invoca -- semántica estándar de clausura por
        referencia, no por valor.
        """
        if vf.nombre_subrutina is not None:
            return self._ejecutar_subrutina(vf.nombre_subrutina, argumentos, nodo)

        nodo_lambda = vf.lambda_nodo
        self._profundidad_llamadas += 1
        if self._profundidad_llamadas > self.MAX_RECURSION:
            self._profundidad_llamadas -= 1
            raise RuntimeError_(
                "IL-EJE-040",
                "Desbordamiento de pila de llamadas (recursión demasiado profunda)",
                nodo.linea,
                nodo.columna,
            )
        marcos_previos = self.pila_marcos
        self.pila_marcos = list(vf.marcos_capturados) + [{}]
        self._pila_subrutinas.append("<lambda>")
        try:
            for param, arg in zip(nodo_lambda.parametros, argumentos, strict=True):
                self.tipos_variables[param.nombre] = param.tipo
                self._declarar_variable(param.nombre, arg)
            try:
                for elem in nodo_lambda.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except ReturnException as e:
                valor = e.valor
                if nodo_lambda.tipo_retorno == "float" and isinstance(valor, int):
                    valor = float(valor)
                return valor
            return None
        finally:
            if self._pila_subrutinas:
                self._pila_subrutinas.pop()
            self.pila_marcos = marcos_previos
            self._profundidad_llamadas -= 1

    def _invocar_orden_superior(self, nombre, args_eval, nodo):
        """Ejecuta mapear/filtrar/reducir.

        _ORDEN_SUPERIOR para el diseño completo. `salida` en mapear/
        filtrar es la MISMA lista de Python que ya representa el arreglo
        del llamador (los arreglos ya se pasan por referencia en todo el
        lenguaje) -- escribir `salida[i] = ...` aquí es exactamente lo
        mismo que ya hace cualquier función que recibe un arreglo por
        parámetro y lo modifica, sin mecanismo nuevo.
        """
        if nombre in ("reducir", "reduce"):
            arreglo, f, inicial = args_eval
            acc = inicial
            for v in arreglo:
                acc = self._invocar_valor_funcion(f, [acc, v], nodo)
            return acc
        if nombre in ("mapear", "map"):
            arreglo, salida, f = args_eval
            for i, v in enumerate(arreglo):
                if i < len(salida):
                    salida[i] = self._invocar_valor_funcion(f, [v], nodo)
            return None
        if nombre in ("filtrar", "filter"):
            arreglo, salida, pred = args_eval
            k = 0
            for v in arreglo:
                if self._invocar_valor_funcion(pred, [v], nodo):
                    if k < len(salida):
                        salida[k] = v
                    k += 1
            return k
        return None

    # ============================================================
    # POO (InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md)
    # ============================================================

    def _es_tipo_clase_de_variable(self, nombre):
        """Indica si `nombre` esta declarado con un tipo de clase (para.

        distinguir, al leerlo, "None porque nunca se asigno" -- error,
        IL-EJE-010 -- de "None porque su valor es nulo/null" -- valido).
        """
        tipo = self.tipos_variables.get(nombre)
        if tipo is None:
            entrada = self.tabla.buscar(nombre)
            tipo = entrada.tipo_dato if entrada else None
        return bool(tipo) and tipo in self.tabla.clases

    def _instancia_actual(self):
        return self._pila_instancias[-1] if self._pila_instancias else None

    def _clase_definicion_actual(self):
        return self._pila_clase_definicion[-1] if self._pila_clase_definicion else None

    def _tipo_runtime(self, valor):
        """Tipo de un valor en tiempo de ejecución, para elegir sobrecarga.

        (Etapa 7) -- mismo vocabulario de tipos que usa el resto del
        compilador ('int'/'float'/'string'/'bool'/nombre de clase/'null').
        """
        if isinstance(valor, bool):
            return "bool"
        if isinstance(valor, int):
            return "int"
        if isinstance(valor, float):
            return "float"
        if isinstance(valor, str):
            return "string"
        if isinstance(valor, InstanciaObjeto):
            return valor.clase
        if valor is None:
            return "null"
        return None

    def _tipo_parametro_ast(self, p):
        """Formato de tipo de parámetro.

        depender de ese módulo (interpreter.py no importa semantic.py).
        """
        if p.es_matriz:
            return f"{p.tipo}[][]"
        if p.es_arreglo:
            return f"{p.tipo}[]"
        return p.tipo

    def _buscar_metodo_ast(self, nombre_clase, nombre_metodo, argumentos=None):
        """Encuentra la implementación más derivada de `nombre_metodo`.

        visible desde `nombre_clase`, devolviendo (clase_declarante,
        MethodDecl). Reutiliza `SymbolTable.resolver_metodo` (ya probado en
        semantic.py/type_checker.py) para decidir QUÉ clase la declara, y
        aquí solo se busca el nodo AST correspondiente en esa clase.

        El despacho VIRTUAL surge por completo de qué `nombre_clase` recibe
        esta función como punto de partida: para una llamada normal
        (this/identificador) se pasa la clase REAL de la instancia; para
        `padre.metodo(...)` se pasa el padre de la clase donde el método
        actual fue declarado, saltándose la resolución dinámica.

        `argumentos` (Etapa 7, sobrecarga): valores YA evaluados de la
        llamada -- si se dan, eligen la sobrecarga cuya firma coincide con
        sus tipos en tiempo de ejecución (mismo mecanismo de
        `resolver_metodo` que ya usa type_checker.py, pero con tipos
        derivados de los VALORES reales en vez de la verificación
        estática). Sin `argumentos` (o con una sola sobrecarga posible),
        se usa la primera/única declarada.
        """
        tipos_args = [self._tipo_runtime(a) for a in argumentos] if argumentos is not None else None
        resultado = self.tabla.resolver_metodo(nombre_clase, nombre_metodo, tipos_args)
        if resultado is None and tipos_args is not None:
            # No debería pasar si type_checker.py ya validó el programa;
            # por robustez, cae a la primera sobrecarga declarada.
            resultado = self.tabla.resolver_metodo(nombre_clase, nombre_metodo)
        if resultado is None:
            return None
        clase_declarante, metodo_info = resultado
        clase_nodo = self.clases_ast.get(clase_declarante)
        if clase_nodo is None:
            return None
        for met in clase_nodo.metodos:
            if met.nombre == nombre_metodo and (
                [self._tipo_parametro_ast(p) for p in met.parametros] == metodo_info.params_tipos
            ):
                return clase_declarante, met
        # Ninguna coincidencia exacta de firma (no debería pasar): primer
        # método con ese nombre, por robustez.
        for met in clase_nodo.metodos:
            if met.nombre == nombre_metodo:
                return clase_declarante, met
        return None

    def _resolver_receptor(self, receptor):
        """Retorna (instancia, nombre_clase_de_busqueda) para el receptor de.

        un acceso a miembro. Ver `_buscar_metodo_ast` sobre por qué el punto
        de partida difiere entre this/identificador (dinámico) y padre
        (fijo, salta el despacho virtual).
        """
        if isinstance(receptor, ThisExpr):
            instancia = self._instancia_actual()
            return instancia, (instancia.clase if instancia else None)
        if isinstance(receptor, SuperExpr):
            instancia = self._instancia_actual()
            clase_def = self._clase_definicion_actual()
            info = self.tabla.clases.get(clase_def) if clase_def else None
            return instancia, (info.padre if info else None)
        if isinstance(receptor, Identifier):
            # Etapa 7 (estatico): si el identificador NO es una variable
            # visible pero SI es el nombre de una clase, es acceso estatico
            # -- NombreClase.miembro. Una variable local que sombree el
            # nombre de una clase (permitido con IL-WARN-001, no un error)
            # gana, igual que en cualquier otro uso de un identificador.
            if not self._existe_en_marco(receptor.nombre) and self.tabla.es_clase(receptor.nombre):
                return _AccesoEstatico(receptor.nombre), receptor.nombre
            instancia = self._obtener_valor_variable(receptor.nombre)
            clase = instancia.clase if isinstance(instancia, InstanciaObjeto) else None
            return instancia, clase
        if isinstance(receptor, ArrayAccess):
            # Elemento de arreglo de objetos: se reutiliza _evaluar_expresion
            # para heredar gratis la verificacion de limites (IL-EJE-050) y
            # de arreglo no inicializado (IL-EJE-010) ya existentes.
            instancia = self._evaluar_expresion(receptor)
            clase = instancia.clase if isinstance(instancia, InstanciaObjeto) else None
            return instancia, clase
        return None, None

    def _inicializar_estaticos(self, ast):
        """Inicializa los atributos estáticos de cada clase UNA sola vez.

        (Etapa 7) -- una única copia compartida en `ClaseInfo.
        estado_estatico`, a diferencia de los atributos de instancia (uno
        por objeto, ver `_inicializar_campos`). Ámbito vacío: sin `this` ni
        variables locales, mismo criterio que los inicializadores de
        instancia.
        """
        self._entrar_marco()
        try:
            for c in ast.clases:
                info = self.tabla.clases.get(c.nombre)
                if info is None:
                    continue
                for attr in c.atributos:
                    if not attr.es_estatico:
                        continue
                    if attr.init_expr is not None:
                        valor = self._evaluar_expresion(attr.init_expr)
                    else:
                        valor = self.VALORES_POR_DEFECTO.get(attr.tipo)
                    info.estado_estatico[attr.nombre] = valor
            # Etapa 11: cada miembro de una enumeración vale su posición de
            # declaración (0, 1, 2, ...) -- se reutiliza el mismo mecanismo
            # de estado_estatico que los atributos estáticos reales, así
            # que NombreEnum.MIEMBRO ya funciona con el código existente.
            for e in ast.enums:
                info = self.tabla.clases.get(e.nombre)
                if info is None:
                    continue
                for indice, miembro in enumerate(e.valores):
                    # Etapa 12.9: miembro es EnumMiembro, no str (ver
                    # semantic.py::_declarar_enum) -- mismo valor ordinal
                    # de siempre, con o sin carga, hasta que la Etapa 12.10
                    # active el mecanismo de clases internas para variantes
                    # con carga.
                    info.estado_estatico[miembro.nombre] = indice
        finally:
            self._salir_marco()

    def _es_atributo_estatico(self, nombre_clase, nombre_campo):
        """Etapa 7: True si `nombre_campo` es un atributo ESTATICO de.

        `nombre_clase` (o un ancestro). Deja acceder a un miembro estático
        también a través de una instancia (`objeto.estatico`), no solo del
        nombre de la clase -- permisivo a propósito, ver semantic.py.
        """
        for clase in self.tabla.cadena_ancestros(nombre_clase) or [nombre_clase]:
            c_info = self.tabla.clases.get(clase)
            if c_info and nombre_campo in c_info.atributos:
                return c_info.atributos[nombre_campo].es_estatico
        return False

    def _leer_campo_estatico(self, nombre_clase, nombre_campo, nodo):
        for clase in self.tabla.cadena_ancestros(nombre_clase) or [nombre_clase]:
            c_info = self.tabla.clases.get(clase)
            if c_info and nombre_campo in c_info.atributos:
                return c_info.estado_estatico.get(nombre_campo)
        raise RuntimeError_(
            "IL-SEM-003", f'Atributo no encontrado: "{nombre_campo}"', nodo.linea, nodo.columna
        )

    def _escribir_campo_estatico(self, nombre_clase, nombre_campo, valor, nodo):
        for clase in self.tabla.cadena_ancestros(nombre_clase) or [nombre_clase]:
            c_info = self.tabla.clases.get(clase)
            if c_info and nombre_campo in c_info.atributos:
                c_info.estado_estatico[nombre_campo] = valor
                return
        raise RuntimeError_(
            "IL-SEM-003", f'Atributo no encontrado: "{nombre_campo}"', nodo.linea, nodo.columna
        )

    def _inicializar_campos(self, instancia, nombre_clase):
        """Inicializa los campos de una instancia recién creada, del.

        ancestro más lejano al más cercano (§4 de la spec de POO). Se
        evalúan los inicializadores en un ámbito vacío -- igual que validó
        semantic.py (sin `este` ni variables locales del llamador visibles,
        clase_actual=None durante esa verificación).
        """
        cadena = self.tabla.cadena_ancestros(nombre_clase) or [nombre_clase]
        self._entrar_marco()
        try:
            for clase in reversed(cadena):
                clase_nodo = self.clases_ast.get(clase)
                if clase_nodo is None:
                    continue
                for attr in clase_nodo.atributos:
                    if attr.init_expr is not None:
                        valor = self._evaluar_expresion(attr.init_expr)
                    else:
                        valor = self.VALORES_POR_DEFECTO.get(attr.tipo)
                    instancia.campos[attr.nombre] = valor
        finally:
            self._salir_marco()

    def _crear_instancia(self, nombre_clase, argumentos, nodo):
        """Implementa `nuevo`/`new`: reserva los campos con sus valores por.

        defecto/inicializadores y ejecuta la cadena de constructores.
        """
        instancia = InstanciaObjeto(nombre_clase)
        self._inicializar_campos(instancia, nombre_clase)
        self._ejecutar_constructor(instancia, nombre_clase, argumentos, nodo)
        return instancia

    def _buscar_constructor_ast(self, nombre_clase, argumentos):
        """Encuentra el ConstructorDecl de `nombre_clase` que coincide con.

        `argumentos` (valores YA evaluados) -- Etapa 10, sobrecarga de
        constructores. Mismo mecanismo que `_buscar_metodo_ast`, pero los
        constructores NUNCA se heredan (cada clase tiene los suyos propios;
        `padre(...)` ya llama explícitamente al del padre). Retorna el nodo
        AST, o None si la clase no declara ningún constructor (implícito).
        """
        clase_nodo = self.clases_ast.get(nombre_clase)
        if clase_nodo is None or not clase_nodo.constructores:
            return None
        tipos_args = [self._tipo_runtime(a) for a in argumentos]
        info_elegida = self.tabla.resolver_constructor(nombre_clase, tipos_args)
        if info_elegida is None:
            # No debería pasar si type_checker.py ya validó el programa;
            # por robustez, cae a la primera sobrecarga declarada.
            info_elegida = self.tabla.resolver_constructor(nombre_clase)
        if info_elegida is None:
            return None
        for ctor in clase_nodo.constructores:
            if [self._tipo_parametro_ast(p) for p in ctor.parametros] == info_elegida.params_tipos:
                return ctor
        return clase_nodo.constructores[0]

    def _ejecutar_constructor(self, instancia, nombre_clase, argumentos, nodo):
        """Ejecuta el constructor de `nombre_clase` sobre `instancia`.

        Si no hay `padre(...)` explícito como primera instrucción (o no hay
        constructor declarado en absoluto), se invoca implícitamente el
        constructor sin argumentos del padre, si lo hay (§5 de la spec).
        """
        clase_nodo = self.clases_ast.get(nombre_clase)
        info = self.tabla.clases.get(nombre_clase)
        if clase_nodo is None or info is None:
            return

        constructor = self._buscar_constructor_ast(nombre_clase, argumentos)
        if constructor is None:
            if info.padre:
                self._ejecutar_constructor(instancia, info.padre, [], nodo)
            return

        self._comprobar_cancelacion()
        self._profundidad_llamadas += 1
        if self._profundidad_llamadas > self.MAX_RECURSION:
            self._profundidad_llamadas -= 1
            raise RuntimeError_(
                "IL-EJE-040",
                "Desbordamiento de pila de llamadas (recursión demasiado profunda)",
                getattr(nodo, "linea", 0),
                getattr(nodo, "columna", 0),
            )
        self._entrar_marco()
        self._pila_instancias.append(instancia)
        self._pila_clase_definicion.append(nombre_clase)
        self._pila_subrutinas.append(f"{nombre_clase}.{nombre_clase}")
        try:
            for param, arg in zip(constructor.parametros, argumentos, strict=True):
                self.tipos_variables[param.nombre] = param.tipo
                self._declarar_variable(param.nombre, arg)

            elementos = constructor.bloque.elementos
            if elementos and isinstance(elementos[0], SuperCallStmt):
                args_padre = [self._evaluar_expresion(a) for a in elementos[0].argumentos]
                if info.padre:
                    self._ejecutar_constructor(instancia, info.padre, args_padre, elementos[0])
                resto = elementos[1:]
            else:
                if info.padre:
                    self._ejecutar_constructor(instancia, info.padre, [], nodo)
                resto = elementos

            try:
                for elem in resto:
                    self._ejecutar_elemento(elem)
            except ReturnException:
                pass  # el constructor no retorna valor
        finally:
            if self._pila_subrutinas:
                self._pila_subrutinas.pop()
            self._pila_clase_definicion.pop()
            self._pila_instancias.pop()
            self._salir_marco()
            self._profundidad_llamadas -= 1

    def _invocar_metodo_desde(
        self, instancia, nombre_clase_inicio, nombre_metodo, argumentos, nodo
    ):
        resultado = self._buscar_metodo_ast(nombre_clase_inicio, nombre_metodo, argumentos)
        if resultado is None:
            raise RuntimeError_(
                "IL-SEM-003",
                f'Método no encontrado: "{nombre_metodo}"',
                getattr(nodo, "linea", 0),
                getattr(nodo, "columna", 0),
            )
        clase_declarante, metodo_nodo = resultado
        return self._ejecutar_metodo(instancia, clase_declarante, metodo_nodo, argumentos, nodo)

    def _ejecutar_metodo(self, instancia, clase_declarante, nodo_metodo, argumentos, nodo_llamada):
        self._comprobar_cancelacion()
        self._profundidad_llamadas += 1
        if self._profundidad_llamadas > self.MAX_RECURSION:
            self._profundidad_llamadas -= 1
            raise RuntimeError_(
                "IL-EJE-040",
                "Desbordamiento de pila de llamadas (recursión demasiado profunda)",
                nodo_metodo.linea,
                nodo_metodo.columna,
            )
        self._entrar_marco()
        self._pila_instancias.append(instancia)
        self._pila_clase_definicion.append(clase_declarante)
        self._pila_subrutinas.append(f"{instancia.clase}.{nodo_metodo.nombre}")
        try:
            for param, arg in zip(nodo_metodo.parametros, argumentos, strict=True):
                self.tipos_variables[param.nombre] = param.tipo
                self._declarar_variable(param.nombre, arg)

            try:
                for elem in nodo_metodo.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except ReturnException as e:
                valor = e.valor
                if (
                    nodo_metodo.tipo_retorno == "float"
                    and isinstance(valor, int)
                    and not isinstance(valor, bool)
                ):
                    valor = float(valor)
                return valor
            return None
        finally:
            if self._pila_subrutinas:
                self._pila_subrutinas.pop()
            self._pila_clase_definicion.pop()
            self._pila_instancias.pop()
            self._salir_marco()
            self._profundidad_llamadas -= 1

    # Nombres de método reconocidos para personalizar imprimir(objeto)
    # (Etapa 10): español primero, alias en inglés -- mismo criterio
    # bilingüe que el resto del lenguaje. Debe ser público, sin parámetros
    # y retornar texto/string; si no, no cuenta (evita que un método no
    # relacionado con el mismo nombre pero otra firma dispare esto por
    # accidente).
    _NOMBRES_A_TEXTO = ("aTexto", "toString")

    def _metodo_a_texto(self, nombre_clase):
        """Busca, en `nombre_clase` y su cadena de ancestros, un método.

        público `aTexto()`/`toString()` sin parámetros que retorne texto
        (Etapa 10). Retorna el nombre encontrado (para invocarlo) o None.
        """
        for nombre in self._NOMBRES_A_TEXTO:
            todos = self.tabla.resolver_metodo_todos(nombre_clase, nombre)
            if todos is None:
                continue
            _, candidatos = todos
            for info in candidatos:
                if (
                    info.visibilidad == "publico"
                    and info.tipo == "string"
                    and not info.params_tipos
                ):
                    return nombre
        return None

    # Nombres de método reconocidos para personalizar == entre objetos
    # (Etapa 11): mismo criterio bilingüe que _NOMBRES_A_TEXTO. Debe ser
    # público, tomar exactamente 1 parámetro (el otro objeto a comparar) y
    # retornar bool; si no, no cuenta.
    _NOMBRES_IGUAL = ("esIgual", "equals")

    def _metodo_igual(self, nombre_clase):
        """Busca, en `nombre_clase` y su cadena de ancestros, un método.

        público `esIgual(x)`/`equals(x)` de 1 parámetro que retorne bool
        (Etapa 11). Retorna el nombre encontrado, o None -- en cuyo caso
        `==`/`!=` siguen siendo identidad de referencia, como siempre.
        """
        for nombre in self._NOMBRES_IGUAL:
            todos = self.tabla.resolver_metodo_todos(nombre_clase, nombre)
            if todos is None:
                continue
            _, candidatos = todos
            for info in candidatos:
                if (
                    info.visibilidad == "publico"
                    and info.tipo == "bool"
                    and len(info.params_tipos) == 1
                ):
                    return nombre
        return None

    def _formatear_objeto(self, instancia):
        """Si la clase (o un ancestro) declara públicamente `aTexto()`/.

        `toString()` (Etapa 10), se usa esa representación personalizada.
        Si no, el formato automático de siempre:
        `NombreClase(campo1=valor1, campo2=valor2, ...)`, en orden de
        declaración del ancestro al descendiente (§4 de la spec de POO).
        """
        nombre_metodo = self._metodo_a_texto(instancia.clase)
        if nombre_metodo is not None:
            resultado = self._invocar_metodo_desde(
                instancia, instancia.clase, nombre_metodo, [], None
            )
            return resultado if isinstance(resultado, str) else str(resultado)
        cadena = self.tabla.cadena_ancestros(instancia.clase) or [instancia.clase]
        pares = []
        for clase in reversed(cadena):
            clase_nodo = self.clases_ast.get(clase)
            if clase_nodo is None:
                continue
            for attr in clase_nodo.atributos:
                valor = instancia.campos.get(attr.nombre)
                pares.append(f"{attr.nombre}={self._repr_valor_campo(valor)}")
        return f"{instancia.clase}(" + ", ".join(pares) + ")"

    def _repr_valor_campo(self, valor):
        if isinstance(valor, bool):
            return "true" if valor else "false"
        if isinstance(valor, str):
            return f'"{valor}"'
        if valor is None:
            return "void"
        if isinstance(valor, InstanciaObjeto):
            return self._formatear_objeto(valor)
        return str(valor)

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
        elif isinstance(nodo, ForEachStmt):
            self._ejecutar_foreach(nodo)
        elif isinstance(nodo, DoWhileStmt):
            self._ejecutar_do_while(nodo)
        elif isinstance(nodo, SwitchStmt):
            self._ejecutar_switch(nodo)
        elif isinstance(nodo, MatchStmt):
            self._ejecutar_match(nodo)
        elif isinstance(nodo, TryStmt):
            self._ejecutar_try(nodo)
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
        elif isinstance(nodo, MethodCallStmt):
            instancia, clase_inicio = self._resolver_receptor(nodo.receptor)
            receptor_invalido = (
                not isinstance(instancia, (InstanciaObjeto, _AccesoEstatico))
                or clase_inicio is None
            )
            if nodo.es_seguro and receptor_invalido:
                # Acceso seguro (Etapa 12.2): objeto?.metodo(); no hace
                # nada si objeto es nulo (mismo cortocircuito que la forma
                # expresion, ver MethodCallExpr en _evaluar_expresion).
                pass
            else:
                args = [self._evaluar_expresion(a) for a in nodo.argumentos]
                if receptor_invalido:
                    raise RuntimeError_(
                        "IL-EJE-010",
                        "Llamada a método sobre una referencia nula o no inicializada",
                        nodo.linea,
                        nodo.columna,
                    )
                self._invocar_metodo_desde(instancia, clase_inicio, nodo.nombre_metodo, args, nodo)
        elif isinstance(nodo, SuperCallStmt):
            # Solo se llega aquí si NO es la primera instrucción de un
            # constructor (ese caso ya lo consume _ejecutar_constructor);
            # semantic.py ya lo marca como error (IL-POO-009), así que este
            # camino solo se ejecuta si se ignoraron errores de compilación.
            for a in nodo.argumentos:
                self._evaluar_expresion(a)

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
        if operador == "=":
            return valor
        if actual is None:
            raise RuntimeError_(
                "IL-EJE-010",
                "Asignación compuesta sobre un destino no inicializado",
                nodo.linea,
                nodo.columna,
            )
        if operador == "+=":
            return actual + valor
        if operador == "-=":
            return actual - valor
        if operador == "*=":
            return actual * valor
        if operador == "/=":
            if valor == 0:
                raise self._error_division_cero(actual, valor, nodo)
            if isinstance(actual, int) and isinstance(valor, int):
                return self._div_entero(actual, valor)
            return actual / valor
        if operador == "%=":
            if valor == 0:
                raise RuntimeError_(
                    "IL-EJE-006", "División por cero en módulo", nodo.linea, nodo.columna
                )
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
                raise RuntimeError_(
                    "IL-EJE-010", f'Arreglo "{nombre}" no inicializado', nodo.linea, nodo.columna
                )
            if idx < 0 or idx >= len(arreglo):
                raise RuntimeError_(
                    "IL-EJE-050",
                    f"Índice {idx} fuera de rango en " f'"{nombre}"',
                    nodo.linea,
                    nodo.columna,
                )
            resultado = self._combinar_compuesto(nodo.operador, arreglo[idx], valor, nodo)
            arreglo[idx] = self._verificar_rango_int(resultado, nodo)

        elif isinstance(nodo.lvalue, MatrixLValue):
            nombre = nodo.lvalue.nombre
            fila = self._evaluar_expresion(nodo.lvalue.fila)
            col = self._evaluar_expresion(nodo.lvalue.columna)
            matriz = self._obtener_valor_variable(nombre)
            if matriz is None:
                raise RuntimeError_(
                    "IL-EJE-010", f'Matriz "{nombre}" no inicializada', nodo.linea, nodo.columna
                )
            if fila < 0 or fila >= len(matriz):
                raise RuntimeError_(
                    "IL-EJE-050", f"Índice de fila {fila} fuera de rango", nodo.linea, nodo.columna
                )
            if col < 0 or col >= len(matriz[fila]):
                raise RuntimeError_(
                    "IL-EJE-050",
                    f"Índice de columna {col} fuera de rango",
                    nodo.linea,
                    nodo.columna,
                )
            resultado = self._combinar_compuesto(nodo.operador, matriz[fila][col], valor, nodo)
            matriz[fila][col] = self._verificar_rango_int(resultado, nodo)

        elif isinstance(nodo.lvalue, MemberLValue):
            instancia, _ = self._resolver_receptor(nodo.lvalue.receptor)
            nombre_campo = nodo.lvalue.nombre_miembro
            if isinstance(instancia, _AccesoEstatico):
                # Etapa 7: NombreClase.miembro estatico -- una sola copia
                # compartida en ClaseInfo.estado_estatico, no por instancia.
                actual = self._leer_campo_estatico(instancia.nombre_clase, nombre_campo, nodo)
                resultado = self._combinar_compuesto(nodo.operador, actual, valor, nodo)
                self._escribir_campo_estatico(
                    instancia.nombre_clase,
                    nombre_campo,
                    self._verificar_rango_int(resultado, nodo),
                    nodo,
                )
            elif isinstance(instancia, InstanciaObjeto):
                if self._es_atributo_estatico(instancia.clase, nombre_campo):
                    # Acceso permisivo a un estático vía instancia (Etapa 7,
                    # ver semantic.py::_resolver_miembro): misma copia
                    # compartida que por NombreClase.miembro.
                    actual = self._leer_campo_estatico(instancia.clase, nombre_campo, nodo)
                    resultado = self._combinar_compuesto(nodo.operador, actual, valor, nodo)
                    self._escribir_campo_estatico(
                        instancia.clase,
                        nombre_campo,
                        self._verificar_rango_int(resultado, nodo),
                        nodo,
                    )
                else:
                    actual = instancia.campos.get(nombre_campo)
                    resultado = self._combinar_compuesto(nodo.operador, actual, valor, nodo)
                    instancia.campos[nombre_campo] = self._verificar_rango_int(resultado, nodo)
            else:
                raise RuntimeError_(
                    "IL-EJE-010",
                    "Asignación a un miembro sobre una referencia nula o no inicializada",
                    nodo.linea,
                    nodo.columna,
                )

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
            raise RuntimeError_(
                "IL-EJE-010", f'Variable "{nodo.nombre}" no inicializada', nodo.linea, nodo.columna
            )

        if nodo.operador == "++":
            self._asignar_variable(nodo.nombre, actual + 1)
        elif nodo.operador == "--":
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
        elif isinstance(valor, InstanciaObjeto):
            s = self._formatear_objeto(valor)
        else:
            s = str(valor)
        self.salida.append(s)
        if self.on_salida is not None:
            self.on_salida(s)

    def _ejecutar_read(self, nodo):
        """Ejecuta read/leer.

        Si hay entrada simulada (CLI args / GUI en modo lote) se consume de
        la cola. En caso contrario se lee de forma bloqueante de la entrada
        estándar (§7.2), o -- si la GUI configuró `leer_interactivo` para su
        terminal integrada (Etapa 9) -- de ese gancho, también bloqueante.
        """
        if self.entrada:
            valor_str = self.entrada.pop(0)
        elif getattr(self, "usar_stdin", True):
            # CLI/consola: lectura bloqueante desde la entrada estándar (§7.2)
            try:
                valor_str = input()
            except EOFError:
                valor_str = ""
        elif self.leer_interactivo is not None:
            valor_str = self.leer_interactivo()
            # Si el consumidor canceló mientras `leer_interactivo` estaba
            # bloqueado (Etapa 9: Detener en la terminal integrada
            # mientras el programa espera una entrada), abortar limpio en
            # vez de tratar la cadena vacía liberada por la cancelación
            # como una entrada real inválida.
            self._comprobar_cancelacion()
        else:
            # GUI en modo lote: sin entrada simulada no se bloquea; se
            # tratará como EOF
            valor_str = ""

        tipo = self.tipos_variables.get(nodo.nombre)
        if tipo is None:
            e_tabla = self.tabla.buscar(nodo.nombre)
            tipo = e_tabla.tipo_dato if e_tabla else None

        if tipo:
            try:
                if tipo == "int":
                    valor = int(valor_str.strip())
                elif tipo == "float":
                    valor = float(valor_str.strip())
                elif tipo == "bool":
                    v = valor_str.strip().lower()
                    if v in ("true", "verdadero", "1"):
                        valor = True
                    elif v in ("false", "falso", "0"):
                        valor = False
                    else:
                        raise ValueError()
                else:
                    valor = valor_str
                self._asignar_variable(nodo.nombre, valor)
            except ValueError as e:
                cod = {"int": "IL-EJE-020", "float": "IL-EJE-021", "bool": "IL-EJE-022"}
                raise RuntimeError_(
                    cod.get(tipo, "IL-EJE-020"),
                    f"Entrada no convertible a " f"{tipo}",
                    nodo.linea,
                    nodo.columna,
                ) from e

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
                "IL-EJE-030",
                "Posible ciclo infinito: se superaron "
                f"{self.max_iteraciones:,} iteraciones sin terminar".replace(",", " "),
                nodo.linea,
                nodo.columna,
            )
        if self.max_segundos and n % 2000 == 0 and self._t_inicio is not None:
            transcurrido = time.monotonic() - self._t_inicio
            if transcurrido > self.max_segundos:
                raise RuntimeError_(
                    "IL-EJE-030",
                    "Posible ciclo infinito: el programa lleva "
                    f"{transcurrido:.1f} s sin "
                    f"terminar",
                    nodo.linea,
                    nodo.columna,
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

    def _ejecutar_do_while(self, nodo):
        """Ejecuta do/hacer ... while/mientras (Etapa 6): el cuerpo corre al.

        menos una vez antes de evaluar la condición por primera vez.
        """
        vueltas = 0
        while True:
            vueltas += 1
            self._guardia_iteraciones(vueltas, nodo)
            self._comprobar_cancelacion()
            try:
                for elem in nodo.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except BreakException:
                break
            except ContinueException:
                pass
            if not self._evaluar_expresion(nodo.condicion):
                break

    def _ejecutar_switch(self, nodo):
        """Ejecuta switch/segun (Etapa 6): salta al primer case cuyo valor.

        coincide y cae al siguiente (fallthrough, semántica C) hasta un
        break o el final. `continue` NO se captura aquí -- debe propagarse
        a un ciclo envolvente, ver IL-SEM-041/semantic.py.
        """
        valor = self._evaluar_expresion(nodo.expr)
        idx_inicio = None
        for i, caso in enumerate(nodo.casos):
            if caso.valor.valor == valor:
                idx_inicio = i
                break
        try:
            if idx_inicio is not None:
                for caso in nodo.casos[idx_inicio:]:
                    for elem in caso.bloque.elementos:
                        self._ejecutar_elemento(elem)
                if nodo.bloque_default is not None:
                    for elem in nodo.bloque_default.elementos:
                        self._ejecutar_elemento(elem)
            elif nodo.bloque_default is not None:
                for elem in nodo.bloque_default.elementos:
                    self._ejecutar_elemento(elem)
        except BreakException:
            pass

    def _ejecutar_match(self, nodo):
        """Ejecuta emparejar/match.

        exactamente como en semantic.py/type_checker.py:
          - Tipo suma con carga: el valor es una InstanciaObjeto real (la
            variante desazucarada, ver semantic.py::_desazucarar_tipos_suma);
            el despacho es instanceof puro, reutilizando es_subtipo_clase
            (Etapa 12.3) -- cero mecanismo de runtime nuevo.
          - Enum puro (Etapa 11.8, sin cambios): el valor es un entero
            (ordinal) desnudo, sin ninguna referencia a su clase -- hace
            falta resolver el tipo DECLARADO de la expresión para saber a
            qué enum pertenece y mapear el ordinal de vuelta a un nombre
            de miembro (ver _tipo_enum_de_expresion).
        """
        valor = self._evaluar_expresion(nodo.expr)
        if isinstance(valor, InstanciaObjeto):
            for caso in nodo.casos:
                if self.tabla.es_subtipo_clase(valor.clase, caso.nombre_variante):
                    info_variante = self.tabla.clases.get(caso.nombre_variante)
                    nombres_campos = (
                        [n for n, a in info_variante.atributos.items() if not a.es_estatico]
                        if info_variante
                        else []
                    )
                    for ligadura, nombre_campo in zip(caso.ligaduras, nombres_campos, strict=True):
                        self._declarar_variable(ligadura, valor.campos.get(nombre_campo))
                    for elem in caso.bloque.elementos:
                        self._ejecutar_elemento(elem)
                    return
            if nodo.caso_comodin is not None:
                for elem in nodo.caso_comodin.elementos:
                    self._ejecutar_elemento(elem)
            return

        nombre_enum = self._tipo_enum_de_expresion(nodo.expr)
        info_enum = self.tabla.clases.get(nombre_enum) if nombre_enum else None
        nombre_miembro = None
        if info_enum is not None:
            for nombre, ordinal in info_enum.estado_estatico.items():
                if ordinal == valor:
                    nombre_miembro = nombre
                    break
        for caso in nodo.casos:
            if caso.nombre_variante == nombre_miembro:
                for elem in caso.bloque.elementos:
                    self._ejecutar_elemento(elem)
                return
        if nodo.caso_comodin is not None:
            for elem in nodo.caso_comodin.elementos:
                self._ejecutar_elemento(elem)

    def _tipo_enum_de_expresion(self, expr):
        """Best-effort: tipo declarado de `expr` para emparejar sobre un.

        enum PURO (Etapa 11.8) -- el único camino donde el valor en tiempo
        de ejecución (un entero ordinal desnudo) no trae consigo su propia
        clase, a diferencia de una instancia de tipo suma. Cubre los casos
        realistas (identificador, acceso a miembro encadenado); una
        expresión más compleja simplemente no resuelve tipo y cae al caso
        comodín/ningún caso -- type_checker.py ya garantizó antes de esto
        que el programa compila, así que en la práctica siempre se resuelve.
        """
        if isinstance(expr, Identifier):
            tipo = self.tipos_variables.get(expr.nombre)
            if tipo is None:
                entrada = self.tabla.buscar(expr.nombre)
                tipo = entrada.tipo_dato if entrada else None
            return tipo
        if isinstance(expr, MemberAccess):
            tipo_receptor = self._tipo_enum_de_expresion(expr.receptor)
            info = self.tabla.clases.get(tipo_receptor) if tipo_receptor else None
            attr = info.atributos.get(expr.nombre_miembro) if info else None
            return attr.tipo if attr else None
        return None

    def _ejecutar_try(self, nodo):
        """Ejecuta try/catch genérico.

        cualquier RuntimeError_ (IL-EJE-*) del bloque try se captura y la
        variable de catch queda ligada a una instancia sintética de la
        clase 'Excepcion' (codigo/mensaje, ver symbol_table.py). Break/
        continue/return del try siguen propagándose -- no son errores.
        """
        try:
            for elem in nodo.bloque_try.elementos:
                self._ejecutar_elemento(elem)
        except RuntimeError_ as e:
            excepcion = InstanciaObjeto("Excepcion")
            excepcion.campos["codigo"] = e.codigo
            excepcion.campos["mensaje"] = e.mensaje
            self._declarar_variable(nodo.nombre_catch, excepcion)
            for elem in nodo.bloque_catch.elementos:
                self._ejecutar_elemento(elem)

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
                        if nodo.act_stmt.operador == "++":
                            self._asignar_variable(nombre, actual + 1)
                        elif nodo.act_stmt.operador == "--":
                            self._asignar_variable(nombre, actual - 1)
                else:
                    self._evaluar_expresion(nodo.act_stmt)

    def _ejecutar_foreach(self, nodo):
        """Ejecuta para_cada/foreach (Etapa 12.1). No es azúcar desarmada.

        en el parser (ver ast_nodes.py::ForEachStmt): se evalúa el arreglo
        una sola vez y se recorre directamente la lista de Python -- igual
        de simple que desazucarar a un while indexado, pero sin necesitar
        una expresión de "longitud de arreglo" que hoy no existe en el
        lenguaje. Sin marco/ámbito propio por iteración, mismo criterio
        que _ejecutar_while/_ejecutar_for (el chequeo estático ya ocurrió
        en semantic.py; en tiempo de ejecución basta con reasignar la
        variable de recorrido en cada vuelta).
        """
        arreglo = self._evaluar_expresion(nodo.arreglo)
        for valor in list(arreglo):
            self._declarar_variable(nodo.nombre, valor)
            try:
                for elem in nodo.bloque.elementos:
                    self._ejecutar_elemento(elem)
            except BreakException:
                break
            except ContinueException:
                continue

    def _ejecutar_return(self, nodo):
        """Ejecuta return."""
        if nodo.expr:
            valor = self._evaluar_expresion(nodo.expr)
            raise ReturnException(valor)
        raise ReturnException(None)

    def _ejecutar_llamada(self, nombre, argumentos, nodo):
        """Ejecuta una llamada a subrutina."""
        if nombre in _NOMBRES_ORDEN_SUPERIOR:
            args_eval = [self._evaluar_expresion(a) for a in argumentos]
            return self._invocar_orden_superior(nombre, args_eval, nodo)

        vf = self._resolver_valor_funcion_variable(nombre)
        if vf is not None:
            # Etapa 12.6: `nombre` es una variable que guarda un closure,
            # no el nombre de una función/procedimiento de nivel superior.
            args_eval = [self._evaluar_expresion(a) for a in argumentos]
            return self._invocar_valor_funcion(vf, args_eval, nodo)

        args_eval = [self._evaluar_expresion(a) for a in argumentos]

        if es_built_in(nombre):
            return self._invocar_built_in(nombre, args_eval, nodo)

        if nombre in self.funciones_ast:
            return self._ejecutar_subrutina(nombre, args_eval, nodo)
        elif nombre in self.procedimientos_ast:
            self._ejecutar_subrutina(nombre, args_eval, nodo)
            return None

        raise RuntimeError_(
            "IL-SEM-003", f'Subrutina no encontrada: "{nombre}"', nodo.linea, nodo.columna
        )

    def _evaluar_expresion(self, nodo):
        """Evalúa una expresión y retorna su valor."""
        if nodo is None:
            return None

        if isinstance(nodo, Literal):
            return nodo.valor

        if isinstance(nodo, Identifier):
            # Etapa 12.6: un IDENTIFICADOR bare que no es NINGUNA variable
            # DECLARADA (ni siquiera sin inicializar -- `tipos_variables`
            # registra toda variable/parámetro declarado, tenga o no ya un
            # valor, a diferencia de `_existe_en_marco`, que un intento
            # anterior usó aquí por error: `int x;` sin inicializar SÍ
            # crea una entrada de marco con valor None, así que
            # `_existe_en_marco` no distingue "declarada sin inicializar"
            # de "no es una variable" -- pero SÍ nombra una función o
            # procedimiento de nivel superior es una referencia a un
            # valor-función (pasar la subrutina "por nombre", ej.
            # `operar = sumar;`). Una variable siempre gana sobre una
            # función del mismo nombre (sombra normal, ya lo impediría
            # semantic.py de todas formas -- los nombres de función están
            # en el mismo espacio que las variables).
            if nodo.nombre not in self.tipos_variables and (
                nodo.nombre in self.funciones_ast or nodo.nombre in self.procedimientos_ast
            ):
                return ValorFuncion(nombre_subrutina=nodo.nombre)
            valor = self._obtener_valor_variable(nodo.nombre)
            if valor is None and not self._es_tipo_clase_de_variable(nodo.nombre):
                # Para un tipo de clase, None ES un valor legitimo (nulo/null,
                # Estructuras de Datos) -- no una variable sin inicializar.
                # Solo los primitivos exigen asignacion antes de leerse.
                raise RuntimeError_(
                    "IL-EJE-010",
                    f'Variable "{nodo.nombre}" no inicializada',
                    nodo.linea,
                    nodo.columna,
                )
            return valor

        if isinstance(nodo, ArrayAccess):
            arreglo = self._obtener_valor_variable(nodo.nombre)
            if arreglo is None:
                raise RuntimeError_(
                    "IL-EJE-010",
                    f'Arreglo "{nodo.nombre}" no inicializado',
                    nodo.linea,
                    nodo.columna,
                )
            idx = self._evaluar_expresion(nodo.indice)
            if idx < 0 or idx >= len(arreglo):
                raise RuntimeError_(
                    "IL-EJE-050",
                    f"Índice {idx} fuera de rango en " f'"{nodo.nombre}"',
                    nodo.linea,
                    nodo.columna,
                )
            return arreglo[idx]

        if isinstance(nodo, MatrixAccess):
            matriz = self._obtener_valor_variable(nodo.nombre)
            if matriz is None:
                raise RuntimeError_(
                    "IL-EJE-010",
                    f'Matriz "{nodo.nombre}" no inicializada',
                    nodo.linea,
                    nodo.columna,
                )
            fila = self._evaluar_expresion(nodo.fila)
            col = self._evaluar_expresion(nodo.columna)
            if fila < 0 or fila >= len(matriz):
                raise RuntimeError_(
                    "IL-EJE-050", f"Fila {fila} fuera de rango", nodo.linea, nodo.columna
                )
            if col < 0 or col >= len(matriz[fila]):
                raise RuntimeError_(
                    "IL-EJE-050", f"Columna {col} fuera de rango", nodo.linea, nodo.columna
                )
            return matriz[fila][col]

        if isinstance(nodo, FunctionCall):
            if nodo.nombre in _NOMBRES_ORDEN_SUPERIOR:
                args = [self._evaluar_expresion(a) for a in nodo.argumentos]
                return self._invocar_orden_superior(nodo.nombre, args, nodo)
            vf = self._resolver_valor_funcion_variable(nodo.nombre)
            if vf is not None:
                args = [self._evaluar_expresion(a) for a in nodo.argumentos]
                return self._invocar_valor_funcion(vf, args, nodo)
            args = [self._evaluar_expresion(a) for a in nodo.argumentos]
            return self._ejecutar_subrutina(nodo.nombre, args, nodo)

        if isinstance(nodo, LambdaExpr):
            # Captura por referencia (Etapa 12.6): `list(...)` copia la
            # LISTA (para que push/pop posteriores sobre self.pila_marcos
            # no afecten a este closure), pero cada elemento sigue siendo
            # el MISMO diccionario de marco -- así una variable capturada
            # que cambia después de crear el lambda se sigue viendo
            # actualizada la próxima vez que se invoque.
            return ValorFuncion(lambda_nodo=nodo, marcos_capturados=list(self.pila_marcos))

        if isinstance(nodo, ThisExpr):
            return self._instancia_actual()

        if isinstance(nodo, NullExpr):
            return None

        if isinstance(nodo, NewExpr):
            args = [self._evaluar_expresion(a) for a in nodo.argumentos]
            return self._crear_instancia(nodo.nombre_clase, args, nodo)

        if isinstance(nodo, MemberAccess):
            instancia, _ = self._resolver_receptor(nodo.receptor)
            if isinstance(instancia, _AccesoEstatico):
                return self._leer_campo_estatico(instancia.nombre_clase, nodo.nombre_miembro, nodo)
            if not isinstance(instancia, InstanciaObjeto):
                # Acceso seguro (Etapa 12.2): "?." produce nulo en vez de
                # lanzar IL-EJE-010 cuando el receptor es nulo/no
                # inicializado -- mismo criterio de "nulo o no
                # inicializado" que ya trataba igual el mensaje de error.
                if nodo.es_seguro:
                    return None
                raise RuntimeError_(
                    "IL-EJE-010",
                    "Acceso a miembro sobre una referencia nula o no inicializada",
                    nodo.linea,
                    nodo.columna,
                )
            if self._es_atributo_estatico(instancia.clase, nodo.nombre_miembro):
                return self._leer_campo_estatico(instancia.clase, nodo.nombre_miembro, nodo)
            if nodo.nombre_miembro not in instancia.campos:
                raise RuntimeError_(
                    "IL-SEM-003",
                    f"Atributo no encontrado: " f'"{nodo.nombre_miembro}"',
                    nodo.linea,
                    nodo.columna,
                )
            return instancia.campos[nodo.nombre_miembro]

        if isinstance(nodo, MethodCallExpr):
            instancia, clase_inicio = self._resolver_receptor(nodo.receptor)
            receptor_invalido = (
                not isinstance(instancia, (InstanciaObjeto, _AccesoEstatico))
                or clase_inicio is None
            )
            if nodo.es_seguro and receptor_invalido:
                # Acceso seguro (Etapa 12.2): los argumentos NO se evalúan
                # si el receptor es nulo (cortocircuito, mismo criterio que
                # cualquier lenguaje con "?." -- no tiene sentido evaluar
                # argumentos de una llamada que no va a ocurrir).
                return None
            args = [self._evaluar_expresion(a) for a in nodo.argumentos]
            if receptor_invalido:
                raise RuntimeError_(
                    "IL-EJE-010",
                    "Llamada a método sobre una referencia nula o no inicializada",
                    nodo.linea,
                    nodo.columna,
                )
            return self._invocar_metodo_desde(
                instancia, clase_inicio, nodo.nombre_metodo, args, nodo
            )

        if isinstance(nodo, BinaryOp):
            # Cortocircuito garantizado por §6.3.1: el operando derecho NO se
            # evalua cuando el izquierdo ya determina el resultado. Debe
            # resolverse aqui, antes de evaluar la derecha.
            if nodo.operador == "&&":
                if self._evaluar_expresion(nodo.izquierda) is not True:
                    return False
                return self._evaluar_expresion(nodo.derecha)
            if nodo.operador == "||":
                if self._evaluar_expresion(nodo.izquierda) is True:
                    return True
                return self._evaluar_expresion(nodo.derecha)
            if nodo.operador == "??":
                # Coalescencia nula (Etapa 12.2): la derecha NO se evalua
                # si la izquierda no es nula (mismo cortocircuito que
                # &&/||, mismo criterio de "no evaluar lo que no hace
                # falta").
                izq = self._evaluar_expresion(nodo.izquierda)
                if izq is not None:
                    return izq
                return self._evaluar_expresion(nodo.derecha)
            left = self._evaluar_expresion(nodo.izquierda)
            right = self._evaluar_expresion(nodo.derecha)
            return self._aplicar_binario(nodo.operador, left, right, nodo)

        if isinstance(nodo, UnaryOp):
            # ++ / -- en expresion modifican la variable (§5.3.3). El operando
            # es siempre un lvalue simple, garantizado por la gramatica.
            if nodo.operador in ("++", "--"):
                return self._aplicar_inc_dec_expr(nodo)
            oper = self._evaluar_expresion(nodo.operando)
            return self._aplicar_unario(nodo.operador, oper, nodo.es_prefijo, nodo)

        if isinstance(nodo, TernaryExpr):
            # Etapa 6: solo se evalua la rama elegida (igual que &&/||, nunca
            # se evalua la rama descartada -- importante si tiene efectos
            # secundarios o dividiria por cero).
            cond = self._evaluar_expresion(nodo.condicion)
            rama = nodo.si_verdadero if cond else nodo.si_falso
            return self._evaluar_expresion(rama)

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
            delta = 1 if nodo.operador == "++" else -1
            return valor + delta if nodo.es_prefijo else valor

        nombre = destino.nombre
        actual = self._obtener_valor_variable(nombre)
        if actual is None:
            raise RuntimeError_(
                "IL-EJE-010", f'Variable "{nombre}" no inicializada', nodo.linea, nodo.columna
            )
        nuevo = actual + 1 if nodo.operador == "++" else actual - 1
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
                "IL-EJE-001",
                f"Desbordamiento de entero: "
                f"{valor} excede el rango "
                f"[{self.INT_MIN}, {self.INT_MAX}]",
                getattr(nodo, "linea", 0),
                getattr(nodo, "columna", 0),
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
                "IL-EJE-002",
                "Operación de punto flotante inválida: división entre 0.0",
                nodo.linea,
                nodo.columna,
            )
        return RuntimeError_("IL-EJE-006", "División por cero", nodo.linea, nodo.columna)

    def _div_entero(self, a, b):
        """División entera con truncamiento hacia cero (§4.2.2).

        Ej: 7/2=3 y -7/2=-3 (a diferencia del operador // de Python que
        redondea hacia -infinito).
        """
        q = abs(a) // abs(b)
        return -q if (a < 0) != (b < 0) else q

    def _mod_entero(self, a, b):
        """Módulo entero con el signo del dividendo (estilo C), consistente.

        con la división que trunca hacia cero.
        """
        r = abs(a) % abs(b)
        return -r if a < 0 else r

    def _aplicar_binario(self, op, left, right, nodo):
        """Aplica un operador binario."""
        if op == "||":
            return left or right
        if op == "&&":
            return left and right
        if op in ("==", "!="):
            # Etapa 11: si AMBOS operandos son objetos (no cuenta comparar
            # contra nulo -- "objeto == nulo" debe seguir siendo el chequeo
            # de nulidad de siempre, sin invocar código de usuario) y la
            # clase del izquierdo (o un ancestro) declara públicamente
            # esIgual()/equals() de 1 parámetro que retorna bool, se usa
            # esa comparación personalizada en vez de identidad de
            # referencia (mismo patrón que aTexto()/toString() para
            # imprimir(objeto)). Si no existe tal método, == sigue siendo
            # identidad de referencia, exactamente como antes.
            if isinstance(left, InstanciaObjeto) and isinstance(right, InstanciaObjeto):
                nombre_metodo = self._metodo_igual(left.clase)
                if nombre_metodo is not None:
                    resultado = bool(
                        self._invocar_metodo_desde(left, left.clase, nombre_metodo, [right], nodo)
                    )
                    return resultado if op == "==" else not resultado
            return left == right if op == "==" else left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        if op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            return self._verificar_rango_int(left + right, nodo)
        if op == "-":
            return self._verificar_rango_int(left - right, nodo)
        if op == "*":
            return self._verificar_rango_int(left * right, nodo)
        if op == "/":
            if right == 0:
                raise self._error_division_cero(left, right, nodo)
            if isinstance(left, int) and isinstance(right, int):
                return self._div_entero(left, right)  # Trunca hacia cero (§4.2.2)
            return left / right
        if op == "%":
            if right == 0:
                raise RuntimeError_(
                    "IL-EJE-006", "División por cero en módulo", nodo.linea, nodo.columna
                )
            if isinstance(left, int) and isinstance(right, int):
                return self._mod_entero(left, right)
            return left % right
        # Bit a bit (Etapa 11): solo enteros (ya validado por
        # type_checker.py). Se pasa por _verificar_rango_int igual que +/-/*
        # -- un desplazamiento grande puede salirse de los 32 bits de int
        # (§4.1) tanto como una suma.
        if op == "&":
            return self._verificar_rango_int(left & right, nodo)
        if op == "|":
            return self._verificar_rango_int(left | right, nodo)
        if op == "^":
            return self._verificar_rango_int(left ^ right, nodo)
        if op == "<<":
            if right < 0:
                raise RuntimeError_(
                    "IL-EJE-001", "Desplazamiento con exponente negativo", nodo.linea, nodo.columna
                )
            return self._verificar_rango_int(left << right, nodo)
        if op == ">>":
            if right < 0:
                raise RuntimeError_(
                    "IL-EJE-001", "Desplazamiento con exponente negativo", nodo.linea, nodo.columna
                )
            return left >> right
        raise RuntimeError_("IL-EJE-001", f"Operador desconocido: {op}", nodo.linea, nodo.columna)

    def _aplicar_unario(self, op, oper, es_prefijo, nodo):
        """Aplica un operador unario."""
        if op == "-":
            return -oper
        if op == "!":
            return not oper
        if op == "~":
            # Negación de bits (Etapa 11): complemento a uno (~x = -x-1).
            # Para cualquier int valido de 32 bits el resultado tambien
            # cae dentro del rango (nunca desborda), pero se pasa por
            # _verificar_rango_int por consistencia con el resto de las
            # operaciones aritmeticas/bit a bit.
            return self._verificar_rango_int(~oper, nodo)
        if op == "++":
            # En expresiones, el valor retornado depende de si es prefijo o postfijo
            # Para simplificar: retornamos el valor y el efecto se aplica en la instrucción
            if es_prefijo:
                return oper + 1
            return oper  # Postfijo retorna el valor original
        if op == "--":
            if es_prefijo:
                return oper - 1
            return oper
        return oper
