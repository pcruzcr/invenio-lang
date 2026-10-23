# security.py — utilidades de seguridad para InvenioLang
#
# Centraliza validaciones que el intérprete y la CLI deben aplicar para
# mitigar riesgos en entorno educativo compartido (aula con 30 estudiantes):
#   - Path traversal y escritura arbitraria vía leer_archivo/escribir_archivo
#   - Límites de ejecución (IL-EJE-030/040) leídos de config.py
# INV-1021: se eliminaron sanitizar_salida, validar_tamano_contenido (builtins
# valida el contenido por su cuenta), auditar_seguridad (re-probaba en tiempo
# de ejecución lo que ya prueban los tests), el parámetro ignorado
# `para_escritura` y cuatro límites copiados que nadie leía.

import os
import re

from .config import DEFAULT_CONFIG

# ————— Límites globales —————
# Se leen de config.py (fuente única, sobreescribible con INVE_*). Antes
# estaban copiados a mano aquí, en cli.py, builtins.py e interpreter.py.
MAX_ARRAY_ELEMENTS = DEFAULT_CONFIG.max_array_elements  # arreglos dinámicos (INV-1440)
MAX_ARCHIVO_BUILTIN = DEFAULT_CONFIG.max_archivo_builtin  # leer/escribir_archivo
MAX_RECURSION = DEFAULT_CONFIG.max_recursion  # frames InvenioLang
MAX_ITERACIONES = DEFAULT_CONFIG.max_iteraciones
MAX_SEGUNDOS = DEFAULT_CONFIG.max_segundos

# ————— Validación de rutas —————
_EXT_PERMITIDAS = {".txt", ".inv", ".csv", ".dat", ".log", ".json", ".tmp"}
_RUTA_MAX_LEN = 260  # MAX_PATH de Windows: rutas de los builtins de archivo


def validar_ruta_relativa(ruta: str) -> str:
    """Valida ruta para builtins de archivo. Lanza ValueError si no cumple."""
    if not isinstance(ruta, str) or not ruta.strip():
        raise ValueError("ruta vacía")
    if any(ord(c) < 0x20 for c in ruta):
        raise ValueError("ruta contiene caracteres de control")
    norm = ruta.replace("\\", "/")
    # UNC antes que "absoluta": "//srv/x" también empieza por "/", así que
    # en el orden anterior este mensaje más preciso era inalcanzable.
    if norm.startswith("//"):
        raise ValueError(f"ruta UNC no permitida: {ruta}")
    if norm.startswith("/") or (len(norm) >= 2 and norm[1] == ":"):
        raise ValueError(f"ruta absoluta no permitida: {ruta}")
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
    if base in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(r"COM[1-9]|LPT[1-9]", base):
        raise ValueError(f"nombre de archivo reservado: {ruta}")
    return ruta
