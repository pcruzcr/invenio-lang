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
                             | def_main"""
        p[0] = p[1]

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
    # Expresiones (precedencia mediante PLY + estructural)
    # ============================================================

    def p_expresion(self, p):
        """expresion : expr_or"""
        p[0] = p[1]

    def p_expr_or(self, p):
        """expr_or : expr_or OP_OR expr_and
                   | expr_and"""
        if len(p) == 4:
            p[0] = BinaryOp(p[2], p[1], p[3], p.lineno(2), self._col(p, 2))
        else:
            p[0] = p[1]

    def p_expr_and(self, p):
        """expr_and : expr_and OP_AND expr_igual
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
        """expr_rel : expr_rel OP_MENOR expr_sum
                    | expr_rel OP_MAYOR expr_sum
                    | expr_rel OP_MENOR_IGUAL expr_sum
                    | expr_rel OP_MAYOR_IGUAL expr_sum
                    | expr_sum"""
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
                       | OP_INC expr_primaria
                       | OP_DEC expr_primaria
                       | expr_primaria OP_INC
                       | expr_primaria OP_DEC
                       | expr_primaria"""
        if len(p) == 3:
            if p.slice[1].type in ('OP_RESTA', 'OP_NOT'):
                # Operador unario: -expr o !expr
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
