# ll1_demo.py - Etapa 12.13: parser LL(1) de comparación
#
# NO se conecta al pipeline principal de InvenioLang: ni lexer.py,
# parser.py, cli.py ni gui_qt.py importan nada de este módulo, y el
# parser LL(1) (ParserLL1/parsear/evaluar) en sí mismo NO importa nada
# del compilador real -- es completamente autónomo, con su propio
# tokenizador. La ÚNICA excepción es `verificar_contra_lalr`, al final
# del archivo: esa función SÍ importa el pipeline real, pero solo para
# poder comparar los dos resultados (el criterio de verificación de esta
# etapa) -- ninguna otra parte del módulo, ni el compilador real,
# depende de esa función. Es un módulo APARTE,
# deliberadamente acotado a expresiones aritméticas (+ - * / ( ), con
# precedencia y unario -) para que el CONTRASTE entre analizar LL(1) a
# mano (descenso recursivo predictivo) y el LALR(1) real de `parser.py`
# (generado por PLY, ver docs/InvenioLang_GramaticaFormal.md) sea el
# entregable, no una pieza de producción del compilador. El ejercicio es
# EXACTAMENTE la subgramática de expresiones aritméticas que
# docs/InvenioLang_GramaticaFormal.md ya documenta con su tabla LALR(1) --
# aquí se documenta la MISMA subgramática, pero reescrita sin recursión
# izquierda (obligatorio para LL(1)) y con sus propios conjuntos
# FIRST/FOLLOW derivados a mano.
#
# ============================================================
# Gramática (ya sin recursión izquierda -- LL(1))
# ============================================================
#
#   E  -> T E'
#   E' -> + T E' | - T E' | ε
#   T  -> F T'
#   T' -> * F T' | / F T' | ε
#   F  -> ( E ) | NUM | - F
#
# La gramática LALR(1) equivalente en parser.py (ver p_expr_suma/
# p_expr_mult/p_expr_unario) SÍ usa recursión izquierda directa
# ("expr_suma : expr_suma OP_SUMA expr_mult | expr_mult"), que un parser
# LL(1) de descenso recursivo NO puede consumir tal cual -- entraría en
# recursión infinita sin avanzar el cursor (E -> E + T probaría E primero,
# que vuelve a probar E primero, ...). Eliminar la recursión izquierda es
# el primer paso obligatorio de CUALQUIER conversión LALR(1) -> LL(1); el
# resultado de arriba es esa conversión aplicada a esta subgramática.
#
# ============================================================
# FIRST / FOLLOW (derivados a mano)
# ============================================================
#
#   FIRST(F)  = { (, NUM, - }
#   FIRST(T)  = FIRST(F) = { (, NUM, - }
#   FIRST(T') = { *, /, ε }
#   FIRST(E)  = FIRST(T) = { (, NUM, - }
#   FIRST(E') = { +, -, ε }
#
#   FOLLOW(E)  = { $, ) }
#   FOLLOW(E') = FOLLOW(E) = { $, ) }
#   FOLLOW(T)  = (FIRST(E') - {ε}) ∪ FOLLOW(E') = { +, -, $, ) }
#   FOLLOW(T') = FOLLOW(T) = { +, -, $, ) }
#   FOLLOW(F)  = (FIRST(T') - {ε}) ∪ FOLLOW(T') = { *, /, +, -, $, ) }
#
# La condición LL(1) (cada no-terminal, para cada par de alternativas
# distintas, tiene conjuntos FIRST disjuntos -- y si alguna alternativa
# deriva ε, FIRST de las demás debe ser disjunto de FOLLOW del
# no-terminal) se cumple en las 5 producciones de arriba:
#   - F: FIRST de sus 3 alternativas -- {(}, {NUM}, {-} -- son disjuntos.
#   - E'/T': la alternativa ε nunca colisiona porque + - (resp. * /) no
#     están en FOLLOW(E)/FOLLOW(T) de forma ambigua (el lookahead de 1
#     token siempre decide sin ambigüedad qué alternativa tomar).
# Esto es lo que hace que la tabla de análisis predictivo M[no-terminal,
# terminal] de abajo tenga EXACTAMENTE una entrada por casilla (0 o 1
# producciones, nunca 2) -- la definición misma de LL(1).
#
# Contraste pedagógico con el LALR(1) de parser.py: ahí la MISMA
# ambigüedad de precedencia (+ vs *) NO se resuelve con una gramática
# reescrita sin recursión izquierda, sino con la tabla `precedence`
# (parser.py líneas ~33-41) que le dice al autómata LALR "en caso de
# duda, desplazar según esta prioridad" -- un mecanismo que un parser
# LL(1) de descenso recursivo simplemente no tiene (ni le hace falta,
# porque la propia estructura de la gramática de arriba ya codifica la
# precedencia: T por encima de F asegura que * se agrupe antes que +).

class ErrorSintacticoLL1(Exception):
    """Error de análisis sintáctico del parser LL(1) de esta demo --
    catálogo propio, deliberadamente separado de IL-SIN-*/IL-LEX-* (este
    módulo no forma parte del compilador real)."""


class NodoLL1:
    """AST minimo: ('num', valor) o (operador, izquierda, derecha)."""

    __slots__ = ('op', 'izq', 'der', 'valor')

    def __init__(self, op, izq=None, der=None, valor=None):
        self.op = op
        self.izq = izq
        self.der = der
        self.valor = valor

    def __repr__(self):
        if self.op == 'num':
            return repr(self.valor)
        if self.op == 'neg':
            return f'(-{self.izq!r})'
        return f'({self.izq!r} {self.op} {self.der!r})'


# ---- Tokenizador (deliberadamente simple: solo lo que la subgramática
# necesita -- enteros, + - * / ( )) ----

def _tokenizar(texto):
    tokens = []
    i = 0
    n = len(texto)
    while i < n:
        c = texto[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit():
            j = i
            while j < n and texto[j].isdigit():
                j += 1
            tokens.append(('NUM', int(texto[i:j])))
            i = j
            continue
        if c in '+-*/()':
            tokens.append((c, c))
            i += 1
            continue
        raise ErrorSintacticoLL1(f'carácter inesperado: {c!r} en la posición {i}')
    tokens.append(('$', '$'))
    return tokens


class ParserLL1:
    """Descenso recursivo predictivo sobre la gramática de la cabecera de
    este módulo -- un método por no-terminal, cada uno decide qué
    alternativa tomar mirando ÚNICAMENTE el token de lookahead actual
    (LL(1): 1 solo token de anticipación, nunca retrocede)."""

    def __init__(self, texto):
        self.tokens = _tokenizar(texto)
        self.pos = 0

    def _actual(self):
        return self.tokens[self.pos]

    def _consumir(self, tipo_esperado):
        tipo, valor = self._actual()
        if tipo != tipo_esperado:
            raise ErrorSintacticoLL1(
                f'se esperaba {tipo_esperado!r}, se encontró {tipo!r} ({valor!r})')
        self.pos += 1
        return valor

    def parsear(self):
        nodo = self._E()
        self._consumir('$')
        return nodo

    def _E(self):
        """E -> T E'"""
        izq = self._T()
        return self._Eprima(izq)

    def _Eprima(self, izq):
        """E' -> + T E' | - T E' | ε -- el lookahead decide: FIRST(+T E')
        = {+}, FIRST(- T E') = {-}, y si el token actual no es ninguno de
        los dos, se toma la alternativa ε (que aquí es "no hay más que
        hacer, retornar `izq` tal cual")."""
        tipo, _ = self._actual()
        if tipo == '+':
            self._consumir('+')
            der = self._T()
            return self._Eprima(NodoLL1('+', izq, der))
        if tipo == '-':
            self._consumir('-')
            der = self._T()
            return self._Eprima(NodoLL1('-', izq, der))
        return izq  # ε: tipo actual no esta en FIRST(E') -- debe estar en FOLLOW(E')

    def _T(self):
        """T -> F T'"""
        izq = self._F()
        return self._Tprima(izq)

    def _Tprima(self, izq):
        """T' -> * F T' | / F T' | ε"""
        tipo, _ = self._actual()
        if tipo == '*':
            self._consumir('*')
            der = self._F()
            return self._Tprima(NodoLL1('*', izq, der))
        if tipo == '/':
            self._consumir('/')
            der = self._F()
            return self._Tprima(NodoLL1('/', izq, der))
        return izq

    def _F(self):
        """F -> ( E ) | NUM | - F -- FIRST disjuntos: {(}, {NUM}, {-}."""
        tipo, valor = self._actual()
        if tipo == '(':
            self._consumir('(')
            nodo = self._E()
            self._consumir(')')
            return nodo
        if tipo == 'NUM':
            self._consumir('NUM')
            return NodoLL1('num', valor=valor)
        if tipo == '-':
            self._consumir('-')
            return NodoLL1('neg', self._F())
        raise ErrorSintacticoLL1(f'token inesperado: {tipo!r} ({valor!r})')


def parsear(texto):
    """Punto de entrada: texto -> NodoLL1 (o ErrorSintacticoLL1)."""
    return ParserLL1(texto).parsear()


def evaluar(nodo):
    """Evalúa un NodoLL1 a un número (int/float) -- misma aritmética
    entera truncada hacia cero de interpreter.py/ir.py para que / y %
    coincidan exactamente si el resultado se compara contra el pipeline
    real (ver `_evaluar_lalr` en las pruebas de este módulo)."""
    if nodo.op == 'num':
        return nodo.valor
    if nodo.op == 'neg':
        return -evaluar(nodo.izq)
    a, b = evaluar(nodo.izq), evaluar(nodo.der)
    if nodo.op == '+':
        return a + b
    if nodo.op == '-':
        return a - b
    if nodo.op == '*':
        return a * b
    if nodo.op == '/':
        if isinstance(a, int) and isinstance(b, int):
            q = abs(a) // abs(b)
            return -q if (a < 0) != (b < 0) else q
        return a / b
    raise ErrorSintacticoLL1(f'operador desconocido: {nodo.op!r}')


# ============================================================
# Verificación: LL(1) (este módulo) vs LALR(1) (parser.py real)
# ============================================================
#
# El criterio de verificación de la Etapa 12.13: el MISMO conjunto de
# expresiones aritméticas, analizadas por los dos analizadores, deben
# producir el mismo resultado. Se importa el pipeline real SOLO dentro de
# esta función de verificación (no en el módulo en general) -- mantiene
# ll1_demo.py desacoplado del compilador, y a la vez permite comparar.

_EXPRESIONES_PRUEBA = [
    '2 + 3',
    '2 + 3 * 4',
    '(2 + 3) * 4',
    '10 - 2 - 3',            # asociatividad izquierda: (10-2)-3 = 5, no 10-(2-3)=11
    '2 * 3 + 4 * 5',
    '-5 + 3',
    '-(5 + 3)',
    '20 / 3',                # división entera truncada hacia cero
    '-20 / 3',
    '2 * (3 + (4 - 1)) / 2',
    '100',
    '((((1))))',
]


def _evaluar_lalr(expresion):
    """Evalúa `expresion` con el pipeline REAL de InvenioLang (lexer.py/
    parser.py/semantic.py/type_checker.py/interpreter.py) envuelta en un
    programa mínimo que la imprime -- la gramática LALR(1) completa de
    expr_suma/expr_mult/expr_unario, no la sub-gramática de este módulo.
    Se compara vía texto impreso (igual que hace pruebas/conformidad.py)
    en vez de tocar el AST/estado interno del intérprete -- más simple y
    más fiel a "lo que el compilador realmente hace". Importa el
    pipeline real localmente (no al nivel del módulo) -- ver el
    comentario de cabecera del archivo."""
    from .lexer import Lexer
    from .parser import Parser
    from .interpreter import Interpreter
    from .semantic import SemanticAnalyzer
    from .type_checker import TypeChecker
    from .errors import ErrorManager

    codigo = f'void main() {{ imprimir({expresion}); }}\n'
    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(codigo, 'll1_demo.inv')
    p = Parser(lx, em)
    ast, em = p.analizar(codigo, 'll1_demo.inv')
    if ast is not None and not em.hay_errores():
        sem = SemanticAnalyzer(em)
        tabla = sem.analizar(ast)
        if not em.hay_errores():
            TypeChecker(em, tabla).verificar(ast)
    if em.hay_errores():
        raise RuntimeError(f'pipeline LALR(1) rechazó {expresion!r}: '
                           f'{[e.codigo for e in em.errores]}')
    interp = Interpreter(em, tabla)
    salida = interp.interpretar(ast, [], usar_stdin=False)
    texto = ''.join(salida)
    return float(texto) if '.' in texto else int(texto)


def verificar_contra_lalr(verboso=False):
    """Corre `_EXPRESIONES_PRUEBA` por ambos analizadores y compara.
    Retorna (ok, detalles) -- ok=True si TODAS coinciden."""
    detalles = []
    ok = True
    for expr in _EXPRESIONES_PRUEBA:
        try:
            resultado_ll1 = evaluar(parsear(expr))
        except Exception as e:
            detalles.append((expr, 'ERROR_LL1', str(e)))
            ok = False
            continue
        try:
            resultado_lalr = _evaluar_lalr(expr)
        except Exception as e:
            detalles.append((expr, 'ERROR_LALR', str(e)))
            ok = False
            continue
        coincide = resultado_ll1 == resultado_lalr
        detalles.append((expr, resultado_ll1, resultado_lalr, coincide))
        if not coincide:
            ok = False
        if verboso:
            print(f'  {"ok  " if coincide else "FALLA"} {expr!r} '
                  f'-> LL(1)={resultado_ll1!r} LALR(1)={resultado_lalr!r}')
    return ok, detalles


if __name__ == '__main__':
    ok, _ = verificar_contra_lalr(verboso=True)
    print('TODO OK' if ok else 'HAY DIVERGENCIAS')
