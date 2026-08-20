# Funciones Integradas de InvenioLang 1.0 (Sección 19)
# Implementa las 8 funciones de conversión entre tipos, más la librería
# estándar de cadenas y matemática de la Etapa 6 (lenguaje estructurado
# completo, ver docs/InvenioLang_Etapa6_Estructurado.md).

import math
import os
import random
import re

# Rango del tipo int / entero: 32 bits con signo (§4.2.1)
INT_MIN = -2147483648
INT_MAX = 2147483647

# Formatos admitidos por las funciones de parseo (§19.7, §19.8)
_RE_ENTERO = re.compile(r'^[+-]?\d+$')
_RE_REAL = re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$')


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
    if val != val or val in (float('inf'), float('-inf')):
        raise BuiltInError('IL-EJE-003',
                           'float_to_int recibió un valor no finito')
    truncado = int(val)  # int() trunca hacia cero
    if truncado < INT_MIN or truncado > INT_MAX:
        raise BuiltInError(
            'IL-EJE-003',
            f'float_to_int: {val} excede el rango de int '
            f'[{INT_MIN}, {INT_MAX}]'
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
    if 'e' in s or 'E' in s:
        # Notación científica: asegurar mantisa con punto ("1e+15" -> "1.0e+15")
        mantisa, _, exp = s.partition('e')
        if '.' not in mantisa:
            mantisa += '.0'
        return f'{mantisa}e{exp}'
    if '.' not in s:
        s += '.0'
    return s


def texto_a_int(val):
    """Convierte string a int decimal (§19.7).

    Acepta signo opcional y dígitos decimales, ignorando espacios en los
    extremos. IL-EJE-004 en cualquier otro caso o si excede el rango de int.
    """
    s = val.strip()
    if not _RE_ENTERO.match(s):
        raise BuiltInError(
            'IL-EJE-004',
            f'string_to_int: "{val}" no es un entero decimal válido'
        )
    n = int(s)
    if n < INT_MIN or n > INT_MAX:
        raise BuiltInError(
            'IL-EJE-004',
            f'string_to_int: {n} excede el rango de int [{INT_MIN}, {INT_MAX}]'
        )
    return n


def texto_a_float(val):
    """Convierte string a float (§19.8).

    Acepta signo, parte decimal opcional y exponente opcional. IL-EJE-005 en
    cualquier otro caso.
    """
    s = val.strip()
    if not _RE_REAL.match(s):
        raise BuiltInError(
            'IL-EJE-005',
            f'string_to_float: "{val}" no es un número real válido'
        )
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
    if v in ('true', 'verdadero'):
        return True
    if v in ('false', 'falso'):
        return False
    raise BuiltInError(
        'IL-EJE-022',
        f'string_to_bool: "{val}" no es true/false/verdadero/falso'
    )


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
            'IL-EST-010',
            f'subcadena: rango [{inicio},{fin}) inválido para una cadena '
            f'de longitud {len(s)}'
        )
    return s[inicio:fin]


def mayusculas(s):
    return s.upper()


def minusculas(s):
    return s.lower()


def caracter_en(s, i):
    """Carácter (como cadena de 1) en la posición i. IL-EST-011 si i está
    fuera de rango."""
    if i < 0 or i >= len(s):
        raise BuiltInError(
            'IL-EST-011',
            f'caracter_en: índice {i} fuera de rango para una cadena de '
            f'longitud {len(s)}'
        )
    return s[i]


def indice_de(s, sub):
    """Posición de la primera aparición de sub en s, o -1 si no aparece
    (mismo convenio que arreglos.inv::buscar)."""
    return s.find(sub)


def recortar(s):
    """Quita espacios en blanco al inicio y al final."""
    return s.strip()


def invertir_texto(s):
    """Cadena invertida (Etapa 10) -- ejercicio clásico de Fundamentos
    (verificar palíndromos) sin tener que armar el bucle manual cada vez."""
    return s[::-1]


def raiz(x):
    """Raíz cuadrada. IL-EST-012 si x es negativo."""
    if x < 0:
        raise BuiltInError('IL-EST-012', f'raiz: no está definida para {x} (negativo)')
    return math.sqrt(x)


def potencia(base, exponente):
    """base elevado a exponente. IL-EST-013 si el resultado no es un
    número real (p. ej. raíz de un negativo con exponente fraccionario)."""
    try:
        resultado = base ** exponente
    except (ValueError, OverflowError) as e:
        raise BuiltInError('IL-EST-013', f'potencia: {e}')
    if isinstance(resultado, complex):
        raise BuiltInError(
            'IL-EST-013',
            f'potencia: {base} ** {exponente} no produce un número real'
        )
    return float(resultado)


def absoluto(x):
    return abs(x)


def piso(x):
    """Redondea hacia abajo al entero más cercano."""
    return math.floor(x)


def techo(x):
    """Redondea hacia arriba al entero más cercano."""
    return math.ceil(x)


def azar(minimo_, maximo_):
    """Entero aleatorio uniforme en [minimo_, maximo_]. IL-EST-014 si el
    rango es inválido."""
    if minimo_ > maximo_:
        raise BuiltInError(
            'IL-EST-014',
            f'azar: el mínimo ({minimo_}) no puede ser mayor que el '
            f'máximo ({maximo_})'
        )
    return random.randint(minimo_, maximo_)


# ============================================================
# Entrada/salida de archivos (Etapa 10)
# ============================================================
#
# Alcance deliberadamente simple: texto plano completo por llamada (sin
# lectura línea a línea ni un tipo "manejador de archivo" nuevo) -- cubre
# el caso real de un ejercicio de Fundamentos/Programación 2 (guardar un
# resultado, leer datos de entrada desde un archivo) sin ampliar el sistema
# de tipos. Codificación siempre UTF-8, igual que el resto del lenguaje.

def existe_archivo(ruta):
    """True si `ruta` existe y es un archivo regular (no directorio).
    Nunca falla -- una ruta inexistente es simplemente False, no un error."""
    return os.path.isfile(ruta)


def leer_archivo(ruta):
    """Contenido completo de `ruta` como texto. IL-EST-015 si no existe, no
    se puede leer (permisos) o no es UTF-8 válido."""
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise BuiltInError('IL-EST-015', f'leer_archivo: no se pudo leer "{ruta}": {e}')


def escribir_archivo(ruta, contenido):
    """Escribe `contenido` en `ruta`, reemplazando el archivo si ya existe
    (o creándolo). Retorna verdadero si tuvo éxito; IL-EST-016 si no se
    pudo escribir (ruta inválida, permisos, disco lleno, ...)."""
    try:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        return True
    except OSError as e:
        raise BuiltInError('IL-EST-016', f'escribir_archivo: no se pudo escribir "{ruta}": {e}')


def agregar_archivo(ruta, contenido):
    """Agrega `contenido` al final de `ruta` (la crea si no existe).
    Retorna verdadero si tuvo éxito; IL-EST-017 si no se pudo escribir."""
    try:
        with open(ruta, 'a', encoding='utf-8') as f:
            f.write(contenido)
        return True
    except OSError as e:
        raise BuiltInError('IL-EST-017', f'agregar_archivo: no se pudo escribir "{ruta}": {e}')


# Tabla de funciones integradas: nombre -> (funcion, tipo_retorno, [tipos_parametros])
# Nombres canónicos (Sección 4 / README): int_a_float, int_a_texto, texto_a_int, ...
# La Sección 19 usa nomenclatura distinta (int_to_float, int_to_string, string_to_int, ...)
# y promete bilingüismo español (entero_a_real, entero_a_texto, ...). Para satisfacer
# ambas secciones, se registran TODOS los alias como nombres válidos e indistinguibles.
_ALIASES_BUILT_IN = {}
FUNCIONES_BUILT_IN = {}


def _registrar(nombre, func, tipo_retorno, tipos_parametros):
    FUNCIONES_BUILT_IN[nombre] = (func, tipo_retorno, tipos_parametros)
    _ALIASES_BUILT_IN[nombre] = (func, tipo_retorno, tipos_parametros)


# Canónicos (§4, §17, README)
_registrar('int_a_float', int_a_float, 'float', ['int'])
_registrar('float_a_int', float_a_int, 'int', ['float'])
_registrar('int_a_texto', int_a_texto, 'string', ['int'])
_registrar('float_a_texto', float_a_texto, 'string', ['float'])
_registrar('texto_a_int', texto_a_int, 'int', ['string'])
_registrar('texto_a_float', texto_a_float, 'float', ['string'])
_registrar('bool_a_texto', bool_a_texto, 'string', ['bool'])
_registrar('texto_a_bool', texto_a_bool, 'bool', ['string'])

# Alias nomenclatura Sección 19 (inglés): int_to_float, string_to_int, ...
_ALIAS_INGLES = {
    'int_a_float': 'int_to_float',
    'float_a_int': 'float_to_int',
    'int_a_texto': 'int_to_string',
    'float_a_texto': 'float_to_string',
    'texto_a_int': 'string_to_int',
    'texto_a_float': 'string_to_float',
    'bool_a_texto': 'bool_to_string',
    'texto_a_bool': 'string_to_bool',
}
for _base, _alias in _ALIAS_INGLES.items():
    _func, _ret, _params = FUNCIONES_BUILT_IN[_base]
    _registrar(_alias, _func, _ret, _params)

# Alias español (Sección 19): entero_a_real, real_a_entero, ...
_ALIAS_ESPANOL = {
    'int_a_float': 'entero_a_real',
    'float_a_int': 'real_a_entero',
    'int_a_texto': 'entero_a_texto',
    'float_a_texto': 'real_a_texto',
    'texto_a_int': 'texto_a_entero',
    'texto_a_float': 'texto_a_real',
    'bool_a_texto': 'logico_a_texto',
    'texto_a_bool': 'texto_a_logico',
}
for _base, _alias in _ALIAS_ESPANOL.items():
    _func, _ret, _params = FUNCIONES_BUILT_IN[_base]
    _registrar(_alias, _func, _ret, _params)

# Librería estándar (Etapa 6): un nombre canónico en español + un alias en
# inglés por función, mismo patrón bilingüe que el resto del lenguaje.
#
# Nota de diseño: los nombres de función integrada están reservados en TODO
# ámbito (§19.1, IL-SEM-080) -- por eso NO se usan aquí palabras como
# "longitud", "raiz", "potencia", "maximo" o "minimo" a secas: son
# exactamente los nombres que varios programas de referencia PERMANENTES
# (§18.1) ya usan para sus propias variables/funciones de ejercicio
# (`potencia` en funciones.inv, `raiz` en arbol_binario.inv, `maximo`/
# `minimo` en estadisticas.inv/calculadora_es.inv, `longitud` como
# parámetro en procedimientos.inv). Reservarlas rompería esos programas.
# `maximo`/`minimo` además quedan fuera de la librería a propósito: con el
# operador ternario nuevo, `a > b ? a : b` los vuelve triviales de escribir
# sin necesidad de una función integrada que colisione con ese nombre tan
# común en ejercicios.
_registrar('longitud_texto', longitud, 'int', ['string'])
_registrar('text_length', longitud, 'int', ['string'])
_registrar('subcadena', subcadena, 'string', ['string', 'int', 'int'])
_registrar('substring', subcadena, 'string', ['string', 'int', 'int'])
_registrar('mayusculas', mayusculas, 'string', ['string'])
_registrar('to_upper', mayusculas, 'string', ['string'])
_registrar('minusculas', minusculas, 'string', ['string'])
_registrar('to_lower', minusculas, 'string', ['string'])
_registrar('caracter_en', caracter_en, 'string', ['string', 'int'])
_registrar('char_at', caracter_en, 'string', ['string', 'int'])
_registrar('indice_de', indice_de, 'int', ['string', 'string'])
_registrar('index_of', indice_de, 'int', ['string', 'string'])
_registrar('recortar', recortar, 'string', ['string'])
_registrar('trim', recortar, 'string', ['string'])
_registrar('invertir_texto', invertir_texto, 'string', ['string'])
_registrar('reverse_string', invertir_texto, 'string', ['string'])

_registrar('raiz_cuadrada', raiz, 'float', ['float'])
_registrar('sqrt', raiz, 'float', ['float'])
_registrar('elevar', potencia, 'float', ['float', 'float'])
_registrar('pow', potencia, 'float', ['float', 'float'])
_registrar('absoluto', absoluto, 'int', ['int'])
_registrar('abs', absoluto, 'int', ['int'])
_registrar('piso', piso, 'int', ['float'])
_registrar('floor', piso, 'int', ['float'])
_registrar('techo', techo, 'int', ['float'])
_registrar('ceil', techo, 'int', ['float'])
_registrar('azar', azar, 'int', ['int', 'int'])
_registrar('random', azar, 'int', ['int', 'int'])

# Entrada/salida de archivos (Etapa 10)
_registrar('existe_archivo', existe_archivo, 'bool', ['string'])
_registrar('file_exists', existe_archivo, 'bool', ['string'])
_registrar('leer_archivo', leer_archivo, 'string', ['string'])
_registrar('read_file', leer_archivo, 'string', ['string'])
_registrar('escribir_archivo', escribir_archivo, 'bool', ['string', 'string'])
_registrar('write_file', escribir_archivo, 'bool', ['string', 'string'])
_registrar('agregar_archivo', agregar_archivo, 'bool', ['string', 'string'])
_registrar('append_file', agregar_archivo, 'bool', ['string', 'string'])


def es_built_in(nombre):
    """Indica si un nombre corresponde a una función integrada."""
    return nombre in FUNCIONES_BUILT_IN


def obtener_built_in(nombre):
    """Retorna la tupla (funcion, tipo_retorno, [tipos_parametros])."""
    return FUNCIONES_BUILT_IN.get(nombre)


def ejecutar_built_in(nombre, argumentos):
    """Ejecuta una función integrada y retorna su resultado."""
    if nombre not in FUNCIONES_BUILT_IN:
        raise ValueError(f"Función integrada desconocida: {nombre}")
    func, _, _ = FUNCIONES_BUILT_IN[nombre]
    return func(*argumentos)
