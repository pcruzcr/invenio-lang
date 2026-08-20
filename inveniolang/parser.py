# Módulo del Analizador Sintáctico (Parser) de InvenioLang 1.0
# Implementado con PLY - Secciones 3, 16 de la especificación
# Construye el AST a partir de la secuencia de tokens

import ply.yacc as yacc
from .lexer import Lexer
from .errors import ErrorManager
from .ast_nodes import *


class Parser:
    """Analizador sintáctico de InvenioLang 1.0.

    Construye un AST usando la gramática formal de la Sección 16.12 (Tabla 13).
    La precedencia de operadores está codificada mediante las reglas de PLY.
    """

    def __init__(self, lexer=None, error_manager=None):
        self.lexer = lexer or Lexer()
        self.error_manager = error_manager or ErrorManager()
        self.tokens = self.lexer.tokens
        self.parser_obj = None
        # Rastreo del último `if` sin `else` para distinguir IL-SIN-032 de
        # IL-SIN-033 (véase p_elem_bloque y p_else_huerfano).
        self._if_sin_else = None
        self._elems_tras_if = 0

    def build(self, **kwargs):
        self.parser_obj = yacc.yacc(module=self, **kwargs)

    # ---- Precedencia de operadores (de menor a mayor) ----
    # Codifica la jerarquía de la Sección 16.7
    precedence = (
        ('left', 'OP_OR'),
        ('left', 'OP_AND'),
        ('left', 'OP_IGUAL', 'OP_DISTINTO'),
        ('left', 'OP_MENOR', 'OP_MAYOR', 'OP_MENOR_IGUAL', 'OP_MAYOR_IGUAL'),
        ('left', 'OP_SUMA', 'OP_RESTA'),
        ('left', 'OP_MULT', 'OP_DIV', 'OP_MOD'),
        ('right', 'UMINUS', 'OP_NOT'),
    )

    # ============================================================
    # Producción raíz
    # ============================================================

    def p_programa(self, p):
        """programa : lista_elementos_programa"""
        prog = Program()
        elementos = p[1]
        for elem in elementos:
            if isinstance(elem, MainDecl):
                if prog.main is not None:
                    # Solo puede existir una main por archivo (§3.2)
                    self.error_manager.error_semantico(
                        'IL-SEM-002',
                        'Identificador duplicado: ya existe una función "main"',
                        elem.linea, elem.columna
                    )
                    continue
                prog.main = elem
            elif isinstance(elem, (FunctionDecl, ProcedureDecl)):
                prog.subrutinas.append(elem)
            elif isinstance(elem, ClassDecl):
                prog.clases.append(elem)
            elif isinstance(elem, EnumDecl):
                prog.enums.append(elem)
            else:
                if prog.main is None:
                    prog.declaraciones_globales.append(elem)
                else:
                    prog.declaraciones_posteriores.append(elem)
        p[0] = prog

    def p_lista_elementos_programa(self, p):
        """lista_elementos_programa : lista_elementos_programa elemento_programa
                                    | elemento_programa"""
        if len(p) == 3:
            p[1].append(p[2])
            p[0] = p[1]
        else:
            p[0] = [p[1]]

    def p_elemento_programa(self, p):
        """elemento_programa : decl_global
                             | def_funcion
                             | def_procedimiento
                             | def_main
                             | class_decl
                             | enum_decl
                             | interface_decl"""
        p[0] = p[1]

    def p_interface_decl(self, p):
        """interface_decl : KW_INTERFACE IDENTIFICADOR DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C"""
        # interfaz/interface (Etapa 12.3): azúcar sobre "abstracta clase"
        # con TODOS los métodos abstractos (se verifica en semantic.py,
        # mismo mensaje mas claro via es_interfaz=True) -- no admite
        # `hereda`/`implementa` propio, alcance deliberadamente acotado
        # (una interfaz no puede extender otra interfaz en este
        # incremento). KW_INTERFACE es un token de apertura propio, sin
        # colisión con nada mas en elemento_programa.
        p[0] = self._construir_class_decl(p[2], None, p[4], True, None,
                                          p.lineno(1), self._col(p, 1),
                                          es_interfaz=True)

    def p_enum_decl(self, p):
        """enum_decl : KW_ENUM IDENTIFICADOR DEL_LLAVE_A lista_miembros_enum DEL_LLAVE_C"""
        # Etapa 11: KW_ENUM es un token de apertura propio -- no comparte
        # prefijo con nada mas en elemento_programa, mismo criterio de bajo
        # riesgo que KW_CLASS/KW_ABSTRACT (verificado sin conflictos nuevos
        # con parser.py(debug=True)).
        p[0] = EnumDecl(p[2], p[4], p.lineno(1), self._col(p, 1))

    def p_lista_miembros_enum(self, p):
        """lista_miembros_enum : lista_miembros_enum DEL_COMA miembro_enum
                               | miembro_enum"""
        # Etapa 12.9 (checkpoint): reemplaza lista_identificadores (que
        # sigue existiendo tal cual, usada por lista_implementa -- NO se
        # modifico, para no arriesgar nada ahi). Cada miembro es
        # EnumMiembro(nombre, parametros) -- parametros=[] para la forma
        # bare (Etapa 11.8, sin cambios de comportamiento), o una lista de
        # Parametro para una variante con carga (tipo suma, Etapa 12.10).
        if len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]
        else:
            p[0] = [p[1]]

    def p_miembro_enum(self, p):
        """miembro_enum : IDENTIFICADOR
                        | IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C"""
        params = p[3] if len(p) == 5 else []
        p[0] = EnumMiembro(p[1], params, p.lineno(1), self._col(p, 1))

    def p_lista_identificadores(self, p):
        """lista_identificadores : lista_identificadores DEL_COMA IDENTIFICADOR
                                 | IDENTIFICADOR"""
        if len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]
        else:
            p[0] = [p[1]]

    def p_def_main(self, p):
        """def_main : KW_VOID KW_MAIN DEL_PAREN_A DEL_PAREN_C bloque"""
        p[0] = MainDecl(p[5], p.lineno(1), self._col(p, 1))

    def p_def_main_tipo_incorrecto(self, p):
        """def_main : tipo KW_MAIN DEL_PAREN_A DEL_PAREN_C bloque"""
        # IL-SEM-021: main debe declararse con tipo de retorno void (§3.2)
        self.error_manager.error_semantico(
            'IL-SEM-021',
            f'main debe declararse con tipo de retorno void, no {p[1]}',
            p.lineno(2), self._col(p, 2)
        )
        p[0] = MainDecl(p[5], p.lineno(1), self._col(p, 1))

    def p_def_main_con_params(self, p):
        """def_main : KW_VOID KW_MAIN DEL_PAREN_A lista_params DEL_PAREN_C bloque
                    | tipo KW_MAIN DEL_PAREN_A lista_params DEL_PAREN_C bloque"""
        # IL-SEM-022: main no admite parámetros en InvenioLang 1.0 (§3.2)
        if p[4]:
            self.error_manager.error_semantico(
                'IL-SEM-022',
                'main no admite parámetros en InvenioLang 1.0',
                p.lineno(2), self._col(p, 2)
            )
        if p.slice[1].type != 'KW_VOID':
            self.error_manager.error_semantico(
                'IL-SEM-021',
                f'main debe declararse con tipo de retorno void, no {p[1]}',
                p.lineno(2), self._col(p, 2)
            )
        p[0] = MainDecl(p[6], p.lineno(1), self._col(p, 1))

    # ============================================================
    # Declaraciones
    # ============================================================

    def p_decl_global(self, p):
        """decl_global : decl_variable
                       | decl_constante
                       | decl_arreglo
                       | decl_matriz"""
        p[0] = p[1]

    def p_decl_variable(self, p):
        """decl_variable : tipo IDENTIFICADOR DEL_PUNTO_COMA
                         | tipo IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA"""
        if len(p) == 4:
            p[0] = VarDecl(p[1], p[2], None, p.lineno(2), self._col(p, 2))
        else:
            p[0] = VarDecl(p[1], p[2], p[4], p.lineno(2), self._col(p, 2))

    def p_decl_variable_multiple(self, p):
        """decl_variable : tipo IDENTIFICADOR DEL_COMA lista_ident DEL_PUNTO_COMA"""
        # IL-SIN-015: cada variable debe declararse por separado (§5.1.2)
        self.error_manager.error_sintactico(
            'IL-SIN-015',
            'No se admite declarar varias variables en una sola instrucción; '
            'declare cada una por separado',
            p.lineno(2), self._col(p, 2)
        )
        p[0] = VarDecl(p[1], p[2], None, p.lineno(2), self._col(p, 2))

    def p_lista_ident(self, p):
        """lista_ident : lista_ident DEL_COMA IDENTIFICADOR
                       | IDENTIFICADOR"""
        p[0] = (p[1] + [p[3]]) if len(p) == 4 else [p[1]]

    def p_decl_constante(self, p):
        """decl_constante : KW_CONST tipo IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA"""
        p[0] = ConstDecl(p[2], p[3], p[5], p.lineno(3), self._col(p, 3))

    def p_decl_constante_sin_init(self, p):
        """decl_constante : KW_CONST tipo IDENTIFICADOR DEL_PUNTO_COMA"""
        # IL-SEM-030: la inicialización de una constante es obligatoria (§5.4.1)
        self.error_manager.error_semantico(
            'IL-SEM-030',
            f'La constante "{p[3]}" debe inicializarse en su declaración',
            p.lineno(3), self._col(p, 3)
        )
        p[0] = ConstDecl(p[2], p[3],
                         Literal(0, 'int', p.lineno(3), self._col(p, 3)),
                         p.lineno(3), self._col(p, 3))

    def p_decl_constante_arreglo(self, p):
        """decl_constante : KW_CONST tipo DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR OP_ASIG DEL_LLAVE_A lista_expr_init DEL_LLAVE_C DEL_PUNTO_COMA"""
        # Etapa 11: arreglo constante -- riesgo de gramática bajo. Tras
        # `KW_CONST tipo`, el siguiente token distingue sin ambigüedad
        # entre la forma escalar (IDENTIFICADOR, ya existente arriba) y
        # esta forma de arreglo (DEL_CORCHETE_A '['); verificado sin
        # conflictos nuevos con parser.py(debug=True).
        p[0] = ArrayDecl(p[2], p[4], p[6], p[9], es_constante=True,
                         linea=p.lineno(6), columna=self._col(p, 6))

    def p_decl_arreglo(self, p):
        """decl_arreglo : tipo DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR DEL_PUNTO_COMA
                        | tipo DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR OP_ASIG DEL_LLAVE_A lista_expr_init DEL_LLAVE_C DEL_PUNTO_COMA"""
        if len(p) == 7:
            p[0] = ArrayDecl(p[1], p[3], p[5], [], p.lineno(5), self._col(p, 5))
        else:
            p[0] = ArrayDecl(p[1], p[3], p[5], p[8], p.lineno(5), self._col(p, 5))

    def p_decl_matriz(self, p):
        """decl_matriz : tipo DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR DEL_PUNTO_COMA
                        | tipo DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR OP_ASIG DEL_LLAVE_A lista_filas_init DEL_LLAVE_C DEL_PUNTO_COMA"""
        if len(p) == 10:
            p[0] = MatrixDecl(p[1], p[3], p[6], p[8], [], p.lineno(8), self._col(p, 8))
        else:
            p[0] = MatrixDecl(p[1], p[3], p[6], p[8], p[11], p.lineno(8), self._col(p, 8))

    # ---- Forma postfija de declaracion (estilo C) ----
    # §16.5 define la forma prefija `tipo [tam] IDENT` como canonica, pero
    # §17.3 imprime `float temps[5]`. Se aceptan ambas para que todos los
    # programas de referencia compilen tal como estan impresos; la postfija
    # emite IL-WARN-040 recomendando la forma canonica.

    def _avisar_postfijo(self, p, idx, nombre):
        self.error_manager.advertencia(
            'IL-WARN-040',
            f'Declaración postfija de "{nombre}": la forma canónica de '
            f'InvenioLang es prefija, con las dimensiones antes del nombre',
            p.lineno(idx), self._col(p, idx)
        )

    def p_decl_arreglo_postfijo(self, p):
        """decl_arreglo : tipo IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_PUNTO_COMA
                        | tipo IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C OP_ASIG DEL_LLAVE_A lista_expr_init DEL_LLAVE_C DEL_PUNTO_COMA"""
        self._avisar_postfijo(p, 2, p[2])
        init = p[8] if len(p) == 11 else []
        p[0] = ArrayDecl(p[1], p[4], p[2], init, p.lineno(2), self._col(p, 2))

    def p_decl_arreglo_clase(self, p):
        """decl_arreglo : IDENTIFICADOR IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_PUNTO_COMA
                        | IDENTIFICADOR IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C OP_ASIG DEL_LLAVE_A lista_expr_init DEL_LLAVE_C DEL_PUNTO_COMA"""
        # Arreglo de objetos (POO, InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md
        # "Arreglos de objetos"): SOLO forma postfija. La prefija (`Clase[tam]
        # nombre;`) colisionaria con `arr[i] = x;` (ambas arrancan
        # IDENTIFICADOR '['), un riesgo de conflicto reduce/reduce que se
        # evita por completo no ofreciendo esa alternativa. A diferencia del
        # postfijo de tipos primitivos, aqui NO se avisa IL-WARN-040: para una
        # clase no existe una forma "canonica" alternativa de la cual desviarse.
        init = p[8] if len(p) == 11 else []
        p[0] = ArrayDecl(p[1], p[4], p[2], init, p.lineno(2), self._col(p, 2))

    def p_decl_matriz_postfijo(self, p):
        """decl_matriz : tipo IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_PUNTO_COMA
                       | tipo IDENTIFICADOR DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_CORCHETE_A tam DEL_CORCHETE_C OP_ASIG DEL_LLAVE_A lista_filas_init DEL_LLAVE_C DEL_PUNTO_COMA"""
        self._avisar_postfijo(p, 2, p[2])
        init = p[11] if len(p) == 14 else []
        p[0] = MatrixDecl(p[1], p[4], p[7], p[2], init, p.lineno(2), self._col(p, 2))

    def p_decl_tres_dimensiones(self, p):
        """decl_arreglo : tipo DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_CORCHETE_A tam DEL_CORCHETE_C DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR DEL_PUNTO_COMA"""
        # IL-SIN-081: InvenioLang 1.0 admite como máximo dos dimensiones (§13.6)
        self.error_manager.error_sintactico(
            'IL-SIN-081',
            'InvenioLang 1.0 admite arreglos de una dimensión y matrices de '
            'dos; no existen tres o más dimensiones',
            p.lineno(11), self._col(p, 11)
        )
        p[0] = ArrayDecl(p[1], p[3], p[11], [], p.lineno(11), self._col(p, 11))

    def p_lista_expr_init(self, p):
        """lista_expr_init : lista_expr_init DEL_COMA expresion
                           | expresion"""
        if len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]
        else:
            p[0] = [p[1]]

    def p_lista_filas_init(self, p):
        """lista_filas_init : lista_filas_init DEL_COMA fila_init
                            | fila_init"""
        if len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]
        else:
            p[0] = [p[1]]

    def p_fila_init(self, p):
        """fila_init : DEL_LLAVE_A lista_expr_init DEL_LLAVE_C"""
        p[0] = p[2]

    def p_tam(self, p):
        """tam : ENTERO_LIT
               | IDENTIFICADOR"""
        p[0] = p[1]

    def p_tipo(self, p):
        """tipo : KW_INT
               | KW_FLOAT
               | KW_STRING
               | KW_BOOL"""
        # void queda FUERA de <tipo> (§16.5): sólo es válido como tipo de
        # retorno de procedimientos. Incluirlo aquí volvía ambigua la gramática
        # entre `void x;` y `void f() {...}`.
        mapa = {
            'KW_INT': 'int', 'KW_FLOAT': 'float',
            'KW_STRING': 'string', 'KW_BOOL': 'bool',
        }
        p[0] = mapa[p.slice[1].type]

    # ---- Funciones de primera clase (Etapa 12.5/12.6) ----
    # Un "tipo funcion" (`funcion(entero a, entero b) entero`) es una
    # cadena canónica sintetizada aquí mismo -- reutiliza el mecanismo ya
    # existente para tipos de clase (una cadena arbitraria como "tipo",
    # comparada estructuralmente donde haga falta en type_checker.py) en
    # vez de inventar un nodo/categoría de tipo nueva. `KW_FUNCION` activa
    # las palabras 'function'/'funcion', reservadas desde la v1.0
    # (Apéndice A) pero sin uso hasta esta etapa -- token de apertura
    # propio, nunca antes usado para iniciar una declaración ni una
    # expresión, así que ninguna de las dos producciones de abajo colisiona
    # con nada existente (verificado con `parser.py(debug=True)`).

    def _tipo_funcion_str(self, parametros, tipo_retorno):
        tipos = ','.join(p.tipo for p in parametros)
        return f'funcion({tipos})->{tipo_retorno}'

    def p_tipo_retorno_funcion(self, p):
        """tipo_retorno_funcion : tipo
                                | KW_VOID"""
        p[0] = p[1] if p.slice[1].type != 'KW_VOID' else 'void'

    def p_decl_variable_funcion(self, p):
        """decl_variable : KW_FUNCION DEL_PAREN_A lista_params DEL_PAREN_C tipo_retorno_funcion IDENTIFICADOR DEL_PUNTO_COMA
                         | KW_FUNCION DEL_PAREN_A lista_params DEL_PAREN_C tipo_retorno_funcion IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA"""
        tipo_str = self._tipo_funcion_str(p[3], p[5])
        init = p[8] if len(p) == 10 else None
        p[0] = VarDecl(tipo_str, p[6], init, p.lineno(6), self._col(p, 6))

    def p_expr_primaria_lambda(self, p):
        """expr_primaria : KW_FUNCION DEL_PAREN_A lista_params DEL_PAREN_C tipo_retorno_funcion bloque"""
        p[0] = LambdaExpr(p[3], p[5], p[6], p.lineno(1), self._col(p, 1))

    # ---- Declaraciones con tipo void ----
    # La gramática las acepta para que el diagnóstico lo emita el analizador
    # semántico (IL-TIPO-015 / IL-SEM-072) en lugar de un error de sintaxis.

    def p_decl_variable_void(self, p):
        """decl_variable : KW_VOID IDENTIFICADOR DEL_PUNTO_COMA
                         | KW_VOID IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA"""
        init = p[4] if len(p) == 6 else None
        p[0] = VarDecl('void', p[2], init, p.lineno(2), self._col(p, 2))

    def p_decl_arreglo_void(self, p):
        """decl_arreglo : KW_VOID DEL_CORCHETE_A tam DEL_CORCHETE_C IDENTIFICADOR DEL_PUNTO_COMA"""
        p[0] = ArrayDecl('void', p[3], p[5], [], p.lineno(5), self._col(p, 5))

    def p_param_void(self, p):
        """param : KW_VOID IDENTIFICADOR"""
        p[0] = Parametro('void', p[2], False, False, p.lineno(2), self._col(p, 2))

    # ============================================================
    # Funciones y Procedimientos
    # ============================================================

    def p_def_funcion(self, p):
        """def_funcion : tipo IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque"""
        p[0] = FunctionDecl(p[1], p[2], p[4], p[6], p.lineno(2), self._col(p, 2))

    def p_def_procedimiento(self, p):
        """def_procedimiento : KW_VOID IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque"""
        p[0] = ProcedureDecl(p[2], p[4], p[6], p.lineno(2), self._col(p, 2))

    def p_lista_params(self, p):
        """lista_params : lista_params DEL_COMA param
                        | param
                        | empty"""
        if p[1] is None:
            p[0] = []
        elif len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]
        else:
            p[0] = [p[1]]

    def p_param(self, p):
        """param : tipo IDENTIFICADOR
                 | tipo DEL_CORCHETE_A DEL_CORCHETE_C IDENTIFICADOR
                 | tipo DEL_CORCHETE_A DEL_CORCHETE_C DEL_CORCHETE_A DEL_CORCHETE_C IDENTIFICADOR"""
        if len(p) == 3:
            p[0] = Parametro(p[1], p[2], False, False, p.lineno(2), self._col(p, 2))
        elif len(p) == 5:
            p[0] = Parametro(p[1], p[4], True, False, p.lineno(4), self._col(p, 4))
        else:
            p[0] = Parametro(p[1], p[6], False, True, p.lineno(6), self._col(p, 6))

    # ============================================================
    # Bloques
    # ============================================================

    def p_bloque(self, p):
        """bloque : DEL_LLAVE_A lista_elem_bloque DEL_LLAVE_C"""
        p[0] = Bloque(p[2], p.lineno(1), self._col(p, 1))

    def p_lista_elem_bloque(self, p):
        """lista_elem_bloque : lista_elem_bloque elem_bloque
                             | empty"""
        if p[1] is None:
            p[0] = []
        elif len(p) == 3:
            if isinstance(p[2], list):
                p[1].extend(p[2])
            else:
                p[1].append(p[2])
            p[0] = p[1]

    def p_elem_bloque(self, p):
        """elem_bloque : decl_local
                       | instruccion"""
        # Rastrear si entre un `if` sin `else` y un `else` posterior se coló
        # alguna instrucción: es lo que distingue IL-SIN-033 de IL-SIN-032.
        elem = p[1]
        if isinstance(elem, IfStmt) and elem.bloque_else is None:
            self._if_sin_else = (elem.linea, elem.columna)
            self._elems_tras_if = 0
        elif self._if_sin_else is not None:
            self._elems_tras_if += 1
        p[0] = elem

    def p_subrutina_local(self, p):
        """elem_bloque : def_funcion
                       | def_procedimiento"""
        # IL-SIN-050: no se admiten subrutinas anidadas (§10.2)
        sub = p[1]
        self.error_manager.error_sintactico(
            'IL-SIN-050',
            f'No se permite declarar la subrutina "{sub.nombre}" dentro de un '
            f'bloque local; debe definirse al nivel más externo del archivo',
            sub.linea, sub.columna
        )
        p[0] = Bloque([], sub.linea, sub.columna)

    def p_decl_local(self, p):
        """decl_local : decl_variable
                      | decl_constante
                      | decl_arreglo
                      | decl_matriz"""
        p[0] = p[1]

    # ============================================================
    # Instrucciones
    # ============================================================

    def p_instruccion(self, p):
        """instruccion : lvalue op_asig expresion DEL_PUNTO_COMA
                       | inc_dec_stmt
                       | print_stmt
                       | read_stmt
                       | if_stmt
                       | while_stmt
                       | for_stmt
                       | foreach_stmt
                       | do_while_stmt
                       | switch_stmt
                       | match_stmt
                       | try_stmt
                       | return_stmt
                       | break_stmt
                       | continue_stmt
                       | call_stmt
                       | instruccion_error"""
        if len(p) == 5:
            p[0] = AssignStmt(p[1], p[2], p[3], p.lineno(1), self._col(p, 1))
        else:
            p[0] = p[1]

    # ---- Instrucciones a las que falta el ";" terminador ----
    # IL-SIN-010 es, por definicion del catalogo (§15.3), "punto y coma
    # faltante". Reconocer la forma sin terminador permite senalarla en su
    # propia linea y, sobre todo, SEGUIR analizando: sin estas producciones el
    # parser descarta tokens y pierde los errores siguientes (§15.8.2).

    def _falta_punto_coma(self, p, idx):
        self.error_manager.error_sintactico(
            'IL-SIN-010',
            'Falta el punto y coma ";" al final de la instrucción',
            p.lineno(idx), self._col(p, idx)
        )

    def p_decl_variable_sin_pc_error(self, p):
        """decl_variable : tipo IDENTIFICADOR OP_ASIG expresion
                         | tipo IDENTIFICADOR"""
        self._falta_punto_coma(p, 2)
        init = p[4] if len(p) == 5 else None
        p[0] = VarDecl(p[1], p[2], init, p.lineno(2), self._col(p, 2))

    def p_asignacion_sin_pc_error(self, p):
        """instruccion_error : lvalue op_asig expresion"""
        self._falta_punto_coma(p, 1)
        p[0] = AssignStmt(p[1], p[2], p[3], p.lineno(1), self._col(p, 1))

    def p_print_sin_pc_error(self, p):
        """print_stmt : KW_PRINT DEL_PAREN_A expresion DEL_PAREN_C"""
        self._falta_punto_coma(p, 1)
        p[0] = PrintStmt(p[3], p.lineno(1), self._col(p, 1))

    def p_punto_coma_aislado(self, p):
        """instruccion_error : DEL_PUNTO_COMA"""
        # IL-SIN-012: InvenioLang no define instrucción nula (§3.4.2)
        self.error_manager.error_sintactico(
            'IL-SIN-012',
            'Punto y coma aislado: InvenioLang no define una instrucción '
            'nula; use un bloque vacío { }',
            p.lineno(1), self._col(p, 1)
        )
        p[0] = Bloque([], p.lineno(1), self._col(p, 1))

    def p_punto_coma_tras_bloque(self, p):
        """instruccion_error : if_stmt DEL_PUNTO_COMA
                             | while_stmt DEL_PUNTO_COMA
                             | for_stmt DEL_PUNTO_COMA"""
        # IL-SIN-011: las instrucciones compuestas no llevan ; de cierre (§3.4.1)
        self.error_manager.error_sintactico(
            'IL-SIN-011',
            'Las instrucciones compuestas (if, while, for) no llevan punto y '
            'coma después de la llave de cierre',
            p.lineno(2), self._col(p, 2)
        )
        p[0] = p[1]

    def p_asignacion_encadenada(self, p):
        """instruccion_error : lvalue op_asig asig_sin_pc DEL_PUNTO_COMA"""
        # IL-SIN-020: la asignación no produce valor (§5.3.1)
        self.error_manager.error_sintactico(
            'IL-SIN-020',
            'Asignación encadenada: la asignación no produce un valor y no '
            'puede usarse dentro de una expresión',
            p.lineno(1), self._col(p, 1)
        )
        p[0] = AssignStmt(p[1], p[2], p[3].expr, p.lineno(1), self._col(p, 1))

    def p_lvalue(self, p):
        """lvalue : IDENTIFICADOR
                  | IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C
                  | IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_CORCHETE_A expresion DEL_CORCHETE_C"""
        if len(p) == 2:
            p[0] = VarLValue(p[1], p.lineno(1), self._col(p, 1))
        elif len(p) == 5:
            p[0] = ArrayLValue(p[1], p[3], p.lineno(1), self._col(p, 1))
        else:
            p[0] = MatrixLValue(p[1], p[3], p[6], p.lineno(1), self._col(p, 1))

    def p_op_asig(self, p):
        """op_asig : OP_ASIG
                   | OP_ASIG_SUMA
                   | OP_ASIG_RESTA
                   | OP_ASIG_MULT
                   | OP_ASIG_DIV
                   | OP_ASIG_MOD"""
        mapa = {
            'OP_ASIG': '=', 'OP_ASIG_SUMA': '+=', 'OP_ASIG_RESTA': '-=',
            'OP_ASIG_MULT': '*=', 'OP_ASIG_DIV': '/=', 'OP_ASIG_MOD': '%=',
        }
        p[0] = mapa[p.slice[1].type]

    def p_inc_dec_stmt(self, p):
        """inc_dec_stmt : OP_INC IDENTIFICADOR DEL_PUNTO_COMA
                        | OP_DEC IDENTIFICADOR DEL_PUNTO_COMA
                        | IDENTIFICADOR OP_INC DEL_PUNTO_COMA
                        | IDENTIFICADOR OP_DEC DEL_PUNTO_COMA"""
        if p.slice[1].type in ('OP_INC', 'OP_DEC'):
            p[0] = IncDecStmt(p[2], p[1], True, p.lineno(2), self._col(p, 2))
        else:
            p[0] = IncDecStmt(p[1], p[2], False, p.lineno(1), self._col(p, 1))

    def p_print_stmt(self, p):
        """print_stmt : KW_PRINT DEL_PAREN_A expresion DEL_PAREN_C DEL_PUNTO_COMA"""
        p[0] = PrintStmt(p[3], p.lineno(1), self._col(p, 1))

    def p_print_stmt_sin_args(self, p):
        """print_stmt : KW_PRINT DEL_PAREN_A DEL_PAREN_C DEL_PUNTO_COMA"""
        # IL-SIN-025: print/imprimir requiere exactamente un argumento (§7.1)
        self.error_manager.error_sintactico(
            'IL-SIN-025',
            'print / imprimir requiere exactamente un argumento',
            p.lineno(1), self._col(p, 1)
        )
        p[0] = PrintStmt(Literal('', 'string', p.lineno(1), self._col(p, 1)),
                         p.lineno(1), self._col(p, 1))

    def p_print_stmt_multi_args(self, p):
        """print_stmt : KW_PRINT DEL_PAREN_A expresion DEL_COMA lista_args DEL_PAREN_C DEL_PUNTO_COMA"""
        # IL-SIN-026: print/imprimir no admite varios argumentos (§7.1)
        self.error_manager.error_sintactico(
            'IL-SIN-026',
            'print / imprimir admite un solo argumento; use una instrucción '
            'de salida por cada valor',
            p.lineno(1), self._col(p, 1)
        )
        p[0] = PrintStmt(p[3], p.lineno(1), self._col(p, 1))

    def p_read_stmt(self, p):
        """read_stmt : KW_READ DEL_PAREN_A expresion DEL_PAREN_C DEL_PUNTO_COMA"""
        # El argumento debe ser un identificador simple (§7.2.1). Se acepta una
        # expresión en la gramática para poder emitir IL-SIN-027 en lugar de un
        # error de sintaxis genérico.
        arg = p[3]
        if isinstance(arg, Identifier):
            p[0] = ReadStmt(arg.nombre, p.lineno(1), self._col(p, 1))
        else:
            self.error_manager.error_sintactico(
                'IL-SIN-027',
                'El argumento de read / leer debe ser un identificador de '
                'variable, no una expresión',
                p.lineno(1), self._col(p, 1)
            )
            p[0] = ReadStmt('<inválido>', p.lineno(1), self._col(p, 1))

    def p_if_stmt(self, p):
        """if_stmt : KW_IF DEL_PAREN_A expresion DEL_PAREN_C bloque
                   | KW_IF DEL_PAREN_A expresion DEL_PAREN_C bloque KW_ELSE bloque"""
        if len(p) == 6:
            p[0] = IfStmt(p[3], p[5], None, p.lineno(1), self._col(p, 1))
        else:
            p[0] = IfStmt(p[3], p[5], p[7], p.lineno(1), self._col(p, 1))

    def p_if_stmt_sin_llaves(self, p):
        """if_stmt : KW_IF DEL_PAREN_A expresion DEL_PAREN_C instruccion
                   | KW_IF DEL_PAREN_A expresion DEL_PAREN_C instruccion KW_ELSE bloque"""
        # IL-SIN-031: el cuerpo de una instrucción compuesta debe ser un bloque
        # entre llaves, aunque contenga una sola instrucción (§8.1)
        self.error_manager.error_sintactico(
            'IL-SIN-031',
            'El cuerpo de if / si debe ir entre llaves { }',
            p.lineno(1), self._col(p, 1)
        )
        cuerpo = Bloque([p[5]], p.lineno(1), self._col(p, 1))
        alterno = p[7] if len(p) == 8 else None
        p[0] = IfStmt(p[3], cuerpo, alterno, p.lineno(1), self._col(p, 1))

    def p_if_stmt_sin_parentesis(self, p):
        """if_stmt : KW_IF expr_rel bloque
                   | KW_IF expr_rel bloque KW_ELSE bloque"""
        # IL-SIN-030: la condición debe ir entre paréntesis (§8.1). Se usa
        # expr_rel (no expresion) para no solaparse con la forma correcta,
        # cuya condición siempre empieza por "(".
        self.error_manager.error_sintactico(
            'IL-SIN-030',
            'La condición de if / si debe ir entre paréntesis: if (condición) { }',
            p.lineno(1), self._col(p, 1)
        )
        alterno = p[5] if len(p) == 6 else None
        p[0] = IfStmt(p[2], p[3], alterno, p.lineno(1), self._col(p, 1))

    def p_while_stmt_sin_parentesis(self, p):
        """while_stmt : KW_WHILE expr_rel bloque"""
        # IL-SIN-035: la condición debe ir entre paréntesis (§9.1)
        self.error_manager.error_sintactico(
            'IL-SIN-035',
            'La condición de while / mientras debe ir entre paréntesis: '
            'while (condición) { }',
            p.lineno(1), self._col(p, 1)
        )
        p[0] = WhileStmt(p[2], p[3], p.lineno(1), self._col(p, 1))

    def p_lvalue_invalido(self, p):
        """instruccion_error : ENTERO_LIT op_asig expresion DEL_PUNTO_COMA
                             | REAL_LIT op_asig expresion DEL_PUNTO_COMA
                             | TEXTO_LIT op_asig expresion DEL_PUNTO_COMA"""
        # IL-SEM-005: el lado izquierdo de una asignación debe ser un
        # identificador de variable (§14.4)
        self.error_manager.error_semantico(
            'IL-SEM-005',
            'El lado izquierdo de una asignación debe ser una variable, '
            'no un literal',
            p.lineno(1), self._col(p, 1)
        )
        p[0] = Bloque([], p.lineno(1), self._col(p, 1))

    # IL-SIN-033 (instrucción entre el bloque then y else) NO se implementa
    # como producción de la gramática: la regla
    #   if_stmt : KW_IF "(" expresion ")" bloque instruccion KW_ELSE bloque
    # es inherentemente ambigua con el caso "if sin else seguido de otra
    # instrucción", que es el patrón más común del lenguaje, y provoca un
    # conflicto reduce/reduce que hace fallar programas válidos. Un `else`
    # separado del `if` por una instrucción se reporta como IL-SIN-032
    # (cláusula else sin if previo), que es un diagnóstico correcto y útil.

    def p_else_huerfano(self, p):
        """instruccion_error : KW_ELSE bloque"""
        # Un `else` que el parser no pudo ligar a su `if` admite dos lecturas
        # (§8.2). Si hay un `if` sin `else` antes y entre ambos se colaron
        # instrucciones, el error es esa separación (IL-SIN-033); si no hay
        # ningún `if` previo, el `else` sobra (IL-SIN-032).
        if self._if_sin_else is not None and self._elems_tras_if > 0:
            self.error_manager.error_sintactico(
                'IL-SIN-033',
                f'No puede aparecer una instrucción entre el bloque del if '
                f'(línea {self._if_sin_else[0]}) y su cláusula else / sino',
                p.lineno(1), self._col(p, 1)
            )
        else:
            self.error_manager.error_sintactico(
                'IL-SIN-032',
                'Cláusula else / sino sin un if previo en el mismo alcance',
                p.lineno(1), self._col(p, 1)
            )
        self._if_sin_else = None
        self._elems_tras_if = 0
        p[0] = p[2]

    def p_while_stmt(self, p):
        """while_stmt : KW_WHILE DEL_PAREN_A expresion DEL_PAREN_C bloque"""
        p[0] = WhileStmt(p[3], p[5], p.lineno(1), self._col(p, 1))

    def p_while_stmt_sin_llaves(self, p):
        """while_stmt : KW_WHILE DEL_PAREN_A expresion DEL_PAREN_C instruccion"""
        # IL-SIN-031: cuerpo de while sin llaves (§9.1)
        self.error_manager.error_sintactico(
            'IL-SIN-031',
            'El cuerpo de while / mientras debe ir entre llaves { }',
            p.lineno(1), self._col(p, 1)
        )
        p[0] = WhileStmt(p[3], Bloque([p[5]], p.lineno(1), self._col(p, 1)),
                         p.lineno(1), self._col(p, 1))

    def p_for_stmt(self, p):
        """for_stmt : KW_FOR DEL_PAREN_A for_init DEL_PUNTO_COMA for_cond DEL_PUNTO_COMA for_act DEL_PAREN_C bloque"""
        p[0] = ForStmt(p[3], p[5], p[7], p[9], p.lineno(1), self._col(p, 1))

    def p_for_init(self, p):
        """for_init : decl_var_sin_pc
                    | asig_sin_pc
                    | empty"""
        p[0] = p[1]

    def p_for_cond(self, p):
        """for_cond : expresion
                    | empty"""
        p[0] = p[1]

    def p_for_act(self, p):
        """for_act : asig_sin_pc
                   | inc_dec_sin_pc
                   | empty"""
        p[0] = p[1]

    def p_decl_var_sin_pc(self, p):
        """decl_var_sin_pc : tipo IDENTIFICADOR
                           | tipo IDENTIFICADOR OP_ASIG expresion"""
        if len(p) == 3:
            p[0] = ForInitVar(p[1], p[2], None, p.lineno(2), self._col(p, 2))
        else:
            p[0] = ForInitVar(p[1], p[2], p[4], p.lineno(2), self._col(p, 2))

    def p_asig_sin_pc(self, p):
        """asig_sin_pc : lvalue op_asig expresion"""
        p[0] = ForInitAsig(p[1], p[2], p[3], p.lineno(1), self._col(p, 1))

    def p_inc_dec_sin_pc(self, p):
        """inc_dec_sin_pc : OP_INC IDENTIFICADOR
                          | OP_DEC IDENTIFICADOR
                          | IDENTIFICADOR OP_INC
                          | IDENTIFICADOR OP_DEC"""
        if p.slice[1].type in ('OP_INC', 'OP_DEC'):
            p[0] = ForInitIncDec(p[2], p[1], True, p.lineno(2), self._col(p, 2))
        else:
            p[0] = ForInitIncDec(p[1], p[2], False, p.lineno(1), self._col(p, 1))

    def p_foreach_stmt(self, p):
        """foreach_stmt : KW_FOREACH DEL_PAREN_A tipo IDENTIFICADOR DEL_DOSPUNTOS expresion DEL_PAREN_C bloque"""
        p[0] = ForEachStmt(p[3], p[4], p[6], p[8], p.lineno(1), self._col(p, 1))

    def p_foreach_stmt_clase(self, p):
        """foreach_stmt : KW_FOREACH DEL_PAREN_A IDENTIFICADOR IDENTIFICADOR DEL_DOSPUNTOS expresion DEL_PAREN_C bloque"""
        # Variable de recorrido de tipo clase (Etapa 12.1), p. ej.
        # para_cada (Persona p : personas) { ... } -- mismo criterio que
        # decl_variable_clase: "IDENTIFICADOR IDENTIFICADOR" tras un token
        # de apertura propio (KW_FOREACH) no colisiona con nada mas.
        p[0] = ForEachStmt(p[3], p[4], p[6], p[8], p.lineno(1), self._col(p, 1))

    def p_return_stmt(self, p):
        """return_stmt : KW_RETURN DEL_PUNTO_COMA
                       | KW_RETURN expresion DEL_PUNTO_COMA"""
        if len(p) == 3:
            p[0] = ReturnStmt(None, p.lineno(1), self._col(p, 1))
        else:
            p[0] = ReturnStmt(p[2], p.lineno(1), self._col(p, 1))

    def p_break_stmt(self, p):
        """break_stmt : KW_BREAK DEL_PUNTO_COMA"""
        p[0] = BreakStmt(p.lineno(1), self._col(p, 1))

    def p_continue_stmt(self, p):
        """continue_stmt : KW_CONTINUE DEL_PUNTO_COMA"""
        p[0] = ContinueStmt(p.lineno(1), self._col(p, 1))

    def p_call_stmt(self, p):
        """call_stmt : IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA"""
        p[0] = CallStmt(p[1], p[3], p.lineno(1), self._col(p, 1))

    # ============================================================
    # Etapa 6: lenguaje estructurado completo
    # ============================================================

    def p_switch_stmt(self, p):
        """switch_stmt : KW_SWITCH DEL_PAREN_A expresion DEL_PAREN_C DEL_LLAVE_A lista_casos DEL_LLAVE_C
                       | KW_SWITCH DEL_PAREN_A expresion DEL_PAREN_C DEL_LLAVE_A lista_casos KW_DEFAULT DEL_DOSPUNTOS lista_elem_bloque DEL_LLAVE_C"""
        if len(p) == 8:
            p[0] = SwitchStmt(p[3], p[6], None, p.lineno(1), self._col(p, 1))
        else:
            bloque_default = Bloque(p[9], p.lineno(7), self._col(p, 7))
            p[0] = SwitchStmt(p[3], p[6], bloque_default, p.lineno(1), self._col(p, 1))

    def p_lista_casos(self, p):
        """lista_casos : lista_casos caso
                       | empty"""
        if p[1] is None:
            p[0] = []
        else:
            p[1].append(p[2])
            p[0] = p[1]

    def p_caso(self, p):
        """caso : KW_CASE literal_caso DEL_DOSPUNTOS lista_elem_bloque"""
        bloque = Bloque(p[4], p.lineno(1), self._col(p, 1))
        p[0] = Caso(p[2], bloque, p.lineno(1), self._col(p, 1))

    def p_literal_caso(self, p):
        """literal_caso : ENTERO_LIT
                        | TEXTO_LIT
                        | bool_lit"""
        if p.slice[1].type == 'ENTERO_LIT':
            p[0] = Literal(p[1], 'int', p.lineno(1), self._col(p, 1))
        elif p.slice[1].type == 'TEXTO_LIT':
            p[0] = Literal(p[1], 'string', p.lineno(1), self._col(p, 1))
        else:
            p[0] = p[1]  # bool_lit ya construye un Literal

    def p_literal_caso_negativo(self, p):
        """literal_caso : OP_RESTA ENTERO_LIT"""
        p[0] = Literal(-p[2], 'int', p.lineno(1), self._col(p, 1))

    def p_match_stmt(self, p):
        """match_stmt : KW_MATCH DEL_PAREN_A expresion DEL_PAREN_C DEL_LLAVE_A lista_casos_match DEL_LLAVE_C
                      | KW_MATCH DEL_PAREN_A expresion DEL_PAREN_C DEL_LLAVE_A lista_casos_match KW_DEFAULT DEL_DOSPUNTOS lista_elem_bloque DEL_LLAVE_C"""
        # Etapa 12.9/12.10: construccion deliberadamente separada de
        # switch (KW_MATCH es un token de apertura propio, nunca antes
        # usado en instruccion -- sin colision de prefijo). Reutiliza
        # KW_DEFAULT/lista_elem_bloque exactamente como switch para el
        # comodin, mismo criterio de bajo riesgo que reusar
        # KW_CASE/KW_DEFAULT dentro de un no-terminal padre distinto
        # (caso_match, en vez de caso).
        if len(p) == 8:
            p[0] = MatchStmt(p[3], p[6], None, p.lineno(1), self._col(p, 1))
        else:
            bloque_comodin = Bloque(p[9], p.lineno(7), self._col(p, 7))
            p[0] = MatchStmt(p[3], p[6], bloque_comodin, p.lineno(1), self._col(p, 1))

    def p_lista_casos_match(self, p):
        """lista_casos_match : lista_casos_match caso_match
                             | empty"""
        if p[1] is None:
            p[0] = []
        else:
            p[1].append(p[2])
            p[0] = p[1]

    def p_caso_match(self, p):
        """caso_match : KW_CASE IDENTIFICADOR DEL_DOSPUNTOS lista_elem_bloque
                      | KW_CASE IDENTIFICADOR DEL_PAREN_A lista_identificadores DEL_PAREN_C DEL_DOSPUNTOS lista_elem_bloque"""
        # Las dos alternativas divergen en el lookahead inmediatamente
        # despues de IDENTIFICADOR (DEL_DOSPUNTOS vs DEL_PAREN_A) --
        # mismo perfil de riesgo bajo que miembro_enum.
        if len(p) == 5:
            bloque = Bloque(p[4], p.lineno(1), self._col(p, 1))
            p[0] = CasoMatch(p[2], [], bloque, p.lineno(1), self._col(p, 1))
        else:
            bloque = Bloque(p[7], p.lineno(1), self._col(p, 1))
            p[0] = CasoMatch(p[2], p[4], bloque, p.lineno(1), self._col(p, 1))

    def p_do_while_stmt(self, p):
        """do_while_stmt : KW_DO bloque KW_WHILE DEL_PAREN_A expresion DEL_PAREN_C DEL_PUNTO_COMA"""
        p[0] = DoWhileStmt(p[2], p[5], p.lineno(1), self._col(p, 1))

    def p_try_stmt(self, p):
        """try_stmt : KW_TRY bloque KW_CATCH DEL_PAREN_A IDENTIFICADOR DEL_PAREN_C bloque"""
        p[0] = TryStmt(p[2], p[5], p[7], p.lineno(1), self._col(p, 1))

    # ============================================================
    # Expresiones (precedencia mediante PLY + estructural)
    # ============================================================

    def p_expresion(self, p):
        """expresion : expr_coalesce
                     | expr_coalesce DEL_INTERROGACION expresion DEL_DOSPUNTOS expresion"""
        # Operador ternario (Etapa 6), asociativo a la derecha: la segunda
        # rama recursiona sobre `expresion` completa, así que un ternario
        # anidado en la rama "si_falso" (a?b:c?d:e) se agrupa como
        # a?b:(c?d:e) sin necesidad de una entrada de precedencia extra.
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = TernaryExpr(p[1], p[3], p[5], p.lineno(2), self._col(p, 2))

    def p_expr_coalesce(self, p):
        """expr_coalesce : expr_or OP_COALESCENCIA expr_coalesce
                         | expr_or"""
        # Coalescencia nula (Etapa 12.2): `a ?? b` vale `a` si no es nulo,
        # si no vale `b`. Asociativo a la derecha (misma tactica que el
        # ternario de arriba: la segunda rama recursiona sobre
        # `expr_coalesce`), y liga mas fuerte que el ternario pero mas
        # flojo que `||` -- mismo criterio que C#/Kotlin. Reutiliza
        # BinaryOp con operador '??' en vez de un nodo AST nuevo, igual
        # que los operadores bit a bit de la Etapa 11.9.
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = BinaryOp('??', p[1], p[3], p.lineno(2), self._col(p, 2))

    def p_expr_or(self, p):
        """expr_or : expr_or OP_OR expr_and
                   | expr_and"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_and(self, p):
        """expr_and : expr_and OP_AND expr_bitor
                    | expr_bitor"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    # ---- Bit a bit (Etapa 11) -- tres niveles nuevos entre && y ==,
    # mismo orden clasico de C: | (menor precedencia) < ^ < & (mayor) ----

    def p_expr_bitor(self, p):
        """expr_bitor : expr_bitor OP_BITOR expr_bitxor
                      | expr_bitxor"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_bitxor(self, p):
        """expr_bitxor : expr_bitxor OP_BITXOR expr_bitand
                       | expr_bitand"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_bitand(self, p):
        """expr_bitand : expr_bitand OP_BITAND expr_igual
                       | expr_igual"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_igual(self, p):
        """expr_igual : expr_igual OP_IGUAL expr_rel
                      | expr_igual OP_DISTINTO expr_rel
                      | expr_rel"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_rel(self, p):
        """expr_rel : expr_rel OP_MENOR expr_shift
                    | expr_rel OP_MAYOR expr_shift
                    | expr_rel OP_MENOR_IGUAL expr_shift
                    | expr_rel OP_MAYOR_IGUAL expr_shift
                    | expr_shift"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_shift(self, p):
        """expr_shift : expr_shift OP_SHL expr_sum
                      | expr_shift OP_SHR expr_sum
                      | expr_sum"""
        # Desplazamiento de bits (Etapa 11): mismo nivel que ocupa en C,
        # entre relacional y aditivo.
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_sum(self, p):
        """expr_sum : expr_sum OP_SUMA expr_mul
                    | expr_sum OP_RESTA expr_mul
                    | expr_mul"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_mul(self, p):
        """expr_mul : expr_mul OP_MULT expr_unaria
                    | expr_mul OP_DIV expr_unaria
                    | expr_mul OP_MOD expr_unaria
                    | expr_unaria"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_unaria(self, p):
        """expr_unaria : OP_RESTA expr_unaria %prec UMINUS
                       | OP_NOT expr_unaria
                       | OP_BITNOT expr_unaria
                       | OP_INC expr_primaria
                       | OP_DEC expr_primaria
                       | expr_primaria OP_INC
                       | expr_primaria OP_DEC
                       | expr_primaria"""
        if len(p) == 3:
            if p.slice[1].type in ('OP_RESTA', 'OP_NOT', 'OP_BITNOT'):
                # Operador unario: -expr, !expr o ~expr (Etapa 11)
                p[0] = UnaryOp(p[1], p[2], True, p.lineno(1), self._col(p, 1))
            elif p.slice[1].type in ('OP_INC', 'OP_DEC'):
                # Incremento/decremento prefijo: ++expr o --expr
                p[0] = UnaryOp(p[1], p[2], True, p.lineno(1), self._col(p, 1))
            else:
                # expr ++ o expr -- (postfijo)
                p[0] = UnaryOp(p[2], p[1], False, p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_primaria(self, p):
        """expr_primaria : ENTERO_LIT
                         | REAL_LIT
                         | TEXTO_LIT
                         | bool_lit
                         | IDENTIFICADOR
                         | acceso_arreglo
                         | acceso_matriz
                         | llamada_funcion
                         | DEL_PAREN_A expresion DEL_PAREN_C"""
        if isinstance(p[1], int) and not isinstance(p[1], bool):
            p[0] = Literal(p[1], 'int', p.lineno(1), self._col(p, 1))
        elif isinstance(p[1], float):
            p[0] = Literal(p[1], 'float', p.lineno(1), self._col(p, 1))
        elif p.slice[1].type == 'TEXTO_LIT':
            p[0] = Literal(p[1], 'string', p.lineno(1), self._col(p, 1))
        elif p.slice[1].type == 'IDENTIFICADOR':
            p[0] = Identifier(p[1], p.lineno(1), self._col(p, 1))
        elif len(p) == 4:
            p[0] = p[2]
        else:
            p[0] = p[1]

    def p_bool_lit(self, p):
        """bool_lit : KW_TRUE
                    | KW_FALSE"""
        mapa = {'KW_TRUE': True, 'KW_FALSE': False}
        p[0] = Literal(mapa[p.slice[1].type], 'bool', p.lineno(1), self._col(p, 1))

    def p_acceso_arreglo(self, p):
        """acceso_arreglo : IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C"""
        p[0] = ArrayAccess(p[1], p[3], p.lineno(1), self._col(p, 1))

    def p_acceso_matriz(self, p):
        """acceso_matriz : IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_CORCHETE_A expresion DEL_CORCHETE_C"""
        p[0] = MatrixAccess(p[1], p[3], p[6], p.lineno(1), self._col(p, 1))

    def p_llamada_funcion(self, p):
        """llamada_funcion : IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C"""
        p[0] = FunctionCall(p[1], p[3], p.lineno(1), self._col(p, 1))

    def p_lista_args(self, p):
        """lista_args : lista_args DEL_COMA expresion
                      | expresion
                      | empty"""
        if p[1] is None:
            p[0] = []
        elif len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]
        else:
            p[0] = [p[1]]

    # ============================================================
    # POO (InvenioLang 2.0 -- docs/InvenioLang_2.0_POO.md)
    # ============================================================
    #
    # Limitacion deliberada (documentada en la spec, no un descuido): el
    # acceso a miembro es de UN SOLO NIVEL -- `receptor.miembro`, con
    # receptor un IDENTIFICADOR, `este`/this o `padre`/super. No se admite
    # encadenar (a.b.c()) ni indexar un miembro (obj.campo[i]). Se escribe
    # de forma repetitiva (una alternativa por cada receptor posible) en
    # vez de introducir un nonterminal `receptor` intermedio, para evitar
    # el riesgo de un conflicto reduce/reduce en LALR(1) al decidir cuando
    # reducirlo antes de ver el "." que lo sigue.

    def _construir_class_decl(self, nombre, padre, miembros, es_abstracta,
                              parametro_tipo, linea, columna, interfaces=None,
                              es_interfaz=False):
        """Separa `miembros` en atributos/métodos/constructores y valida
        IL-POO-019 (cada constructor debe llamarse igual que la clase) --
        compartido por las 4 formas de `class_decl` (normal, abstracta,
        genérica, interfaz). Una clase puede declarar VARIOS constructores
        (Etapa 10: sobrecarga) -- la detección de firma duplicada exacta
        (misma aridad/tipos de parámetros) se hace en semantic.py, igual
        que ya pasa con la sobrecarga de métodos, porque necesita resolver
        tipos de parámetro (clases declaradas más adelante en el
        archivo)."""
        atributos = [m for m in miembros if isinstance(m, AttrDecl)]
        metodos = [m for m in miembros if isinstance(m, MethodDecl)]
        constructores = [m for m in miembros if isinstance(m, ConstructorDecl)]

        for ctor in constructores:
            if ctor.nombre != nombre:
                self.error_manager.error_poo(
                    'IL-POO-019',
                    f'El constructor debe llamarse igual que la clase "{nombre}", '
                    f'no "{ctor.nombre}"',
                    ctor.linea, ctor.columna
                )

        return ClassDecl(nombre, padre, atributos, metodos, constructores,
                         es_abstracta=es_abstracta, parametro_tipo=parametro_tipo,
                         linea=linea, columna=columna, interfaces=interfaces,
                         es_interfaz=es_interfaz)

    def p_class_decl(self, p):
        """class_decl : KW_CLASS IDENTIFICADOR lista_implementa DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C
                       | KW_CLASS IDENTIFICADOR KW_EXTENDS IDENTIFICADOR lista_implementa DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C
                       | KW_ABSTRACT KW_CLASS IDENTIFICADOR lista_implementa DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C
                       | KW_ABSTRACT KW_CLASS IDENTIFICADOR KW_EXTENDS IDENTIFICADOR lista_implementa DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C"""
        # abstracta/abstract (Etapa 7): KW_ABSTRACT es un token de apertura
        # distinto de KW_CLASS, así que desambigua sin riesgo -- el resto de
        # la producción es idéntica a la forma no abstracta, corrida un
        # índice hacia la derecha. `implementa`/`implements` (Etapa 12.3) se
        # localiza SIEMPRE 4 posiciones antes del final (justo antes de
        # DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C), sin importar cuántas
        # piezas opcionales lo precedan -- evita repetir la aritmética de
        # índices `d` para una pieza más, que ya está bastante cargada.
        es_abstracta = p.slice[1].type == 'KW_ABSTRACT'
        d = 1 if es_abstracta else 0
        interfaces = p[len(p) - 4]
        if len(p) - d == 7:
            nombre, padre, miembros = p[2 + d], None, p[5 + d]
        else:
            nombre, padre, miembros = p[2 + d], p[4 + d], p[7 + d]
        p[0] = self._construir_class_decl(nombre, padre, miembros, es_abstracta, None,
                                          p.lineno(2 + d), self._col(p, 2 + d),
                                          interfaces=interfaces)

    def p_lista_implementa_vacia(self, p):
        """lista_implementa : empty"""
        p[0] = []

    def p_lista_implementa(self, p):
        """lista_implementa : KW_IMPLEMENTS lista_identificadores"""
        # implementa/implements (Etapa 12.3): lista de interfaces que la
        # clase debe satisfacer -- distinto de `hereda`/`extends` (siempre
        # singular). KW_IMPLEMENTS es un token de apertura propio, sin
        # colisión con nada de lo que ya sigue a un IDENTIFICADOR de clase.
        p[0] = p[2]

    def p_class_decl_generica(self, p):
        """class_decl : KW_CLASS IDENTIFICADOR OP_MENOR IDENTIFICADOR OP_MAYOR DEL_LLAVE_A lista_miembros_clase DEL_LLAVE_C"""
        # Genéricos (Etapa 7, sustitución sintáctica -- ver semantic.py::
        # _expandir_genericos). Alcance deliberadamente acotado: un solo
        # parámetro de tipo, sin herencia combinada con genéricos. El "< >"
        # aquí NO es el operador relacional -- reutiliza los mismos tokens
        # OP_MENOR/OP_MAYOR, pero solo en esta posición sintáctica exacta
        # (justo después de "class NOMBRE"), donde ninguna otra regla
        # espera esa secuencia; verificado sin conflictos LALR nuevos.
        p[0] = self._construir_class_decl(p[2], None, p[7], False, p[4],
                                          p.lineno(2), self._col(p, 2))

    def p_lista_miembros_clase(self, p):
        """lista_miembros_clase : lista_miembros_clase miembro_clase
                                | empty"""
        if p[1] is None:
            p[0] = []
        else:
            p[1].append(p[2])
            p[0] = p[1]

    def p_visibilidad(self, p):
        """visibilidad : KW_PUBLIC
                       | KW_PRIVATE"""
        p[0] = 'publico' if p.slice[1].type == 'KW_PUBLIC' else 'privado'

    # ---- Modificadores de miembro (Etapa 7) ----
    # `estatico`/`abstracto` van despues de la visibilidad. Un atributo solo
    # admite `estatico`; un metodo admite `estatico` O `abstracto` (nunca
    # ambos -- la gramatica ya lo hace mutuamente excluyente al ser
    # alternativas separadas de UN solo modificador).

    def p_modificador_miembro(self, p):
        """modificador_miembro : KW_STATIC
                               | KW_ABSTRACT
                               | empty"""
        # Un solo no terminal para atributos Y métodos: `mod_attr`/
        # `mod_metodo` separados (con las mismas dos alternativas KW_STATIC/
        # empty en común) resultaron indistinguibles para LALR(1) en este
        # punto de la gramática -- el parser no puede decidir a cuál de los
        # dos reducir un `empty`/`KW_STATIC` antes de ver qué sigue,
        # produciendo un conflicto reduce/reduce real (verificado con
        # `parser.py(debug=True)`). Con un solo no terminal compartido no
        # hay ambigüedad que resolver; que "abstracto" no tenga sentido en
        # un atributo se valida en semantic.py (IL-POO-023), mismo criterio
        # que ya usa el proyecto para "void x;".
        tipo = p.slice[1].type
        p[0] = 'static' if tipo == 'KW_STATIC' else 'abstract' if tipo == 'KW_ABSTRACT' else None

    def p_cuerpo_metodo(self, p):
        """cuerpo_metodo : bloque
                         | DEL_PUNTO_COMA"""
        # Un metodo abstracto (Etapa 7) no lleva cuerpo -- termina en ';'.
        # La gramatica acepta ambas formas para cualquier metodo; que
        # 'abstracto' concuerde con "sin cuerpo" (y viceversa) se valida en
        # semantic.py (IL-POO-022), mismo criterio que ya usa el proyecto
        # para "void x;" (sintacticamente valido, error semantico aparte).
        p[0] = None if p.slice[1].type == 'DEL_PUNTO_COMA' else p[1]

    def _validar_mod_attr(self, mod, p, idx):
        """IL-POO-023: 'abstracto' no tiene sentido en un atributo (solo en
        métodos). Se valida aquí, no en la gramática, mismo criterio que
        'void x;' (§16.5)."""
        if mod == 'abstract':
            self.error_manager.error_poo(
                'IL-POO-023',
                'El modificador "abstracto"/"abstract" no es válido en un '
                'atributo, solo en métodos',
                p.lineno(idx), self._col(p, idx)
            )

    def p_miembro_atributo(self, p):
        """miembro_clase : visibilidad modificador_miembro tipo IDENTIFICADOR DEL_PUNTO_COMA
                         | visibilidad modificador_miembro tipo IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA"""
        self._validar_mod_attr(p[2], p, 4)
        init = p[6] if len(p) == 8 else None
        p[0] = AttrDecl(p[1], p[3], p[4], init, es_estatico=(p[2] == 'static'),
                        linea=p.lineno(4), columna=self._col(p, 4))

    def p_miembro_metodo(self, p):
        """miembro_clase : visibilidad modificador_miembro tipo IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C cuerpo_metodo
                         | visibilidad modificador_miembro KW_VOID IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C cuerpo_metodo"""
        tipo_retorno = 'void' if p.slice[3].type == 'KW_VOID' else p[3]
        mod = p[2]
        p[0] = MethodDecl(p[1], tipo_retorno, p[4], p[6], p[8],
                          es_estatico=(mod == 'static'), es_abstracto=(mod == 'abstract'),
                          linea=p.lineno(4), columna=self._col(p, 4))

    def p_miembro_constructor(self, p):
        """miembro_clase : IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque"""
        p[0] = ConstructorDecl(p[1], p[3], p[5], linea=p.lineno(1), columna=self._col(p, 1))

    def p_miembro_constructor_visibilidad(self, p):
        """miembro_clase : visibilidad KW_CONSTRUCTOR IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque"""
        # Etapa 11: constructor con visibilidad explicita (privado, para el
        # patron Singleton). PRIMER INTENTO (descartado): `visibilidad
        # IDENTIFICADOR (...)` sin la palabra clave -- comparte el prefijo
        # `visibilidad IDENTIFICADOR` con un atributo/metodo de tipo clase
        # (`publico Persona amigo;`), y con solo 1 token de lookahead
        # LALR(1) no puede distinguir "es el nombre del constructor" de "es
        # el tipo del atributo" hasta ver el SIGUIENTE token -- probado con
        # parser.py(debug=True): rompía el parseo real de atributos/métodos
        # de tipo clase con visibilidad explícita (poo_completo.inv y
        # varios de Estructuras de Datos fallaban con IL-SIN-010).
        # Con la palabra clave `constructor` de por medio, el token que
        # sigue a `visibilidad` es KW_CONSTRUCTOR (no IDENTIFICADOR), un
        # punto de decisión limpio -- verificado sin conflictos nuevos.
        p[0] = ConstructorDecl(p[3], p[5], p[7], visibilidad=p[1],
                               linea=p.lineno(3), columna=self._col(p, 3))

    def _receptor(self, p, idx):
        """Construye el nodo del receptor de un acceso a miembro a partir del
        token en la posicion idx (IDENTIFICADOR, KW_THIS o KW_SUPER)."""
        tipo = p.slice[idx].type
        if tipo == 'KW_THIS':
            return ThisExpr(p.lineno(idx), self._col(p, idx))
        if tipo == 'KW_SUPER':
            return SuperExpr(p.lineno(idx), self._col(p, idx))
        return Identifier(p[idx], p.lineno(idx), self._col(p, idx))

    def p_expr_primaria_new(self, p):
        """expr_primaria : KW_NEW IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C"""
        p[0] = NewExpr(p[2], p[4], p.lineno(1), self._col(p, 1))

    def p_expr_primaria_new_generico(self, p):
        """expr_primaria : KW_NEW IDENTIFICADOR OP_MENOR tipo_generico_arg OP_MAYOR DEL_PAREN_A lista_args DEL_PAREN_C"""
        # nuevo Pila<entero>(...) (Etapa 7, genéricos). Tras "new IDENT" el
        # siguiente token decide sin ambigüedad entre esta forma y la no
        # genérica: '(' aquí, '<' allá.
        nombre_clase = f'{p[2]}<{p[4]}>'
        p[0] = NewExpr(nombre_clase, p[7], p.lineno(1), self._col(p, 1))

    def p_expr_primaria_this(self, p):
        """expr_primaria : KW_THIS"""
        p[0] = ThisExpr(p.lineno(1), self._col(p, 1))

    def p_expr_primaria_null(self, p):
        """expr_primaria : KW_NULL"""
        # nulo/null (Estructuras de Datos): ausencia de objeto, solo
        # compatible con tipos de clase (ver _compatible en type_checker.py).
        p[0] = NullExpr(p.lineno(1), self._col(p, 1))

    def p_expr_primaria_miembro(self, p):
        """expr_primaria : IDENTIFICADOR DEL_PUNTO IDENTIFICADOR
                         | KW_THIS DEL_PUNTO IDENTIFICADOR
                         | KW_SUPER DEL_PUNTO IDENTIFICADOR"""
        p[0] = MemberAccess(self._receptor(p, 1), p[3], p.lineno(1), self._col(p, 1))

    def p_expr_primaria_miembro_seguro(self, p):
        """expr_primaria : IDENTIFICADOR OP_ACCESO_SEGURO IDENTIFICADOR"""
        # Acceso seguro (Etapa 12.2): solo sobre un receptor IDENTIFICADOR
        # -- `este`/`padre` nunca son nulos dentro de un metodo (ya lo
        # verifica IL-POO-011/012), asi que `?.` sobre ellos no aporta
        # nada y se deja fuera a proposito para no ampliar mas la
        # gramatica sin necesidad real.
        p[0] = MemberAccess(Identifier(p[1], p.lineno(1), self._col(p, 1)), p[3],
                            p.lineno(1), self._col(p, 1), es_seguro=True)

    def p_expr_primaria_llamada_metodo(self, p):
        """expr_primaria : IDENTIFICADOR DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C
                         | KW_THIS DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C
                         | KW_SUPER DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C"""
        p[0] = MethodCallExpr(self._receptor(p, 1), p[3], p[5],
                              p.lineno(1), self._col(p, 1))

    def p_expr_primaria_llamada_metodo_segura(self, p):
        """expr_primaria : IDENTIFICADOR OP_ACCESO_SEGURO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C"""
        p[0] = MethodCallExpr(Identifier(p[1], p.lineno(1), self._col(p, 1)), p[3], p[5],
                              p.lineno(1), self._col(p, 1), es_seguro=True)

    # ---- Nombre de clase usado como tipo ----
    # §3 regla 1 de la spec de POO: un nombre de clase es valido en variable,
    # parametro y retorno, igual que un `tipo` primitivo. Como el nombre de
    # una clase es sintacticamente un IDENTIFICADOR igual que cualquier otro,
    # estas producciones son "IDENTIFICADOR IDENTIFICADOR ..." -- una secuencia
    # que ninguna otra regla del lenguaje produce, así que el siguiente token
    # (otro IDENTIFICADOR vs. un operador/paréntesis) basta para que LALR(1)
    # decida sin ambigüedad. La validez real del nombre (¿existe esa clase?)
    # se resuelve en semantic.py/type_checker.py, no aquí.

    def p_decl_variable_clase(self, p):
        """decl_variable : IDENTIFICADOR IDENTIFICADOR DEL_PUNTO_COMA
                         | IDENTIFICADOR IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA"""
        init = p[4] if len(p) == 6 else None
        p[0] = VarDecl(p[1], p[2], init, p.lineno(2), self._col(p, 2))

    def p_tipo_generico_arg(self, p):
        """tipo_generico_arg : tipo
                             | IDENTIFICADOR"""
        # El argumento de un genérico puede ser un tipo primitivo
        # (Caja<entero>) o el nombre de una clase (Caja<Persona>).
        p[0] = p[1]

    def p_decl_variable_generica(self, p):
        """decl_variable : IDENTIFICADOR OP_MENOR tipo_generico_arg OP_MAYOR IDENTIFICADOR DEL_PUNTO_COMA
                         | IDENTIFICADOR OP_MENOR tipo_generico_arg OP_MAYOR IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA"""
        # Pila<entero> p [= expr]; (Etapa 7, genéricos). Alcance acotado:
        # solo declaración de variable y `nuevo` (ver p_expr_primaria_new_
        # generico) admiten esta sintaxis -- NO parámetros, tipos de
        # retorno, ni atributos genéricos, para mantener la superficie de
        # gramática nueva mínima (documentado en InvenioLang_2.0_POO.md).
        tipo = f'{p[1]}<{p[3]}>'
        nombre = p[5]
        init = p[7] if len(p) == 9 else None
        p[0] = VarDecl(tipo, nombre, init, p.lineno(5), self._col(p, 5))

    def p_param_clase(self, p):
        """param : IDENTIFICADOR IDENTIFICADOR"""
        p[0] = Parametro(p[1], p[2], False, False, p.lineno(2), self._col(p, 2))

    def p_param_clase_arreglo(self, p):
        """param : IDENTIFICADOR DEL_CORCHETE_A DEL_CORCHETE_C IDENTIFICADOR"""
        # Parametro de tipo arreglo de objetos (Clase[] nombre): a diferencia
        # de la declaracion de variable, un parametro no compite con una
        # asignacion (arr[i]=x no aparece dentro de una lista de parametros),
        # asi que no hay riesgo de conflicto y puede usar la misma forma que
        # ya usan los primitivos.
        p[0] = Parametro(p[1], p[4], True, False, p.lineno(4), self._col(p, 4))

    def p_def_funcion_clase(self, p):
        """def_funcion : IDENTIFICADOR IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C bloque"""
        p[0] = FunctionDecl(p[1], p[2], p[4], p[6], p.lineno(2), self._col(p, 2))

    def p_miembro_atributo_clase(self, p):
        """miembro_clase : visibilidad modificador_miembro IDENTIFICADOR IDENTIFICADOR DEL_PUNTO_COMA
                         | visibilidad modificador_miembro IDENTIFICADOR IDENTIFICADOR OP_ASIG expresion DEL_PUNTO_COMA"""
        self._validar_mod_attr(p[2], p, 4)
        init = p[6] if len(p) == 8 else None
        p[0] = AttrDecl(p[1], p[3], p[4], init, es_estatico=(p[2] == 'static'),
                        linea=p.lineno(4), columna=self._col(p, 4))

    def p_miembro_metodo_clase(self, p):
        """miembro_clase : visibilidad modificador_miembro IDENTIFICADOR IDENTIFICADOR DEL_PAREN_A lista_params DEL_PAREN_C cuerpo_metodo"""
        mod = p[2]
        p[0] = MethodDecl(p[1], p[3], p[4], p[6], p[8],
                          es_estatico=(mod == 'static'), es_abstracto=(mod == 'abstract'),
                          linea=p.lineno(4), columna=self._col(p, 4))

    def p_lvalue_miembro(self, p):
        """lvalue : IDENTIFICADOR DEL_PUNTO IDENTIFICADOR
                  | KW_THIS DEL_PUNTO IDENTIFICADOR
                  | KW_SUPER DEL_PUNTO IDENTIFICADOR"""
        p[0] = MemberLValue(self._receptor(p, 1), p[3], p.lineno(1), self._col(p, 1))

    def p_call_stmt_metodo(self, p):
        """call_stmt : IDENTIFICADOR DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA
                     | KW_THIS DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA
                     | KW_SUPER DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA"""
        p[0] = MethodCallStmt(self._receptor(p, 1), p[3], p[5],
                              p.lineno(1), self._col(p, 1))

    def p_call_stmt_metodo_seguro(self, p):
        """call_stmt : IDENTIFICADOR OP_ACCESO_SEGURO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA"""
        # objeto?.metodo(); (Etapa 12.2) -- no hace nada si objeto es nulo,
        # en vez de lanzar IL-EJE-010. Uso tipico: notificar a un listener
        # opcional.
        p[0] = MethodCallStmt(Identifier(p[1], p.lineno(1), self._col(p, 1)), p[3], p[5],
                              p.lineno(1), self._col(p, 1), es_seguro=True)

    def p_call_stmt_super(self, p):
        """call_stmt : KW_SUPER DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA"""
        p[0] = SuperCallStmt(p[3], p.lineno(1), self._col(p, 1))

    # ---- Receptor = elemento de arreglo (Estructuras de Datos) ----
    # personas[i].saludar() / personas[i].edad = 30 -- el receptor de un
    # acceso a miembro tambien puede ser un elemento de arreglo de objetos,
    # ademas de IDENTIFICADOR/este/padre. Sigue siendo "un solo nivel": no se
    # puede seguir encadenando despues del metodo/atributo. Se construye el
    # nodo ArrayAccess ya existente directamente como receptor, sin AST nuevo.

    def p_expr_primaria_miembro_arreglo(self, p):
        """expr_primaria : IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_PUNTO IDENTIFICADOR"""
        receptor = ArrayAccess(p[1], p[3], p.lineno(1), self._col(p, 1))
        p[0] = MemberAccess(receptor, p[6], p.lineno(1), self._col(p, 1))

    def p_expr_primaria_llamada_metodo_arreglo(self, p):
        """expr_primaria : IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C"""
        receptor = ArrayAccess(p[1], p[3], p.lineno(1), self._col(p, 1))
        p[0] = MethodCallExpr(receptor, p[6], p[8], p.lineno(1), self._col(p, 1))

    def p_lvalue_miembro_arreglo(self, p):
        """lvalue : IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_PUNTO IDENTIFICADOR"""
        receptor = ArrayAccess(p[1], p[3], p.lineno(1), self._col(p, 1))
        p[0] = MemberLValue(receptor, p[6], p.lineno(1), self._col(p, 1))

    def p_call_stmt_metodo_arreglo(self, p):
        """call_stmt : IDENTIFICADOR DEL_CORCHETE_A expresion DEL_CORCHETE_C DEL_PUNTO IDENTIFICADOR DEL_PAREN_A lista_args DEL_PAREN_C DEL_PUNTO_COMA"""
        receptor = ArrayAccess(p[1], p[3], p.lineno(1), self._col(p, 1))
        p[0] = MethodCallStmt(receptor, p[6], p[8], p.lineno(1), self._col(p, 1))

    # ============================================================
    # Empty production
    # ============================================================

    def p_empty(self, p):
        """empty :"""
        p[0] = None

    # ============================================================
    # Error sintáctico
    # ============================================================

    # Palabras reservadas por su token interno, para mensajes de error
    _LEXEMA_KW = {
        'KW_IF': 'if/si', 'KW_ELSE': 'else/sino', 'KW_WHILE': 'while/mientras',
        'KW_FOR': 'for/para', 'KW_RETURN': 'return', 'KW_PRINT': 'print/imprimir',
        'KW_READ': 'read/leer', 'KW_INT': 'int/entero', 'KW_FLOAT': 'float/real',
        'KW_STRING': 'string/texto', 'KW_BOOL': 'bool/logico',
        'KW_VOID': 'void/vacio', 'KW_CONST': 'const/constante',
        'KW_TRUE': 'true/verdadero', 'KW_FALSE': 'false/falso',
        'KW_BREAK': 'break/romper', 'KW_CONTINUE': 'continue/continuar',
        'KW_MAIN': 'main',
    }

    def p_error(self, p):
        """Clasifica el error sintáctico con el código más específico posible.

        Sin esta discriminación todo error del parser se reportaría como
        IL-SIN-010, que es lo que el catálogo (§15.3) reserva únicamente para
        el punto y coma faltante.
        """
        if p is None:
            self.error_manager.error_sintactico(
                'IL-SIN-006',
                'Se alcanzó el final del archivo con uno o más bloques sin cerrar',
                0, 0
            )
            return

        linea, col = p.lineno, self._col_lexpos(p)

        # IL-SIN-005: llave de cierre sin apertura correspondiente (§3.3.3)
        if p.type == 'DEL_LLAVE_C':
            self.error_manager.error_sintactico(
                'IL-SIN-005',
                'Llave de cierre "}" sin una llave de apertura correspondiente',
                linea, col
            )
            return

        # IL-LEX-006: palabra reservada donde se esperaba un identificador (§2.5.3)
        if p.type in self._LEXEMA_KW and self._espera_identificador():
            self.error_manager.error_lexico(
                'IL-LEX-006',
                f'"{p.value}" es una palabra reservada del lenguaje y no puede '
                f'usarse como identificador',
                linea, col
            )
            return

        # IL-SIN-040: faltan los ; separadores del encabezado del for (§9.2)
        if self._dentro_de_for():
            self.error_manager.error_sintactico(
                'IL-SIN-040',
                'Faltan los punto y coma separadores en el encabezado de '
                'for / para: for (inicio; condición; actualización)',
                linea, col
            )
            return

        self.error_manager.error_sintactico(
            'IL-SIN-010',
            f'Se esperaba ";" o una instrucción válida cerca de "{p.value}"',
            linea, col
        )

    def _pila_simbolos(self):
        """Símbolos actualmente en la pila del parser (para clasificar errores)."""
        try:
            return [getattr(s, 'type', None) for s in self.parser_obj.symstack]
        except Exception:
            return []

    # Tokens tras los cuales la gramática exige un IDENTIFICADOR. Se incluyen
    # los lexemas de tipo sin reducir porque, en el momento del error, PLY aún
    # no ha reducido KW_INT/KW_FLOAT/... al no terminal `tipo`.
    _PRECEDE_IDENTIFICADOR = {
        'tipo', 'KW_CONST', 'KW_INT', 'KW_FLOAT', 'KW_STRING', 'KW_BOOL',
        'KW_VOID', 'DEL_CORCHETE_C',
    }

    def _espera_identificador(self):
        """Indica si el token problemático ocupa el lugar de un identificador."""
        pila = self._pila_simbolos()
        return bool(pila) and pila[-1] in self._PRECEDE_IDENTIFICADOR

    def _dentro_de_for(self):
        """Indica si el error ocurrió dentro del encabezado de un for."""
        return 'KW_FOR' in self._pila_simbolos()[-6:]

    def _col(self, p, idx):
        lexpos = p.lexpos(idx) if hasattr(p, 'lexpos') else 0
        return self._calc_col_pos(lexpos)

    def _col_lexpos(self, p):
        return self._calc_col_pos(p.lexpos)

    def _calc_col_pos(self, lexpos):
        if (hasattr(self.lexer, 'lexer_obj') and self.lexer.lexer_obj
                and hasattr(self.lexer.lexer_obj, 'lexdata')
                and self.lexer.lexer_obj.lexdata):
            data = self.lexer.lexer_obj.lexdata
            inicio = data.rfind('\n', 0, lexpos) + 1 if '\n' in data[:lexpos] else 0
            return lexpos - inicio + 1
        return 1

    def analizar(self, codigo, archivo="<desconocido>"):
        """Analiza sintácticamente el código fuente.

        Args:
            codigo: Código fuente como string
            archivo: Nombre del archivo

        Retorna:
            Tupla (ast, error_manager)
        """
        self.error_manager.set_archivo(archivo)
        self.error_manager.limpiar()
        self._if_sin_else = None
        self._elems_tras_if = 0

        if not self.parser_obj:
            self.build()

        # Asegurar que el lexer esté construido
        if not self.lexer.lexer_obj:
            self.lexer.build()
        self.lexer.lexer_obj.input(codigo)
        self.lexer.lexer_obj.lineno = 1

        try:
            ast = self.parser_obj.parse(lexer=self.lexer.lexer_obj)
            return ast, self.error_manager
        except Exception as e:
            self.error_manager.error_sintactico(
                'IL-SIN-010',
                f'Error de sintaxis: {str(e)}', 0, 0
            )
            return None, self.error_manager
