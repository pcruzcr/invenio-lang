# Módulo de Código Intermedio de InvenioLang (Etapa 5, Fase 2)
#
# Cierra las tres etapas del "back end" clásico de un compilador que la
# v1.0/v2.0 nunca tuvieron (interpreter.py es un intérprete de árbol, nunca
# genera nada): código de tres direcciones (TAC), optimización sobre ese
# TAC, y un motor de ejecución separado (MaquinaTAC) que lo interpreta.
# Patrones aplicados: Factory (Instrucciones TAC), Strategy (pasadas de
# optimización intercambiables), Builder (construcción TAC), Visitor (recorrido
# AST → TAC), Decorator (instrumentación), Template Method (pipeline TAC)
from __future__ import annotations

from . import builtins

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
from .ast_nodes import (
    ArrayAccess,
    ArrayDecl,
    ArrayLValue,
    AssignStmt,
    BinaryOp,
    BreakStmt,
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
    Identifier,
    IfStmt,
    IncDecStmt,
    Literal,
    MatrixAccess,
    MatrixDecl,
    MatrixLValue,
    MemberAccess,
    PrintStmt,
    ReadStmt,
    ReturnStmt,
    SwitchStmt,
    TernaryExpr,
    TryStmt,
    UnaryOp,
    VarDecl,
    VarLValue,
    WhileStmt,
)
from .i18n import M, t, texto
from .patterns import RegistryFactory

# Bit a bit (Etapa 11): el generador ya emitía estos operadores tal cual
# venían del AST, pero ni MaquinaTAC ni el plegado los conocían, así que
# cualquier programa con `&`, `|`, `^`, `<<` o `>>` fallaba con
# "operación de IR no soportada" bajo --run-ir (pruebas/bit_a_bit.inv).
_BINOPS = {
    "+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=",
    "&", "|", "^", "<<", ">>",
}  # fmt: skip
# Operaciones unarias puras -> símbolo con que se imprimen. `bnot` (`~x`,
# complemento a uno) antes se traducía a `not` (negación lógica): `~5`
# daba `false` en vez de `-6`.
_UNOPS = {"neg": "-", "not": "!", "bnot": "~"}
_VALORES_POR_DEFECTO = {"int": 0, "float": 0.0, "string": "", "bool": False}


class Temp(str):
    """Nombre de un temporal generado por `GeneradorIR` (`t1`, `t2`, ...).

    Se imprime igual que un `str`, pero se distingue por tipo. Antes los
    temporales se reconocían por el prefijo `"t"`, y eso confundía a
    variables del programa como `tam`, `total` o `t`: la eliminación de
    código muerto borraba `tam = const 0` de las globales y `--run-ir-opt`
    terminaba operando con `None` (pruebas/monticulo.inv, arbol_b.inv).
    Además un temporal siempre vive en el marco de la llamada actual; nunca
    se comparte con las globales ni entre llamadas recursivas.
    """

    __slots__ = ()


class Local(str):
    """Destino de una DECLARACIÓN local (`int x = ...;` dentro de una subrutina).

    Marca que el nombre nace en el marco actual aunque exista una global
    homónima: sin esta marca, `MaquinaTAC` escribía la variable local sobre
    la global (sombreado roto).
    """

    __slots__ = ()


class _Matriz(list):
    """Arreglo row-major que recuerda su número de columnas en ejecución.

    Hace falta para indexar un parámetro `int [][] m`, cuyas columnas no se
    conocen al generar el TAC de la subrutina.
    """

    __slots__ = ("cols",)


def _es_nombre_de_marco(nombre):
    """True si `nombre` siempre vive en el marco actual (temporal o local)."""
    return isinstance(nombre, (Temp, Local))


class NoSoportadoIR(Exception):
    """El programa usa una construcción fuera del subconjunto que cubre el.

    generador de código intermedio (POO o matrices).
    """


class ErrorEjecucionTAC(Exception):
    """Error de ejecución detectado por MaquinaTAC, con `codigo`/`mensaje`.

    al estilo del catálogo IL-EJE-* (ver interpreter.py::RuntimeError_).
    No replica el catálogo completo -- solo división/módulo por cero e
    índice de arreglo fuera de rango -- pero es real: es lo que un
    try/catch (Etapa 6) ejecutado con --run-ir efectivamente captura.
    """

    def __init__(self, codigo, mensaje):
        self.codigo = codigo
        self.mensaje = mensaje
        super().__init__(codigo, mensaje)

    def __str__(self):
        # INV-1400: `mensaje` puede ser un Mensaje diferido; se presenta al
        # convertir a texto (idioma del proceso), no al crear la excepcion.
        return f"[{self.codigo}] {self.mensaje}"


class Instr:
    """Una instrucción de código de tres direcciones (cuádrupla).

    El significado de `arg1`/`arg2`/`arg3` depende de `op`; ver los
    comentarios de `GeneradorIR` para el significado de cada operación.
    Los operandos que son nombres de variable/temporal son `str`; el único
    lugar donde un operando es un valor literal "en crudo" es `arg1` de
    `const` (y el tamaño literal de `array_new`).
    """

    __slots__ = ("op", "arg1", "arg2", "arg3", "resultado")

    def __init__(self, op, arg1=None, arg2=None, arg3=None, resultado=None):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.arg3 = arg3
        self.resultado = resultado

    def __repr__(self):
        op, a1, a2, a3, r = self.op, self.arg1, self.arg2, self.arg3, self.resultado
        if op == "label":
            return f"{a1}:"
        if op == "goto":
            return f"    goto {a1}"
        if op == "if_false":
            return f"    if_false {a1} goto {a2}"
        if op == "const":
            return f"    {r} = const {a1!r}"
        if op == "copy":
            return f"    {r} = {a1}"
        if op in _UNOPS:
            return f"    {r} = {_UNOPS[op]}{a1}"
        if op == "ncols":
            return f"    {r} = ncols({a1})"
        if op == "a_float":
            return f"    {r} = (float) {a1}"
        if op == "param":
            return f"    param {a1}"
        if op == "call":
            return f"    {r} = call {a1}, {a2}" if r else f"    call {a1}, {a2}"
        if op == "return":
            return f"    return {a1}" if a1 is not None else "    return"
        if op == "print":
            return f"    print {a1}"
        if op == "read":
            return f"    {r} = read({a1})"
        if op == "array_new":
            return f"    {a1} = new_array[{a2}]"
        if op == "array_get":
            return f"    {r} = {a1}[{a2}]"
        if op == "array_set":
            return f"    {a1}[{a2}] = {a3}"
        if op == "try_begin":
            return f"    try_begin catch={a1} var={a2}"
        if op == "try_end":
            return "    try_end"
        if op == "pop_manejador":
            return "    pop_manejador"
        if op in _BINOPS:
            return f"    {r} = {a1} {op} {a2}"
        return f"    {op} {a1} {a2} {a3} -> {r}"


class InstrFactory(RegistryFactory):
    """Factory para instrucciones TAC — centraliza creación y permite pooling."""

    _default: InstrFactory | None = None

    @classmethod
    def get_default(cls) -> InstrFactory:
        """Retorna la instancia compartida."""
        if cls._default is None:
            cls._default = cls()
        return cls._default

    def create_instr(self, op: str, arg1=None, arg2=None, arg3=None, resultado=None) -> Instr:
        """Crea una instrucción TAC."""
        return Instr(op, arg1, arg2, arg3, resultado)


# ============================================================
# Generación de código intermedio (AST -> TAC)
# ============================================================


class GeneradorIR:
    """Recorre el AST (ya validado por semantic.py/type_checker.py) y.

    genera TAC. Reutiliza el mismo patrón de recorrido de control de flujo
    ya resuelto en el diagrama de flujo (flujo/esquema.py) para
    if/while/for/break/continue/return,
    aquí emitiendo saltos con etiquetas en vez de geometría 2D.
    """

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
        self._tipos = {}  # nombre -> tipo declarado (para 'leer')
        self._tams = {}  # nombre de arreglo -> tam declarado (Etapa 12.1, para_cada)
        self._cols = {}  # nombre de matriz -> columnas (int o nombre de const), row-major
        # Lo que declaran las globales, visible desde toda subrutina. Antes
        # `_reiniciar` vaciaba `_cols` al empezar cada subrutina, así que una
        # matriz GLOBAL se indexaba con 10 columnas por defecto dentro de
        # las funciones (arbol_b.inv: "Índice 30 fuera de rango"), mientras
        # `_tipos`/`_tams` nunca se vaciaban y se filtraban de una subrutina
        # a la siguiente.
        self._globales_tipos = {}
        self._globales_tams = {}
        self._globales_cols = {}
        self._en_subrutina = False
        # INV-1291: pila de ámbitos de bloque de la subrutina en curso
        # (nombre fuente -> nombre TAC). El marco de MaquinaTAC es plano por
        # llamada, así que una declaración en un bloque interno que reutiliza
        # un nombre ya visible (global, parámetro o de un bloque externo) se
        # renombra a `nombre#k`: sin esto, `entero x = 1;` dentro de un `si`
        # seguía tapando a la global `x` después de cerrar el bloque.
        self._ambitos: list[dict[str, str]] = []
        self._renombres = 0
        self._tipo_retorno = "void"

    # ---- utilidades ----

    def _nuevo_temp(self):
        self._temp_n += 1
        return Temp(f"t{self._temp_n}")

    def _destino_decl(self, nombre):
        """Nombre destino de una declaración: local si estamos en una subrutina.

        Registra la declaración en el ámbito de bloque actual y, si el nombre
        ya era visible, le asigna un nombre TAC único (INV-1291).
        """
        if not self._en_subrutina:
            return nombre
        visible = nombre in self._globales_tipos or any(nombre in a for a in self._ambitos)
        destino = nombre
        if visible:
            self._renombres += 1
            destino = f"{nombre}#{self._renombres}"
        self._ambitos[-1][nombre] = destino
        return Local(destino)

    def _r(self, nombre):
        """Nombre TAC de `nombre` según los ámbitos de bloque visibles."""
        for ambito in reversed(self._ambitos):
            if nombre in ambito:
                return ambito[nombre]
        return nombre

    def _entrar_ambito(self):
        self._ambitos.append({})

    def _salir_ambito(self):
        self._ambitos.pop()

    def _gen_bloque(self, elementos):
        """Genera una lista de instrucciones dentro de un ámbito de bloque propio."""
        self._entrar_ambito()
        for e in elementos:
            self._gen_stmt(e)
        self._salir_ambito()

    def _nueva_etiqueta(self):
        self._label_n += 1
        return f"L{self._label_n}"

    def _emit(self, op, arg1=None, arg2=None, arg3=None, resultado=None):
        self.instrucciones.append(Instr(op, arg1, arg2, arg3, resultado))

    # ---- puntos de entrada ----

    def generar_globales(self, ast):
        """Genera TAC de declaraciones globales.

        para ejecutarse una sola vez antes de invocar 'main' (§5.2.3).
        """
        self._reiniciar()
        self._en_subrutina = False
        self._ambitos = []
        for d in list(ast.declaraciones_globales) + list(ast.declaraciones_posteriores):
            self._gen_declaracion_global(d)
        self._globales_tipos = dict(self._tipos)
        self._globales_tams = dict(self._tams)
        self._globales_cols = dict(self._cols)
        return self.instrucciones

    def generar_subrutina(self, parametros, bloque, tipo_retorno="void"):
        """TAC de UNA función/procedimiento.

        Retorna (nombres_parametros, instrucciones).
        """
        self._reiniciar()
        self._en_subrutina = True
        self._tipo_retorno = tipo_retorno
        self._ambitos = [{p.nombre: p.nombre for p in parametros}, {}]
        for p in parametros:
            self._tipos[p.nombre] = p.tipo
            # Un parámetro sombrea a cualquier global homónima.
            self._tams.pop(p.nombre, None)
            if getattr(p, "es_matriz", False):
                # Columnas desconocidas al generar: se leen del propio
                # arreglo en ejecución (ver op 'ncols' y _Matriz).
                self._cols[p.nombre] = None
            else:
                self._cols.pop(p.nombre, None)
        # INV-1293: un argumento int que llega a un parámetro `real` se
        # promueve al entrar (el intérprete de árbol ya lo hacía; --run-ir
        # imprimía "3" en vez de "3.0").
        for p in parametros:
            if (
                p.tipo == "float"
                and not getattr(p, "es_arreglo", False)
                and not getattr(p, "es_matriz", False)
            ):
                self._emit("a_float", p.nombre, resultado=p.nombre)
        for elem in bloque.elementos:
            self._gen_stmt(elem)
        return [p.nombre for p in parametros], self.instrucciones

    def _reiniciar(self):
        self._temp_n = 0
        self._label_n = 0
        self.instrucciones = []
        self._ctx_ciclo = []
        self._profundidad_try = 0
        self._tipos = dict(self._globales_tipos)
        self._tams = dict(self._globales_tams)
        self._cols = dict(self._globales_cols)

    def _gen_declaracion_global(self, d):
        if isinstance(d, VarDecl):
            self._tipos[d.nombre] = d.tipo
            if d.init_expr is not None:
                val = self._gen_expr(d.init_expr)
                if d.tipo == "float":
                    val = self._gen_promover_float(val)
                self._emit("copy", val, resultado=d.nombre)
            else:
                self._emit("const", _VALORES_POR_DEFECTO.get(d.tipo), resultado=d.nombre)
        elif isinstance(d, ConstDecl):
            self._tipos[d.nombre] = d.tipo
            val = self._gen_expr(d.init_expr)
            if d.tipo == "float":
                val = self._gen_promover_float(val)
            self._emit("copy", val, resultado=d.nombre)
        elif isinstance(d, ArrayDecl):
            self._gen_array_decl(d)
        elif isinstance(d, MatrixDecl):
            self._gen_matrix_decl(d)

    # ---- instrucciones ----

    def _gen_stmt(self, nodo):
        if isinstance(nodo, VarDecl):
            # El inicializador se evalúa con el ámbito ANTERIOR a la
            # declaración (`entero x = x + 1;` lee la x externa).
            val = self._gen_expr(nodo.init_expr) if nodo.init_expr is not None else None
            destino = self._destino_decl(nodo.nombre)
            self._tipos[destino] = nodo.tipo
            self._tams.pop(destino, None)
            self._cols.pop(destino, None)
            if nodo.init_expr is not None:
                if nodo.tipo == "float":
                    val = self._gen_promover_float(val)
                self._emit("copy", val, resultado=destino)
            else:
                # Sin inicializador la variable igual NACE aquí (valor por
                # defecto del tipo, como en las globales); si no se emitía
                # nada, la primera asignación posterior caía sobre una
                # global homónima.
                self._emit("const", _VALORES_POR_DEFECTO.get(nodo.tipo), resultado=destino)
        elif isinstance(nodo, ConstDecl):
            val = self._gen_expr(nodo.init_expr)
            destino = self._destino_decl(nodo.nombre)
            self._tipos[destino] = nodo.tipo
            if nodo.tipo == "float":
                val = self._gen_promover_float(val)
            self._emit("copy", val, resultado=destino)
        elif isinstance(nodo, ArrayDecl):
            self._gen_array_decl(nodo)
        elif isinstance(nodo, MatrixDecl):
            self._gen_matrix_decl(nodo)
        elif isinstance(nodo, AssignStmt):
            self._gen_asignacion(nodo.lvalue, nodo.operador, nodo.expr)
        elif isinstance(nodo, IncDecStmt):
            self._gen_incdec(self._r(nodo.nombre), nodo.operador)
        elif isinstance(nodo, PrintStmt):
            val = self._gen_expr(nodo.expr)
            self._emit("print", val)
        elif isinstance(nodo, ReadStmt):
            nombre = self._r(nodo.nombre)
            tipo = self._tipos.get(nombre, "string")
            self._emit("read", tipo, resultado=nombre)
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
            if val is not None and self._tipo_retorno == "float":
                val = self._gen_promover_float(val)  # INV-1293: `retornar 1;` en una función real
            self._emit("return", val)
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
                M("IR.no_soportado.no_esta_soportado_generador_2", clase=type(nodo).__name__)
            )

    def _gen_array_decl(self, nodo):
        valores = [self._gen_expr(e) for e in nodo.init_exprs]
        nombre = self._destino_decl(nodo.nombre)
        self._tipos[nombre] = nodo.tipo
        self._cols.pop(nombre, None)
        self._tams[nombre] = len(nodo.init_exprs) if nodo.init_exprs else nodo.tam
        if nodo.init_exprs:
            self._emit("array_new", nombre, len(valores))
            for i, val in enumerate(valores):
                self._emit("array_set", nombre, i, val)
        else:
            self._emit("array_new", nombre, nodo.tam)

    def _gen_matrix_decl(self, nodo):
        # row-major: arreglo plano de filas*cols. Una dimensión puede ser un
        # literal entero o el nombre de una constante (`int [N][M] m`); antes
        # cualquier dimensión no literal se sustituía en silencio por 10, lo
        # que daba índices equivocados con N/M distintos de 10.
        nombre = self._destino_decl(nodo.nombre)
        self._tipos[nombre] = nodo.tipo
        self._tams.pop(nombre, None)
        filas, cols = nodo.filas, nodo.cols
        for dim in (filas, cols):
            if not isinstance(dim, (int, str)) or isinstance(dim, bool):
                raise NoSoportadoIR(M("IR.no_soportado.generador_codigo_intermedio_solo"))
        self._cols[nombre] = cols
        if isinstance(filas, int) and isinstance(cols, int):
            total = filas * cols
        else:
            total = self._nuevo_temp()
            self._emit("*", filas, cols, resultado=total)
        # arg3 = columnas: MaquinaTAC crea una _Matriz que las recuerda, para
        # poder indexarla también a través de un parámetro `int [][]`.
        self._emit("array_new", nombre, total, cols)
        if nodo.init_filas:
            for r, fila in enumerate(nodo.init_filas):
                for c, e in enumerate(fila):
                    val = self._gen_expr(e)
                    if isinstance(cols, int):
                        idx = r * cols + c
                    else:
                        t_mul = self._nuevo_temp()
                        self._emit("*", r, cols, resultado=t_mul)
                        idx = self._nuevo_temp()
                        self._emit("+", t_mul, c, resultado=idx)
                    self._emit("array_set", nombre, idx, val)

    def _gen_indice_matriz(self, nombre, fila_expr, col_expr):
        """TAC del índice row-major `fila * cols + col` de `nombre[fila][col]`.

        `nombre` ya es el nombre TAC (resuelto con `_r`).
        """
        fila = self._gen_expr(fila_expr)
        col = self._gen_expr(col_expr)
        if nombre not in self._cols:
            raise NoSoportadoIR(
                M("IR.no_soportado.matriz_sin_dimensiones_conocidas", nombre=nombre)
            )
        cols = self._cols[nombre]
        if cols is None:  # parámetro `int [][] m`: columnas en ejecución
            cols = self._nuevo_temp()
            self._emit("ncols", nombre, resultado=cols)
        t_mul = self._nuevo_temp()
        self._emit("*", fila, cols, resultado=t_mul)
        t_idx = self._nuevo_temp()
        self._emit("+", t_mul, col, resultado=t_idx)
        return t_idx

    def _gen_promover_float(self, val):
        """Promueve int a float en TAC.

        en tiempo de ejecución, lo convierte a float (es una decisión que
        solo puede tomarse en tiempo de ejecución, así que se emite como
        instrucción, no se decide aquí).
        """
        t = self._nuevo_temp()
        self._emit("a_float", val, resultado=t)
        return t

    def _gen_asignacion(self, lvalue, operador, expr):
        val = self._gen_expr(expr)
        destino_float = (
            isinstance(lvalue, VarLValue) and self._tipos.get(self._r(lvalue.nombre)) == "float"
        )
        if destino_float:
            val = self._gen_promover_float(val)
        if operador != "=":
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
        self._emit("+" if operador == "++" else "-", nombre, 1, resultado=t)
        self._emit("copy", t, resultado=nombre)

    def _gen_lvalue_read(self, lvalue):
        if isinstance(lvalue, VarLValue):
            return self._r(lvalue.nombre)
        if isinstance(lvalue, ArrayLValue):
            idx = self._gen_expr(lvalue.indice)
            t = self._nuevo_temp()
            self._emit("array_get", self._r(lvalue.nombre), idx, resultado=t)
            return t
        if isinstance(lvalue, MatrixLValue):
            nombre = self._r(lvalue.nombre)
            t_idx = self._gen_indice_matriz(nombre, lvalue.fila, lvalue.columna)
            t = self._nuevo_temp()
            self._emit("array_get", nombre, t_idx, resultado=t)
            return t
        raise NoSoportadoIR(
            M("IR.no_soportado.lvalue_fuera_subconjunto_estructurado", clase=type(lvalue).__name__)
        )

    def _gen_lvalue_write(self, lvalue, valor):
        if isinstance(lvalue, VarLValue):
            self._emit("copy", valor, resultado=self._r(lvalue.nombre))
        elif isinstance(lvalue, ArrayLValue):
            idx = self._gen_expr(lvalue.indice)
            self._emit("array_set", self._r(lvalue.nombre), idx, valor)
        elif isinstance(lvalue, MatrixLValue):
            nombre = self._r(lvalue.nombre)
            t_idx = self._gen_indice_matriz(nombre, lvalue.fila, lvalue.columna)
            self._emit("array_set", nombre, t_idx, valor)
        else:
            raise NoSoportadoIR(
                M(
                    "IR.no_soportado.lvalue_fuera_subconjunto_estructurado",
                    clase=type(lvalue).__name__,
                )
            )

    def _gen_if(self, nodo):
        cond = self._gen_expr(nodo.condicion)
        etq_else = self._nueva_etiqueta()
        self._emit("if_false", cond, etq_else)
        self._gen_bloque(nodo.bloque_then.elementos)
        if nodo.bloque_else is not None:
            etq_fin = self._nueva_etiqueta()
            self._emit("goto", etq_fin)
            self._emit("label", etq_else)
            self._gen_bloque(nodo.bloque_else.elementos)
            self._emit("label", etq_fin)
        else:
            self._emit("label", etq_else)

    def _gen_while(self, nodo):
        etq_inicio = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        self._emit("label", etq_inicio)
        cond = self._gen_expr(nodo.condicion)
        self._emit("if_false", cond, etq_fin)
        self._ctx_ciclo.append(("loop", etq_inicio, etq_fin, self._profundidad_try))
        self._gen_bloque(nodo.bloque.elementos)
        self._ctx_ciclo.pop()
        self._emit("goto", etq_inicio)
        self._emit("label", etq_fin)

    def _gen_foreach(self, nodo):
        """TAC de para_cada/foreach (Etapa 12.1): solo soportado sobre un.

        arreglo LOCAL de tamaño estático conocido (`self._tams`, poblado
        por `_gen_array_decl`) -- ir.py ya no soporta arreglos de
        parámetro en ningún otro punto (no hay 'PARAM_ARREGLO' en todo
        este módulo), así que esto no reduce el alcance ya existente, solo
        lo hereda. Se traduce a un bucle indexado explícito con
        `array_get`, equivalente a como un estudiante lo escribiría a
        mano con un `for` clásico.
        """
        arreglo = self._r(nodo.arreglo.nombre) if isinstance(nodo.arreglo, Identifier) else None
        tam = self._tams.get(arreglo) if arreglo is not None else None
        if tam is None:
            raise NoSoportadoIR(M("IR.no_soportado.cada_foreach_solo_esta"))
        idx = self._nuevo_temp()
        self._emit("const", 0, resultado=idx)
        etq_inicio = self._nueva_etiqueta()
        etq_continuar = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        self._emit("label", etq_inicio)
        cond = self._nuevo_temp()
        self._emit("<", idx, tam, resultado=cond)
        self._emit("if_false", cond, etq_fin)
        self._entrar_ambito()
        destino = self._destino_decl(nodo.nombre)
        self._tipos[destino] = nodo.tipo
        self._emit("array_get", arreglo, idx, resultado=destino)
        self._ctx_ciclo.append(("loop", etq_continuar, etq_fin, self._profundidad_try))
        self._gen_bloque(nodo.bloque.elementos)
        self._ctx_ciclo.pop()
        self._salir_ambito()
        self._emit("label", etq_continuar)
        t = self._nuevo_temp()
        self._emit("+", idx, 1, resultado=t)
        self._emit("copy", t, resultado=idx)
        self._emit("goto", etq_inicio)
        self._emit("label", etq_fin)

    def _gen_for(self, nodo):
        self._entrar_ambito()  # la variable del encabezado es local al ciclo
        if nodo.init_stmt is not None:
            self._gen_for_init_act(nodo.init_stmt)
        etq_inicio = self._nueva_etiqueta()
        etq_continuar = self._nueva_etiqueta()  # 'continue' salta al ACT, no directo a la condicion
        etq_fin = self._nueva_etiqueta()
        self._emit("label", etq_inicio)
        if nodo.cond_expr is not None:
            cond = self._gen_expr(nodo.cond_expr)
            self._emit("if_false", cond, etq_fin)
        self._ctx_ciclo.append(("loop", etq_continuar, etq_fin, self._profundidad_try))
        self._gen_bloque(nodo.bloque.elementos)
        self._ctx_ciclo.pop()
        self._emit("label", etq_continuar)
        if nodo.act_stmt is not None:
            self._gen_for_init_act(nodo.act_stmt)
        self._emit("goto", etq_inicio)
        self._emit("label", etq_fin)
        self._salir_ambito()

    def _gen_do_while(self, nodo):
        """do/hacer ... while/mientras (Etapa 6): el cuerpo corre al menos.

        una vez; `continue` salta a re-evaluar la condición (no directo al
        inicio del cuerpo).
        """
        etq_inicio = self._nueva_etiqueta()
        etq_continuar = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        self._emit("label", etq_inicio)
        self._ctx_ciclo.append(("loop", etq_continuar, etq_fin, self._profundidad_try))
        self._gen_bloque(nodo.bloque.elementos)
        self._ctx_ciclo.pop()
        self._emit("label", etq_continuar)
        cond = self._gen_expr(nodo.condicion)
        self._emit("if_false", cond, etq_fin)
        self._emit("goto", etq_inicio)
        self._emit("label", etq_fin)

    def _gen_switch(self, nodo):
        """switch/segun (Etapa 6): cadena de comparaciones (no una tabla de.

        saltos O(1) -- suficiente para el tamaño típico de un switch
        didáctico) que salta al primer case coincidente; los cuerpos de los
        case se emiten en secuencia SIN goto entre ellos, así que caen al
        siguiente por sí solos (fallthrough, semántica C) salvo que haya un
        `break`.
        """
        valor = self._gen_expr(nodo.expr)
        etq_fin = self._nueva_etiqueta()
        etq_casos = [self._nueva_etiqueta() for _ in nodo.casos]
        etq_default = self._nueva_etiqueta() if nodo.bloque_default is not None else etq_fin

        for etq, caso in zip(etq_casos, nodo.casos, strict=True):
            t_const = self._nuevo_temp()
            self._emit("const", caso.valor.valor, resultado=t_const)
            t_neq = self._nuevo_temp()
            self._emit("!=", valor, t_const, resultado=t_neq)
            # t_neq es False exactamente cuando valor == const -> if_false
            # salta a la etiqueta del case, sin necesitar un "if_true".
            self._emit("if_false", t_neq, etq)
        self._emit("goto", etq_default)

        self._ctx_ciclo.append(("switch", etq_fin, self._profundidad_try))
        self._entrar_ambito()  # un solo ámbito para todo el cuerpo (semántica C)
        for etq, caso in zip(etq_casos, nodo.casos, strict=True):
            self._emit("label", etq)
            for e in caso.bloque.elementos:
                self._gen_stmt(e)
        if nodo.bloque_default is not None:
            self._emit("label", etq_default)
            for e in nodo.bloque_default.elementos:
                self._gen_stmt(e)
        self._salir_ambito()
        self._ctx_ciclo.pop()
        self._emit("label", etq_fin)

    def _gen_try(self, nodo):
        """try/intentar ... catch/capturar genérico (Etapa 6): `try_begin`.

        registra en MaquinaTAC un manejador activo (etiqueta + nombre de la
        variable de catch) que se desactiva con `try_end` al salir
        normalmente, o se consume al capturar un error -- ver
        MaquinaTAC._ejecutar_lista. El acceso a `nombre.codigo`/
        `nombre.mensaje` dentro del catch se resuelve en `_gen_expr`
        (MemberAccess) leyendo directamente las variables sintéticas que el
        manejador deja escritas.
        """
        etq_catch = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        self._emit("try_begin", etq_catch, nodo.nombre_catch)
        self._profundidad_try += 1
        self._gen_bloque(nodo.bloque_try.elementos)
        self._profundidad_try -= 1
        self._emit("try_end")
        self._emit("goto", etq_fin)
        self._emit("label", etq_catch)
        self._gen_bloque(nodo.bloque_catch.elementos)
        self._emit("label", etq_fin)

    def _emit_pops_manejadores(self, profundidad_objetivo):
        """Antes de un break/continue que salta fuera de uno o más try.

        activos, cierra esos manejadores (si no, quedarían "colgados" y
        podrían capturar por error algo que ocurra después del ciclo).
        """
        for _ in range(self._profundidad_try - profundidad_objetivo):
            self._emit("pop_manejador")

    def _emit_break(self):
        for entrada in reversed(self._ctx_ciclo):
            if entrada[0] == "loop":
                _, _, etq_break, prof = entrada
            elif entrada[0] == "switch":
                _, etq_break, prof = entrada
            else:
                continue
            self._emit_pops_manejadores(prof)
            self._emit("goto", etq_break)
            return
        raise NoSoportadoIR(M("IR.no_soportado.break_fuera_ciclo_switch"))

    def _emit_continue(self):
        for entrada in reversed(self._ctx_ciclo):
            if entrada[0] == "loop":
                _, etq_continuar, _, prof = entrada
                self._emit_pops_manejadores(prof)
                self._emit("goto", etq_continuar)
                return
        raise NoSoportadoIR(M("IR.no_soportado.continue_fuera_ciclo_no"))

    def _gen_for_init_act(self, nodo):
        if isinstance(nodo, ForInitVar):
            val = self._gen_expr(nodo.init_expr) if nodo.init_expr is not None else None
            destino = self._destino_decl(nodo.nombre)
            self._tipos[destino] = nodo.tipo
            if nodo.init_expr is not None:
                if nodo.tipo == "float":
                    val = self._gen_promover_float(val)
                self._emit("copy", val, resultado=destino)
            else:
                self._emit("const", _VALORES_POR_DEFECTO.get(nodo.tipo), resultado=destino)
        elif isinstance(nodo, ForInitAsig):
            self._gen_asignacion(nodo.lvalue, nodo.operador, nodo.expr)
        elif isinstance(nodo, ForInitIncDec):
            self._gen_incdec(self._r(nodo.nombre), nodo.operador)

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
        if self._tipos.get(self._r(nombre), "").startswith("funcion("):
            raise NoSoportadoIR(M("IR.no_soportado.generador_codigo_intermedio_no_2"))
        for arg in argumentos:
            val = self._gen_expr(arg)
            self._emit("param", val)
        t = self._nuevo_temp() if quiere_valor else None
        self._emit("call", nombre, len(argumentos), resultado=t)
        return t

    # ---- expresiones ----

    def _gen_expr(self, nodo):
        """Genera TAC para una expresión y retorna el NOMBRE (variable o.

        temporal) que contiene su valor.
        """
        if isinstance(nodo, Literal):
            t = self._nuevo_temp()
            self._emit("const", nodo.valor, resultado=t)
            return t
        if isinstance(nodo, Identifier):
            nombre = self._r(nodo.nombre)
            if nombre not in self._tipos:
                # Etapa 12.6: la única razón por la que un IDENTIFICADOR ya
                # validado por semantic.py NO es una variable/parámetro
                # conocido (todo lo cual queda registrado en self._tipos al
                # generarse) es que sea una referencia bare a una función/
                # procedimiento de nivel superior pasada por valor
                # (`operar = sumar;`) -- fuera de alcance de este generador,
                # mismo criterio que _gen_llamada de arriba.
                raise NoSoportadoIR(M("IR.no_soportado.generador_codigo_intermedio_no_3"))
            return nombre
        if isinstance(nodo, ArrayAccess):
            idx = self._gen_expr(nodo.indice)
            t = self._nuevo_temp()
            self._emit("array_get", self._r(nodo.nombre), idx, resultado=t)
            return t
        if isinstance(nodo, MatrixAccess):
            nombre = self._r(nodo.nombre)
            t_idx = self._gen_indice_matriz(nombre, nodo.fila, nodo.columna)
            t = self._nuevo_temp()
            self._emit("array_get", nombre, t_idx, resultado=t)
            return t
        if isinstance(nodo, FunctionCall):
            return self._gen_llamada(nodo.nombre, nodo.argumentos, quiere_valor=True)
        if isinstance(nodo, BinaryOp):
            if nodo.operador == "&&":
                return self._gen_and(nodo)
            if nodo.operador == "||":
                return self._gen_or(nodo)
            izq = self._gen_expr(nodo.izquierda)
            der = self._gen_expr(nodo.derecha)
            t = self._nuevo_temp()
            self._emit(nodo.operador, izq, der, resultado=t)
            return t
        if isinstance(nodo, UnaryOp):
            if nodo.operador in ("++", "--"):
                return self._gen_incdec_expr(nodo)
            val = self._gen_expr(nodo.operando)
            if nodo.operador == "+":
                return val
            op = {"-": "neg", "!": "not", "~": "bnot"}.get(nodo.operador)
            if op is None:
                raise NoSoportadoIR(
                    M("IR.no_soportado.operador_unario_no_soportado", operador=nodo.operador)
                )
            t = self._nuevo_temp()
            self._emit(op, val, resultado=t)
            return t
        if isinstance(nodo, TernaryExpr):
            return self._gen_ternario(nodo)
        if (
            isinstance(nodo, MemberAccess)
            and isinstance(nodo.receptor, Identifier)
            and nodo.nombre_miembro in ("codigo", "mensaje", "code", "message")
        ):
            # Caso especial acotado (Etapa 6, NO soporte general de POO):
            # `e.codigo`/`e.mensaje` dentro de un catch -- el manejador de
            # MaquinaTAC ya dejó el valor en esta variable sintética (ver
            # _gen_try / MaquinaTAC._ejecutar_lista, op 'try_begin').
            return f"{nodo.receptor.nombre}.{nodo.nombre_miembro}"
        raise NoSoportadoIR(
            M("IR.no_soportado.no_esta_soportado_generador", clase=type(nodo).__name__)
        )

    def _gen_ternario(self, nodo):
        """Cond ? si_verdadero : si_falso (Etapa 6) -- solo se genera código.

        para la rama elegida en tiempo de ejecución (igual criterio que
        &&/||: nunca se evalúa la rama descartada).
        """
        t = self._nuevo_temp()
        etq_falso = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        cond = self._gen_expr(nodo.condicion)
        self._emit("if_false", cond, etq_falso)
        val_v = self._gen_expr(nodo.si_verdadero)
        self._emit("copy", val_v, resultado=t)
        self._emit("goto", etq_fin)
        self._emit("label", etq_falso)
        val_f = self._gen_expr(nodo.si_falso)
        self._emit("copy", val_f, resultado=t)
        self._emit("label", etq_fin)
        return t

    def _gen_incdec_expr(self, nodo):
        # el operando siempre es un Identifier simple (garantizado por la gramatica)
        nombre = self._r(nodo.operando.nombre)
        t_nuevo = self._nuevo_temp()
        self._emit("+" if nodo.operador == "++" else "-", nombre, 1, resultado=t_nuevo)
        if nodo.es_prefijo:
            self._emit("copy", t_nuevo, resultado=nombre)
            return nombre
        t_viejo = self._nuevo_temp()
        self._emit("copy", nombre, resultado=t_viejo)  # valor ANTES de sobreescribir
        self._emit("copy", t_nuevo, resultado=nombre)
        return t_viejo

    def _gen_and(self, nodo):
        # cortocircuito (§6.3.1 de la v1.0): la derecha no se evalúa si la
        # izquierda ya decide el resultado.
        t = self._nuevo_temp()
        etq_falso = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        izq = self._gen_expr(nodo.izquierda)
        self._emit("if_false", izq, etq_falso)
        der = self._gen_expr(nodo.derecha)
        self._emit("copy", der, resultado=t)
        self._emit("goto", etq_fin)
        self._emit("label", etq_falso)
        self._emit("const", False, resultado=t)
        self._emit("label", etq_fin)
        return t

    def _gen_or(self, nodo):
        t = self._nuevo_temp()
        etq_seguir = self._nueva_etiqueta()
        etq_fin = self._nueva_etiqueta()
        izq = self._gen_expr(nodo.izquierda)
        self._emit("if_false", izq, etq_seguir)
        self._emit("const", True, resultado=t)
        self._emit("goto", etq_fin)
        self._emit("label", etq_seguir)
        der = self._gen_expr(nodo.derecha)
        self._emit("copy", der, resultado=t)
        self._emit("label", etq_fin)
        return t


def generar_programa(ast):
    """Genera el IR de todo el programa. Retorna (subrutinas, ir_globales).

    donde `subrutinas` es dict nombre -> (nombres_parametros, instrucciones)
    e incluye 'main'. Lanza NoSoportadoIR si el programa usa clases/POO.
    """
    if ast.clases:
        raise NoSoportadoIR(M("IR.no_soportado.generador_codigo_intermedio_no"))
    gen = GeneradorIR()
    ir_globales = gen.generar_globales(ast)
    subrutinas = {}
    if ast.main is not None:
        subrutinas["main"] = gen.generar_subrutina([], ast.main.bloque)
    for sub in ast.subrutinas:
        subrutinas[sub.nombre] = gen.generar_subrutina(
            sub.parametros, sub.bloque, getattr(sub, "tipo_retorno", "void")
        )
    return subrutinas, ir_globales


def formatear(instrucciones):
    """Texto legible de una lista de instrucciones, una por línea."""
    return "\n".join(repr(ins) for ins in instrucciones)


# ============================================================
# Optimización (pasadas sobre el TAC)
# ============================================================


def _calcular_binop(op, a, b):
    """Misma aritmética que interpreter.py (división/módulo truncados hacia.

    cero, §4.2.2) para que el plegado de constantes y MaquinaTAC calculen
    exactamente lo mismo que el intérprete de árbol.
    """
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == ">":
        return a > b
    if op == "<=":
        return a <= b
    if op == ">=":
        return a >= b
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if _es_entero(a) and _es_entero(b):
            q = abs(a) // abs(b)
            return -q if (a < 0) != (b < 0) else q
        return a / b
    if op == "%":
        if _es_entero(a) and _es_entero(b):
            r = abs(a) % abs(b)
            return -r if a < 0 else r
        return a % b
    if op == "&":
        return a & b
    if op == "|":
        return a | b
    if op == "^":
        return a ^ b
    if op in ("<<", ">>"):
        if b < 0:
            # Igual que interpreter.py::_aplicar_binario (IL-EJE-001).
            raise ValueError(M("IL-EJE-001.desplazamiento_exponente_negativo"))
        return a << b if op == "<<" else a >> b
    raise ValueError(f"operador no soportado: {op}")


def _calcular_unop(op, v):
    if op == "neg":
        return -v
    if op == "not":
        return not v
    if op == "bnot":
        return ~v
    raise ValueError(f"operador unario no soportado: {op}")


def _es_entero(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _es_real(v):
    return isinstance(v, float)


def plegado_constantes(instrucciones):
    """Plegado + propagación de constantes en una sola pasada hacia.

    adelante: sigue qué nombres tienen actualmente un valor constante
    conocido, propaga ese valor a los usos, y si TODOS los operandos de una
    operación quedan constantes, la reduce a una única instrucción `const`.
    Una `label` es un punto de unión de varios caminos posibles, así que
    invalida todo lo que se sabía hasta ahí (conservador pero correcto).
    """
    constantes = {}
    nuevas = []
    cambios = 0
    for ins in instrucciones:
        if ins.op == "label":
            constantes.clear()
            nuevas.append(ins)
            continue
        if ins.op == "const":
            constantes[ins.resultado] = ins.arg1
            nuevas.append(ins)
            continue
        if ins.op == "copy" and isinstance(ins.arg1, str) and ins.arg1 in constantes:
            valor = constantes[ins.arg1]
            nuevas.append(Instr("const", valor, resultado=ins.resultado))
            constantes[ins.resultado] = valor
            cambios += 1
            continue
        if (
            ins.op in _BINOPS
            and isinstance(ins.arg1, str)
            and isinstance(ins.arg2, str)
            and ins.arg1 in constantes
            and ins.arg2 in constantes
        ):
            # No plegar división/módulo por cero: debe preservarse para que
            # MaquinaTAC/interpreter produzca IL-EJE-002/006 en tiempo de
            # ejecución, no un 'inf' o una excepción de Python. Para floats,
            # Python no lanza ZeroDivisionError sino que produce inf.
            if ins.op in ("/", "%") and constantes[ins.arg2] == 0:
                pass  # conservar la operación original
            else:
                try:
                    valor = _calcular_binop(ins.op, constantes[ins.arg1], constantes[ins.arg2])
                except (ValueError, ZeroDivisionError):
                    valor = None
                if valor is not None:
                    # Evitar plegar 0.0/0.0 -> nan o inf; preservar semántica de error
                    if isinstance(valor, float) and (
                        valor != valor or valor in (float("inf"), float("-inf"))
                    ):
                        pass
                    else:
                        nuevas.append(Instr("const", valor, resultado=ins.resultado))
                        constantes[ins.resultado] = valor
                        cambios += 1
                        continue
        if ins.op in _UNOPS and isinstance(ins.arg1, str) and ins.arg1 in constantes:
            valor = _calcular_unop(ins.op, constantes[ins.arg1])
            nuevas.append(Instr("const", valor, resultado=ins.resultado))
            constantes[ins.resultado] = valor
            cambios += 1
            continue
        if ins.op == "a_float" and isinstance(ins.arg1, str) and ins.arg1 in constantes:
            v = constantes[ins.arg1]
            valor = float(v) if _es_entero(v) else v
            nuevas.append(Instr("const", valor, resultado=ins.resultado))
            constantes[ins.resultado] = valor
            cambios += 1
            continue
        if ins.op == "call":
            # La subrutina llamada puede modificar cualquier variable global;
            # solo los temporales (siempre locales a este marco) conservan
            # su valor conocido a través de una llamada.
            for nombre in [k for k in constantes if not isinstance(k, Temp)]:
                del constantes[nombre]
        if ins.resultado is not None:
            constantes.pop(ins.resultado, None)
        nuevas.append(ins)
    return nuevas, cambios


def eliminar_codigo_muerto(instrucciones):
    """Quita instrucciones PURAS (sin efectos de lado: const/copy/aritmética/.

    array_get) cuyo resultado -- siempre un temporal, nunca una variable del
    programa -- no se usa en ningún lado.
    """
    usados = set()
    for ins in instrucciones:
        for campo in (ins.arg1, ins.arg2, ins.arg3):
            if isinstance(campo, str):
                usados.add(campo)
    puras = _BINOPS | set(_UNOPS) | {"const", "copy", "a_float", "array_get", "ncols"}
    nuevas = []
    cambios = 0
    for ins in instrucciones:
        es_temp_no_usado = isinstance(ins.resultado, Temp) and ins.resultado not in usados
        if ins.op in puras and es_temp_no_usado:
            cambios += 1
            continue
        nuevas.append(ins)
    return nuevas, cambios


def eliminar_inalcanzable(instrucciones):
    """Quita instrucciones entre un salto incondicional (`goto`/`return`) y.

    la siguiente etiqueta -- nunca se llega a ejecutarlas.
    """
    nuevas = []
    cambios = 0
    muerto = False
    for ins in instrucciones:
        if ins.op == "label":
            muerto = False
            nuevas.append(ins)
            continue
        if muerto:
            cambios += 1
            continue
        nuevas.append(ins)
        if ins.op in ("goto", "return"):
            muerto = True
    return nuevas, cambios


def peephole_saltos_redundantes(instrucciones):
    """Quita un `goto` cuyo destino es la etiqueta inmediatamente.

    siguiente -- saltar ahí es lo mismo que no saltar.
    """
    nuevas = []
    cambios = 0
    n = len(instrucciones)
    for i, ins in enumerate(instrucciones):
        if (
            ins.op == "goto"
            and i + 1 < n
            and instrucciones[i + 1].op == "label"
            and instrucciones[i + 1].arg1 == ins.arg1
        ):
            cambios += 1
            continue
        nuevas.append(ins)
    return nuevas, cambios


def eliminar_recursion_cola(nombre_funcion, nombres_parametros, instrucciones):
    """Elimina la recursión de cola DIRECTA (Etapa 12.8): cuando la última.

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
    agnósticas del nombre).
    """
    etq_inicio = f"__tco_{nombre_funcion}_inicio"
    nuevas = [Instr("label", etq_inicio)]
    siguiente_temp = max(
        (
            int(ins.resultado[1:])
            for ins in instrucciones
            if isinstance(ins.resultado, Temp) and ins.resultado[1:].isdigit()
        ),
        default=0,
    )
    cambios = 0
    i = 0
    n = len(instrucciones)
    while i < n:
        ins = instrucciones[i]
        if (
            ins.op == "call"
            and ins.arg1 == nombre_funcion
            and i + 1 < n
            and instrucciones[i + 1].op == "return"
            and instrucciones[i + 1].arg1 == ins.resultado
        ):
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
                if nuevas[j].op == "param":
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
                # Asignación PARALELA: primero se copian todos los valores a
                # temporales nuevos y solo después a los parámetros. Copiar
                # directo rompía `f(b, a)` (intercambio): `a = b; b = a`
                # dejaba ambos parámetros con el valor de `b`.
                intermedios = []
                for val in valores:
                    siguiente_temp += 1
                    tmp = Temp(f"t{siguiente_temp}")
                    nuevas.append(Instr("copy", val, resultado=tmp))
                    intermedios.append(tmp)
                for nombre_param, tmp in zip(nombres_parametros, intermedios, strict=True):
                    nuevas.append(Instr("copy", tmp, resultado=nombre_param))
                nuevas.append(Instr("goto", etq_inicio))
                cambios += 1
                i += 2  # el 'call' y el 'return' que lo sigue, ya reemplazados
                continue
        nuevas.append(ins)
        i += 1
    if cambios == 0:
        return instrucciones, 0  # sin llamada de cola: no vale la pena la etiqueta extra
    return nuevas, cambios


_PASADAS = (
    ("plegado de constantes", plegado_constantes),
    ("eliminación de código inalcanzable", eliminar_inalcanzable),
    ("eliminación de código muerto", eliminar_codigo_muerto),
    ("peephole (saltos redundantes)", peephole_saltos_redundantes),
)


# INV-1401: los nombres internos de las pasadas siguen siendo la identidad
# estable del resumen (las pruebas y la GUI los usan como clave); lo que ve
# el estudiante se presenta desde el catalogo i18n con esta tabla.
CLAVES_PASADAS = {
    "plegado de constantes": "IR.pasada.plegado_constantes",
    "eliminación de código inalcanzable": "IR.pasada.inalcanzable",
    "eliminación de código muerto": "IR.pasada.codigo_muerto",
    "peephole (saltos redundantes)": "IR.pasada.peephole",
    "eliminación de recursión de cola": "IR.pasada.recursion_cola",
}


def nombre_pasada(nombre, idioma=None):
    """Nombre presentable de una pasada de optimización en `idioma`."""
    clave = CLAVES_PASADAS.get(nombre)
    return t(clave, idioma) if clave else nombre


def optimizar(instrucciones, rondas=3):
    """Corre las pasadas de optimización repetidamente hasta que ninguna.

    cambie nada (una pasada puede desbloquear a otra: por ejemplo, plegar
    una condición constante puede dejar una rama entera inalcanzable) o se
    agoten las `rondas`. Retorna (instrucciones_optimizadas, resumen) donde
    `resumen` es una lista de (nombre_pasada, instrucciones_afectadas) solo
    con las pasadas que sí cambiaron algo, en orden.
    """
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
    """Aplica `optimizar` a cada subrutina de un programa generado por.

    `generar_programa`. Retorna (subrutinas_optimizadas, resumen_por_nombre).

    La eliminación de recursión de cola (Etapa 12.8) se aplica ANTES que
    las pasadas genéricas de `_PASADAS` -- necesita el nombre de la propia
    subrutina (una de las claves de `subrutinas`), así que no encaja en
    `_PASADAS` (agnósticas del nombre); una vez reescrita a `copy`+`goto`,
    el resto de pasadas (peephole en particular) puede seguir limpiándola
    igual que a cualquier otro código.
    """
    optimizadas = {}
    resumenes = {}
    for nombre, (parametros, instrucciones) in subrutinas.items():
        tras_tco, cambios_tco = eliminar_recursion_cola(nombre, parametros, instrucciones)
        nuevas, resumen = optimizar(tras_tco)
        if cambios_tco:
            resumen = [("eliminación de recursión de cola", cambios_tco)] + resumen
        optimizadas[nombre] = (parametros, nuevas)
        resumenes[nombre] = resumen
    return optimizadas, resumenes


# ============================================================
# Ejecución (MaquinaTAC): el "código objetivo" de esta etapa es el propio
# TAC (optimizado o no), ejecutado por este motor lineal separado -- no se
# agrega además un bytecode de más bajo nivel, para mantener el alcance
# manejable (queda anotado como candidato futuro en la hoja de ruta).
# ============================================================


def _ejecutar_globales(ir_globales):
    """Ejecuta el TAC de las globales y devuelve el dict de globales.

    Los temporales usados para calcularlas se descartan al terminar: si se
    quedaban en las globales, `_escribir_var` escribía los temporales de
    cada subrutina sobre esas globales homónimas (`t1`, `t2`, ...) y una
    llamada recursiva pisaba los temporales de su llamador.
    """
    globales = {}
    MaquinaTAC({}, ir_globales)._ejecutar_lista(ir_globales, globales)
    for nombre in [k for k in globales if isinstance(k, Temp)]:
        del globales[nombre]
    return globales


class MaquinaTAC:
    """Intérprete lineal de TAC. Modelo de ámbitos deliberadamente simple.

    (dos niveles: variables globales compartidas + un marco plano por
    llamada activa, sin bloques anidados -- el propio TAC ya aplanó los
    bloques del AST) -- suficiente para el subconjunto estructurado que
    cubre el generador; no reproduce el catálogo completo de errores de
    ejecución de interpreter.py (IL-EJE-*), solo el resultado computacional,
    ya que su propósito es demostrar/verificar el back end, no reemplazar
    el intérprete de producción.
    """

    def __init__(self, subrutinas, ir_globales, idioma=None):
        self.subrutinas = subrutinas  # nombre -> (parametros, instrucciones)
        self.ir_globales = ir_globales
        # INV-1400: idioma del texto que recibe `e.mensaje` dentro de un catch
        # (None = idioma del proceso), igual que el interprete de arbol.
        self.idioma = idioma
        self.globales = {}
        self.salida = []
        self.entrada = []

    def ejecutar(self, entrada=None):
        """Ejecuta el programa."""
        self.entrada = list(entrada) if entrada else []
        self.salida = []
        self.globales = _ejecutar_globales(self.ir_globales)
        self._llamar("main", [])
        return self.salida

    def _llamar(self, nombre, argumentos):
        if builtins.es_built_in(nombre):
            try:
                return builtins.ejecutar_built_in(nombre, argumentos)
            except builtins.BuiltInError as e:
                raise ErrorEjecucionTAC(e.codigo, e.mensaje) from e
        entrada_sub = self.subrutinas.get(nombre)
        if entrada_sub is None:
            raise RuntimeError(f'subrutina no encontrada en el IR: "{nombre}"')
        parametros, instrucciones = entrada_sub
        marco = dict(zip(parametros, argumentos, strict=True))
        tipo, valor = self._ejecutar_lista(instrucciones, marco)
        return valor if tipo == "return" else None

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
        # Temporales y declaraciones locales nacen siempre en el marco
        # actual; cualquier otro nombre se escribe donde ya exista (local o
        # global) y, si no existe, en el marco actual.
        if _es_nombre_de_marco(nombre) or nombre in marco or nombre not in self.globales:
            marco[nombre] = valor
        else:
            self.globales[nombre] = valor

    def _ejecutar_lista(self, instrucciones, marco):
        etiquetas = {ins.arg1: i for i, ins in enumerate(instrucciones) if ins.op == "label"}
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
                if op == "label":
                    pass
                elif op == "const":
                    self._escribir_var(ins.resultado, ins.arg1, marco)
                elif op == "copy":
                    self._escribir_var(ins.resultado, self._leer_var(ins.arg1, marco), marco)
                elif op in _BINOPS:
                    a = self._leer_var(ins.arg1, marco)
                    b = self._leer_var(ins.arg2, marco)
                    try:
                        resultado = _calcular_binop(op, a, b)
                    except ValueError as e:
                        raise ErrorEjecucionTAC(
                            "IL-EJE-001", e.args[0] if e.args else str(e)
                        ) from e
                    except ZeroDivisionError as e:
                        # Misma distinción que interpreter.py::_error_division_cero:
                        # '/' entre reales -> IL-EJE-002, entre enteros -> IL-EJE-006;
                        # '%' (siempre entero) es IL-EJE-006 en cualquier caso.
                        if op == "/" and (_es_real(a) or _es_real(b)):
                            raise ErrorEjecucionTAC(
                                "IL-EJE-002",
                                M("IL-EJE-002.operacion_punto_flotante_invalida"),
                            ) from e
                        raise ErrorEjecucionTAC(
                            "IL-EJE-006",
                            M(
                                "IL-EJE-006.division_cero"
                                if op == "/"
                                else "IL-EJE-006.division_cero_modulo"
                            ),
                        ) from e
                    self._escribir_var(ins.resultado, resultado, marco)
                elif op in _UNOPS:
                    v = _calcular_unop(op, self._leer_var(ins.arg1, marco))
                    self._escribir_var(ins.resultado, v, marco)
                elif op == "ncols":
                    arr = self._contenedor(ins.arg1, marco)[ins.arg1]
                    self._escribir_var(ins.resultado, arr.cols, marco)
                elif op == "a_float":
                    v = self._leer_var(ins.arg1, marco)
                    self._escribir_var(ins.resultado, float(v) if _es_entero(v) else v, marco)
                elif op == "goto":
                    i = etiquetas[ins.arg1]
                    continue
                elif op == "if_false":
                    if not self._leer_var(ins.arg1, marco):
                        i = etiquetas[ins.arg2]
                        continue
                elif op == "param":
                    pila_params.append(self._leer_var(ins.arg1, marco))
                elif op == "call":
                    nombre_f, nargs = ins.arg1, ins.arg2
                    args = pila_params[len(pila_params) - nargs :] if nargs else []
                    del pila_params[len(pila_params) - nargs :]
                    valor = self._llamar(nombre_f, args)
                    if ins.resultado is not None:
                        self._escribir_var(ins.resultado, valor, marco)
                elif op == "return":
                    valor = self._leer_var(ins.arg1, marco) if ins.arg1 is not None else None
                    return ("return", valor)
                elif op == "print":
                    self._escribir_salida(self._leer_var(ins.arg1, marco))
                elif op == "read":
                    self._escribir_var(ins.resultado, self._leer_entrada(ins.arg1), marco)
                elif op == "array_new":
                    tam = self._leer_var(ins.arg2, marco)
                    if ins.arg3 is None:
                        marco[ins.arg1] = [None] * tam
                    else:
                        matriz = _Matriz([None] * tam)
                        matriz.cols = self._leer_var(ins.arg3, marco)
                        marco[ins.arg1] = matriz
                elif op == "array_get":
                    arr = self._contenedor(ins.arg1, marco)[ins.arg1]
                    idx = self._leer_var(ins.arg2, marco)
                    if idx < 0 or idx >= len(arr):
                        raise ErrorEjecucionTAC(
                            "IL-EJE-050", M("IL-EJE-050.indice_fuera_rango_2", idx=idx)
                        )
                    self._escribir_var(ins.resultado, arr[idx], marco)
                elif op == "array_set":
                    arr = self._contenedor(ins.arg1, marco)[ins.arg1]
                    idx = self._leer_var(ins.arg2, marco)
                    if idx < 0 or idx >= len(arr):
                        raise ErrorEjecucionTAC(
                            "IL-EJE-050", M("IL-EJE-050.indice_fuera_rango_2", idx=idx)
                        )
                    arr[idx] = self._leer_var(ins.arg3, marco)
                elif op == "try_begin":
                    pila_manejadores.append((ins.arg1, ins.arg2))
                elif op == "try_end":
                    if pila_manejadores:
                        pila_manejadores.pop()
                elif op == "pop_manejador":
                    if pila_manejadores:
                        pila_manejadores.pop()
                else:
                    raise RuntimeError(f"operación de IR no soportada: {op}")
            except ErrorEjecucionTAC as err:
                if not pila_manejadores:
                    raise
                etq_catch, nombre_catch = pila_manejadores.pop()
                marco[f"{nombre_catch}.codigo"] = err.codigo
                marco[f"{nombre_catch}.mensaje"] = texto(err.mensaje, self.idioma)
                # INV-1404: alias en inglés (`e.code`/`e.message`).
                marco[f"{nombre_catch}.code"] = err.codigo
                marco[f"{nombre_catch}.message"] = marco[f"{nombre_catch}.mensaje"]
                i = etiquetas[etq_catch]
                continue
            i += 1
        return (None, None)

    def _escribir_salida(self, valor):
        if isinstance(valor, bool):
            s = "true" if valor else "false"
        elif isinstance(valor, float):
            s = str(valor)
        elif valor is None:
            s = "void"
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
                crudo = ""
        crudo = crudo.strip()
        if tipo == "int":
            return int(crudo)
        if tipo == "float":
            return float(crudo)
        if tipo == "bool":
            v = crudo.lower()
            return v in ("true", "verdadero", "1")
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
    """El programa usa una construcción fuera del subconjunto que cubre el.

    generador de código objetivo (arreglos, try/catch, lectura de entrada).
    """


class InstrObjetivo:
    """Una instrucción del ISA de juguete."""

    __slots__ = ("op", "arg1", "arg2")

    def __init__(self, op, arg1=None, arg2=None):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2

    def __repr__(self):
        op, a1, a2 = self.op, self.arg1, self.arg2
        if op == "LABEL":
            return f"{a1}:"
        if op in ("JMP", "JZ"):
            return f"    {op} {a1}"
        if op == "PUSH":
            return f"    PUSH {a1!r}"
        if op in ("LOAD", "STORE"):
            return f"    {op} {a1}"
        if op in ("CALL", "CALLV"):
            return f"    {op} {a1}, {a2}"
        return f"    {op}"


_MAPA_BINOP_OBJETIVO = {
    "+": "ADD",
    "-": "SUB",
    "*": "MUL",
    "/": "DIV",
    "%": "MOD",
    "==": "CMPEQ",
    "!=": "CMPNE",
    "<": "CMPLT",
    "<=": "CMPLE",
    ">": "CMPGT",
    ">=": "CMPGE",
    "&": "AND",
    "|": "OR",
    "^": "XOR",
    "<<": "SHL",
    ">>": "SHR",
}
_MAPA_OBJETIVO_BINOP = {v: k for k, v in _MAPA_BINOP_OBJETIVO.items()}

_NO_SOPORTADOS_OBJETIVO = {
    "array_new",
    "array_get",
    "array_set",
    "try_begin",
    "try_end",
    "pop_manejador",
    "read",
    "ncols",
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
    if op in ("label", "goto"):
        return set(), set()
    if op == "const":
        return set(), _s(ins.resultado)
    if op in ("copy", "a_float", "ncols") or op in _UNOPS:
        return _s(ins.arg1), _s(ins.resultado)
    if op in _BINOPS:
        return _s(ins.arg1) | _s(ins.arg2), _s(ins.resultado)
    if op in ("if_false", "param", "return", "print"):
        return _s(ins.arg1), set()
    if op in ("call", "read"):
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
    """Punto fijo hacia atrás sobre IN[i]/OUT[i] (ver comentario de.

    sección). Retorna (vivo_in, vivo_out): dos listas de sets[str], una
    entrada por instrucción, en el mismo orden que `instrucciones`.
    """
    n = len(instrucciones)
    etiquetas = {ins.arg1: i for i, ins in enumerate(instrucciones) if ins.op == "label"}

    sucesores = []
    for i, ins in enumerate(instrucciones):
        if ins.op == "goto":
            sucesores.append([etiquetas[ins.arg1]])
        elif ins.op == "if_false":
            s = [etiquetas[ins.arg2]]
            if i + 1 < n:
                s.append(i + 1)
            sucesores.append(s)
        elif ins.op == "return":
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
    """Rango de vida [inicio, fin] de cada variable/temporal -- el índice.

    de instrucción MÍNIMO y MÁXIMO en el que aparece viva (en `vivo_in` o
    `vivo_out`). Retorna dict nombre -> (inicio, fin).
    """
    rangos = {}
    for i in range(len(instrucciones)):
        for v in vivo_in[i] | vivo_out[i]:
            if v not in rangos:
                rangos[v] = [i, i]
            else:
                if i < rangos[v][0]:
                    rangos[v][0] = i
                if i > rangos[v][1]:
                    rangos[v][1] = i
    return {v: tuple(r) for v, r in rangos.items()}


def asignar_registros(rangos, k=4):
    """Asignador linear-scan simple (Poletto & Sarkar) sobre los rangos de.

    vida de `calcular_rangos_vida`, con `k` registros disponibles.
    Retorna (asignacion, spills):
      asignacion: dict nombre -> 'R0'..'R{k-1}' (registro) o el propio
                  `nombre` (sin cambios -- spill, se queda en memoria).
      spills: list[str] de los nombres que terminaron en memoria, en el
              orden en que se decidió el spill (para reportar/verificar).
    """
    orden = sorted(rangos.items(), key=lambda par: par[1][0])
    libres = [f"R{i}" for i in range(k)]
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
    """Traduce el TAC de una subrutina a objetivo.

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
    ambos por igual).
    """

    def _ren(nombre):
        if asignacion is None or nombre is None:
            return nombre
        return asignacion.get(nombre, nombre)

    def _cargar(operando):
        # Un operando que no es str es un literal inmediato (el `1` de
        # `i++`, un índice constante...). Antes se emitía `LOAD 1` y
        # MaquinaObjetivo buscaba una variable llamada 1 -> None, así que
        # cualquier programa con ++/-- fallaba en el código objetivo.
        if isinstance(operando, str):
            return InstrObjetivo("LOAD", _ren(operando))
        return InstrObjetivo("PUSH", operando)

    salida = []
    for ins in instrucciones:
        op = ins.op
        if op in _NO_SOPORTADOS_OBJETIVO:
            raise NoSoportadoObjetivo(M("IR.objetivo.no_esta_soportado_generador", op=op))
        if op == "label":
            salida.append(InstrObjetivo("LABEL", ins.arg1))
        elif op == "const":
            salida.append(InstrObjetivo("PUSH", ins.arg1))
            salida.append(InstrObjetivo("STORE", _ren(ins.resultado)))
        elif op == "copy":
            salida.append(_cargar(ins.arg1))
            salida.append(InstrObjetivo("STORE", _ren(ins.resultado)))
        elif op in _BINOPS:
            salida.append(_cargar(ins.arg1))
            salida.append(_cargar(ins.arg2))
            salida.append(InstrObjetivo(_MAPA_BINOP_OBJETIVO[op]))
            salida.append(InstrObjetivo("STORE", _ren(ins.resultado)))
        elif op == "neg":
            salida.append(_cargar(ins.arg1))
            salida.append(InstrObjetivo("NEG"))
            salida.append(InstrObjetivo("STORE", _ren(ins.resultado)))
        elif op == "not":
            salida.append(_cargar(ins.arg1))
            salida.append(InstrObjetivo("NOT"))
            salida.append(InstrObjetivo("STORE", _ren(ins.resultado)))
        elif op == "bnot":
            salida.append(_cargar(ins.arg1))
            salida.append(InstrObjetivo("BNOT"))
            salida.append(InstrObjetivo("STORE", _ren(ins.resultado)))
        elif op == "a_float":
            salida.append(_cargar(ins.arg1))
            salida.append(InstrObjetivo("CVTF"))
            salida.append(InstrObjetivo("STORE", _ren(ins.resultado)))
        elif op == "goto":
            salida.append(InstrObjetivo("JMP", ins.arg1))
        elif op == "if_false":
            salida.append(_cargar(ins.arg1))
            salida.append(InstrObjetivo("JZ", ins.arg2))
        elif op == "param":
            salida.append(_cargar(ins.arg1))
            salida.append(InstrObjetivo("PUSHPARAM"))
        elif op == "call":
            if ins.resultado is not None:
                salida.append(InstrObjetivo("CALL", ins.arg1, ins.arg2))
                salida.append(InstrObjetivo("STORE", _ren(ins.resultado)))
            else:
                salida.append(InstrObjetivo("CALLV", ins.arg1, ins.arg2))
        elif op == "return":
            if ins.arg1 is not None:
                salida.append(_cargar(ins.arg1))
                salida.append(InstrObjetivo("RETV"))
            else:
                salida.append(InstrObjetivo("RET"))
        elif op == "print":
            salida.append(_cargar(ins.arg1))
            salida.append(InstrObjetivo("PRINT"))
        else:
            raise NoSoportadoObjetivo(M("IR.objetivo.no_esta_soportado_generador_2", op=op))
    return salida


def generar_objetivo_programa(subrutinas, k_registros=None):
    """Traduce TODAS las subrutinas de un programa (dict nombre ->.

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
    `optimizar_programa`.
    """
    resultado = {}
    resumen = {}
    for nombre, (params, instrs) in subrutinas.items():
        asignacion = None
        if k_registros:
            vivo_in, vivo_out = calcular_liveness(instrs)
            rangos = calcular_rangos_vida(instrs, vivo_in, vivo_out)
            # Solo temporales, locales declarados y parámetros pueden ir a
            # registro: una GLOBAL renombrada a 'R2' se escribía en el marco
            # de la llamada y la global real nunca cambiaba (bit_a_bit.inv).
            locales = {str(i.resultado) for i in instrs if isinstance(i.resultado, Local)}
            elegibles = locales | set(params)
            rangos = {n: r for n, r in rangos.items() if isinstance(n, Temp) or str(n) in elegibles}
            # Todos los parámetros llegan VIVOS a la entrada, a la vez: si el
            # rango de uno empezaba tarde, dos parámetros podían compartir
            # registro y uno pisaba al otro al armar el marco (hanoi.inv).
            for p in params:
                if p in rangos:
                    rangos[p] = (0, rangos[p][1])
            asignacion, spills = asignar_registros(rangos, k_registros)
            resumen[nombre] = (asignacion, spills)
            params = [asignacion.get(p, p) for p in params]
        resultado[nombre] = (params, generar_objetivo_subrutina(instrs, asignacion))
    return resultado, resumen


def formatear_objetivo(instrucciones):
    """Texto legible de una lista de InstrObjetivo, una por línea."""
    return "\n".join(repr(ins) for ins in instrucciones)


class MaquinaObjetivo:
    """Ejecuta el ISA de juguete generado por `generar_objetivo_programa`.

    -- una máquina de pila de operandos por marco de llamada, con las
    mismas dos capas de ámbito que `MaquinaTAC` (globales compartidas +
    un marco plano por llamada activa). Sirve para comprobar que la
    traducción TAC -> objetivo preserva el resultado: mismo criterio de
    paridad que ya se usa entre `--run-ir` y el intérprete de árbol.
    """

    def __init__(self, subrutinas, ir_globales):
        self.subrutinas = subrutinas  # nombre -> (parametros, instrucciones_objetivo)
        self.ir_globales = ir_globales  # TAC (sin traducir) de las declaraciones globales
        self.globales = {}
        self.salida = []
        self.entrada = []

    def ejecutar(self, entrada=None):
        """Ejecuta el programa."""
        self.entrada = list(entrada) if entrada else []
        self.salida = []
        # Las declaraciones globales son TAC sin traducir -- se ejecutan con
        # la misma lógica que MaquinaTAC (no hay control de flujo real en
        # ellas, solo 'const'/'copy'/binops), reutilizada aquí sin duplicar
        # código.
        self.globales = _ejecutar_globales(self.ir_globales)
        self._llamar("main", [])
        return self.salida

    def _llamar(self, nombre, argumentos):
        if builtins.es_built_in(nombre):
            try:
                return builtins.ejecutar_built_in(nombre, argumentos)
            except builtins.BuiltInError as e:
                raise ErrorEjecucionTAC(e.codigo, e.mensaje) from e
        entrada_sub = self.subrutinas.get(nombre)
        if entrada_sub is None:
            raise RuntimeError(f'subrutina no encontrada en el código objetivo: "{nombre}"')
        parametros, instrucciones = entrada_sub
        marco = dict(zip(parametros, argumentos, strict=True))
        return self._ejecutar_lista(instrucciones, marco)

    def _contenedor(self, nombre, marco):
        return marco if nombre in marco else self.globales

    def _leer_var(self, nombre, marco):
        return self._contenedor(nombre, marco).get(nombre)

    def _escribir_var(self, nombre, valor, marco):
        if _es_nombre_de_marco(nombre) or nombre in marco or nombre not in self.globales:
            marco[nombre] = valor
        else:
            self.globales[nombre] = valor

    def _ejecutar_lista(self, instrucciones, marco):
        etiquetas = {ins.arg1: i for i, ins in enumerate(instrucciones) if ins.op == "LABEL"}
        pila = []  # pila de operandos
        pila_params = []  # argumentos pendientes (PUSHPARAM), como MaquinaTAC
        i = 0
        n = len(instrucciones)
        while i < n:
            ins = instrucciones[i]
            op = ins.op
            if op == "LABEL":
                pass
            elif op == "PUSH":
                pila.append(ins.arg1)
            elif op == "LOAD":
                pila.append(self._leer_var(ins.arg1, marco))
            elif op == "STORE":
                self._escribir_var(ins.arg1, pila.pop(), marco)
            elif op in _MAPA_OBJETIVO_BINOP:
                b = pila.pop()
                a = pila.pop()
                simbolo = _MAPA_OBJETIVO_BINOP[op]
                try:
                    pila.append(_calcular_binop(simbolo, a, b))
                except ValueError as e:
                    raise ErrorEjecucionTAC("IL-EJE-001", e.args[0] if e.args else str(e)) from e
                except ZeroDivisionError as e:
                    if simbolo == "/" and (_es_real(a) or _es_real(b)):
                        raise ErrorEjecucionTAC(
                            "IL-EJE-002", M("IL-EJE-002.operacion_punto_flotante_invalida")
                        ) from e
                    raise ErrorEjecucionTAC(
                        "IL-EJE-006",
                        M(
                            "IL-EJE-006.division_cero"
                            if simbolo == "/"
                            else "IL-EJE-006.division_cero_modulo"
                        ),
                    ) from e
            elif op == "NEG":
                pila.append(-pila.pop())
            elif op == "NOT":
                pila.append(not pila.pop())
            elif op == "BNOT":
                pila.append(~pila.pop())
            elif op == "CVTF":
                v = pila.pop()
                pila.append(float(v) if _es_entero(v) else v)
            elif op == "JMP":
                i = etiquetas[ins.arg1]
                continue
            elif op == "JZ":
                if not pila.pop():
                    i = etiquetas[ins.arg1]
                    continue
            elif op == "PUSHPARAM":
                pila_params.append(pila.pop())
            elif op in ("CALL", "CALLV"):
                nombre_f, nargs = ins.arg1, ins.arg2
                args = pila_params[len(pila_params) - nargs :] if nargs else []
                del pila_params[len(pila_params) - nargs :]
                valor = self._llamar(nombre_f, args)
                if op == "CALL":
                    pila.append(valor)
            elif op == "RETV":
                return pila.pop()
            elif op == "RET":
                return None
            elif op == "PRINT":
                self._escribir_salida(pila.pop())
            else:
                raise RuntimeError(f"operación de código objetivo no soportada: {op}")
            i += 1
        return None

    def _escribir_salida(self, valor):
        if isinstance(valor, bool):
            s = "true" if valor else "false"
        elif isinstance(valor, float):
            s = str(valor)
        elif valor is None:
            s = "void"
        else:
            s = str(valor)
        self.salida.append(s)
