"""Reglas de encaje: estructura, campos y tipos de los bloques (INV-4006).

Un editor de bloques es útil porque **no deja soltar** lo que no encaja y
dice por qué. Este módulo reúne esas reglas para que la GUI Qt, la API y la
web (que replica el catálogo) den exactamente el mismo veredicto:

* estructura: qué familia admite cada lista, mínimos y máximos, huecos
  obligatorios vacíos, ``romper``/``continuar`` fuera de lugar (mismos
  mensajes que el diagrama de flujo, ``FLU.val.*``);
* campos: cada nombre, tipo, número o literal se comprueba con el lexer real;
* tipos: inferencia estática prudente (familias ``entero``, ``real``,
  ``texto``, ``logico``, ``nulo``, ``arreglo``, ``objeto``, ``funcion`` y
  ``cualquiera``) con las MISMAS reglas que ``type_checker.py`` (la
  condición debe ser lógica, ``%`` sólo con enteros, ``+`` no mezcla texto y
  número, a un ``entero`` no se le asigna un ``real``…). Sólo se rechaza
  cuando ambas familias se conocen con certeza; en la duda decide el
  compilador real en ``edicion.validar``.

Todos los rechazos son ``ErrorBloques`` con mensaje bilingüe ``BLQ.*``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from ..flujo.extraccion import tokens_fuente
from .catalogo import TIPOS, Campo, familia_de_lista
from .modelo import Bloque, ErrorBloques, Etiqueta, ModeloBloques, nombre_parte, nombre_tipo

__all__ = [
    "Contexto",
    "Ranura",
    "error_campo",
    "exigir_completo",
    "faltantes",
    "familia",
    "motivo_rechazo",
    "problemas_de_tipos",
    "saltos_fuera_de_lugar",
]

NUMEROS = ("entero", "real")
_ARITMETICOS = ("-", "*", "/")
_ENTEROS = ("%", "&", "|", "^", "<<", ">>")
_RELACIONALES = ("<", ">", "<=", ">=")
_LOGICOS = ("&&", "||")
_CICLOS = ("mientras", "hacer_mientras", "para", "para_cada")


@dataclass(frozen=True)
class Ranura:
    """Sitio dentro de un bloque: un hueco (``indice`` None) o una posición de lista."""

    clase: str  # "hueco" o "lista"
    nombre: str
    indice: int | None = None


# ====================================================================== campos


def _tokens(texto: str) -> list[str]:
    return [t.tipo for t in tokens_fuente(texto)]


def _lista_de(texto: str, validos: tuple[str, ...]) -> bool:
    """``a, b, c`` donde cada elemento es un token de ``validos``."""
    toks = _tokens(texto)
    if not toks or len(toks) % 2 == 0:
        return False
    return all((t in validos) if k % 2 == 0 else t == "DEL_COMA" for k, t in enumerate(toks))


def _es_tipo(texto: str, retorno: bool) -> bool:
    from .lector import Ids, Lector

    lector = Lector("es", Ids())
    try:
        lector._con(texto, lambda: (lector._tipo(retorno), lector._nuevo("variable"))[1])
    except ErrorBloques:
        return False
    return True


def _es_caso(texto: str) -> bool:
    from .lector import Ids, Lector

    try:
        Lector("es", Ids()).texto_caso(texto)
    except ErrorBloques:
        return False
    return True


def error_campo(c: Campo, valor: object) -> ErrorBloques | None:
    """Motivo (bilingüe) por el que ``valor`` no sirve para el campo ``c``, o ``None``."""
    if c.clase == "bandera":
        return None if isinstance(valor, bool) else ErrorBloques("BLQ.val.campo.bandera")
    if not isinstance(valor, str):
        return ErrorBloques("BLQ.contrato.texto")
    if valor == "" and c.vacio_ok:
        return None
    if valor.strip() != valor or not valor:
        return ErrorBloques(f"BLQ.val.campo.{c.clase}", valor=valor)
    toks = _tokens(valor)
    bien = {
        "identificador": toks == ["IDENTIFICADOR"],
        "nombre_subrutina": toks in (["IDENTIFICADOR"], ["KW_MAIN"]),
        "identificadores": _lista_de(valor, ("IDENTIFICADOR",)),
        "dimensiones": _lista_de(valor, ("ENTERO_LIT", "IDENTIFICADOR")),
        "numero": toks in (["ENTERO_LIT"], ["REAL_LIT"]),
        "texto": toks == ["TEXTO_LIT"],
        "opcion": valor in c.opciones,
    }
    if c.clase in ("tipo", "tipo_retorno"):
        ok = _es_tipo(valor, c.clase == "tipo_retorno")
    elif c.clase == "literal_caso":
        ok = _es_caso(valor)
    else:
        ok = bien[c.clase]
    if ok:
        return None
    if c.clase == "opcion":
        return ErrorBloques("BLQ.val.campo.opcion", valor=valor, validas=", ".join(c.opciones))
    return ErrorBloques(f"BLQ.val.campo.{c.clase}", valor=valor)


# ====================================================================== estructura


def _faltantes_de(b: Bloque) -> Iterator[ErrorBloques]:
    desc = TIPOS[b.tipo]
    for c in desc.campos:
        err = error_campo(c, b.campos.get(c.nombre))
        if err is not None:
            yield ErrorBloques(
                "BLQ.val.en_campo", bloque=b.id, campo=nombre_parte(c.nombre), detalle=err
            )
    for h in desc.huecos:
        hijo = b.huecos.get(h.nombre)
        if hijo is None and not h.opcional:
            yield ErrorBloques(
                "BLQ.val.hueco_vacio",
                bloque=b.id,
                hueco=nombre_parte(h.nombre),
                tipo=nombre_tipo(b.tipo),
            )
        elif hijo is not None and TIPOS[hijo.tipo].forma != "valor":
            yield ErrorBloques("BLQ.contrato.no_valor", bloque=hijo.id, tipo=hijo.tipo)
    for x in desc.listas:
        elementos = b.listas.get(x.nombre, [])
        if len(elementos) < x.minimo:
            yield ErrorBloques(
                "BLQ.val.lista_minima", bloque=b.id, lista=nombre_parte(x.nombre), minimo=x.minimo
            )
        if x.maximo is not None and len(elementos) > x.maximo:
            yield ErrorBloques(
                "BLQ.val.lista_maxima", bloque=b.id, lista=nombre_parte(x.nombre), maximo=x.maximo
            )
        for e in elementos:
            if not familia_de_lista(x.acepta, e.tipo):
                yield ErrorBloques("BLQ.contrato.no_cabe", bloque=e.id, tipo=e.tipo, lista=x.nombre)
    ocultas = {
        "tiene_sino": "sino",
        "tiene_defecto": "por_defecto",
        "con_cuerpo": "cuerpo",
        "con_parametros": "parametros",
    }
    for bandera, lista in ocultas.items():
        if bandera in b.campos and not b.campos[bandera] and b.listas.get(lista):
            yield ErrorBloques(
                "BLQ.val.parte_oculta",
                bloque=b.id,
                lista=nombre_parte(lista),
                campo=nombre_parte(bandera),
            )
    if b.tipo == "arreglo" and b.listas["valores"] and b.listas["filas"]:
        yield ErrorBloques("BLQ.val.valores_y_filas", bloque=b.id)
    for _, _, hijo in b.hijos():
        yield from _faltantes_de(hijo)


def faltantes(modelo: ModeloBloques) -> list[ErrorBloques]:
    """Lo que impide escribir el programa: campos inválidos, huecos vacíos, listas."""
    salida: list[ErrorBloques] = []
    for b in modelo.programa:
        if not familia_de_lista("definicion", b.tipo):
            salida.append(
                ErrorBloques("BLQ.contrato.no_cabe", bloque=b.id, tipo=b.tipo, lista="programa")
            )
        salida.extend(_faltantes_de(b))
    return salida


def exigir_completo(modelo: ModeloBloques) -> None:
    """``ErrorBloques`` (``BLQ.error.incompleto``) con el primer faltante, si lo hay."""
    errores = faltantes(modelo)
    if errores:
        raise ErrorBloques("BLQ.error.incompleto", bloque=errores[0].bloque, detalle=errores[0])


def saltos_fuera_de_lugar(modelo: ModeloBloques) -> list[ErrorBloques]:
    """``romper`` fuera de un ciclo o ``segun`` y ``continuar`` fuera de un ciclo.

    Misma regla y mismos mensajes que la edición del diagrama de flujo
    (``flujo.edicion``); el cuerpo de una función anónima empieza de cero.
    """
    salida: list[ErrorBloques] = []

    def visitar(b: Bloque, en_ciclo: bool, en_segun: bool) -> None:
        if b.tipo == "romper" and not (en_ciclo or en_segun):
            salida.append(ErrorBloques("FLU.val.romper_fuera", bloque=b.id))
        if b.tipo == "continuar" and not en_ciclo:
            salida.append(ErrorBloques("FLU.val.continuar_fuera", bloque=b.id))
        for _, _, h in b.hijos():
            if b.tipo in ("lambda", "subrutina", "metodo", "constructor"):
                visitar(h, False, False)
            else:
                visitar(
                    h,
                    en_ciclo or b.tipo in _CICLOS,
                    (en_segun or b.tipo == "segun") and b.tipo not in _CICLOS,
                )

    for b in modelo.programa:
        visitar(b, False, False)
    return salida


# ====================================================================== tipos


@dataclass(frozen=True)
class _Simbolo:
    familia: str
    elemento: str = "cualquiera"  # familia de los elementos si es arreglo
    dims: int = 0


def familia_de_tipo(texto: str, clases: set[str]) -> _Simbolo:
    """Familia de un tipo escrito (``entero``, ``real[]``, ``Pila``, ``T``…)."""
    texto = texto.strip()
    dims = 0
    while texto.endswith("[]"):
        texto = texto[:-2].strip()
        dims += 1
    toks = _tokens(texto)
    primero = toks[0] if toks else ""
    base = {
        "KW_INT": "entero",
        "KW_FLOAT": "real",
        "KW_STRING": "texto",
        "KW_BOOL": "logico",
        "KW_FUNCION": "funcion",
        "KW_VOID": "vacio",
    }.get(primero, "cualquiera")
    if primero == "IDENTIFICADOR" and texto.split("<")[0] in clases:
        base = "objeto"
    if dims:
        return _Simbolo("arreglo", base, dims)
    return _Simbolo(base)


class Contexto:
    """Índice del modelo para inferir tipos: padres, ámbitos y declaraciones."""

    def __init__(self, modelo: ModeloBloques):
        self.modelo = modelo
        self.padres: dict[str, tuple[Bloque | None, Ranura]] = {}
        self._por_id: dict[str, Bloque] = {}
        for k, b in enumerate(modelo.programa):
            self._indexar(b, None, Ranura("lista", "programa", k))
        self.clases = {
            b.campos["nombre"]
            for b in modelo.programa
            if b.tipo in ("clase", "interfaz", "enumeracion")
        }
        self.globales = self._declaraciones(
            [b for b in modelo.programa if b.tipo in ("declarar", "arreglo")]
        )
        self.retornos: dict[str, set[str]] = {}
        for b in modelo.programa:
            if b.tipo == "subrutina":
                fam = familia_de_tipo(b.campos["retorno"], self.clases).familia
                self.retornos.setdefault(b.campos["nombre"], set()).add(fam)

    def _indexar(self, b: Bloque, padre: Bloque | None, ranura: Ranura) -> None:
        self.padres[b.id] = (padre, ranura)
        self._por_id[b.id] = b
        for nombre, k, h in b.hijos():
            self._indexar(h, b, Ranura("hueco" if k is None else "lista", nombre, k))

    def contiene(self, b: Bloque | None) -> bool:
        """¿``b`` es (este mismo objeto) un bloque del modelo?

        Se compara la identidad y no sólo el id: un bloque que se está
        arrastrando puede traer un id que coincide con otro del modelo.
        """
        return b is not None and self._por_id.get(b.id) is b

    def ancestros(self, b: Bloque) -> Iterator[Bloque]:
        """Padres de ``b`` desde el más cercano."""
        padre = self.padres.get(b.id, (None, Ranura("lista", "programa")))[0]
        while padre is not None:
            yield padre
            padre = self.padres.get(padre.id, (None, Ranura("lista", "programa")))[0]

    def _declaraciones(self, bloques: list[Bloque]) -> dict[str, set[_Simbolo]]:
        tabla: dict[str, set[_Simbolo]] = {}

        def poner(nombre: str, s: _Simbolo) -> None:
            tabla.setdefault(nombre.strip(), set()).add(s)

        pila = list(bloques)
        while pila:
            b = pila.pop()
            c = b.campos
            if b.tipo in ("declarar", "atributo", "parametro"):
                poner(c["nombre"], familia_de_tipo(c["tipo"], self.clases))
            elif b.tipo == "arreglo":
                elem = familia_de_tipo(c["tipo"], self.clases).familia
                poner(c["nombre"], _Simbolo("arreglo", elem, len(c["dimensiones"].split(","))))
            elif b.tipo == "para_cada":
                poner(c["variable"], familia_de_tipo(c["tipo"], self.clases))
            if b.tipo in ("lambda",):
                continue  # su cuerpo tiene su propio ámbito
            for _, _, h in b.hijos():
                pila.append(h)
        return tabla

    def ambito(self, b: Bloque) -> dict[str, set[_Simbolo]]:
        """Nombres visibles (con sus familias posibles) donde está ``b``."""
        tabla: dict[str, set[_Simbolo]] = {k: set(v) for k, v in self.globales.items()}
        cadena = [b, *self.ancestros(b)]
        for anc in reversed(cadena):
            if anc.tipo in ("clase",):
                miembros = [m for m in anc.listas["miembros"] if m.tipo == "atributo"]
                for k, v in self._declaraciones(miembros).items():
                    tabla[k] = v
            if anc.tipo in ("subrutina", "metodo", "constructor", "lambda"):
                locales = self._declaraciones(anc.listas["parametros"] + anc.listas["cuerpo"])
                for k, v in locales.items():
                    tabla[k] = v
        return tabla

    def atributos(self, b: Bloque) -> dict[str, set[_Simbolo]]:
        """Atributos de la clase que contiene a ``b`` (para ``este.x``)."""
        for anc in [b, *self.ancestros(b)]:
            if anc.tipo == "clase":
                return self._declaraciones(
                    [m for m in anc.listas["miembros"] if m.tipo == "atributo"]
                )
        return {}

    def subrutina(self, b: Bloque) -> Bloque | None:
        """Subrutina, método o función anónima que contiene a ``b``."""
        return next(
            (a for a in [b, *self.ancestros(b)] if a.tipo in ("subrutina", "metodo", "lambda")),
            None,
        )


def _unico(simbolos: set[_Simbolo] | None) -> _Simbolo | None:
    return next(iter(simbolos)) if simbolos and len(simbolos) == 1 else None


def familia(b: Bloque | None, ctx: Contexto, dentro: Bloque | None = None) -> str:
    """Familia del valor de ``b`` (``cualquiera`` si no se sabe con certeza).

    ``dentro``: bloque del modelo junto al que se evalúa (para un bloque que
    todavía no está en el modelo, p. ej. el que se está arrastrando).
    """
    return _simbolo(b, ctx, dentro or b).familia if b is not None else "cualquiera"


def _simbolo(b: Bloque, ctx: Contexto, lugar: Bloque | None) -> _Simbolo:
    t, c, h = b.tipo, b.campos, b.huecos
    lugar = lugar if ctx.contiene(lugar) else None
    if t == "numero":
        return _Simbolo("real" if "." in c["valor"] else "entero")
    if t in ("texto", "logico", "nulo"):
        return _Simbolo(t)
    if t in ("nuevo", "este", "padre"):
        return _Simbolo("objeto")
    if t == "nuevo_arreglo":
        elem = familia_de_tipo(c["tipo"], ctx.clases).familia
        return _Simbolo("arreglo", elem, 1)
    if t == "lambda":
        return _Simbolo("funcion")
    if t == "incremento":
        return _hijo(h["objetivo"], ctx, lugar, b)
    if t == "variable":
        if lugar is None:
            return _Simbolo("cualquiera")
        return _unico(ctx.ambito(lugar).get(c["nombre"])) or _Simbolo("cualquiera")
    if t == "propiedad" and h["objeto"] is not None and h["objeto"].tipo == "este":
        if lugar is None:
            return _Simbolo("cualquiera")
        return _unico(ctx.atributos(lugar).get(c["nombre"])) or _Simbolo("cualquiera")
    if t == "llamada":
        familias = ctx.retornos.get(c["nombre"])
        if familias and len(familias) == 1:
            return _Simbolo(next(iter(familias)))
        return _Simbolo("cualquiera")
    if t == "indice":
        col = _hijo(h["coleccion"], ctx, lugar, b)
        if col.familia == "arreglo" and col.dims > 1:
            return _Simbolo("arreglo", col.elemento, col.dims - 1)
        if col.familia == "arreglo":
            return _Simbolo(col.elemento)
        return _Simbolo("cualquiera")
    if t == "unaria":
        if c["op"] == "!":
            return _Simbolo("logico")
        interior = _hijo(h["valor"], ctx, lugar, b).familia
        return _Simbolo(interior if interior in NUMEROS else "cualquiera")
    if t == "binaria":
        op = c["op"]
        if op in _RELACIONALES or op in _LOGICOS or op in ("==", "!="):
            return _Simbolo("logico")
        izq = _hijo(h["izquierda"], ctx, lugar, b).familia
        der = _hijo(h["derecha"], ctx, lugar, b).familia
        if op == "+" and izq == der == "texto":
            return _Simbolo("texto")
        if op in ("+",) + _ARITMETICOS and izq in NUMEROS and der in NUMEROS:
            return _Simbolo("real" if "real" in (izq, der) else "entero")
        if op in _ENTEROS and izq == der == "entero":
            return _Simbolo("entero")
        return _Simbolo("cualquiera")
    if t == "ternaria":
        a = _hijo(h["si_verdadero"], ctx, lugar, b)
        z = _hijo(h["si_falso"], ctx, lugar, b)
        return a if a == z else _Simbolo("cualquiera")
    return _Simbolo("cualquiera")


def _hijo(hijo: Bloque | None, ctx: Contexto, lugar: Bloque | None, padre: Bloque) -> _Simbolo:
    if hijo is None:
        return _Simbolo("cualquiera")
    return _simbolo(hijo, ctx, hijo if ctx.contiene(hijo) else lugar)


def _asignable(destino: str, valor: str) -> bool:
    """¿Se puede guardar un valor de familia ``valor`` donde se espera ``destino``?

    Mismo criterio que ``type_checker._compatible``: entero → real se
    promueve; ``nulo`` sólo vale para objetos (y arreglos/funciones).
    """
    if "cualquiera" in (destino, valor) or destino == "vacio":
        return True
    if destino == valor:
        return True
    if destino == "real" and valor == "entero":
        return True
    return valor == "nulo" and destino in ("objeto", "arreglo", "funcion")


def _rechazo(hueco: str, padre: Bloque, esperado: str, recibido: str) -> ErrorBloques:
    return ErrorBloques(
        "BLQ.encaje.tipo",
        bloque=padre.id,
        hueco=nombre_parte(hueco),
        tipo=nombre_tipo(padre.tipo),
        esperado=Etiqueta(f"BLQ.familia.{esperado}"),
        recibido=Etiqueta(f"BLQ.familia.{recibido}"),
    )


def _esperado(padre: Bloque, ranura: Ranura, ctx: Contexto) -> tuple[str, str] | None:
    """(familia esperada, familia con la que se compara) según el hueco y sus vecinos."""
    t, c = padre.tipo, padre.campos
    if t == "binaria":
        op = c["op"]
        if op in _LOGICOS:
            return "logico", "logico"
        if op in _RELACIONALES or op in _ARITMETICOS:
            return "numero", "numero"
        if op in _ENTEROS:
            return "entero", "entero"
        otro = padre.huecos["derecha" if ranura.nombre == "izquierda" else "izquierda"]
        vecino = familia(otro, ctx, padre)
        if op == "+":
            if vecino in NUMEROS:
                return "numero", "numero"
            if vecino == "texto":
                return "texto", "texto"
            return "numero_o_texto", "numero_o_texto"
        if op in ("==", "!=") and vecino != "cualquiera":
            return vecino, "comparable"
        return None
    if t == "unaria":
        return ("logico", "logico") if c["op"] == "!" else ("numero", "numero")
    if t in ("asignar",) and ranura.nombre == "valor":
        destino = familia(padre.huecos["destino"], ctx, padre)
        if c["op"] == "=":
            return destino, "asignable"
        if c["op"] == "+=" and destino == "texto":
            return "texto", "texto"
        return ("entero", "entero") if c["op"] == "%=" else ("numero", "numero")
    if t in ("declarar", "atributo") and ranura.nombre == "valor":
        return familia_de_tipo(c["tipo"], ctx.clases).familia, "asignable"
    if t == "arreglo" or (t == "fila" and ranura.clase == "lista"):
        decl = (
            padre
            if t == "arreglo"
            else next((a for a in ctx.ancestros(padre) if a.tipo == "arreglo"), None)
        )
        if decl is None:
            return None
        return familia_de_tipo(decl.campos["tipo"], ctx.clases).familia, "asignable"
    if t == "retornar":
        sub = ctx.subrutina(padre)
        if sub is None:
            return None
        return familia_de_tipo(sub.campos["retorno"], ctx.clases).familia, "asignable"
    if t == "indice" and ranura.nombre == "coleccion":
        return "coleccion", "coleccion"
    if t == "para_cada" and ranura.nombre == "coleccion":
        return "arreglo", "coleccion"
    return None


def _cumple(esperado: str, criterio: str, recibido: str) -> bool:
    if recibido == "cualquiera" or esperado == "cualquiera":
        return True
    if criterio == "asignable":
        return _asignable(esperado, recibido)
    if criterio == "comparable":
        if esperado in NUMEROS:
            return recibido in NUMEROS
        if recibido == "nulo" or esperado == "nulo":
            return esperado not in NUMEROS + ("logico", "texto") and recibido not in NUMEROS + (
                "logico",
                "texto",
            )
        return recibido == esperado
    if criterio == "numero":
        return recibido in NUMEROS
    if criterio == "numero_o_texto":
        return recibido in NUMEROS + ("texto",)
    if criterio == "coleccion":
        return (
            recibido in ("arreglo", "texto") if esperado == "coleccion" else recibido == "arreglo"
        )
    return recibido == esperado


_FORMA_HUECO = {
    "asignable": ("variable", "indice", "propiedad"),
    "llamada": ("llamada", "llamada_metodo"),
    "variable": ("variable",),
}


def motivo_rechazo(
    modelo: ModeloBloques | Contexto, bloque: Bloque, padre: Bloque | None, ranura: Ranura
) -> ErrorBloques | None:
    """Por qué ``bloque`` NO puede ir en ``ranura`` de ``padre`` (``None``: sí encaja).

    ``padre`` debe estar en el modelo (``None``: el programa, lista
    ``programa``). Es la comprobación «al soltar» del editor: familia de la
    lista o del hueco, máximo de la lista y familia del valor.
    """
    ctx = modelo if isinstance(modelo, Contexto) else Contexto(modelo)
    desc = TIPOS[bloque.tipo]
    if padre is None:
        if not familia_de_lista("definicion", bloque.tipo):
            return ErrorBloques(
                "BLQ.encaje.solo_dentro", bloque=bloque.id, tipo=nombre_tipo(bloque.tipo)
            )
        return None
    pdesc = TIPOS[padre.tipo]
    if ranura.clase == "lista":
        lista = pdesc.lista(ranura.nombre)
        if lista is None:
            return ErrorBloques(
                "BLQ.error.parte", parte=nombre_parte(ranura.nombre), tipo=nombre_tipo(padre.tipo)
            )
        if not familia_de_lista(lista.acepta, bloque.tipo):
            return ErrorBloques(
                f"BLQ.encaje.lista.{lista.acepta}",
                bloque=bloque.id,
                tipo=nombre_tipo(bloque.tipo),
                destino=nombre_tipo(padre.tipo),
            )
        actuales = [x for x in padre.listas[ranura.nombre] if x.id != bloque.id]
        if lista.maximo is not None and len(actuales) >= lista.maximo:
            return ErrorBloques(
                "BLQ.encaje.lleno", lista=nombre_parte(ranura.nombre), maximo=lista.maximo
            )
        if desc.forma != "valor" and not (padre.tipo == "arreglo" or padre.tipo == "fila"):
            return None
    else:
        hueco = pdesc.hueco(ranura.nombre)
        if hueco is None:
            return ErrorBloques(
                "BLQ.error.parte", parte=nombre_parte(ranura.nombre), tipo=nombre_tipo(padre.tipo)
            )
        if desc.forma != "valor":
            return ErrorBloques("BLQ.encaje.no_valor", tipo=nombre_tipo(bloque.tipo))
        formas = _FORMA_HUECO.get(hueco.acepta)
        if formas is not None and bloque.tipo not in formas:
            return ErrorBloques(f"BLQ.encaje.hueco.{hueco.acepta}", tipo=nombre_tipo(bloque.tipo))
        recibido = familia(bloque, ctx, padre)
        if hueco.acepta == "logico" and recibido not in ("logico", "cualquiera"):
            return _rechazo(ranura.nombre, padre, "logico", recibido)
        if hueco.acepta == "numero" and recibido not in NUMEROS + ("cualquiera",):
            return _rechazo(ranura.nombre, padre, "numero", recibido)
    esperado = _esperado(padre, ranura, ctx)
    if esperado is None:
        return None
    recibido = familia(bloque, ctx, padre)
    if not _cumple(esperado[0], esperado[1], recibido):
        return _rechazo(ranura.nombre, padre, esperado[0], recibido)
    return None


def problemas_de_tipos(modelo: ModeloBloques) -> list[ErrorBloques]:
    """Todo bloque colocado donde, por su tipo, no encaja."""
    ctx = Contexto(modelo)
    salida: list[ErrorBloques] = []
    for ident, (padre, ranura) in ctx.padres.items():
        if padre is None:
            continue
        bloque = next(b for n, k, b in padre.hijos() if b.id == ident)
        err = motivo_rechazo(ctx, bloque, padre, ranura)
        if err is not None and err.clave_mensaje.startswith("BLQ.encaje.tipo"):
            err.bloque = ident
            salida.append(err)
    return salida
