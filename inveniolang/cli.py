# Interfaz de Línea de Comandos (CLI) de InvenioLang 1.0
# Permite ejecutar el compilador desde la terminal
# Uso: python -m inveniolang.cli <archivo.inv>

import sys
import os
from .lexer import Lexer
from .parser import Parser
from .errors import ErrorManager
from .semantic import SemanticAnalyzer
from .type_checker import TypeChecker
from .interpreter import Interpreter, DebugStopped
from . import ir as ir_mod


def leer_fuente(ruta, error_manager=None):
    """Lee un archivo .inv validando su codificacion.

    La Seccion 2.1 exige que un archivo que no sea UTF-8 valido se rechace con
    IL-LEX-001 antes de iniciar el analisis lexico. Centralizar la lectura
    evita que alguna ruta del CLI deje escapar un UnicodeDecodeError crudo.

    Retorna (codigo, None) si la lectura tuvo exito, o (None, codigo_de_salida)
    si fallo. Cuando se pasa un `error_manager`, el diagnostico se registra en
    el para que las interfaces graficas puedan mostrarlo en su panel de errores.
    """
    nombre = os.path.basename(ruta)
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read(), None
    except FileNotFoundError:
        mensaje = f"Archivo no encontrado: {ruta}"
        if error_manager is not None:
            error_manager.set_archivo(nombre)
            error_manager.error_lexico('IL-LEX-001', mensaje, 0, 0)
        else:
            print(f"Error: {mensaje}")
        return None, 1
    except UnicodeDecodeError as e:
        mensaje = (f"El archivo no esta codificado en UTF-8 valido "
                   f"(byte invalido en la posicion {e.start})")
        if error_manager is not None:
            error_manager.set_archivo(nombre)
            error_manager.error_lexico('IL-LEX-001', mensaje, 0, 0)
        else:
            print(f"[IL-LEX-001] {nombre}:0:0 — {mensaje}")
        return None, 1


def _imprimir_ast(nodo, nivel=0):
    """Imprime el AST de forma indentada."""
    if nodo is None:
        print("  " * nivel + "None")
        return
    texto = "  " * nivel + nodo.__class__.__name__
    if hasattr(nodo, 'nombre') and nodo.nombre:
        texto += f"({nodo.nombre})"
    if hasattr(nodo, 'tipo') and nodo.tipo:
        if isinstance(nodo.tipo, str):
            texto += f" : {nodo.tipo}"
    if hasattr(nodo, 'tipo_retorno'):
        texto += f" : {nodo.tipo_retorno}"
    print(texto)
    if hasattr(nodo, 'elementos') and nodo.elementos:
        for e in nodo.elementos:
            _imprimir_ast(e, nivel + 1)
    if hasattr(nodo, 'bloque') and nodo.bloque:
        _imprimir_ast(nodo.bloque, nivel + 1)
    if hasattr(nodo, 'declaraciones_globales'):
        for d in nodo.declaraciones_globales:
            _imprimir_ast(d, nivel + 1)
    if hasattr(nodo, 'declaraciones_posteriores'):
        for d in nodo.declaraciones_posteriores:
            _imprimir_ast(d, nivel + 1)
    if hasattr(nodo, 'subrutinas'):
        for s in nodo.subrutinas:
            _imprimir_ast(s, nivel + 1)
    if hasattr(nodo, 'main') and nodo.main:
        _imprimir_ast(nodo.main, nivel + 1)


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
    tokens = lexer.tokenizar(codigo, nombre_archivo)

    if error_manager.hay_errores():
        print("=== ERRORES LÉXICOS ===")
        for reporte in error_manager.obtener_reportes():
            print(reporte)
        return 1

    # === FASE 2: Análisis Sintáctico ===
    parser = Parser(lexer, error_manager)
    ast, error_manager = parser.analizar(codigo, nombre_archivo)

    if error_manager.hay_errores():
        print("=== ERRORES SINTÁCTICOS ===")
        for reporte in error_manager.obtener_reportes():
            print(reporte)
        return 1

    # === FASE 3: Análisis Semántico ===
    semantico = SemanticAnalyzer(error_manager)
    tabla = semantico.analizar(ast)

    if error_manager.hay_errores():
        print("=== ERRORES SEMÁNTICOS ===")
        for reporte in error_manager.obtener_reportes():
            print(reporte)
        return 1

    # Mostrar advertencias
    if error_manager.warnings:
        print("=== ADVERTENCIAS ===")
        for warn in error_manager.obtener_advertencias():
            print(warn)

    # === FASE 4: Verificación de Tipos ===
    type_checker = TypeChecker(error_manager, tabla)
    type_checker.verificar(ast)

    if error_manager.hay_errores():
        print("=== ERRORES DE TIPOS ===")
        for reporte in error_manager.obtener_reportes():
            print(reporte)
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
        print("=== ERRORES DE EJECUCIÓN ===")
        for reporte in error_manager.obtener_reportes():
            print(reporte)
        return 1

    # Mostrar salida
    if salida:
        sys.stdout.write(''.join(salida))

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
        print("ERRORES LÉXICOS"); [print("  " + e.formato_oficial())
                                   for e in em.obtener_reportes()]; return 1
    parser = Parser(lexer, em)
    ast, em = parser.analizar(codigo, nombre_archivo)
    if em.hay_errores():
        print("ERRORES SINTÁCTICOS"); [print("  " + e.formato_oficial())
                                       for e in em.obtener_reportes()]; return 1
    if ast is None:
        return 1
    semantico = SemanticAnalyzer(em)
    tabla = semantico.analizar(ast)
    if em.hay_errores():
        print("ERRORES SEMÁNTICOS"); [print("  " + e.formato_oficial())
                                      for e in em.obtener_reportes()]; return 1
    tc = TypeChecker(em, tabla)
    tc.verificar(ast)
    if em.hay_errores():
        print("ERRORES DE TIPOS"); [print("  " + e.formato_oficial())
                                    for e in em.obtener_reportes()]; return 1

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
        varmas = ", ".join(f"{v['nombre']}={v['valor']!r}" for v in snap['variables'])
        pila = "/".join(snap['pila']) if snap['pila'] else "(main)"
        print(f"[{i:3}] L{snap['linea']:<4} pila={pila:<16} {varmas}")
    if salida:
        print("\n=== SALIDA ===")
        sys.stdout.write(''.join(salida))
    n_err = len(em.errores)
    if n_err:
        print("\n=== ERRORES DE EJECUCIÓN ===")
        for e in em.obtener_reportes():
            print("  " + e)
    print(f"\nPasos registrados: {len(traza)}  Errores: {n_err}")
    return 1 if n_err else 0


def _compilar_estatico(ruta):
    """Corre léxico->sintáctico->semántico->tipos y retorna (ast, tabla, em)
    si no hubo errores, o (None, None, em) si los hubo (ya impresos)."""
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
    (clases/POO, matrices) -- ver inveniolang/ir.py."""
    try:
        return ir_mod.generar_programa(ast)
    except ir_mod.NoSoportadoIR as e:
        print("=== CÓDIGO INTERMEDIO NO DISPONIBLE ===")
        print(f"  {e}")
        return None


def mostrar_ir(ruta, optimizar=False):
    """--ir / --ir-opt: genera y muestra el código de tres direcciones (TAC)
    del programa. Con `optimizar=True` corre además las pasadas de
    optimización y muestra un resumen de qué cambió cada una."""
    ast, tabla, em = _compilar_estatico(ruta)
    if ast is None:
        return 1

    generado = _generar_ir_o_avisar(ast)
    if generado is None:
        return 1
    subrutinas, globales = generado

    def _mostrar(nombre_titulo, instrucciones):
        print(f'--- {nombre_titulo} ---')
        print(ir_mod.formatear(instrucciones) if instrucciones else '  (vacío)')

    print(f"=== CÓDIGO INTERMEDIO (TAC): {os.path.basename(ruta)} ===")
    _mostrar('variables globales', globales)
    for nombre, (parametros, instrucciones) in subrutinas.items():
        firma = f"{nombre}({', '.join(parametros)})"
        _mostrar(firma, instrucciones)

    if optimizar:
        opt_globales, resumen_globales = ir_mod.optimizar(globales)
        opt_subrutinas, resumenes = ir_mod.optimizar_programa(subrutinas)
        print()
        print("=== CÓDIGO INTERMEDIO OPTIMIZADO ===")
        _mostrar('variables globales', opt_globales)
        if resumen_globales:
            print('  optimizaciones: ' + ', '.join(f'{n} x{c}' for n, c in resumen_globales))
        for nombre, (parametros, instrucciones) in opt_subrutinas.items():
            firma = f"{nombre}({', '.join(parametros)})"
            _mostrar(firma, instrucciones)
            resumen = resumenes.get(nombre) or []
            if resumen:
                print('  optimizaciones: ' + ', '.join(f'{n} x{c}' for n, c in resumen))

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
    redujeron a los `k_registros` disponibles."""
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
        print(f'--- {firma} ---')
        print(ir_mod.formatear_objetivo(instrucciones) if instrucciones else '  (vacío)')
        if nombre in resumen_registros:
            asignacion, spills = resumen_registros[nombre]
            registros = {v: r for v, r in asignacion.items() if r.startswith('R')}
            print('  asignación: ' + ', '.join(f'{v}->{r}' for v, r in registros.items())
                  if registros else '  asignación: (sin variables con registro)')
            if spills:
                print(f'  spill (memoria): {", ".join(spills)}')
    return 0


def ejecutar_con_ir(ruta, entrada_usuario=None, optimizado=False):
    """--run-ir: ejecuta el programa con MaquinaTAC (el motor del código
    intermedio) en vez del intérprete de árbol de producción, e imprime la
    salida con el mismo formato que la ejecución normal."""
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
        sys.stdout.write(''.join(salida))
    return 0


def main():
    """Punto de entrada de la CLI."""
    if len(sys.argv) < 2:
        print("Uso: python -m inveniolang.cli <archivo.inv> [entrada...]")
        print("")
        print("Opciones:")
        print("  --check       Revisar el código sin ejecutarlo (léxico, sintáctico, semántico y tipos)")
        print("  --step        Ejecutar mostrando la traza (linea, variables y pila) de cada instrucción")
        print("  --maxpasos N  Limitar la traza a N pasos (con --step)")
        print("  --tokens      Mostrar solo los tokens (análisis léxico)")
        print("  --ast         Mostrar el AST (análisis sintáctico)")
        print("  --tabla       Mostrar la tabla de símbolos")
        print("  --ir          Mostrar el código intermedio (TAC) sin optimizar")
        print("  --ir-opt      Mostrar el código intermedio optimizado + resumen de cambios")
        print("  --run-ir      Ejecutar con la MaquinaTAC (backend de código intermedio)")
        print("  --run-ir-opt  Igual, pero con el TAC optimizado (incluye TCO, Etapa 12.8)")
        print("  --target      Mostrar el código objetivo (ISA de juguete, Etapa 12.11)")
        print("  --target-reg  Igual, con asignación de registros (linear-scan, Etapa 12.12)")
        print("  --help        Mostrar esta ayuda")
        return 1

    if '--help' in sys.argv:
        print("InvenioLang 1.0 - Compilador e Intérprete")
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
        print("  --help        Mostrar esta ayuda")
        print("")
        print("Para entrada interactiva, pasar valores después del archivo:")
        print("  python -m inveniolang.cli programa.inv 42 3.14 Hola")
        return 0

    # Detectar flags y extraer ruta
    flags = {f for f in sys.argv if f.startswith('--')}
    solo_check = '--check' in flags
    solo_step = '--step' in flags
    solo_tokens = '--tokens' in flags
    solo_ast = '--ast' in flags
    solo_tabla = '--tabla' in flags
    solo_ir = '--ir' in flags
    solo_ir_opt = '--ir-opt' in flags
    correr_ir = '--run-ir' in flags
    correr_ir_opt = '--run-ir-opt' in flags
    solo_objetivo = '--target' in flags
    solo_objetivo_reg = '--target-reg' in flags

    args_sin_flags = [a for a in sys.argv[1:] if not a.startswith('--')]
    # El valor de --maxpasos no es un archivo ni entrada
    if '--maxpasos' in sys.argv:
        i = sys.argv.index('--maxpasos')
        if i + 1 < len(sys.argv) and sys.argv[i + 1] in args_sin_flags:
            args_sin_flags.remove(sys.argv[i + 1])
    if not args_sin_flags:
        print("Error: No se especificó archivo")
        return 1

    ruta = args_sin_flags[0]
    entrada = args_sin_flags[1:] if len(args_sin_flags) > 1 else []

    # Revisar sin ejecutar: análisis estático completo
    if solo_check:
        return revisar_archivo(ruta)

    # Traza de ejecución (paso a paso con variables y pila)
    if solo_step:
        max_pasos = None
        if '--maxpasos' in flags:
            i = sys.argv.index('--maxpasos')
            if i + 1 < len(sys.argv):
                try:
                    max_pasos = int(sys.argv[i + 1])
                except ValueError:
                    pass
        return trazar_archivo(ruta, max_pasos)

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
            for e in error_manager.obtener_reportes():
                print(e)
        return 0

    if solo_ast:
        from .ast_nodes import Program
        lexer = Lexer(error_manager)
        parser = Parser(lexer, error_manager)
        ast, _ = parser.analizar(codigo, nombre_archivo)
        if ast:
            _imprimir_ast(ast)
        if error_manager.hay_errores():
            for e in error_manager.obtener_reportes():
                print(e)
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


if __name__ == '__main__':
    sys.exit(main())
