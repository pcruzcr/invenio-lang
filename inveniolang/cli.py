"""Interfaz de línea de comandos (CLI) de InvenioLang.

Uso: ``python -m inveniolang.cli <archivo.inv> [entrada...] [opciones]``
(o ``python main.py --cli ...``). Ver ``--help``.

La CLI es un adaptador de E/S: lee el archivo, imprime y elige el código de
salida. El orden de fases y el corte ante errores viven en la fachada única
del núcleo (``core.analizar_fuente``/``compile_pure``) y las herramientas
didácticas en ``api`` (INV-1022). Antes había aquí cinco copias del pipeline
``Lexer → Parser → SemanticAnalyzer → TypeChecker`` más una ``CompilerFacade``
paralela; además ``--step`` fallaba con ``AttributeError`` ante cualquier
error de compilación y la ejecución normal no mostraba las advertencias del
verificador de tipos.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from . import api
from . import ir as ir_mod
from ._version import __version__
from .config import DEFAULT_CONFIG
from .core import Analisis, analizar_fuente
from .i18n import IDIOMAS, establecer_idioma, idioma_actual, normalizar_idioma, t
from .interpreter import DebugStopped, Interpreter

# Límites desde la configuración central (config.py), no repetidos aquí.
_MAX_FUENTE_BYTES = DEFAULT_CONFIG.max_fuente_bytes  # evita DoS por archivo gigante
_RUTA_MAX_LEN = DEFAULT_CONFIG.ruta_max_len

# Clave del catálogo i18n con el título de cada fase (INV-1402).
_TITULOS = {
    "lexer": "CLI.errores_lexicos",
    "parser": "CLI.errores_sintacticos",
    "modulos": "CLI.errores_modulos",
    "semantico": "CLI.errores_semanticos",
    "tipos": "CLI.errores_tipos",
}


def _titulo(fase: str | None) -> str:
    return t(_TITULOS[fase or "lexer"])


def _fallo_lectura(mensaje, nombre, error_manager, oficial=True):
    """Registra o imprime un fallo de lectura del fuente (IL-LEX-001)."""
    if error_manager is not None:
        error_manager.set_archivo(nombre)
        error_manager.error_lexico("IL-LEX-001", mensaje, 0, 0)
    elif oficial:
        print(f"[IL-LEX-001] {nombre}:0:0 — {mensaje}")
    else:
        print(t("CLI.error", msg=mensaje))
    return None, 1


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
    nombre = os.path.basename(ruta) if ruta and isinstance(ruta, str) else "<desconocido>"
    if not ruta or not isinstance(ruta, str):
        return _fallo_lectura(t("CLI.ruta_vacia"), nombre, error_manager, False)
    if len(ruta) > _RUTA_MAX_LEN or "\x00" in ruta:
        msg = t("CLI.ruta_larga", n=len(ruta))
        return _fallo_lectura(msg, nombre, error_manager)
    try:
        try:
            tam = os.path.getsize(ruta)
        except OSError:
            tam = 0  # si no se puede stat, dejar que open falle
        if tam > _MAX_FUENTE_BYTES:
            msg = t("CLI.archivo_grande", tam=tam, limite=_MAX_FUENTE_BYTES)
            return _fallo_lectura(msg, nombre, error_manager)
        with open(ruta, encoding="utf-8") as f:
            data = f.read(_MAX_FUENTE_BYTES + 1)
        # El límite es en BYTES: comparar caracteres dejaba pasar hasta
        # 4x el límite con texto multibyte si el stat previo fallaba.
        if len(data) > _MAX_FUENTE_BYTES or len(data.encode("utf-8")) > _MAX_FUENTE_BYTES:
            msg = t("CLI.archivo_excede", limite=_MAX_FUENTE_BYTES)
            return _fallo_lectura(msg, nombre, error_manager)
        return data, None
    except FileNotFoundError:
        return _fallo_lectura(t("CLI.no_encontrado", ruta=ruta), nombre, error_manager, False)
    except UnicodeDecodeError as e:
        return _fallo_lectura(t("CLI.no_utf8", pos=e.start), nombre, error_manager)
    except OSError as e:
        return _fallo_lectura(t("CLI.no_leer", ruta=ruta, e=e), nombre, error_manager)


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


def _imprimir_errores_con_caret(error_manager, codigo: str, titulo: str) -> None:
    """Imprime errores con contexto visual.

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
        if getattr(err, "archivo", None) != error_manager.archivo_base:
            continue  # INV-1420: error de un módulo importado, no de `codigo`
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
        print(f"=== {t('CLI.advertencias')} ===")
        for warn in error_manager.obtener_advertencias():
            print(warn)


def _imprimir_errores_fase(analisis: Analisis) -> None:
    """Título de la fase fallida + un diagnóstico oficial por línea."""
    print(_titulo(analisis.fase_fallida))
    for e in analisis.errores.obtener_reportes():
        print("  " + e)


def ejecutar_archivo(ruta_archivo, entrada_usuario=None):
    """Ejecuta un archivo .inv a través de todo el pipeline del compilador.

    Args:
        ruta_archivo: Ruta al archivo .inv
        entrada_usuario: Lista opcional de strings para entrada estándar

    Retorna:
        Código de salida (0 = éxito, 1 = error)
    """
    codigo, fallo = leer_fuente(ruta_archivo)
    if fallo is not None:
        return fallo
    analisis = analizar_fuente(codigo, os.path.basename(ruta_archivo), ruta_fuente=ruta_archivo)
    em = analisis.errores
    if analisis.fase_fallida in ("lexer", "parser", "modulos", "semantico"):
        _imprimir_errores_con_caret(em, codigo, _titulo(analisis.fase_fallida))
        return 1
    # INV-1022: también se muestran las advertencias del verificador de
    # tipos (antes se imprimían antes de correrlo y nunca aparecían).
    _imprimir_advertencias(em)
    if analisis.fase_fallida == "tipos":
        _imprimir_errores_con_caret(em, codigo, _titulo("tipos"))
        return 1
    interprete = Interpreter(em, analisis.tabla)
    try:
        salida = interprete.interpretar(analisis.ast, entrada_usuario)
    except Exception as e:
        print(t("CLI.error_ejecucion", e=e))
        return 1
    if em.hay_errores():
        _imprimir_errores_con_caret(em, codigo, t("CLI.errores_ejecucion"))
        return 1
    if salida:
        sys.stdout.write("".join(salida))
    return 0


def revisar_archivo(ruta, detalle=True):
    """Análisis estático completo (léxico → tipos) SIN interpretar el programa.

    Es el equivalente CLI del análisis en vivo de la GUI. Retorna 0 si no hay
    errores y 1 si los hay.
    """
    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return fallo
    nombre_archivo = os.path.basename(ruta)
    em = analizar_fuente(codigo, nombre_archivo, ruta_fuente=ruta).errores
    if detalle:
        print(f"=== {t('CLI.analisis_estatico', archivo=nombre_archivo)} ===")
        errores = em.obtener_reportes()
        advertencias = em.obtener_advertencias()
        if errores:
            print(t("CLI.errores_dos_puntos"))
            for e in errores:
                print(f"  {e}")
        if advertencias:
            print(t("CLI.advertencias_dos_puntos"))
            for w in advertencias:
                print(f"  {w}")
        estado = "OK" if not em.errores else "ERROR"
        print(
            t("CLI.resumen_revision", estado=estado, n_err=len(em.errores), n_warn=len(em.warnings))
        )
    return 1 if em.hay_errores() else 0


class _FuentesPaso:
    """Archivo y texto de la línea de cada paso de ``--step`` (INV-4404).

    El intérprete da la línea y la pila de llamadas; el archivo es el de la
    subrutina activa más interna que venga de un módulo importado
    (``archivo_origen``) o, si no, el programa principal.
    """

    def __init__(self, ast, nombre_principal, codigo):
        self.principal = nombre_principal
        self.origen = {}
        for s in getattr(ast, "subrutinas", []) or []:
            self.origen[s.nombre] = getattr(s, "archivo_origen", None)
        for c in getattr(ast, "clases", []) or []:
            for m in list(c.metodos) + list(c.constructores):
                nombre = c.nombre if m in c.constructores else m.nombre
                self.origen[f"{c.nombre}.{nombre}"] = getattr(m, "archivo_origen", None)
        self.rutas = dict(getattr(ast, "rutas_modulos", {}) or {})
        self.lineas = {nombre_principal: codigo.splitlines()}

    def archivo(self, pila):
        """Archivo de la subrutina activa (una lambda hereda el de quien la ejecuta)."""
        for marco in reversed(pila):
            if marco in self.origen:
                return self.origen[marco] or self.principal
        return self.principal

    def linea(self, archivo, n):
        """Texto (sin sangría) de la línea ``n`` de ``archivo``; "" si no se puede leer."""
        if archivo not in self.lineas:
            try:
                with open(self.rutas[archivo], encoding="utf-8") as f:
                    self.lineas[archivo] = f.read().splitlines()
            except (KeyError, OSError, UnicodeDecodeError):
                self.lineas[archivo] = []
        lineas = self.lineas[archivo]
        return lineas[n - 1].strip() if 1 <= n <= len(lineas) else ""


def trazar_archivo(ruta, max_pasos=None):
    """Traza la ejecución: cada instrucción con sus variables y la pila de llamadas.

    Args:
        ruta: Ruta al archivo .inv
        max_pasos: Límite opcional de pasos a registrar

    Retorna:
        Código de salida (0 = sin errores en ejecución, 1 = hubo errores)
    """
    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return fallo
    nombre_archivo = os.path.basename(ruta)
    analisis = analizar_fuente(codigo, nombre_archivo, ruta_fuente=ruta)
    if not analisis.ok:
        _imprimir_errores_fase(analisis)
        return 1
    em = analisis.errores
    interp = Interpreter(em, analisis.tabla)
    interp.debug = True
    traza = []

    def on_statement(snap, pausar=False):
        """Registra el paso; nunca pausa (devuelve False)."""
        traza.append(snap)
        if max_pasos is not None and len(traza) >= max_pasos:
            interp.debug_detener = True
        return False

    interp.debug_on_statement = on_statement
    salida = []
    try:
        salida = interp.interpretar(analisis.ast, usar_stdin=False)
    except DebugStopped:
        pass  # límite de pasos alcanzado

    print(f"=== {t('CLI.traza', archivo=nombre_archivo)} ===")
    fuentes = _FuentesPaso(analisis.ast, nombre_archivo, codigo)
    for i, snap in enumerate(traza, 1):
        varmas = ", ".join(f"{v['nombre']}={v['valor']!r}" for v in snap["variables"])
        pila = "/".join(snap["pila"]) if snap["pila"] else "(main)"
        archivo = fuentes.archivo(snap["pila"])
        # INV-4404: cada paso dice en qué archivo y línea está y muestra el
        # código de esa línea (antes solo "L12", sin archivo ni código).
        print(f"[{i:3}] {archivo}:{snap['linea']:<4} {t('CLI.pila')}={pila:<16} {varmas}")
        linea = fuentes.linea(archivo, snap["linea"])
        if linea:
            print(f"      | {linea}")
    if salida:
        print(f"\n=== {t('CLI.salida')} ===")
        sys.stdout.write("".join(salida))
    n_err = len(em.errores)
    if n_err:
        print(f"\n=== {t('CLI.errores_ejecucion')} ===")
        for e in em.obtener_reportes():
            print("  " + e)
    print("\n" + t("CLI.pasos", pasos=len(traza), errores=n_err))
    return 1 if n_err else 0


def _compilar_estatico(ruta):
    """Análisis estático; retorna (ast, tabla, em) o (None, None, em) con errores ya impresos."""
    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return None, None, None
    analisis = analizar_fuente(codigo, os.path.basename(ruta), ruta_fuente=ruta)
    if not analisis.ok:
        _imprimir_errores_fase(analisis)
        return None, None, analisis.errores
    return analisis.ast, analisis.tabla, analisis.errores


def _generar_ir_o_avisar(ast):
    """Genera el IR, o imprime un aviso y retorna None si el programa usa POO."""
    try:
        return ir_mod.generar_programa(ast)
    except ir_mod.NoSoportadoIR as e:
        print(f"=== {t('CLI.ir_no_disponible')} ===")
        print(f"  {e}")
        return None


def _lista_pasadas(resumen):
    """Resumen "pasada xN, ..." con los nombres de pasada en el idioma actual."""
    return ", ".join(f"{ir_mod.nombre_pasada(n)} x{c}" for n, c in resumen)


def mostrar_ir(ruta, optimizar=False):
    """--ir / --ir-opt: genera y muestra el código de tres direcciones (TAC).

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
        print(ir_mod.formatear(instrucciones) if instrucciones else "  " + t("CLI.vacio"))

    print(f"=== {t('CLI.ir_titulo', archivo=os.path.basename(ruta))} ===")
    _mostrar(t("CLI.variables_globales"), globales)
    for nombre, (parametros, instrucciones) in subrutinas.items():
        firma = f"{nombre}({', '.join(parametros)})"
        _mostrar(firma, instrucciones)

    if optimizar:
        opt_globales, resumen_globales = ir_mod.optimizar(globales)
        opt_subrutinas, resumenes = ir_mod.optimizar_programa(subrutinas)
        print()
        print(f"=== {t('CLI.ir_optimizado')} ===")
        _mostrar(t("CLI.variables_globales"), opt_globales)
        if resumen_globales:
            print("  " + t("CLI.optimizaciones", lista=_lista_pasadas(resumen_globales)))
        for nombre, (parametros, instrucciones) in opt_subrutinas.items():
            firma = f"{nombre}({', '.join(parametros)})"
            _mostrar(firma, instrucciones)
            resumen = resumenes.get(nombre) or []
            if resumen:
                print("  " + t("CLI.optimizaciones", lista=_lista_pasadas(resumen)))

    return 0


def mostrar_objetivo(ruta, k_registros=None):
    """--target (Etapa 12.11): genera y muestra el código objetivo del ISA.

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
        print(f"=== {t('CLI.objetivo_no_disponible')} ===")
        print(f"  {e}")
        return 1

    titulo = t("CLI.objetivo_registros") if k_registros else t("CLI.objetivo_isa")
    print(f"=== {titulo}: {os.path.basename(ruta)} ===")
    if k_registros:
        print("  " + t("CLI.linear_scan", k=k_registros))
    for nombre, (parametros, instrucciones) in objetivo.items():
        firma = f"{nombre}({', '.join(parametros)})"
        print(f"--- {firma} ---")
        print(ir_mod.formatear_objetivo(instrucciones) if instrucciones else "  " + t("CLI.vacio"))
        if nombre in resumen_registros:
            asignacion, spills = resumen_registros[nombre]
            registros = {v: r for v, r in asignacion.items() if r.startswith("R")}
            print(
                "  "
                + t("CLI.asignacion", lista=", ".join(f"{v}->{r}" for v, r in registros.items()))
                if registros
                else "  " + t("CLI.asignacion_vacia")
            )
            if spills:
                print("  " + t("CLI.spill", lista=", ".join(spills)))
    return 0


def ejecutar_con_ir(ruta, entrada_usuario=None, optimizado=False):
    """--run-ir: ejecuta el programa con MaquinaTAC (el motor del código.

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
        print(t("CLI.error_ejecucion_tac", e=e))
        return 1

    if salida:
        sys.stdout.write("".join(salida))
    return 0


_VERSION = __version__

# Herramientas didácticas: flag -> (función de api, argumentos extra desde args).
_HERRAMIENTAS = ("complejidad", "efectos", "ssa", "uml", "ver_como", "formatear")


def build_argparser():
    """Construye el parser de argumentos CLI (ayuda desde el catálogo i18n, INV-1402)."""
    import argparse

    p = argparse.ArgumentParser(
        prog="inveniolang", description=t("CLI.descripcion", version=_VERSION)
    )
    p.add_argument("archivo", nargs="?", help=t("CLI.arg.archivo"))
    p.add_argument("entrada", nargs="*", help=t("CLI.arg.entrada"))
    for opcion in (
        "check",
        "step",
        "tokens",
        "ast",
        "tabla",
        "ir",
        "ir-opt",
        "run-ir",
        "run-ir-opt",
        "target",
        "target-reg",
        "ssa",
        "complejidad",
        "efectos",
        "formatear",
        "json",
        "metrics",
        "sandbox",
        "version",
    ):
        p.add_argument(
            f"--{opcion}", action="store_true", help=t("CLI.arg." + opcion.replace("-", "_"))
        )
    p.add_argument("--maxpasos", type=int, default=None, help=t("CLI.arg.maxpasos"))
    # INV-3213: --uml admite también svg, json y texto (descripción accesible).
    p.add_argument(
        "--uml",
        nargs="?",
        const="plantuml",
        choices=("plantuml", "mermaid", "svg", "json", "texto"),
        help=t("CLI.arg.uml"),
    )
    p.add_argument(
        "--ver-como",
        choices=("python", "c", "cpp", "java", "csharp", "pascal"),
        help=t("CLI.arg.ver_como"),
    )
    p.add_argument("--idioma", choices=IDIOMAS, default=None, help=t("CLI.arg.idioma"))
    return p


def _ejecutar_con_metricas(ruta: str, entrada: list[str]) -> int:
    """Pipeline puro con métricas por fase y alertas de presupuesto (JSON a stdout)."""
    import json as _json
    from dataclasses import asdict

    from .budgets import evaluar_metricas
    from .observability import PipelineMetrics

    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return fallo
    metrics = PipelineMetrics()
    resultado = api.ejecutar(codigo, ruta=ruta, entrada=tuple(entrada or ()), metrics=metrics)
    informe = {
        "archivo": ruta,
        "ok": resultado.ok,
        "salida": list(resultado.salida),
        "errores": list(resultado.errores),
        "run_id": resultado.run_id,
        "metrics": metrics.to_dict(),
        # INV-1026: budgets.py solo lo usaban las pruebas; ahora las alertas
        # de presupuesto acompañan a las métricas que las originan.
        "alertas": [asdict(a) for a in evaluar_metricas(metrics)],
    }
    print(_json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if resultado.ok else 1


def _herramienta(nombre: str, args: Any, codigo: str, ruta: str, ruta_fuente: str) -> int:
    """Ejecuta una herramienta didáctica de la fachada ``api`` e imprime su informe."""
    if nombre == "uml":
        # INV-3213: ruta_fuente para que `importar` resuelva junto al archivo;
        # --idioma, si se dio, fija el idioma de los tipos y del texto.
        r = api.uml(codigo, ruta, formato=args.uml, idioma=args.idioma, ruta_fuente=ruta_fuente)
    elif nombre == "ver_como":
        r = api.ver_como(args.ver_como, codigo, ruta)
    elif nombre in ("complejidad", "efectos"):
        r = getattr(api, nombre)(codigo, ruta, idioma=idioma_actual())
    else:
        r = getattr(api, nombre)(codigo, ruta)
    if not r.ok:
        for e in r.errores:
            print(e)
        return 1
    texto = "".join(r.salida)
    sys.stdout.write(texto if texto.endswith("\n") else texto + "\n")
    return 0


def _check_json(ruta: str) -> int:
    import json

    from .errors import ErrorManager

    em = ErrorManager()
    codigo, _ = leer_fuente(ruta, em)
    if codigo is not None:
        em = analizar_fuente(codigo, ruta).errores  # ruta completa: base de `importar`
    informe = {"archivo": ruta, "errores": em.obtener_reportes_json(), "ok": not em.hay_errores()}
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if not em.hay_errores() else 1


def _mostrar_basico(pargs: Any, ruta: str) -> int:
    """--tokens / --ast / --tabla: vistas de las fases tempranas (siempre retornan 0)."""
    codigo, fallo = leer_fuente(ruta)
    if fallo is not None:
        return fallo
    nombre = os.path.basename(ruta)
    if pargs.tokens:
        analisis = analizar_fuente(codigo, nombre, hasta="lexer")
        for tok in analisis.tokens:
            print(f"{tok[0]:20s} {repr(tok[1]):30s} L{tok[2]}:C{tok[3]}")
    elif pargs.ast:
        analisis = analizar_fuente(codigo, nombre, hasta="modulos", ruta_fuente=ruta)
        if analisis.ast:
            _imprimir_ast(analisis.ast)
    else:
        analisis = analizar_fuente(codigo, nombre, hasta="semantico", ruta_fuente=ruta)
        if analisis.tabla is not None:
            print(f"=== {t('CLI.tabla_simbolos')} ===")
            for _nombre, entrada in analisis.tabla.obtener_simbolos_visibles().items():
                print(f"  {entrada}")
    for rep in analisis.errores.obtener_reportes():
        print(rep)
    return 0


def _main_traducir(argv) -> int:
    """``inveniolang traducir archivo.inv --a en|es [--salida destino.inv]`` (INV-1404).

    Traduce palabras clave y nombres de funciones integradas conservando
    comentarios, literales y formato (ver traductor.py). Sin --salida, la
    traducción se escribe en la salida estándar.
    """
    import argparse

    from . import security
    from .traductor import tokens_con_posicion, traducir

    p = argparse.ArgumentParser(prog="inveniolang traducir", description=t("CLI.trad.descripcion"))
    p.add_argument("archivo", help=t("CLI.trad.arg.archivo"))
    p.add_argument("--a", dest="destino", choices=IDIOMAS, required=True, help=t("CLI.trad.arg.a"))
    p.add_argument("--salida", default=None, help=t("CLI.trad.arg.salida"))
    p.add_argument("--idioma", choices=IDIOMAS, default=None, help=t("CLI.arg.idioma"))
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    codigo, fallo = leer_fuente(args.archivo)
    if fallo is not None:
        return fallo
    _, em = tokens_con_posicion(codigo)
    if em.hay_errores():
        em.set_archivo(os.path.basename(args.archivo))
        _imprimir_errores_con_caret(em, codigo, t("CLI.errores_lexicos"))
        return 1
    traducido = traducir(codigo, args.destino)
    if args.salida is None:
        sys.stdout.write(traducido)
        return 0
    try:
        security.validar_ruta_relativa(args.salida)
        with open(args.salida, "w", encoding="utf-8", newline="") as f:
            f.write(traducido)
    except (ValueError, OSError) as e:
        print(t("CLI.trad.ruta_salida", ruta=args.salida, e=e))
        return 1
    print(t("CLI.trad.escrito", ruta=args.salida))
    return 0


def _escribir_traza(ruta: str, contenido: str, idioma: str) -> bool:
    """Escribe una exportación de la traza; informa del fallo en vez de lanzarlo."""
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
    except OSError as e:
        print(t("CLI.trz.no_escribir", idioma, ruta=ruta, e=e))
        return False
    return True


def _numero_de_paso(par, opcion):
    """Número de paso (1..N) de ``--svg-paso``/``--objetos``; 0 si no es válido, None si falta."""
    if par is None:
        return None
    try:
        n = int(par[0])
    except ValueError:
        n = 0
    if n < 1:
        print(t("CLI.trz.paso_invalido", opcion=opcion, total="?", n=par[0]))
        return 0
    return n


def _main_trazar(argv) -> int:
    """``inveniolang trazar archivo.inv [entrada...]`` con sus exportaciones (INV-2005).

    INV-2005/INV-2009: registra la ejecución paso a paso (``api.trazar``).
    ``--json`` escribe la traza (contrato v1), ``--html`` el reproductor
    autónomo, ``--svg-paso N f`` el dibujo del paso número N (como se numera
    en ``--texto``), ``--objetos N f`` su diagrama de objetos UML (SVG si ``f``
    termina en ``.svg``; si no, texto) y ``--texto`` la descripción accesible de cada paso
    (``render_texto.describir``), que es lo que se hace si no se pide ninguna
    exportación. Código de salida 1 si el programa tiene errores.
    """
    import argparse

    from .visualizacion import describir, html_traza, svg_paso
    from .visualizacion.modelo import a_json
    from .visualizacion.traza import MAX_PASOS_TRAZA

    defecto = 5000
    p = argparse.ArgumentParser(prog="inveniolang trazar", description=t("CLI.trz.descripcion"))
    p.add_argument("archivo", help=t("CLI.trz.arg.archivo"))
    p.add_argument("entrada", nargs="*", help=t("CLI.trz.arg.entrada"))
    p.add_argument("--json", dest="json", default=None, help=t("CLI.trz.arg.json"))
    p.add_argument("--html", dest="html", default=None, help=t("CLI.trz.arg.html"))
    p.add_argument(
        "--svg-paso",
        dest="svg_paso",
        nargs=2,
        metavar=("N", "SVG"),
        default=None,
        help=t("CLI.trz.arg.svg_paso"),
    )
    # INV-4402: el diagrama de objetos (Fase 3, api.diagrama_objetos) solo era
    # accesible desde Python; ahora también desde la línea de órdenes.
    p.add_argument(
        "--objetos",
        "--objects",
        dest="objetos",
        nargs=2,
        metavar=("N", "ARCHIVO"),
        default=None,
        help=t("CLI.trz.arg.objetos"),
    )
    p.add_argument("--texto", action="store_true", help=t("CLI.trz.arg.texto"))
    p.add_argument(
        "--max-pasos",
        type=int,
        default=defecto,
        help=t("CLI.trz.arg.max_pasos", maximo=MAX_PASOS_TRAZA, defecto=defecto),
    )
    p.add_argument("--idioma", choices=IDIOMAS, default=None, help=t("CLI.arg.idioma"))
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    if not 1 <= args.max_pasos <= MAX_PASOS_TRAZA:
        print(t("CLI.trz.max_pasos_invalido", maximo=MAX_PASOS_TRAZA))
        return 2
    n_svg = _numero_de_paso(args.svg_paso, "--svg-paso")
    n_obj = _numero_de_paso(args.objetos, "--objetos")
    if n_svg == 0 or n_obj == 0:
        return 2
    codigo, fallo = leer_fuente(args.archivo)
    if fallo is not None:
        return fallo
    traza = api.trazar(
        codigo,
        os.path.basename(args.archivo),
        entrada=tuple(args.entrada),
        idioma=args.idioma,
        max_pasos=args.max_pasos,
        ruta_fuente=args.archivo,
    )
    idioma = traza.idioma
    pasos = len(traza.pasos)
    if args.json is not None:
        if not _escribir_traza(args.json, a_json(traza), idioma):
            return 1
        print(t("CLI.trz.json_escrito", idioma, ruta=args.json, pasos=pasos))
    if args.html is not None:
        if not _escribir_traza(args.html, html_traza(traza, idioma), idioma):
            return 1
        print(t("CLI.trz.html_escrito", idioma, ruta=args.html, pasos=pasos))
    if n_svg is not None:
        if n_svg > pasos:
            print(t("CLI.trz.paso_invalido", idioma, opcion="--svg-paso", total=pasos, n=n_svg))
            return 2
        svg = svg_paso(traza.pasos[n_svg - 1].a_dict(), idioma)
        if not _escribir_traza(args.svg_paso[1], svg, idioma):
            return 1
        print(t("CLI.trz.svg_escrito", idioma, ruta=args.svg_paso[1], n=n_svg))
    if n_obj is not None:
        if n_obj > pasos:
            print(t("CLI.trz.paso_invalido", idioma, opcion="--objetos", total=pasos, n=n_obj))
            return 2
        destino = args.objetos[1]
        # .svg → dibujo; cualquier otra extensión → descripción textual accesible.
        formato = "svg" if destino.lower().endswith(".svg") else "texto"
        diagrama = api.diagrama_objetos(traza, n_obj - 1, formato=formato, idioma=idioma)
        if not _escribir_traza(destino, diagrama, idioma):
            return 1
        print(t("CLI.trz.objetos_escrito", idioma, ruta=destino, n=n_obj))
    exporta = any(x is not None for x in (args.json, args.html, n_svg, n_obj))
    if args.texto or not exporta:
        nombre = os.path.basename(args.archivo)
        print(t("TRZ.titulo", idioma, archivo=nombre, pasos=pasos))
        for paso in traza.pasos:
            print(describir(paso.a_dict(), idioma))
        if traza.salida:
            print(f"\n{t('TRZ.salida_total', idioma)}")
            texto = "".join(traza.salida)
            sys.stdout.write(texto if texto.endswith("\n") else texto + "\n")
    if traza.truncada:
        print(t("TRZ.truncada", idioma, pasos=pasos))
    if traza.error:
        print(t("TRZ.error", idioma))
        print(traza.error)
        return 1
    return 0


# ---------------------------------------------------------------------------
# Diagramas de flujo (equipo FLUJO, INV-3009)
# ---------------------------------------------------------------------------


def _escribir_salida(ruta: str, contenido: str) -> bool:
    """Escribe una exportación del diagrama; informa del fallo en vez de lanzarlo."""
    try:
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(contenido)
    except OSError as e:
        print(t("CLI.flu.no_escribir", ruta=ruta, e=e))
        return False
    return True


def _main_flujo(argv) -> int:
    """``inveniolang flujo archivo.inv [--subrutina N] [--svg f|--mermaid f|--json f|--texto]``.

    INV-3009: diagrama de flujo de un programa (``api.diagrama_flujo``). Sin
    exportación se imprime la descripción accesible (``--texto``). Código 1
    si el programa no compila o la subrutina no existe.
    """
    import argparse

    from .flujo import ErrorFlujo, exportar, modelo_desde_codigo

    p = argparse.ArgumentParser(prog="inveniolang flujo", description=t("CLI.flu.descripcion"))
    p.add_argument("archivo", help=t("CLI.flu.arg.archivo"))
    p.add_argument("--subrutina", default=None, help=t("CLI.flu.arg.subrutina"))
    p.add_argument("--svg", default=None, help=t("CLI.flu.arg.svg"))
    p.add_argument("--mermaid", default=None, help=t("CLI.flu.arg.mermaid"))
    p.add_argument("--json", default=None, help=t("CLI.flu.arg.json"))
    p.add_argument("--texto", action="store_true", help=t("CLI.flu.arg.texto"))
    p.add_argument(
        "--tema", choices=("claro", "oscuro", "auto"), default="claro", help=t("CLI.flu.arg.tema")
    )
    p.add_argument("--idioma", choices=IDIOMAS, default=None, help=t("CLI.arg.idioma"))
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    codigo, fallo = leer_fuente(args.archivo)
    if fallo is not None:
        return fallo
    try:
        modelo = modelo_desde_codigo(
            codigo, args.idioma, ruta=os.path.basename(args.archivo), ruta_fuente=args.archivo
        )
        salidas = [
            (destino, exportar(modelo, formato, args.subrutina, tema=args.tema))
            for formato, destino in (
                ("svg", args.svg),
                ("mermaid", args.mermaid),
                ("json", args.json),
            )
            if destino is not None
        ]
        texto = exportar(modelo, "texto", args.subrutina) if args.texto or not salidas else None
    except ErrorFlujo as e:
        print(e.texto())
        for diagnostico in e.diagnosticos:
            print(diagnostico)
        return 1
    for destino, contenido in salidas:
        if not _escribir_salida(destino, contenido):
            return 1
        print(t("CLI.flu.escrito", ruta=destino))
    if texto is not None:
        sys.stdout.write(texto)
    return 0


def _main_desde_flujo(argv) -> int:
    """``inveniolang desde-flujo diagrama.json [--idioma es|en] [-o archivo.inv]``.

    INV-3009: genera el programa de un diagrama (``api.codigo_desde_flujo``)
    y lo compila; si el diagrama tiene problemas los lista con el nodo que
    los causa y termina con código 1 sin escribir nada.
    """
    import argparse

    from .flujo import ErrorFlujo, codigo_desde_modelo, desde_json, validar

    p = argparse.ArgumentParser(
        prog="inveniolang desde-flujo", description=t("CLI.dflu.descripcion")
    )
    p.add_argument("diagrama", help=t("CLI.dflu.arg.diagrama"))
    p.add_argument("-o", "--salida", default=None, help=t("CLI.dflu.arg.salida"))
    p.add_argument("--idioma", choices=IDIOMAS, default=None, help=t("CLI.dflu.arg.idioma"))
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    try:
        with open(args.diagrama, encoding="utf-8") as f:
            modelo = desde_json(f.read())
    except OSError as e:
        print(t("CLI.flu.no_leer", ruta=args.diagrama, e=e))
        return 1
    except ErrorFlujo as e:
        print(e.texto())
        return 1
    problemas = validar(modelo)
    if problemas:
        print(t("CLI.dflu.problemas", n=len(problemas)))
        for pr in problemas:
            print(
                t(
                    "CLI.dflu.problema",
                    diagrama=pr.clave or "-",
                    nodo=pr.nodo or "-",
                    texto=pr.texto(args.idioma),
                )
            )
        return 1
    codigo = codigo_desde_modelo(modelo, args.idioma)
    if args.salida is None:
        sys.stdout.write(codigo)
        return 0
    if not _escribir_salida(args.salida, codigo):
        return 1
    print(t("CLI.flu.escrito", ruta=args.salida))
    return 0


# ---------------------------------------------------------------------------
# Programación por bloques (equipo BLOQUES, INV-4010)
# ---------------------------------------------------------------------------


def _main_bloques(argv) -> int:
    """``inveniolang bloques archivo.inv [--json f] [--texto] [--catalogo f] [--idioma es|en]``.

    INV-4010: bloques de un programa (``api.bloques``). Sin ``--json`` ni
    ``--catalogo`` se imprime la descripción accesible de los bloques.
    Código 1 si el programa no compila.
    """
    import argparse
    import json

    from . import bloques as B  # noqa: N812 - alias corto del paquete
    from .flujo import ErrorFlujo

    p = argparse.ArgumentParser(prog="inveniolang bloques", description=t("CLI.blq.descripcion"))
    p.add_argument("archivo", help=t("CLI.blq.arg.archivo"))
    p.add_argument("--json", default=None, help=t("CLI.blq.arg.json"))
    p.add_argument("--texto", action="store_true", help=t("CLI.flu.arg.texto"))
    p.add_argument("--catalogo", default=None, help=t("CLI.blq.arg.catalogo"))
    p.add_argument("--idioma", choices=IDIOMAS, default=None, help=t("CLI.blq.arg.idioma"))
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    codigo, fallo = leer_fuente(args.archivo)
    if fallo is not None:
        return fallo
    try:
        modelo = B.bloques_desde_codigo(
            codigo, args.idioma, ruta=os.path.basename(args.archivo), ruta_fuente=args.archivo
        )
    except ErrorFlujo as e:
        print(t("CLI.blq.no_compila", args.idioma))
        for diagnostico in e.diagnosticos:
            print(diagnostico)
        return 1
    if args.json is not None:
        if not _escribir_bloques(args.json, B.a_json(modelo), args.idioma):
            return 1
        print(t("CLI.blq.escrito", args.idioma, ruta=args.json))
    if args.catalogo is not None:
        catalogo = json.dumps(B.catalogo_dict(modelo.idioma), ensure_ascii=False, indent=2)
        if not _escribir_bloques(args.catalogo, catalogo, args.idioma):
            return 1
        print(t("CLI.blq.catalogo_escrito", args.idioma, ruta=args.catalogo))
    if args.texto or (args.json is None and args.catalogo is None):
        sys.stdout.write(B.describir(modelo, args.idioma or modelo.idioma))
    return 0


def _escribir_bloques(ruta: str, contenido: str, idioma) -> bool:
    try:
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(contenido)
    except OSError as e:
        print(t("CLI.blq.no_escribir", idioma, ruta=ruta, e=e))
        return False
    return True


def _main_desde_bloques(argv) -> int:
    """``inveniolang desde-bloques bloques.json [--idioma es|en] [-o archivo.inv]``.

    INV-4010: genera el programa de un archivo de bloques
    (``api.codigo_desde_bloques``) tras validarlo con ``bloques.validar``
    (estructura, tipos y compilación); si hay problemas los lista con el
    bloque culpable y termina con código 1 sin escribir nada.
    """
    import argparse

    from . import bloques as B  # noqa: N812 - alias corto del paquete

    p = argparse.ArgumentParser(
        prog="inveniolang desde-bloques", description=t("CLI.dblq.descripcion")
    )
    p.add_argument("archivo", help=t("CLI.dblq.arg.archivo"))
    p.add_argument("-o", "--salida", default=None, help=t("CLI.dblq.arg.salida"))
    p.add_argument("--idioma", choices=IDIOMAS, default=None, help=t("CLI.dblq.arg.idioma"))
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    try:
        with open(args.archivo, encoding="utf-8") as f:
            modelo = B.desde_json(f.read())
    except OSError as e:
        print(t("CLI.blq.ilegible", args.idioma, ruta=args.archivo, e=e))
        return 1
    except B.ErrorBloques as e:
        print(e.texto(args.idioma))
        return 1
    problemas = B.validar(modelo)
    if problemas:
        print(t("CLI.dblq.invalido", args.idioma))
        for pr in problemas:
            print(f"[{pr.bloque or '-'}] {pr.texto(args.idioma)}")
        return 1
    codigo = B.codigo_desde_bloques(modelo, args.idioma)
    if args.salida is None:
        sys.stdout.write(codigo)
        return 0
    if not _escribir_bloques(args.salida, codigo, args.idioma):
        return 1
    print(t("CLI.dblq.escrito", args.idioma, ruta=args.salida))
    return 0


# ================================================================ UML (Fase 3)


def _main_desde_uml(argv) -> int:
    """``inveniolang desde-uml diagrama.(json|puml) [--idioma es|en] [-o f.inv]`` (INV-3213).

    Genera un esqueleto InvenioLang que compila a partir de un diagrama de
    clases (``api.codigo_desde_uml``). Sin ``-o``, el código se imprime.
    Código de salida 1 si el diagrama no se puede leer o expresar.
    """
    import argparse

    p = argparse.ArgumentParser(prog="inveniolang desde-uml", description=t("CLI.uml.descripcion"))
    p.add_argument("archivo", help=t("CLI.uml.arg.archivo"))
    p.add_argument("--idioma", choices=IDIOMAS, default=None, help=t("CLI.uml.arg.idioma"))
    p.add_argument("-o", "--salida", dest="salida", default=None, help=t("CLI.uml.arg.salida"))
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    try:
        with open(args.archivo, encoding="utf-8") as f:
            fuente = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(t("CLI.uml.ilegible", ruta=args.archivo))
        print(e)
        return 1
    r = api.codigo_desde_uml(fuente, args.idioma)
    if not r.salida:
        print(t("CLI.uml.no_generable", args.idioma))
        for error in r.errores:
            print(f"  - {error}")
        return 1
    if not r.ok:  # generó código pero no compila: es un defecto del generador
        for error in r.errores:
            print(error)
        return 1
    if args.salida is None:
        sys.stdout.write(r.salida[0])
        return 0
    try:
        with open(args.salida, "w", encoding="utf-8") as f:
            f.write(r.salida[0])
    except OSError as e:
        print(t("CLI.uml.no_escribir", args.idioma, ruta=args.salida, e=e))
        return 1
    print(t("CLI.uml.escrito", args.idioma, ruta=args.salida))
    return 0


def _fijar_idioma_desde_argv(argv) -> None:
    """INV-1402: aplica ``--idioma X`` / ``--idioma=X`` antes de imprimir nada.

    Se lee a mano (y no solo con argparse) porque --help y --version se
    atienden antes de argparse y también deben salir en el idioma pedido. Un
    valor inválido se ignora aquí: argparse lo rechazará con su mensaje.
    """
    for i, arg in enumerate(argv):
        valor = None
        if arg == "--idioma" and i + 1 < len(argv):
            valor = argv[i + 1]
        elif arg.startswith("--idioma="):
            valor = arg.split("=", 1)[1]
        if valor is not None:
            try:
                establecer_idioma(normalizar_idioma(valor))
            except ValueError:
                pass


def _forzar_utf8() -> None:
    """Salida en UTF-8 aunque se redirija a un archivo o tubería (INV-5002).

    En Windows, ``python -m inveniolang.cli`` redirigido escribía en cp1252:
    quien leía la salida como UTF-8 (pruebas, el LSP, scripts) recibía bytes
    inválidos en cada tilde. ``main.py`` ya lo hacía; ahora también la CLI.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass  # flujo reemplazado (p. ej. capturado por pytest)


def main():
    """Punto de entrada de la CLI."""
    _forzar_utf8()
    _fijar_idioma_desde_argv(sys.argv[1:])
    if len(sys.argv) >= 2 and sys.argv[1] in ("traducir", "translate"):
        return _main_traducir(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] in ("trazar", "trace"):
        return _main_trazar(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] in ("flujo", "flowchart"):
        return _main_flujo(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] in ("desde-flujo", "from-flowchart"):
        return _main_desde_flujo(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] in ("desde-uml", "from-uml"):
        return _main_desde_uml(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] in ("bloques", "blocks"):
        return _main_bloques(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] in ("desde-bloques", "from-blocks"):
        return _main_desde_bloques(sys.argv[2:])
    if len(sys.argv) < 2:
        build_argparser().print_help()
        return 1
    if "--version" in sys.argv:
        print(f"InvenioLang {_VERSION}")
        return 0
    if "--help" in sys.argv or "-h" in sys.argv:
        print(t("CLI.ayuda", version=_VERSION))
        return 0
    try:
        pargs = build_argparser().parse_args()
    except SystemExit as e:
        return e.code
    if not pargs.archivo:
        print(t("CLI.sin_archivo"))
        build_argparser().print_help()
        return 1
    ruta = pargs.archivo
    entrada = pargs.entrada or []

    if pargs.metrics:
        return _ejecutar_con_metricas(ruta, entrada)
    if pargs.sandbox:
        from .sandbox import run_sandboxed

        # INV-1022: antes la entrada simulada no llegaba al sandbox.
        r = run_sandboxed(ruta, timeout=5, entrada=entrada or None)
        if r.get("stdout"):
            print(r["stdout"], end="" if r["stdout"].endswith("\n") else "\n")
        if not r.get("ok") and r.get("stderr"):
            print(r["stderr"])
        return 0 if r.get("ok") else 1
    if pargs.check:
        return _check_json(ruta) if pargs.json else revisar_archivo(ruta)
    if pargs.step:
        return trazar_archivo(ruta, pargs.maxpasos)
    if pargs.ir or pargs.ir_opt:
        return mostrar_ir(ruta, optimizar=pargs.ir_opt)
    if pargs.target or pargs.target_reg:
        return mostrar_objetivo(ruta, k_registros=4 if pargs.target_reg else None)
    if pargs.run_ir or pargs.run_ir_opt:
        return ejecutar_con_ir(ruta, entrada or None, optimizado=pargs.run_ir_opt)
    herramienta = next((h for h in _HERRAMIENTAS if getattr(pargs, h)), None)
    if herramienta:
        codigo, fallo = leer_fuente(ruta)
        if fallo is not None:
            return fallo
        return _herramienta(herramienta, pargs, codigo, os.path.basename(ruta), ruta)
    if pargs.tokens or pargs.ast or pargs.tabla:
        return _mostrar_basico(pargs, ruta)
    return ejecutar_archivo(ruta, entrada or None)


if __name__ == "__main__":
    sys.exit(main())
