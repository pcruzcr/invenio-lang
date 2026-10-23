# Funciones Integradas de InvenioLang 1.0 (Sección 19)
# Implementa las 8 funciones de conversión entre tipos, más la librería
# estándar de cadenas y matemática de la Etapa 6 (lenguaje estructurado
# completo, ver docs/InvenioLang_Etapa6_Estructurado.md).
# Patrones aplicados: Strategy (cada conversión es estrategia intercambiable),
# Factory (registro centralizado), Decorator (validación/seguridad), Template
# Method (flujo parseo → validación → conversión)
from __future__ import annotations

import math
import os
import random
import re
from collections.abc import Callable

from . import security
from .i18n import M
from .patterns import RegistryFactory

# Rango del tipo int / entero: 32 bits con signo (§4.2.1)
INT_MIN = -2147483648
INT_MAX = 2147483647

# Formatos admitidos por las funciones de parseo (§19.7, §19.8)
_RE_ENTERO = re.compile(r"^[+-]?\d+$")
_RE_REAL = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


class BuiltInError(Exception):
    """Fallo de una función integrada, con su código del catálogo (§15.6).

    El intérprete la traduce a un error de ejecución con línea y columna en
    lugar de dejar escapar una excepción del lenguaje de implementación.
    """

    def __init__(self, codigo, mensaje):
        self.codigo = codigo
        self.mensaje = mensaje
        super().__init__(mensaje)


def int_a_float(val):
    """Convierte int a float. Siempre exitoso (§19.3)."""
    return float(val)


def float_a_int(val):
    """Convierte float a int truncando hacia cero (§19.4).

    IL-EJE-003 si el valor truncado excede el rango de int.
    """
    if val != val or val in (float("inf"), float("-inf")):
        raise BuiltInError("IL-EJE-003", M("IL-EJE-003.float_to_int_recibio"))
    truncado = int(val)  # int() trunca hacia cero
    if truncado < INT_MIN or truncado > INT_MAX:
        raise BuiltInError(
            "IL-EJE-003",
            M("IL-EJE-003.float_to_int_excede", val=val, INT_MIN=INT_MIN, INT_MAX=INT_MAX),
        )
    return truncado


def int_a_texto(val):
    """Convierte int a string en base decimal (§19.5)."""
    return str(val)


def float_a_texto(val):
    """Convierte float a string (§19.6).

    Garantía mínima de la especificación: el resultado siempre lleva punto
    decimal y al menos un dígito a cada lado.
    """
    s = repr(float(val))
    if "e" in s or "E" in s:
        # Notación científica: asegurar mantisa con punto ("1e+15" -> "1.0e+15")
        mantisa, _, exp = s.partition("e")
        if "." not in mantisa:
            mantisa += ".0"
        return f"{mantisa}e{exp}"
    if "." not in s:
        s += ".0"
    return s


def texto_a_int(val):
    """Convierte string a int decimal (§19.7).

    Acepta signo opcional y dígitos decimales, ignorando espacios en los
    extremos. IL-EJE-004 en cualquier otro caso o si excede el rango de int.
    """
    s = val.strip()
    if not _RE_ENTERO.match(s):
        raise BuiltInError("IL-EJE-004", M("IL-EJE-004.string_to_int_no", val=val))
    n = int(s)
    if n < INT_MIN or n > INT_MAX:
        raise BuiltInError(
            "IL-EJE-004",
            M("IL-EJE-004.string_to_int_excede", n=n, INT_MIN=INT_MIN, INT_MAX=INT_MAX),
        )
    return n


def texto_a_float(val):
    """Convierte string a float (§19.8).

    Acepta signo, parte decimal opcional y exponente opcional. IL-EJE-005 en
    cualquier otro caso.
    """
    s = val.strip()
    if not _RE_REAL.match(s):
        raise BuiltInError("IL-EJE-005", M("IL-EJE-005.string_to_float_no", val=val))
    return float(s)


def bool_a_texto(val):
    """Convierte bool a string: siempre 'true' o 'false' (§19.9)."""
    return "true" if val else "false"


def texto_a_bool(val):
    """Convierte string a bool (§19.10).

    Sólo son válidas las cuatro formas "true", "false", "verdadero" y "falso",
    insensibles a mayúsculas. Cualquier otra cadena produce IL-EJE-022.
    """
    v = val.strip().lower()
    if v in ("true", "verdadero"):
        return True
    if v in ("false", "falso"):
        return False
    raise BuiltInError("IL-EJE-022", M("IL-EJE-022.string_to_bool_no", val=val))


# ============================================================
# Librería estándar (Etapa 6: lenguaje estructurado completo)
# ============================================================


def longitud(s):
    """Cantidad de caracteres de una cadena."""
    return len(s)


def subcadena(s, inicio, fin):
    """Subcadena [inicio, fin) de s. IL-EST-010 si el rango es inválido."""
    if inicio < 0 or fin > len(s) or inicio > fin:
        raise BuiltInError(
            "IL-EST-010",
            M("IL-EST-010.subcadena_rango_invalido_cadena", inicio=inicio, fin=fin, len_s=len(s)),
        )
    return s[inicio:fin]


def mayusculas(s):
    """Convierte a mayúsculas."""
    return s.upper()


def minusculas(s):
    """Convierte a minúsculas."""
    return s.lower()


def caracter_en(s, i):
    """Carácter (como cadena de 1) en la posición i. IL-EST-011 si i está.

    fuera de rango.
    """
    if i < 0 or i >= len(s):
        raise BuiltInError(
            "IL-EST-011",
            M("IL-EST-011.caracter_indice_fuera_rango", i=i, len_s=len(s)),
        )
    return s[i]


def indice_de(s, sub):
    """Posición de la primera aparición de sub en s, o -1 si no aparece.

    (mismo convenio que arreglos.inv::buscar).
    """
    return s.find(sub)


def recortar(s):
    """Quita espacios en blanco al inicio y al final."""
    return s.strip()


def invertir_texto(s):
    """Cadena invertida (Etapa 10) -- ejercicio clásico de Fundamentos.

    (verificar palíndromos) sin tener que armar el bucle manual cada vez.
    """
    return s[::-1]


def raiz(x):
    """Raíz cuadrada. IL-EST-012 si x es negativo."""
    if x < 0:
        raise BuiltInError("IL-EST-012", M("IL-EST-012.raiz_no_esta_definida", x=x))
    return math.sqrt(x)


def potencia(base, exponente):
    """Base elevado a exponente. IL-EST-013 si el resultado no es un.

    número real (p. ej. raíz de un negativo con exponente fraccionario).
    """
    try:
        resultado = base**exponente
    except (ValueError, OverflowError) as e:
        raise BuiltInError("IL-EST-013", M("IL-EST-013.potencia", e=e)) from e
    if isinstance(resultado, complex):
        raise BuiltInError(
            "IL-EST-013", M("IL-EST-013.potencia_no_produce_numero", base=base, exponente=exponente)
        )
    return float(resultado)


def absoluto(x):
    """Calcula el valor absoluto."""
    return abs(x)


def piso(x):
    """Redondea hacia abajo al entero más cercano."""
    return math.floor(x)


def techo(x):
    """Redondea hacia arriba al entero más cercano."""
    return math.ceil(x)


def azar(minimo_, maximo_):
    """Entero aleatorio uniforme en [minimo_, maximo_]. IL-EST-014 si el.

    rango es inválido.
    """
    if minimo_ > maximo_:
        raise BuiltInError(
            "IL-EST-014",
            M("IL-EST-014.azar_minimo_no_puede", minimo_=minimo_, maximo_=maximo_),
        )
    return random.randint(minimo_, maximo_)  # noqa: S311 - azar didáctico, no criptografía


# ============================================================
# Entrada/salida de archivos (Etapa 10) — con hardening de seguridad
# ============================================================
#
# Alcance deliberadamente simple: texto plano completo por llamada (sin
# lectura línea a línea ni un tipo "manejador de archivo" nuevo) -- cubre
# el caso real de un ejercicio de Fundamentos/Programación 2 (guardar un
# resultado, leer datos de entrada desde un archivo) sin ampliar el sistema
# de tipos. Codificación siempre UTF-8, igual que el resto del lenguaje.
#
# Hardening (mejora profesional / seguridad):
#   - Solo se permiten rutas relativas simples, sin traversal (".."),
#     sin separadores absolutos y sin caracteres de control.
#   - Extensiones permitidas: .txt, .inv, .csv, .dat, .log (evita sobrescribir
#     .py, .exe, .dll, etc.).
#   - Límite de tamaño: lectura max 2 MiB, escritura max 2 MiB.
#   - Esto mitiga path traversal y DoS por archivos gigantes en entorno
#     educativo compartido, sin romper los casos de uso reales.

_RUTAS_PERMITIDAS_EXT = security._EXT_PERMITIDAS
_MAX_ARCHIVO_BYTES = security.MAX_ARCHIVO_BUILTIN
_MAX_CONTENIDO_ESCRITURA = security.MAX_ARCHIVO_BUILTIN


def _validar_ruta(ruta: str):
    """Valida ruta para operaciones de archivo. Lanza BuiltInError si no cumple."""
    if not isinstance(ruta, str) or not ruta.strip():
        raise BuiltInError("IL-EST-015", M("IL-EST-015.leer_archivo_ruta_vacia"))
    if "\x00" in ruta or "\n" in ruta or "\r" in ruta:
        raise BuiltInError(
            "IL-EST-015", M("IL-EST-015.ruta_contiene_caracteres_control", ruta=ruta)
        )
    # Normalizar separadores
    ruta_n = ruta.replace("\\", "/")
    if ruta_n.startswith("/") or (len(ruta_n) >= 2 and ruta_n[1] == ":"):
        raise BuiltInError("IL-EST-015", M("IL-EST-015.ruta_absoluta_no_permitida", ruta=ruta))
    partes = ruta_n.split("/")
    if ".." in partes:
        raise BuiltInError("IL-EST-015", M("IL-EST-015.traversal_no_permitido_ruta", ruta=ruta))
    # Extensión
    _, ext = os.path.splitext(ruta_n)
    if ext.lower() not in _RUTAS_PERMITIDAS_EXT:
        raise BuiltInError(
            "IL-EST-015",
            M(
                "IL-EST-015.extension_no_permitida_permitidas",
                ext=ext,
                ruta=ruta,
                valor=", ".join(sorted(_RUTAS_PERMITIDAS_EXT)),
            ),
        )
    # Longitud
    if len(ruta) > security._RUTA_MAX_LEN:
        raise BuiltInError(
            "IL-EST-015", M("IL-EST-015.ruta_demasiado_larga_chars", len_ruta=len(ruta))
        )
    # Resto de controles de security.validar_ruta_relativa, que antes solo
    # se usaba en el panel de auditoría y NO en ejecución: flujos alternos
    # NTFS ("datos:oculto.txt"), nombres reservados de Windows ("CON.txt",
    # "NUL.log"), comodines, caracteres de control y puntos/espacios finales.
    try:
        security.validar_ruta_relativa(ruta)
    except ValueError as e:
        raise BuiltInError("IL-EST-015", M("IL-EST-015.ruta_no_permitida", ruta=ruta, e=e)) from e
    return ruta


def _validar_contenido(contenido: str, limite=_MAX_CONTENIDO_ESCRITURA):
    if not isinstance(contenido, str):
        raise BuiltInError("IL-EST-016", M("IL-EST-016.contenido_debe_ser_texto"))
    if len(contenido.encode("utf-8")) > limite:
        raise BuiltInError(
            "IL-EST-016", M("IL-EST-016.contenido_excede_limite_bytes", limite=limite)
        )


def existe_archivo(ruta):
    """True si `ruta` existe y es un archivo regular (no directorio).

    Nunca falla -- una ruta inexistente es simplemente False, no un error.
    """
    try:
        ruta_v = _validar_ruta(ruta)
    except BuiltInError:
        return False
    return os.path.isfile(ruta_v)


def leer_archivo(ruta):
    """Contenido completo de `ruta` como texto. IL-EST-015 si no existe, no.

    se puede leer (permisos) o no es UTF-8 válido. Máx 2 MiB.
    """
    ruta_v = _validar_ruta(ruta)
    try:
        # Comprobar tamaño antes de leer completo
        try:
            tam = os.path.getsize(ruta_v)
            if tam > _MAX_ARCHIVO_BYTES:
                raise BuiltInError(
                    "IL-EST-015",
                    M(
                        "IL-EST-015.leer_archivo_excede_limite",
                        ruta=ruta,
                        MAX_ARCHIVO_BYTES=_MAX_ARCHIVO_BYTES,
                        tam=tam,
                    ),
                )
        except OSError:
            pass  # si no se puede stat, dejar que open falle con su mensaje
        with open(ruta_v, encoding="utf-8") as f:
            data = f.read(_MAX_ARCHIVO_BYTES + 1)
            if len(data.encode("utf-8")) > _MAX_ARCHIVO_BYTES:
                raise BuiltInError(
                    "IL-EST-015",
                    M(
                        "IL-EST-015.leer_archivo_excede_limite_2",
                        ruta=ruta,
                        MAX_ARCHIVO_BYTES=_MAX_ARCHIVO_BYTES,
                    ),
                )
            return data
    except BuiltInError:
        raise
    except (OSError, UnicodeDecodeError) as e:
        raise BuiltInError(
            "IL-EST-015", M("IL-EST-015.leer_archivo_no_pudo", ruta=ruta, e=e)
        ) from e


def escribir_archivo(ruta, contenido):
    """Escribe `contenido` en `ruta`, reemplazando el archivo si ya existe.

    (o creándolo). Retorna verdadero si tuvo éxito; IL-EST-016 si no se
    pudo escribir (ruta inválida, permisos, disco lleno, ...). Máx 2 MiB.
    """
    ruta_v = _validar_ruta(ruta)
    _validar_contenido(contenido)
    try:
        with open(ruta_v, "w", encoding="utf-8") as f:
            f.write(contenido)
        return True
    except OSError as e:
        raise BuiltInError(
            "IL-EST-016", M("IL-EST-016.escribir_archivo_no_pudo", ruta=ruta, e=e)
        ) from e


def agregar_archivo(ruta, contenido):
    """Agrega `contenido` al final de `ruta` (la crea si no existe).

    Retorna verdadero si tuvo éxito; IL-EST-017 si no se pudo escribir. Máx 2 MiB por agregado.
    """
    ruta_v = _validar_ruta(ruta)
    _validar_contenido(contenido)
    # Comprobar tamaño resultante
    try:
        if os.path.exists(ruta_v):
            tam_actual = os.path.getsize(ruta_v)
            if tam_actual + len(contenido.encode("utf-8")) > _MAX_ARCHIVO_BYTES:
                raise BuiltInError(
                    "IL-EST-017",
                    M(
                        "IL-EST-017.agregar_archivo_tamano_resultante",
                        MAX_ARCHIVO_BYTES=_MAX_ARCHIVO_BYTES,
                    ),
                )
    except BuiltInError:
        raise
    except OSError:
        pass
    try:
        with open(ruta_v, "a", encoding="utf-8") as f:
            f.write(contenido)
        return True
    except OSError as e:
        raise BuiltInError(
            "IL-EST-017", M("IL-EST-017.agregar_archivo_no_pudo", ruta=ruta, e=e)
        ) from e


# ============================================================
# Funciones de apoyo añadidas en la v11 (INV-1410)
# ============================================================


def absoluto_real(x):
    """Valor absoluto de un real (``absoluto``/``abs`` solo aceptan int)."""
    return abs(float(x))


def redondear(x):
    """Redondeo al entero más cercano, con los empates alejándose de cero.

    Es la regla que se enseña en la escuela (2.5 -> 3, -2.5 -> -3); el
    ``round`` de Python redondea al par (2.5 -> 2), lo que sorprende a un
    estudiante. IL-EJE-003 si el resultado no cabe en int.
    """
    if x != x or x in (float("inf"), float("-inf")):
        raise BuiltInError("IL-EJE-003", M("IL-EJE-003.redondear_no_finito"))
    n = math.floor(abs(x) + 0.5)
    n = n if x >= 0 else -n
    if n < INT_MIN or n > INT_MAX:
        raise BuiltInError(
            "IL-EJE-003", M("IL-EJE-003.redondear_excede", val=x, INT_MIN=INT_MIN, INT_MAX=INT_MAX)
        )
    return n


def longitud_arreglo(arreglo):
    """Cantidad de elementos de un arreglo (de filas, si es una matriz).

    Un procedimiento que recibe ``entero[] a`` no conoce el tamaño con que
    se declaró el arreglo del llamador; sin esta función había que pasarlo
    siempre como parámetro extra.
    """
    return len(arreglo)


def lanzar_error(mensaje):
    """Detiene la ejecución con un error del programa (IL-EJE-060).

    Permite que una estructura de datos rechace una operación inválida
    (desapilar una pila vacía) con un mensaje propio, capturable con
    intentar/capturar, en vez de devolver un valor inventado.
    """
    raise BuiltInError("IL-EJE-060", M("IL-EJE-060.error_programa", mensaje=mensaje))


# Tabla de funciones integradas: nombre -> (funcion, tipo_retorno, [tipos_parametros])
FUNCIONES_BUILT_IN: dict[str, tuple[Callable, str, list[str]]] = {}

# INV-1410: registro BILINGÜE declarativo. Cada fila es UNA implementación
# con su nombre en español, su nombre en inglés y, si los hay, alias
# históricos (los nombres "canónicos" mixtos de la §4 como int_a_float). El
# traductor de código fuente (traductor.py) usa esta misma tabla para pasar
# de un idioma al otro, así que no puede existir una función con nombre en
# un solo idioma: lo comprueba tests/test_i18n.py.
#
# Nota de diseño: los nombres de función integrada están reservados en TODO
# ámbito (§19.1, IL-SEM-080) -- por eso NO se usan aquí palabras como
# "longitud", "raiz", "potencia", "maximo" o "minimo" a secas: son
# exactamente los nombres que varios programas de referencia PERMANENTES
# (§18.1) ya usan para sus propias variables/funciones de ejercicio
# (`potencia` en funciones.inv, `raiz` en arbol_binario.inv, `maximo`/
# `minimo` en estadisticas.inv/calculadora_es.inv, `longitud` como
# parámetro en procedimientos.inv). Reservarlas rompería esos programas.
# `maximo`/`minimo` además quedan fuera a propósito: con el operador
# ternario, `a > b ? a : b` los vuelve triviales de escribir.
#   (español, inglés, alias, función, tipo_retorno, tipos_parámetros)
BUILT_INS_BILINGUES: tuple[tuple[str, str, tuple[str, ...], Callable, str, list[str]], ...] = (
    # Conversiones (§19): la §4 usa nombres mixtos (int_a_float) que siguen
    # siendo válidos como alias.
    ("entero_a_real", "int_to_float", ("int_a_float",), int_a_float, "float", ["int"]),
    ("real_a_entero", "float_to_int", ("float_a_int",), float_a_int, "int", ["float"]),
    ("entero_a_texto", "int_to_string", ("int_a_texto",), int_a_texto, "string", ["int"]),
    ("real_a_texto", "float_to_string", ("float_a_texto",), float_a_texto, "string", ["float"]),
    ("texto_a_entero", "string_to_int", ("texto_a_int",), texto_a_int, "int", ["string"]),
    ("texto_a_real", "string_to_float", ("texto_a_float",), texto_a_float, "float", ["string"]),
    ("logico_a_texto", "bool_to_string", ("bool_a_texto",), bool_a_texto, "string", ["bool"]),
    ("texto_a_logico", "string_to_bool", ("texto_a_bool",), texto_a_bool, "bool", ["string"]),
    # Cadenas (Etapa 6)
    ("longitud_texto", "text_length", (), longitud, "int", ["string"]),
    ("subcadena", "substring", (), subcadena, "string", ["string", "int", "int"]),
    ("mayusculas", "to_upper", (), mayusculas, "string", ["string"]),
    ("minusculas", "to_lower", (), minusculas, "string", ["string"]),
    ("caracter_en", "char_at", (), caracter_en, "string", ["string", "int"]),
    ("indice_de", "index_of", (), indice_de, "int", ["string", "string"]),
    ("recortar", "trim", (), recortar, "string", ["string"]),
    ("invertir_texto", "reverse_string", (), invertir_texto, "string", ["string"]),
    # Matemática (Etapa 6 + INV-1410)
    ("raiz_cuadrada", "sqrt", (), raiz, "float", ["float"]),
    ("elevar", "pow", (), potencia, "float", ["float", "float"]),
    ("absoluto", "abs", (), absoluto, "int", ["int"]),
    ("absoluto_real", "fabs", (), absoluto_real, "float", ["float"]),
    ("redondear", "round", (), redondear, "int", ["float"]),
    ("piso", "floor", (), piso, "int", ["float"]),
    ("techo", "ceil", (), techo, "int", ["float"]),
    ("azar", "random", (), azar, "int", ["int", "int"]),
    # Arreglos (INV-1410): el parámetro "int[]" acepta cualquier arreglo o
    # matriz por referencia (type_checker no compara el tipo de elemento
    # en el paso por referencia).
    ("longitud_arreglo", "array_length", (), longitud_arreglo, "int", ["int[]"]),
    # Errores del programa (INV-1410)
    ("lanzar_error", "throw_error", (), lanzar_error, "void", ["string"]),
    # Entrada/salida de archivos (Etapa 10)
    ("existe_archivo", "file_exists", (), existe_archivo, "bool", ["string"]),
    ("leer_archivo", "read_file", (), leer_archivo, "string", ["string"]),
    ("escribir_archivo", "write_file", (), escribir_archivo, "bool", ["string", "string"]),
    ("agregar_archivo", "append_file", (), agregar_archivo, "bool", ["string", "string"]),
)

# Nombre (en cualquier idioma o alias) -> (español, inglés). Lo usa el
# traductor de código fuente.
PARES_BUILT_IN: dict[str, tuple[str, str]] = {}

# Funciones de orden superior (Etapa 12.7): no están en FUNCIONES_BUILT_IN
# porque reciben valores-función (ver semantic.py::_ORDEN_SUPERIOR), pero
# también tienen nombre en ambos idiomas.
PARES_ORDEN_SUPERIOR: dict[str, tuple[str, str]] = {
    nombre: par
    for par in (("reducir", "reduce"), ("mapear", "map"), ("filtrar", "filter"))
    for nombre in par
}

for _es, _en, _alias, _func, _ret, _params in BUILT_INS_BILINGUES:
    for _nombre in (_es, _en, *_alias):
        FUNCIONES_BUILT_IN[_nombre] = (_func, _ret, _params)
        PARES_BUILT_IN[_nombre] = (_es, _en)


def es_built_in(nombre):
    """Indica si un nombre corresponde a una función integrada."""
    return nombre in FUNCIONES_BUILT_IN


def ejecutar_built_in(nombre, argumentos):
    """Ejecuta una función integrada y retorna su resultado. Facade + Strategy."""
    if nombre not in FUNCIONES_BUILT_IN:
        raise ValueError(f"Función integrada desconocida: {nombre}")
    func, _, _ = FUNCIONES_BUILT_IN[nombre]
    return func(*argumentos)


# ============================================================
# Strategy Registry — Cada conversión es una estrategia
# ============================================================


class BuiltInFactory(RegistryFactory):
    """Factory para built-ins — centraliza creación y validación."""

    _instance: BuiltInFactory | None = None

    @classmethod
    def get_instance(cls) -> BuiltInFactory:
        """Retorna la instancia compartida."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._init_defaults()
        return cls._instance

    def _init_defaults(self) -> None:
        for nombre, (func, _ret, _params) in FUNCIONES_BUILT_IN.items():
            self.register(nombre, lambda f=func: f)
