# Módulo de Análisis Semántico de InvenioLang 1.0
# Implementa las reglas semánticas de la Sección 14
# Construye la tabla de símbolos y verifica reglas de alcance, declaración y uso

import copy

from .ast_nodes import *
from .symbol_table import SymbolTable, TipoSimbolo, MiembroInfo, MetodoInfo
from .builtins import FUNCIONES_BUILT_IN

# Tipos primitivos de InvenioLang 1.0. Cualquier otro nombre de tipo debe ser
# una clase declarada (POO, InvenioLang 2.0) o es IL-POO-016.
_TIPOS_PRIMITIVOS = {'int', 'float', 'string', 'bool', 'void'}

# Orden superior sobre arreglos (Etapa 12.7): reducir/mapear/filtrar reciben
# un valor-función como argumento -- no caben en `FUNCIONES_BUILT_IN`
# (builtins.py), cuya tabla genérica solo admite tipos de parámetro
# primitivos/clase, no "funcion(...)->...". Se reconocen aquí por nombre,
# como una tercera categoría de "llamada especial" (junto a función
# declarada por el usuario y valor-función en variable, ver
# _visitar_llamada) -- NO se registran como funciones de verdad en la tabla
# de símbolos. Alcance deliberadamente monomórfico sobre entero (InvenioLang
# no infiere tipos genéricos; los genéricos de la Etapa 7 son explícitos
# `Clase<T>`, no aplican a funciones sueltas) y, como una función NUNCA
# puede retornar un arreglo en este lenguaje (`tipo` de retorno es siempre
# primitivo o clase, ver InvenioLang_GramaticaFormal.md §2.1), `mapear`/
# `filtrar` escriben su resultado en un arreglo de SALIDA pasado por
# referencia en vez de retornar uno nuevo -- reutiliza el mecanismo de
# paso de arreglos por referencia que ya existe, no inventa uno nuevo:
#   entero reducir(entero[] arr, funcion(entero,entero) entero f, entero inicial)
#   void mapear(entero[] arr, entero[] salida, funcion(entero) entero f)
#   entero filtrar(entero[] arr, entero[] salida, funcion(entero) bool pred)  -- retorna cuantos escribio
_ORDEN_SUPERIOR = {
    'reducir': 3, 'reduce': 3,
    'mapear': 3, 'map': 3,
    'filtrar': 3, 'filter': 3,
}


class SemanticAnalyzer:
    """Analizador semántico de InvenioLang 1.0.

    Recorre el AST y construye la tabla de símbolos verificando:
    - Declaración antes de uso (IL-SEM-003)
    - Identificadores duplicados (IL-SEM-002)
    - Constantes no modificadas (IL-SEM-031)
    - Break/continue dentro de bucles (IL-SEM-040, IL-SEM-041)
    - Return en funciones (IL-SEM-050, IL-SEM-053)
    - Procedimientos como expresiones (IL-SEM-060)
    - Argumentos correctos (IL-SEM-052)
    - main válido (IL-SEM-020, IL-SEM-021, IL-SEM-022, IL-SEM-023)
    """

    def __init__(self, error_manager):
        self.error_manager = error_manager
        self.tabla = SymbolTable()
        self._registrar_builtins()

    def _registrar_builtins(self):
        """Registra las funciones integradas en la tabla de símbolos."""
        from .symbol_table import TipoSimbolo
        for nombre, (func, tipo_ret, tipos_params) in FUNCIONES_BUILT_IN.items():
            entrada = self.tabla.declarar(nombre, TipoSimbolo.FUNCION, tipo_ret, 0, 0)
            if entrada:
                entrada.params = tipos_params
                entrada.tipo_retorno = tipo_ret
        self.funcion_actual = None  # Nombre de la función/procedimiento actual
        self.tipo_retorno_actual = None
        self.en_funcion = False
        self.en_procedimiento = False
        self.en_main = False
        self.tiene_return = False
        # Variables ya avisadas con IL-WARN-002 (una advertencia por nombre)
        self._avisadas_sin_init = set()
        # POO (InvenioLang 2.0): clase cuyo metodo/constructor se visita
        # actualmente (None fuera de un cuerpo de clase -- controla la
        # validez de este/this y padre/super, IL-POO-011).
        self.clase_actual = None
        self.en_constructor = False
        # Etapa 12.9/12.10: tipos suma (enum con al menos una variante con
        # carga) -- llenado por _desazucarar_tipos_suma antes de cualquier
        # otra visita. Las variantes ya NO existen como EnumDecl a este
        # punto: se convirtieron en ClassDecl reales (ver ese metodo), asi
        # que estos diccionarios son la unica forma de recuperar "que
        # variantes tenia este enum" para verificar exhaustividad en
        # _visitar_match.
        self.variantes_enum = {}    # nombre_enum -> list[str] variantes, en orden
        self.campos_variante = {}   # nombre_variante -> list[str] campos, en orden
        self.enum_de_variante = {}  # nombre_variante -> nombre_enum
        self.en_metodo_estatico = False  # Etapa 7: bloquea este/padre (IL-POO-025)

    def analizar(self, ast):
        """Analiza semánticamente el AST completo."""
        if ast is None:
            return self.tabla
        self._expandir_genericos(ast)
        self._desazucarar_tipos_suma(ast)
        self._visitar_programa(ast)
        return self.tabla

    # ============================================================
    # Tipos suma / pattern matching (Etapa 12.9/12.10)
    # ============================================================
    #
    # Diseno: un enum donde AL MENOS una variante lleva carga (campos) se
    # desazucara COMPLETO -- todas sus variantes, con o sin carga -- a una
    # clase abstracta base (el nombre del enum) mas una clase concreta por
    # variante que hereda de ella, con sus campos como atributos publicos
    # y un constructor generado que los asigna. Esto reutiliza el 100% del
    # mecanismo de herencia/clases abstractas/despacho virtual ya existente
    # (Etapa 7) -- cero runtime nuevo, ver docs/InvenioLang_GramaticaFormal.md
    # y el plan de la Etapa 12.9. `nuevo Circulo(5)` construye la variante
    # exactamente como cualquier `nuevo` sobre una clase real, porque a
    # partir de aqui ES una clase real.
    #
    # Un enum SIN ninguna variante con carga (el caso de la Etapa 11.8, el
    # unico que existia antes de esta etapa) NO se toca -- sigue el camino
    # de siempre (_declarar_enum, atributos estaticos ordinales).
    def _desazucarar_tipos_suma(self, ast):
        enums_puros = []
        for e in ast.enums:
            if any(m.tiene_carga for m in e.valores):
                self._generar_clases_tipo_suma(e, ast.clases)
            else:
                enums_puros.append(e)
        ast.enums = enums_puros

    def _generar_clases_tipo_suma(self, enum_nodo, lista_clases):
        nombres_variantes = []
        for m in enum_nodo.valores:
            if m.nombre in nombres_variantes:
                self.error_manager.error_poo(
                    'IL-POO-031',
                    f'Valor duplicado "{m.nombre}" en la enumeración "{enum_nodo.nombre}"',
                    enum_nodo.linea, enum_nodo.columna
                )
                continue
            nombres_variantes.append(m.nombre)
            self.enum_de_variante[m.nombre] = enum_nodo.nombre
            self.campos_variante[m.nombre] = [p.nombre for p in m.parametros]

            atributos = [
                AttrDecl('publico', p.tipo, p.nombre, None, False, m.linea, m.columna)
                for p in m.parametros
            ]
            cuerpo_ctor = [
                AssignStmt(
                    MemberLValue(ThisExpr(m.linea, m.columna), p.nombre, m.linea, m.columna),
                    '=', Identifier(p.nombre, m.linea, m.columna), m.linea, m.columna
                )
                for p in m.parametros
            ]
            ctor = ConstructorDecl(
                m.nombre, m.parametros, Bloque(cuerpo_ctor, m.linea, m.columna),
                'publico', m.linea, m.columna
            )
            clase_variante = ClassDecl(
                m.nombre, enum_nodo.nombre, atributos, [], [ctor],
                False, None, m.linea, m.columna
            )
            lista_clases.append(clase_variante)

        self.variantes_enum[enum_nodo.nombre] = nombres_variantes
        clase_base = ClassDecl(
            enum_nodo.nombre, None, [], [], [],
            True, None, enum_nodo.linea, enum_nodo.columna
        )
        lista_clases.append(clase_base)

    # ============================================================
    # Genéricos (Etapa 7 -- sustitución sintáctica, docs/InvenioLang_2.0_POO.md)
    # ============================================================
    #
    # Diseño: NO es un sistema de tipos genérico real (sin inferencia, sin
    # "erasure" al estilo Java) -- es sustitución sintáctica al estilo de
    # cómo C++ expande templates, la opción de menor riesgo dado el sistema
    # de tipos simple de InvenioLang. Antes de CUALQUIER otra validación,
    # cada clase `clase Pila<T> {...}` se reemplaza por una copia
    # ESPECIALIZADA por cada combinación (Clase, tipo_concreto) que el
    # programa realmente usa -- `Pila<entero>` se registra como una clase
    # normal más, con `T` sustituido por `entero` en todo el cuerpo. El
    # resto del compilador (este mismo analizador, type_checker.py,
    # interpreter.py) NUNCA ve una clase genérica sin especializar; no
    # necesitan saber que los genéricos existen.
    #
    # Alcance deliberadamente acotado (ver docs/InvenioLang_2.0_POO.md):
    # un solo parámetro de tipo, sin herencia combinada con genéricos, y
    # la sintaxis `Nombre<Arg>` solo es válida en dos posiciones
    # (declaración de variable y `nuevo`) -- NO en atributos, parámetros ni
    # tipos de retorno (dentro del CUERPO de la clase genérica, `T` se usa
    # sin `< >`, como cualquier otro nombre de tipo, así que eso sí
    # funciona sin gramática nueva). Esto excluye genéricos anidados o
    # auto-referenciados (p.ej. un nodo enlazado genérico).
    #
    # Una plantilla genérica que el programa nunca instancia no se valida
    # -- no genera ninguna especialización, así que desaparece del programa
    # sin más (igual que un template de C++ nunca instanciado).

    def _expandir_genericos(self, ast):
        genericas = {c.nombre: c for c in ast.clases if c.parametro_tipo is not None}
        if not genericas:
            return
        usos = set()
        self._recolectar_usos_genericos(ast, genericas, usos)
        especializadas = [self._especializar_clase(genericas[base], arg)
                          for base, arg in sorted(usos)]
        ast.clases = [c for c in ast.clases if c.parametro_tipo is None] + especializadas

    def _recolectar_usos_genericos(self, obj, genericas, usos, vistos=None):
        """Recorre el AST completo (genérico, vía __dict__ -- no hace falta
        enumerar cada tipo de nodo a mano) buscando cadenas de tipo con la
        forma 'Base<Arg>' que correspondan a una clase genérica declarada."""
        if vistos is None:
            vistos = set()
        if isinstance(obj, ASTNode):
            if id(obj) in vistos:
                return
            vistos.add(id(obj))
            for attr in ('tipo', 'nombre_clase', 'tipo_retorno'):
                valor = getattr(obj, attr, None)
                if isinstance(valor, str) and valor.endswith('>') and '<' in valor:
                    base, _, resto = valor.partition('<')
                    if base in genericas:
                        usos.add((base, resto[:-1]))
            for valor in vars(obj).values():
                self._recolectar_usos_genericos(valor, genericas, usos, vistos)
        elif isinstance(obj, list):
            for item in obj:
                self._recolectar_usos_genericos(item, genericas, usos, vistos)

    def _especializar_clase(self, plantilla, arg):
        """Copia profunda de la ClassDecl genérica `plantilla`, con el
        parámetro de tipo sustituido por `arg` en todo el cuerpo. El nombre
        especializado ('Base<arg>') es el nombre INTERNO de la nueva clase
        -- nunca puede colisionar con un identificador real de InvenioLang
        (la sintaxis del lenguaje no admite '<'/'>' en un nombre)."""
        nueva = copy.deepcopy(plantilla)
        nombre_especializado = f'{plantilla.nombre}<{arg}>'
        self._sustituir_parametro_tipo(nueva, plantilla.parametro_tipo, arg)
        nueva.nombre = nombre_especializado
        nueva.parametro_tipo = None
        for ctor in nueva.constructores:
            ctor.nombre = nombre_especializado
        return nueva

    def _sustituir_parametro_tipo(self, obj, param, arg, vistos=None):
        if vistos is None:
            vistos = set()
        if isinstance(obj, ASTNode):
            if id(obj) in vistos:
                return
            vistos.add(id(obj))
            for attr in ('tipo', 'tipo_retorno'):
                if getattr(obj, attr, None) == param:
                    setattr(obj, attr, arg)
            for valor in vars(obj).values():
                self._sustituir_parametro_tipo(valor, param, arg, vistos)
        elif isinstance(obj, list):
            for item in obj:
                self._sustituir_parametro_tipo(item, param, arg, vistos)

    def _visitar_programa(self, nodo):
        """Visita el nodo Programa."""
        # Registrar funciones, procedimientos y clases primero (forward
        # reference entre cualquier combinación de ellos).
        for sub in nodo.subrutinas:
            self._declarar_subrutina(sub)
        for e in nodo.enums:
            self._declarar_enum(e)
        for c in nodo.clases:
            self._declarar_clase(c)

        # Con todos los nombres ya conocidos: validar herencia y que los
        # tipos usados en firmas (parametros, retornos, atributos) sean
        # primitivos o clases realmente declaradas (IL-POO-002/003/016).
        self._validar_herencia()
        self._validar_interfaces()
        self._validar_metodos_abstractos()
        self._validar_tipos_subrutinas(nodo.subrutinas)
        self._validar_tipos_clases(nodo.clases)

        # Declaraciones globales (deben ir antes de visitar cuerpos de funciones)
        for d in nodo.declaraciones_globales:
            self._visitar_declaracion(d)

        for d in nodo.declaraciones_posteriores:
            self._visitar_declaracion(d)

        # Visitar cuerpos de funciones y procedimientos
        for sub in nodo.subrutinas:
            self._visitar_subrutina(sub)

        # Visitar cuerpos de clases (metodos y constructor)
        for c in nodo.clases:
            self._visitar_clase(c)

        # Verificar main
        if nodo.main is None:
            self.error_manager.error_semantico(
                'IL-SEM-020', 'No se encontró la función main en el archivo fuente',
                0, 0
            )
        else:
            self._visitar_main(nodo.main)

    def _declarar_subrutina(self, nodo):
        """Registra una función o procedimiento en la tabla de símbolos."""
        if isinstance(nodo, FunctionDecl):
            ts = TipoSimbolo.FUNCION
            tipo_ret = nodo.tipo_retorno
        elif isinstance(nodo, ProcedureDecl):
            ts = TipoSimbolo.PROCEDIMIENTO
            tipo_ret = 'void'
        else:
            return

        entrada = self._declarar_simbolo(nodo.nombre, ts, tipo_ret, nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        # Guardar tipos de parámetros
        entrada.params = [self._tipo_parametro(p) for p in nodo.parametros]
        if isinstance(nodo, FunctionDecl):
            entrada.tipo_retorno = nodo.tipo_retorno
        else:
            # Se marca en la declaración (no al visitar el cuerpo) para que el
            # dato esté disponible sea cual sea el orden de las subrutinas.
            entrada.retorna_valor = self._retorna_valor(nodo.bloque.elementos)

    def _retorna_valor(self, elems):
        """Indica si un cuerpo contiene algún `return` con expresión.

        Se usa para distinguir IL-SEM-051 de IL-SEM-061 (§10.2, §11.5): una
        subrutina declarada `void` que devuelve un valor y además se invoca
        dentro de una expresión revela que el programador quiso declarar una
        función, no un procedimiento.
        """
        for e in elems:
            if isinstance(e, ReturnStmt):
                if e.expr is not None:
                    return True
            elif isinstance(e, IfStmt):
                if self._retorna_valor(e.bloque_then.elementos):
                    return True
                if e.bloque_else and self._retorna_valor(e.bloque_else.elementos):
                    return True
            elif isinstance(e, (WhileStmt, ForStmt, ForEachStmt)):
                if self._retorna_valor(e.bloque.elementos):
                    return True
        return False

    def _tipo_parametro(self, param):
        """Retorna la representación del tipo de un parámetro."""
        if param.es_matriz:
            return f'{param.tipo}[][]'
        if param.es_arreglo:
            return f'{param.tipo}[]'
        return param.tipo

    # ============================================================
    # POO (InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md)
    # ============================================================

    def _validar_tipo(self, tipo, linea, columna):
        """IL-POO-016: un tipo debe ser primitivo, una clase declarada, o
        un tipo función sintetizado por el parser (Etapa 12.6,
        `funcion(...)->...` -- su forma ya está garantizada válida por la
        gramática misma: cada tipo de parámetro que compone la cadena ya
        pasó por `tipo`/`tipo_retorno_funcion`, no hace falta re-validar)."""
        if tipo in _TIPOS_PRIMITIVOS or self.tabla.es_clase(tipo) or tipo.startswith('funcion('):
            return
        self.error_manager.error_poo(
            'IL-POO-016',
            f'"{tipo}" no es un tipo válido: ni un tipo primitivo ni una '
            f'clase declarada',
            linea, columna
        )

    def _validar_tipos_subrutinas(self, subrutinas):
        for sub in subrutinas:
            if isinstance(sub, FunctionDecl):
                self._validar_tipo(sub.tipo_retorno, sub.linea, sub.columna)
            for p in sub.parametros:
                self._validar_tipo(p.tipo, p.linea, p.columna)

    def _validar_tipos_clases(self, clases):
        for c in clases:
            if self.tabla.clases.get(c.nombre) is None:
                continue  # nombre duplicado, ya reportado (IL-POO-001)
            for attr in c.atributos:
                self._validar_tipo(attr.tipo, attr.linea, attr.columna)
            for met in c.metodos:
                self._validar_tipo(met.tipo_retorno, met.linea, met.columna)
                for p in met.parametros:
                    self._validar_tipo(p.tipo, p.linea, p.columna)
            for ctor in c.constructores:
                for p in ctor.parametros:
                    self._validar_tipo(p.tipo, p.linea, p.columna)

    def _nombre_ocupado_por_atributo(self, info, nombre):
        """Un atributo y un metodo comparten espacio de nombres dentro de
        una clase (más simple de razonar para el estudiante que permitir que
        coexistan, como sí hacen algunos lenguajes de producción)."""
        return nombre in info.atributos or nombre in info.metodos

    def _declarar_enum(self, nodo):
        """Registra una enumeración (Etapa 11): internamente es una
        ClaseInfo con es_enum=True y un atributo estático público por cada
        miembro, de tipo "el propio nombre del enum" -- reutiliza TODO el
        mecanismo de acceso a miembro estático que ya existe para clases
        (NombreEnum.MIEMBRO), sin duplicar código. El valor entero de cada
        miembro (su posición 0, 1, 2, ...) lo asigna interpreter.py al
        inicializar estáticos, igual que ya hace con los estáticos reales."""
        info = self.tabla.declarar_clase(nodo.nombre, None, nodo.linea, nodo.columna)
        if info is None:
            self.error_manager.error_poo(
                'IL-POO-001',
                f'Clase duplicada: "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
            return
        info.es_enum = True

        entrada = self._declarar_simbolo(nodo.nombre, TipoSimbolo.CLASE, nodo.nombre,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)

        # Etapa 12.9 (checkpoint): nodo.valores ahora es list[EnumMiembro],
        # no list[str] (Etapa 11.8). Mientras la Etapa 12.10 no implemente
        # el mecanismo de clases internas para variantes CON carga, este
        # metodo sigue registrando cada miembro -- con o sin carga -- como
        # atributo estatico ordinal, EXACTAMENTE como antes (mismo
        # comportamiento observable para enums puros, que es todo lo que
        # existe hoy en el lenguaje real). El bifurcado real llega en 12.10.
        vistos = set()
        for miembro in nodo.valores:
            nombre = miembro.nombre
            if nombre in vistos:
                self.error_manager.error_poo(
                    'IL-POO-031',
                    f'Valor duplicado "{nombre}" en la enumeración "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )
                continue
            vistos.add(nombre)
            info.atributos[nombre] = MiembroInfo(
                nombre, 'publico', nodo.nombre, nodo.linea, nodo.columna,
                es_estatico=True)

    def _declarar_clase(self, nodo):
        """Registra una clase (encabezado + miembros) en la tabla de
        símbolos. La cadena de herencia NO se valida aquí -- necesita que
        TODAS las clases estén registradas primero (`_validar_herencia`),
        por si el padre se declara más adelante en el archivo."""
        info = self.tabla.declarar_clase(nodo.nombre, nodo.padre, nodo.linea, nodo.columna,
                                         es_abstracta=nodo.es_abstracta,
                                         interfaces=nodo.interfaces,
                                         es_interfaz=nodo.es_interfaz)
        if info is None:
            self.error_manager.error_poo(
                'IL-POO-001',
                f'Clase duplicada: "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
            return

        # También ocupa el espacio de nombres global, para que choque con
        # una variable/función del mismo nombre igual que cualquier otro
        # identificador (IL-SEM-002/IL-SEM-080).
        entrada = self._declarar_simbolo(nodo.nombre, TipoSimbolo.CLASE, nodo.nombre,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)

        if nodo.es_interfaz and nodo.atributos:
            # IL-POO-034 (Etapa 12.3): una interfaz no declara estado de
            # instancia -- mismo criterio que Java/C#/Kotlin (una interfaz
            # es un contrato de comportamiento, no de datos).
            self.error_manager.error_poo(
                'IL-POO-034',
                f'La interfaz "{nodo.nombre}" no puede declarar atributos '
                f'(solo métodos abstractos)',
                nodo.atributos[0].linea, nodo.atributos[0].columna
            )
        if nodo.es_interfaz and nodo.constructores:
            self.error_manager.error_poo(
                'IL-POO-034',
                f'La interfaz "{nodo.nombre}" no puede declarar constructores '
                f'(no es instanciable)',
                nodo.constructores[0].linea, nodo.constructores[0].columna
            )

        for attr in nodo.atributos:
            if self._nombre_ocupado_por_atributo(info, attr.nombre):
                self.error_manager.error_poo(
                    'IL-POO-004',
                    f'Miembro duplicado "{attr.nombre}" en la clase "{nodo.nombre}"',
                    attr.linea, attr.columna
                )
                continue
            info.atributos[attr.nombre] = MiembroInfo(
                attr.nombre, attr.visibilidad, attr.tipo, attr.linea, attr.columna,
                es_estatico=attr.es_estatico)

        for met in nodo.metodos:
            # IL-POO-022: un método abstracto no lleva cuerpo, y viceversa.
            if met.es_abstracto and met.bloque is not None:
                self.error_manager.error_poo(
                    'IL-POO-022',
                    f'El método abstracto "{nodo.nombre}.{met.nombre}" no '
                    f'debe tener cuerpo',
                    met.linea, met.columna
                )
            elif not met.es_abstracto and met.bloque is None:
                self.error_manager.error_poo(
                    'IL-POO-022',
                    f'El método "{nodo.nombre}.{met.nombre}" debe tener '
                    f'cuerpo (no está marcado abstracto)',
                    met.linea, met.columna
                )
            # IL-POO-024: un método abstracto solo tiene sentido en una
            # clase que también lo es (si no, nunca podría instanciarse
            # nada que lo deje sin implementar -- ver IL-POO-020/021).
            if met.es_abstracto and not nodo.es_abstracta:
                self.error_manager.error_poo(
                    'IL-POO-024',
                    f'El método abstracto "{nodo.nombre}.{met.nombre}" solo '
                    f'puede declararse en una clase abstracta',
                    met.linea, met.columna
                )
            # IL-POO-034 (Etapa 12.3): una interfaz solo declara metodos
            # abstractos -- uno con cuerpo ya se rechaza como error de
            # sintaxis mas arriba (IL-POO-022 exige bloque=None si es
            # abstracto), pero uno declarado SIN 'abstracto' tambien es
            # invalido dentro de 'interfaz X {...}'.
            if nodo.es_interfaz and not met.es_abstracto:
                self.error_manager.error_poo(
                    'IL-POO-034',
                    f'La interfaz "{nodo.nombre}.{met.nombre}" debe ser '
                    f'abstracta (una interfaz no declara métodos con cuerpo)',
                    met.linea, met.columna
                )

            if met.nombre in info.atributos:
                # IL-POO-004: un método no puede compartir nombre con un
                # atributo, con o sin sobrecarga.
                self.error_manager.error_poo(
                    'IL-POO-004',
                    f'Miembro duplicado "{met.nombre}" en la clase "{nodo.nombre}"',
                    met.linea, met.columna
                )
                continue
            params_tipos = [self._tipo_parametro(p) for p in met.parametros]
            sobrecargas = info.metodos.setdefault(met.nombre, [])
            if any(m.params_tipos == params_tipos for m in sobrecargas):
                # IL-POO-004: sobrecarga con la MISMA firma exacta ya
                # existente -- eso no es sobrecarga, es un duplicado.
                self.error_manager.error_poo(
                    'IL-POO-004',
                    f'"{nodo.nombre}.{met.nombre}({", ".join(params_tipos)})" '
                    f'ya está declarado en esta clase',
                    met.linea, met.columna
                )
                continue
            sobrecargas.append(MetodoInfo(
                met.nombre, met.visibilidad, met.tipo_retorno, params_tipos,
                met.linea, met.columna,
                es_estatico=met.es_estatico, es_abstracto=met.es_abstracto))

        # Etapa 10: sobrecarga de constructores -- mismo criterio que la
        # sobrecarga de métodos de arriba (IL-POO-019 en vez de IL-POO-004,
        # para que el diagnóstico apunte al vocabulario de "constructor").
        for ctor in nodo.constructores:
            params_tipos = [self._tipo_parametro(p) for p in ctor.parametros]
            if any(c.params_tipos == params_tipos for c in info.constructores):
                self.error_manager.error_poo(
                    'IL-POO-019',
                    f'"{nodo.nombre}({", ".join(params_tipos)})" ya está '
                    f'declarado como constructor de esta clase',
                    ctor.linea, ctor.columna
                )
                continue
            info.constructores.append(MetodoInfo(
                nodo.nombre, ctor.visibilidad, nodo.nombre, params_tipos,
                ctor.linea, ctor.columna))

    def _detectar_ciclo(self, nombre):
        """Camina la cadena de padres desde `nombre`. Retorna la lista del
        ciclo si lo hay, o None si la cadena termina (en la raíz o en un
        padre inexistente, que no es un ciclo y se reporta aparte)."""
        camino = []
        actual = nombre
        while actual is not None:
            if actual in camino:
                return camino
            camino.append(actual)
            info = self.tabla.clases.get(actual)
            if info is None:
                return None
            actual = info.padre
        return None

    def _validar_herencia(self):
        """IL-POO-002 (padre inexistente) e IL-POO-003 (herencia circular)."""
        for nombre, info in self.tabla.clases.items():
            if info.padre is not None and info.padre not in self.tabla.clases:
                self.error_manager.error_poo(
                    'IL-POO-002',
                    f'La clase "{nombre}" hereda de "{info.padre}", que no '
                    f'es una clase declarada',
                    info.linea, info.columna
                )

        reportadas = set()
        for nombre, info in self.tabla.clases.items():
            if nombre in reportadas:
                continue
            ciclo = self._detectar_ciclo(nombre)
            if ciclo:
                reportadas.update(ciclo)
                self.error_manager.error_poo(
                    'IL-POO-003',
                    'Herencia circular detectada: '
                    f'{" -> ".join(ciclo + [ciclo[0]])}',
                    info.linea, info.columna
                )

    def _validar_interfaces(self):
        """IL-POO-002 (reutilizado: implementa algo no declarado) e
        IL-POO-033 (implementa algo que no es abstracto/interfaz -- Etapa
        12.3). `implementa` es una lista, a diferencia de `hereda`
        (siempre singular) -- por eso no se apoya en `_detectar_ciclo` ni
        en `cadena_ancestros`, que asumen un solo padre."""
        for nombre, info in self.tabla.clases.items():
            for interfaz in info.interfaces:
                destino = self.tabla.clases.get(interfaz)
                if destino is None:
                    self.error_manager.error_poo(
                        'IL-POO-002',
                        f'La clase "{nombre}" implementa "{interfaz}", que no '
                        f'es una clase/interfaz declarada',
                        info.linea, info.columna
                    )
                elif not destino.es_abstracta:
                    self.error_manager.error_poo(
                        'IL-POO-033',
                        f'La clase "{nombre}" implementa "{interfaz}", que no '
                        f'es una interfaz ni una clase abstracta',
                        info.linea, info.columna
                    )

    def _validar_metodos_abstractos(self):
        """IL-POO-021: una clase NO abstracta debe implementar (con cuerpo)
        todo método abstracto heredado (por `hereda`) O exigido por una
        interfaz (`implementa`, Etapa 12.3) -- si no, sigue siendo
        efectivamente abstracta y `nuevo` sobre ella dejaría un método sin
        cuerpo por ejecutar. Recorre cada jerarquía de la raíz hacia el más
        derivado: una implementación concreta "cierra" un pendiente
        declarado por un ancestro más básico o por una interfaz; una
        re-declaración abstracta lo reabre (caso raro pero correcto)."""
        for nombre, info in self.tabla.clases.items():
            if info.es_abstracta:
                continue  # una clase abstracta puede dejar métodos sin implementar
            cadena = self.tabla.cadena_ancestros(nombre)
            if cadena is None:
                continue  # herencia inválida, ya reportado (IL-POO-002/003)
            pendientes = {}  # (nombre, firma) -> MetodoInfo mas reciente
            # Interfaces (Etapa 12.3): sus metodos son TODOS abstractos por
            # construccion (interfaz X {...} solo admite metodos abstractos,
            # ver _validar_interfaz_solo_abstracta), asi que cualquiera de
            # ellos que la cadena de ancestros no implemente con cuerpo
            # queda pendiente igual que uno heredado por `hereda`.
            for interfaz in info.interfaces:
                i_info = self.tabla.clases.get(interfaz)
                if i_info is None:
                    continue  # interfaz inexistente, ya reportado (IL-POO-002)
                for m_nombre, sobrecargas in i_info.metodos.items():
                    for m in sobrecargas:
                        pendientes[(m_nombre, tuple(m.params_tipos))] = m
            for clase in reversed(cadena):  # de la raiz al mas derivado
                c_info = self.tabla.clases[clase]
                for m_nombre, sobrecargas in c_info.metodos.items():
                    for m in sobrecargas:
                        clave = (m_nombre, tuple(m.params_tipos))
                        if m.es_abstracto:
                            pendientes[clave] = m
                        else:
                            pendientes.pop(clave, None)
            for (m_nombre, params), m in pendientes.items():
                firma = ', '.join(params)
                self.error_manager.error_poo(
                    'IL-POO-021',
                    f'La clase "{nombre}" no es abstracta pero no implementa '
                    f'el método abstracto "{m_nombre}({firma})" heredado',
                    info.linea, info.columna
                )

    def _visitar_clase(self, nodo):
        """Visita el cuerpo (constructor + métodos) de una clase ya
        registrada. Los inicializadores de atributo se visitan SIN
        `clase_actual` activo: no tienen acceso a `este`/this ni a otros
        atributos (se evalúan antes de que exista la instancia)."""
        info = self.tabla.clases.get(nodo.nombre)
        if info is None:
            return  # nombre duplicado, ya reportado; no hay info fiable

        for attr in nodo.atributos:
            if attr.init_expr is not None:
                self._visitar_expresion(attr.init_expr)

        self.clase_actual = nodo.nombre
        if nodo.constructores:
            for ctor in nodo.constructores:
                self._visitar_constructor(nodo, ctor)
        elif info.padre is not None:
            # Constructor implícito (0 parámetros): igual necesita que la
            # cadena de herencia tenga un constructor de 0 argumentos.
            self._validar_super_implicito(nodo, nodo)
        for met in nodo.metodos:
            if met.es_abstracto:
                continue  # sin cuerpo que visitar (Etapa 7)
            self._visitar_metodo(nodo, met)
        self.clase_actual = None

    def _visitar_constructor(self, clase_nodo, nodo):
        self.tabla.entrar_ambito()
        self.funcion_actual = f'{clase_nodo.nombre}.{nodo.nombre}'
        self.tipo_retorno_actual = 'void'
        self.en_funcion = False
        self.en_procedimiento = False
        self.en_constructor = True
        self.tiene_return = False

        for p in nodo.parametros:
            self._declarar_parametro(p)

        elementos = nodo.bloque.elementos
        if elementos and isinstance(elementos[0], SuperCallStmt):
            self._visitar_super_call_stmt(elementos[0], es_primera=True)
            resto = elementos[1:]
        else:
            self._validar_super_implicito(clase_nodo, nodo)
            resto = elementos
        for elem in resto:
            self._visitar_elemento_bloque(elem)

        self.en_constructor = False
        self.funcion_actual = None
        self.tabla.salir_ambito()

    def _visitar_metodo(self, clase_nodo, nodo):
        self.tabla.entrar_ambito()
        self.funcion_actual = f'{clase_nodo.nombre}.{nodo.nombre}'
        self.tipo_retorno_actual = nodo.tipo_retorno
        self.en_funcion = nodo.tipo_retorno != 'void'
        self.en_procedimiento = nodo.tipo_retorno == 'void'
        self.en_constructor = False
        self.en_metodo_estatico = nodo.es_estatico
        self.tiene_return = False

        for p in nodo.parametros:
            self._declarar_parametro(p)

        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        # Reutiliza IL-SEM-050 (§10.4 de la v1.0): el requisito de que toda
        # ruta de ejecución alcance un return es el mismo para un método que
        # para una función; no hace falta un código IL-POO paralelo.
        if nodo.tipo_retorno != 'void' and not self._siempre_retorna(nodo.bloque.elementos):
            self.error_manager.error_semantico(
                'IL-SEM-050',
                f'El método "{clase_nodo.nombre}.{nodo.nombre}" tiene al '
                f'menos una ruta de ejecución que no alcanza ningún return',
                nodo.linea, nodo.columna
            )

        self.tabla.salir_ambito()
        self.funcion_actual = None
        self.en_funcion = False
        self.en_procedimiento = False
        self.en_metodo_estatico = False

    def _validar_super_implicito(self, clase_nodo, nodo_ref):
        """Si el constructor (explícito o implícito) no llama a padre(...),
        y la clase tiene padre, se necesita que el padre tenga un
        constructor de 0 argumentos -- ya sea el implícito (si no declara
        ninguno) o una sobrecarga explícita de 0 parámetros (Etapa 10:
        sobrecarga de constructores) -- si no, IL-POO-007."""
        info = self.tabla.clases.get(clase_nodo.nombre)
        if info is None or info.padre is None:
            return
        padre_info = self.tabla.clases.get(info.padre)
        if padre_info is None:
            return  # padre inexistente, ya reportado (IL-POO-002)
        ctor_cero = next((c for c in padre_info.constructores
                          if len(c.params_tipos) == 0), None)
        if padre_info.constructores and ctor_cero is None:
            self.error_manager.error_poo(
                'IL-POO-007',
                f'La clase "{clase_nodo.nombre}" no llama a padre(...) '
                f'explícitamente, pero "{info.padre}" no declara ningún '
                f'constructor de 0 argumentos',
                nodo_ref.linea, nodo_ref.columna
            )
        elif ctor_cero is not None and ctor_cero.visibilidad == 'privado':
            # Etapa 11: el constructor implícito de 0 argumentos del padre
            # existe pero es privado -- tampoco se puede invocar
            # implícitamente desde una subclase (IL-POO-030).
            self.error_manager.error_poo(
                'IL-POO-030',
                f'La clase "{clase_nodo.nombre}" no llama a padre(...) '
                f'explícitamente, pero el constructor de 0 argumentos de '
                f'"{info.padre}" es privado',
                nodo_ref.linea, nodo_ref.columna
            )

    def _visitar_super_call_stmt(self, nodo, es_primera):
        """Valida un padre(...)/super(...). `es_primera` indica si el
        llamador ya confirmó que es la primera instrucción de un
        constructor -- si no, siempre es un uso inválido (IL-POO-009)."""
        if not (self.en_constructor and es_primera):
            self.error_manager.error_poo(
                'IL-POO-009',
                'padre(...) (super) solo puede usarse como la primera '
                'instrucción de un constructor',
                nodo.linea, nodo.columna
            )
        if self.clase_actual is not None:
            info = self.tabla.clases.get(self.clase_actual)
            if info is not None and info.padre is None:
                self.error_manager.error_poo(
                    'IL-POO-010',
                    f'padre(...) usado en "{self.clase_actual}", que no '
                    f'tiene clase padre',
                    nodo.linea, nodo.columna
                )
            elif info is not None and info.padre is not None:
                padre_info = self.tabla.clases.get(info.padre)
                if padre_info is not None:
                    # Etapa 10 (sobrecarga de constructores): con 0 o 1
                    # constructor declarado en el padre, la aridad se valida
                    # aquí (mismo mensaje de siempre). Con varias sobrecargas,
                    # cuál aplica depende de los TIPOS de los argumentos --
                    # esa decisión (y su diagnóstico, IL-POO-029) es de
                    # type_checker.py, igual que ya pasa con los métodos.
                    candidatos = padre_info.constructores
                    if len(candidatos) <= 1:
                        esperados = candidatos[0].params_tipos if candidatos else []
                        if len(esperados) != len(nodo.argumentos):
                            self.error_manager.error_poo(
                                'IL-POO-007',
                                f'padre(...): "{info.padre}" espera '
                                f'{len(esperados)} argumento(s), se pasaron '
                                f'{len(nodo.argumentos)}',
                                nodo.linea, nodo.columna
                            )
        for a in nodo.argumentos:
            self._visitar_expresion(a)

    def _visitar_receptor(self, receptor):
        """Visita el receptor de un acceso a miembro (este/padre/IDENT) y
        retorna el nombre de la clase estática que representa, o None si no
        se pudo resolver (ya se reportó el error correspondiente).

        Los receptores están acotados por gramática a estas tres formas
        (§2 de la spec de POO: sin encadenar), así que no hace falta el
        motor general de tipos de type_checker.py para resolverlos."""
        if isinstance(receptor, ThisExpr):
            if self.clase_actual is None:
                self.error_manager.error_poo(
                    'IL-POO-011',
                    'este/this solo puede usarse dentro de un método o '
                    'constructor',
                    receptor.linea, receptor.columna
                )
                return None
            if self.en_metodo_estatico:
                # IL-POO-025 (Etapa 7): un método estático no tiene instancia.
                self.error_manager.error_poo(
                    'IL-POO-025',
                    'este/this no puede usarse dentro de un método estático',
                    receptor.linea, receptor.columna
                )
                return None
            return self.clase_actual
        if isinstance(receptor, SuperExpr):
            if self.clase_actual is None:
                self.error_manager.error_poo(
                    'IL-POO-011',
                    'padre/super solo puede usarse dentro de un método o '
                    'constructor',
                    receptor.linea, receptor.columna
                )
                return None
            if self.en_metodo_estatico:
                self.error_manager.error_poo(
                    'IL-POO-025',
                    'padre/super no puede usarse dentro de un método estático',
                    receptor.linea, receptor.columna
                )
                return None
            info = self.tabla.clases.get(self.clase_actual)
            if info is None or info.padre is None:
                self.error_manager.error_poo(
                    'IL-POO-012',
                    f'padre/super usado en "{self.clase_actual}", que no '
                    f'tiene clase padre',
                    receptor.linea, receptor.columna
                )
                return None
            return info.padre
        if isinstance(receptor, Identifier):
            entrada = self.tabla.buscar(receptor.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Identificador no declarado: "{receptor.nombre}"',
                    receptor.linea, receptor.columna
                )
                return None
            if not self.tabla.es_clase(entrada.tipo_dato):
                self.error_manager.error_poo(
                    'IL-POO-006',
                    f'"{receptor.nombre}" no es una instancia de una clase; '
                    f'no tiene miembros',
                    receptor.linea, receptor.columna
                )
                return None
            return entrada.tipo_dato
        if isinstance(receptor, ArrayAccess):
            # Elemento de arreglo de objetos (Estructuras de Datos):
            # `_visitar_expresion` ya sabe validar un ArrayAccess (declarado,
            # tipo de indice, limites); se reutiliza en vez de duplicar esa
            # logica aqui.
            self._visitar_expresion(receptor)
            entrada = self.tabla.buscar(receptor.nombre)
            if entrada is None:
                return None
            if not self.tabla.es_clase(entrada.tipo_dato):
                self.error_manager.error_poo(
                    'IL-POO-006',
                    f'"{receptor.nombre}" no es un arreglo de objetos; sus '
                    f'elementos no tienen miembros',
                    receptor.linea, receptor.columna
                )
                return None
            return entrada.tipo_dato
        return None

    def _receptor_es_estatico(self, receptor):
        """True si el receptor es el NOMBRE de una clase (acceso estático,
        Etapa 7: NombreClase.miembro), no una variable/instancia. Solo un
        IDENTIFICADOR puede serlo -- este/padre/elemento de arreglo nunca
        lo son (siempre representan una instancia)."""
        if not isinstance(receptor, Identifier):
            return False
        entrada = self.tabla.buscar(receptor.nombre)
        return entrada is not None and entrada.tipo_simbolo == TipoSimbolo.CLASE

    def _resolver_miembro(self, tipo_clase, nombre_miembro, es_metodo, nodo,
                          receptor_estatico=False):
        """Busca `nombre_miembro` en `tipo_clase` y su cadena de ancestros,
        validando existencia (IL-POO-006), visibilidad (IL-POO-005) y,
        cuando el receptor es un nombre de clase, que el miembro sea
        estático (IL-POO-026 -- acceder a un miembro de instancia sin una
        instancia no tiene sentido). Al revés SÍ se permite (acceder a un
        miembro estático a través de una instancia es válido, mismo
        criterio permisivo que otros lenguajes). Retorna la MiembroInfo/
        MetodoInfo encontrada, o None."""
        resolver = self.tabla.resolver_metodo if es_metodo else self.tabla.resolver_atributo
        resultado = resolver(tipo_clase, nombre_miembro)
        if resultado is None:
            self.error_manager.error_poo(
                'IL-POO-006',
                f'"{tipo_clase}" no tiene {"el método" if es_metodo else "el atributo"} '
                f'"{nombre_miembro}"',
                nodo.linea, nodo.columna
            )
            return None
        clase_declarante, info = resultado
        if info.visibilidad == 'privado' and self.clase_actual != clase_declarante:
            self.error_manager.error_poo(
                'IL-POO-005',
                f'"{nombre_miembro}" es privado en "{clase_declarante}" y '
                f'no es accesible desde aquí',
                nodo.linea, nodo.columna
            )
            return None
        if receptor_estatico and not info.es_estatico:
            self.error_manager.error_poo(
                'IL-POO-026',
                f'"{nombre_miembro}" no es estático; no se puede acceder a '
                f'través del nombre de la clase "{tipo_clase}", solo de una '
                f'instancia',
                nodo.linea, nodo.columna
            )
            return None
        return info

    def _visitar_llamada_metodo(self, receptor, nombre_metodo, argumentos, nodo):
        tipo_clase = self._visitar_receptor(receptor)
        if tipo_clase is not None:
            info = self._resolver_miembro(tipo_clase, nombre_metodo, True, nodo,
                                          receptor_estatico=self._receptor_es_estatico(receptor))
            if info is not None:
                # Etapa 7 (sobrecarga): con una sola firma declarada, la
                # aridad se valida aquí (mismo mensaje de siempre). Con
                # varias sobrecargas, cuál aplica depende de los TIPOS de
                # los argumentos, no solo la cantidad -- esa decisión más
                # fina (y su diagnóstico, IL-POO-027) es de type_checker.py.
                todos = self.tabla.resolver_metodo_todos(tipo_clase, nombre_metodo)
                candidatos = todos[1] if todos is not None else [info]
                if len(candidatos) == 1:
                    num_params, num_args = len(info.params_tipos), len(argumentos)
                    if num_params != num_args:
                        self.error_manager.error_poo(
                            'IL-POO-017',
                            f'Llamada a "{nombre_metodo}": esperados '
                            f'{num_params} argumentos, recibidos {num_args}',
                            nodo.linea, nodo.columna
                        )
        for a in argumentos:
            self._visitar_expresion(a)

    def _visitar_new(self, nodo):
        if not self.tabla.es_clase(nodo.nombre_clase):
            self.error_manager.error_poo(
                'IL-POO-016',
                f'"{nodo.nombre_clase}" no es una clase declarada',
                nodo.linea, nodo.columna
            )
        else:
            info = self.tabla.clases[nodo.nombre_clase]
            if info.es_abstracta:
                # IL-POO-020: una clase abstracta no es instanciable.
                self.error_manager.error_poo(
                    'IL-POO-020',
                    f'No se puede instanciar la clase abstracta '
                    f'"{nodo.nombre_clase}" con nuevo/new',
                    nodo.linea, nodo.columna
                )
            elif info.es_enum:
                # IL-POO-032 (Etapa 11): una enumeración no es un tipo
                # instanciable -- se usa por sus miembros (Enum.MIEMBRO).
                self.error_manager.error_poo(
                    'IL-POO-032',
                    f'"{nodo.nombre_clase}" es una enumeración: no se puede '
                    f'instanciar con nuevo/new, use "{nodo.nombre_clase}.'
                    f'MIEMBRO"',
                    nodo.linea, nodo.columna
                )
                return
            # Etapa 10 (sobrecarga de constructores): mismo criterio que
            # _visitar_llamada_metodo -- con 0 o 1 constructor declarado la
            # aridad se valida aquí; con varias sobrecargas, la resolución
            # por tipos es de type_checker.py (IL-POO-029).
            candidatos = self.tabla.resolver_constructor_todos(nodo.nombre_clase)
            if len(candidatos) <= 1:
                esperados = candidatos[0].params_tipos if candidatos else []
                if len(esperados) != len(nodo.argumentos):
                    self.error_manager.error_poo(
                        'IL-POO-007',
                        f'nuevo {nodo.nombre_clase}(...): esperados '
                        f'{len(esperados)} argumento(s), recibidos '
                        f'{len(nodo.argumentos)}',
                        nodo.linea, nodo.columna
                    )
        for a in nodo.argumentos:
            self._visitar_expresion(a)

    def _declarar_simbolo(self, nombre, tipo_simbolo, tipo_dato, linea, columna):
        """Declara un símbolo y emite IL-WARN-001 cuando oculta uno externo
        (§3.5.3, §14.16). Retorna la entrada o None si ya existe (duplicado)."""
        # Los nombres de funciones integradas están reservados en TODO ámbito,
        # no sólo en el global (§19.1). Se rechaza aquí y el reporte lo emite
        # `_manejar_duplicado`, que ya distingue IL-SEM-080 de IL-SEM-002.
        if nombre in FUNCIONES_BUILT_IN:
            return None
        entrada = self.tabla.declarar(nombre, tipo_simbolo, tipo_dato, linea, columna)
        if entrada is None:
            return None
        if self.tabla.profundidad_ambito() > 1 and self.tabla.hay_externo(nombre):
            self.error_manager.advertencia(
                'IL-WARN-001',
                f'"{nombre}" oculta un identificador externo del mismo nombre',
                linea, columna
            )
        return entrada

    def _manejar_duplicado(self, nombre, linea, columna):
        """Reporta un identificador duplicado. Si el nombre es de una función
        integrada, se emite IL-SEM-080 (§19.11); en caso contrario IL-SEM-002."""
        if nombre in FUNCIONES_BUILT_IN:
            self.error_manager.error_semantico(
                'IL-SEM-080',
                f'El nombre "{nombre}" está reservado por una función integrada',
                linea, columna
            )
        else:
            self.error_manager.error_semantico(
                'IL-SEM-002',
                f'Identificador duplicado: "{nombre}"',
                linea, columna
            )

    def _es_expr_constante(self, expr):
        """Indica si una expresión es constante (literales, constantes y
        operaciones sobre ellas). Se usa para IL-SEM-032 (§5.3)."""
        if isinstance(expr, Literal):
            return True
        if isinstance(expr, Identifier):
            e = self.tabla.buscar(expr.nombre)
            return e is not None and e.tipo_simbolo == TipoSimbolo.CONSTANTE
        if isinstance(expr, BinaryOp):
            return self._es_expr_constante(expr.izquierda) and self._es_expr_constante(expr.derecha)
        if isinstance(expr, UnaryOp):
            return self._es_expr_constante(expr.operando)
        return False

    def _es_true_constante(self, expr):
        """Indica si una expresión es constantemente verdadera (§9.1.3).

        Se usa para IL-WARN-010. Comprueba el VALOR de la constante, no sólo
        que sea de tipo bool: `const bool SALIR = false;` no debe advertir.
        """
        if isinstance(expr, Literal) and expr.tipo_literal == 'bool' and expr.valor is True:
            return True
        if isinstance(expr, Identifier):
            e = self.tabla.buscar(expr.nombre)
            if e is None or e.tipo_simbolo != TipoSimbolo.CONSTANTE:
                return False
            if e.tipo_dato != 'bool':
                return False
            return getattr(e, 'valor_constante', None) is True
        return False

    def _siempre_retorna(self, elems):
        """Indica si una lista de instrucciones retorna por todas sus rutas.

        Implementa IL-SEM-050 (§10.4): una función es correcta sólo si toda
        ruta de ejecución alcanza un `return`. Reglas:
          - `return` cierra la ruta.
          - un `if` la cierra sólo si tiene `else` Y ambas ramas la cierran.
          - un ciclo NO la cierra: su cuerpo puede no ejecutarse nunca.
        """
        for e in elems:
            if isinstance(e, ReturnStmt):
                return True
            if isinstance(e, IfStmt):
                if e.bloque_else is None:
                    continue
                if (self._siempre_retorna(e.bloque_then.elementos)
                        and self._siempre_retorna(e.bloque_else.elementos)):
                    return True
        return False

    def _bloque_tiene_break(self, elems):
        """Indica si existe una instrucción break alcanzable en una lista de
        elementos (recorre if/while/for para detectar break anidados)."""
        for e in elems:
            if isinstance(e, BreakStmt):
                return True
            if isinstance(e, IfStmt):
                if self._bloque_tiene_break(e.bloque_then.elementos):
                    return True
                if e.bloque_else and self._bloque_tiene_break(e.bloque_else.elementos):
                    return True
            if isinstance(e, WhileStmt) and self._bloque_tiene_break(e.bloque.elementos):
                return True
            if isinstance(e, ForStmt) and self._bloque_tiene_break(e.bloque.elementos):
                return True
            if isinstance(e, ForEachStmt) and self._bloque_tiene_break(e.bloque.elementos):
                return True
        return False

    def _visitar_main(self, nodo):
        """Verifica la función main y visita su bloque."""
        # main debe ser void (es garantizado por la gramática)
        if not self.tabla.buscar_funcion('main'):
            entrada = self._declarar_simbolo('main', TipoSimbolo.FUNCION, 'void',
                                             nodo.linea, nodo.columna)
            if entrada:
                entrada.params = []

        self.tabla.entrar_ambito()
        self.funcion_actual = 'main'
        self.tipo_retorno_actual = 'void'
        self.en_funcion = False
        # main no es un procedimiento: un return con valor en su interior es
        # IL-SEM-023, no IL-SEM-061 (§3.2).
        self.en_procedimiento = False
        self.en_main = True
        self.tiene_return = False

        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        self.tabla.salir_ambito()
        self.funcion_actual = None
        self.en_main = False

    def _visitar_subrutina(self, nodo):
        """Visita una subrutina registrada."""
        if isinstance(nodo, FunctionDecl):
            self._visitar_funcion(nodo)
        elif isinstance(nodo, ProcedureDecl):
            self._visitar_procedimiento(nodo)

    def _visitar_funcion(self, nodo):
        """Visita una función."""
        entrada = self.tabla.buscar_funcion(nodo.nombre)
        if entrada and entrada.params:
            # Verificar que los parámetros tengan longitud correcta
            pass

        self.tabla.entrar_ambito()
        self.funcion_actual = nodo.nombre
        self.tipo_retorno_actual = nodo.tipo_retorno
        self.en_funcion = True
        self.en_procedimiento = False
        self.tiene_return = False

        # Declarar parámetros
        for p in nodo.parametros:
            self._declarar_parametro(p)

        # Visitar cuerpo
        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        # IL-SEM-050: toda ruta de ejecución debe alcanzar un return (§10.4)
        if nodo.tipo_retorno != 'void' and not self._siempre_retorna(nodo.bloque.elementos):
            self.error_manager.error_semantico(
                'IL-SEM-050',
                f'La función "{nodo.nombre}" tiene al menos una ruta de '
                f'ejecución que no alcanza ningún return',
                nodo.linea, nodo.columna
            )

        self.tabla.salir_ambito()
        self.funcion_actual = None
        self.en_funcion = False

    def _visitar_procedimiento(self, nodo):
        """Analiza el cuerpo de un procedimiento."""
        self.tabla.entrar_ambito()
        self.funcion_actual = nodo.nombre
        self.tipo_retorno_actual = 'void'
        self.en_funcion = False
        self.en_procedimiento = True
        self.tiene_return = False

        for p in nodo.parametros:
            self._declarar_parametro(p)

        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        self.tabla.salir_ambito()
        self.funcion_actual = None
        self.en_procedimiento = False

    def _declarar_parametro(self, param):
        """Declara un parámetro en la tabla de símbolos."""
        if param.tipo == 'void':
            self.error_manager.error_tipo(
                'IL-TIPO-015',
                f'Parámetro "{param.nombre}" no puede ser de tipo void',
                param.linea, param.columna
            )
        if param.es_matriz:
            ts = TipoSimbolo.PARAM_MATRIZ
        elif param.es_arreglo:
            ts = TipoSimbolo.PARAM_ARREGLO
        else:
            ts = TipoSimbolo.PARAMETRO

        entrada = self._declarar_simbolo(param.nombre, ts, param.tipo,
                                         param.linea, param.columna)
        if entrada is None:
            self._manejar_duplicado(param.nombre, param.linea, param.columna)
        else:
            entrada.inicializado = True  # Los parámetros están siempre inicializados
            if param.es_matriz:
                entrada.es_parametro_matriz = True
            elif param.es_arreglo:
                entrada.es_parametro_arreglo = True

    def _visitar_elemento_bloque(self, elem):
        """Visita un elemento de bloque (declaración o instrucción)."""
        if isinstance(elem, (VarDecl, ConstDecl, ArrayDecl, MatrixDecl)):
            self._visitar_declaracion(elem)
        elif isinstance(elem, FunctionDecl):
            # Función declarada localmente - error sintáctico/semántico
            self.error_manager.error_sintactico(
                'IL-SIN-050',
                'No se permite declarar funciones dentro de bloques locales',
                elem.linea, elem.columna
            )
        else:
            self._visitar_instruccion(elem)

    def _visitar_declaracion(self, nodo):
        """Visita una declaración y la registra en la tabla de símbolos."""
        if isinstance(nodo, VarDecl):
            self._visitar_var_decl(nodo)
        elif isinstance(nodo, ConstDecl):
            self._visitar_const_decl(nodo)
        elif isinstance(nodo, ArrayDecl):
            self._visitar_array_decl(nodo)
        elif isinstance(nodo, MatrixDecl):
            self._visitar_matrix_decl(nodo)

    def _visitar_var_decl(self, nodo):
        """Declara una variable."""
        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-TIPO-015',
                f'Variable "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )
        else:
            self._validar_tipo(nodo.tipo, nodo.linea, nodo.columna)
        ts = TipoSimbolo.VARIABLE
        entrada = self._declarar_simbolo(nodo.nombre, ts, nodo.tipo,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        if not entrada:
            return
        if nodo.init_expr is not None:
            entrada.inicializado = True
            # Verificar autorreferencia
            self._verificar_autoref(nodo.nombre, nodo.init_expr)
            self._visitar_expresion(nodo.init_expr)
        # Sin inicializador no se advierte aquí: IL-WARN-002 se emite en el
        # punto de LECTURA, si es que la variable llega a leerse sin asignar
        # (§5.2.2). Las globales sí reciben valor por defecto (§5.2.3).

    def _verificar_autoref(self, nombre, expr):
        """Verifica IL-SEM-004: autorreferencia en inicialización (§5.1.3).

        Recorre la expresión completa, no sólo su raíz: `int x = x + 1;` es
        tan autorreferente como `int x = x;`.
        """
        if expr is None:
            return
        if isinstance(expr, Identifier) and expr.nombre == nombre:
            self.error_manager.error_semantico(
                'IL-SEM-004',
                f'Autorreferencia en inicialización de "{nombre}"',
                expr.linea, expr.columna
            )
            return
        if isinstance(expr, BinaryOp):
            self._verificar_autoref(nombre, expr.izquierda)
            self._verificar_autoref(nombre, expr.derecha)
        elif isinstance(expr, UnaryOp):
            self._verificar_autoref(nombre, expr.operando)
        elif isinstance(expr, FunctionCall):
            for a in expr.argumentos:
                self._verificar_autoref(nombre, a)
        elif isinstance(expr, ArrayAccess):
            if expr.nombre == nombre:
                self.error_manager.error_semantico(
                    'IL-SEM-004',
                    f'Autorreferencia en inicialización de "{nombre}"',
                    expr.linea, expr.columna
                )
                return
            self._verificar_autoref(nombre, expr.indice)
        elif isinstance(expr, MatrixAccess):
            if expr.nombre == nombre:
                self.error_manager.error_semantico(
                    'IL-SEM-004',
                    f'Autorreferencia en inicialización de "{nombre}"',
                    expr.linea, expr.columna
                )
                return
            self._verificar_autoref(nombre, expr.fila)
            self._verificar_autoref(nombre, expr.columna)

    def _visitar_const_decl(self, nodo):
        """Declara una constante."""
        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-TIPO-015',
                f'Constante "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )
        ts = TipoSimbolo.CONSTANTE
        entrada = self._declarar_simbolo(nodo.nombre, ts, nodo.tipo,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        entrada.inicializado = True
        # Recordar el valor si es un literal, para IL-WARN-010 (§9.1.3)
        if isinstance(nodo.init_expr, Literal):
            entrada.valor_constante = nodo.init_expr.valor
        # IL-SEM-032: la inicialización de una constante debe ser constante
        if not self._es_expr_constante(nodo.init_expr):
            self.error_manager.error_semantico(
                'IL-SEM-032',
                f'La constante "{nodo.nombre}" debe inicializarse con una '
                f'expresión constante',
                nodo.init_expr.linea, nodo.init_expr.columna
            )
        self._visitar_expresion(nodo.init_expr)

    def _visitar_array_decl(self, nodo):
        """Declara un arreglo."""
        ts = TipoSimbolo.ARREGLO
        entrada = self._declarar_simbolo(nodo.nombre, ts, nodo.tipo,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return
        # Etapa 11: arreglo constante -- sigue siendo TipoSimbolo.ARREGLO
        # (necesita toda la mecanica de indices/limites de un arreglo
        # normal), pero marcado aparte para que _visitar_asignacion
        # rechace reasignar cualquiera de sus elementos (IL-SEM-031).
        entrada.es_constante = nodo.es_constante

        # Verificar tamaño
        if isinstance(nodo.tam, int):
            if nodo.tam <= 0:
                self.error_manager.error_semantico(
                    'IL-SEM-071',
                    f'Dimensión de arreglo "{nodo.nombre}" debe ser positiva',
                    nodo.linea, nodo.columna
                )
            else:
                entrada.tam_arreglo = nodo.tam
        else:
            # IDENTIFICADOR - debe ser una constante
            const_entry = self.tabla.buscar(nodo.tam)
            if const_entry and const_entry.tipo_simbolo == TipoSimbolo.CONSTANTE:
                entrada.tam_arreglo = nodo.tam  # Guardar nombre de la constante
            else:
                self.error_manager.error_semantico(
                    'IL-SEM-070',
                    f'Dimensión de arreglo "{nodo.nombre}" debe ser una constante',
                    nodo.linea, nodo.columna
                )

        # Verificar void como tipo base (IL-SEM-072, §12/§14)
        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-SEM-072',
                f'Arreglo "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )
        else:
            self._validar_tipo(nodo.tipo, nodo.linea, nodo.columna)

        if nodo.init_exprs:
            entrada.inicializado = True
            for e in nodo.init_exprs:
                self._visitar_expresion(e)
            if isinstance(entrada.tam_arreglo, int) and len(nodo.init_exprs) != entrada.tam_arreglo:
                self.error_manager.error_semantico(
                    'IL-SEM-073',
                    f'Arreglo "{nodo.nombre}" esperaba {entrada.tam_arreglo} elementos, '
                    f'pero se proporcionaron {len(nodo.init_exprs)}',
                    nodo.linea, nodo.columna
                )

    def _visitar_matrix_decl(self, nodo):
        """Declara una matriz."""
        ts = TipoSimbolo.MATRIZ
        entrada = self._declarar_simbolo(nodo.nombre, ts, nodo.tipo,
                                         nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
            return

        if isinstance(nodo.filas, int):
            if nodo.filas <= 0:
                self.error_manager.error_semantico(
                    'IL-SEM-071',
                    f'Dimensión de matriz "{nodo.nombre}" debe ser positiva',
                    nodo.linea, nodo.columna
                )
            else:
                entrada.filas_matriz = nodo.filas
        else:
            const_entry = self.tabla.buscar(nodo.filas)
            if const_entry and const_entry.tipo_simbolo == TipoSimbolo.CONSTANTE:
                entrada.filas_matriz = nodo.filas
            else:
                self.error_manager.error_semantico(
                    'IL-SEM-070',
                    f'Dimensión de matriz "{nodo.nombre}" debe ser una constante',
                    nodo.linea, nodo.columna
                )
        if isinstance(nodo.cols, int):
            if nodo.cols <= 0:
                self.error_manager.error_semantico(
                    'IL-SEM-071',
                    f'Dimensión de matriz "{nodo.nombre}" debe ser positiva',
                    nodo.linea, nodo.columna
                )
            else:
                entrada.cols_matriz = nodo.cols
        else:
            const_entry = self.tabla.buscar(nodo.cols)
            if const_entry and const_entry.tipo_simbolo == TipoSimbolo.CONSTANTE:
                entrada.cols_matriz = nodo.cols
            else:
                self.error_manager.error_semantico(
                    'IL-SEM-070',
                    f'Dimensión de matriz "{nodo.nombre}" debe ser una constante',
                    nodo.linea, nodo.columna
                )

        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-SEM-072',
                f'Matriz "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )

        if nodo.init_filas:
            entrada.inicializado = True
            for fila in nodo.init_filas:
                for e in fila:
                    self._visitar_expresion(e)
            filas_ok = isinstance(entrada.filas_matriz, int)
            cols_ok = isinstance(entrada.cols_matriz, int)
            if filas_ok and len(nodo.init_filas) != entrada.filas_matriz:
                self.error_manager.error_semantico(
                    'IL-SEM-073',
                    f'Matriz "{nodo.nombre}" esperaba {entrada.filas_matriz} filas, '
                    f'pero se proporcionaron {len(nodo.init_filas)}',
                    nodo.linea, nodo.columna
                )
            if cols_ok:
                for i, fila in enumerate(nodo.init_filas):
                    if len(fila) != entrada.cols_matriz:
                        self.error_manager.error_semantico(
                            'IL-SEM-073',
                            f'Matriz "{nodo.nombre}" fila {i} esperaba {entrada.cols_matriz} columnas, '
                            f'pero se proporcionaron {len(fila)}',
                            nodo.linea, nodo.columna
                        )

    def _visitar_instruccion(self, nodo):
        """Visita una instrucción."""
        if isinstance(nodo, AssignStmt):
            self._visitar_asignacion(nodo)
        elif isinstance(nodo, IncDecStmt):
            self._visitar_inc_dec(nodo)
        elif isinstance(nodo, PrintStmt):
            # Un procedimiento como argumento directo de print corresponde a
            # IL-TIPO-020 (§7.1), que emite el verificador de tipos; no se
            # adelanta aquí IL-SEM-060 para no ocultarlo.
            if isinstance(nodo.expr, FunctionCall):
                self._visitar_llamada(nodo.expr.nombre, nodo.expr.argumentos, nodo.expr)
            else:
                self._visitar_expresion(nodo.expr)
        elif isinstance(nodo, ReadStmt):
            self._visitar_read(nodo)
        elif isinstance(nodo, IfStmt):
            self._visitar_if(nodo)
        elif isinstance(nodo, WhileStmt):
            self._visitar_while(nodo)
        elif isinstance(nodo, ForStmt):
            self._visitar_for(nodo)
        elif isinstance(nodo, ForEachStmt):
            self._visitar_foreach(nodo)
        elif isinstance(nodo, DoWhileStmt):
            self._visitar_do_while(nodo)
        elif isinstance(nodo, SwitchStmt):
            self._visitar_switch(nodo)
        elif isinstance(nodo, MatchStmt):
            self._visitar_match(nodo)
        elif isinstance(nodo, TryStmt):
            self._visitar_try(nodo)
        elif isinstance(nodo, ReturnStmt):
            self._visitar_return(nodo)
        elif isinstance(nodo, BreakStmt):
            self._visitar_break(nodo)
        elif isinstance(nodo, ContinueStmt):
            self._visitar_continue(nodo)
        elif isinstance(nodo, (CallStmt, FunctionCall)):
            # El parser construye CallStmt para toda llamada en posición de
            # instrucción; FunctionCall se acepta por robustez.
            self._visitar_llamada(nodo.nombre, nodo.argumentos, nodo)
            # IL-WARN-020: se descarta el valor de retorno (§10.5)
            entrada = self.tabla.buscar_funcion(nodo.nombre)
            if entrada and entrada.tipo_retorno and entrada.tipo_retorno != 'void':
                self.error_manager.advertencia(
                    'IL-WARN-020',
                    f'Se descarta el valor de retorno de la función "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )
        elif isinstance(nodo, MethodCallStmt):
            self._visitar_llamada_metodo(nodo.receptor, nodo.nombre_metodo,
                                         nodo.argumentos, nodo)
        elif isinstance(nodo, SuperCallStmt):
            # Solo llega aquí un padre(...)/super(...) que NO es la primera
            # instrucción de un constructor (ese caso especial lo consume
            # directamente _visitar_constructor) -- siempre inválido, pero
            # se sigue analizando para dar diagnósticos adicionales.
            self._visitar_super_call_stmt(nodo, es_primera=False)

    def _visitar_asignacion(self, nodo):
        """Verifica asignación."""
        # Verificar que el lvalue sea válido
        if isinstance(nodo.lvalue, VarLValue):
            entrada = self.tabla.buscar(nodo.lvalue.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Identificador no declarado: "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            elif entrada.tipo_simbolo == TipoSimbolo.CONSTANTE:
                self.error_manager.error_semantico(
                    'IL-SEM-031',
                    f'No se puede asignar a la constante "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            elif entrada.tipo_simbolo in (TipoSimbolo.ARREGLO, TipoSimbolo.MATRIZ,
                                          TipoSimbolo.PARAM_ARREGLO,
                                          TipoSimbolo.PARAM_MATRIZ):
                # IL-SIN-070: no se puede asignar un arreglo/matriz completo
                # con "="; la copia debe ser elemento a elemento (§12.6).
                self.error_manager.error_sintactico(
                    'IL-SIN-070',
                    f'No se puede asignar el arreglo o matriz completo '
                    f'"{nodo.lvalue.nombre}"; copie elemento a elemento',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            else:
                entrada.inicializado = True
        elif isinstance(nodo.lvalue, ArrayLValue):
            entrada = self.tabla.buscar(nodo.lvalue.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Arreglo no declarado: "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            elif entrada.es_constante:
                # Etapa 11: arreglo constante -- ninguno de sus elementos
                # se puede reasignar, mismo código que una constante
                # escalar (IL-SEM-031).
                self.error_manager.error_semantico(
                    'IL-SEM-031',
                    f'No se puede asignar a un elemento del arreglo '
                    f'constante "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            else:
                self._verificar_indices_matriz(entrada, nodo.lvalue)
                entrada.inicializado = True
            self._visitar_expresion(nodo.lvalue.indice)
        elif isinstance(nodo.lvalue, MatrixLValue):
            entrada = self.tabla.buscar(nodo.lvalue.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Matriz no declarada: "{nodo.lvalue.nombre}"',
                    nodo.lvalue.linea, nodo.lvalue.columna
                )
            else:
                entrada.inicializado = True
            self._visitar_expresion(nodo.lvalue.fila)
            self._visitar_expresion(nodo.lvalue.columna)
        elif isinstance(nodo.lvalue, MemberLValue):
            tipo_clase = self._visitar_receptor(nodo.lvalue.receptor)
            if tipo_clase is not None:
                self._resolver_miembro(tipo_clase, nodo.lvalue.nombre_miembro,
                                       False, nodo.lvalue,
                                       receptor_estatico=self._receptor_es_estatico(nodo.lvalue.receptor))

        self._visitar_expresion(nodo.expr)

    def _verificar_indices_matriz(self, entrada, nodo):
        """IL-SIN-080: una matriz debe indexarse con dos índices (§13.4)."""
        if entrada.tipo_simbolo in (TipoSimbolo.MATRIZ, TipoSimbolo.PARAM_MATRIZ):
            self.error_manager.error_sintactico(
                'IL-SIN-080',
                f'La matriz "{nodo.nombre}" requiere dos índices: '
                f'{nodo.nombre}[fila][columna]',
                nodo.linea, nodo.columna
            )

    def _visitar_inc_dec(self, nodo):
        """Verifica incremento/decremento."""
        entrada = self.tabla.buscar(nodo.nombre)
        if entrada is None:
            self.error_manager.error_semantico(
                'IL-SEM-003',
                f'Identificador no declarado: "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
        elif entrada.tipo_simbolo == TipoSimbolo.CONSTANTE:
            self.error_manager.error_semantico(
                'IL-SEM-031',
                f'No se puede modificar la constante "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
        else:
            entrada.inicializado = True

    def _visitar_read(self, nodo):
        """Verifica instrucción read/leer."""
        entrada = self.tabla.buscar(nodo.nombre)
        if entrada is None:
            self.error_manager.error_semantico(
                'IL-SEM-003',
                f'Identificador no declarado: "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
        elif entrada.tipo_simbolo == TipoSimbolo.CONSTANTE:
            self.error_manager.error_semantico(
                'IL-SEM-031',
                f'No se puede leer en la constante "{nodo.nombre}"',
                nodo.linea, nodo.columna
            )
        else:
            entrada.inicializado = True

    def _visitar_if(self, nodo):
        """Verifica instrucción if."""
        self._visitar_expresion(nodo.condicion)
        self.tabla.entrar_ambito()
        for elem in nodo.bloque_then.elementos:
            self._visitar_elemento_bloque(elem)
        self.tabla.salir_ambito()

        if nodo.bloque_else:
            self.tabla.entrar_ambito()
            for elem in nodo.bloque_else.elementos:
                self._visitar_elemento_bloque(elem)
            self.tabla.salir_ambito()

    def _visitar_while(self, nodo):
        """Verifica instrucción while."""
        self._visitar_expresion(nodo.condicion)
        # IL-WARN-010: while infinito (condición literal true) sin break (§9.1.3)
        if self._es_true_constante(nodo.condicion) and not self._bloque_tiene_break(nodo.bloque.elementos):
            self.error_manager.advertencia(
                'IL-WARN-010',
                'Ciclo while con condición constantemente true sin break alcanzable',
                nodo.linea, nodo.columna
            )
        self.tabla.loop_actual += 1
        self.tabla.entrar_ambito()
        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)
        self.tabla.salir_ambito()
        self.tabla.loop_actual -= 1

    def _visitar_for(self, nodo):
        """Verifica instrucción for."""
        # Crear ámbito para el for (init, cond, act y cuerpo comparten ámbito)
        self.tabla.loop_actual += 1
        self.tabla.entrar_ambito()

        # Inicialización
        if nodo.init_stmt:
            if isinstance(nodo.init_stmt, ForInitVar):
                ts = TipoSimbolo.VARIABLE
                entrada = self._declarar_simbolo(nodo.init_stmt.nombre, ts,
                                                 nodo.init_stmt.tipo,
                                                 nodo.init_stmt.linea,
                                                 nodo.init_stmt.columna)
                if entrada is None:
                    self._manejar_duplicado(nodo.init_stmt.nombre,
                                            nodo.init_stmt.linea,
                                            nodo.init_stmt.columna)
                elif nodo.init_stmt.init_expr:
                    entrada.inicializado = True
                    self._visitar_expresion(nodo.init_stmt.init_expr)
            elif isinstance(nodo.init_stmt, ForInitAsig):
                self._visitar_lvalue_simple(nodo.init_stmt.lvalue)
                self._visitar_expresion(nodo.init_stmt.expr)

        # Condición
        if nodo.cond_expr:
            self._visitar_expresion(nodo.cond_expr)

        # Acción
        if nodo.act_stmt:
            if isinstance(nodo.act_stmt, ForInitAsig):
                self._visitar_lvalue_simple(nodo.act_stmt.lvalue)
                self._visitar_expresion(nodo.act_stmt.expr)
            elif isinstance(nodo.act_stmt, ForInitIncDec):
                entrada = self.tabla.buscar(nodo.act_stmt.nombre)
                if entrada is None:
                    self.error_manager.error_semantico(
                        'IL-SEM-003',
                        f'Identificador no declarado: "{nodo.act_stmt.nombre}"',
                        nodo.act_stmt.linea, nodo.act_stmt.columna
                    )

        # Cuerpo
        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        self.tabla.salir_ambito()

    def _visitar_foreach(self, nodo):
        """Verifica para_cada/foreach (Etapa 12.1).

        Que `nodo.arreglo` sea realmente un arreglo/matriz y que
        `nodo.tipo` sea compatible con su tipo de elemento se verifica en
        type_checker.py (mismo criterio de división de responsabilidades
        que el resto del lenguaje: aquí solo registro de símbolos y
        alcance, la compatibilidad de tipos vive en el verificador de
        tipos)."""
        if nodo.tipo == 'void':
            self.error_manager.error_semantico(
                'IL-TIPO-015',
                f'La variable de recorrido "{nodo.nombre}" no puede ser de tipo void',
                nodo.linea, nodo.columna
            )
        else:
            self._validar_tipo(nodo.tipo, nodo.linea, nodo.columna)
        self._visitar_expresion(nodo.arreglo)

        self.tabla.loop_actual += 1
        self.tabla.entrar_ambito()
        entrada = self._declarar_simbolo(nodo.nombre, TipoSimbolo.VARIABLE,
                                         nodo.tipo, nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre, nodo.linea, nodo.columna)
        elif entrada:
            entrada.inicializado = True

        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        self.tabla.salir_ambito()
        self.tabla.loop_actual -= 1
        self.tabla.loop_actual -= 1

    def _visitar_do_while(self, nodo):
        """Verifica instrucción do/hacer ... while/mientras (Etapa 6)."""
        self.tabla.loop_actual += 1
        self.tabla.entrar_ambito()
        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)
        self.tabla.salir_ambito()
        self.tabla.loop_actual -= 1
        self._visitar_expresion(nodo.condicion)

    def _visitar_switch(self, nodo):
        """Verifica instrucción switch/segun (Etapa 6). El tipo de la
        expresión y de cada case se valida en type_checker.py; aquí sólo se
        controlan alcance, `break` y duplicados (estructural, igual que el
        resto de semantic.py)."""
        self._visitar_expresion(nodo.expr)
        self.tabla.switch_actual += 1
        vistos = set()
        for caso in nodo.casos:
            clave = (caso.valor.tipo_literal, caso.valor.valor)
            if clave in vistos:
                self.error_manager.error_estructurado(
                    'IL-EST-003',
                    f'Valor de case duplicado dentro del mismo switch: '
                    f'{caso.valor.valor!r}',
                    caso.linea, caso.columna
                )
            vistos.add(clave)
            self.tabla.entrar_ambito()
            for elem in caso.bloque.elementos:
                self._visitar_elemento_bloque(elem)
            self.tabla.salir_ambito()
        if nodo.bloque_default is not None:
            self.tabla.entrar_ambito()
            for elem in nodo.bloque_default.elementos:
                self._visitar_elemento_bloque(elem)
            self.tabla.salir_ambito()
        self.tabla.switch_actual -= 1

    def _visitar_match(self, nodo):
        """Verifica emparejar/match (Etapa 12.9/12.10): alcance y ligadura
        de variables por caso -- igual que switch, la verificación de
        TIPOS (variante válida, aridad, exhaustividad) vive en
        type_checker.py::_verificar_match (necesita el tipo estático de
        `nodo.expr`, que semantic.py no computa). Aquí sólo se declaran
        las ligaduras de cada caso con el tipo de campo que ya se conoce
        (las variantes, con o sin carga, ya son clases reales a esta
        altura -- ver _desazucarar_tipos_suma) y se visita cada bloque en
        su propio ámbito."""
        self._visitar_expresion(nodo.expr)
        for caso in nodo.casos:
            self.tabla.entrar_ambito()
            info_variante = self.tabla.clases.get(caso.nombre_variante)
            campos = []
            if info_variante is not None:
                campos = [a for a in info_variante.atributos.values() if not a.es_estatico]
            for i, ligadura in enumerate(caso.ligaduras):
                tipo_campo = campos[i].tipo if i < len(campos) else None
                entrada = self._declarar_simbolo(ligadura, TipoSimbolo.VARIABLE, tipo_campo,
                                                 caso.linea, caso.columna)
                if entrada is None:
                    self._manejar_duplicado(ligadura, caso.linea, caso.columna)
                else:
                    entrada.inicializado = True
            for elem in caso.bloque.elementos:
                self._visitar_elemento_bloque(elem)
            self.tabla.salir_ambito()
        if nodo.caso_comodin is not None:
            self.tabla.entrar_ambito()
            for elem in nodo.caso_comodin.elementos:
                self._visitar_elemento_bloque(elem)
            self.tabla.salir_ambito()

    def _visitar_try(self, nodo):
        """Verifica try/intentar ... catch/capturar genérico (Etapa 6). La
        variable del catch queda declarada con tipo 'Excepcion' (clase
        sintética siempre registrada, ver symbol_table.py), reutilizando el
        acceso a miembro de POO para `.codigo`/`.mensaje`."""
        self.tabla.entrar_ambito()
        for elem in nodo.bloque_try.elementos:
            self._visitar_elemento_bloque(elem)
        self.tabla.salir_ambito()

        self.tabla.entrar_ambito()
        entrada = self._declarar_simbolo(nodo.nombre_catch, TipoSimbolo.VARIABLE,
                                         'Excepcion', nodo.linea, nodo.columna)
        if entrada is None:
            self._manejar_duplicado(nodo.nombre_catch, nodo.linea, nodo.columna)
        else:
            entrada.inicializado = True
        for elem in nodo.bloque_catch.elementos:
            self._visitar_elemento_bloque(elem)
        self.tabla.salir_ambito()

    def _visitar_lvalue_simple(self, lvalue):
        """Visita un lvalue en contexto de for."""
        if isinstance(lvalue, VarLValue):
            entrada = self.tabla.buscar(lvalue.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Identificador no declarado: "{lvalue.nombre}"',
                    lvalue.linea, lvalue.columna
                )
        elif isinstance(lvalue, ArrayLValue):
            self._visitar_expresion(lvalue.indice)
        elif isinstance(lvalue, MatrixLValue):
            self._visitar_expresion(lvalue.fila)
            self._visitar_expresion(lvalue.columna)

    def _visitar_return(self, nodo):
        """Verifica instrucción return."""
        if self.en_funcion:
            if nodo.expr is None:
                self.error_manager.error_semantico(
                    'IL-SEM-053',
                    f'La función "{self.funcion_actual}" requiere return con expresión',
                    nodo.linea, nodo.columna
                )
            else:
                self._visitar_expresion(nodo.expr)
                self.tiene_return = True
        elif self.en_procedimiento:
            if nodo.expr is not None:
                self.error_manager.error_semantico(
                    'IL-SEM-061',
                    f'Procedimiento "{self.funcion_actual}" no puede retornar valor',
                    nodo.linea, nodo.columna
                )
            else:
                self.tiene_return = True
        else:
            # return en main
            if nodo.expr is not None:
                self.error_manager.error_semantico(
                    'IL-SEM-023',
                    'main no debe retornar valor',
                    nodo.linea, nodo.columna
                )

    def _visitar_break(self, nodo):
        """Verifica break. Válido dentro de un ciclo (while/for/do-while) O
        de un switch/segun (Etapa 6) -- a diferencia de continue."""
        if not self.tabla.esta_en_loop_o_switch():
            self.error_manager.error_semantico(
                'IL-SEM-040',
                'break solo puede usarse dentro de un ciclo o un switch/segun',
                nodo.linea, nodo.columna
            )

    def _visitar_continue(self, nodo):
        """Verifica continue."""
        if not self.tabla.esta_en_loop():
            self.error_manager.error_semantico(
                'IL-SEM-041',
                'continue solo puede usarse dentro de un ciclo',
                nodo.linea, nodo.columna
            )

    def _visitar_expresion(self, nodo):
        """Visita una expresión (análisis semántico básico)."""
        if nodo is None:
            return

        if isinstance(nodo, BinaryOp):
            self._visitar_expresion(nodo.izquierda)
            self._visitar_expresion(nodo.derecha)
        elif isinstance(nodo, UnaryOp):
            self._visitar_expresion(nodo.operando)
        elif isinstance(nodo, Literal):
            # IL-SEM-010: verificar desbordamiento de enteros
            if isinstance(nodo.valor, int) and not isinstance(nodo.valor, bool):
                if nodo.valor > 2147483647 or nodo.valor < -2147483648:
                    self.error_manager.error_semantico(
                        'IL-SEM-010',
                        f'Literal entero fuera de rango: {nodo.valor}',
                        nodo.linea, nodo.columna
                    )
        elif isinstance(nodo, Identifier):
            entrada = self.tabla.buscar(nodo.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Identificador no declarado: "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )
            elif (entrada.tipo_simbolo == TipoSimbolo.VARIABLE
                    and not entrada.inicializado
                    and not self.tabla.es_global(nodo.nombre)):
                # IL-WARN-002: lectura de una local posiblemente sin inicializar
                # (§5.2.2). Se avisa una sola vez por variable.
                if nodo.nombre not in self._avisadas_sin_init:
                    self._avisadas_sin_init.add(nodo.nombre)
                    self.error_manager.advertencia(
                        'IL-WARN-002',
                        f'"{nodo.nombre}" puede leerse antes de ser inicializada',
                        nodo.linea, nodo.columna
                    )
            # Antes de la Etapa 12.6, un IDENTIFICADOR bare que resolvía a
            # un PROCEDIMIENTO siempre era IL-SEM-060 ("procedimiento usado
            # como expresión") -- ahora es una referencia válida a un
            # valor-función (funciones de primera clase), así que ya no se
            # rechaza aquí. La forma LLAMADA (`p()`, ver FunctionCall más
            # abajo) sigue rechazándose igual que siempre -- eso nunca
            # cambió de significado.
        elif isinstance(nodo, ArrayAccess):
            entrada = self.tabla.buscar(nodo.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Arreglo no declarado: "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )
            else:
                self._verificar_indices_matriz(entrada, nodo)
            self._visitar_expresion(nodo.indice)
        elif isinstance(nodo, MatrixAccess):
            entrada = self.tabla.buscar(nodo.nombre)
            if entrada is None:
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Matriz no declarada: "{nodo.nombre}"',
                    nodo.linea, nodo.columna
                )
            self._visitar_expresion(nodo.fila)
            self._visitar_expresion(nodo.columna)
        elif isinstance(nodo, FunctionCall):
            callee = self.tabla.buscar_funcion(nodo.nombre)
            if callee and callee.tipo_simbolo == TipoSimbolo.PROCEDIMIENTO:
                self._reportar_uso_como_valor(callee, nodo.nombre, nodo)
            self._visitar_llamada(nodo.nombre, nodo.argumentos, nodo)
        elif isinstance(nodo, ThisExpr):
            self._visitar_receptor(nodo)  # solo valida el contexto (IL-POO-011)
        elif isinstance(nodo, NullExpr):
            pass  # sin identificador que resolver
        elif isinstance(nodo, MemberAccess):
            tipo_clase = self._visitar_receptor(nodo.receptor)
            if tipo_clase is not None:
                self._resolver_miembro(tipo_clase, nodo.nombre_miembro, False, nodo,
                                       receptor_estatico=self._receptor_es_estatico(nodo.receptor))
        elif isinstance(nodo, MethodCallExpr):
            self._visitar_llamada_metodo(nodo.receptor, nodo.nombre_metodo,
                                         nodo.argumentos, nodo)
        elif isinstance(nodo, NewExpr):
            self._visitar_new(nodo)
        elif isinstance(nodo, TernaryExpr):
            self._visitar_expresion(nodo.condicion)
            self._visitar_expresion(nodo.si_verdadero)
            self._visitar_expresion(nodo.si_falso)
        elif isinstance(nodo, LambdaExpr):
            self._visitar_lambda(nodo)

    def _visitar_lambda(self, nodo):
        """Verifica el cuerpo de un lambda (Etapa 12.6). A diferencia de
        una función/procedimiento de nivel superior, un lambda está
        anidado SINTÁCTICAMENTE dentro del cuerpo que lo crea -- entrar un
        ámbito nuevo aquí, sobre la pila de ámbitos YA vigente en este
        punto, es lo que hace que sus parámetros vean las variables ya
        declaradas en el ámbito envolvente sin ningún mecanismo de captura
        estático nuevo (la pila de ámbitos es, literalmente, el entorno
        léxico). El resto del análisis (return/IL-SEM-050) reutiliza
        exactamente el mismo mecanismo de `funcion_actual`/`en_funcion`/
        `en_procedimiento`/`tiene_return` que ya usa cualquier función o
        procedimiento normal (`_visitar_funcion`/`_visitar_procedimiento`)
        -- guardado y restaurado aquí porque un lambda puede anidarse
        dentro del cuerpo de OTRA función, y no debe pisar su contexto."""
        self.tabla.entrar_ambito()
        for p in nodo.parametros:
            self._declarar_parametro(p)

        funcion_previa = self.funcion_actual
        tipo_retorno_previo = self.tipo_retorno_actual
        en_funcion_previo = self.en_funcion
        en_proc_previo = self.en_procedimiento
        tiene_return_previo = self.tiene_return

        self.funcion_actual = '<lambda>'
        self.tipo_retorno_actual = nodo.tipo_retorno
        self.en_funcion = nodo.tipo_retorno != 'void'
        self.en_procedimiento = nodo.tipo_retorno == 'void'
        self.tiene_return = False

        for elem in nodo.bloque.elementos:
            self._visitar_elemento_bloque(elem)

        if nodo.tipo_retorno != 'void' and not self._siempre_retorna(nodo.bloque.elementos):
            self.error_manager.error_semantico(
                'IL-SEM-050',
                'El lambda tiene al menos una ruta de ejecución que no '
                'alcanza ningún return',
                nodo.linea, nodo.columna
            )

        self.funcion_actual = funcion_previa
        self.tipo_retorno_actual = tipo_retorno_previo
        self.en_funcion = en_funcion_previo
        self.en_procedimiento = en_proc_previo
        self.tiene_return = tiene_return_previo

        self.tabla.salir_ambito()

    def _reportar_uso_como_valor(self, entrada, nombre, nodo):
        """Reporta el uso de un procedimiento donde se espera un valor.

        Si además devuelve un valor, el error de fondo está en la declaración:
        se quiso escribir una función y se declaró `void` (IL-SEM-051, §10.2).
        Si no devuelve nada, el error está en el uso (IL-SEM-060, §11.4.1).
        """
        if getattr(entrada, 'retorna_valor', False):
            self.error_manager.error_semantico(
                'IL-SEM-051',
                f'"{nombre}" devuelve un valor pero está declarada con tipo '
                f'de retorno void; declárela como función con su tipo',
                nodo.linea, nodo.columna
            )
        else:
            self.error_manager.error_semantico(
                'IL-SEM-060',
                f'Procedimiento "{nombre}" usado como expresión',
                nodo.linea, nodo.columna
            )

    def _visitar_llamada(self, nombre, argumentos, nodo):
        """Verifica una llamada a función/procedimiento."""
        if nombre in _ORDEN_SUPERIOR:
            # Etapa 12.7: reducir/mapear/filtrar (ver _ORDEN_SUPERIOR) --
            # aridad fija, cada argumento se visita normalmente (el 2do,
            # una funcion o un arreglo de salida segun el caso, no
            # necesita verificacion especial aqui: type_checker.py valida
            # lo que pueda por tipo, el resto es responsabilidad del
            # programador, igual que cualquier funcion integrada).
            esperados = _ORDEN_SUPERIOR[nombre]
            if len(argumentos) != esperados:
                self.error_manager.error_semantico(
                    'IL-SEM-052',
                    f'Llamada a "{nombre}": esperados {esperados} argumentos, '
                    f'recibidos {len(argumentos)}',
                    nodo.linea, nodo.columna
                )
            for arg in argumentos:
                self._visitar_expresion(arg)
            return
        entrada = self.tabla.buscar_funcion(nombre)
        if entrada is None:
            # Etapa 12.6: `nombre` también puede ser una variable local de
            # tipo función (closure) -- misma sintaxis de llamada
            # (`llamada_funcion : IDENTIFICADOR '(' args ')'`), el punto de
            # decisión es semántico, no gramatical (ver checkpoint 12.5).
            var = self.tabla.buscar(nombre)
            if var and isinstance(var.tipo_dato, str) and var.tipo_dato.startswith('funcion('):
                num_params = var.tipo_dato[len('funcion('):var.tipo_dato.index(')')]
                num_params = len([t for t in num_params.split(',') if t]) if num_params else 0
                if num_params != len(argumentos):
                    self.error_manager.error_semantico(
                        'IL-SEM-052',
                        f'Llamada a "{nombre}": esperados {num_params} argumentos, '
                        f'recibidos {len(argumentos)}',
                        nodo.linea, nodo.columna
                    )
            else:
                # Podría ser una función definida después
                self.error_manager.error_semantico(
                    'IL-SEM-003',
                    f'Función o procedimiento no declarado: "{nombre}"',
                    nodo.linea, nodo.columna
                )
        else:
            # Verificar número de argumentos
            num_params = len(entrada.params)
            num_args = len(argumentos)
            if num_params != num_args:
                self.error_manager.error_semantico(
                    'IL-SEM-052',
                    f'Llamada a "{nombre}": esperados {num_params} argumentos, recibidos {num_args}',
                    nodo.linea, nodo.columna
                )

        for arg in argumentos:
            self._visitar_expresion(arg)
