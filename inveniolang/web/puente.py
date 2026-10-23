"""Puente JSON entre el estudio web y el compilador (INV-4200).

El *Web Worker* del estudio (``web/estudio/js/trabajador.js``) importa este
módulo dentro de Pyodide y solo llama a :func:`llamar` con un texto JSON
``{"metodo": "...", "args": {...}}``. La respuesta es siempre JSON:

* ``{"ok": true, "datos": {...}}`` si la operación se pudo hacer (aunque el
  programa del estudiante tenga errores: esos van en ``datos``);
* ``{"ok": false, "error": {"tipo": "...", "mensaje": "..."}}`` si la
  petición misma es inválida (método desconocido, argumento de tipo erróneo).

Por qué un único punto de entrada con JSON y no objetos de Pyodide: los
``PyProxy`` hay que liberarlos a mano y su forma depende de la versión de
Pyodide; el texto JSON no fuga memoria, se prueba igual en CPython
(``tests/web/test_puente.py``) y es el mismo contrato que usa la prueba de
humo con un Pyodide simulado. ``CONTRATO`` se sube si cambia la forma de
alguna respuesta (el estudio comprueba que coincida al arrancar).

Los diagnósticos se devuelven estructurados (código, línea, columna,
mensaje) y con la explicación pedagógica de ``error_explainer`` en el idioma
de la interfaz. Los métodos ``bloques*`` (INV-4224) trabajan sobre el
contrato JSON v1 de ``inveniolang.bloques`` a través de :mod:`.bloques_web`;
si el paquete empaquetado no lo incluye responden ``sin_bloques``.
"""

from __future__ import annotations

import importlib
import json
import re
from collections.abc import Callable, Mapping
from typing import Any

from .. import api, flujo, i18n
from .._version import __version__
from ..error_explainer import explicar
from ..traductor import traducir as _traducir
from ..visualizacion.traza import detectar_idioma
from . import bloques_web

__all__ = ["CONTRATO", "METODOS", "llamar"]

CONTRATO = 1

# Formato oficial de un diagnóstico (§15.8): "[IL-XXX-NNN] archivo:L:C — mensaje".
_DIAGNOSTICO = re.compile(
    r"^\[(?P<codigo>IL-[A-Z]+-\d+)\] (?P<archivo>.*?):(?P<linea>\d+):(?P<columna>\d+) — "
    r"(?P<mensaje>.*)$",
    re.DOTALL,
)

# Límites de lo que acepta el puente: el estudio es para programas de
# estudiante; un texto de varios megabytes solo puede ser un error (o un
# intento de colgar la pestaña) y se rechaza con un mensaje claro.
MAX_CODIGO = 200_000
MAX_ENTRADA = 10_000
MAX_PASOS = 20_000
TEMAS = ("claro", "oscuro")


class PeticionInvalida(ValueError):
    """La petición no cumple el contrato (no es un error del programa)."""


class SinBloques(RuntimeError):
    """El paquete empaquetado no incluye ``inveniolang.bloques`` (copia anterior a la Fase 4)."""


# ------------------------------------------------------------------ argumentos


def _texto(args: Mapping[str, Any], nombre: str, defecto: str | None = None) -> str:
    valor = args.get(nombre, defecto)
    if not isinstance(valor, str):
        raise PeticionInvalida(f"«{nombre}» debe ser texto")
    if len(valor) > MAX_CODIGO:
        raise PeticionInvalida(f"«{nombre}» supera {MAX_CODIGO} caracteres")
    return valor


def _idioma(args: Mapping[str, Any], nombre: str = "idioma") -> str:
    valor = args.get(nombre, "es")
    try:
        return i18n.normalizar_idioma(valor if isinstance(valor, str) else None)
    except ValueError as e:
        raise PeticionInvalida(f"«{nombre}»: {e}") from e


def _tema(args: Mapping[str, Any]) -> str:
    tema = args.get("tema", "claro")
    if tema not in TEMAS:
        raise PeticionInvalida(f"«tema» debe ser uno de {', '.join(TEMAS)}")
    return str(tema)


def _entrada(args: Mapping[str, Any]) -> tuple[str, ...]:
    valor = args.get("entrada", [])
    if not isinstance(valor, list) or not all(isinstance(x, str) for x in valor):
        raise PeticionInvalida("«entrada» debe ser una lista de textos")
    if len(valor) > MAX_ENTRADA:
        raise PeticionInvalida(f"«entrada» supera {MAX_ENTRADA} líneas")
    return tuple(valor)


# ------------------------------------------------------------------ diagnósticos


def diagnostico(texto: str, idioma: str) -> dict[str, Any]:
    """Diagnóstico oficial como dict, con su explicación pedagógica si existe."""
    m = _DIAGNOSTICO.match(texto)
    if m is None:
        # Mensajes que no siguen §15.8 (p. ej. del sandbox): se muestran tal cual.
        return {"codigo": None, "linea": 0, "columna": 0, "mensaje": texto, "explicacion": None}
    exp = explicar(m["codigo"], idioma)
    return {
        "codigo": m["codigo"],
        "linea": int(m["linea"]),
        "columna": int(m["columna"]),
        "mensaje": m["mensaje"],
        "explicacion": (
            None
            if exp is None
            else {
                "titulo": exp.titulo,
                "por_que": exp.por_que,
                "malo": exp.ejemplo_malo,
                "bueno": exp.ejemplo_bueno,
                "arreglo": exp.fix,
                "nivel": exp.nivel,
            }
        ),
    }


def _diagnosticos(textos: tuple[str, ...] | list[str], idioma: str) -> list[dict[str, Any]]:
    return [diagnostico(t, idioma) for t in textos]


# ------------------------------------------------------------------ métodos


def _info(args: Mapping[str, Any]) -> dict[str, Any]:
    return {"version": __version__, "contrato": CONTRATO, "idiomas": list(i18n.IDIOMAS)}


def _ejecutar(args: Mapping[str, Any]) -> dict[str, Any]:
    idioma = _idioma(args)
    r = api.ejecutar(
        _texto(args, "codigo"), ruta="programa.inv", entrada=_entrada(args), idioma=idioma
    )
    return {"ok": r.ok, "salida": "".join(r.salida), "errores": _diagnosticos(r.errores, idioma)}


def _revisar(args: Mapping[str, Any]) -> dict[str, Any]:
    idioma = _idioma(args)
    r = api.compilar(_texto(args, "codigo"), ruta="programa.inv", idioma=idioma)
    return {"ok": r.ok, "errores": _diagnosticos(r.errores, idioma)}


def _traducir_codigo(args: Mapping[str, Any]) -> dict[str, Any]:
    codigo = _texto(args, "codigo")
    destino = _idioma(args, "destino")
    return {"codigo": _traducir(codigo, destino), "origen": detectar_idioma(codigo)}


def _formatear_codigo(args: Mapping[str, Any]) -> dict[str, Any]:
    idioma = _idioma(args)
    r = api.formatear(_texto(args, "codigo"), ruta="programa.inv")
    if not r.ok:
        return {"ok": False, "codigo": None, "errores": _diagnosticos(r.errores, idioma)}
    return {"ok": True, "codigo": r.salida[0], "errores": []}


def _error_flujo(e: flujo.ErrorFlujo, idioma: str) -> dict[str, Any]:
    if e.diagnosticos:
        return {"ok": False, "errores": _diagnosticos(e.diagnosticos, idioma)}
    return {"ok": False, "errores": [diagnostico(e.texto(idioma), idioma)]}


def _flujo(args: Mapping[str, Any]) -> dict[str, Any]:
    """SVG y descripción accesible de un diagrama (o de todos) + la lista de claves."""
    idioma = _idioma(args)
    tema = _tema(args)
    subrutina = args.get("subrutina")
    if subrutina is not None and not isinstance(subrutina, str):
        raise PeticionInvalida("«subrutina» debe ser texto o null")
    try:
        modelo = flujo.modelo_desde_codigo(_texto(args, "codigo"), None, ruta="programa.inv")
        diagramas = [
            {"clave": d.clave, "nombre": d.nombre, "tipo": d.tipo, "firma": d.firma}
            for d in modelo.diagramas()
        ]
        svg = flujo.exportar(modelo, "svg", subrutina, idioma, tema)
        texto = flujo.exportar(modelo, "texto", subrutina, idioma)
    except flujo.ErrorFlujo as e:
        return _error_flujo(e, idioma)
    return {"ok": True, "diagramas": diagramas, "svg": svg, "texto": texto, "errores": []}


def _uml(args: Mapping[str, Any]) -> dict[str, Any]:
    idioma = _idioma(args)
    codigo = _texto(args, "codigo")
    tema = _tema(args)
    salidas: dict[str, str] = {}
    for formato in ("svg", "texto", "plantuml"):
        r = api.uml(codigo, "programa.inv", formato, idioma=idioma, tema=tema)
        if not r.ok:
            return {"ok": False, "errores": _diagnosticos(r.errores, idioma)}
        salidas[formato] = r.salida[0]
    return {"ok": True, "errores": [], **salidas}


def _traza(args: Mapping[str, Any]) -> dict[str, Any]:
    """Reproductor paso a paso (HTML autónomo de la fase 2) para incrustar."""
    idioma = _idioma(args)
    max_pasos = args.get("max_pasos", 5000)
    if not isinstance(max_pasos, int) or isinstance(max_pasos, bool):
        raise PeticionInvalida("«max_pasos» debe ser un entero")
    max_pasos = min(max(max_pasos, 1), MAX_PASOS)
    codigo = _texto(args, "codigo")
    # Los errores de compilación se muestran en el panel de errores con su
    # explicación; el reproductor solo tiene sentido con un programa válido.
    previo = api.compilar(codigo, ruta="programa.inv", idioma=idioma)
    if not previo.ok:
        return {"ok": False, "errores": _diagnosticos(previo.errores, idioma)}
    traza = api.trazar(
        codigo, "programa.inv", entrada=_entrada(args), idioma=idioma, max_pasos=max_pasos
    )
    return {
        "ok": True,
        "errores": [],
        "pasos": len(traza.pasos),
        "truncada": traza.truncada,
        "html": api.traza_html(traza, idioma=idioma),
    }


# ------------------------------------------------------------------ bloques (INV-4224)


def _con_bloques(args: Mapping[str, Any], fn: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    """Ejecuta ``fn(ui)`` traduciendo los errores del contrato de bloques.

    ``ErrorBloques`` (operación imposible, JSON fuera de contrato) es una
    respuesta normal con su motivo en el idioma de la interfaz; un destino
    mal formado es una petición inválida del estudio.
    """
    ui = _idioma(args)
    try:
        bloques = importlib.import_module("inveniolang.bloques")
    except ModuleNotFoundError as e:
        raise SinBloques(str(e)) from e
    try:
        return fn(ui)
    except bloques.ErrorBloques as e:
        return {"ok": False, "motivo": e.texto(ui)}
    except ValueError as e:
        if isinstance(e, flujo.ErrorFlujo):
            raise
        raise PeticionInvalida(f"bloques: {e}") from e


def _modelo(args: Mapping[str, Any]) -> Any:
    dato = args.get("modelo")
    if not isinstance(dato, dict):
        raise PeticionInvalida("«modelo» debe ser un objeto JSON")
    return bloques_web.modelo_de(dato)


def _bloques(args: Mapping[str, Any]) -> dict[str, Any]:
    """Código → bloques (contrato v1 de inveniolang.bloques) con su vista y su paleta."""
    codigo = _texto(args, "codigo")
    idioma = _idioma(args, "idioma_bloques") if args.get("idioma_bloques") else None

    def hacer(ui: str) -> dict[str, Any]:
        try:
            modelo = bloques_web.desde_codigo(codigo, idioma)
        except flujo.ErrorFlujo as e:
            return _error_flujo(e, ui)
        return {
            "ok": True,
            "errores": [],
            **bloques_web.estado(modelo, ui),
            "paleta": bloques_web.paleta(modelo.idioma, ui),
        }

    return _con_bloques(args, hacer)


def _bloques_estado(args: Mapping[str, Any]) -> dict[str, Any]:
    """Vista, problemas y código de un modelo (tras deshacer o rehacer en el estudio)."""
    return _con_bloques(args, lambda ui: {"ok": True, **bloques_web.estado(_modelo(args), ui)})


def _bloques_paleta(args: Mapping[str, Any]) -> dict[str, Any]:
    idioma = _idioma(args, "idioma_bloques")
    return _con_bloques(args, lambda ui: {"ok": True, "paleta": bloques_web.paleta(idioma, ui)})


def _bloques_operar(args: Mapping[str, Any]) -> dict[str, Any]:
    """Una operación de edición; devuelve el estado nuevo o el motivo del rechazo."""
    op = _texto(args, "op")

    def hacer(ui: str) -> dict[str, Any]:
        nuevo = bloques_web.operar(_modelo(args), op, dict(args))
        return {"ok": True, **bloques_web.estado(nuevo, ui)}

    return _con_bloques(args, hacer)


def _bloques_encaje(args: Mapping[str, Any]) -> dict[str, Any]:
    """¿Encaja el origen en el destino? (lo pregunta el lienzo mientras se arrastra)."""
    origen = args.get("origen")
    if not isinstance(origen, dict):
        raise PeticionInvalida("«origen» debe ser un objeto")

    def hacer(ui: str) -> dict[str, Any]:
        motivo = bloques_web.encaje(_modelo(args), origen, args.get("destino"), ui)
        return {"ok": motivo is None, "motivo": motivo}

    return _con_bloques(args, hacer)


def _bloques_destinos(args: Mapping[str, Any]) -> dict[str, Any]:
    """Destinos válidos en orden de lectura (mover o insertar con el teclado)."""
    origen = args.get("origen")
    if not isinstance(origen, dict):
        raise PeticionInvalida("«origen» debe ser un objeto")
    return _con_bloques(
        args,
        lambda ui: {"ok": True, "destinos": bloques_web.destinos(_modelo(args), origen, ui)},
    )


METODOS: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "info": _info,
    "ejecutar": _ejecutar,
    "revisar": _revisar,
    "traducir": _traducir_codigo,
    "formatear": _formatear_codigo,
    "flujo": _flujo,
    "uml": _uml,
    "traza": _traza,
    "bloques": _bloques,
    "bloques_estado": _bloques_estado,
    "bloques_paleta": _bloques_paleta,
    "bloques_operar": _bloques_operar,
    "bloques_encaje": _bloques_encaje,
    "bloques_destinos": _bloques_destinos,
}


def llamar(peticion: str) -> str:
    """Atiende una petición JSON del estudio y devuelve la respuesta JSON.

    Nunca lanza: cualquier fallo se devuelve como ``{"ok": false, ...}`` para
    que el *worker* no quede en un estado roto. Un error inesperado del
    compilador se informa como ``interno`` con su tipo, sin la traza de Python.
    """
    try:
        dato = json.loads(peticion)
        if not isinstance(dato, dict) or not isinstance(dato.get("metodo"), str):
            raise PeticionInvalida('se esperaba {"metodo": texto, "args": objeto}')
        metodo = METODOS.get(dato["metodo"])
        if metodo is None:
            raise PeticionInvalida(f"método desconocido: {dato['metodo']}")
        args = dato.get("args", {})
        if not isinstance(args, dict):
            raise PeticionInvalida("«args» debe ser un objeto")
        respuesta: dict[str, Any] = {"ok": True, "datos": metodo(args)}
    except (PeticionInvalida, json.JSONDecodeError) as e:
        respuesta = {"ok": False, "error": {"tipo": "peticion", "mensaje": str(e)}}
    except SinBloques as e:
        respuesta = {"ok": False, "error": {"tipo": "sin_bloques", "mensaje": str(e)}}
    except RecursionError:
        respuesta = {"ok": False, "error": {"tipo": "recursion", "mensaje": "RecursionError"}}
    except Exception as e:  # noqa: BLE001 - frontera con JavaScript: nunca propagar
        respuesta = {"ok": False, "error": {"tipo": "interno", "mensaje": type(e).__name__}}
    return json.dumps(respuesta, ensure_ascii=False)
