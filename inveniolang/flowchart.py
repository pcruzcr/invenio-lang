# Módulo de Diagramas de Flujo de InvenioLang (Etapa 4, Fase 2)
# Motor de layout puro en Python (sin dependencia de Qt): recorre un Bloque
# del AST ya validado y produce una estructura de cajas/flechas lista para
# pintar. Separado de gui_qt.py para poder probarlo sin abrir una ventana.
# Patrones: Builder (construcción diagrama), Factory (cajas/flechas),
# Strategy (layout), Visitor (recorrido AST), Composite (diagrama)
from __future__ import annotations

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

# ---- Formas de caja (estilo PSeInt / ISO 5807 simplificado) ----
INICIO = "inicio"
FIN = "fin"
PROCESO = "proceso"
DECISION = "decision"
ENTRADA_SALIDA = "entrada_salida"
CONECTOR = "conector"  # punto de union invisible, solo para enrutar flechas

# Dimensiones fijas por forma: evita propagar anchos dinamicos segun el
# texto (que complicaria mucho el calculo de layout de las ramas); el texto
# largo se recorta en su lugar (ver _recortar).
ANCHO = {
    PROCESO: 200,
    ENTRADA_SALIDA: 200,
    DECISION: 180,
    INICIO: 140,
    FIN: 140,
    CONECTOR: 1,
}
ALTO = {
    PROCESO: 50,
    ENTRADA_SALIDA: 50,
    DECISION: 80,
    INICIO: 44,
    FIN: 44,
    CONECTOR: 1,
}
ESPACIO_V = 30
ESPACIO_H = 40
RAMA_OFFSET = 220  # separacion horizontal entre las ramas de un if
MAX_TEXTO = 42


class Caja:
    """Un nodo del diagrama: `x`/`y` son la esquina superior izquierda."""

    def __init__(self, id_, forma, texto, x, y, w, h, linea):
        self.id = id_
        self.forma = forma
        self.texto = texto
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.linea = linea

    @property
    def centro_x(self):
        """Centro horizontal de la caja."""
        return self.x + self.w / 2

    @property
    def arriba(self):
        """Ordenada del borde superior."""
        return (self.centro_x, self.y)

    @property
    def abajo(self):
        """Ordenada del borde inferior."""
        return (self.centro_x, self.y + self.h)

    @property
    def derecha(self):
        """Punto medio del borde derecho."""
        return (self.x + self.w, self.y + self.h / 2)


class Flecha:
    """`puntos` es la ruta completa (lista de coordenadas); se resuelve al.

    final del layout para las flechas rectas simples (ver `_resolver_puntos`
    en `construir_diagrama`), y se da explícita para las rutas especiales
    (retroceso de ciclo, autolazo).
    """

    def __init__(self, origen_id, destino_id, etiqueta, puntos):
        self.origen_id = origen_id
        self.destino_id = destino_id
        self.etiqueta = etiqueta
        self.puntos = puntos


class Diagrama:
    """Diagrama de flujo con cajas y flechas."""

    def __init__(self, cajas, flechas, ancho, alto):
        self.cajas = cajas
        self.flechas = flechas
        self.ancho = ancho
        self.alto = alto


class _CicloInfo:
    """Datos del ciclo mas cercano, para resolver break/continue (§9.4)."""

    def __init__(self, cond_id):
        self.cond_id = cond_id
        self.breaks_pendientes = []  # ids de cajas 'romper' a conectar a la salida


class _Contexto:
    def __init__(self, fin_id, ciclo=None, break_target=None):
        self.fin_id = fin_id
        self.ciclo = ciclo  # CicloInfo del bucle mas cercano (para 'continuar')
        # Lista .append(id) de la caja 'romper' mas cercana que la satisface
        # -- un bucle O un switch/segun (Etapa 6); separado de `ciclo`
        # porque un switch detiene `romper` pero NO `continuar` (§9,
        # semantic.py). Por defecto es la misma lista que `ciclo.
        # breaks_pendientes` cuando el contexto es el cuerpo de un bucle.
        self.break_target = break_target


def _recortar(texto, maximo=MAX_TEXTO):
    texto = texto.replace("\n", " ")
    if len(texto) > maximo:
        return texto[: maximo - 1] + "…"
    return texto


class _Constructor:
    def __init__(self):
        self._siguiente_id = 0
        self.cajas = {}
        self.flechas = []

    def caja(self, forma, texto, cx, y, linea):
        """Agrega una caja al diagrama."""
        w, h = ANCHO[forma], ALTO[forma]
        id_ = self._siguiente_id
        self._siguiente_id += 1
        self.cajas[id_] = Caja(id_, forma, _recortar(texto), cx - w / 2, y, w, h, linea)
        return id_

    def flecha(self, origen_id, destino_id, etiqueta=None, puntos=None):
        """Agrega una flecha entre cajas."""
        self.flechas.append(Flecha(origen_id, destino_id, etiqueta, puntos))


# ============================================================
# "Unparser": reconstruye texto legible desde el AST (no se guarda el
# texto fuente original por nodo). Cubre expresiones/instrucciones de la
# v1.0 y de POO/Estructuras de Datos (Etapas 2-3).
# ============================================================


def _texto_receptor(receptor):
    if isinstance(receptor, ArrayAccess):
        return f"{receptor.nombre}[{_texto_expr(receptor.indice)}]"
    return _texto_expr(receptor)


def _texto_expr(nodo):
    if nodo is None:
        return ""
    if isinstance(nodo, Literal):
        if nodo.tipo_literal == "string":
            return f'"{nodo.valor}"'
        if nodo.tipo_literal == "bool":
            return "verdadero" if nodo.valor else "falso"
        return str(nodo.valor)
    if isinstance(nodo, Identifier):
        return nodo.nombre
    if isinstance(nodo, ArrayAccess):
        return f"{nodo.nombre}[{_texto_expr(nodo.indice)}]"
    if isinstance(nodo, MatrixAccess):
        return f"{nodo.nombre}[{_texto_expr(nodo.fila)}][{_texto_expr(nodo.columna)}]"
    if isinstance(nodo, FunctionCall):
        args = ", ".join(_texto_expr(a) for a in nodo.argumentos)
        return f"{nodo.nombre}({args})"
    if isinstance(nodo, BinaryOp):
        return f"{_texto_expr(nodo.izquierda)} {nodo.operador} {_texto_expr(nodo.derecha)}"
    if isinstance(nodo, UnaryOp):
        if nodo.operador in ("++", "--"):
            return (
                f"{nodo.operador}{_texto_expr(nodo.operando)}"
                if nodo.es_prefijo
                else f"{_texto_expr(nodo.operando)}{nodo.operador}"
            )
        return f"{nodo.operador}{_texto_expr(nodo.operando)}"
    if isinstance(nodo, ThisExpr):
        return "este"
    if isinstance(nodo, SuperExpr):
        return "padre"
    if isinstance(nodo, NullExpr):
        return "nulo"
    if isinstance(nodo, NewExpr):
        args = ", ".join(_texto_expr(a) for a in nodo.argumentos)
        return f"nuevo {nodo.nombre_clase}({args})"
    if isinstance(nodo, MemberAccess):
        punto = "?." if nodo.es_seguro else "."
        return f"{_texto_receptor(nodo.receptor)}{punto}{nodo.nombre_miembro}"
    if isinstance(nodo, MethodCallExpr):
        args = ", ".join(_texto_expr(a) for a in nodo.argumentos)
        punto = "?." if nodo.es_seguro else "."
        return f"{_texto_receptor(nodo.receptor)}{punto}{nodo.nombre_metodo}({args})"
    if isinstance(nodo, TernaryExpr):
        return (
            f"{_texto_expr(nodo.condicion)} ? {_texto_expr(nodo.si_verdadero)} "
            f": {_texto_expr(nodo.si_falso)}"
        )
    if isinstance(nodo, LambdaExpr):
        # Etapa 12.6: no se dibuja el cuerpo del lambda como sub-diagrama
        # (alcance acotado -- ver docs/InvenioLang_2.0_POO.md) -- solo su
        # firma, igual que como se ve en el código fuente.
        tipos = ", ".join(p.tipo for p in nodo.parametros)
        return f"funcion({tipos}) {nodo.tipo_retorno} {{...}}"
    return "?"


def _texto_lvalue(lvalue):
    if isinstance(lvalue, VarLValue):
        return lvalue.nombre
    if isinstance(lvalue, ArrayLValue):
        return f"{lvalue.nombre}[{_texto_expr(lvalue.indice)}]"
    if isinstance(lvalue, MatrixLValue):
        return f"{lvalue.nombre}[{_texto_expr(lvalue.fila)}][{_texto_expr(lvalue.columna)}]"
    if isinstance(lvalue, MemberLValue):
        return f"{_texto_receptor(lvalue.receptor)}.{lvalue.nombre_miembro}"
    return "?"


def _texto_instruccion(nodo):
    if isinstance(nodo, VarDecl):
        base = f"{nodo.tipo} {nodo.nombre}"
        return base if nodo.init_expr is None else f"{base} = {_texto_expr(nodo.init_expr)}"
    if isinstance(nodo, ConstDecl):
        return f"const {nodo.tipo} {nodo.nombre} = {_texto_expr(nodo.init_expr)}"
    if isinstance(nodo, ArrayDecl):
        return f"{nodo.tipo}[{nodo.tam}] {nodo.nombre}"
    if isinstance(nodo, MatrixDecl):
        return f"{nodo.tipo}[{nodo.filas}][{nodo.cols}] {nodo.nombre}"
    if isinstance(nodo, AssignStmt):
        return f"{_texto_lvalue(nodo.lvalue)} {nodo.operador} {_texto_expr(nodo.expr)}"
    if isinstance(nodo, IncDecStmt):
        return (
            f"{nodo.operador}{nodo.nombre}" if nodo.es_prefijo else f"{nodo.nombre}{nodo.operador}"
        )
    if isinstance(nodo, PrintStmt):
        return f"imprimir({_texto_expr(nodo.expr)})"
    if isinstance(nodo, ReadStmt):
        return f"leer({nodo.nombre})"
    if isinstance(nodo, CallStmt):
        args = ", ".join(_texto_expr(a) for a in nodo.argumentos)
        return f"{nodo.nombre}({args})"
    if isinstance(nodo, MethodCallStmt):
        args = ", ".join(_texto_expr(a) for a in nodo.argumentos)
        punto = "?." if nodo.es_seguro else "."
        return f"{_texto_receptor(nodo.receptor)}{punto}{nodo.nombre_metodo}({args})"
    if isinstance(nodo, SuperCallStmt):
        args = ", ".join(_texto_expr(a) for a in nodo.argumentos)
        return f"padre({args})"
    return None


def _texto_for_init_act(nodo):
    if isinstance(nodo, ForInitVar):
        base = f"{nodo.tipo} {nodo.nombre}"
        return base if nodo.init_expr is None else f"{base} = {_texto_expr(nodo.init_expr)}"
    if isinstance(nodo, ForInitAsig):
        return f"{_texto_lvalue(nodo.lvalue)} {nodo.operador} {_texto_expr(nodo.expr)}"
    if isinstance(nodo, ForInitIncDec):
        return (
            f"{nodo.operador}{nodo.nombre}" if nodo.es_prefijo else f"{nodo.nombre}{nodo.operador}"
        )
    return ""


def _auto_lazo_puntos(caja):
    """Ruta de una flecha que sale y vuelve a la MISMA caja (ciclo con.

    cuerpo vacío) -- pasa por el lado derecho para no degenerar a una
    línea de longitud cero.
    """
    cx, cy = caja.derecha
    return [(cx, cy), (cx + 60, cy), (cx + 60, cy - 20), (cx, cy - 20)]


# ============================================================
# Layout
# ============================================================


def _layout_secuencia(c, elementos, cx, y, contexto):
    """Apila `elementos` verticalmente centrados en `cx` desde `y`.

    Retorna (entrada_id, salida_id, y_siguiente, ancho). `entrada_id`/
    `salida_id` son None si `elementos` está vacía; `salida_id` también es
    None si el flujo no "cae" al final (termina en return/break/continue,
    o en un if cuyas dos ramas terminan así) -- el resto de la lista, si
    la hay, queda como código inalcanzable y no se dibuja.
    """
    entrada_id = None
    anterior_id = None
    y_actual = y
    ancho = ANCHO[PROCESO]
    for elem in elementos:
        e_id, s_id, y_actual, ancho_elem = _layout_elemento(c, elem, cx, y_actual, contexto)
        ancho = max(ancho, ancho_elem)
        if entrada_id is None:
            entrada_id = e_id
        if anterior_id is not None:
            c.flecha(anterior_id, e_id)
        anterior_id = s_id
        if s_id is None:
            break  # código inalcanzable a partir de aquí
    return entrada_id, anterior_id, y_actual, ancho


def _layout_rama(c, bloque, cx, y, contexto):
    """Como `_layout_secuencia`, pero acepta un Bloque (o None)."""
    if bloque is None or not bloque.elementos:
        return None, None, y, ANCHO[PROCESO]
    return _layout_secuencia(c, bloque.elementos, cx, y, contexto)


def _layout_elemento(c, elem, cx, y, contexto):
    if isinstance(elem, IfStmt):
        return _layout_if(c, elem, cx, y, contexto)
    if isinstance(elem, WhileStmt):
        return _layout_while(c, elem, cx, y, contexto)
    if isinstance(elem, ForStmt):
        return _layout_for(c, elem, cx, y, contexto)
    if isinstance(elem, ForEachStmt):
        return _layout_foreach(c, elem, cx, y, contexto)
    if isinstance(elem, DoWhileStmt):
        return _layout_do_while(c, elem, cx, y, contexto)
    if isinstance(elem, SwitchStmt):
        return _layout_switch(c, elem, cx, y, contexto)
    if isinstance(elem, MatchStmt):
        return _layout_match(c, elem, cx, y, contexto)
    if isinstance(elem, TryStmt):
        return _layout_try(c, elem, cx, y, contexto)

    if isinstance(elem, ReturnStmt):
        texto = "retornar" if elem.expr is None else f"retornar {_texto_expr(elem.expr)}"
        id_ = c.caja(PROCESO, texto, cx, y, elem.linea)
        c.flecha(id_, contexto.fin_id)
        return id_, None, y + ALTO[PROCESO] + ESPACIO_V, ANCHO[PROCESO]

    if isinstance(elem, BreakStmt):
        id_ = c.caja(PROCESO, "romper", cx, y, elem.linea)
        if contexto.break_target is not None:
            contexto.break_target.append(id_)
        return id_, None, y + ALTO[PROCESO] + ESPACIO_V, ANCHO[PROCESO]

    if isinstance(elem, ContinueStmt):
        id_ = c.caja(PROCESO, "continuar", cx, y, elem.linea)
        if contexto.ciclo is not None:
            c.flecha(id_, contexto.ciclo.cond_id)
        return id_, None, y + ALTO[PROCESO] + ESPACIO_V, ANCHO[PROCESO]

    forma = ENTRADA_SALIDA if isinstance(elem, (PrintStmt, ReadStmt)) else PROCESO
    texto = _texto_instruccion(elem)
    if texto is None:
        texto = elem.__class__.__name__  # nodo no reconocido: no debe crashear
    id_ = c.caja(forma, texto, cx, y, getattr(elem, "linea", 0))
    return id_, id_, y + ALTO[forma] + ESPACIO_V, ANCHO[forma]


def _layout_if(c, nodo, cx, y, contexto):
    cond_id = c.caja(DECISION, _texto_expr(nodo.condicion), cx, y, nodo.linea)
    y_ramas = y + ALTO[DECISION] + ESPACIO_V

    e_then, s_then, y_then_fin, _ = _layout_rama(
        c, nodo.bloque_then, cx - RAMA_OFFSET, y_ramas, contexto
    )
    e_else, s_else, y_else_fin, _ = _layout_rama(
        c, nodo.bloque_else, cx + RAMA_OFFSET, y_ramas, contexto
    )
    y_convergencia = max(y_then_fin, y_else_fin)

    then_cae = e_then is None or s_then is not None
    else_cae = e_else is None or s_else is not None
    if not then_cae and not else_cae:
        # Ambas ramas terminan en return/break/continue: el if no cae.
        if e_then is not None:
            c.flecha(cond_id, e_then, etiqueta="Sí")
        if e_else is not None:
            c.flecha(cond_id, e_else, etiqueta="No")
        return cond_id, None, y_convergencia, 2 * RAMA_OFFSET + ANCHO[DECISION]

    conector_id = c.caja(CONECTOR, "", cx, y_convergencia, 0)

    if e_then is None:
        c.flecha(cond_id, conector_id, etiqueta="Sí")
    else:
        c.flecha(cond_id, e_then, etiqueta="Sí")
        if s_then is not None:
            c.flecha(s_then, conector_id)

    if e_else is None:
        c.flecha(cond_id, conector_id, etiqueta="No")
    else:
        c.flecha(cond_id, e_else, etiqueta="No")
        if s_else is not None:
            c.flecha(s_else, conector_id)

    ancho = 2 * RAMA_OFFSET + ANCHO[DECISION]
    return cond_id, conector_id, y_convergencia + ALTO[CONECTOR] + ESPACIO_V, ancho


def _layout_while(c, nodo, cx, y, contexto):
    cond_id = c.caja(DECISION, _texto_expr(nodo.condicion), cx, y, nodo.linea)
    y_cuerpo = y + ALTO[DECISION] + ESPACIO_V

    ciclo = _CicloInfo(cond_id)
    contexto_cuerpo = _Contexto(
        fin_id=contexto.fin_id, ciclo=ciclo, break_target=ciclo.breaks_pendientes
    )
    e_cuerpo, s_cuerpo, y_fin, ancho_cuerpo = _layout_rama(
        c, nodo.bloque, cx, y_cuerpo, contexto_cuerpo
    )

    if e_cuerpo is not None:
        c.flecha(cond_id, e_cuerpo, etiqueta="Sí")
        if s_cuerpo is not None:
            c.flecha(s_cuerpo, cond_id)
    else:
        c.flecha(cond_id, cond_id, etiqueta="Sí", puntos=_auto_lazo_puntos(c.cajas[cond_id]))

    salida_id = c.caja(CONECTOR, "", cx, y_fin, 0)
    c.flecha(cond_id, salida_id, etiqueta="No")
    for break_id in ciclo.breaks_pendientes:
        c.flecha(break_id, salida_id)

    return (
        cond_id,
        salida_id,
        y_fin + ALTO[CONECTOR] + ESPACIO_V,
        max(ancho_cuerpo, ANCHO[DECISION]),
    )


def _layout_foreach(c, nodo, cx, y, contexto):
    """Dibuja para_cada como decisión sin condición.

    una decision con el texto "nombre en arreglo" en vez de una condicion
    booleana (el recorrido siempre termina cuando se agota el arreglo, no
    hay condicion explicita que dibujar).
    """
    texto = f"{nodo.nombre} en {_texto_expr(nodo.arreglo)}"
    cond_id = c.caja(DECISION, texto, cx, y, nodo.linea)
    y_cuerpo = y + ALTO[DECISION] + ESPACIO_V

    ciclo = _CicloInfo(cond_id)
    contexto_cuerpo = _Contexto(
        fin_id=contexto.fin_id, ciclo=ciclo, break_target=ciclo.breaks_pendientes
    )
    e_cuerpo, s_cuerpo, y_fin, ancho_cuerpo = _layout_rama(
        c, nodo.bloque, cx, y_cuerpo, contexto_cuerpo
    )

    if e_cuerpo is not None:
        c.flecha(cond_id, e_cuerpo, etiqueta="cada elemento")
        if s_cuerpo is not None:
            c.flecha(s_cuerpo, cond_id)
    else:
        c.flecha(
            cond_id, cond_id, etiqueta="cada elemento", puntos=_auto_lazo_puntos(c.cajas[cond_id])
        )

    salida_id = c.caja(CONECTOR, "", cx, y_fin, 0)
    c.flecha(cond_id, salida_id, etiqueta="fin del arreglo")
    for break_id in ciclo.breaks_pendientes:
        c.flecha(break_id, salida_id)

    return (
        cond_id,
        salida_id,
        y_fin + ALTO[CONECTOR] + ESPACIO_V,
        max(ancho_cuerpo, ANCHO[DECISION]),
    )


def _layout_for(c, nodo, cx, y, contexto):
    y_actual = y
    init_id = None
    if nodo.init_stmt is not None:
        init_id = c.caja(PROCESO, _texto_for_init_act(nodo.init_stmt), cx, y_actual, nodo.linea)
        y_actual += ALTO[PROCESO] + ESPACIO_V

    texto_cond = _texto_expr(nodo.cond_expr) if nodo.cond_expr is not None else "verdadero"
    cond_id = c.caja(DECISION, texto_cond, cx, y_actual, nodo.linea)
    if init_id is not None:
        c.flecha(init_id, cond_id)
    entrada_id = init_id if init_id is not None else cond_id
    y_cuerpo = y_actual + ALTO[DECISION] + ESPACIO_V

    ciclo = _CicloInfo(cond_id)
    contexto_cuerpo = _Contexto(
        fin_id=contexto.fin_id, ciclo=ciclo, break_target=ciclo.breaks_pendientes
    )
    e_cuerpo, s_cuerpo, y_fin, ancho_cuerpo = _layout_rama(
        c, nodo.bloque, cx, y_cuerpo, contexto_cuerpo
    )

    act_id = None
    if nodo.act_stmt is not None:
        act_id = c.caja(PROCESO, _texto_for_init_act(nodo.act_stmt), cx, y_fin, nodo.linea)
        y_fin += ALTO[PROCESO] + ESPACIO_V

    if e_cuerpo is not None:
        c.flecha(cond_id, e_cuerpo, etiqueta="Sí")
        destino_retorno = act_id if act_id is not None else cond_id
        if s_cuerpo is not None:
            c.flecha(s_cuerpo, destino_retorno)
    elif act_id is not None:
        c.flecha(cond_id, act_id, etiqueta="Sí")
    else:
        c.flecha(cond_id, cond_id, etiqueta="Sí", puntos=_auto_lazo_puntos(c.cajas[cond_id]))

    if act_id is not None:
        c.flecha(act_id, cond_id)

    salida_id = c.caja(CONECTOR, "", cx, y_fin, 0)
    c.flecha(cond_id, salida_id, etiqueta="No")
    for break_id in ciclo.breaks_pendientes:
        c.flecha(break_id, salida_id)

    return (
        entrada_id,
        salida_id,
        y_fin + ALTO[CONECTOR] + ESPACIO_V,
        max(ancho_cuerpo, ANCHO[DECISION]),
    )


def _layout_do_while(c, nodo, cx, y, contexto):
    """do/hacer ... while/mientras (Etapa 6): el cuerpo va ANTES de la caja.

    de decisión. Se reserva el id de la decisión antes de poner el cuerpo
    (misma técnica que el Fin del diagrama completo, "y se corrige
    después") para que un 'continuar' dentro del cuerpo pueda apuntarle.
    """
    cond_id = c.caja(DECISION, _texto_expr(nodo.condicion), cx, 0, nodo.linea)
    ciclo = _CicloInfo(cond_id)
    contexto_cuerpo = _Contexto(
        fin_id=contexto.fin_id, ciclo=ciclo, break_target=ciclo.breaks_pendientes
    )
    e_cuerpo, s_cuerpo, y_fin_cuerpo, ancho_cuerpo = _layout_rama(
        c, nodo.bloque, cx, y, contexto_cuerpo
    )
    c.cajas[cond_id].y = y_fin_cuerpo

    entrada_id = e_cuerpo if e_cuerpo is not None else cond_id
    if e_cuerpo is not None:
        c.flecha(cond_id, e_cuerpo, etiqueta="Sí")
        if s_cuerpo is not None:
            c.flecha(s_cuerpo, cond_id)
    else:
        c.flecha(cond_id, cond_id, etiqueta="Sí", puntos=_auto_lazo_puntos(c.cajas[cond_id]))

    y_fin = y_fin_cuerpo + ALTO[DECISION] + ESPACIO_V
    salida_id = c.caja(CONECTOR, "", cx, y_fin, 0)
    c.flecha(cond_id, salida_id, etiqueta="No")
    for break_id in ciclo.breaks_pendientes:
        c.flecha(break_id, salida_id)

    return (
        entrada_id,
        salida_id,
        y_fin + ALTO[CONECTOR] + ESPACIO_V,
        max(ancho_cuerpo, ANCHO[DECISION]),
    )


def _layout_switch(c, nodo, cx, y, contexto):
    """switch/segun (Etapa 6): una caja de decisión con una rama por cada.

    case (+ default si existe), convergiendo después -- simplificación
    visual del fallthrough real (cada case se dibuja como una rama
    independiente, no encadenada a la siguiente).
    """
    cond_id = c.caja(DECISION, _texto_expr(nodo.expr), cx, y, nodo.linea)
    y_ramas = y + ALTO[DECISION] + ESPACIO_V

    bloques = [caso.bloque for caso in nodo.casos]
    etiquetas = [_texto_expr(caso.valor) for caso in nodo.casos]
    if nodo.bloque_default is not None:
        bloques.append(nodo.bloque_default)
        etiquetas.append("default")
    n = max(len(bloques), 1)

    switch_breaks = []
    # `ciclo` se hereda del contexto exterior sin cambios: 'continuar' NO lo
    # satisface un switch (§9, semantic.py), solo el bucle envolvente.
    contexto_ramas = _Contexto(
        fin_id=contexto.fin_id, ciclo=contexto.ciclo, break_target=switch_breaks
    )

    resultados = []
    y_max = y_ramas
    for i, bloque in enumerate(bloques):
        offset = (i - (n - 1) / 2) * RAMA_OFFSET
        e_id, s_id, y_fin_i, _ = _layout_rama(c, bloque, cx + offset, y_ramas, contexto_ramas)
        resultados.append((e_id, s_id))
        y_max = max(y_max, y_fin_i)

    conector_id = c.caja(CONECTOR, "", cx, y_max, 0)
    algo_converge = False
    for (e_id, s_id), etiqueta in zip(resultados, etiquetas, strict=True):
        if e_id is None:
            c.flecha(cond_id, conector_id, etiqueta=etiqueta)
            algo_converge = True
        else:
            c.flecha(cond_id, e_id, etiqueta=etiqueta)
            if s_id is not None:
                c.flecha(s_id, conector_id)
                algo_converge = True
    for break_id in switch_breaks:
        c.flecha(break_id, conector_id)
        algo_converge = True
    if nodo.bloque_default is None:
        # Sin default: si ningún case coincide, también se converge.
        c.flecha(cond_id, conector_id, etiqueta="(ninguno)")
        algo_converge = True

    ancho = max(ANCHO[DECISION], n * RAMA_OFFSET)
    if not algo_converge:
        return cond_id, None, y_max, ancho
    return cond_id, conector_id, y_max + ALTO[CONECTOR] + ESPACIO_V, ancho


def _layout_match(c, nodo, cx, y, contexto):
    """emparejar/match (Etapa 12.9/12.10): mismo patrón visual que switch.

    -- una caja de decisión con una rama por caso (+ comodín si existe),
    convergiendo después. A diferencia de switch, cada rama es realmente
    excluyente (instanceof, sin fallthrough) y no admite `break` propio --
    `contexto` se pasa SIN una lista de break_target nueva (un `break`
    dentro de un caso, si lo hubiera, apunta al bucle envolvente, no al
    match, ver semantic.py::_visitar_match).
    """
    cond_id = c.caja(DECISION, _texto_expr(nodo.expr), cx, y, nodo.linea)
    y_ramas = y + ALTO[DECISION] + ESPACIO_V

    bloques = [caso.bloque for caso in nodo.casos]
    etiquetas = [caso.nombre_variante for caso in nodo.casos]
    if nodo.caso_comodin is not None:
        bloques.append(nodo.caso_comodin)
        etiquetas.append("_")
    n = max(len(bloques), 1)

    contexto_ramas = _Contexto(
        fin_id=contexto.fin_id, ciclo=contexto.ciclo, break_target=contexto.break_target
    )

    resultados = []
    y_max = y_ramas
    for i, bloque in enumerate(bloques):
        offset = (i - (n - 1) / 2) * RAMA_OFFSET
        e_id, s_id, y_fin_i, _ = _layout_rama(c, bloque, cx + offset, y_ramas, contexto_ramas)
        resultados.append((e_id, s_id))
        y_max = max(y_max, y_fin_i)

    conector_id = c.caja(CONECTOR, "", cx, y_max, 0)
    algo_converge = False
    for (e_id, s_id), etiqueta in zip(resultados, etiquetas, strict=True):
        if e_id is None:
            c.flecha(cond_id, conector_id, etiqueta=etiqueta)
            algo_converge = True
        else:
            c.flecha(cond_id, e_id, etiqueta=etiqueta)
            if s_id is not None:
                c.flecha(s_id, conector_id)
                algo_converge = True
    if nodo.caso_comodin is None:
        # Sin comodín: si el valor no coincide con ningún caso (programa
        # inválido segun type_checker.py, pero el diagrama debe seguir
        # siendo dibujable), también se converge.
        c.flecha(cond_id, conector_id, etiqueta="(ninguno)")
        algo_converge = True

    ancho = max(ANCHO[DECISION], n * RAMA_OFFSET)
    if not algo_converge:
        return cond_id, None, y_max, ancho
    return cond_id, conector_id, y_max + ALTO[CONECTOR] + ESPACIO_V, ancho


def _layout_try(c, nodo, cx, y, contexto):
    """try/intentar ... catch/capturar genérico (Etapa 6): mismo patrón de.

    dos ramas que convergen ya usado por `_layout_if`, con la rama
    izquierda el bloque protegido y la derecha el manejador.
    """
    marcador_id = c.caja(PROCESO, f"intentar / capturar ({nodo.nombre_catch})", cx, y, nodo.linea)
    y_ramas = y + ALTO[PROCESO] + ESPACIO_V

    e_try, s_try, y_try_fin, _ = _layout_rama(
        c, nodo.bloque_try, cx - RAMA_OFFSET, y_ramas, contexto
    )
    e_catch, s_catch, y_catch_fin, _ = _layout_rama(
        c, nodo.bloque_catch, cx + RAMA_OFFSET, y_ramas, contexto
    )
    y_convergencia = max(y_try_fin, y_catch_fin)

    try_cae = e_try is None or s_try is not None
    catch_cae = e_catch is None or s_catch is not None
    if not try_cae and not catch_cae:
        if e_try is not None:
            c.flecha(marcador_id, e_try, etiqueta="intentar")
        if e_catch is not None:
            c.flecha(marcador_id, e_catch, etiqueta="error")
        return marcador_id, None, y_convergencia, 2 * RAMA_OFFSET + ANCHO[PROCESO]

    conector_id = c.caja(CONECTOR, "", cx, y_convergencia, 0)
    if e_try is None:
        c.flecha(marcador_id, conector_id, etiqueta="intentar")
    else:
        c.flecha(marcador_id, e_try, etiqueta="intentar")
        if s_try is not None:
            c.flecha(s_try, conector_id)
    if e_catch is None:
        c.flecha(marcador_id, conector_id, etiqueta="error")
    else:
        c.flecha(marcador_id, e_catch, etiqueta="error")
        if s_catch is not None:
            c.flecha(s_catch, conector_id)

    ancho = 2 * RAMA_OFFSET + ANCHO[PROCESO]
    return marcador_id, conector_id, y_convergencia + ALTO[CONECTOR] + ESPACIO_V, ancho


def construir_diagrama(bloque):
    """Construye el diagrama de flujo del cuerpo de una subrutina/método.

    `bloque` es el `Bloque` (AST) ya validado semánticamente de la
    subrutina, método o constructor a diagramar.
    """
    c = _Constructor()
    cx = 500.0
    y = 20.0
    inicio_id = c.caja(INICIO, "Inicio", cx, y, 0)
    y += ALTO[INICIO] + ESPACIO_V

    fin_id = c.caja(FIN, "Fin", cx, 0, 0)  # y se corrige abajo, tras el layout
    contexto = _Contexto(fin_id=fin_id)

    entrada_id, salida_id, y_fin, _ = _layout_secuencia(c, bloque.elementos, cx, y, contexto)

    if entrada_id is not None:
        c.flecha(inicio_id, entrada_id)
        origen_fin = salida_id
    else:
        origen_fin = inicio_id
        y_fin = y

    c.cajas[fin_id].y = y_fin
    if origen_fin is not None:
        c.flecha(origen_fin, fin_id)

    # Resolver las flechas rectas simples (las de ruta especial ya la traen).
    for f in c.flechas:
        if f.puntos is None:
            ox, oy = c.cajas[f.origen_id].abajo
            dx, dy = c.cajas[f.destino_id].arriba
            f.puntos = [(ox, oy), (dx, dy)]

    xs_izq = [caja.x for caja in c.cajas.values()]
    xs_der = [caja.x + caja.w for caja in c.cajas.values()]
    min_x = min(xs_izq) - ESPACIO_H
    ancho_total = (max(xs_der) - min(xs_izq)) + 2 * ESPACIO_H
    alto_total = c.cajas[fin_id].y + ALTO[FIN] + ESPACIO_V

    for caja in c.cajas.values():
        caja.x -= min_x
    for f in c.flechas:
        f.puntos = [(px - min_x, py) for px, py in f.puntos]

    return Diagrama(list(c.cajas.values()), c.flechas, ancho_total, alto_total)
