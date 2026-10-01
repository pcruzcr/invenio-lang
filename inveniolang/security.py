# security.py — utilidades de seguridad para InvenioLang
#
# Centraliza validaciones que el intérprete y la CLI deben aplicar para
# mitigar riesgos en entorno educativo compartido (aula con 30 estudiantes):
#   - Path traversal y escritura arbitraria vía leer_archivo/escribir_archivo
#   - DoS por archivos / arreglos gigantes
#   - Límites de ejecución ya existentes (IL-EJE-030/040) — documentados aquí
#   - Sanitización de salida / inyección (aunque InvenioLang no evalúa código)

import os
import re

# ————— Límites globales (profesionales, documentados) —————
MAX_FUENTE_BYTES = 1 * 1024 * 1024  # .inv fuente
MAX_ARCHIVO_BUILTIN = 2 * 1024 * 1024  # leer/escribir_archivo
MAX_ARRAY_ELEMENTS = 100_000  # por arreglo
MAX_MATRIX_CELLS = 200_000  # filas*cols
MAX_MATRIX_DIM = 10_000
MAX_RECURSION = 500  # frames InvenioLang
MAX_ITERACIONES = 1_000_000
MAX_SEGUNDOS = 5.0
MAX_STRING_LEN = 100_000  # literales y conversión

# ————— Validación de rutas —————
_EXT_PERMITIDAS = {".txt", ".inv", ".csv", ".dat", ".log", ".json", ".tmp"}
_RUTA_MAX_LEN = 260


def validar_ruta_relativa(ruta: str, *, para_escritura=False) -> str:
    """Valida ruta para builtins de archivo. Lanza ValueError si no cumple."""
    if not isinstance(ruta, str) or not ruta.strip():
        raise ValueError("ruta vacía")
    if any(ord(c) < 0x20 for c in ruta):
        raise ValueError("ruta contiene caracteres de control")
    norm = ruta.replace("\\", "/")
    if norm.startswith("/") or (len(norm) >= 2 and norm[1] == ":"):
        raise ValueError(f"ruta absoluta no permitida: {ruta}")
    if norm.startswith("//"):
        raise ValueError(f"ruta UNC no permitida: {ruta}")
    if ":" in norm:
        raise ValueError(f"':' no permitido (NTFS ADS): {ruta}")
    if ".." in norm.split("/"):
        raise ValueError(f"traversal '..' no permitido: {ruta}")
    if len(ruta) > _RUTA_MAX_LEN:
        raise ValueError(f"ruta demasiado larga ({len(ruta)})")
    if ruta.rstrip() != ruta or ruta.rstrip(".") != ruta:
        raise ValueError("puntos/espacios finales no permitidos")
    if any(c in ruta for c in '*?<>|"'):
        raise ValueError("wildcards/inyección de ruta no permitidos")
    _, ext = os.path.splitext(norm)
    if ext.lower() not in _EXT_PERMITIDAS:
        raise ValueError(
            f"extensión '{ext}' no permitida (permitidas: {', '.join(sorted(_EXT_PERMITIDAS))})"
        )
    # Evitar dispositivos reservados de Windows
    base = os.path.basename(norm).upper().split(".")[0]
    if base in {"CON", "PRN", "AUX", "NUL"} or re.match(r"COM[1-9]|LPT[1-9]", base):
        raise ValueError(f"nombre de archivo reservado: {ruta}")
    return ruta


def validar_tamano_contenido(texto: str, limite=MAX_ARCHIVO_BUILTIN):
    """Valida tamano contenido."""
    if not isinstance(texto, str):
        raise ValueError("contenido debe ser texto")
    if len(texto.encode("utf-8")) > limite:
        raise ValueError(f"contenido excede {limite} bytes")
    if len(texto) > MAX_STRING_LEN:
        raise ValueError(f"texto excede {MAX_STRING_LEN} caracteres")


def sanitizar_salida(texto: str, max_len=10000) -> str:
    """Trunca salida para la GUI / CLI sin perder diagnóstico."""
    if len(texto) > max_len:
        return texto[:max_len] + f"\n... [truncado, {len(texto) - max_len} chars más]"
    return texto


# ————— Auditoría rápida —————
def auditar_seguridad() -> list:
    """Retorna lista de (severidad, mensaje) para el panel de auditoría."""
    hallazgos = []
    # Comprobar que builtins valida
    try:
        validar_ruta_relativa("../../etc/passwd")
        hallazgos.append(("ALTA", "validar_ruta_relativa no bloquea traversal"))
    except ValueError:
        pass
    try:
        validar_ruta_relativa("C:/Windows/system32/cmd.exe")
        hallazgos.append(("ALTA", "validar_ruta_relativa no bloquea ruta absoluta"))
    except ValueError:
        pass
    try:
        validar_ruta_relativa("malware.exe")
        hallazgos.append(("MEDIA", "validar_ruta_relativa no bloquea extensión .exe"))
    except ValueError:
        pass
    if not hallazgos:
        hallazgos.append(("OK", "Controles de seguridad de rutas: OK"))
    return hallazgos
