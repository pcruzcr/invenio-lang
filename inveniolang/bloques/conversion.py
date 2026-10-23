"""Código ⇄ bloques y bloques ⇄ diagrama de flujo (INV-4005).

El diagrama de flujo y los bloques son dos vistas del **mismo árbol
estructurado** (``docs/bloques.md``):

* código → bloques: ``flujo.modelo_desde_codigo`` (compilador real, árbol
  estructurado con los textos del estudiante) y después ``lector.py``
  descompone cada texto en bloques; las instrucciones conservan el id del
  nodo del diagrama;
* bloques → código: ``a_flujo`` vuelve a escribir cada texto
  (``escritor.py``) y la generación del programa es la de
  ``flujo.generacion`` (palabras clave en es/en, formateador del proyecto);
* bloques → diagrama de flujo: ``a_flujo`` (mismos ids: seleccionar un bloque
  selecciona su caja y al revés).
"""

from __future__ import annotations

from .. import flujo
from ..flujo import modelo as F  # noqa: N812 - alias corto del modelo de flujo
from ..flujo.generacion import generar
from ..i18n import normalizar_idioma
from ..modulos import CargadorModulos
from .escritor import Escritor
from .lector import Ids, Lector
from .modelo import Bloque, ErrorBloques, ModeloBloques
from .reglas import exigir_completo

__all__ = [
    "a_flujo",
    "bloques_desde_codigo",
    "claves_de_diagramas",
    "codigo_con_lineas",
    "codigo_desde_bloques",
    "desde_flujo",
    "traducir_bloques",
]

_PROCEDIMIENTO = ("vacio", "void")


def desde_flujo(modelo: F.ModeloFlujo) -> ModeloBloques:
    """Bloques de un modelo de diagrama de flujo (sus textos deben ser válidos)."""
    ids = Ids({n.id for d in modelo.diagramas() for n in F.recorrer(d.cuerpo)})
    lector = Lector(modelo.idioma, ids)
    programa: list[Bloque] = []
    for el in modelo.elementos:
        if el.tipo == "codigo":
            programa.append(lector.texto_codigo(el.texto, en_clase=False))
        elif el.tipo == "subrutina":
            assert el.diagrama is not None
            programa.append(_definicion(lector, el.diagrama, "subrutina"))
        else:
            clase = lector.texto_cabecera(el.texto)
            for m in el.miembros:
                if m.diagrama is None:
                    clase.listas["miembros"].append(lector.texto_codigo(m.texto, en_clase=True))
                else:
                    clase.listas["miembros"].append(
                        _definicion(lector, m.diagrama, m.diagrama.tipo)
                    )
            programa.append(clase)
    return ModeloBloques(modelo.idioma, programa)


def _definicion(lector: Lector, d: F.Diagrama, tipo: str) -> Bloque:
    b = lector.texto_firma(d.firma, tipo)
    b.linea = d.linea
    b.listas["cuerpo"] = lector.instrucciones(d.cuerpo)
    return b


class _Claves:
    """Claves de diagrama como las de la extracción (sobrecargas: ``#2``, ``#3``…)."""

    def __init__(self) -> None:
        self._vistas: dict[str, int] = {}

    def clave(self, base: str) -> str:
        n = self._vistas.get(base, 0) + 1
        self._vistas[base] = n
        return base if n == 1 else f"{base}#{n}"


def a_flujo(modelo: ModeloBloques) -> F.ModeloFlujo:
    """Diagrama de flujo de los bloques (mismos ids de instrucción).

    No exige que el programa esté completo: un hueco vacío se escribe como
    texto vacío (y la validación del diagrama lo señala), para que la vista
    de flujo acompañe al estudiante mientras construye.
    """
    esc = Escritor(modelo.idioma)
    claves = _Claves()
    elementos: list[F.Elemento] = []
    for b in modelo.programa:
        if b.tipo == "subrutina":
            elementos.append(_elemento_subrutina(esc, claves, b, None))
        elif b.tipo in ("clase", "interfaz"):
            miembros = []
            for m in b.listas["miembros"]:
                if m.tipo == "atributo" or (m.tipo == "metodo" and not m.campos["con_cuerpo"]):
                    miembros.append(F.Elemento("codigo", texto=esc.codigo(m)))
                else:
                    miembros.append(_elemento_subrutina(esc, claves, m, b.campos["nombre"]))
            elementos.append(F.Elemento("clase", texto=esc.cabecera(b), miembros=miembros))
        else:
            elementos.append(F.Elemento("codigo", texto=esc.codigo(b)))
    return F.ModeloFlujo(modelo.idioma, elementos)


def _elemento_subrutina(esc: Escritor, claves: _Claves, b: Bloque, clase: str | None) -> F.Elemento:
    nombre = b.campos["nombre"]
    if b.tipo == "subrutina":
        if nombre == "main":
            tipo = "main"
        else:
            tipo = "procedimiento" if b.campos["retorno"] in _PROCEDIMIENTO else "funcion"
    else:
        tipo = b.tipo
    base = nombre if clase is None else f"{clase}.{nombre}"
    d = F.Diagrama(
        clave=claves.clave(base),
        nombre=nombre,
        tipo=tipo,
        firma=esc.firma(b),
        clase=clase,
        linea=b.linea,
        cuerpo=esc.nodos(b.listas["cuerpo"]),
    )
    return F.Elemento("subrutina", diagrama=d)


def claves_de_diagramas(modelo: ModeloBloques) -> dict[str, str]:
    """Clave de cada diagrama de ``a_flujo`` → id del bloque que lo define."""
    claves = _Claves()
    salida: dict[str, str] = {}
    for b in modelo.programa:
        if b.tipo == "subrutina":
            salida[claves.clave(b.campos["nombre"])] = b.id
        elif b.tipo in ("clase", "interfaz"):
            for m in b.listas["miembros"]:
                if m.tipo == "constructor" or (m.tipo == "metodo" and m.campos["con_cuerpo"]):
                    base = f"{b.campos['nombre']}.{m.campos['nombre']}"
                    salida[claves.clave(base)] = m.id
    return salida


def bloques_desde_codigo(
    codigo: str,
    idioma: str | None = None,
    *,
    ruta: str = "<memoria>",
    cargador: CargadorModulos | None = None,
    ruta_fuente: str | None = None,
) -> ModeloBloques:
    """Bloques de un programa **válido** (``idioma``: el de los bloques; ``None`` lo deduce).

    Lanza ``flujo.ErrorFlujo`` con los diagnósticos oficiales si el programa
    no compila.
    """
    modelo = flujo.modelo_desde_codigo(
        codigo, idioma, ruta=ruta, cargador=cargador, ruta_fuente=ruta_fuente
    )
    return desde_flujo(modelo)


def codigo_desde_bloques(modelo: ModeloBloques, idioma: str | None = None) -> str:
    """Programa InvenioLang de los bloques en ``idioma`` (``None``: el del modelo).

    Lanza ``ErrorBloques`` si al programa le falta algo para poder escribirse
    (un hueco obligatorio vacío, un campo sin valor, una lista sin su mínimo).
    """
    return codigo_con_lineas(modelo, idioma)[0]


def codigo_con_lineas(
    modelo: ModeloBloques, idioma: str | None = None
) -> tuple[str, dict[str, int]]:
    """Código y, para cada bloque de instrucción o definición, su línea en ese código.

    La GUI lo usa para mantener sincronizados bloques, editor y depurador
    tras regenerar el programa: el traductor sólo cambia palabras y el
    formateador sólo la sangría, así que las líneas no se mueven.
    """
    exigir_completo(modelo)
    destino = normalizar_idioma(idioma) if idioma is not None else modelo.idioma
    mf = a_flujo(modelo)
    generado = generar(mf)
    lineas: dict[str, int] = {}
    for k, (_clave, nodo) in enumerate(generado.duenos):
        if nodo is not None:
            lineas.setdefault(nodo, k + 1)
    for b, linea in zip(_definiciones(modelo), generado.inicios, strict=True):
        lineas[b.id] = linea
    return flujo.codigo_desde_modelo(mf, destino), lineas


def _definiciones(modelo: ModeloBloques) -> list[Bloque]:
    """Elementos del programa y miembros de clase, en el orden de ``Generado.inicios``."""
    salida: list[Bloque] = []
    for b in modelo.programa:
        salida.append(b)
        if b.tipo in ("clase", "interfaz"):
            salida.extend(b.listas["miembros"])
    return salida


def traducir_bloques(modelo: ModeloBloques, idioma: str) -> ModeloBloques:
    """Copia de los bloques con todos sus textos en ``idioma`` (no compila nada).

    Pasa por el diagrama de flujo y su traductor por tokens; los ids de las
    instrucciones se conservan.
    """
    exigir_completo(modelo)
    traducido = flujo.traducir_modelo(a_flujo(modelo), idioma)
    nuevo = desde_flujo(traducido)
    if not _misma_forma(modelo.programa, nuevo.programa):
        raise ErrorBloques("BLQ.error.traduccion")
    return nuevo


def _misma_forma(a: list[Bloque], b: list[Bloque]) -> bool:
    return len(a) == len(b) and all(
        x.tipo == y.tipo
        and list(x.listas) == list(y.listas)
        and all(_misma_forma(x.listas[k], y.listas[k]) for k in x.listas)
        for x, y in zip(a, b, strict=True)
    )
