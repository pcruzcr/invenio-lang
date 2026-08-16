# Funciones Integradas de InvenioLang 1.0 (Sección 19)
# Implementa las 8 funciones de conversión entre tipos

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
