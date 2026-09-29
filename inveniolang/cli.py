# Interfaz de Línea de Comandos (CLI) de InvenioLang 1.0
# Permite ejecutar el compilador desde la terminal
# Uso: python -m inveniolang.cli <archivo.inv>
# Patrones: Facade (pipeline), Command (cada flag es comando), Template
# Method (fases), Strategy (formateo salida), Observer (progreso)
from __future__ import annotations

import os
import sys
from typing import Any

from . import ir as ir_mod
from .errors import ErrorManager
from .interpreter import DebugStopped, Interpreter
from .lexer import Lexer
from .parser import Parser
from .patterns import Command, CommandInvoker, Facade, Subject
from .semantic import SemanticAnalyzer
from .type_checker import TypeChecker

_MAX_FUENTE_BYTES = 1 * 1024 * 1024  # 1 MiB — evita DoS por archivo gigante
_RUTA_MAX_LEN = 512


def leer_fuente(ruta, error_manager=None):
    """Lee un archivo .inv validando su codificacion y límites de seguridad.

    La Seccion 2.1 exige que un archivo que no sea UTF-8 valido se rechace con
    IL-LEX-001 antes de iniciar el analisis lexico. Centralizar la lectura
    evita que alguna ruta del CLI deje escapar un UnicodeDecodeError crudo.
    Además valida longitud de ruta, tamaño y caracteres de control para
    evitar DoS / path traversal en entorno educativo compartido.

    Retorna (codigo, None) si la lectura tuvo exito, o (None, codigo_de_salida)
    si fallo. Cuando se pasa un `error_manager`, el diagnostico se registra en
    el para que las interfaces graficas puedan mostrarlo en su panel de errores.
    """
    nombre = os.path.basename(ruta) if ruta else "<desconocido>"
    # Validación básica de ruta
    if not ruta or not isinstance(ruta, str):
        msg = "Ruta de archivo vacía o inválida"
        if error_manager is not None:
            error_manager.set_archivo(nombre)
            error_manager.error_lexico("IL-LEX-001", msg, 0, 0)
        else:
            print(f"Error: {msg}")
        return None, 1
    if len(ruta) > _RUTA_MAX_LEN or "\x00" in ruta:
        msg = f"Ruta inválida o demasiado larga ({len(ruta)} chars)"
        if error_manager is not None:
            error_manager.set_archivo(nombre)
            error_manager.error_lexico("IL-LEX-001", msg, 0, 0)
        else:
            print(f"[IL-LEX-001] {nombre}:0:0 — {msg}")
        return None, 1
    # Advertencia de extensión (no bloqueante, pero informativa)
    if not ruta.lower().endswith(".inv"):
        # No falla: el CLI permite cualquier archivo, pero se registra si hay EM
        pass
    try:
        # Comprobar tamaño antes de leer
        try:
            tam = os.path.getsize(ruta)
            if tam > _MAX_FUENTE_BYTES:
                msg = f"Archivo demasiado grande ({tam} bytes, límite {_MAX_FUENTE_BYTES})"
                if error_manager is not None:
                    error_manager.set_archivo(nombre)
                    error_manager.error_lexico("IL-LEX-001", msg, 0, 0)
                else:
                    print(f"[IL-LEX-001] {nombre}:0:0 — {msg}")
                return None, 1
        except OSError:
            pass  # si no se puede stat, dejar que open falle
        with open(ruta, encoding="utf-8") as f:
            data = f.read(_MAX_FUENTE_BYTES + 1)
            if len(data) > _MAX_FUENTE_BYTES:
                msg = f"Archivo excede límite de {_MAX_FUENTE_BYTES} bytes"
                if error_manager is not None:
                    error_manager.set_archivo(nombre)
                    error_manager.error_lexico("IL-LEX-001", msg, 0, 0)
                else:
                    print(f"[IL-LEX-001] {nombre}:0:0 — {msg}")
                return None, 1
            return data, None
    except FileNotFoundError:
        mensaje = f"Archivo no encontrado: {ruta}"
        if error_manager is not None:
            error_manager.set_archivo(nombre)
            error_manager.error_lexico("IL-LEX-001", mensaje, 0, 0)
        else:
            print(f"Error: {mensaje}")
        return None, 1
    except UnicodeDecodeError as e:
        mensaje = f"El archivo no esta codificado en UTF-8 valido " f"(byte invalido en la posicion {e.start})"
        if error_manager is not None:
            error_manager.set_archivo(nombre)
            error_manager.error_lexico("IL-LEX-001", mensaje, 0, 0)
        else:
            print(f"[IL-LEX-001] {nombre}:0:0 — {mensaje}")
        return None, 1
    except OSError as e:
        mensaje = f"No se pudo leer el archivo: {ruta} ({e})"
        if error_manager is not None:
            error_manager.set_archivo(nombre)
            error_manager.error_lexico("IL-LEX-001", mensaje, 0, 0)
        else:
            print(f"[IL-LEX-001] {nombre}:0:0 — {mensaje}")
        return None, 1


def _imprimir_ast(nodo, nivel=0):
    """Imprime el AST de forma indentada."""
    if nodo is None:
        print("  " * nivel + "None")
        return
    texto = "  " * nivel + nodo.__class__.__name__
    if hasattr(nodo, "nombre") and nodo.nombre:
        texto += f"({nodo.nombre})"
    if hasattr(nodo, "tipo") and nodo.tipo:
        if isinstance(nodo.tipo, str):
            texto += f" : {nodo.tipo}"
    if hasattr(nodo, "tipo_retorno"):
        texto += f" : {nodo.tipo_retorno}"
    print(texto)
    if hasattr(nodo, "elementos") and nodo.elementos:
        for e in nodo.elementos:
            _imprimir_ast(e, nivel + 1)
    if hasattr(nodo, "bloque") and nodo.bloque:
        _imprimir_ast(nodo.bloque, nivel + 1)
    if hasattr(nodo, "declaraciones_globales"):
        for d in nodo.declaraciones_globales:
            _imprimir_ast(d, nivel + 1)
    if hasattr(nodo, "declaraciones_posteriores"):
        for d in nodo.declaraciones_posteriores:
            _imprimir_ast(d, nivel + 1)
    if hasattr(nodo, "subrutinas"):
        for s in nodo.subrutinas:
            _imprimir_ast(s, nivel + 1)
    if hasattr(nodo, "main") and nodo.main:
        _imprimir_ast(nodo.main, nivel + 1)


# ============================================================
# Patrones Facade + Command + Template Method para pipeline
# ============================================================


class CompilationCommand(Command):
    """Command para cada fase del pipeline — permite cola, undo, logging."""

    def __init__(self, name: str, func, *args, **kwargs):
        self.name = name
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def execute(self) -> Any:
        self.result = self.func(*self.args, **self.kwargs)
        return self.result


class CompilerFacade(Facade, Subject):
    """Facade que simplifica el pipeline completo lex→parse→semantic→types→run.
    Observer para progreso, Template Method para orden de fases.
    """

    def __init__(self):
        super().__init__()
        self.invoker = CommandInvoker()

    def execute(self, ruta: str, entrada: list[str] | None = None, modo: str = "run") -> dict[str, Any]:
        from .errors import ErrorManager as EM

        em = EM()
        codigo, fallo = leer_fuente(ruta, em)
        if fallo:
            return {"ok": False, "errores": em.obtener_reportes()}
        self.notify("inicio", ruta)
        # Template: fases secuenciales
        lex = Lexer(em)
        lex.tokenizar(codigo, ruta)
        if em.hay_errores():
            return {"ok": False, "errores": em.obtener_reportes()}
        parser = Parser(lex, em)
        ast, _ = parser.analizar(codigo, ruta)
        if em.hay_errores() or ast is None:
            return {"ok": False, "errores": em.obtener_reportes()}
        sem = SemanticAnalyzer(em)
        tabla = sem.analizar(ast)
        if em.hay_errores():
            return {"ok": False, "errores": em.obtener_reportes()}
        tc = TypeChecker(em, tabla)
        tc.verificar(ast)
        if em.hay_errores():
            return {"ok": False, "errores": em.obtener_reportes()}
        if modo == "check":
            return {"ok": True, "errores": []}
        interp = Interpreter(em, tabla)
        salida = interp.interpretar(ast, entrada)
        return {"ok": not em.hay_errores(), "salida": salida, "errores": em.obtener_reportes()}

    def check(self, ruta: str) -> dict[str, Any]:
        return self.execute(ruta, modo="check")


def _imprimir_errores_con_caret(error_manager, codigo: str, titulo: str) -> None:
    """Imprime los errores de una fase con contexto visual (UX/UDC):

        [IL-SIN-010] t.inv:1:23 — Se esperaba ";"
            1 | entero x = 2 escribir(x+3);
              |                      ^

    Ayuda al estudiante a localizar el error sin abrir el editor. Tolerante:
    si la línea/columna no existe en el fuente, solo imprime el reporte.
    """
    print(f"=== {titulo} ===")
    lineas = (codigo or "").splitlines()
    lineas_mostradas = set()
    for err in error_manager.errores:
        print(err.formato_oficial())
        try:
            linea_n = int(getattr(err, "linea", 0) or 0)
            col_n = int(getattr(err, "columna", 0) or 0)
            if 1 <= linea_n <= len(lineas) and linea_n not in lineas_mostradas:
                lineas_mostradas.add(linea_n)
                texto = lineas[linea_n - 1]
                col = max(0, min(col_n - 1, len(texto)))
                print(f"    {texto}")
                print(f"    {' ' * col}^")
        except (ValueError, AttributeError):
            continue


def _imprimir_advertencias(error_manager) -> None:
    if error_manager.warnings:
        print("=== ADVERTENCIAS ===")
        for warn in error_manager.obtener_advertencias():
            print(warn)


def ejecutar_archivo(ruta_archivo, entrada_usuario=None):
    """Ejecuta un archivo .inv a través de todo el pipeline del compilador.

    Args:
        ruta_archivo: Ruta al archivo .inv
        entrada_usuario: Lista opcional de strings para entrada estándar

    Retorna:
        Código de salida (0 = éxito, 1 = error)
    """
    # Leer archivo
    codigo, fallo = leer_fuente(ruta_archivo)
    if fallo is not None:
        return fallo

    nombre_archivo = os.path.basename(ruta_archivo)
    error_manager = ErrorManager()

    # === FASE 1: Análisis Léxico ===
    lexer = Lexer(error_manager)
    lexer.tokenizar(codigo, nombre_archivo)

    if error_manager.hay_errores():
        _imprimir_errores_con_caret(error_manager, codigo, "ERRORES LÉXICOS")
        return 1

    # === FASE 2: Análisis Sintáctico ===
    parser = Parser(lexer, error_manager)
    ast, error_manager = parser.analizar(codigo, nombre_archivo)

    if error_manager.hay_errores():
        _imprimir_errores_con_caret(error_manager, codigo, "ERRORES SINTÁCTICOS")
        return 1

    # === FASE 3: Análisis Semántico ===
    semantico = SemanticAnalyzer(error_manager)
    tabla = semantico.analizar(ast)

    if error_manager.hay_errores():
        _imprimir_errores_con_caret(error_manager, codigo, "ERRORES SEMÁNTICOS")
        return 1

    # Mostrar advertencias
    _imprimir_advertencias(error_manager)

    # === FASE 4: Verificación de Tipos ===
    type_checker = TypeChecker(error_manager, tabla)
    type_checker.verificar(ast)

    if error_manager.hay_errores():
        _imprimir_errores_con_caret(error_manager, codigo, "ERRORES DE TIPOS")
        return 1

    # === FASE 5: Interpretación ===
    interprete = Interpreter(error_manager, tabla)

    try:
        salida = interprete.interpretar(ast, entrada_usuario)
    except Exception as e:
        print(f"Error de ejecución: {e}")
        return 1

    # Mostrar errores de ejecución
    if error_manager.hay_errores():
        _imprimir_errores_con_caret(error_manager, codigo, "ERRORES DE EJECUCIÓN")
        return 1

    # Mostrar salida
    if salida:
        sys.stdout.write("".join(salida))

    return 0


def revisar_archivo(ruta, detalle=True):
    """Revisa un archivo .inv realizando el análisis estático completo
    (léxico -> sintáctico -> semántico -> tipos) SIN interpretar el programa.

    Es el equivalente CLI del análisis en vivo de la GUI: reporta errores y
    advertencias sin ejecutar el código.

    Args:
        ruta: Ruta al archivo .inv
        detalle: si True imprime el detalle de errores/advertencias

    Retorna:
        Código de salida (0 = sin errores, 1 = hay errores)
    """
    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return fallo

    nombre_archivo = os.path.basename(ruta)
    em = ErrorManager()

    # Análisis estático por etapas (sin intérprete)
    lexer = Lexer(em)
    lexer.tokenizar(codigo, nombre_archivo)
    if not em.hay_errores():
        parser = Parser(lexer, em)
        ast, em = parser.analizar(codigo, nombre_archivo)
        if ast is not None and not em.hay_errores():
            semantico = SemanticAnalyzer(em)
            tabla = semantico.analizar(ast)
            if not em.hay_errores():
                tc = TypeChecker(em, tabla)
                tc.verificar(ast)

    if detalle:
        print(f"=== ANÁLISIS ESTÁTICO: {nombre_archivo} ===")
        errores = em.obtener_reportes()
        advertencias = em.obtener_advertencias()
        if errores:
            print("ERRORES:")
            for e in errores:
                print(f"  {e}")
        if advertencias:
            print("ADVERTENCIAS:")
            for w in advertencias:
                print(f"  {w}")
        n_err = len(em.errores)
        n_warn = len(em.warnings)
        estado = "OK" if n_err == 0 else "ERROR"
        print(f"{estado} - {n_err} error(es), {n_warn} advertencia(s)")

    return 1 if em.hay_errores() else 0


def trazar_archivo(ruta, max_pasos=None):
    """Traza (según la ejecución) un archivo .inv: muestra cada instrucción
    ejecutada con sus variables y la pila de llamadas. Sin interpretar a ciegas.

    Args:
        ruta: Ruta al archivo .inv
        max_pasos: Límite opcional de pasos a registrar (protección/fragmento)

    Retorna:
        Código de salida (0 = sin errores en ejecución, 1 = hubo errores)
    """
    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return fallo

    nombre_archivo = os.path.basename(ruta)
    em = ErrorManager()

    lexer = Lexer(em)
    lexer.tokenizar(codigo, nombre_archivo)
    if em.hay_errores():
        print("ERRORES LÉXICOS")
        [print("  " + e.formato_oficial()) for e in em.obtener_reportes()]
        return 1
    parser = Parser(lexer, em)
    ast, em = parser.analizar(codigo, nombre_archivo)
    if em.hay_errores():
        print("ERRORES SINTÁCTICOS")
        [print("  " + e.formato_oficial()) for e in em.obtener_reportes()]
        return 1
    if ast is None:
        return 1
    semantico = SemanticAnalyzer(em)
    tabla = semantico.analizar(ast)
    if em.hay_errores():
        print("ERRORES SEMÁNTICOS")
        [print("  " + e.formato_oficial()) for e in em.obtener_reportes()]
        return 1
    tc = TypeChecker(em, tabla)
    tc.verificar(ast)
    if em.hay_errores():
        print("ERRORES DE TIPOS")
        [print("  " + e.formato_oficial()) for e in em.obtener_reportes()]
        return 1

    interp = Interpreter(em, tabla)
    interp.debug = True
    traza = []

    def on_statement(snap, pausar=False):
        # El intérprete invoca el callback como (snapshot, pausar) y usa el
        # valor retornado para decidir si debe bloquearse. La traza sólo
        # registra, nunca pausa.
        traza.append(snap)
        if max_pasos is not None and len(traza) >= max_pasos:
            interp.debug_detener = True
        return False

    interp.debug_on_statement = on_statement
    salida = []
    try:
        salida = interp.interpretar(ast, usar_stdin=False)
    except DebugStopped:
        pass  # límite de pasos alcanzado

    print(f"=== TRAZA DE EJECUCIÓN: {nombre_archivo} ===")
    for i, snap in enumerate(traza, 1):
        varmas = ", ".join(f"{v['nombre']}={v['valor']!r}" for v in snap["variables"])
        pila = "/".join(snap["pila"]) if snap["pila"] else "(main)"
        print(f"[{i:3}] L{snap['linea']:<4} pila={pila:<16} {varmas}")
    if salida:
        print("\n=== SALIDA ===")
        sys.stdout.write("".join(salida))
    n_err = len(em.errores)
    if n_err:
        print("\n=== ERRORES DE EJECUCIÓN ===")
        for e in em.obtener_reportes():
            print("  " + e)
    print(f"\nPasos registrados: {len(traza)}  Errores: {n_err}")
    return 1 if n_err else 0


def _compilar_estatico(ruta):
    """Corre léxico->sintáctico->semántico->tipos y retorna (ast, tabla, em)
    si no hubo errores, o (None, None, em) si los hubo (ya impresos).
    """
    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return None, None, None
    nombre_archivo = os.path.basename(ruta)
    em = ErrorManager()
    lexer = Lexer(em)
    lexer.tokenizar(codigo, nombre_archivo)
    if em.hay_errores():
        print("ERRORES LÉXICOS")
        for e in em.obtener_reportes():
            print("  " + e)
        return None, None, em
    parser = Parser(lexer, em)
    ast, em = parser.analizar(codigo, nombre_archivo)
    if em.hay_errores():
        print("ERRORES SINTÁCTICOS")
        for e in em.obtener_reportes():
            print("  " + e)
        return None, None, em
    semantico = SemanticAnalyzer(em)
    tabla = semantico.analizar(ast)
    if em.hay_errores():
        print("ERRORES SEMÁNTICOS")
        for e in em.obtener_reportes():
            print("  " + e)
        return None, None, em
    tc = TypeChecker(em, tabla)
    tc.verificar(ast)
    if em.hay_errores():
        print("ERRORES DE TIPOS")
        for e in em.obtener_reportes():
            print("  " + e)
        return None, None, em
    return ast, tabla, em


def _generar_ir_o_avisar(ast):
    """Genera el IR del programa, o imprime un aviso claro y retorna None si
    el programa usa una construcción fuera del alcance del generador
    (clases/POO, matrices) -- ver inveniolang/ir.py.
    """
    try:
        return ir_mod.generar_programa(ast)
    except ir_mod.NoSoportadoIR as e:
        print("=== CÓDIGO INTERMEDIO NO DISPONIBLE ===")
        print(f"  {e}")
        return None


def mostrar_ir(ruta, optimizar=False):
    """--ir / --ir-opt: genera y muestra el código de tres direcciones (TAC)
    del programa. Con `optimizar=True` corre además las pasadas de
    optimización y muestra un resumen de qué cambió cada una.
    """
    ast, tabla, em = _compilar_estatico(ruta)
    if ast is None:
        return 1

    generado = _generar_ir_o_avisar(ast)
    if generado is None:
        return 1
    subrutinas, globales = generado

    def _mostrar(nombre_titulo, instrucciones):
        print(f"--- {nombre_titulo} ---")
        print(ir_mod.formatear(instrucciones) if instrucciones else "  (vacío)")

    print(f"=== CÓDIGO INTERMEDIO (TAC): {os.path.basename(ruta)} ===")
    _mostrar("variables globales", globales)
    for nombre, (parametros, instrucciones) in subrutinas.items():
        firma = f"{nombre}({', '.join(parametros)})"
        _mostrar(firma, instrucciones)

    if optimizar:
        opt_globales, resumen_globales = ir_mod.optimizar(globales)
        opt_subrutinas, resumenes = ir_mod.optimizar_programa(subrutinas)
        print()
        print("=== CÓDIGO INTERMEDIO OPTIMIZADO ===")
        _mostrar("variables globales", opt_globales)
        if resumen_globales:
            print("  optimizaciones: " + ", ".join(f"{n} x{c}" for n, c in resumen_globales))
        for nombre, (parametros, instrucciones) in opt_subrutinas.items():
            firma = f"{nombre}({', '.join(parametros)})"
            _mostrar(firma, instrucciones)
            resumen = resumenes.get(nombre) or []
            if resumen:
                print("  optimizaciones: " + ", ".join(f"{n} x{c}" for n, c in resumen))

    return 0


def mostrar_objetivo(ruta, k_registros=None):
    """--target (Etapa 12.11): genera y muestra el código objetivo del ISA
    de juguete (traducido del TAC ya optimizado -- incluye la eliminación
    de recursión de cola de la Etapa 12.8 si aplica). Ver ir.py, sección
    "Etapa 12.11" para el ISA completo.

    --target-reg (Etapa 12.12, `k_registros` dado): además, corre
    liveness + asignación de registros (linear-scan) ANTES de traducir, y
    muestra un resumen de qué variable/temporal quedó en qué registro (o
    en memoria por spill) por cada subrutina -- comparar contra la salida
    de --target deja ver directamente cuántos nombres distintos se
    redujeron a los `k_registros` disponibles.
    """
    ast, tabla, em = _compilar_estatico(ruta)
    if ast is None:
        return 1

    generado = _generar_ir_o_avisar(ast)
    if generado is None:
        return 1
    subrutinas, globales = generado
    subrutinas_opt, _ = ir_mod.optimizar_programa(subrutinas)

    try:
        objetivo, resumen_registros = ir_mod.generar_objetivo_programa(subrutinas_opt, k_registros)
    except ir_mod.NoSoportadoObjetivo as e:
        print("=== CÓDIGO OBJETIVO NO DISPONIBLE ===")
        print(f"  {e}")
        return 1

    titulo = "CÓDIGO OBJETIVO CON REGISTROS" if k_registros else "CÓDIGO OBJETIVO (ISA de juguete)"
    print(f"=== {titulo}: {os.path.basename(ruta)} ===")
    if k_registros:
        print(f"  (linear-scan, {k_registros} registros disponibles)")
    for nombre, (parametros, instrucciones) in objetivo.items():
        firma = f"{nombre}({', '.join(parametros)})"
        print(f"--- {firma} ---")
        print(ir_mod.formatear_objetivo(instrucciones) if instrucciones else "  (vacío)")
        if nombre in resumen_registros:
            asignacion, spills = resumen_registros[nombre]
            registros = {v: r for v, r in asignacion.items() if r.startswith("R")}
            print(
                "  asignación: " + ", ".join(f"{v}->{r}" for v, r in registros.items())
                if registros
                else "  asignación: (sin variables con registro)"
            )
            if spills:
                print(f'  spill (memoria): {", ".join(spills)}')
    return 0


def ejecutar_con_ir(ruta, entrada_usuario=None, optimizado=False):
    """--run-ir: ejecuta el programa con MaquinaTAC (el motor del código
    intermedio) en vez del intérprete de árbol de producción, e imprime la
    salida con el mismo formato que la ejecución normal.
    """
    ast, tabla, em = _compilar_estatico(ruta)
    if ast is None:
        return 1

    generado = _generar_ir_o_avisar(ast)
    if generado is None:
        return 1
    subrutinas, globales = generado

    if optimizado:
        globales, _ = ir_mod.optimizar(globales)
        subrutinas, _ = ir_mod.optimizar_programa(subrutinas)

    maquina = ir_mod.MaquinaTAC(subrutinas, globales)
    try:
        salida = maquina.ejecutar(entrada_usuario)
    except Exception as e:
        print(f"Error de ejecución (MaquinaTAC): {e}")
        return 1

    if salida:
        sys.stdout.write("".join(salida))
    return 0


_VERSION = "10.0.0"


def build_argparser():
    import argparse

    p = argparse.ArgumentParser(prog="inveniolang", description="InvenioLang 10.0 — Compilador educativo estable")
    p.add_argument("archivo", nargs="?", help="Archivo .inv a compilar/ejecutar")
    p.add_argument("entrada", nargs="*", help="Entrada simulada para read/leer")
    p.add_argument("--check", action="store_true", help="Revisar sin ejecutar (léxico/sintáctico/semántico/tipos)")
    p.add_argument("--step", action="store_true", help="Traza paso a paso")
    p.add_argument("--maxpasos", type=int, default=None, help="Límite traza (con --step)")
    p.add_argument("--tokens", action="store_true", help="Mostrar tokens")
    p.add_argument("--ast", action="store_true", help="Mostrar AST")
    p.add_argument("--tabla", action="store_true", help="Mostrar tabla símbolos")
    p.add_argument("--ir", action="store_true", help="TAC sin optimizar")
    p.add_argument("--ir-opt", action="store_true", help="TAC optimizado")
    p.add_argument("--run-ir", action="store_true", help="Ejecutar con MaquinaTAC")
    p.add_argument("--run-ir-opt", action="store_true", help="MaquinaTAC optimizado (TCO)")
    p.add_argument("--target", action="store_true", help="Código objetivo ISA juguete")
    p.add_argument("--target-reg", action="store_true", help="Código objetivo + registros")
    p.add_argument("--json", action="store_true", help="Errores en JSON")
    p.add_argument(
        "--metrics",
        action="store_true",
        help="Compila y ejecuta por el pipeline puro reportando métricas por fase (JSON a stdout)",
    )
    p.add_argument(
        "--sandbox",
        action="store_true",
        help="Ejecuta el archivo aislado en subproceso con timeout y memoria limitada",
    )
    p.add_argument("--version", action="store_true", help="Versión")
    return p


def _ejecutar_con_metricas(ruta: str, entrada: list[str]) -> int:
    """Pipeline puro (core.compiler.compile_pure) con métricas por fase.

    Imprime a stdout un JSON con resultado + tiempos por fase; la salida del
    programa va en el campo `salida`. Útil para CI, docencia y benchmarking.
    """
    import json as _json

    from .core import CompileRequest, compile_pure
    from .observability import PipelineMetrics

    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return fallo
    metrics = PipelineMetrics()
    req = CompileRequest(ruta=ruta, codigo=codigo, entrada=tuple(entrada or ()))
    resultado = compile_pure(req, metrics=metrics)
    print(
        _json.dumps(
            {
                "archivo": ruta,
                "ok": resultado.ok,
                "salida": list(resultado.salida),
                "errores": list(resultado.errores),
                "metrics": metrics.to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if resultado.ok else 1


def main():
    """Punto de entrada de la CLI. v10.0 usa argparse con compatibilidad manual."""
    # Fast path para --help/--version sin archivo (argparse exigiría archivo)
    if len(sys.argv) < 2:
        build_argparser().print_help()
        return 1

    if "--version" in sys.argv:
        print(f"InvenioLang {_VERSION}")
        return 0

    if "--help" in sys.argv:
        print(f"InvenioLang {_VERSION} - Compilador e Intérprete")
        print("")
        print("Uso: python -m inveniolang.cli <archivo.inv> [entrada...]")
        print("")
        print("Opciones:")
        print("  --check       Revisar el código sin ejecutarlo")
        print("  --step        Mostrar la traza de ejecución (línea, variables, pila)")
        print("  --maxpasos N  Limitar la traza a N pasos")
        print("  --tokens      Mostrar solo los tokens")
        print("  --ast         Mostrar el AST")
        print("  --tabla       Mostrar la tabla de símbolos")
        print("  --ir          Mostrar el código de tres direcciones (TAC) sin optimizar")
        print("  --ir-opt      Mostrar el TAC optimizado (plegado de constantes, código")
        print("                muerto, peephole) y un resumen de qué cambió cada pasada")
        print("  --run-ir      Ejecutar con la MaquinaTAC en vez del intérprete de árbol")
        print("                (subconjunto estructurado: sin clases/POO ni matrices)")
        print("  --run-ir-opt  Igual que --run-ir, pero sobre el TAC optimizado -- incluye")
        print("                la eliminación de recursión de cola (Etapa 12.8): una función")
        print("                escrita con acumulador y llamada de cola directa corre con")
        print("                profundidad de pila CONSTANTE, a diferencia de --run-ir (sin")
        print("                optimizar) y del intérprete de árbol (interpreter.py NUNCA")
        print("                aplica TCO), que siguen limitados por la recursión real.")
        print("  --target      Mostrar el código objetivo: traduce el TAC optimizado a un")
        print("                ISA de juguete de pila de operandos (PUSH/LOAD/STORE/ADD/...,")
        print("                ver ir.py sección Etapa 12.11) -- cierra el pipeline fuente ->")
        print("                AST -> TAC -> TAC optimizado -> código objetivo. Mismo alcance")
        print("                que --run-ir, MENOS arreglos y try/catch.")
        print("  --target-reg  Igual que --target, pero antes corre liveness analysis +")
        print("                asignación de registros (linear-scan, Etapa 12.12, 4 registros)")
        print("                sobre el TAC -- muestra qué variable/temporal quedó en qué")
        print("                registro ('R0'..'R3') o en memoria por spill, por subrutina.")
        print("  --json        Salida de errores en formato JSON (para integración con IDE/CI)")
        print("  --sandbox     Ejecutar aislado en sandbox (timeout y memoria limitada)")
        print("  --version     Mostrar versión")
        print("  --help        Mostrar esta ayuda")
        print("")
        print("Para entrada interactiva, pasar valores después del archivo:")
        print("  python -m inveniolang.cli programa.inv 42 3.14 Hola")
        return 0

    # v10.0: argparse puro (valida --help y tipos), con fallback manual para compatibilidad
    try:
        pargs = build_argparser().parse_args()
    except SystemExit as e:
        return e.code
    # --version/--help ya manejados arriba, pero argparse también los maneja
    if pargs.version:
        print(f"InvenioLang {_VERSION}")
        return 0
    if not pargs.archivo:
        print("Error: No se especificó archivo")
        build_argparser().print_help()
        return 1
    ruta = pargs.archivo
    entrada = pargs.entrada or []
    # mapeo argparse → lógica existente (convierte dest con guiones)
    solo_check = pargs.check
    solo_step = pargs.step
    solo_tokens = pargs.tokens
    solo_ast = pargs.ast
    solo_tabla = pargs.tabla
    solo_ir = pargs.ir
    solo_ir_opt = getattr(pargs, "ir_opt", False)
    correr_ir = getattr(pargs, "run_ir", False)
    correr_ir_opt = getattr(pargs, "run_ir_opt", False)
    solo_objetivo = pargs.target
    solo_objetivo_reg = getattr(pargs, "target_reg", False)
    max_pasos_cli = pargs.maxpasos

    # Observabilidad: pipeline puro + métricas por fase en JSON (auditoría v10.2)
    if getattr(pargs, "metrics", False):
        return _ejecutar_con_metricas(ruta, entrada)

    # Aislamiento: subproceso con límites, sin cambiar el pipeline por defecto
    if getattr(pargs, "sandbox", False):
        from .sandbox import run_sandboxed as _run_sb

        r = _run_sb(ruta, strategy="resource", timeout=5)
        if r.get("stdout"):
            print(r["stdout"], end="" if r["stdout"].endswith("\n") else "\n")
        if not r.get("ok") and r.get("stderr"):
            print(r["stderr"])
        return 0 if r.get("ok") else 1

    # Revisar sin ejecutar: análisis estático completo
    if solo_check:
        if pargs.json:
            import json

            from .errors import ErrorManager as EM2

            em2 = EM2()
            codigo2, _ = leer_fuente(ruta, em2)
            if codigo2 is not None:
                from .lexer import Lexer as Lx2
                from .parser import Parser as Pa2
                from .semantic import SemanticAnalyzer as Se2
                from .type_checker import TypeChecker as Tc2

                lx = Lx2(em2)
                lx.tokenizar(codigo2, ruta)
                if not em2.hay_errores():
                    pa, _ = Pa2(lx, em2).analizar(codigo2, ruta)
                    if pa and not em2.hay_errores():
                        ta = Se2(em2).analizar(pa)
                        if not em2.hay_errores():
                            Tc2(em2, ta).verificar(pa)
            print(
                json.dumps(
                    {"archivo": ruta, "errores": em2.obtener_reportes_json(), "ok": not em2.hay_errores()},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if not em2.hay_errores() else 1
        return revisar_archivo(ruta)

    # Traza de ejecución (paso a paso con variables y pila)
    if solo_step:
        return trazar_archivo(ruta, max_pasos_cli)

    if solo_ir:
        return mostrar_ir(ruta, optimizar=False)

    if solo_ir_opt:
        return mostrar_ir(ruta, optimizar=True)

    if solo_objetivo:
        return mostrar_objetivo(ruta)

    if solo_objetivo_reg:
        return mostrar_objetivo(ruta, k_registros=4)

    if correr_ir_opt:
        return ejecutar_con_ir(ruta, entrada if entrada else None, optimizado=True)

    if correr_ir:
        return ejecutar_con_ir(ruta, entrada if entrada else None)

    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return fallo

    nombre_archivo = os.path.basename(ruta)
    error_manager = ErrorManager()

    if solo_tokens:
        lexer = Lexer(error_manager)
        tokens = lexer.tokenizar(codigo, nombre_archivo)
        for tok in tokens:
            print(f"{tok[0]:20s} {repr(tok[1]):30s} L{tok[2]}:C{tok[3]}")
        if error_manager.hay_errores():
            for rep in error_manager.obtener_reportes():
                print(rep)
        return 0

    if solo_ast:
        pass

        lexer = Lexer(error_manager)
        parser = Parser(lexer, error_manager)
        ast, _ = parser.analizar(codigo, nombre_archivo)
        if ast:
            _imprimir_ast(ast)
        if error_manager.hay_errores():
            for rep in error_manager.obtener_reportes():
                print(rep)
        return 0

    if solo_tabla:
        from .semantic import SemanticAnalyzer

        lexer = Lexer(error_manager)
        parser = Parser(lexer, error_manager)
        ast, _ = parser.analizar(codigo, nombre_archivo)
        if ast:
            sem = SemanticAnalyzer(error_manager)
            tabla = sem.analizar(ast)
            print("=== TABLA DE SÍMBOLOS ===")
            for nombre, entrada in tabla.obtener_simbolos_visibles().items():
                print(f"  {entrada}")
        return 0

    return ejecutar_archivo(ruta, entrada if entrada else None)


if __name__ == "__main__":
    sys.exit(main())
