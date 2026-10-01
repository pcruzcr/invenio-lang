# Constructor de diagramas de flujo de InvenioLang (Etapa 13, Fase 1/Fase 2)
# Patrones: Builder (diagrama → código), Factory (bloques), Command (insertar/mover/eliminar),
# Observer (validación viva), Strategy (generación de texto)
#
# Cierra el hueco identificado al revisar el cierre de Fase 1/Fase 2:
# `flowchart.py` ya genera un diagrama de flujo A PARTIR de código ya
# escrito (herramienta de REVELAR); este módulo hace el camino inverso --
# el ESTUDIANTE arma el diagrama insertando bloques de una paleta
# (Proceso, Decisión, Mientras, Hacer-mientras, Para, Entrada, Salida) en
# una secuencia, y el módulo GENERA el código InvenioLang correspondiente.
#
# Decisión de diseño clave: un diagrama de flujo dibujado libremente
# (cajas + flechas arbitrarias) es un GRAFO; InvenioLang es un lenguaje
# ESTRUCTURADO (sin goto). Convertir un grafo arbitrario a código
# estructurado es un problema de "structuring" de flujo de control
# genuinamente difícil y con casos sin solución limpia. Se evita por
# completo NO permitiendo dibujo libre de flechas: el estado interno del
# diagrama es literalmente un `Bloque` real de `ast_nodes.py` (mismas
# clases que usa el parser real -- IfStmt/WhileStmt/DoWhileStmt/ForStmt/
# PrintStmt/ReadStmt/...), así que es estructuralmente válido por
# construcción, nunca ambiguo -- exactamente igual que cualquier `Bloque`
# que ya produce `parser.py` a partir de código real.
#
# Reuso deliberado, cero mecanismo nuevo de análisis:
#   - Cada fragmento de texto que escribe el estudiante en una caja (una
#     instrucción, una condición, ...) se valida ENVOLVIÉNDOLO en un
#     programa mínimo (`void main() { ... }`, o la forma que corresponda
#     -- `si (...) { }`, `mientras (...) { }`, ...) y corriéndolo por el
#     Lexer/Parser REAL -- mismo patrón que ya usan
#     `pruebas/conformidad.py::analizar()` e
#     `inveniolang/ll1_demo.py::_evaluar_lalr()`. Nunca se escribe un
#     segundo analizador.
#   - La generación de texto para las instrucciones HOJA (asignaciones,
#     imprimir/leer, declaraciones, ...) reutiliza
#     `flowchart.py::_texto_instruccion`/`_texto_expr`/
#     `_texto_for_init_act` tal cual -- este módulo solo añade el
#     "envoltorio" de las construcciones de control (si/mientras/
#     hacer-mientras/para) que `flowchart.py` no necesita como texto
#     (las dibuja directamente con su propio layout).
#   - La vista previa en vivo (en gui_qt.py) reutiliza
#     `flowchart.py::construir_diagrama(bloque)` sin ningún caso
#     especial: el `Bloque` que arma el estudiante es indistinguible,
#     para ese motor, del `Bloque` de un archivo `.inv` real.
#
# ALCANCE v1 (documentado explícitamente, mismo criterio que excluye
# POO/matrices de `ir.py`): secuencia, si/si-sino, mientras,
# hacer-mientras, para, entrada (`leer`), salida (`imprimir`), proceso
# (una instrucción o declaración suelta). Genera siempre el cuerpo de
# `void main()`. Fuera de alcance v1: switch/case, try/catch,
# romper/continuar, múltiples funciones/procedimientos por diagrama,
# clases/POO/arreglos dentro del diagrama.

from __future__ import annotations

from . import flowchart as fc
from .ast_nodes import Bloque, DoWhileStmt, ForStmt, IfStmt, WhileStmt
from .errors import ErrorManager, InvenioLangError
from .lexer import Lexer
from .parser import Parser
from .semantic import SemanticAnalyzer
from .type_checker import TypeChecker

# ---- Formas de la paleta (vocabulario propio de este módulo -- INICIO/FIN
# no aplican, siempre hay exactamente uno de cada uno al principio/final
# del diagrama y el estudiante no los inserta) ----
PROCESO = "proceso"
ENTRADA = "entrada"
SALIDA = "salida"
DECISION = "decision"
MIENTRAS = "mientras"
HACER_MIENTRAS = "hacer_mientras"
PARA = "para"

FORMAS_PALETA = (PROCESO, ENTRADA, SALIDA, DECISION, MIENTRAS, HACER_MIENTRAS, PARA)


def _error_local(mensaje):
    """Error propio de este módulo (p. ej. "debe ser una sola.

    instrucción"), NO del catálogo oficial IL-* (§18.1: ese catálogo es
    estable entre versiones) -- código con prefijo distinto a propósito,
    para que nunca se confunda con un diagnóstico real del compilador.
    """
    return InvenioLangError("DIAG-001", mensaje, 1, 1, "diagrama")


def _parsear_programa(codigo):
    """Corre Lexer + Parser (solo sintaxis, sin semántico/tipos -- eso se.

    hace aparte, sobre el diagrama COMPLETO, ver `validar_diagrama`) sobre
    un programa envoltorio mínimo. Retorna (ast, errores) -- ast es None
    si errores no está vacío.
    """
    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(codigo, "diagrama.inv")
    if em.hay_errores():
        return None, list(em.errores)
    p = Parser(lx, em)
    ast, em = p.analizar(codigo, "diagrama.inv")
    if ast is None or em.hay_errores():
        return None, list(em.errores)
    return ast, []


# ============================================================
# Validación + construcción de cada forma de la paleta
# ============================================================


def _asegurar_punto_coma(texto):
    """Le agrega ";" al final si el estudiante no lo escribió -- el resto.

    de las formas (Entrada/Salida/condiciones) nunca le piden el ";" al
    estudiante (va implícito en la plantilla que las envuelve), así que
    Proceso tampoco debería exigírselo.
    """
    texto = texto.strip()
    if texto and not texto.endswith((";", "}")):
        texto += ";"
    return texto


def crear_proceso(texto):
    """Valida `texto` como UNA instrucción o declaración suelta InvenioLang.

    (asignación, incremento/decremento, llamada, declaración de variable/
    constante, ...). No hace falta escribir el ";" final. Retorna
    (nodo, errores).
    """
    ast, errores = _parsear_programa(f"void main() {{ {_asegurar_punto_coma(texto)} }}")
    if errores:
        return None, errores
    elementos = ast.main.bloque.elementos
    if len(elementos) != 1:
        return None, [
            _error_local(
                'Un bloque de "Proceso" debe contener exactamente una instrucción o declaración.'
            )
        ]
    return elementos[0], []


def crear_entrada(texto):
    """`texto` debe ser un identificador simple (variable ya declarada.

    antes en el diagrama -- eso se comprueba al validar el diagrama
    completo, no aquí). Retorna (ReadStmt, errores).
    """
    ast, errores = _parsear_programa(f"void main() {{ leer({texto}); }}")
    if errores:
        return None, errores
    return ast.main.bloque.elementos[0], []


def crear_salida(texto):
    """`texto` es cualquier expresión InvenioLang válida. Retorna.

    (PrintStmt, errores).
    """
    ast, errores = _parsear_programa(f"void main() {{ imprimir({texto}); }}")
    if errores:
        return None, errores
    return ast.main.bloque.elementos[0], []


def crear_decision(texto_condicion):
    """Retorna (IfStmt con ramas vacías, errores)."""
    ast, errores = _parsear_programa(f"void main() {{ si ({texto_condicion}) {{ }} }}")
    if errores:
        return None, errores
    condicion = ast.main.bloque.elementos[0].condicion
    return IfStmt(condicion, Bloque([]), None), []


def crear_mientras(texto_condicion):
    """Retorna (WhileStmt con cuerpo vacío, errores)."""
    ast, errores = _parsear_programa(f"void main() {{ mientras ({texto_condicion}) {{ }} }}")
    if errores:
        return None, errores
    condicion = ast.main.bloque.elementos[0].condicion
    return WhileStmt(condicion, Bloque([])), []


def crear_hacer_mientras(texto_condicion):
    """Retorna (DoWhileStmt con cuerpo vacío, errores)."""
    ast, errores = _parsear_programa(f"void main() {{ hacer {{ }} mientras ({texto_condicion}); }}")
    if errores:
        return None, errores
    condicion = ast.main.bloque.elementos[0].condicion
    return DoWhileStmt(Bloque([]), condicion), []


def crear_para(texto_init, texto_cond, texto_paso):
    """Los tres campos se ensamblan tal cual en la cabecera real de un.

    `para (init; cond; paso)`. Retorna (ForStmt con cuerpo vacío, errores).
    """
    ast, errores = _parsear_programa(
        f"void main() {{ para ({texto_init}; {texto_cond}; {texto_paso}) {{ }} }}"
    )
    if errores:
        return None, errores
    nodo = ast.main.bloque.elementos[0]
    return ForStmt(nodo.init_stmt, nodo.cond_expr, nodo.act_stmt, Bloque([])), []


# ============================================================
# Edición del árbol -- operan sobre las listas Bloque.elementos reales;
# el propio Bloque/IfStmt.bloque_then/IfStmt.bloque_else/WhileStmt.bloque/
# DoWhileStmt.bloque/ForStmt.bloque YA son la estructura de árbol, no hace
# falta una clase nueva.
# ============================================================


def insertar(bloque, indice, nodo):
    """Inserta un nodo en el bloque."""
    bloque.elementos.insert(indice, nodo)


def reemplazar(bloque, nodo_viejo, nodo_nuevo):
    """Sustituye `nodo_viejo` por `nodo_nuevo` EN SU MISMA POSICIÓN dentro.

    de `bloque.elementos` -- para editar el texto de una caja hoja
    (Proceso/Entrada/Salida) sin perder el orden de sus hermanas. Para
    editar solo la condición de una Decisión/Mientras/Hacer-mientras/Para
    (que sí tienen hijos que preservar -- sus ramas/cuerpo), es mejor
    mutar `.condicion` (o `.init_stmt`/`.cond_expr`/`.act_stmt`) del nodo
    EXISTENTE directamente en vez de reemplazarlo entero; ver el uso de
    esta función en gui_qt.py.
    """
    bloque.elementos[bloque.elementos.index(nodo_viejo)] = nodo_nuevo


def eliminar(bloque, nodo):
    """Elimina un nodo del bloque."""
    bloque.elementos.remove(nodo)


def mover(bloque, nodo, delta):
    """Desplaza `nodo` `delta` posiciones dentro de `bloque.elementos`.

    (-1 = subir, +1 = bajar). No hace nada si el movimiento se sale de
    los límites de la lista.
    """
    i = bloque.elementos.index(nodo)
    j = i + delta
    if 0 <= j < len(bloque.elementos):
        bloque.elementos[i], bloque.elementos[j] = bloque.elementos[j], bloque.elementos[i]


def agregar_rama_else(if_stmt):
    """Agrega una rama "sino" vacía a un IfStmt que no la tenía."""
    if if_stmt.bloque_else is None:
        if_stmt.bloque_else = Bloque([])


def quitar_rama_else(if_stmt):
    """Quita la rama else del condicional."""
    if_stmt.bloque_else = None


# ============================================================
# Generación de texto InvenioLang desde el Bloque construido
# ============================================================


def _sangria(nivel):
    return "    " * nivel


def _registrar(nodo, lineas, mapa_lineas):
    # La próxima línea que se agregue a `lineas` será, una vez agregada,
    # la línea número len(lineas) + 1 (1-indexado, mismo criterio que
    # Lexer/Parser al reportar `.linea` en un error).
    mapa_lineas[id(nodo)] = len(lineas) + 1


def _emitir_bloque(bloque, nivel, lineas, mapa_lineas):
    for nodo in bloque.elementos:
        _emitir_instruccion(nodo, nivel, lineas, mapa_lineas)


def _emitir_instruccion(nodo, nivel, lineas, mapa_lineas):
    ind = _sangria(nivel)
    if isinstance(nodo, IfStmt):
        _registrar(nodo, lineas, mapa_lineas)
        lineas.append(f"{ind}si ({fc._texto_expr(nodo.condicion)}) {{")
        _emitir_bloque(nodo.bloque_then, nivel + 1, lineas, mapa_lineas)
        if nodo.bloque_else is not None:
            lineas.append(f"{ind}}} sino {{")
            _emitir_bloque(nodo.bloque_else, nivel + 1, lineas, mapa_lineas)
        lineas.append(f"{ind}}}")
    elif isinstance(nodo, WhileStmt):
        _registrar(nodo, lineas, mapa_lineas)
        lineas.append(f"{ind}mientras ({fc._texto_expr(nodo.condicion)}) {{")
        _emitir_bloque(nodo.bloque, nivel + 1, lineas, mapa_lineas)
        lineas.append(f"{ind}}}")
    elif isinstance(nodo, DoWhileStmt):
        _registrar(nodo, lineas, mapa_lineas)
        lineas.append(f"{ind}hacer {{")
        _emitir_bloque(nodo.bloque, nivel + 1, lineas, mapa_lineas)
        lineas.append(f"{ind}}} mientras ({fc._texto_expr(nodo.condicion)});")
    elif isinstance(nodo, ForStmt):
        _registrar(nodo, lineas, mapa_lineas)
        init_txt = fc._texto_for_init_act(nodo.init_stmt)
        act_txt = fc._texto_for_init_act(nodo.act_stmt)
        cond_txt = fc._texto_expr(nodo.cond_expr)
        lineas.append(f"{ind}para ({init_txt}; {cond_txt}; {act_txt}) {{")
        _emitir_bloque(nodo.bloque, nivel + 1, lineas, mapa_lineas)
        lineas.append(f"{ind}}}")
    else:
        texto = fc._texto_instruccion(nodo)
        _registrar(nodo, lineas, mapa_lineas)
        lineas.append(f"{ind}{texto};" if texto is not None else f"{ind}/* forma no soportada */")


def generar_texto_main(bloque):
    """Genera el programa InvenioLang COMPLETO (`void main() { ... }`) a.

    partir del `Bloque` construido en el panel. Retorna (texto,
    mapa_lineas) -- mapa_lineas: dict[id(nodo) -> línea 1-indexada],
    usado por `validar_diagrama` para reasignar cada error a la caja que
    lo originó.
    """
    lineas = ["void main() {"]
    mapa_lineas = {}
    _emitir_bloque(bloque, 1, lineas, mapa_lineas)
    lineas.append("}")
    return "\n".join(lineas) + "\n", mapa_lineas


def validar_diagrama(bloque):
    """Corre el pipeline completo (Lexer -> Parser -> SemanticAnalyzer ->.

    TypeChecker, mismo orden que `pruebas/conformidad.py::analizar()`)
    sobre el texto generado por TODO el diagrama junto -- así una caja que
    lee una variable declarada en una caja anterior no se marca como error
    falso (a diferencia de validar cada caja aislada). Retorna (texto,
    errores_por_nodo) -- errores_por_nodo: dict[id(nodo) ->
    list[InvenioLangError]], solo con entradas para los nodos que
    realmente tienen algún error asociado.
    """
    texto, mapa_lineas = generar_texto_main(bloque)
    linea_a_nodo = {linea: id_nodo for id_nodo, linea in mapa_lineas.items()}

    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(texto, "diagrama.inv")
    ast = None
    if not em.hay_errores():
        p = Parser(lx, em)
        ast, em = p.analizar(texto, "diagrama.inv")
        if ast is not None and not em.hay_errores():
            sem = SemanticAnalyzer(em)
            tabla = sem.analizar(ast)
            if not em.hay_errores():
                TypeChecker(em, tabla).verificar(ast)

    errores_por_nodo = {}
    for err in em.errores:
        id_nodo = linea_a_nodo.get(err.linea)
        errores_por_nodo.setdefault(id_nodo, []).append(err)
    return texto, errores_por_nodo
