# Módulo de Verificación de Tipos de InvenioLang 1.0
# Implementa el sistema de tipos de la Sección 4 y las reglas de la Sección 14
# Verifica compatibilidad de tipos en todas las operaciones

from .ast_nodes import *
from .symbol_table import TipoSimbolo
from .builtins import es_built_in

# Orden superior sobre arreglos (Etapa 12.7): tipo de retorno fijo de cada
# nombre reconocido -- ver semantic.py::_ORDEN_SUPERIOR para el porqué del
# diseño (monomórfico sobre entero, mapear/filtrar escriben en un arreglo
# de salida en vez de retornar uno nuevo). 'mapear'/'map' no aparecen aquí
# a propósito: son void, se llaman como CallStmt, nunca como expresión.
_ORDEN_SUPERIOR_TIPO = {'reducir': 'int', 'reduce': 'int', 'filtrar': 'int', 'filter': 'int'}


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
        # POO (InvenioLang 2.0): clase cuyo metodo/constructor se verifica
        # actualmente, para resolver el tipo de este/this y padre/super.
        self.clase_actual = None
        # Auditoria (Etapa 12.6): tipo de retorno declarado de la función/
        # procedimiento/método/lambda cuyo cuerpo se verifica actualmente,
        # o None dentro de un constructor/procedimiento/main (sin `return`
        # con valor posible). Usado para IL-TIPO-001 en `return` -- hueco
        # real encontrado al implementar el tipo de retorno de un lambda:
        # NINGUNA forma de subrutina (ni siquiera una función de nivel
        # superior normal, ver auditoría) validaba el tipo de su propio
        # `return` contra su tipo de retorno declarado antes de esto.
        self.tipo_retorno_actual = None

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
        self._validar_sobrescrituras(nodo.clases)
        for c in nodo.clases:
            self._visitar_clase(c)
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
            # BUG encontrado en auditoría (Etapa 12.1): a diferencia de
            # FunctionDecl, este caso NUNCA volvía a declarar los
            # parámetros del procedimiento en el ámbito del type checker
            # antes de visitar su cuerpo -- cualquier chequeo de tipos que
            # necesitara resolver uno de los PROPIOS parámetros del
            # procedimiento (tabla.buscar(...) -> None) se saltaba en
            # silencio (todo el código de este archivo hace `if tipo and
            # ... ` antes de comparar, así que un tipo no encontrado nunca
            # se reportaba como error). Mismo tratamiento que
            # `_visitar_funcion` ahora.
            self.tabla.entrar_ambito()
            for p in nodo.parametros:
                self._declarar_parametro_tc(p)
            tipo_previo = self.tipo_retorno_actual
            self.tipo_retorno_actual = 'void'
            self._visitar_bloque(nodo.bloque)
            self.tipo_retorno_actual = tipo_previo
            self.tabla.salir_ambito()

    def _visitar_funcion(self, nodo):
        """Visita una función verificando tipos."""
        self.tabla.entrar_ambito()
        for p in nodo.parametros:
            self._declarar_parametro_tc(p)
        tipo_previo = self.tipo_retorno_actual
        self.tipo_retorno_actual = nodo.tipo_retorno
        self._visitar_bloque(nodo.bloque)
        self.tipo_retorno_actual = tipo_previo
        self.tabla.salir_ambito()

    # ============================================================
    # POO (InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md)
    # ============================================================

    def _declarar_parametro_tc(self, p):
        """Re-declara un parametro en el ambito del type checker (mismo
        patron que ya usa `_visitar_funcion` para funciones normales)."""
        ts = TipoSimbolo.PARAMETRO
        if p.es_matriz:
            ts = TipoSimbolo.PARAM_MATRIZ
        elif p.es_arreglo:
            ts = TipoSimbolo.PARAM_ARREGLO
        entrada = self.tabla.declarar(p.nombre, ts, p.tipo, p.linea, p.columna)
        if entrada:
            entrada.inicializado = True

    def _visitar_clase(self, nodo):
        """Visita los constructores y los metodos de una clase, verificando
        tipos en sus cuerpos (mismo patron que `_visitar_funcion`). Etapa
        10: una clase puede declarar varios constructores (sobrecarga)."""
        self.clase_actual = nodo.nombre
        for ctor in nodo.constructores:
            self.tabla.entrar_ambito()
            for p in ctor.parametros:
                self._declarar_parametro_tc(p)
            tipo_previo = self.tipo_retorno_actual
            self.tipo_retorno_actual = 'void'  # un constructor nunca retorna valor
            self._visitar_bloque(ctor.bloque)
            self.tipo_retorno_actual = tipo_previo
            self.tabla.salir_ambito()
        for met in nodo.metodos:
            self.tabla.entrar_ambito()
            for p in met.parametros:
                self._declarar_parametro_tc(p)
            tipo_previo = self.tipo_retorno_actual
            self.tipo_retorno_actual = met.tipo_retorno
            self._visitar_bloque(met.bloque)
            self.tipo_retorno_actual = tipo_previo
            self.tabla.salir_ambito()
        self.clase_actual = None

    def _validar_sobrescrituras(self, clases):
        """IL-POO-014/015: un metodo que sobrescribe uno heredado debe
        conservar el mismo tipo de retorno y los mismos tipos de
        parametros. Con sobrecarga (Etapa 7) hay que revisar cada
        sobrecarga por separado: una firma que EXISTE (exacta o
        compatible) en el padre es una sobrescritura y debe conservar el
        tipo de retorno; una firma que no coincide con ninguna del padre es
        simplemente una sobrecarga nueva, no una sobrescritura."""
        for c in clases:
            info = self.tabla.clases.get(c.nombre)
            if info is None or info.padre is None:
                continue
            for nombre_met, sobrecargas in info.metodos.items():
                for met_info in sobrecargas:
                    self._validar_sobrescritura_una(c.nombre, info.padre, nombre_met, met_info)

    def _validar_sobrescritura_una(self, nombre_clase, nombre_padre, nombre_met, met_info):
        resultado = self.tabla.resolver_metodo(nombre_padre, nombre_met, met_info.params_tipos)
        if resultado is None:
            return  # no sobrescribe nada: metodo (o sobrecarga) nuevo
        clase_padre, padre_met = resultado
        if met_info.tipo != padre_met.tipo:
            self.error_manager.error_poo(
                'IL-POO-014',
                f'"{nombre_clase}.{nombre_met}" sobrescribe el método de '
                f'"{clase_padre}" con tipo de retorno {met_info.tipo}, '
                f'pero el padre lo declara {padre_met.tipo}',
                met_info.linea, met_info.columna
            )
        elif met_info.params_tipos != padre_met.params_tipos:
            self.error_manager.error_poo(
                'IL-POO-015',
                f'"{nombre_clase}.{nombre_met}" sobrescribe el método de '
                f'"{clase_padre}" con parámetros {met_info.params_tipos}, '
                f'pero el padre declara {padre_met.params_tipos}',
                met_info.linea, met_info.columna
            )

    def _tipo_receptor(self, receptor):
        """Tipo estático (nombre de clase) del receptor de un acceso a
        miembro, o None si no se puede resolver. No re-reporta errores de
        existencia/contexto: semantic.py ya los emitió (IL-SEM-003,
        IL-POO-006/011/012); aquí solo interesa el tipo para seguir
        verificando, en silencio si algo ya estaba roto."""
        if isinstance(receptor, ThisExpr):
            return self.clase_actual
        if isinstance(receptor, SuperExpr):
            if self.clase_actual is None:
                return None
            info = self.tabla.clases.get(self.clase_actual)
            return info.padre if info else None
        if isinstance(receptor, Identifier):
            entrada = self.tabla.buscar(receptor.nombre)
            if entrada is None:
                return None
            return entrada.tipo_dato if self.tabla.es_clase(entrada.tipo_dato) else None
        if isinstance(receptor, ArrayAccess):
            # Elemento de arreglo de objetos: reutiliza _obtener_tipo para
            # heredar la verificacion de tipo/rango de indice ya existente.
            self._obtener_tipo(receptor)
            entrada = self.tabla.buscar(receptor.nombre)
            if entrada is None:
                return None
            return entrada.tipo_dato if self.tabla.es_clase(entrada.tipo_dato) else None
        return None

    def _verificar_args(self, nombre, argumentos, tipos_esperados, nodo, codigo_error):
        """Verifica la compatibilidad de tipo de cada argumento emparejado
        con su parámetro esperado (la aridad ya la valida semantic.py)."""
        for i, (arg, tipo_esp) in enumerate(zip(argumentos, tipos_esperados)):
            tipo_arg = self._obtener_tipo(arg)
            if tipo_arg and not self._compatible(tipo_esp, tipo_arg):
                self.error_manager.error_poo(
                    codigo_error,
                    f'Tipo incompatible en argumento {i + 1} de "{nombre}": '
                    f'se esperaba {tipo_esp}, se encontró {tipo_arg}',
                    arg.linea if hasattr(arg, 'linea') else nodo.linea,
                    arg.columna if hasattr(arg, 'columna') else nodo.columna
                )
        for arg in argumentos[len(tipos_esperados):]:
            self._obtener_tipo(arg)

    def _verificar_visibilidad_constructor(self, nombre_clase, info_ctor, nodo):
        """IL-POO-030 (Etapa 11): un constructor privado solo puede
        invocarse desde DENTRO de la misma clase (p.ej. un metodo/
        constructor estatico de fabrica, patron Singleton) -- ni desde
        afuera, ni siquiera desde una subclase via padre(...) (mismo
        criterio que un constructor privado en Java/C#: no se hereda el
        acceso). No se distingue "misma clase por padre(...)" de "misma
        clase por nuevo directo": ambos exigen `clase_actual == nombre_clase`."""
        if info_ctor.visibilidad == 'privado' and self.clase_actual != nombre_clase:
            self.error_manager.error_poo(
                'IL-POO-030',
                f'El constructor de "{nombre_clase}" es privado: solo se '
                f'puede invocar desde dentro de la propia clase',
                nodo.linea, nodo.columna
            )

    def _verificar_llamada_constructor(self, nombre_clase, argumentos, nodo):
        """Etapa 10 (sobrecarga de constructores): mismo patrón que
        `_tipo_llamada_metodo` -- con 0 o 1 constructor declarado, se
        comporta EXACTO que antes (IL-POO-008 por argumento). Con varias
        sobrecargas, recién ahí hace falta el tipo de cada argumento para
        elegir cuál -- IL-POO-029 si ninguna coincide. Etapa 11: además
        valida visibilidad (IL-POO-030) sobre el constructor finalmente
        resuelto."""
        if not self.tabla.es_clase(nombre_clase):
            for a in argumentos:
                self._obtener_tipo(a)
            return
        candidatos = self.tabla.resolver_constructor_todos(nombre_clase)
        if len(candidatos) <= 1:
            tipos_esperados = candidatos[0].params_tipos if candidatos else []
            self._verificar_args(f'nuevo {nombre_clase}', argumentos, tipos_esperados,
                                 nodo, 'IL-POO-008')
            if candidatos:
                self._verificar_visibilidad_constructor(nombre_clase, candidatos[0], nodo)
            return

        tipos_args = [self._obtener_tipo(a) for a in argumentos]
        if any(t is None for t in tipos_args):
            return  # algún argumento ya tiene un error de tipos propio
        elegido = self.tabla.resolver_constructor(nombre_clase, tipos_args)
        if elegido is None:
            self.error_manager.error_poo(
                'IL-POO-029',
                f'Ninguna sobrecarga del constructor de "{nombre_clase}" '
                f'coincide con los tipos de argumento ({", ".join(tipos_args)})',
                nodo.linea, nodo.columna
            )
            return
        self._verificar_visibilidad_constructor(nombre_clase, elegido, nodo)

    def _tipo_llamada_metodo(self, receptor, nombre_metodo, argumentos, nodo):
        """Etapa 7 (sobrecarga): si `nombre_metodo` tiene una sola firma
        declarada, se comporta EXACTO que antes (IL-POO-018 por argumento,
        sin evaluar los tipos dos veces). Si tiene varias (sobrecarga real),
        recién ahí hace falta el tipo de cada argumento para elegir cuál --
        IL-POO-027 si ninguna coincide."""
        tipo_receptor = self._tipo_receptor(receptor)
        if tipo_receptor is None:
            for a in argumentos:
                self._obtener_tipo(a)
            return None
        todos = self.tabla.resolver_metodo_todos(tipo_receptor, nombre_metodo)
        if todos is None:
            for a in argumentos:
                self._obtener_tipo(a)
            return None  # no existe: ya lo reportó semantic.py (IL-POO-006)
        _, candidatos = todos
        if len(candidatos) == 1:
            info = candidatos[0]
            self._verificar_args(nombre_metodo, argumentos, info.params_tipos,
                                 nodo, 'IL-POO-018')
            return info.tipo

        tipos_args = [self._obtener_tipo(a) for a in argumentos]
        if any(t is None for t in tipos_args):
            return None  # algún argumento ya tiene un error de tipos propio
        resultado = self.tabla.resolver_metodo(tipo_receptor, nombre_metodo, tipos_args)
        if resultado is None:
            self.error_manager.error_poo(
                'IL-POO-027',
                f'Ninguna sobrecarga de "{nombre_metodo}" en "{tipo_receptor}" '
                f'coincide con los tipos de argumento ({", ".join(tipos_args)})',
                nodo.linea, nodo.columna
            )
            return None
        _, info = resultado
        return info.tipo

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
        elif isinstance(nodo, ForEachStmt):
            self._verificar_foreach(nodo)
        elif isinstance(nodo, DoWhileStmt):
            self._visitar_bloque(nodo.bloque)
            self._verificar_condicion(nodo.condicion, nodo.linea, nodo.columna)
        elif isinstance(nodo, SwitchStmt):
            self._verificar_switch(nodo)
        elif isinstance(nodo, MatchStmt):
            self._verificar_match(nodo)
        elif isinstance(nodo, TryStmt):
            self._visitar_bloque(nodo.bloque_try)
            self.tabla.declarar(nodo.nombre_catch, TipoSimbolo.VARIABLE,
                                'Excepcion', nodo.linea, nodo.columna)
            self._visitar_bloque(nodo.bloque_catch)
        elif isinstance(nodo, ReturnStmt):
            if nodo.expr:
                tipo_expr = self._obtener_tipo(nodo.expr)
                if (tipo_expr and self.tipo_retorno_actual
                        and self.tipo_retorno_actual != 'void'
                        and not self._compatible(self.tipo_retorno_actual, tipo_expr)):
                    self.error_manager.error_tipo(
                        'IL-TIPO-001',
                        f'Tipo de retorno incompatible: se esperaba '
                        f'"{self.tipo_retorno_actual}", se encontró "{tipo_expr}"',
                        nodo.linea, nodo.columna
                    )
        elif isinstance(nodo, CallStmt):
            self._verificar_llamada(nodo.nombre, nodo.argumentos, nodo)
        elif isinstance(nodo, FunctionCall):
            self._verificar_llamada(nodo.nombre, nodo.argumentos, nodo)
        elif isinstance(nodo, MethodCallStmt):
            self._tipo_llamada_metodo(nodo.receptor, nodo.nombre_metodo,
                                      nodo.argumentos, nodo)
        elif isinstance(nodo, SuperCallStmt):
            info = self.tabla.clases.get(self.clase_actual) if self.clase_actual else None
            padre_info = self.tabla.clases.get(info.padre) if info and info.padre else None
            if padre_info is not None:
                # Etapa 10 (sobrecarga de constructores): mismo patrón que
                # _verificar_llamada_constructor.
                candidatos = padre_info.constructores
                if len(candidatos) <= 1:
                    tipos_esperados = candidatos[0].params_tipos if candidatos else []
                    self._verificar_args('padre(...)', nodo.argumentos, tipos_esperados,
                                         nodo, 'IL-POO-008')
                    if candidatos:
                        self._verificar_visibilidad_constructor(info.padre, candidatos[0], nodo)
                else:
                    tipos_args = [self._obtener_tipo(a) for a in nodo.argumentos]
                    if not any(t is None for t in tipos_args):
                        elegido = self.tabla.resolver_constructor(info.padre, tipos_args)
                        if elegido is None:
                            self.error_manager.error_poo(
                                'IL-POO-029',
                                f'padre(...): ninguna sobrecarga del constructor '
                                f'de "{info.padre}" coincide con los tipos de '
                                f'argumento ({", ".join(tipos_args)})',
                                nodo.linea, nodo.columna
                            )
                        else:
                            self._verificar_visibilidad_constructor(info.padre, elegido, nodo)
            else:
                for a in nodo.argumentos:
                    self._obtener_tipo(a)

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

        # POO (v2.0): ningún operador compuesto está definido sobre tipos de
        # clase (evita que el intérprete intente sumar/restar instancias).
        if any(self.tabla.es_clase(t) for t in tipos):
            self.error_manager.error_poo(
                'IL-POO-013',
                f'El operador {operador} no está definido para tipos de clase',
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
        elif isinstance(lvalue, MemberLValue):
            tipo_receptor = self._tipo_receptor(lvalue.receptor)
            if tipo_receptor is None:
                return None
            resultado = self.tabla.resolver_atributo(tipo_receptor, lvalue.nombre_miembro)
            return resultado[1].tipo if resultado else None
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

    def _verificar_switch(self, nodo):
        """Verifica switch/segun (Etapa 6): la expresión debe ser int,
        string o bool (dispatch por valor exacto, no tiene sentido con
        float); cada case debe coincidir con ese tipo exactamente."""
        tipo_expr = self._obtener_tipo(nodo.expr)
        if tipo_expr and tipo_expr not in ('int', 'string', 'bool'):
            self.error_manager.error_estructurado(
                'IL-EST-001',
                f'switch/segun no admite expresiones de tipo {tipo_expr} '
                f'(solo int, string o bool)',
                nodo.linea, nodo.columna
            )
            tipo_expr = None  # ya reportado: no encadenar IL-EST-002 por cada case
        for caso in nodo.casos:
            if tipo_expr and caso.valor.tipo_literal != tipo_expr:
                self.error_manager.error_estructurado(
                    'IL-EST-002',
                    f'El case {caso.valor.valor!r} es de tipo '
                    f'{caso.valor.tipo_literal}, pero el switch es de tipo {tipo_expr}',
                    caso.linea, caso.columna
                )
            self._visitar_bloque(caso.bloque)
        if nodo.bloque_default is not None:
            self._visitar_bloque(nodo.bloque_default)

    def _verificar_match(self, nodo):
        """Verifica emparejar/match (Etapa 12.9/12.10): la expresión debe
        ser de un tipo enum -- puro (Etapa 11.8, sin cambios) o tipo suma
        con carga (Etapa 12.10, desazucarado a clases reales por
        semantic.py::_desazucarar_tipos_suma antes de llegar aquí, así que
        "es de tipo enum" y "es de tipo clase" son la MISMA pregunta:
        `tipo_expr in self.tabla.clases`). Reutiliza `es_subtipo_clase`
        (ya extendido en la Etapa 12.3 para interfaces) para reconocer que
        `caso NombreVariante(...)` corresponde a esta enumeración -- cero
        mecanismo nuevo de resolución de tipos."""
        tipo_expr = self._obtener_tipo(nodo.expr)
        info_enum = self.tabla.clases.get(tipo_expr) if tipo_expr else None
        if info_enum is None:
            if tipo_expr:
                self.error_manager.error_tipo(
                    'IL-TIPO-022',
                    f'emparejar/match requiere una expresión de tipo enum, '
                    f'"{tipo_expr}" no lo es',
                    nodo.linea, nodo.columna
                )
            for caso in nodo.casos:
                self._visitar_bloque(caso.bloque)
            if nodo.caso_comodin is not None:
                self._visitar_bloque(nodo.caso_comodin)
            return

        cubiertas = set()
        hubo_error = False
        for caso in nodo.casos:
            if info_enum.es_enum:
                # Enum puro (Etapa 11.8, sin cambios): cada caso liga un
                # miembro por nombre, sin campos que ligar.
                if caso.nombre_variante not in info_enum.atributos:
                    self.error_manager.error_tipo(
                        'IL-TIPO-022',
                        f'"{caso.nombre_variante}" no es un miembro de la '
                        f'enumeración "{tipo_expr}"',
                        caso.linea, caso.columna
                    )
                    hubo_error = True
                elif caso.ligaduras:
                    self.error_manager.error_tipo(
                        'IL-TIPO-022',
                        f'El miembro "{caso.nombre_variante}" de "{tipo_expr}" '
                        f'no tiene campos que ligar',
                        caso.linea, caso.columna
                    )
                    hubo_error = True
                else:
                    cubiertas.add(caso.nombre_variante)
                self._visitar_bloque(caso.bloque)
                continue

            # Tipo suma con carga (Etapa 12.10): cada caso liga los campos
            # (si los hay) de una variante -- una subclase directa de
            # tipo_expr, generada por _desazucarar_tipos_suma.
            info_variante = self.tabla.clases.get(caso.nombre_variante)
            es_variante_valida = (info_variante is not None
                                  and self.tabla.es_subtipo_clase(caso.nombre_variante, tipo_expr))
            if not es_variante_valida:
                self.error_manager.error_tipo(
                    'IL-TIPO-022',
                    f'"{caso.nombre_variante}" no es una variante de "{tipo_expr}"',
                    caso.linea, caso.columna
                )
                hubo_error = True
                self._visitar_bloque(caso.bloque)
                continue

            campos = [a for a in info_variante.atributos.values() if not a.es_estatico]
            if len(caso.ligaduras) != len(campos):
                self.error_manager.error_tipo(
                    'IL-TIPO-022',
                    f'La variante "{caso.nombre_variante}" espera {len(campos)} '
                    f'campo(s), se ligaron {len(caso.ligaduras)}',
                    caso.linea, caso.columna
                )
                hubo_error = True
                self._visitar_bloque(caso.bloque)
                continue

            self.tabla.entrar_ambito()
            for ligadura, attr in zip(caso.ligaduras, campos):
                self.tabla.declarar(ligadura, TipoSimbolo.VARIABLE, attr.tipo,
                                    caso.linea, caso.columna)
            self._visitar_bloque(caso.bloque)
            self.tabla.salir_ambito()
            cubiertas.add(caso.nombre_variante)

        if nodo.caso_comodin is not None:
            self._visitar_bloque(nodo.caso_comodin)
        elif hubo_error:
            # Ya se reportó un problema puntual en algún caso -- no
            # encadenar tambien "no exhaustivo" por el mismo motivo (mismo
            # criterio de _verificar_switch: no seguir apilando diagnósticos
            # derivados de un primer error ya reportado).
            pass
        else:
            # Exhaustividad (Etapa 12.9/12.10): sin comodín, todas las
            # variantes/miembros declarados deben estar cubiertos -- la
            # razón de ser pedagógica del pattern matching sobre tipos
            # suma frente a un switch/case normal (ver docs/
            # InvenioLang_GramaticaFormal.md).
            if info_enum.es_enum:
                todas = set(info_enum.atributos.keys())
            else:
                todas = {n for n, i in self.tabla.clases.items() if i.padre == tipo_expr}
            faltantes = todas - cubiertas
            if faltantes:
                self.error_manager.error_tipo(
                    'IL-TIPO-022',
                    f'emparejar/match no exhaustivo sobre "{tipo_expr}": '
                    f'falta(n) {", ".join(sorted(faltantes))} (o agregue un caso default)',
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

    def _verificar_foreach(self, nodo):
        """Verifica para_cada/foreach (Etapa 12.1): `nodo.arreglo` debe
        resolver a un arreglo (variable o parámetro), y el tipo declarado
        de la variable de recorrido debe ser compatible con el tipo de
        elemento del arreglo -- mismo criterio de `_compatible` que ya usa
        cualquier otra asignación/paso de argumento (promoción int->float,
        upcasting de clases incluido)."""
        entrada_arr = None
        if isinstance(nodo.arreglo, Identifier):
            entrada_arr = self.tabla.buscar(nodo.arreglo.nombre)
        if (entrada_arr is None
                or entrada_arr.tipo_simbolo not in (TipoSimbolo.ARREGLO, TipoSimbolo.PARAM_ARREGLO)):
            self.error_manager.error_tipo(
                'IL-TIPO-001',
                'para_cada / foreach solo puede recorrer un arreglo de una dimensión',
                nodo.linea, nodo.columna
            )
        elif not self._compatible(nodo.tipo, entrada_arr.tipo_dato):
            self.error_manager.error_tipo(
                'IL-TIPO-001',
                f'Tipo incompatible en para_cada / foreach: el arreglo es de '
                f'"{entrada_arr.tipo_dato}", la variable de recorrido es "{nodo.tipo}"',
                nodo.linea, nodo.columna
            )
        self._visitar_bloque(nodo.bloque)

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
            if entrada is None:
                return None
            if entrada.tipo_simbolo in (TipoSimbolo.FUNCION, TipoSimbolo.PROCEDIMIENTO):
                # Etapa 12.6: un IDENTIFICADOR bare que nombra una función o
                # procedimiento (no llamada, ver FunctionCall más abajo) es
                # una referencia a un VALOR función -- su tipo es
                # "funcion(tipos_param)->retorno", no `entrada.tipo_dato`
                # (que guarda el tipo de retorno solo, para cuando SÍ se
                # llama).
                tipo_ret = entrada.tipo_dato if entrada.tipo_simbolo == TipoSimbolo.FUNCION else 'void'
                return self._tipo_funcion_str(entrada.params or [], tipo_ret)
            return entrada.tipo_dato

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
            if nodo.nombre in _ORDEN_SUPERIOR_TIPO:
                # Etapa 12.7: aridad fija ya validada por semantic.py; aquí
                # solo interesa el tipo de retorno para seguir propagando
                # tipos (ej. `int suma = reducir(arr, f, 0);`).
                for arg in nodo.argumentos:
                    self._obtener_tipo(arg)
                return _ORDEN_SUPERIOR_TIPO[nodo.nombre]
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

        if isinstance(nodo, ThisExpr):
            return self.clase_actual

        if isinstance(nodo, NullExpr):
            return 'null'  # pseudo-tipo: compatible solo con clases, ver _compatible

        if isinstance(nodo, MemberAccess):
            tipo_receptor = self._tipo_receptor(nodo.receptor)
            if tipo_receptor is None:
                return None
            resultado = self.tabla.resolver_atributo(tipo_receptor, nodo.nombre_miembro)
            return resultado[1].tipo if resultado else None

        if isinstance(nodo, MethodCallExpr):
            return self._tipo_llamada_metodo(nodo.receptor, nodo.nombre_metodo,
                                             nodo.argumentos, nodo)

        if isinstance(nodo, NewExpr):
            self._verificar_llamada_constructor(nodo.nombre_clase, nodo.argumentos, nodo)
            return nodo.nombre_clase if self.tabla.es_clase(nodo.nombre_clase) else None

        if isinstance(nodo, TernaryExpr):
            return self._tipo_ternario(nodo)

        if isinstance(nodo, LambdaExpr):
            return self._tipo_lambda(nodo)

        return None

    def _tipo_funcion_str(self, tipos_param, tipo_retorno):
        """Construye la misma cadena canónica que
        parser.py::_tipo_funcion_str (Etapa 12.6) -- "funcion(t1,t2)->tr".
        Comparar dos tipos función es comparar estas cadenas: es la única
        excepción deliberada a que InvenioLang es de tipado nominal en
        todo lo demás (dos valores función son "del mismo tipo" si
        coinciden en tipos de parámetro y de retorno, no por nombre de
        declaración -- no existe tal nombre)."""
        return f'funcion({",".join(tipos_param)})->{tipo_retorno}'

    def _tipo_lambda(self, nodo):
        """Verifica el cuerpo de un lambda y retorna su tipo función
        (Etapa 12.6). Mismo patrón que _visitar_funcion: ámbito nuevo,
        parámetros re-declarados, cuerpo visitado -- ver semantic.py::
        _visitar_lambda para por qué el ámbito se anida sobre el vigente
        en vez de resetear (captura léxica)."""
        self.tabla.entrar_ambito()
        for p in nodo.parametros:
            self._declarar_parametro_tc(p)
        tipo_previo = self.tipo_retorno_actual
        self.tipo_retorno_actual = nodo.tipo_retorno
        self._visitar_bloque(nodo.bloque)
        self.tipo_retorno_actual = tipo_previo
        self.tabla.salir_ambito()
        tipos_param = [p.tipo for p in nodo.parametros]
        return self._tipo_funcion_str(tipos_param, nodo.tipo_retorno)

    def _tipo_ternario(self, nodo):
        """Determina el tipo resultante de cond ? si_verdadero : si_falso
        (Etapa 6): la condición debe ser bool, y las dos ramas deben ser del
        mismo tipo o compatibles entre sí (misma regla de _compatible() que
        ya usan asignaciones/argumentos: promoción int->float, upcasting de
        clases, nulo)."""
        self._verificar_condicion(nodo.condicion, nodo.linea, nodo.columna)
        tipo_v = self._obtener_tipo(nodo.si_verdadero)
        tipo_f = self._obtener_tipo(nodo.si_falso)
        if tipo_v is None or tipo_f is None:
            return tipo_v or tipo_f
        if tipo_v == tipo_f:
            return tipo_v
        if self._compatible(tipo_v, tipo_f):
            return tipo_v
        if self._compatible(tipo_f, tipo_v):
            return tipo_f
        self.error_manager.error_estructurado(
            'IL-EST-004',
            f'Las ramas del operador ternario tienen tipos incompatibles: '
            f'{tipo_v} y {tipo_f}',
            nodo.linea, nodo.columna
        )
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

        if op == '??':
            # Coalescencia nula (Etapa 12.2): la izquierda debe poder valer
            # nulo -- variable/expresion de tipo clase, el literal `nulo`,
            # o el resultado de un acceso seguro `?.` (que puede valer
            # nulo aunque su tipo estatico sea primitivo, ej.
            # "p?.nombre ?? 'x'" con nombre : texto). Los primitivos NO
            # detras de un "?." nunca son nulos en InvenioLang (§5.2.3,
            # siempre tienen valor por defecto), asi que "??" sobre ellos
            # no aporta nada y se rechaza.
            es_seguro_izq = (isinstance(nodo.izquierda, (MemberAccess, MethodCallExpr))
                             and nodo.izquierda.es_seguro)
            if t_left != 'null' and not self.tabla.es_clase(t_left) and not es_seguro_izq:
                self.error_manager.error_tipo(
                    'IL-TIPO-001',
                    f'El operando izquierdo de "??" debe poder ser nulo '
                    f'(tipo clase o resultado de "?."), no "{t_left}"',
                    nodo.linea, nodo.columna
                )
                return t_right
            if self._compatible(t_left, t_right):
                return t_right if t_left == 'null' else t_left
            if self._compatible(t_right, t_left):
                return t_right
            self.error_manager.error_tipo(
                'IL-TIPO-001',
                f'Tipos incompatibles en "??": "{t_left}" y "{t_right}"',
                nodo.linea, nodo.columna
            )
            return None

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
            # Compatibles: int con int, float con float, string con string,
            # bool con bool, y (Estructuras de Datos) nulo/null contra
            # cualquier tipo de clase, o dos referencias de clase entre si
            # (identidad, §9 regla "sin" de la spec de POO).
            es_nulo_vs_clase = (
                (t_left == 'null' and (t_right == 'null' or self.tabla.es_clase(t_right)))
                or (t_right == 'null' and self.tabla.es_clase(t_left))
                or (self.tabla.es_clase(t_left) and self.tabla.es_clase(t_right))
            )
            if t_left != t_right and not (t_left == 'int' and t_right == 'float') \
                    and not (t_left == 'float' and t_right == 'int') \
                    and not es_nulo_vs_clase:
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

        # Bit a bit: & | ^ << >> (Etapa 11) -- solo entre enteros, mismo
        # criterio que % (IL-TIPO-010): no tiene sentido desplazar o
        # combinar bits de un float/string/bool/objeto.
        if op in ('&', '|', '^', '<<', '>>'):
            if t_left == 'int' and t_right == 'int':
                return 'int'
            self.error_manager.error_tipo(
                'IL-TIPO-010',
                f'Operador {op} solo es aplicable entre operandos int '
                f'(se encontró {t_left} y {t_right})',
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

        if op == '~':
            # Negación de bits (Etapa 11): solo int, mismo criterio que %.
            if t_oper != 'int':
                self.error_manager.error_tipo(
                    'IL-TIPO-010',
                    f'Operador ~ solo es aplicable a int (se encontró {t_oper})',
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
        # POO (v2.0): upcasting -- una instancia de una subclase es
        # compatible con el tipo de cualquier ancestro (§3 regla 9 de la
        # spec de POO).
        if self.tabla.es_clase(tipo_esperado) and self.tabla.es_clase(tipo_real):
            return self.tabla.es_subtipo_clase(tipo_real, tipo_esperado)
        # Estructuras de Datos: nulo/null es compatible con cualquier tipo
        # de clase (nunca con un primitivo).
        if tipo_real == 'null' and self.tabla.es_clase(tipo_esperado):
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
        # POO (v2.0): incompatibilidad entre tipos de clase no emparentados.
        # error_tipo() y error_poo() son equivalentes en ErrorManager (solo
        # difieren en el nombre); se reutiliza error_tipo() aquí porque
        # todos los llamadores de este helper ya invocan ese método.
        if self.tabla.es_clase(tipo_esperado) or self.tabla.es_clase(tipo_real):
            return 'IL-POO-013'
        return 'IL-TIPO-001'
