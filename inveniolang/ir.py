# Módulo de Código Intermedio de InvenioLang (Etapa 5, Fase 2)
#
# Cierra las tres etapas del "back end" clásico de un compilador que la
# v1.0/v2.0 nunca tuvieron (interpreter.py es un intérprete de árbol, nunca
# genera nada): código de tres direcciones (TAC), optimización sobre ese
# TAC, y un motor de ejecución separado (MaquinaTAC) que lo interpreta.
#
# ADITIVO Y AISLADO A PROPÓSITO: interpreter.py sigue siendo el motor de
# ejecución de producción del IDE (depurador, 214 pruebas de conformidad).
# Este módulo es un camino nuevo y aparte, pensado para enseñar/demostrar
# las etapas del back end -- no reemplaza nada.
#
# ALCANCE: subconjunto ESTRUCTURADO de InvenioLang 1.0 + Etapa 6 (variables,
# constantes, arreglos de una dimensión, funciones/procedimientos, control
# de flujo completo incluido break/continue/return/switch/do-while/ternario/
# try-catch). NO cubre clases/POO (Etapas 2-3-7: encapsulación, herencia,
# polimorfismo, abstractas, estáticos, sobrecarga, genéricos) ni matrices --
# ver NoSoportadoIR. La comprobación es automática: `generar_programa`
# rechaza cualquier AST con `ast.clases` no vacío, y la expansión de
# genéricos de semantic.py (`_expandir_genericos`) corre ANTES de llegar
# aquí, así que una clase genérica especializada también cae en este mismo
# rechazo -- no hace falta un caso especial para genéricos.

from .ast_nodes import *
from . import builtins

_BINOPS = {'+', '-', '*', '/', '%', '==', '!=', '<', '>', '<=', '>='}
_VALORES_POR_DEFECTO = {'int': 0, 'float': 0.0, 'string': '', 'bool': False}


class NoSoportadoIR(Exception):
    """El programa usa una construcción fuera del subconjunto que cubre el
    generador de código intermedio (POO o matrices)."""


class ErrorEjecucionTAC(Exception):
    """Error de ejecución detectado por MaquinaTAC, con `codigo`/`mensaje`
    al estilo del catálogo IL-EJE-* (ver interpreter.py::RuntimeError_).
    No replica el catálogo completo -- solo división/módulo por cero e
    índice de arreglo fuera de rango -- pero es real: es lo que un
    try/catch (Etapa 6) ejecutado con --run-ir efectivamente captura."""

    def __init__(self, codigo, mensaje):
        self.codigo = codigo
        self.mensaje = mensaje
        super().__init__(f'[{codigo}] {mensaje}')


class Instr:
    """Una instrucción de código de tres direcciones (cuádrupla).

    El significado de `arg1`/`arg2`/`arg3` depende de `op`; ver los
    comentarios de `GeneradorIR` para el significado de cada operación.
    Los operandos que son nombres de variable/temporal son `str`; el único
    lugar donde un operando es un valor literal "en crudo" es `arg1` de
    `const` (y el tamaño literal de `array_new`).
    """
    __slots__ = ('op', 'arg1', 'arg2', 'arg3', 'resultado')

    def __init__(self, op, arg1=None, arg2=None, arg3=None, resultado=None):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.arg3 = arg3
        self.resultado = resultado

    def __repr__(self):
        op, a1, a2, a3, r = self.op, self.arg1, self.arg2, self.arg3, self.resultado
        if op == 'label':
            return f'{a1}:'
        if op == 'goto':
            return f'    goto {a1}'
        if op == 'if_false':
            return f'    if_false {a1} goto {a2}'
        if op == 'const':
            return f'    {r} = const {a1!r}'
        if op == 'copy':
            return f'    {r} = {a1}'
        if op in ('neg', 'not'):
            simbolo = '-' if op == 'neg' else '!'
            return f'    {r} = {simbolo}{a1}'
        if op == 'a_float':
            return f'    {r} = (float) {a1}'
        if op == 'param':
            return f'    param {a1}'
        if op == 'call':
            return f'    {r} = call {a1}, {a2}' if r else f'    call {a1}, {a2}'
        if op == 'return':
            return f'    return {a1}' if a1 is not None else '    return'
        if op == 'print':
            return f'    print {a1}'
        if op == 'read':
            return f'    {r} = read({a1})'
        if op == 'array_new':
            return f'    {a1} = new_array[{a2}]'
        if op == 'array_get':
            return f'    {r} = {a1}[{a2}]'
        if op == 'array_set':
            return f'    {a1}[{a2}] = {a3}'
        if op == 'try_begin':
            return f'    try_begin catch={a1} var={a2}'
        if op == 'try_end':
            return '    try_end'
        if op == 'pop_manejador':
            return '    pop_manejador'
        if op in _BINOPS:
            return f'    {r} = {a1} {op} {a2}'
        return f'    {op} {a1} {a2} {a3} -> {r}'


# ============================================================
# Generación de código intermedio (AST -> TAC)
# ============================================================

class GeneradorIR:
    """Recorre el AST (ya validado por semantic.py/type_checker.py) y
    genera TAC. Reutiliza el mismo patrón de recorrido de control de flujo
    ya resuelto en flowchart.py para if/while/for/break/continue/return,
    aquí emitiendo saltos con etiquetas en vez de geometría 2D."""

    def __init__(self):
        self._temp_n = 0
        self._label_n = 0
        self.instrucciones = []
        # Pila de contextos de break/continue (Etapa 6: switch también
        # participa). Cada entrada:
        #   ('loop', etq_continuar, etq_break, profundidad_try_al_entrar)
        #   ('switch', etq_break, profundidad_try_al_entrar)
        # `continue` solo mira las entradas 'loop' (un switch NO lo satisface,
        # ver semantic.py); `break` mira ambas.
        self._ctx_ciclo = []
        self._profundidad_try = 0  # try/catch anidados actualmente abiertos
        self._tipos = {}      # nombre -> tipo declarado (para 'leer')
        self._tams = {}       # nombre de arreglo -> tam declarado (Etapa 12.1, para_cada)

    # ---- utilidades ----

    def _nuevo_temp(self):
        self._temp_n += 1
        return f't{self._temp_n}'

    def _nueva_etiqueta(self):
        self._label_n += 1
        return f'L{self._label_n}'

    def _emit(self, op, arg1=None, arg2=None, arg3=None, resultado=None):
        self.instrucciones.append(Instr(op, arg1, arg2, arg3, resultado))

    # ---- puntos de entrada ----

    def generar_globales(self, ast):
        """TAC de las declaraciones globales (antes y después de main),
        para ejecutarse una sola vez antes de invocar 'main' (§5.2.3)."""
        self._reiniciar()
        for d in list(ast.declaraciones_globales) + list(ast.declaraciones_posteriores):
            self._gen_declaracion_global(d)
        return self.instrucciones

    def generar_subrutina(self, parametros, bloque):
        """TAC de UNA función/procedimiento. Retorna (nombres_parametros,
        instrucciones)."""
        self._reiniciar()
        for p in parametros:
            self._tipos[p.nombre] = p.tipo
        for elem in bloque.elementos:
            self._gen_stmt(elem)
        return [p.nombre for p in parametros], self.instrucciones

    def _reiniciar(self):
        self._temp_n = 0
        self._label_n = 0
        self.instrucciones = []
        self._ctx_ciclo = []
        self._profundidad_try = 0

    def _gen_declaracion_global(self, d):
        if isinstance(d, VarDecl):
            self._tipos[d.nombre] = d.tipo
            if d.init_expr is not None:
                val = self._gen_expr(d.init_expr)
                if d.tipo == 'float':
                    val = self._gen_promover_float(val)
                self._emit('copy', val, resultado=d.nombre)
            else:
                self._emit('const', _VALORES_POR_DEFECTO.get(d.tipo), resultado=d.nombre)
        elif isinstance(d, ConstDecl):
            self._tipos[d.nombre] = d.tipo
            val = self._gen_expr(d.init_expr)
            if d.tipo == 'float':
                val = self._gen_promover_float(val)
            self._emit('copy', val, resultado=d.nombre)
        elif isinstance(d, ArrayDecl):
            self._gen_array_decl(d)
        elif isinstance(d, MatrixDecl):
            raise NoSoportadoIR(
                'El generador de código intermedio no cubre matrices en '
                'este incremento (alcance: subconjunto estructurado, sin '
                'matrices ni POO). Ver docs/InvenioLang_2.0_POO.md.')

    # ---- instrucciones ----

    def _gen_stmt(self, nodo):
        if isinstance(nodo, VarDecl):
            self._tipos[nodo.nombre] = nodo.tipo
            if nodo.init_expr is not None:
                val = self._gen_expr(nodo.init_expr)
                if nodo.tipo == 'float':
                    val = self._gen_promover_float(val)
                self._emit('copy', val, resultado=nodo.nombre)
        elif isinstance(nodo, ConstDecl):
            self._tipos[nodo.nombre] = nodo.tipo
            val = self._gen_expr(nodo.init_expr)
            if nodo.tipo == 'float':
                val = self._gen_promover_float(val)
            self._emit('copy', val, resultado=nodo.nombre)
        elif isinstance(nodo, ArrayDecl):
            self._gen_array_decl(nodo)
        elif isinstance(nodo, MatrixDecl):
            raise NoSoportadoIR(
                'El generador de código intermedio no cubre matrices en '
                'este incremento (alcance: subconjunto estructurado, sin '
                'matrices ni POO).')
        elif isinstance(nodo, AssignStmt):
            self._gen_asignacion(nodo.lvalue, nodo.operador, nodo.expr)
        elif isinstance(nodo, IncDecStmt):
            self._gen_incdec(nodo.nombre, nodo.operador)
        elif isinstance(nodo, PrintStmt):
            val = self._gen_expr(nodo.expr)
            self._emit('print', val)
        elif isinstance(nodo, ReadStmt):
            tipo = self._tipos.get(nodo.nombre, 'string')
            self._emit('read', tipo, resultado=nodo.nombre)
        elif isinstance(nodo, IfStmt):
            self._gen_if(nodo)
        elif isinstance(nodo, WhileStmt):
            self._gen_while(nodo)
        elif isinstance(nodo, ForStmt):
            self._gen_for(nodo)
        elif isinstance(nodo, ForEachStmt):
            self._gen_foreach(nodo)
        elif isinstance(nodo, DoWhileStmt):
            self._gen_do_while(nodo)
        elif isinstance(nodo, SwitchStmt):
            self._gen_switch(nodo)
        elif isinstance(nodo, TryStmt):
            self._gen_try(nodo)
        elif isinstance(nodo, ReturnStmt):
            val = self._gen_expr(nodo.expr) if nodo.expr is not None else None
            self._emit('return', val)
        elif isinstance(nodo, BreakStmt):
            self._emit_break()
        elif isinstance(nodo, ContinueStmt):
            self._emit_continue()
        elif isinstance(nodo, CallStmt):
            self._gen_llamada(nodo.nombre, nodo.argumentos, quiere_valor=False)
        elif isinstance(nodo, FunctionCall):
            self._gen_llamada(nodo.nombre, nodo.argumentos, quiere_valor=False)
        else:
            raise NoSoportadoIR(
                f'"{type(nodo).__name__}" no está soportado por el generador '
                f'de código intermedio (alcance: subconjunto estructurado, '
                f'sin POO). Ver docs/InvenioLang_2.0_POO.md.')

    def _gen_array_decl(self, nodo):
        self._tipos[nodo.nombre] = nodo.tipo
        self._tams[nodo.nombre] = len(nodo.init_exprs) if nodo.init_exprs else nodo.tam
        if nodo.init_exprs:
            tam = len(nodo.init_exprs)
            self._emit('array_new', nodo.nombre, tam)
            for i, e in enumerate(nodo.init_exprs):
                val = self._gen_expr(e)
                # Nota: interpreter.py NO promueve int->float elemento a
                # elemento en un inicializador de arreglo (§5.2.1) -- se
                # replica tal cual, sin promoción aquí.
                self._emit('array_set', nodo.nombre, i, val)
        else:
            self._emit('array_new', nodo.nombre, nodo.tam)

    def _gen_promover_float(self, val):
        """Replica interpreter.py::_promover_si_float: si el valor es un int
        en tiempo de ejecución, lo convierte a float (es una decisión que
        solo puede tomarse en tiempo de ejecución, así que se emite como
        instrucción, no se decide aquí)."""
        t = self._nuevo_temp()
        self._emit('a_float', val, resultado=t)
        return t

    def _gen_asignacion(self, lvalue, operador, expr):
        val = self._gen_expr(expr)
        destino_float = isinstance(lvalue, VarLValue) and self._tipos.get(lvalue.nombre) == 'float'
        if destino_float:
            val = self._gen_promover_float(val)
        if operador != '=':
            base = operador[0]  # '+=' -> '+', etc. (todos los compuestos son de 2 chars)
            actual = self._gen_lvalue_read(lvalue)
            t = self._nuevo_temp()
            self._emit(base, actual, val, resultado=t)
            val = t
            if destino_float:
                val = self._gen_promover_float(val)
        self._gen_lvalue_write(lvalue, val)

    def _gen_incdec(self, nombre, operador):
        t = self._nuevo_temp()
        self._emit('+' if operador == '++' else '-', nombre, 1, resultado=t)
        self._emit('copy', t, resultado=nombre)

    def _gen_lvalue_read(self, lvalue):
        if isinstance(lvalue, VarLValue):
            return lvalue.nombre
        if isinstance(lvalue, ArrayLValue):
            idx = self._gen_expr(lvalue.indice)
            t = self._nuevo_temp()
            self._emit('array_get', lvalue.nombre, idx, resultado=t)
            return t
        raise NoSoportadoIR(f'lvalue "{type(lvalue).__name__}" fuera del subconjunto estructurado')

    def _gen_lvalue_write(self, lvalue, valor):
        if isinstance(lvalue, VarLValue):
            self._emit('copy', valor, resultado=lvalue.nombre)
        elif isinstance(lvalue, ArrayLValue):
            idx = self._gen_expr(lvalue.indice)
            self._emit('array_set', lvalue.nombre, idx, valor)
        else:
            raise NoSoportadoIR(f'lvalue "{type(lvalue).__name__}" fuera del subconjunto estructurado')

    def _gen_if(self, nodo):
        cond = self._gen_expr(nodo.condicion)
        etq_else = self._nueva_etiqueta()
        self._emit('if_false', cond, etq_else)
        for e in nodo.bloque_then.elementos:
            self._gen_stmt(e)
        if nodo.bloque_else is not None:
            etq_fin = self._nueva_etiqueta()
            self._emit('goto', etq_fin)
            self._emit('label', etq_else)
            for e in nodo.bloque_else.elementos:
                self._gen_stmt(e)
            self._emit('label', etq_fin)
        else:
            self._emit('label', etq_else)

    def _gen_while(self, nodo):
        etq_inicio = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        self._emit('label', etq_inicio)
        cond = self._gen_expr(nodo.condicion)
        self._emit('if_false', cond, etq_fin)
        self._ctx_ciclo.append(('loop', etq_inicio, etq_fin, self._profundidad_try))
        for e in nodo.bloque.elementos:
            self._gen_stmt(e)
        self._ctx_ciclo.pop()
        self._emit('goto', etq_inicio)
        self._emit('label', etq_fin)

    def _gen_foreach(self, nodo):
        """TAC de para_cada/foreach (Etapa 12.1): solo soportado sobre un
        arreglo LOCAL de tamaño estático conocido (`self._tams`, poblado
        por `_gen_array_decl`) -- ir.py ya no soporta arreglos de
        parámetro en ningún otro punto (no hay 'PARAM_ARREGLO' en todo
        este módulo), así que esto no reduce el alcance ya existente, solo
        lo hereda. Se traduce a un bucle indexado explícito con
        `array_get`, equivalente a como un estudiante lo escribiría a
        mano con un `for` clásico."""
        tam = self._tams.get(nodo.arreglo.nombre) if isinstance(nodo.arreglo, Identifier) else None
        if tam is None:
            raise NoSoportadoIR(
                'para_cada / foreach solo está soportado por el generador de '
                'código intermedio sobre un arreglo local de tamaño estático '
                'conocido (no un parámetro). Ver docs/InvenioLang_2.0_POO.md.')
        idx = self._nuevo_temp()
        self._emit('const', 0, resultado=idx)
        etq_inicio = self._nueva_etiqueta()
        etq_continuar = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        self._emit('label', etq_inicio)
        cond = self._nuevo_temp()
        self._emit('<', idx, tam, resultado=cond)
        self._emit('if_false', cond, etq_fin)
        self._emit('array_get', nodo.arreglo.nombre, idx, resultado=nodo.nombre)
        self._ctx_ciclo.append(('loop', etq_continuar, etq_fin, self._profundidad_try))
        for e in nodo.bloque.elementos:
            self._gen_stmt(e)
        self._ctx_ciclo.pop()
        self._emit('label', etq_continuar)
        t = self._nuevo_temp()
        self._emit('+', idx, 1, resultado=t)
        self._emit('copy', t, resultado=idx)
        self._emit('goto', etq_inicio)
        self._emit('label', etq_fin)

    def _gen_for(self, nodo):
        if nodo.init_stmt is not None:
            self._gen_for_init_act(nodo.init_stmt)
        etq_inicio = self._nueva_etiqueta()
        etq_continuar = self._nueva_etiqueta()  # 'continue' salta al ACT, no directo a la condicion
        etq_fin = self._nueva_etiqueta()
        self._emit('label', etq_inicio)
        if nodo.cond_expr is not None:
            cond = self._gen_expr(nodo.cond_expr)
            self._emit('if_false', cond, etq_fin)
        self._ctx_ciclo.append(('loop', etq_continuar, etq_fin, self._profundidad_try))
        for e in nodo.bloque.elementos:
            self._gen_stmt(e)
        self._ctx_ciclo.pop()
        self._emit('label', etq_continuar)
        if nodo.act_stmt is not None:
            self._gen_for_init_act(nodo.act_stmt)
        self._emit('goto', etq_inicio)
        self._emit('label', etq_fin)

    def _gen_do_while(self, nodo):
        """do/hacer ... while/mientras (Etapa 6): el cuerpo corre al menos
        una vez; `continue` salta a re-evaluar la condición (no directo al
        inicio del cuerpo)."""
        etq_inicio = self._nueva_etiqueta()
        etq_continuar = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        self._emit('label', etq_inicio)
        self._ctx_ciclo.append(('loop', etq_continuar, etq_fin, self._profundidad_try))
        for e in nodo.bloque.elementos:
            self._gen_stmt(e)
        self._ctx_ciclo.pop()
        self._emit('label', etq_continuar)
        cond = self._gen_expr(nodo.condicion)
        self._emit('if_false', cond, etq_fin)
        self._emit('goto', etq_inicio)
        self._emit('label', etq_fin)

    def _gen_switch(self, nodo):
        """switch/segun (Etapa 6): cadena de comparaciones (no una tabla de
        saltos O(1) -- suficiente para el tamaño típico de un switch
        didáctico) que salta al primer case coincidente; los cuerpos de los
        case se emiten en secuencia SIN goto entre ellos, así que caen al
        siguiente por sí solos (fallthrough, semántica C) salvo que haya un
        `break`."""
        valor = self._gen_expr(nodo.expr)
        etq_fin = self._nueva_etiqueta()
        etq_casos = [self._nueva_etiqueta() for _ in nodo.casos]
        etq_default = self._nueva_etiqueta() if nodo.bloque_default is not None else etq_fin

        for etq, caso in zip(etq_casos, nodo.casos):
            t_const = self._nuevo_temp()
            self._emit('const', caso.valor.valor, resultado=t_const)
            t_neq = self._nuevo_temp()
            self._emit('!=', valor, t_const, resultado=t_neq)
            # t_neq es False exactamente cuando valor == const -> if_false
            # salta a la etiqueta del case, sin necesitar un "if_true".
            self._emit('if_false', t_neq, etq)
        self._emit('goto', etq_default)

        self._ctx_ciclo.append(('switch', etq_fin, self._profundidad_try))
        for etq, caso in zip(etq_casos, nodo.casos):
            self._emit('label', etq)
            for e in caso.bloque.elementos:
                self._gen_stmt(e)
        if nodo.bloque_default is not None:
            self._emit('label', etq_default)
            for e in nodo.bloque_default.elementos:
                self._gen_stmt(e)
        self._ctx_ciclo.pop()
        self._emit('label', etq_fin)

    def _gen_try(self, nodo):
        """try/intentar ... catch/capturar genérico (Etapa 6): `try_begin`
        registra en MaquinaTAC un manejador activo (etiqueta + nombre de la
        variable de catch) que se desactiva con `try_end` al salir
        normalmente, o se consume al capturar un error -- ver
        MaquinaTAC._ejecutar_lista. El acceso a `nombre.codigo`/
        `nombre.mensaje` dentro del catch se resuelve en `_gen_expr`
        (MemberAccess) leyendo directamente las variables sintéticas que el
        manejador deja escritas."""
        etq_catch = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        self._emit('try_begin', etq_catch, nodo.nombre_catch)
        self._profundidad_try += 1
        for e in nodo.bloque_try.elementos:
            self._gen_stmt(e)
        self._profundidad_try -= 1
        self._emit('try_end')
        self._emit('goto', etq_fin)
        self._emit('label', etq_catch)
        for e in nodo.bloque_catch.elementos:
            self._gen_stmt(e)
        self._emit('label', etq_fin)

    def _emit_pops_manejadores(self, profundidad_objetivo):
        """Antes de un break/continue que salta fuera de uno o más try
        activos, cierra esos manejadores (si no, quedarían "colgados" y
        podrían capturar por error algo que ocurra después del ciclo)."""
        for _ in range(self._profundidad_try - profundidad_objetivo):
            self._emit('pop_manejador')

    def _emit_break(self):
        for entrada in reversed(self._ctx_ciclo):
            if entrada[0] == 'loop':
                _, _, etq_break, prof = entrada
            elif entrada[0] == 'switch':
                _, etq_break, prof = entrada
            else:
                continue
            self._emit_pops_manejadores(prof)
            self._emit('goto', etq_break)
            return
        raise NoSoportadoIR('break fuera de un ciclo o switch (no debería pasar el semántico)')

    def _emit_continue(self):
        for entrada in reversed(self._ctx_ciclo):
            if entrada[0] == 'loop':
                _, etq_continuar, _, prof = entrada
                self._emit_pops_manejadores(prof)
                self._emit('goto', etq_continuar)
                return
        raise NoSoportadoIR('continue fuera de un ciclo (no debería pasar el semántico)')

    def _gen_for_init_act(self, nodo):
        if isinstance(nodo, ForInitVar):
            self._tipos[nodo.nombre] = nodo.tipo
            if nodo.init_expr is not None:
                val = self._gen_expr(nodo.init_expr)
                if nodo.tipo == 'float':
                    val = self._gen_promover_float(val)
                self._emit('copy', val, resultado=nodo.nombre)
        elif isinstance(nodo, ForInitAsig):
            self._gen_asignacion(nodo.lvalue, nodo.operador, nodo.expr)
        elif isinstance(nodo, ForInitIncDec):
            self._gen_incdec(nodo.nombre, nodo.operador)

    def _gen_llamada(self, nombre, argumentos, quiere_valor):
        # Etapa 12.6: `nombre(args)` puede ahora ser una llamada a través
        # de una variable de tipo función (closure), no solo a una
        # función/procedimiento de nivel superior -- semantic.py ya lo
        # valida como programa correcto, así que sin este chequeo aquí
        # `_emit('call', nombre, ...)` emitiría una llamada a un nombre de
        # subrutina que jamás se generó, y `MaquinaTAC` fallaría en tiempo
        # de EJECUCIÓN con un error de "subrutina no encontrada" en vez de
        # rechazarse limpiamente en tiempo de generación (mismo criterio
        # que la exclusión de POO/matrices: NoSoportadoIR aquí mismo, antes
        # de emitir nada).
        if self._tipos.get(nombre, '').startswith('funcion('):
            raise NoSoportadoIR(
                'El generador de código intermedio no soporta llamar a través '
                'de una variable de tipo función (closures, Etapa 12.6) -- '
                'alcance: subconjunto estructurado, sin funciones de primera '
                'clase. Ver docs/InvenioLang_2.0_POO.md.')
        for arg in argumentos:
            val = self._gen_expr(arg)
            self._emit('param', val)
        t = self._nuevo_temp() if quiere_valor else None
        self._emit('call', nombre, len(argumentos), resultado=t)
        return t

    # ---- expresiones ----

    def _gen_expr(self, nodo):
        """Genera TAC para una expresión y retorna el NOMBRE (variable o
        temporal) que contiene su valor."""
        if isinstance(nodo, Literal):
            t = self._nuevo_temp()
            self._emit('const', nodo.valor, resultado=t)
            return t
        if isinstance(nodo, Identifier):
            if nodo.nombre not in self._tipos:
                # Etapa 12.6: la única razón por la que un IDENTIFICADOR ya
                # validado por semantic.py NO es una variable/parámetro
                # conocido (todo lo cual queda registrado en self._tipos al
                # generarse) es que sea una referencia bare a una función/
                # procedimiento de nivel superior pasada por valor
                # (`operar = sumar;`) -- fuera de alcance de este generador,
                # mismo criterio que _gen_llamada de arriba.
                raise NoSoportadoIR(
                    'El generador de código intermedio no soporta pasar una '
                    'función por nombre como valor (funciones de primera '
                    'clase, Etapa 12.6). Ver docs/InvenioLang_2.0_POO.md.')
            return nodo.nombre
        if isinstance(nodo, ArrayAccess):
            idx = self._gen_expr(nodo.indice)
            t = self._nuevo_temp()
            self._emit('array_get', nodo.nombre, idx, resultado=t)
            return t
        if isinstance(nodo, FunctionCall):
            return self._gen_llamada(nodo.nombre, nodo.argumentos, quiere_valor=True)
        if isinstance(nodo, BinaryOp):
            if nodo.operador == '&&':
                return self._gen_and(nodo)
            if nodo.operador == '||':
                return self._gen_or(nodo)
            izq = self._gen_expr(nodo.izquierda)
            der = self._gen_expr(nodo.derecha)
            t = self._nuevo_temp()
            self._emit(nodo.operador, izq, der, resultado=t)
            return t
        if isinstance(nodo, UnaryOp):
            if nodo.operador in ('++', '--'):
                return self._gen_incdec_expr(nodo)
            val = self._gen_expr(nodo.operando)
            t = self._nuevo_temp()
            self._emit('neg' if nodo.operador == '-' else 'not', val, resultado=t)
            return t
        if isinstance(nodo, TernaryExpr):
            return self._gen_ternario(nodo)
        if (isinstance(nodo, MemberAccess) and isinstance(nodo.receptor, Identifier)
                and nodo.nombre_miembro in ('codigo', 'mensaje')):
            # Caso especial acotado (Etapa 6, NO soporte general de POO):
            # `e.codigo`/`e.mensaje` dentro de un catch -- el manejador de
            # MaquinaTAC ya dejó el valor en esta variable sintética (ver
            # _gen_try / MaquinaTAC._ejecutar_lista, op 'try_begin').
            return f'{nodo.receptor.nombre}.{nodo.nombre_miembro}'
        raise NoSoportadoIR(
            f'"{type(nodo).__name__}" no está soportado por el generador de '
            f'código intermedio (alcance: subconjunto estructurado, sin POO).')

    def _gen_ternario(self, nodo):
        """cond ? si_verdadero : si_falso (Etapa 6) -- solo se genera código
        para la rama elegida en tiempo de ejecución (igual criterio que
        &&/||: nunca se evalúa la rama descartada)."""
        t = self._nuevo_temp()
        etq_falso = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        cond = self._gen_expr(nodo.condicion)
        self._emit('if_false', cond, etq_falso)
        val_v = self._gen_expr(nodo.si_verdadero)
        self._emit('copy', val_v, resultado=t)
        self._emit('goto', etq_fin)
        self._emit('label', etq_falso)
        val_f = self._gen_expr(nodo.si_falso)
        self._emit('copy', val_f, resultado=t)
        self._emit('label', etq_fin)
        return t

    def _gen_incdec_expr(self, nodo):
        # el operando siempre es un Identifier simple (garantizado por la gramatica)
        nombre = nodo.operando.nombre
        t_nuevo = self._nuevo_temp()
        self._emit('+' if nodo.operador == '++' else '-', nombre, 1, resultado=t_nuevo)
        if nodo.es_prefijo:
            self._emit('copy', t_nuevo, resultado=nombre)
            return nombre
        t_viejo = self._nuevo_temp()
        self._emit('copy', nombre, resultado=t_viejo)  # valor ANTES de sobreescribir
        self._emit('copy', t_nuevo, resultado=nombre)
        return t_viejo

    def _gen_and(self, nodo):
        # cortocircuito (§6.3.1 de la v1.0): la derecha no se evalúa si la
        # izquierda ya decide el resultado.
        t = self._nuevo_temp()
        etq_falso = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        izq = self._gen_expr(nodo.izquierda)
        self._emit('if_false', izq, etq_falso)
        der = self._gen_expr(nodo.derecha)
        self._emit('copy', der, resultado=t)
        self._emit('goto', etq_fin)
        self._emit('label', etq_falso)
        self._emit('const', False, resultado=t)
        self._emit('label', etq_fin)
        return t

    def _gen_or(self, nodo):
        t = self._nuevo_temp()
        etq_seguir = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        izq = self._gen_expr(nodo.izquierda)
        self._emit('if_false', izq, etq_seguir)
        self._emit('const', True, resultado=t)
        self._emit('goto', etq_fin)
        self._emit('label', etq_seguir)
        der = self._gen_expr(nodo.derecha)
        self._emit('copy', der, resultado=t)
        self._emit('label', etq_fin)
        return t


def generar_programa(ast):
    """Genera el IR de todo el programa. Retorna (subrutinas, ir_globales)
    donde `subrutinas` es dict nombre -> (nombres_parametros, instrucciones)
    e incluye 'main'. Lanza NoSoportadoIR si el programa usa clases/POO."""
    if ast.clases:
        raise NoSoportadoIR(
            'El generador de código intermedio no cubre clases/POO en este '
            'incremento (alcance: subconjunto estructurado de la v1.0). '
            'Ver docs/InvenioLang_2.0_POO.md.')
    gen = GeneradorIR()
    ir_globales = gen.generar_globales(ast)
    subrutinas = {}
    if ast.main is not None:
        subrutinas['main'] = gen.generar_subrutina([], ast.main.bloque)
    for sub in ast.subrutinas:
        subrutinas[sub.nombre] = gen.generar_subrutina(sub.parametros, sub.bloque)
    return subrutinas, ir_globales


def formatear(instrucciones):
    """Texto legible de una lista de instrucciones, una por línea."""
    return '\n'.join(repr(ins) for ins in instrucciones)


# ============================================================
# Optimización (pasadas sobre el TAC)
# ============================================================

def _calcular_binop(op, a, b):
    """Misma aritmética que interpreter.py (división/módulo truncados hacia
    cero, §4.2.2) para que el plegado de constantes y MaquinaTAC calculen
    exactamente lo mismo que el intérprete de árbol."""
    if op == '==':
        return a == b
    if op == '!=':
        return a != b
    if op == '<':
        return a < b
    if op == '>':
        return a > b
    if op == '<=':
        return a <= b
    if op == '>=':
        return a >= b
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    if op == '/':
        if _es_entero(a) and _es_entero(b):
            q = abs(a) // abs(b)
            return -q if (a < 0) != (b < 0) else q
        return a / b
    if op == '%':
        if _es_entero(a) and _es_entero(b):
            r = abs(a) % abs(b)
            return -r if a < 0 else r
        return a % b
    raise ValueError(f'operador no soportado: {op}')


def _es_entero(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _es_real(v):
    return isinstance(v, float)


def plegado_constantes(instrucciones):
    """Plegado + propagación de constantes en una sola pasada hacia
    adelante: sigue qué nombres tienen actualmente un valor constante
    conocido, propaga ese valor a los usos, y si TODOS los operandos de una
    operación quedan constantes, la reduce a una única instrucción `const`.
    Una `label` es un punto de unión de varios caminos posibles, así que
    invalida todo lo que se sabía hasta ahí (conservador pero correcto)."""
    constantes = {}
    nuevas = []
    cambios = 0
    for ins in instrucciones:
        if ins.op == 'label':
            constantes.clear()
            nuevas.append(ins)
            continue
        if ins.op == 'const':
            constantes[ins.resultado] = ins.arg1
            nuevas.append(ins)
            continue
        if ins.op == 'copy' and isinstance(ins.arg1, str) and ins.arg1 in constantes:
            valor = constantes[ins.arg1]
            nuevas.append(Instr('const', valor, resultado=ins.resultado))
            constantes[ins.resultado] = valor
            cambios += 1
            continue
        if ins.op in _BINOPS and isinstance(ins.arg1, str) and isinstance(ins.arg2, str) \
                and ins.arg1 in constantes and ins.arg2 in constantes:
            try:
                valor = _calcular_binop(ins.op, constantes[ins.arg1], constantes[ins.arg2])
            except (ValueError, ZeroDivisionError):
                valor = None
            if valor is not None:
                nuevas.append(Instr('const', valor, resultado=ins.resultado))
                constantes[ins.resultado] = valor
                cambios += 1
                continue
        if ins.op in ('neg', 'not') and isinstance(ins.arg1, str) and ins.arg1 in constantes:
            valor = (-constantes[ins.arg1]) if ins.op == 'neg' else (not constantes[ins.arg1])
            nuevas.append(Instr('const', valor, resultado=ins.resultado))
            constantes[ins.resultado] = valor
            cambios += 1
            continue
        if ins.op == 'a_float' and isinstance(ins.arg1, str) and ins.arg1 in constantes:
            v = constantes[ins.arg1]
            valor = float(v) if _es_entero(v) else v
            nuevas.append(Instr('const', valor, resultado=ins.resultado))
            constantes[ins.resultado] = valor
            cambios += 1
            continue
        if ins.resultado is not None:
            constantes.pop(ins.resultado, None)
        nuevas.append(ins)
    return nuevas, cambios


def eliminar_codigo_muerto(instrucciones):
    """Quita instrucciones PURAS (sin efectos de lado: const/copy/aritmética/
    array_get) cuyo resultado -- siempre un temporal, nunca una variable del
    programa -- no se usa en ningún lado."""
    usados = set()
    for ins in instrucciones:
        for campo in (ins.arg1, ins.arg2, ins.arg3):
            if isinstance(campo, str):
                usados.add(campo)
    puras = _BINOPS | {'const', 'copy', 'neg', 'not', 'a_float', 'array_get'}
    nuevas = []
    cambios = 0
    for ins in instrucciones:
        es_temp_no_usado = (ins.resultado is not None
                            and ins.resultado.startswith('t')
                            and ins.resultado not in usados)
        if ins.op in puras and es_temp_no_usado:
            cambios += 1
            continue
        nuevas.append(ins)
    return nuevas, cambios


def eliminar_inalcanzable(instrucciones):
    """Quita instrucciones entre un salto incondicional (`goto`/`return`) y
    la siguiente etiqueta -- nunca se llega a ejecutarlas."""
    nuevas = []
    cambios = 0
    muerto = False
    for ins in instrucciones:
        if ins.op == 'label':
            muerto = False
            nuevas.append(ins)
            continue
        if muerto:
            cambios += 1
            continue
        nuevas.append(ins)
        if ins.op in ('goto', 'return'):
            muerto = True
    return nuevas, cambios


def peephole_saltos_redundantes(instrucciones):
    """Quita un `goto` cuyo destino es la etiqueta inmediatamente
    siguiente -- saltar ahí es lo mismo que no saltar."""
    nuevas = []
    cambios = 0
    n = len(instrucciones)
    for i, ins in enumerate(instrucciones):
        if (ins.op == 'goto' and i + 1 < n and instrucciones[i + 1].op == 'label'
                and instrucciones[i + 1].arg1 == ins.arg1):
            cambios += 1
            continue
        nuevas.append(ins)
    return nuevas, cambios


def eliminar_recursion_cola(nombre_funcion, nombres_parametros, instrucciones):
    """Elimina la recursión de cola DIRECTA (Etapa 12.8): cuando la última
    instrucción antes de un `return t` es exactamente una llamada a la
    PROPIA subrutina (`t = call nombre_funcion, N`, con los `N` `param`
    que la preceden inmediatamente y sin ninguna instrucción entre el
    `call` y el `return`), reescribe esa secuencia como una reasignación
    de los parámetros a los nuevos valores seguida de un `goto` al inicio
    de la subrutina -- la transformación clásica de eliminación de
    recursión de cola sobre TAC. Es la razón por la que una función escrita
    con acumulador explícito (`sumaCola(n, acc)`) corre con profundidad de
    pila de Python CONSTANTE bajo `--run-ir`, mientras que la misma
    función sin acumulador (`return n + f(n-1);`, la llamada NO es lo
    último que pasa) sigue creciendo la pila -- y el intérprete de árbol
    (interpreter.py) nunca aplica esta transformación, así que sigue
    limitado por MAX_RECURSION/IL-EJE-040 en ambos casos por igual. Ver
    pruebas/tco_demo.inv para el contraste con salida real.

    Retorna (instrucciones_nuevas, cambios) -- mismo contrato que las
    demás pasadas de `_PASADAS`, pero esta SÍ necesita el nombre de la
    propia subrutina, así que se aplica por separado en
    `optimizar_programa`, no dentro de `_PASADAS` (que son todas
    agnósticas del nombre)."""
    etq_inicio = f'__tco_{nombre_funcion}_inicio'
    nuevas = [Instr('label', etq_inicio)]
    cambios = 0
    i = 0
    n = len(instrucciones)
    while i < n:
        ins = instrucciones[i]
        if (ins.op == 'call' and ins.arg1 == nombre_funcion
                and i + 1 < n and instrucciones[i + 1].op == 'return'
                and instrucciones[i + 1].arg1 == ins.resultado):
            num_args = ins.arg2
            # Los `num_args` 'param' que alimentan este 'call' NO son
            # necesariamente contiguos en `nuevas`: `_gen_llamada` emite,
            # por cada argumento, primero las instrucciones que calculan
            # su valor y luego su 'param' -- así que el cómputo del
            # segundo argumento queda ENTRE el 'param' del primero y el
            # del segundo. Se buscan los `num_args` 'param' más recientes,
            # sin importar qué haya entre medio.
            indices_param = []
            j = len(nuevas) - 1
            while j >= 0 and len(indices_param) < num_args:
                if nuevas[j].op == 'param':
                    indices_param.append(j)
                j -= 1
            if len(indices_param) == num_args:
                indices_param.reverse()  # orden de argumento: primero -> último
                valores = [nuevas[idx].arg1 for idx in indices_param]
                for idx in sorted(indices_param, reverse=True):
                    del nuevas[idx]
                # Las instrucciones que calcularon esos valores (const,
                # aritmética, ...) quedan en `nuevas` sin su 'param' -- se
                # vuelven temporales muertos que `eliminar_codigo_muerto`
                # (la pasada siguiente en optimizar_programa) limpia solo.
                for nombre_param, val in zip(nombres_parametros, valores):
                    nuevas.append(Instr('copy', val, resultado=nombre_param))
                nuevas.append(Instr('goto', etq_inicio))
                cambios += 1
                i += 2  # el 'call' y el 'return' que lo sigue, ya reemplazados
                continue
        nuevas.append(ins)
        i += 1
    if cambios == 0:
        return instrucciones, 0  # sin llamada de cola: no vale la pena la etiqueta extra
    return nuevas, cambios


_PASADAS = (
    ('plegado de constantes', plegado_constantes),
    ('eliminación de código inalcanzable', eliminar_inalcanzable),
    ('eliminación de código muerto', eliminar_codigo_muerto),
    ('peephole (saltos redundantes)', peephole_saltos_redundantes),
)


def optimizar(instrucciones, rondas=3):
    """Corre las pasadas de optimización repetidamente hasta que ninguna
    cambie nada (una pasada puede desbloquear a otra: por ejemplo, plegar
    una condición constante puede dejar una rama entera inalcanzable) o se
    agoten las `rondas`. Retorna (instrucciones_optimizadas, resumen) donde
    `resumen` es una lista de (nombre_pasada, instrucciones_afectadas) solo
    con las pasadas que sí cambiaron algo, en orden."""
    resumen = []
    actuales = list(instrucciones)
    for _ in range(rondas):
        total_ronda = 0
        for nombre, funcion in _PASADAS:
            actuales, cambios = funcion(actuales)
            if cambios:
                resumen.append((nombre, cambios))
                total_ronda += cambios
        if total_ronda == 0:
            break
    return actuales, resumen


def optimizar_programa(subrutinas):
    """Aplica `optimizar` a cada subrutina de un programa generado por
    `generar_programa`. Retorna (subrutinas_optimizadas, resumen_por_nombre).

    La eliminación de recursión de cola (Etapa 12.8) se aplica ANTES que
    las pasadas genéricas de `_PASADAS` -- necesita el nombre de la propia
    subrutina (una de las claves de `subrutinas`), así que no encaja en
    `_PASADAS` (agnósticas del nombre); una vez reescrita a `copy`+`goto`,
    el resto de pasadas (peephole en particular) puede seguir limpiándola
    igual que a cualquier otro código."""
    optimizadas = {}
    resumenes = {}
    for nombre, (parametros, instrucciones) in subrutinas.items():
        tras_tco, cambios_tco = eliminar_recursion_cola(nombre, parametros, instrucciones)
        nuevas, resumen = optimizar(tras_tco)
        if cambios_tco:
            resumen = [('eliminación de recursión de cola', cambios_tco)] + resumen
        optimizadas[nombre] = (parametros, nuevas)
        resumenes[nombre] = resumen
    return optimizadas, resumenes


# ============================================================
# Ejecución (MaquinaTAC): el "código objetivo" de esta etapa es el propio
# TAC (optimizado o no), ejecutado por este motor lineal separado -- no se
# agrega además un bytecode de más bajo nivel, para mantener el alcance
# manejable (queda anotado como candidato futuro en la hoja de ruta).
# ============================================================

class MaquinaTAC:
    """Intérprete lineal de TAC. Modelo de ámbitos deliberadamente simple
    (dos niveles: variables globales compartidas + un marco plano por
    llamada activa, sin bloques anidados -- el propio TAC ya aplanó los
    bloques del AST) -- suficiente para el subconjunto estructurado que
    cubre el generador; no reproduce el catálogo completo de errores de
    ejecución de interpreter.py (IL-EJE-*), solo el resultado computacional,
    ya que su propósito es demostrar/verificar el back end, no reemplazar
    el intérprete de producción."""

    def __init__(self, subrutinas, ir_globales):
        self.subrutinas = subrutinas  # nombre -> (parametros, instrucciones)
        self.ir_globales = ir_globales
        self.globales = {}
        self.salida = []
        self.entrada = []

    def ejecutar(self, entrada=None):
        self.entrada = list(entrada) if entrada else []
        self.salida = []
        self.globales = {}
        self._ejecutar_lista(self.ir_globales, self.globales)
        self._llamar('main', [])
        return self.salida

    def _llamar(self, nombre, argumentos):
        if builtins.es_built_in(nombre):
            try:
                return builtins.ejecutar_built_in(nombre, argumentos)
            except builtins.BuiltInError as e:
                raise ErrorEjecucionTAC(e.codigo, e.mensaje)
        entrada_sub = self.subrutinas.get(nombre)
        if entrada_sub is None:
            raise RuntimeError(f'subrutina no encontrada en el IR: "{nombre}"')
        parametros, instrucciones = entrada_sub
        marco = dict(zip(parametros, argumentos))
        tipo, valor = self._ejecutar_lista(instrucciones, marco)
        return valor if tipo == 'return' else None

    def _contenedor(self, nombre, marco):
        return marco if nombre in marco else self.globales

    def _leer_var(self, operando, marco):
        # Un operando NO-str (int/float/bool/None) es un literal inmediato
        # usado directo, sin pasar por 'const' (p. ej. el "1" de i++, o un
        # índice de arreglo ya conocido en tiempo de generación) -- nunca un
        # nombre de variable (esos siempre son str).
        if not isinstance(operando, str):
            return operando
        return self._contenedor(operando, marco).get(operando)

    def _escribir_var(self, nombre, valor, marco):
        # Ya existe como local o global: escribe ahí. Primera aparición
        # (declaración): nace en el marco local actual.
        cont = marco if nombre in marco else (self.globales if nombre in self.globales else marco)
        cont[nombre] = valor


    def _ejecutar_lista(self, instrucciones, marco):
        etiquetas = {ins.arg1: i for i, ins in enumerate(instrucciones) if ins.op == 'label'}
        pila_params = []
        # Manejadores de try/catch activos (Etapa 6): pila de
        # (etiqueta_catch, nombre_variable_catch). Ver 'try_begin' abajo.
        pila_manejadores = []
        i = 0
        n = len(instrucciones)
        while i < n:
            ins = instrucciones[i]
            op = ins.op
            try:
                if op == 'label':
                    pass
                elif op == 'const':
                    self._escribir_var(ins.resultado, ins.arg1, marco)
                elif op == 'copy':
                    self._escribir_var(ins.resultado, self._leer_var(ins.arg1, marco), marco)
                elif op in _BINOPS:
                    a = self._leer_var(ins.arg1, marco)
                    b = self._leer_var(ins.arg2, marco)
                    try:
                        resultado = _calcular_binop(op, a, b)
                    except ZeroDivisionError:
                        # Misma distinción que interpreter.py::_error_division_cero:
                        # '/' entre reales -> IL-EJE-002, entre enteros -> IL-EJE-006;
                        # '%' (siempre entero) es IL-EJE-006 en cualquier caso.
                        if op == '/' and (_es_real(a) or _es_real(b)):
                            raise ErrorEjecucionTAC(
                                'IL-EJE-002',
                                'Operación de punto flotante inválida: división entre 0.0')
                        raise ErrorEjecucionTAC(
                            'IL-EJE-006',
                            'División por cero' if op == '/' else 'División por cero en módulo')
                    self._escribir_var(ins.resultado, resultado, marco)
                elif op == 'neg':
                    self._escribir_var(ins.resultado, -self._leer_var(ins.arg1, marco), marco)
                elif op == 'not':
                    self._escribir_var(ins.resultado, not self._leer_var(ins.arg1, marco), marco)
                elif op == 'a_float':
                    v = self._leer_var(ins.arg1, marco)
                    self._escribir_var(ins.resultado, float(v) if _es_entero(v) else v, marco)
                elif op == 'goto':
                    i = etiquetas[ins.arg1]
                    continue
                elif op == 'if_false':
                    if not self._leer_var(ins.arg1, marco):
                        i = etiquetas[ins.arg2]
                        continue
                elif op == 'param':
                    pila_params.append(self._leer_var(ins.arg1, marco))
                elif op == 'call':
                    nombre_f, nargs = ins.arg1, ins.arg2
                    args = pila_params[len(pila_params) - nargs:] if nargs else []
                    del pila_params[len(pila_params) - nargs:]
                    valor = self._llamar(nombre_f, args)
                    if ins.resultado is not None:
                        self._escribir_var(ins.resultado, valor, marco)
                elif op == 'return':
                    valor = self._leer_var(ins.arg1, marco) if ins.arg1 is not None else None
                    return ('return', valor)
                elif op == 'print':
                    self._escribir_salida(self._leer_var(ins.arg1, marco))
                elif op == 'read':
                    self._escribir_var(ins.resultado, self._leer_entrada(ins.arg1), marco)
                elif op == 'array_new':
                    marco[ins.arg1] = [None] * self._leer_var(ins.arg2, marco)
                elif op == 'array_get':
                    arr = self._contenedor(ins.arg1, marco)[ins.arg1]
                    idx = self._leer_var(ins.arg2, marco)
                    if idx < 0 or idx >= len(arr):
                        raise ErrorEjecucionTAC('IL-EJE-050', f'Índice {idx} fuera de rango')
                    self._escribir_var(ins.resultado, arr[idx], marco)
                elif op == 'array_set':
                    arr = self._contenedor(ins.arg1, marco)[ins.arg1]
                    idx = self._leer_var(ins.arg2, marco)
                    if idx < 0 or idx >= len(arr):
                        raise ErrorEjecucionTAC('IL-EJE-050', f'Índice {idx} fuera de rango')
                    arr[idx] = self._leer_var(ins.arg3, marco)
                elif op == 'try_begin':
                    pila_manejadores.append((ins.arg1, ins.arg2))
                elif op == 'try_end':
                    if pila_manejadores:
                        pila_manejadores.pop()
                elif op == 'pop_manejador':
                    if pila_manejadores:
                        pila_manejadores.pop()
                else:
                    raise RuntimeError(f'operación de IR no soportada: {op}')
            except ErrorEjecucionTAC as err:
                if not pila_manejadores:
                    raise
                etq_catch, nombre_catch = pila_manejadores.pop()
                marco[f'{nombre_catch}.codigo'] = err.codigo
                marco[f'{nombre_catch}.mensaje'] = err.mensaje
                i = etiquetas[etq_catch]
                continue
            i += 1
        return (None, None)

    def _escribir_salida(self, valor):
        if isinstance(valor, bool):
            s = 'true' if valor else 'false'
        elif isinstance(valor, float):
            s = str(valor)
        elif valor is None:
            s = 'void'
        else:
            s = str(valor)
        self.salida.append(s)

    def _leer_entrada(self, tipo):
        if self.entrada:
            crudo = self.entrada.pop(0)
        else:
            try:
                crudo = input()
            except EOFError:
                crudo = ''
        crudo = crudo.strip()
        if tipo == 'int':
            return int(crudo)
        if tipo == 'float':
            return float(crudo)
        if tipo == 'bool':
            v = crudo.lower()
            return v in ('true', 'verdadero', '1')
        return crudo


# ============================================================
# Generación de código a un objetivo de juguete (Etapa 12.11)
# ============================================================
#
# Cierra el pipeline canónico de un curso de compiladores que el módulo se
# queda corto de completar hasta esta etapa: fuente -> AST -> TAC -> TAC
# optimizado -> CÓDIGO OBJETIVO. `generar_objetivo_programa` traduce TAC ya
# generado (opcionalmente optimizado por `optimizar_programa`, Etapa 12.8
# incluida) a un ISA de juguete tipo "SM" (máquina de pila de operandos),
# documentado aquí completo -- deliberadamente de una sola página, sin
# convenciones de llamada realistas (sin direcciones de retorno ni marco de
# pila real: CALL/CALLV invocan directamente a `MaquinaObjetivo._llamar`,
# igual que ya hace `MaquinaTAC` -- el objetivo pedagógico es mostrar CÓMO
# una operación de TAC en tres direcciones ("t1 = a + b") se descompone en
# una secuencia de instrucciones de pila ("LOAD a; LOAD b; ADD; STORE t1"),
# no reproducir un enlazador real).
#
# ISA (26 instrucciones, todas sobre una pila de operandos + variables por
# nombre -- la asignación de REGISTROS reales llega en la Etapa 12.12,
# como una pasada posterior sobre este mismo código):
#   PUSH v          empuja el literal v
#   LOAD nombre     empuja el valor de la variable `nombre`
#   STORE nombre    saca el tope y lo guarda en `nombre`
#   ADD SUB MUL DIV MOD   saca b, saca a, empuja (a op b)
#   NEG             saca a, empuja -a
#   NOT             saca a, empuja not a
#   CVTF            saca a, empuja float(a)
#   CMPEQ CMPNE CMPLT CMPLE CMPGT CMPGE   saca b, saca a, empuja bool(a op b)
#   LABEL nombre    marcador de salto (no hace nada al ejecutar)
#   JMP nombre      salta incondicional a `nombre`
#   JZ nombre       saca a; si a es falso, salta a `nombre`
#   PUSHPARAM       saca el tope y lo agrega a la lista de argumentos pendiente
#   CALL nombre, n  invoca `nombre` con los ultimos n argumentos pendientes;
#                   empuja el valor de retorno (la subrutina SIEMPRE retorna
#                   algo en este caso -- lo exige el type checker antes de
#                   llegar aqui)
#   CALLV nombre, n como CALL, pero el valor de retorno (si lo hay) se
#                   descarta sin empujarlo -- llamada en posición de
#                   instrucción, IL-WARN-020
#   RETV            saca el tope y termina la subrutina retornándolo
#   RET             termina la subrutina sin retornar valor
#   PRINT           saca el tope y lo imprime
#
# ALCANCE: el mismo subconjunto de `generar_programa` (estructurado, sin
# POO), MENOS arreglos y try/catch -- `NoSoportadoObjetivo` se lanza para
# 'array_new'/'array_get'/'array_set'/'try_begin'/'try_end'/
# 'pop_manejador'/'read' (una máquina de pila real necesitaría direcciones
# de memoria indexables y manejo de excepciones con desenrollado de pila
# para esos, fuera del alcance "de una página" de este incremento -- mismo
# criterio de exclusión documentada que ya usa `NoSoportadoIR` para POO).

class NoSoportadoObjetivo(Exception):
    """El programa usa una construcción fuera del subconjunto que cubre el
    generador de código objetivo (arreglos, try/catch, lectura de entrada)."""


class InstrObjetivo:
    """Una instrucción del ISA de juguete."""

    __slots__ = ('op', 'arg1', 'arg2')

    def __init__(self, op, arg1=None, arg2=None):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2

    def __repr__(self):
        op, a1, a2 = self.op, self.arg1, self.arg2
        if op == 'LABEL':
            return f'{a1}:'
        if op in ('JMP', 'JZ'):
            return f'    {op} {a1}'
        if op == 'PUSH':
            return f'    PUSH {a1!r}'
        if op in ('LOAD', 'STORE'):
            return f'    {op} {a1}'
        if op in ('CALL', 'CALLV'):
            return f'    {op} {a1}, {a2}'
        return f'    {op}'


_MAPA_BINOP_OBJETIVO = {
    '+': 'ADD', '-': 'SUB', '*': 'MUL', '/': 'DIV', '%': 'MOD',
    '==': 'CMPEQ', '!=': 'CMPNE', '<': 'CMPLT', '<=': 'CMPLE',
    '>': 'CMPGT', '>=': 'CMPGE',
}

_NO_SOPORTADOS_OBJETIVO = {
    'array_new', 'array_get', 'array_set',
    'try_begin', 'try_end', 'pop_manejador', 'read',
}


# ============================================================
# Análisis de flujo de datos: liveness + asignación de registros
# (Etapa 12.12)
# ============================================================
#
# Pasada CLÁSICA de un curso de Lenguajes Formales/Compiladores, aplicada
# sobre el TAC de UNA subrutina (antes de traducir a código objetivo,
# Etapa 12.11): para cada instrucción i, dos conjuntos de nombres
# (variables/temporales) --
#   USE[i]  lo que la instrucción LEE
#   DEF[i]  lo que la instrucción ESCRIBE
# -- y dos más, calculados por un punto fijo hacia atrás sobre las
# ecuaciones de flujo de datos estándar:
#   IN[i]  = USE[i] ∪ (OUT[i] - DEF[i])
#   OUT[i] = ∪ IN[s] para cada sucesor s de i
# El grafo de flujo se construye a nivel de INSTRUCCIÓN individual (no de
# bloque básico -- matemáticamente equivalente, más simple de construir
# directamente sobre la lista lineal de TAC con label/goto/if_false que ya
# produce `GeneradorIR`).
#
# Con IN/OUT calculados, el RANGO DE VIDA de una variable es el intervalo
# [primera aparición, última aparición] entre todos los puntos donde está
# viva (simplificación estándar de un asignador linear-scan simple --
# puede sobrestimar el rango si la variable tiene huecos de vida, p. ej.
# a través de un ciclo; un asignador de producción particiona rangos con
# huecos, fuera de alcance aquí). `asignar_registros` es el algoritmo
# clásico de Poletto & Sarkar: recorre los rangos ordenados por inicio,
# mantiene una lista de rangos "activos" con un registro fijo cada uno, y
# cuando se necesitan más de `k` a la vez, hace SPILL del activo con el
# fin MÁS LEJANO (si termina después que el nuevo rango) -- la heurística
# "spill furthest", que minimiza spills totales en el caso simple.

def _usos_defs_instr(ins):
    """USE/DEF de una sola instrucción TAC (ver comentario de sección)."""
    def _s(x):
        return {x} if isinstance(x, str) else set()

    op = ins.op
    if op in ('label', 'goto'):
        return set(), set()
    if op == 'const':
        return set(), _s(ins.resultado)
    if op in ('copy', 'neg', 'not', 'a_float'):
        return _s(ins.arg1), _s(ins.resultado)
    if op in _BINOPS:
        return _s(ins.arg1) | _s(ins.arg2), _s(ins.resultado)
    if op in ('if_false', 'param', 'return', 'print'):
        return _s(ins.arg1), set()
    if op in ('call', 'read'):
        return set(), _s(ins.resultado)
    # array_*/try_*: fuera del alcance real de generar_objetivo (Etapa
    # 12.11) -- se cubren aquí de forma conservadora (cualquier argumento
    # de tipo str cuenta como uso) para que calcular_liveness no falle si
    # se le da TAC de ese subconjunto más amplio.
    usados = set()
    for campo in (ins.arg1, ins.arg2, ins.arg3):
        usados |= _s(campo)
    return usados, _s(ins.resultado)


def calcular_liveness(instrucciones):
    """Punto fijo hacia atrás sobre IN[i]/OUT[i] (ver comentario de
    sección). Retorna (vivo_in, vivo_out): dos listas de sets[str], una
    entrada por instrucción, en el mismo orden que `instrucciones`."""
    n = len(instrucciones)
    etiquetas = {ins.arg1: i for i, ins in enumerate(instrucciones) if ins.op == 'label'}

    sucesores = []
    for i, ins in enumerate(instrucciones):
        if ins.op == 'goto':
            sucesores.append([etiquetas[ins.arg1]])
        elif ins.op == 'if_false':
            s = [etiquetas[ins.arg2]]
            if i + 1 < n:
                s.append(i + 1)
            sucesores.append(s)
        elif ins.op == 'return':
            sucesores.append([])
        else:
            sucesores.append([i + 1] if i + 1 < n else [])

    usos_por_instr = []
    defs_por_instr = []
    for ins in instrucciones:
        u, d = _usos_defs_instr(ins)
        usos_por_instr.append(u)
        defs_por_instr.append(d)

    vivo_in = [set() for _ in range(n)]
    vivo_out = [set() for _ in range(n)]
    cambio = True
    while cambio:
        cambio = False
        for i in range(n - 1, -1, -1):
            nuevo_out = set()
            for s in sucesores[i]:
                nuevo_out |= vivo_in[s]
            nuevo_in = usos_por_instr[i] | (nuevo_out - defs_por_instr[i])
            if nuevo_in != vivo_in[i] or nuevo_out != vivo_out[i]:
                cambio = True
                vivo_in[i] = nuevo_in
                vivo_out[i] = nuevo_out
    return vivo_in, vivo_out


def calcular_rangos_vida(instrucciones, vivo_in, vivo_out):
    """Rango de vida [inicio, fin] de cada variable/temporal -- el índice
    de instrucción MÍNIMO y MÁXIMO en el que aparece viva (en `vivo_in` o
    `vivo_out`). Retorna dict nombre -> (inicio, fin)."""
    rangos = {}
    for i in range(len(instrucciones)):
        for v in (vivo_in[i] | vivo_out[i]):
            if v not in rangos:
                rangos[v] = [i, i]
            else:
                if i < rangos[v][0]:
                    rangos[v][0] = i
                if i > rangos[v][1]:
                    rangos[v][1] = i
    return {v: tuple(r) for v, r in rangos.items()}


def asignar_registros(rangos, k=4):
    """Asignador linear-scan simple (Poletto & Sarkar) sobre los rangos de
    vida de `calcular_rangos_vida`, con `k` registros disponibles.
    Retorna (asignacion, spills):
      asignacion: dict nombre -> 'R0'..'R{k-1}' (registro) o el propio
                  `nombre` (sin cambios -- spill, se queda en memoria).
      spills: list[str] de los nombres que terminaron en memoria, en el
              orden en que se decidió el spill (para reportar/verificar)."""
    orden = sorted(rangos.items(), key=lambda par: par[1][0])
    libres = [f'R{i}' for i in range(k)]
    activos = []  # lista de (fin, nombre, registro)
    asignacion = {}
    spills = []

    def _expirar(inicio):
        nonlocal activos
        aun_activos = []
        for fin, nombre, reg in activos:
            if fin < inicio:
                libres.append(reg)
            else:
                aun_activos.append((fin, nombre, reg))
        activos = aun_activos

    for nombre, (inicio, fin) in orden:
        _expirar(inicio)
        if libres:
            reg = libres.pop(0)
            asignacion[nombre] = reg
            activos.append((fin, nombre, reg))
            activos.sort()
        else:
            activos.sort()
            fin_lejano, nombre_lejano, reg_lejano = activos[-1]
            if fin_lejano > fin:
                # El activo de fin más lejano cede su registro al rango
                # nuevo (que termina antes) y se manda a memoria.
                asignacion[nombre] = reg_lejano
                asignacion[nombre_lejano] = nombre_lejano
                spills.append(nombre_lejano)
                activos[-1] = (fin, nombre, reg_lejano)
                activos.sort()
            else:
                # El propio rango nuevo termina después que todos los
                # activos: se manda a memoria (sin desplazar a nadie).
                asignacion[nombre] = nombre
                spills.append(nombre)
    return asignacion, spills


def generar_objetivo_subrutina(instrucciones, asignacion=None):
    """Traduce el TAC de UNA subrutina (ya generada por `GeneradorIR`,
    optimizada o no) a una lista de `InstrObjetivo`.

    `asignacion` (Etapa 12.12, opcional): dict nombre_TAC -> nombre final
    ('R0'..'R{k-1}' si se le asignó registro, o el propio nombre si quedó
    en memoria por spill) producido por `asignar_registros`. Cuando se
    pasa, cada LOAD/STORE emitido usa el nombre YA renombrado en vez del
    nombre de variable/temporal original -- es la ÚNICA diferencia con el
    código objetivo sin asignación de registros: mismas instrucciones,
    mismo ISA, solo cambia qué cadena identifica cada valor (el ISA de
    juguete no distingue "registro" de "memoria" en tiempo de ejecución,
    solo en el NOMBRE -- ver MaquinaObjetivo, que usa un dict plano para
    ambos por igual)."""
    def _ren(nombre):
        if asignacion is None or nombre is None:
            return nombre
        return asignacion.get(nombre, nombre)

    salida = []
    for ins in instrucciones:
        op = ins.op
        if op in _NO_SOPORTADOS_OBJETIVO:
            raise NoSoportadoObjetivo(
                f'"{op}" no está soportado por el generador de código '
                f'objetivo (alcance: subconjunto estructurado sin arreglos '
                f'ni try/catch). Ver ir.py, sección "Etapa 12.11".')
        if op == 'label':
            salida.append(InstrObjetivo('LABEL', ins.arg1))
        elif op == 'const':
            salida.append(InstrObjetivo('PUSH', ins.arg1))
            salida.append(InstrObjetivo('STORE', _ren(ins.resultado)))
        elif op == 'copy':
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
            salida.append(InstrObjetivo('STORE', _ren(ins.resultado)))
        elif op in _BINOPS:
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg2)))
            salida.append(InstrObjetivo(_MAPA_BINOP_OBJETIVO[op]))
            salida.append(InstrObjetivo('STORE', _ren(ins.resultado)))
        elif op == 'neg':
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
            salida.append(InstrObjetivo('NEG'))
            salida.append(InstrObjetivo('STORE', _ren(ins.resultado)))
        elif op == 'not':
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
            salida.append(InstrObjetivo('NOT'))
            salida.append(InstrObjetivo('STORE', _ren(ins.resultado)))
        elif op == 'a_float':
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
            salida.append(InstrObjetivo('CVTF'))
            salida.append(InstrObjetivo('STORE', _ren(ins.resultado)))
        elif op == 'goto':
            salida.append(InstrObjetivo('JMP', ins.arg1))
        elif op == 'if_false':
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
            salida.append(InstrObjetivo('JZ', ins.arg2))
        elif op == 'param':
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
            salida.append(InstrObjetivo('PUSHPARAM'))
        elif op == 'call':
            if ins.resultado is not None:
                salida.append(InstrObjetivo('CALL', ins.arg1, ins.arg2))
                salida.append(InstrObjetivo('STORE', _ren(ins.resultado)))
            else:
                salida.append(InstrObjetivo('CALLV', ins.arg1, ins.arg2))
        elif op == 'return':
            if ins.arg1 is not None:
                salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
                salida.append(InstrObjetivo('RETV'))
            else:
                salida.append(InstrObjetivo('RET'))
        elif op == 'print':
            salida.append(InstrObjetivo('LOAD', _ren(ins.arg1)))
            salida.append(InstrObjetivo('PRINT'))
        else:
            raise NoSoportadoObjetivo(
                f'"{op}" no está soportado por el generador de código objetivo.')
    return salida


def generar_objetivo_programa(subrutinas, k_registros=None):
    """Traduce TODAS las subrutinas de un programa (dict nombre ->
    (parametros, instrucciones), la misma forma que retorna
    `generar_programa`/`optimizar_programa`) a código objetivo.

    `k_registros` (Etapa 12.12, opcional): si se da, cada subrutina pasa
    primero por `calcular_liveness` + `asignar_registros` (linear-scan,
    `k_registros` registros) ANTES de traducir a InstrObjetivo -- el
    código generado usa 'R0'..'R{k-1}' en vez de nombres de temporal
    arbitrarios, con spill a memoria (nombre original) cuando no alcanzan.

    Retorna (dict nombre -> (parametros, list[InstrObjetivo]),
    dict nombre -> (asignacion, spills) -- vacío si `k_registros` es
    None), mismo contrato de "resumen aparte" que ya usa
    `optimizar_programa`."""
    resultado = {}
    resumen = {}
    for nombre, (params, instrs) in subrutinas.items():
        asignacion = None
        if k_registros:
            vivo_in, vivo_out = calcular_liveness(instrs)
            rangos = calcular_rangos_vida(instrs, vivo_in, vivo_out)
            asignacion, spills = asignar_registros(rangos, k_registros)
            resumen[nombre] = (asignacion, spills)
            params = [asignacion.get(p, p) for p in params]
        resultado[nombre] = (params, generar_objetivo_subrutina(instrs, asignacion))
    return resultado, resumen


def formatear_objetivo(instrucciones):
    """Texto legible de una lista de InstrObjetivo, una por línea."""
    return '\n'.join(repr(ins) for ins in instrucciones)


class MaquinaObjetivo:
    """Ejecuta el ISA de juguete generado por `generar_objetivo_programa`
    -- una máquina de pila de operandos por marco de llamada, con las
    mismas dos capas de ámbito que `MaquinaTAC` (globales compartidas +
    un marco plano por llamada activa). Sirve para comprobar que la
    traducción TAC -> objetivo preserva el resultado: mismo criterio de
    paridad que ya se usa entre `--run-ir` y el intérprete de árbol."""

    def __init__(self, subrutinas, ir_globales):
        self.subrutinas = subrutinas  # nombre -> (parametros, instrucciones_objetivo)
        self.ir_globales = ir_globales  # TAC (sin traducir) de las declaraciones globales
        self.globales = {}
        self.salida = []
        self.entrada = []

    def ejecutar(self, entrada=None):
        self.entrada = list(entrada) if entrada else []
        self.salida = []
        self.globales = {}
        # Las declaraciones globales son TAC sin traducir -- se ejecutan con
        # la misma lógica que MaquinaTAC (no hay control de flujo real en
        # ellas, solo 'const'/'copy'/binops), reutilizada aquí sin duplicar
        # código.
        MaquinaTAC({}, self.ir_globales)._ejecutar_lista(self.ir_globales, self.globales)
        self._llamar('main', [])
        return self.salida

    def _llamar(self, nombre, argumentos):
        if builtins.es_built_in(nombre):
            try:
                return builtins.ejecutar_built_in(nombre, argumentos)
            except builtins.BuiltInError as e:
                raise ErrorEjecucionTAC(e.codigo, e.mensaje)
        entrada_sub = self.subrutinas.get(nombre)
        if entrada_sub is None:
            raise RuntimeError(f'subrutina no encontrada en el código objetivo: "{nombre}"')
        parametros, instrucciones = entrada_sub
        marco = dict(zip(parametros, argumentos))
        return self._ejecutar_lista(instrucciones, marco)

    def _contenedor(self, nombre, marco):
        return marco if nombre in marco else self.globales

    def _leer_var(self, nombre, marco):
        return self._contenedor(nombre, marco).get(nombre)

    def _escribir_var(self, nombre, valor, marco):
        cont = marco if nombre in marco else (self.globales if nombre in self.globales else marco)
        cont[nombre] = valor

    def _ejecutar_lista(self, instrucciones, marco):
        etiquetas = {ins.arg1: i for i, ins in enumerate(instrucciones) if ins.op == 'LABEL'}
        pila = []            # pila de operandos
        pila_params = []     # argumentos pendientes (PUSHPARAM), como MaquinaTAC
        i = 0
        n = len(instrucciones)
        while i < n:
            ins = instrucciones[i]
            op = ins.op
            if op == 'LABEL':
                pass
            elif op == 'PUSH':
                pila.append(ins.arg1)
            elif op == 'LOAD':
                pila.append(self._leer_var(ins.arg1, marco))
            elif op == 'STORE':
                self._escribir_var(ins.arg1, pila.pop(), marco)
            elif op in ('ADD', 'SUB', 'MUL', 'DIV', 'MOD',
                       'CMPEQ', 'CMPNE', 'CMPLT', 'CMPLE', 'CMPGT', 'CMPGE'):
                b = pila.pop()
                a = pila.pop()
                simbolo = {v: k for k, v in _MAPA_BINOP_OBJETIVO.items()}[op]
                try:
                    pila.append(_calcular_binop(simbolo, a, b))
                except ZeroDivisionError:
                    if simbolo == '/' and (_es_real(a) or _es_real(b)):
                        raise ErrorEjecucionTAC(
                            'IL-EJE-002',
                            'Operación de punto flotante inválida: división entre 0.0')
                    raise ErrorEjecucionTAC(
                        'IL-EJE-006',
                        'División por cero' if simbolo == '/' else 'División por cero en módulo')
            elif op == 'NEG':
                pila.append(-pila.pop())
            elif op == 'NOT':
                pila.append(not pila.pop())
            elif op == 'CVTF':
                v = pila.pop()
                pila.append(float(v) if _es_entero(v) else v)
            elif op == 'JMP':
                i = etiquetas[ins.arg1]
                continue
            elif op == 'JZ':
                if not pila.pop():
                    i = etiquetas[ins.arg1]
                    continue
            elif op == 'PUSHPARAM':
                pila_params.append(pila.pop())
            elif op in ('CALL', 'CALLV'):
                nombre_f, nargs = ins.arg1, ins.arg2
                args = pila_params[len(pila_params) - nargs:] if nargs else []
                del pila_params[len(pila_params) - nargs:]
                valor = self._llamar(nombre_f, args)
                if op == 'CALL':
                    pila.append(valor)
            elif op == 'RETV':
                return pila.pop()
            elif op == 'RET':
                return None
            elif op == 'PRINT':
                self._escribir_salida(pila.pop())
            else:
                raise RuntimeError(f'operación de código objetivo no soportada: {op}')
            i += 1
        return None

    def _escribir_salida(self, valor):
        if isinstance(valor, bool):
            s = 'true' if valor else 'false'
        elif isinstance(valor, float):
            s = str(valor)
        elif valor is None:
            s = 'void'
        else:
            s = str(valor)
        self.salida.append(s)
