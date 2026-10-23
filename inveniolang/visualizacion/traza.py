"""Trazador paso a paso: ejecuta un programa y registra cada instrucción.

INV-2003: el depurador de la IDE solo mostraba las variables visibles de la
activación en curso y el ``--step`` de la CLI imprimía ``repr`` de listas de
Python. Para VER cómo cambia una estructura hacen falta, en cada instrucción:
todas las activaciones de la pila de llamadas, un montículo con ids estables
(el mismo objeto conserva su id en todos los pasos, así se puede animar), qué
celdas y campos se leyeron/escribieron y la forma de cada estructura viva.

Diseño:

* :class:`InterpreteTrazado` **hereda** del intérprete de producción y solo
  sobrescribe puntos de contabilidad (entrar/salir de activaciones, declarar/
  asignar variables): la ejecución normal no paga nada por ellos. Reutiliza el
  gancho existente ``debug_on_statement`` (llamado antes de cada instrucción)
  y el registro de accesos ``registro_accesos`` (INV-2000), apagado por defecto.
* Un :class:`Paso` describe el estado DESPUÉS de ejecutar su instrucción: se
  abre en el gancho de la instrucción y se cierra en el gancho siguiente o al
  salir de la activación (así un ``retornar`` todavía muestra el marco que
  termina). Al volver de una llamada se abre un paso de "regreso" en la línea
  del llamador, que recoge, por ejemplo, la asignación del valor devuelto.
* Las instrucciones de módulos importados (biblioteca estándar incluida)
  tienen líneas de OTRO archivo: se agrupan en el paso de la llamada del
  programa principal (``p.apilar(3)`` es un paso con todas sus escrituras).
* El montículo se reconstruye por paso, pero un nodo solo se vuelve a copiar
  si se escribió (o es nuevo); los nodos sin cambios se comparten entre pasos.
  Las escrituras posibles son exactamente las que avisa ``registro_accesos``
  (asignación a celda/campo, mapear/filtrar); los objetos recién creados no
  tienen copia previa.
* Límites: ``max_pasos`` (truncado), un presupuesto total de celdas copiadas
  (:data:`MAX_CELDAS_TRAZA`) y los límites de iteraciones/tiempo/recursión
  del propio intérprete, que siguen activos.
"""

from __future__ import annotations

import math
import os
import sys
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ..core import analizar_fuente
from ..i18n import idioma_actual, normalizar_idioma
from ..interpreter import (
    BreakException,
    ContinueException,
    DebugStopped,
    InstanciaObjeto,
    Interpreter,
    ReturnException,
    ValorFuncion,
)
from ..modulos import CargadorMemoria
from ..traductor import PALABRAS_CLAVE, tokens_con_posicion
from .clasificador import clasificar
from .modelo import (
    Acceso,
    Marco,
    NodoMonticulo,
    Paso,
    Traza,
    Valor,
    VariableMarco,
)

__all__ = [
    "MAX_ACCESOS_POR_PASO",
    "MAX_CELDAS_TRAZA",
    "MAX_PASOS_TRAZA",
    "InterpreteTrazado",
    "detectar_idioma",
    "trazar",
]

# Tope absoluto de pasos que acepta `trazar` (cada paso guarda marcos y
# montículo: sin tope, un cliente podría pedir una traza que agote la memoria).
MAX_PASOS_TRAZA = 100_000
# Celdas (valores) copiadas en total al construir montículos; al agotarse la
# traza se trunca. Los nodos sin cambios se comparten y no cuentan.
MAX_CELDAS_TRAZA = 2_000_000
# Accesos guardados por paso (una llamada a la biblioteca que recorre una
# lista entera puede producir cientos; se conservan los primeros).
MAX_ACCESOS_POR_PASO = 500

_NOMBRE_GLOBAL = "<global>"
_EXCEPCIONES_DE_CONTROL = (ReturnException, BreakException, ContinueException)


class _PresupuestoAgotado(Exception):
    """Se superó :data:`MAX_CELDAS_TRAZA`."""


def detectar_idioma(codigo: str) -> str | None:
    """Idioma de las palabras clave del programa (``"es"``/``"en"``), o None si empata.

    Cuenta los lexemas de palabras clave que solo existen en un idioma
    (``mientras`` frente a ``while``); ``main`` o ``constructor`` no cuentan.
    """
    tokens, _ = tokens_con_posicion(codigo)
    cuenta = {"es": 0, "en": 0}
    for tok in tokens:
        par = PALABRAS_CLAVE.get(tok.tipo)
        if par is None or par[0] == par[1]:
            continue
        if tok.lexema == par[0]:
            cuenta["es"] += 1
        elif tok.lexema == par[1]:
            cuenta["en"] += 1
    if cuenta["es"] == cuenta["en"]:
        return None
    return "es" if cuenta["es"] > cuenta["en"] else "en"


# ====================================================================== montículo


class _Monticulo:
    """Ids estables por objeto de Python y copias inmutables compartidas.

    Guarda una referencia fuerte a cada objeto numerado: si el recolector lo
    liberara, Python podría reutilizar su ``id()`` para otro objeto y dos
    objetos distintos compartirían id en la traza. Todo se libera al terminar
    ``trazar``.

    Cambios: un objeto marcado entero (``_sucios``) se vuelve a copiar; si solo
    se escribieron celdas concretas de un arreglo/matriz (``_celdas``), se
    parchean esas celdas sobre la copia anterior. Rellenar un arreglo de mil
    elementos cuesta así mil celdas y no un millón.
    """

    # Valores escalares compartidos (inmutables); tope para no crecer sin fin.
    _MAX_ESCALARES = 50_000

    def __init__(self, presupuesto: int = MAX_CELDAS_TRAZA):
        self._ids: dict[int, tuple[object, int]] = {}
        self._cache: dict[int, tuple[NodoMonticulo, tuple[object, ...]]] = {}
        self._sucios: set[int] = set()
        self._celdas: dict[int, set[tuple[int, ...]]] = {}
        self._escalares: dict[tuple[type, Any], Valor] = {}
        self.celdas = 0
        self.presupuesto = presupuesto

    def id_de(self, obj: object) -> int:
        """Id estable de ``obj`` (se asigna en orden de descubrimiento, desde 1)."""
        par = self._ids.get(id(obj))
        if par is None:
            n = len(self._ids) + 1
            self._ids[id(obj)] = (obj, n)
            return n
        return par[1]

    def marcar(self, obj: object, indices: tuple[int, ...] = ()) -> None:
        """Avisa de que ``obj`` cambió (en ``indices`` si se dan) para el próximo paso."""
        par = self._ids.get(id(obj))
        if par is None:
            return  # aún sin copia: se construirá entera
        nid = par[1]
        if indices and isinstance(obj, list) and nid not in self._sucios:
            self._celdas.setdefault(nid, set()).add(indices)
        else:
            self._sucios.add(nid)
            self._celdas.pop(nid, None)

    def valor(self, x: Any) -> Valor:
        """Convierte un valor del intérprete al :class:`Valor` del contrato."""
        if isinstance(x, (list, InstanciaObjeto)):
            return Valor.ref(self.id_de(x))
        clave = (type(x), x)
        try:
            compartido = self._escalares.get(clave)
        except TypeError:  # valor no hashable (no ocurre con los del lenguaje)
            compartido = None
        if compartido is not None:
            return compartido
        nuevo = self._escalar(x)
        if len(self._escalares) < self._MAX_ESCALARES and not isinstance(x, ValorFuncion):
            self._escalares[clave] = nuevo
        return nuevo

    @staticmethod
    def _escalar(x: Any) -> Valor:
        if isinstance(x, bool):
            return Valor.escalar("bool", x)
        if isinstance(x, int):
            return Valor.escalar("int", x)
        if isinstance(x, float):
            # JSON estándar no tiene inf/nan: se guardan como texto.
            return Valor.escalar("float", x if math.isfinite(x) else repr(x))
        if isinstance(x, str):
            return Valor.escalar("string", x)
        if x is None:
            return Valor.escalar("null", None)
        if isinstance(x, ValorFuncion):
            return Valor.escalar("funcion", x.nombre_subrutina or "lambda")
        return Valor.escalar(type(x).__name__, str(x))

    @staticmethod
    def _hijos(obj: object) -> tuple[object, ...]:
        valores: list[Any]
        if isinstance(obj, InstanciaObjeto):
            valores = list(obj.campos.values())
        else:
            assert isinstance(obj, list)
            if obj and all(isinstance(fila, list) for fila in obj):
                valores = [x for fila in obj for x in fila]
            else:
                valores = obj
        return tuple(x for x in valores if isinstance(x, (list, InstanciaObjeto)))

    def _construir(self, obj: object, nid: int) -> NodoMonticulo:
        if isinstance(obj, InstanciaObjeto):
            campos = {k: self.valor(v) for k, v in obj.campos.items()}
            self._gastar(len(campos))
            return NodoMonticulo(nid, "objeto", obj.clase, (), campos)
        assert isinstance(obj, list)
        if obj and all(isinstance(fila, list) for fila in obj):
            filas = tuple(tuple(self.valor(x) for x in fila) for fila in obj)
            self._gastar(sum(len(f) for f in filas))
            return NodoMonticulo(nid, "matriz", None, filas)
        elementos = tuple(self.valor(x) for x in obj)
        self._gastar(len(elementos))
        return NodoMonticulo(nid, "arreglo", None, elementos)

    def _parchear(
        self, obj: list[Any], previo: NodoMonticulo, celdas: set[tuple[int, ...]]
    ) -> tuple[NodoMonticulo, bool]:
        """Copia ``previo`` cambiando solo ``celdas``; dice si alguna era/es referencia."""
        filas = list(previo.elementos)
        refs = False
        if previo.tipo == "matriz":
            por_fila: dict[int, list[Valor]] = {}
            for f, c in (ind for ind in celdas if len(ind) == 2):
                fila = por_fila.setdefault(f, list(filas[f]))
                refs = refs or fila[c].es_ref
                fila[c] = self.valor(obj[f][c])
                refs = refs or fila[c].es_ref
            for f, fila in por_fila.items():
                filas[f] = tuple(fila)
        else:
            for (i,) in (ind for ind in celdas if len(ind) == 1):
                refs = refs or filas[i].es_ref
                filas[i] = self.valor(obj[i])
                refs = refs or filas[i].es_ref
        self._gastar(len(celdas))
        return NodoMonticulo(previo.id, previo.tipo, None, tuple(filas)), refs

    def _gastar(self, n: int) -> None:
        self.celdas += n
        if self.celdas > self.presupuesto:
            raise _PresupuestoAgotado()

    def instantanea(self, raices: Iterable[object]) -> dict[int, NodoMonticulo]:
        """Nodos alcanzables desde ``raices``, ordenados por id."""
        resultado: dict[int, NodoMonticulo] = {}
        pendientes = deque(raices)
        while pendientes:
            obj = pendientes.popleft()
            nid = self.id_de(obj)
            if nid in resultado:
                continue
            guardado = self._cache.get(nid)
            if guardado is None or nid in self._sucios:
                nodo = self._construir(obj, nid)
                if guardado is not None and guardado[0] == nodo:
                    nodo = guardado[0]  # sin cambios reales: se comparte la copia
                hijos = self._hijos(obj)
            elif nid in self._celdas:
                assert isinstance(obj, list)
                nodo, refs = self._parchear(obj, guardado[0], self._celdas[nid])
                hijos = self._hijos(obj) if refs else guardado[1]
            else:
                nodo, hijos = guardado
            self._cache[nid] = (nodo, hijos)
            self._sucios.discard(nid)
            self._celdas.pop(nid, None)
            resultado[nid] = nodo
            pendientes.extend(hijos)
        return dict(sorted(resultado.items()))


def _tipo_escalar(valor: Any) -> str:
    if isinstance(valor, bool):
        return "bool"
    if isinstance(valor, int):
        return "int"
    if isinstance(valor, float):
        return "float"
    if isinstance(valor, str):
        return "string"
    if isinstance(valor, InstanciaObjeto):
        return valor.clase
    if isinstance(valor, ValorFuncion):
        return "funcion"
    return "null" if valor is None else type(valor).__name__


def _tipo_variable(valor: Any, declarado: str | None) -> str:
    """Tipo para mostrar: el declarado, completado con ``[]``/``[][]`` en arreglos.

    Los parámetros arreglo se declaran con su tipo de ELEMENTO y las
    declaraciones de arreglo no registran tipo en el marco; la forma (``[]``
    o ``[][]``) se toma del valor real.
    """
    if not isinstance(valor, list):
        return declarado or _tipo_escalar(valor)
    dims = "[][]" if valor and all(isinstance(f, list) for f in valor) else "[]"
    if declarado and "[" in declarado:
        return declarado
    base = declarado or getattr(valor, "tipo", None)
    if base is None:
        celdas = [x for f in valor for x in (f if isinstance(f, list) else [f])]
        base = next((_tipo_escalar(x) for x in celdas if x is not None), "?")
    return base + dims


# ====================================================================== registro


class _Registro:
    """Máquina de pasos: abre/cierra pasos y construye cada :class:`Paso`."""

    def __init__(self, idioma: str, max_pasos: int, presupuesto: int):
        self.idioma = idioma
        self.max_pasos = max_pasos
        self.monticulo = _Monticulo(presupuesto)
        self.pasos: list[Paso] = []
        self.truncada = False
        self.interp: InterpreteTrazado | None = None
        # Paso abierto: (linea, columna, profundidad de la activación).
        self.pendiente: tuple[int, int, int] | None = None
        self.accesos: list[tuple[str, str | None, object, tuple[int, ...], str | None]] = []
        self.salida_vista = 0
        # (linea, columna) en curso de cada activación, de la base al tope.
        self.lineas: list[tuple[int, int]] = []
        # Nombres e instancias de la pila en el último gancho: al salir de una
        # activación el intérprete ya desapiló su nombre (ver al_salir).
        self.nombres: list[str] = []
        self.instancias: list[object] = []
        self._errores_vistos: list[BaseException] = []

    # ---- ganchos del intérprete ----

    def al_instruccion(self, snap: Mapping[str, Any], pausar: bool) -> bool:
        """``debug_on_statement``: cierra el paso anterior y abre el de esta instrucción."""
        interp = self.interp
        if interp is None or self.truncada or interp.profundidad_foranea:
            return False
        nombres = list(interp._pila_subrutinas)
        instancias = list(interp._pila_instancias)
        linea, columna = int(snap.get("linea") or 0), int(snap.get("columna") or 0)
        if self.pendiente is not None:
            self._cerrar(nombres, instancias, (linea, columna))
            if self.truncada:
                return False
        if len(self.pasos) >= self.max_pasos:
            self._truncar()
            return False
        prof = interp.profundidad()
        del self.lineas[prof:]
        while len(self.lineas) < prof:
            self.lineas.append((0, 0))  # activaciones sin instrucciones propias aún
        self.lineas[prof - 1] = (linea, columna)
        self.pendiente = (linea, columna, prof)
        self.nombres, self.instancias = nombres, instancias
        return False

    def al_acceso(
        self,
        op: str,
        var: str | None,
        obj: object,
        indices: Sequence[int],
        campo: str | None,
    ) -> None:
        """``registro_accesos``: anota el acceso y marca como cambiado lo escrito."""
        if op == "escribe" and obj is not None:
            self.monticulo.marcar(obj, tuple(indices))
        if self.pendiente is not None and len(self.accesos) < MAX_ACCESOS_POR_PASO:
            if var is None and campo is not None and self.interp is not None:
                if obj is self.interp._instancia_actual():
                    var = "este" if self.idioma == "es" else "this"  # este.campo
            self.accesos.append((op, var, obj, tuple(indices), campo))

    def al_salir(self) -> None:
        """Antes de desapilar una activación: cierra su último paso con el marco vivo."""
        interp = self.interp
        if interp is None:
            return
        prof = interp.profundidad()
        if self.pendiente is not None and self.pendiente[2] == prof and not self.truncada:
            exc = sys.exc_info()[1]
            en_error = (
                exc is not None
                and not isinstance(exc, _EXCEPCIONES_DE_CONTROL)
                and all(exc is not e for e in self._errores_vistos)
            )
            self._cerrar(self.nombres, self.instancias, None)
            llamador = prof - 1
            if en_error and exc is not None:
                # Un error se propaga: el último paso es donde ocurrió; no hay
                # "regreso" al llamador (lo habrá si un intentar lo captura).
                self._errores_vistos.append(exc)
            elif (
                not self.truncada
                and llamador >= 2
                and not interp.profundidad_foranea
                and len(self.lineas) >= llamador
            ):
                if len(self.pasos) >= self.max_pasos:
                    self._truncar()
                else:
                    linea, columna = self.lineas[llamador - 1]
                    self.pendiente = (linea, columna, llamador)
                    nombre = self.nombres[llamador - 1] if len(self.nombres) >= llamador else ""
                    self.nombres = self.nombres[: llamador - 1]
                    if "." in nombre and self.instancias:
                        self.instancias = self.instancias[:-1]
        del self.lineas[prof - 1 :]

    def terminar(self) -> None:
        """Cierra el paso abierto al acabar la ejecución."""
        interp = self.interp
        if self.pendiente is not None and interp is not None and not self.truncada:
            self._cerrar(list(interp._pila_subrutinas), list(interp._pila_instancias), None)

    # ---- construcción de pasos ----

    def _truncar(self) -> None:
        self.truncada = True
        self.pendiente = None
        self.accesos = []
        if self.interp is not None:
            # _debug_ejecucion lanza DebugStopped en la próxima instrucción.
            self.interp.debug_detener = True
            self.interp.registro_accesos = None

    def _cerrar(
        self,
        nombres: list[str],
        instancias: list[object],
        siguiente: tuple[int, int] | None,
    ) -> None:
        interp = self.interp
        assert interp is not None and self.pendiente is not None
        linea, columna, _ = self.pendiente
        try:
            marcos, raices = self._marcos(nombres, instancias, siguiente)
            objetos = [a[2] for a in self.accesos if a[2] is not None]
            monticulo = self.monticulo.instantanea(list(raices) + objetos)
        except _PresupuestoAgotado:
            self._truncar()
            return
        accesos = tuple(
            Acceso(op, var, self.monticulo.id_de(obj) if obj is not None else None, ind, campo)
            for op, var, obj, ind, campo in self.accesos
        )
        salida = interp.salida
        nueva = tuple(salida[self.salida_vista :])
        self.salida_vista = len(salida)
        self.pasos.append(
            Paso(
                len(self.pasos) + 1,
                linea,
                columna,
                marcos,
                monticulo,
                accesos,
                nueva,
                clasificar(marcos, monticulo),
            )
        )
        self.pendiente = None
        self.accesos = []

    def _marcos(
        self,
        nombres: list[str],
        instancias: list[object],
        siguiente: tuple[int, int] | None,
    ) -> tuple[tuple[Marco, ...], list[object]]:
        """Marcos base→tope y los objetos raíz (valores de variables y ``este``)."""
        interp = self.interp
        assert interp is not None
        este = "este" if self.idioma == "es" else "this"
        marcos: list[Marco] = []
        raices: list[object] = []
        pendientes_inst = list(instancias)
        for i, (nombre, frames) in enumerate(interp.activaciones(nombres)):
            variables: dict[str, VariableMarco] = {}
            if "." in nombre and pendientes_inst:
                inst = pendientes_inst.pop(0)
                if isinstance(inst, InstanciaObjeto):
                    variables[este] = VariableMarco(inst.clase, self.monticulo.valor(inst))
                    raices.append(inst)
            for frame in frames:
                tipos = getattr(frame, "tipos", {})
                for k, v in frame.items():
                    variables[k] = VariableMarco(
                        _tipo_variable(v, tipos.get(k)), self.monticulo.valor(v)
                    )
                    if isinstance(v, (list, InstanciaObjeto)):
                        raices.append(v)
            if i < len(self.lineas):
                linea = self.lineas[i][0]
            else:
                linea = siguiente[0] if siguiente is not None else 0
            marcos.append(Marco(nombre, linea, variables))
        return tuple(marcos), raices


# ====================================================================== intérprete


class InterpreteTrazado(Interpreter):
    """Intérprete de producción + contabilidad de activaciones para la traza.

    Solo sobrescribe métodos de contabilidad; la semántica del lenguaje es la
    de :class:`Interpreter` (mismas salidas y errores, lo comprueban las
    pruebas sobre el currículo completo).
    """

    def __init__(self, error_manager: Any, tabla: Any, registro: _Registro):
        super().__init__(error_manager, tabla)
        self._registro = registro
        registro.interp = self
        # Contextos suspendidos por la invocación de un lambda, que reemplaza
        # la pila de marcos entera: (pila, base, bases_previas, nombres hasta ahí).
        self._suspendidos: list[tuple[list[Any], int, list[int], int]] = []
        # >0 mientras corre código de un módulo importado (ver docstring del módulo).
        self.profundidad_foranea = 0
        self.debug = True
        self.debug_on_statement = registro.al_instruccion
        self.registro_accesos = registro.al_acceso

    # ---- pila de activaciones ----

    def _contextos(self) -> list[tuple[list[Any], int, list[int], int]]:
        actual = (self.pila_marcos, self._base, self._bases_previas, len(self._pila_subrutinas))
        return self._suspendidos + [actual]

    def profundidad(self) -> int:
        """Número de activaciones vivas, contando el ámbito global."""
        return sum(len(previas) + 1 for _, _, previas, _ in self._contextos())

    def activaciones(self, nombres: Sequence[str]) -> list[tuple[str, list[Any]]]:
        """``(nombre, marcos de bloque)`` de cada activación, de la base al tope.

        Una activación ocupa ``pila_marcos[base_k : base_{k+1}]``. Cada
        ``_entrar_marco`` va acompañado de un nombre en ``_pila_subrutinas``
        (los inicializadores de campos/estáticos se nombran en esta clase); un
        lambda abre un contexto nuevo cuya base 1 deja fuera el marco global.
        """
        resultado: list[tuple[str, list[Any]]] = []
        contextos = self._contextos()
        inicio_nombres = 0
        for c, (pila, base, previas, _) in enumerate(contextos):
            bases = list(previas) + [base]
            for k, ini in enumerate(bases):
                fin = bases[k + 1] if k + 1 < len(bases) else len(pila)
                if c == 0 and k == 0:
                    resultado.append((_NOMBRE_GLOBAL, list(pila[0:fin])))
                    continue
                j = inicio_nombres + (k - 1 if c == 0 else k)
                nombre = nombres[j] if 0 <= j < len(nombres) else "?"
                resultado.append((nombre, list(pila[ini:fin])))
            inicio_nombres = contextos[c][3]
        return resultado

    def _salir_marco(self) -> None:
        self._registro.al_salir()
        super()._salir_marco()

    def _invocar_valor_funcion(self, vf: Any, argumentos: Any, nodo: Any) -> Any:
        if vf.nombre_subrutina is not None:
            return super()._invocar_valor_funcion(vf, argumentos, nodo)
        self._suspendidos.append(
            (self.pila_marcos, self._base, self._bases_previas, len(self._pila_subrutinas))
        )
        try:
            return super()._invocar_valor_funcion(vf, argumentos, nodo)
        finally:
            self._suspendidos.pop()

    def _inicializar_campos(self, instancia: Any, nombre_clase: Any) -> None:
        self._pila_subrutinas.append(f"<{nombre_clase}>")
        try:
            super()._inicializar_campos(instancia, nombre_clase)
        finally:
            self._pila_subrutinas.pop()
        self._registro.monticulo.marcar(instancia)

    def _inicializar_estaticos(self, ast: Any) -> None:
        self._pila_subrutinas.append("<static>")
        try:
            super()._inicializar_estaticos(ast)
        finally:
            self._pila_subrutinas.pop()

    # ---- código de módulos importados ----
    # Cada sobrescritura añade UN marco de Python por llamada (sin lambdas ni
    # ayudantes intermedios): `trazar` amplía el límite de recursión en esa
    # proporción para que IL-EJE-040 siga disparándose antes que RecursionError.

    def _ejecutar_funcion(self, nodo: Any, argumentos: Any) -> Any:
        foranea = bool(getattr(nodo, "archivo_origen", None))
        self.profundidad_foranea += foranea
        try:
            return super()._ejecutar_funcion(nodo, argumentos)
        finally:
            self.profundidad_foranea -= foranea

    def _ejecutar_procedimiento(self, nodo: Any, argumentos: Any) -> Any:
        foranea = bool(getattr(nodo, "archivo_origen", None))
        self.profundidad_foranea += foranea
        try:
            return super()._ejecutar_procedimiento(nodo, argumentos)
        finally:
            self.profundidad_foranea -= foranea

    def _ejecutar_metodo(
        self,
        instancia: Any,
        clase_declarante: Any,
        nodo_metodo: Any,
        argumentos: Any,
        nodo_llamada: Any,
    ) -> Any:
        foranea = bool(getattr(nodo_metodo, "archivo_origen", None))
        self.profundidad_foranea += foranea
        try:
            return super()._ejecutar_metodo(
                instancia, clase_declarante, nodo_metodo, argumentos, nodo_llamada
            )
        finally:
            self.profundidad_foranea -= foranea

    def _ejecutar_constructor(
        self, instancia: Any, nombre_clase: Any, argumentos: Any, nodo: Any
    ) -> Any:
        clase = self.clases_ast.get(nombre_clase)
        foranea = bool(getattr(clase, "archivo_origen", None))
        self.profundidad_foranea += foranea
        try:
            return super()._ejecutar_constructor(instancia, nombre_clase, argumentos, nodo)
        finally:
            self.profundidad_foranea -= foranea

    # ---- variables escritas ----

    def _declarar_variable(self, nombre: Any, valor: Any) -> None:
        super()._declarar_variable(nombre, valor)
        if not self.profundidad_foranea and self.registro_accesos is not None:
            self.registro_accesos("escribe", nombre, None, (), None)

    def _asignar_variable(self, nombre: Any, valor: Any) -> None:
        super()._asignar_variable(nombre, valor)
        if not self.profundidad_foranea and self.registro_accesos is not None:
            self.registro_accesos("escribe", nombre, None, (), None)


# ====================================================================== API


def trazar(
    codigo: str,
    ruta: str = "<memoria>",
    entrada: Sequence[str] = (),
    idioma: str | None = None,
    max_pasos: int = 5000,
    modulos: Mapping[str, str] | None = None,
    ruta_fuente: str | None = None,
) -> Traza:
    """Ejecuta ``codigo`` y devuelve su :class:`Traza` paso a paso.

    Args:
        codigo: Fuente InvenioLang (palabras clave en español o inglés).
        ruta: Nombre que aparece en los diagnósticos.
        entrada: Una cadena por cada ``leer``/``read`` (nunca se lee stdin).
        idioma: ``"es"``/``"en"`` para diagnósticos y para el campo ``idioma``;
            ``None`` lo deduce de las palabras clave del programa y, si empata,
            usa el idioma del proceso.
        max_pasos: Pasos a registrar (1..``MAX_PASOS_TRAZA``); al superarlos la
            ejecución se detiene y la traza queda ``truncada``.
        modulos: ``{ruta: texto}`` para servir los ``importar`` desde memoria.
        ruta_fuente: Ruta real del archivo, base para resolver ``importar``
            desde disco (la GUI y la CLI la pasan); por defecto ``ruta``.

    Returns:
        La traza; con errores de compilación no tiene pasos y ``error`` lleva
        los diagnósticos. Un error de ejecución deja los pasos hasta el fallo.

    Raises:
        ValueError: ``max_pasos`` fuera de rango o ``idioma`` no soportado.
    """
    if isinstance(max_pasos, bool) or not isinstance(max_pasos, int):
        raise ValueError("max_pasos debe ser un entero")
    if not 1 <= max_pasos <= MAX_PASOS_TRAZA:
        raise ValueError(f"max_pasos debe estar entre 1 y {MAX_PASOS_TRAZA}")
    if idioma is not None:
        lengua = normalizar_idioma(idioma)
    else:
        lengua = detectar_idioma(codigo) or idioma_actual()
    cargador = None
    if modulos is not None:
        base = os.path.dirname(os.path.abspath(ruta_fuente or ruta))
        cargador = CargadorMemoria({os.path.join(base, k): v for k, v in modulos.items()})
    analisis = analizar_fuente(
        codigo, ruta, idioma=lengua, cargador=cargador, ruta_fuente=ruta_fuente
    )
    em = analisis.errores
    if not analisis.ok:
        return Traza(lengua, codigo, error="\n".join(em.obtener_reportes()))
    registro = _Registro(lengua, max_pasos, MAX_CELDAS_TRAZA)
    interp = InterpreteTrazado(em, analisis.tabla, registro)
    # Margen de recursión del intérprete + el marco extra por llamada de las
    # sobrescrituras de InterpreteTrazado (y el del gancho en la hoja).
    margen = interp.MAX_RECURSION * (interp.MARCOS_PYTHON_POR_LLAMADA + 2) + 2000
    if sys.getrecursionlimit() < margen:
        sys.setrecursionlimit(margen)
    try:
        interp.interpretar(analisis.ast, list(entrada) or None, usar_stdin=False)
    except DebugStopped:
        pass  # max_pasos o presupuesto de celdas alcanzado (registro.truncada)
    registro.terminar()
    error = "\n".join(em.obtener_reportes()) if em.hay_errores() else None
    return Traza(
        lengua,
        codigo,
        tuple(registro.pasos),
        registro.truncada,
        error,
        tuple(interp.salida),
    )
