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
    # POO (InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md)
    CLASE = auto()
    ATRIBUTO = auto()
    METODO = auto()
    CONSTRUCTOR = auto()


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
        self.es_constante = False  # Etapa 11: arreglo declarado con const (IL-SEM-031)

    def __repr__(self):
        return (f"{self.nombre}: {self.tipo_simbolo.name}({self.tipo_dato}) "
                f"[L{self.linea}:C{self.columna}]")


class MiembroInfo:
    """Informacion de un atributo, independiente del nodo AST (POO, v2.0)."""

    def __init__(self, nombre, visibilidad, tipo, linea, columna, es_estatico=False):
        self.nombre = nombre
        self.visibilidad = visibilidad  # 'publico' | 'privado'
        self.tipo = tipo  # tipo de dato del atributo
        self.linea = linea
        self.columna = columna
        self.es_estatico = es_estatico  # Etapa 7: atributo de clase, no de instancia


class MetodoInfo(MiembroInfo):
    """Informacion de un metodo: agrega la firma (tipos de parametros)."""

    def __init__(self, nombre, visibilidad, tipo_retorno, params_tipos, linea, columna,
                es_estatico=False, es_abstracto=False):
        super().__init__(nombre, visibilidad, tipo_retorno, linea, columna, es_estatico)
        self.params_tipos = params_tipos  # list[str]
        self.es_abstracto = es_abstracto  # Etapa 7: sin cuerpo, la subclase debe implementarlo


class ClaseInfo:
    """Informacion de una clase declarada (POO, InvenioLang 2.0).

    Vive en `SymbolTable.clases`, un mecanismo PARALELO a `ambitos`: el
    lookup de un miembro de instancia (`objeto.miembro`) no es una busqueda
    de ambito lexico -- es una busqueda por jerarquia de herencia -- por eso
    no se apoya en `buscar()`, que recorre la pila de ambitos léxicos.
    """

    def __init__(self, nombre, padre, linea, columna, es_abstracta=False, es_enum=False,
                interfaces=None, es_interfaz=False):
        self.nombre = nombre
        self.padre = padre  # str o None
        self.linea = linea
        self.columna = columna
        self.es_abstracta = es_abstracta  # Etapa 7: no instanciable con nuevo
        self.es_enum = es_enum  # Etapa 11: tampoco instanciable con nuevo
        self.interfaces = interfaces if interfaces else []  # list[str] (Etapa 12.3)
        self.es_interfaz = es_interfaz  # Etapa 12.3: 'interfaz X {...}'
        self.atributos = {}  # nombre -> MiembroInfo (instancia o estatico)
        self.metodos = {}  # nombre -> list[MetodoInfo] (Etapa 7: sobrecarga)
        self.constructores = []  # list[MetodoInfo] (Etapa 10: sobrecarga; vacia = implicito, 0 args)
        self.estado_estatico = {}  # Etapa 7: nombre_attr_estatico -> valor (interpreter.py)

    def __repr__(self):
        return f"ClaseInfo({self.nombre}, hereda={self.padre})"


class SymbolTable:
    """Tabla de símbolos con soporte de alcance léxico estático por bloques.

    Mantiene una pila de ámbitos. Cada ámbito es un diccionario nombre -> SymbolEntry.
    El ámbito 0 es siempre el global. Los ámbitos se crean al entrar en un bloque
    y se destruyen al salir.
    """

    def __init__(self):
        self.ambitos = [{}]  # Pila de ámbitos, índice 0 = global
        self.nombres_funciones = {}  # Acceso rápido a funciones/procedimientos
        self.loop_actual = 0  # Contador de profundidad de bucles anidados (while/for/do-while)
        self.switch_actual = 0  # Contador de profundidad de switch anidados (Etapa 6)
        self.clases = {}  # nombre -> ClaseInfo (POO, InvenioLang 2.0)
        self._registrar_clase_excepcion()

    def _registrar_clase_excepcion(self):
        """Clase sintética 'Excepcion' (Etapa 6, try/catch genérico): siempre
        disponible sin que el usuario la declare, con dos campos públicos de
        solo lectura `codigo` y `mensaje` -- reutiliza el mecanismo de
        acceso a miembro que ya existe para POO en vez de un tipo nuevo. Un
        `clase Excepcion {...}` del usuario reporta IL-POO-001 (duplicado),
        igual que redeclarar cualquier otra clase reservada."""
        info = ClaseInfo('Excepcion', None, 0, 0)
        info.atributos['codigo'] = MiembroInfo('codigo', 'publico', 'string', 0, 0)
        info.atributos['mensaje'] = MiembroInfo('mensaje', 'publico', 'string', 0, 0)
        self.clases['Excepcion'] = info

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
        """Indica si estamos dentro de un bucle (while/for/do-while) -- lo
        único que satisface `continue` (§9, Etapa 6)."""
        return self.loop_actual > 0

    def esta_en_loop_o_switch(self):
        """Indica si `break` es válido aquí: dentro de un bucle O de un
        switch/segun (Etapa 6) -- a diferencia de `continue`, que un switch
        NO satisface."""
        return self.loop_actual > 0 or self.switch_actual > 0

    def marcar_inicializado(self, nombre):
        """Marca un símbolo como inicializado."""
        entrada = self.buscar(nombre)
        if entrada:
            entrada.inicializado = True

    # ============================================================
    # POO (InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md)
    # ============================================================

    def declarar_clase(self, nombre, padre, linea, columna, es_abstracta=False,
                       interfaces=None, es_interfaz=False):
        """Registra una clase nueva. Retorna la ClaseInfo creada, o None si
        el nombre ya estaba declarado (IL-POO-001, a cargo del llamador)."""
        if nombre in self.clases:
            return None
        info = ClaseInfo(nombre, padre, linea, columna, es_abstracta=es_abstracta,
                         interfaces=interfaces, es_interfaz=es_interfaz)
        self.clases[nombre] = info
        return info

    def buscar_clase(self, nombre):
        """Retorna la ClaseInfo de `nombre`, o None si no es una clase
        declarada."""
        return self.clases.get(nombre)

    def es_clase(self, nombre):
        return nombre in self.clases

    def cadena_ancestros(self, nombre):
        """Lista de nombres de clase desde `nombre` hasta la raiz de su
        jerarquia (`nombre` incluido). Retorna None si hay un ciclo de
        herencia o un padre inexistente -- el llamador (semantic.py) debe
        validar esos dos casos (IL-POO-002/003) ANTES de apoyarse en el
        resultado de este metodo para otra cosa."""
        vistos = []
        actual = nombre
        while actual is not None:
            if actual in vistos:
                return None  # herencia circular
            vistos.append(actual)
            info = self.clases.get(actual)
            if info is None:
                return None  # padre inexistente
            actual = info.padre
        return vistos

    def es_subtipo_clase(self, hijo, ancestro):
        """True si `hijo` es `ancestro`, desciende de el (upcasting, §3
        regla 9 de la spec de POO), o `ancestro` es una interfaz que
        `hijo` (o cualquiera de sus ancestros por `hereda`) implementa
        (Etapa 12.3) -- una clase que implementa una interfaz "es" esa
        interfaz para efectos de asignacion/paso de argumentos, igual que
        Java/C#/Kotlin."""
        cadena = self.cadena_ancestros(hijo)
        if cadena is None:
            return False
        if ancestro in cadena:
            return True
        for clase in cadena:
            if ancestro in self.clases[clase].interfaces:
                return True
        return False

    def resolver_atributo(self, nombre_clase, nombre_atributo):
        """Busca `nombre_atributo` en `nombre_clase` y su cadena de
        ancestros (el mas derivado que lo declara gana, pero en InvenioLang
        2.0 los atributos no se redeclaran entre padre e hijo -- ver
        IL-POO-004). Retorna (nombre_clase_declarante, MiembroInfo) o None."""
        for clase in self.cadena_ancestros(nombre_clase) or []:
            info = self.clases[clase]
            if nombre_atributo in info.atributos:
                return clase, info.atributos[nombre_atributo]
        return None

    def resolver_metodo(self, nombre_clase, nombre_metodo, tipos_args=None):
        """Busca `nombre_metodo` en `nombre_clase` y su cadena de
        ancestros, devolviendo la implementacion MAS DERIVADA visible desde
        `nombre_clase` (la cadena ya va del mas derivado al mas base).
        Retorna (nombre_clase_declarante, MetodoInfo) o None.

        Esta misma funcion sirve para dos propositos distintos segun desde
        donde se la llame: resolucion ESTATICA de tipos (type_checker.py,
        arrancando desde el tipo declarado de la variable) y despacho
        VIRTUAL en tiempo de ejecucion (interpreter.py, arrancando desde la
        clase REAL del objeto) -- el polimorfismo surge simplemente de que
        el intérprete la invoca con un `nombre_clase` distinto al que usó
        el verificador de tipos.

        `tipos_args` (Etapa 7, sobrecarga): sin dar este argumento, retorna
        la PRIMERA sobrecarga declarada (uso previo a la sobrecarga: solo
        existencia/aridad, a cargo de semantic.py). Dandolo, elige la
        sobrecarga cuya firma coincide -- exacta primero, si no compatible
        por promocion/upcasting; None si ninguna coincide o hay mas de una
        igual de buena (ambigua). La sobrecarga se resuelve SOLO dentro de
        la clase que primero declara ese nombre en la cadena: una subclase
        que redeclara el nombre no hereda las sobrecargas del padre, igual
        que ya pasa con la sobrescritura simple."""
        for clase in self.cadena_ancestros(nombre_clase) or []:
            info = self.clases[clase]
            candidatos = info.metodos.get(nombre_metodo)
            if not candidatos:
                continue
            if tipos_args is None:
                return clase, candidatos[0]
            elegido = self._elegir_sobrecarga(candidatos, tipos_args)
            return (clase, elegido) if elegido is not None else None
        return None

    def resolver_metodo_todos(self, nombre_clase, nombre_metodo):
        """Todas las sobrecargas de `nombre_metodo` visibles desde
        `nombre_clase` (para diagnosticos de aridad -- semantic.py, que no
        conoce tipos de argumentos). Retorna (clase_declarante,
        list[MetodoInfo]) o None."""
        for clase in self.cadena_ancestros(nombre_clase) or []:
            info = self.clases[clase]
            candidatos = info.metodos.get(nombre_metodo)
            if candidatos:
                return clase, candidatos
        return None

    def resolver_constructor(self, nombre_clase, tipos_args=None):
        """Busca el constructor de `nombre_clase` que coincide con
        `tipos_args` (Etapa 10: sobrecarga de constructores). A diferencia
        de resolver_metodo, NO camina la cadena de herencia -- cada clase
        tiene sus propios constructores, nunca hereda los del padre (ya era
        así con un solo constructor: padre(...)/super(...) llama
        explícitamente al del padre, nunca por herencia implícita).

        Sin `tipos_args`, retorna el primero declarado (uso previo a la
        sobrecarga: solo existencia/aridad, a cargo de semantic.py). Con
        `tipos_args`, elige la sobrecarga cuya firma coincide -- exacta
        primero, si no compatible por promoción/upcasting; None si ninguna
        coincide o hay ambigüedad. Si la clase no declara NINGÚN
        constructor, retorna None -- el llamador debe tratar eso como el
        constructor implícito de 0 argumentos (mismo criterio que antes)."""
        info = self.clases.get(nombre_clase)
        if info is None or not info.constructores:
            return None
        if tipos_args is None:
            return info.constructores[0]
        return self._elegir_sobrecarga(info.constructores, tipos_args)

    def resolver_constructor_todos(self, nombre_clase):
        """Todas las sobrecargas de constructor de `nombre_clase` (para
        diagnósticos de aridad en semantic.py). Retorna list[MetodoInfo]
        (vacía si no declara ninguno -- constructor implícito)."""
        info = self.clases.get(nombre_clase)
        return list(info.constructores) if info is not None else []

    def _elegir_sobrecarga(self, candidatos, tipos_args):
        """candidatos: list[MetodoInfo] con el mismo nombre. Retorna el que
        coincide con `tipos_args`, o None si ninguno o si hay ambiguedad."""
        exactas = [m for m in candidatos if m.params_tipos == tipos_args]
        if len(exactas) == 1:
            return exactas[0]
        if exactas:
            return None
        compatibles = [
            m for m in candidatos
            if len(m.params_tipos) == len(tipos_args)
            and all(self._tipo_compatible_simple(esp, real)
                   for esp, real in zip(m.params_tipos, tipos_args))
        ]
        return compatibles[0] if len(compatibles) == 1 else None

    def _tipo_compatible_simple(self, esperado, real):
        """Version reducida de TypeChecker._compatible -- solo lo que hace
        falta para elegir sobrecarga (promocion int->float, upcasting de
        clases, nulo). symbol_table.py no depende de type_checker.py, asi
        que se duplica esta regla simple en vez de importar de ahi."""
        if esperado == real:
            return True
        if esperado == 'float' and real == 'int':
            return True
        if self.es_clase(esperado) and self.es_clase(real):
            return self.es_subtipo_clase(real, esperado)
        if real == 'null' and self.es_clase(esperado):
            return True
        return False
