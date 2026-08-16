# Módulo de Tabla de Símbolos de InvenioLang 1.0
# Implementa la gestión de ámbitos y almacenamiento de símbolos (§5.5, §14)
# Soporta tres niveles de alcance: global, función y bloque interno

from enum import Enum, auto


class TipoSimbolo(Enum):
    """Clasificación de los símbolos en la tabla."""
    VARIABLE = auto()
    CONSTANTE = auto()
    FUNCION = auto()
    PROCEDIMIENTO = auto()
    ARREGLO = auto()
    MATRIZ = auto()
    PARAMETRO = auto()
    PARAM_ARREGLO = auto()
    PARAM_MATRIZ = auto()


class SymbolEntry:
    """Entrada individual en la tabla de símbolos.

    Atributos:
        nombre: Nombre del identificador
        tipo_simbolo: Tipo de símbolo (variable, función, etc.)
        tipo_dato: Tipo de dato ('int', 'float', 'string', 'bool', 'void')
        linea: Línea de declaración
        columna: Columna de declaración
        inicializado: Indica si tiene inicialización
        tam_arreglo: Tamaño si es arreglo
        filas_matriz: Filas si es matriz
        cols_matriz: Columnas si es matriz
        params: Lista de tipos de parámetros (para funciones/procedimientos)
        tipo_retorno: Tipo de retorno (para funciones)
        es_parametro_arreglo: True si es parámetro de tipo arreglo
        es_parametro_matriz: True si es parámetro de tipo matriz
    """

    def __init__(self, nombre, tipo_simbolo, tipo_dato, linea, columna):
        self.nombre = nombre
        self.tipo_simbolo = tipo_simbolo
        self.tipo_dato = tipo_dato
        self.linea = linea
        self.columna = columna
        self.inicializado = False
        self.tam_arreglo = None
        self.filas_matriz = None
        self.cols_matriz = None
        self.params = []
        self.tipo_retorno = None
        self.es_parametro_arreglo = False
        self.es_parametro_matriz = False

    def __repr__(self):
        return (f"{self.nombre}: {self.tipo_simbolo.name}({self.tipo_dato}) "
                f"[L{self.linea}:C{self.columna}]")


class SymbolTable:
    """Tabla de símbolos con soporte de alcance léxico estático por bloques.

    Mantiene una pila de ámbitos. Cada ámbito es un diccionario nombre -> SymbolEntry.
    El ámbito 0 es siempre el global. Los ámbitos se crean al entrar en un bloque
    y se destruyen al salir.
    """

    def __init__(self):
        self.ambitos = [{}]  # Pila de ámbitos, índice 0 = global
        self.nombres_funciones = {}  # Acceso rápido a funciones/procedimientos
        self.loop_actual = 0  # Contador de profundidad de bucles anidados

    def entrar_ambito(self):
        """Entra en un nuevo ámbito (nuevo bloque)."""
        self.ambitos.append({})

    def salir_ambito(self):
        """Sale del ámbito actual."""
        if len(self.ambitos) > 1:
            self.ambitos.pop()

    def ambito_actual(self):
        """Retorna el diccionario del ámbito actual."""
        return self.ambitos[-1]

    def declarar(self, nombre, tipo_simbolo, tipo_dato, linea, columna):
        """Declara un nuevo símbolo en el ámbito actual.

        Retorna la entrada creada o None si ya existe (error de duplicado).
        """
        ambito = self.ambito_actual()
        if nombre in ambito:
            return None
        entrada = SymbolEntry(nombre, tipo_simbolo, tipo_dato, linea, columna)
        ambito[nombre] = entrada
        # Si es función o procedimiento, también se guarda en el índice global
        if tipo_simbolo in (TipoSimbolo.FUNCION, TipoSimbolo.PROCEDIMIENTO):
            self.nombres_funciones[nombre] = entrada
        return entrada

    def buscar(self, nombre):
        """Busca un símbolo en todos los ámbitos visibles (del más interno al global).

        Retorna la entrada o None si no se encuentra.
        """
        for ambito in reversed(self.ambitos):
            if nombre in ambito:
                return ambito[nombre]
        return None

    def buscar_en_ambito_actual(self, nombre):
        """Busca solo en el ámbito actual."""
        return self.ambito_actual().get(nombre)

    def hay_externo(self, nombre):
        """Indica si el identificador ya está declarado en algún ámbito externo
        (no en el actual). Se usa para detectar ocultamiento (IL-WARN-001 §3.5.3)."""
        for ambito in self.ambitos[:-1]:
            if nombre in ambito:
                return True
        return False

    def buscar_funcion(self, nombre):
        """Busca una función o procedimiento registrado."""
        return self.nombres_funciones.get(nombre)

    def es_global(self, nombre):
        """Indica si un símbolo está en el ámbito global."""
        return nombre in self.ambitos[0]

    def profundidad_ambito(self):
        """Retorna la profundidad actual de la pila de ámbitos."""
        return len(self.ambitos)

    def obtener_simbolos_visibles(self):
        """Retorna todos los símbolos visibles (para depuración)."""
        vistos = set()
        resultado = {}
        for ambito in reversed(self.ambitos):
            for nombre, entrada in ambito.items():
                if nombre not in vistos:
                    resultado[nombre] = entrada
                    vistos.add(nombre)
        return resultado

    def esta_en_loop(self):
        """Indica si estamos dentro de un bucle (while/for)."""
        return self.loop_actual > 0

    def marcar_inicializado(self, nombre):
        """Marca un símbolo como inicializado."""
        entrada = self.buscar(nombre)
        if entrada:
            entrada.inicializado = True
