"""Edición estructurada del diagrama de flujo y su validación (INV-3007).

Base del editor de la GUI (y del futuro editor de arrastrar y soltar): el
estudiante nunca dibuja flechas, sino que **inserta, elimina, mueve o
envuelve** símbolos dentro de las secuencias del árbol. Como el modelo es un
árbol estructurado, ninguna operación puede crear un salto arbitrario; lo
único que hay que vigilar es que ``romper``/``continuar`` queden dentro de
algo que los acepte, y eso se comprueba tras cada operación.

Todas las operaciones son **puras**: devuelven un modelo nuevo y no tocan el
recibido (la GUI guarda los anteriores para «Deshacer»). Si la operación no
es válida lanzan ``ErrorFlujo`` con un mensaje bilingüe del catálogo
``FLU.*``. Cada texto que escribe el estudiante se analiza con el lexer y el
parser reales dentro de un programa mínimo (``validar_fragmento``); la
validación completa (``validar``) compila el programa generado y cuelga cada
diagnóstico del nodo que lo causó.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from .. import ast_nodes as A  # noqa: N812 - alias corto del módulo de nodos
from ..core.compiler import analizar_fuente
from ..errors import ErrorManager
from ..i18n import normalizar_idioma
from ..lexer import Lexer
from ..parser import Parser
from ..traductor import PALABRAS_CLAVE
from .generacion import generar
from .modelo import TIPOS, TIPOS_CICLO, Diagrama, Elemento, ErrorFlujo, ModeloFlujo, Nodo, Rama

__all__ = [
    "CAMPOS",
    "Problema",
    "Ubicacion",
    "agregar_rama",
    "editar",
    "eliminar",
    "envolver_en_ciclo",
    "envolver_en_si",
    "insertar",
    "mover",
    "nuevo_modelo",
    "nuevo_nodo",
    "quitar_rama",
    "validar",
    "validar_fragmento",
]

# Campos editables por tipo (nombre público -> atributo de Nodo).
CAMPOS: dict[str, dict[str, str]] = {
    "proceso": {"texto": "texto"},
    "declaracion": {"texto": "texto"},
    "leer": {"texto": "texto"},
    "escribir": {"texto": "texto"},
    "llamada": {"texto": "texto"},
    "retornar": {"texto": "texto"},
    "romper": {},
    "continuar": {},
    "si": {},
    "segun": {"expresion": "texto"},
    "coincidir": {"expresion": "texto"},
    "mientras": {"condicion": "texto"},
    "hacer_mientras": {"condicion": "texto"},
    "para": {"inicio": "inicio", "condicion": "texto", "paso": "paso"},
    "para_cada": {"variable": "variable", "coleccion": "texto"},
    "intentar": {"variable": "variable"},
}

# Clases del AST que acepta cada caja hoja.
_HOJAS: dict[str, tuple[type, ...]] = {
    "proceso": (A.AssignStmt, A.IncDecStmt),
    "declaracion": (A.VarDecl, A.ConstDecl, A.ArrayDecl, A.MatrixDecl),
    "llamada": (A.CallStmt, A.MethodCallStmt, A.SuperCallStmt),
}


@dataclass(frozen=True)
class Ubicacion:
    """Posición de inserción en una secuencia del diagrama.

    Secuencia ``parte`` del compuesto ``padre`` (``None``: el cuerpo del
    diagrama), en la posición ``indice`` (``None``: al final).

    ``parte``: ``cuerpo``, ``rama:K`` (si), ``caso:K`` (segun/coincidir),
    ``sino``, ``por_defecto`` o ``captura``.
    """

    padre: str | None = None
    parte: str = "cuerpo"
    indice: int | None = None


@dataclass(frozen=True)
class Problema:
    """Un problema del diagrama: en qué diagrama y nodo, y su mensaje."""

    clave: str | None
    nodo: str | None
    error: ErrorFlujo

    def texto(self, idioma: str | None = None) -> str:
        """Mensaje en ``idioma``."""
        return self.error.texto(idioma)


# ====================================================================== fragmentos


def _como_error(err: Any) -> ErrorFlujo:
    """Diagnóstico del compilador como ``ErrorFlujo`` presentable en cualquier idioma.

    Los diagnósticos guardan su clave del catálogo y sus argumentos.
    """
    if err.clave is not None:
        return ErrorFlujo(err.clave, **err.args_mensaje)
    return ErrorFlujo("FLU.val.compilacion", diagnostico=err.mensaje)


def _analizar(programa: str) -> tuple[Any, list[ErrorFlujo]]:
    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(programa, "diagrama.inv")
    if em.hay_errores():
        return None, [_como_error(e) for e in em.errores]
    ast, em = Parser(lx, em).analizar(programa, "diagrama.inv", enlazar=False)
    if ast is None or em.hay_errores():
        return None, [_como_error(e) for e in em.errores]
    return ast, []


def _envoltorio(tipo: str, campo: str, valor: str, nodo: Nodo | None) -> tuple[str, type] | None:
    """Programa mínimo que contiene el fragmento y la clase de AST esperada."""
    n = nodo or Nodo("", tipo)
    if tipo in _HOJAS:
        return f"{valor};", A.Instruccion
    plantillas: dict[tuple[str, str], tuple[str, type]] = {
        ("leer", "texto"): (f"leer({valor});", A.ReadStmt),
        ("escribir", "texto"): (f"imprimir({valor});", A.PrintStmt),
        ("retornar", "texto"): (f"retornar {valor};", A.ReturnStmt),
        ("si", "condicion"): (f"si ({valor}) {{ }}", A.IfStmt),
        ("mientras", "condicion"): (f"mientras ({valor}) {{ }}", A.WhileStmt),
        ("hacer_mientras", "condicion"): (f"hacer {{ }} mientras ({valor});", A.DoWhileStmt),
        ("segun", "expresion"): (f"segun ({valor}) {{ }}", A.SwitchStmt),
        ("segun", "caso"): (f"segun (x) {{ caso {valor}: }}", A.SwitchStmt),
        ("coincidir", "expresion"): (f"emparejar ({valor}) {{ }}", A.MatchStmt),
        ("coincidir", "caso"): (f"emparejar (x) {{ caso {valor}: }}", A.MatchStmt),
        ("intentar", "variable"): (f"intentar {{ }} capturar ({valor}) {{ }}", A.TryStmt),
    }
    if tipo == "para":
        partes = {"inicio": n.inicio, "condicion": n.texto, "paso": n.paso, campo: valor}
        return (
            f"para ({partes['inicio']}; {partes['condicion']}; {partes['paso']}) {{ }}",
            A.ForStmt,
        )
    if tipo == "para_cada":
        partes = {"variable": n.variable, "coleccion": n.texto, campo: valor}
        return f"para_cada ({partes['variable']} : {partes['coleccion']}) {{ }}", A.ForEachStmt
    return plantillas.get((tipo, campo))


def _limpio(valor: str) -> str:
    """Texto de una caja sin espacios sobrantes ni el ``;`` final (va implícito)."""
    return valor.strip().removesuffix(";").strip()


def _obligatorio(tipo: str, campo: str) -> bool:
    return not (tipo == "retornar" or (tipo == "para" and campo in ("inicio", "condicion", "paso")))


def validar_fragmento(
    tipo: str, campo: str, valor: str, idioma: str = "es", nodo: Nodo | None = None
) -> list[str]:
    """Errores de sintaxis del texto ``valor`` para el ``campo`` de un nodo ``tipo``.

    Se analiza con el lexer y el parser reales dentro de ``vacio main() { … }``
    y se exige que el resultado sea exactamente UNA instrucción de la clase
    esperada (así un texto no puede «colar» llaves u otras instrucciones).
    ``nodo`` aporta los demás campos de un ``para``/``para_cada``. Lista vacía:
    el fragmento es válido.
    """
    idioma = normalizar_idioma(idioma)
    return [e.texto(idioma) for e in _fallos(tipo, campo, valor, nodo)]


def _fallos(tipo: str, campo: str, valor: str, nodo: Nodo | None) -> list[ErrorFlujo]:
    """Errores (diferidos, bilingües) de un fragmento; ver ``validar_fragmento``."""
    if not valor.strip():
        if _obligatorio(tipo, campo):
            return [ErrorFlujo("FLU.val.vacio")]
        if tipo == "retornar":
            return []
    plantilla = _envoltorio(tipo, campo, _limpio(valor), nodo)
    if plantilla is None:
        return [ErrorFlujo("FLU.val.campo", campo=campo, tipo=tipo)]
    programa, clase = plantilla
    ast, errores = _analizar(f"vacio main() {{ {programa} }}")
    if errores:
        return errores
    elementos = ast.main.bloque.elementos if ast.main is not None else []
    extra = ast.subrutinas or ast.clases or ast.enums or ast.declaraciones_posteriores
    if extra or ast.declaraciones_globales or len(elementos) != 1:
        return [ErrorFlujo("FLU.val.una_instruccion")]
    if tipo in _HOJAS:
        if not isinstance(elementos[0], _HOJAS[tipo]):
            return [ErrorFlujo(f"FLU.val.no_es.{tipo}")]
    elif not isinstance(elementos[0], clase):
        return [ErrorFlujo("FLU.val.una_instruccion")]
    return []


def _exigir_fragmento(tipo: str, campo: str, valor: str, nodo: Nodo | None) -> None:
    errores = _fallos(tipo, campo, valor, nodo)
    if errores:
        raise ErrorFlujo("FLU.val.fragmento", campo=campo, detalle=errores[0])


def nuevo_nodo(tipo: str, **campos: str) -> Nodo:
    """Nodo nuevo (sin id: lo asigna ``insertar``) con sus textos ya validados.

    Campos por tipo: ver ``CAMPOS``. Para ``si`` se da ``condicion``; para
    ``segun``/``coincidir`` la ``expresion``. ``intentar`` lleva ``variable``
    (por defecto ``e``).
    """
    if tipo not in TIPOS:
        raise ErrorFlujo("FLU.val.tipo", tipo=tipo, validos=", ".join(TIPOS))
    n = Nodo("", tipo)
    if tipo == "intentar":
        n.alterno = []
        campos.setdefault("variable", "e")
    permitidos = set(CAMPOS[tipo]) | ({"condicion"} if tipo == "si" else set())
    sobran = sorted(set(campos) - permitidos)
    if sobran:
        raise ErrorFlujo("FLU.val.campo", campo=", ".join(sobran), tipo=tipo)
    if tipo == "si":
        condicion = campos.get("condicion", "")
        _exigir_fragmento("si", "condicion", condicion, None)
        n.ramas.append(Rama(condicion.strip()))
        return n
    for campo, attr in CAMPOS[tipo].items():
        setattr(n, attr, _limpio(campos.get(campo, "")))
    for campo in CAMPOS[tipo]:
        _exigir_fragmento(tipo, campo, getattr(n, CAMPOS[tipo][campo]), n)
    return n


def nuevo_modelo(idioma: str = "es") -> ModeloFlujo:
    """Programa vacío con solo ``main`` (punto de partida del constructor)."""
    idioma = normalizar_idioma(idioma)
    vacio = PALABRAS_CLAVE["KW_VOID"][0 if idioma == "es" else 1]
    d = Diagrama("main", "main", "main", f"{vacio} main()")
    return ModeloFlujo(idioma, [Elemento("subrutina", diagrama=d)])


# ====================================================================== búsqueda


def _ids(modelo: ModeloFlujo) -> Iterator[str]:
    for d in modelo.diagramas():
        pila = list(d.cuerpo)
        while pila:
            n = pila.pop()
            yield n.id
            for _, sec in n.secuencias():
                pila.extend(sec)


def _asignar_ids(modelo: ModeloFlujo, nodo: Nodo) -> None:
    usados = set(_ids(modelo))
    siguiente = 1 + max((int(i[1:]) for i in usados if i[1:].isdigit()), default=0)
    pila = [nodo]
    while pila:
        n = pila.pop()
        if not n.id or n.id in usados:
            n.id = f"n{siguiente}"
            siguiente += 1
        usados.add(n.id)
        for _, sec in n.secuencias():
            pila.extend(sec)


def _buscar(cuerpo: list[Nodo], ident: str) -> tuple[list[Nodo], int, Nodo] | None:
    """(secuencia que lo contiene, posición, nodo) o None."""
    for k, n in enumerate(cuerpo):
        if n.id == ident:
            return cuerpo, k, n
        for _, sec in n.secuencias():
            hallado = _buscar(sec, ident)
            if hallado is not None:
                return hallado
    return None


def _nodo(d: Diagrama, ident: str) -> tuple[list[Nodo], int, Nodo]:
    hallado = _buscar(d.cuerpo, ident)
    if hallado is None:
        raise ErrorFlujo("FLU.val.nodo_desconocido", id=ident)
    return hallado


def _secuencia(d: Diagrama, padre: str | None, parte: str) -> list[Nodo]:
    if padre is None:
        if parte != "cuerpo":
            raise ErrorFlujo("FLU.val.parte", parte=parte)
        return d.cuerpo
    _, _, n = _nodo(d, padre)
    for nombre, sec in n.secuencias():
        if nombre == parte:
            return sec
    raise ErrorFlujo("FLU.val.parte", parte=parte)


def _copiar(modelo: ModeloFlujo, clave: str) -> tuple[ModeloFlujo, Diagrama]:
    nuevo = copy.deepcopy(modelo)
    return nuevo, nuevo.diagrama(clave)


def _comprobar_saltos(nodos: list[Nodo], en_ciclo: bool, en_segun: bool) -> None:
    for n in nodos:
        if n.tipo == "romper" and not (en_ciclo or en_segun):
            raise ErrorFlujo("FLU.val.romper_fuera")
        if n.tipo == "continuar" and not en_ciclo:
            raise ErrorFlujo("FLU.val.continuar_fuera")
        if n.tipo == "si" and not n.ramas:
            raise ErrorFlujo("FLU.contrato.sin_ramas")
        for _, sec in n.secuencias():
            _comprobar_saltos(
                sec,
                en_ciclo or n.tipo in TIPOS_CICLO,
                (en_segun or n.tipo == "segun") and n.tipo not in TIPOS_CICLO,
            )


def _comprobar(d: Diagrama) -> None:
    _comprobar_saltos(d.cuerpo, False, False)


# ====================================================================== operaciones


def insertar(modelo: ModeloFlujo, clave: str, ubicacion: Ubicacion, nodo: Nodo) -> ModeloFlujo:
    """Inserta ``nodo`` (y su contenido) en ``ubicacion`` del diagrama ``clave``."""
    nuevo, d = _copiar(modelo, clave)
    nodo = copy.deepcopy(nodo)
    _asignar_ids(nuevo, nodo)
    sec = _secuencia(d, ubicacion.padre, ubicacion.parte)
    indice = len(sec) if ubicacion.indice is None else ubicacion.indice
    if not 0 <= indice <= len(sec):
        raise ErrorFlujo("FLU.val.indice", indice=indice, total=len(sec))
    sec.insert(indice, nodo)
    _comprobar(d)
    return nuevo


def eliminar(modelo: ModeloFlujo, clave: str, nodo_id: str) -> ModeloFlujo:
    """Quita el nodo ``nodo_id`` con todo su contenido."""
    nuevo, d = _copiar(modelo, clave)
    sec, k, _ = _nodo(d, nodo_id)
    del sec[k]
    return nuevo


def mover(modelo: ModeloFlujo, clave: str, nodo_id: str, ubicacion: Ubicacion) -> ModeloFlujo:
    """Lleva el nodo a otra posición del mismo diagrama (no dentro de sí mismo).

    ``ubicacion.indice`` se interpreta en la secuencia de destino ya sin el
    nodo movido.
    """
    nuevo, d = _copiar(modelo, clave)
    sec, k, nodo = _nodo(d, nodo_id)
    if ubicacion.padre is not None and _buscar([nodo], ubicacion.padre) is not None:
        raise ErrorFlujo("FLU.val.dentro_de_si")
    del sec[k]
    destino = _secuencia(d, ubicacion.padre, ubicacion.parte)
    indice = len(destino) if ubicacion.indice is None else ubicacion.indice
    if not 0 <= indice <= len(destino):
        raise ErrorFlujo("FLU.val.indice", indice=indice, total=len(destino))
    destino.insert(indice, nodo)
    _comprobar(d)
    return nuevo


def _consecutivos(d: Diagrama, ids: list[str]) -> tuple[list[Nodo], int, int]:
    if not ids:
        raise ErrorFlujo("FLU.val.sin_seleccion")
    sec, _, _ = _nodo(d, ids[0])
    posicion = {n.id: k for k, n in enumerate(sec)}
    if len(set(ids)) != len(ids) or any(i not in posicion for i in ids):
        raise ErrorFlujo("FLU.val.no_consecutivos")
    ks = sorted(posicion[i] for i in ids)
    if ks != list(range(ks[0], ks[0] + len(ks))):
        raise ErrorFlujo("FLU.val.no_consecutivos")
    return sec, ks[0], ks[-1] + 1


def _envolver(modelo: ModeloFlujo, clave: str, ids: list[str], contenedor: Nodo) -> ModeloFlujo:
    nuevo, d = _copiar(modelo, clave)
    sec, a, b = _consecutivos(d, ids)
    contenedor = copy.deepcopy(contenedor)
    _asignar_ids(nuevo, contenedor)  # antes de meter los nodos: conservan su id
    interior = sec[a:b]
    if contenedor.tipo == "si":
        contenedor.ramas[0].cuerpo = interior
    else:
        contenedor.cuerpo = interior
    sec[a:b] = [contenedor]
    _comprobar(d)
    return nuevo


def envolver_en_si(modelo: ModeloFlujo, clave: str, ids: list[str], condicion: str) -> ModeloFlujo:
    """Mete los nodos consecutivos ``ids`` en la rama «sí» de un ``si`` nuevo."""
    return _envolver(modelo, clave, ids, nuevo_nodo("si", condicion=condicion))


def envolver_en_ciclo(
    modelo: ModeloFlujo, clave: str, ids: list[str], tipo: str, **campos: str
) -> ModeloFlujo:
    """Mete los nodos consecutivos ``ids`` en el cuerpo de un ciclo nuevo.

    Mete los nodos consecutivos ``ids`` en el cuerpo de un ciclo nuevo (``mientras``,
    ``hacer_mientras``, ``para`` o ``para_cada``).
    """
    if tipo not in TIPOS_CICLO:
        raise ErrorFlujo("FLU.val.tipo", tipo=tipo, validos=", ".join(TIPOS_CICLO))
    return _envolver(modelo, clave, ids, nuevo_nodo(tipo, **campos))


def editar(modelo: ModeloFlujo, clave: str, nodo_id: str, campo: str, valor: str) -> ModeloFlujo:
    """Cambia un texto del nodo.

    Cambia un texto del nodo: un campo de ``CAMPOS`` o la etiqueta de una rama/caso (``rama:K`` en
    ``si``, ``caso:K`` en ``segun``/``coincidir``).
    """
    nuevo, d = _copiar(modelo, clave)
    _, _, n = _nodo(d, nodo_id)
    valor = _limpio(valor)
    if campo.startswith(("rama:", "caso:")):
        prefijo, _, num = campo.partition(":")
        if (prefijo == "rama") != (n.tipo == "si") or not num.isdigit():
            raise ErrorFlujo("FLU.val.campo", campo=campo, tipo=n.tipo)
        k = int(num)
        if not 0 <= k < len(n.ramas):
            raise ErrorFlujo("FLU.val.indice", indice=k, total=len(n.ramas))
        _exigir_fragmento(n.tipo, "condicion" if n.tipo == "si" else "caso", valor, n)
        n.ramas[k].etiqueta = valor
        return nuevo
    if campo not in CAMPOS[n.tipo]:
        raise ErrorFlujo("FLU.val.campo", campo=campo, tipo=n.tipo)
    _exigir_fragmento(n.tipo, campo, valor, n)
    setattr(n, CAMPOS[n.tipo][campo], valor)
    return nuevo


def agregar_rama(
    modelo: ModeloFlujo, clave: str, nodo_id: str, parte: str, etiqueta: str = ""
) -> ModeloFlujo:
    """Añade una rama.

    Añade una rama: ``rama`` («sino si» al final de un ``si``), ``caso`` (en
    ``segun``/``coincidir``), ``sino`` o ``por_defecto`` (vacíos).
    """
    nuevo, d = _copiar(modelo, clave)
    _, _, n = _nodo(d, nodo_id)
    if (parte == "rama" and n.tipo == "si") or (
        parte == "caso" and n.tipo in ("segun", "coincidir")
    ):
        campo = "condicion" if n.tipo == "si" else "caso"
        _exigir_fragmento(n.tipo, campo, etiqueta, n)
        n.ramas.append(Rama(etiqueta.strip()))
    elif (parte == "sino" and n.tipo == "si") or (
        parte == "por_defecto" and n.tipo in ("segun", "coincidir")
    ):
        if n.alterno is not None:
            raise ErrorFlujo("FLU.val.ya_existe", parte=parte)
        n.alterno = []
    else:
        raise ErrorFlujo("FLU.val.parte", parte=parte)
    return nuevo


def quitar_rama(modelo: ModeloFlujo, clave: str, nodo_id: str, parte: str) -> ModeloFlujo:
    """Quita la rama ``parte``.

    Quita la rama ``parte`` (``rama:K``, ``caso:K``, ``sino`` o ``por_defecto``) con su contenido.
    Un ``si`` conserva siempre al menos una condición.
    """
    nuevo, d = _copiar(modelo, clave)
    _, _, n = _nodo(d, nodo_id)
    nombres = [nombre for nombre, _ in n.secuencias()]
    if parte not in nombres or parte in ("cuerpo", "captura"):
        raise ErrorFlujo("FLU.val.parte", parte=parte)
    if parte in ("sino", "por_defecto"):
        n.alterno = None
    else:
        k = int(parte.partition(":")[2])
        if n.tipo == "si" and len(n.ramas) == 1:
            raise ErrorFlujo("FLU.contrato.sin_ramas")
        del n.ramas[k]
    return nuevo


# ====================================================================== validación


def validar(modelo: ModeloFlujo) -> list[Problema]:
    """Todos los problemas del modelo: estructura, textos y compilación.

    Los diagnósticos del compilador se asignan al nodo dueño de la línea
    generada (``generacion.generar``); cada ``Problema`` se presenta en el
    idioma que se pida con ``texto(idioma)``. Lista vacía: el diagrama genera
    un programa válido.
    """
    problemas: list[Problema] = []
    for d in modelo.diagramas():
        try:
            _comprobar(d)
        except ErrorFlujo as e:
            problemas.append(Problema(d.clave, None, e))
        pila = list(d.cuerpo)
        while pila:
            n = pila.pop()
            campos = [(c, getattr(n, a)) for c, a in CAMPOS[n.tipo].items()]
            prefijo = "condicion" if n.tipo == "si" else "caso"
            campos += [(prefijo, r.etiqueta) for r in n.ramas]
            for campo, valor in campos:
                for err in _fallos(n.tipo, campo, valor, n):
                    problemas.append(
                        Problema(
                            d.clave, n.id, ErrorFlujo("FLU.val.fragmento", campo=campo, detalle=err)
                        )
                    )
            for _, sec in n.secuencias():
                pila.extend(sec)
    if problemas:
        return problemas
    generado = generar(modelo)
    analisis = analizar_fuente(generado.texto, "diagrama.inv")
    for fallo in analisis.errores.errores:
        k = fallo.linea - 1
        clave, nodo = generado.duenos[k] if 0 <= k < len(generado.duenos) else (None, None)
        problemas.append(
            Problema(
                clave,
                nodo,
                ErrorFlujo(
                    "FLU.val.diagnostico",
                    codigo=fallo.codigo,
                    linea=fallo.linea,
                    detalle=_como_error(fallo),
                ),
            )
        )
    return problemas
