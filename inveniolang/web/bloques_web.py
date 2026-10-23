"""Bloques para el estudio web: vista dibujable, operaciones y destinos (INV-4224).

El estudio web consume el contrato JSON v1 de ``inveniolang.bloques`` (equipo
BLOQUES, ``docs/bloques.md``). Para no reimplementar en JavaScript las
plantillas, las banderas que ocultan bocas, los rótulos accesibles ni las
reglas de encaje tipado, Python entrega al navegador:

* una **vista**: el árbol de bloques ya resuelto en piezas dibujables
  (texto, campo editable con sus opciones, hueco con su hijo o vacío, lista
  en línea, bocas con su rótulo), con los textos del código en el idioma de
  los bloques y los nombres accesibles en el idioma de la interfaz;
* las **operaciones** puras de ``bloques.edicion`` (insertar, mover,
  eliminar, duplicar, envolver, editar) seguidas de ``validar``, y el código
  generado cuando el programa no tiene problemas;
* el **encaje** de un bloque en un sitio (mientras se arrastra) y la lista de
  **destinos** válidos en orden de lectura para mover o insertar con el
  teclado: las mismas zonas que ``bloques.diseno`` da al lienzo Qt.

``inveniolang.bloques`` se importa al usarse (``importlib``): así este módulo
se analiza y se empaqueta aunque el paquete aún no exista en una copia vieja,
y el puente lo explica como «sin_bloques» en vez de fallar al importar.
"""

from __future__ import annotations

import copy
import importlib
import json
from typing import Any

from .. import i18n


def _b() -> Any:
    """El paquete ``inveniolang.bloques`` (``ModuleNotFoundError`` si falta)."""
    return importlib.import_module("inveniolang.bloques")


def _m(nombre: str) -> Any:
    return importlib.import_module(f"inveniolang.bloques.{nombre}")


# ------------------------------------------------------------------ vista


def _plano(piezas: Any) -> list[Any]:
    """El lienzo muestra siempre los tramos opcionales (sus huecos se pueden rellenar)."""
    salida: list[Any] = []
    for p in piezas:
        if p.clase == "opcional":
            salida.extend(_plano(p.hijas))
        else:
            salida.append(p)
    return salida


def _texto_opcion(bloque: Any, campo: str, valor: Any, idioma: str) -> str:
    otro = copy.copy(bloque)
    otro.campos = {**bloque.campos, campo: valor}
    return str(_m("texto").texto_campo(otro, campo, idioma)) or str(valor)


def _campo(bloque: Any, desc: Any, idioma: str, ui: str) -> dict[str, Any]:
    texto = _m("texto")
    valor = bloque.campos[desc.nombre]
    dato: dict[str, Any] = {
        "t": "campo",
        "nombre": desc.nombre,
        "clase": desc.clase,
        "valor": valor,
        "texto": texto.texto_campo(bloque, desc.nombre, idioma),
        "etiqueta": i18n.t(f"BLQ.parte.{desc.nombre}", ui),
    }
    if desc.clase == "opcion":
        dato["opciones"] = [
            {"valor": o, "texto": _texto_opcion(bloque, desc.nombre, o, idioma)}
            for o in desc.opciones
        ]
    return dato


def _vista(bloque: Any, idioma: str, ui: str, rama_otra: bool = False) -> dict[str, Any]:
    B = _b()  # noqa: N806 - alias corto del paquete
    texto = _m("texto")
    desc = B.TIPOS[bloque.tipo]
    cabecera: list[dict[str, Any]] = []
    for p in _plano(texto.piezas(bloque.tipo, idioma, rama_otra)):
        if p.clase == "texto":
            if p.valor.strip():
                cabecera.append({"t": "texto", "texto": p.valor.strip()})
            continue
        nombre = p.valor
        etiqueta = i18n.t(f"BLQ.parte.{nombre}", ui)
        if nombre in bloque.campos:
            cabecera.append(_campo(bloque, desc.campo(nombre), idioma, ui))
        elif nombre in bloque.huecos:
            hijo = bloque.huecos[nombre]
            cabecera.append(
                {
                    "t": "hueco",
                    "nombre": nombre,
                    "etiqueta": etiqueta,
                    "acepta": desc.hueco(nombre).acepta,
                    "hijo": None if hijo is None else _vista(hijo, idioma, ui),
                }
            )
        else:
            cabecera.append(
                {
                    "t": "lista",
                    "nombre": nombre,
                    "etiqueta": etiqueta,
                    "hijos": [_vista(h, idioma, ui) for h in bloque.listas[nombre]],
                }
            )
    bocas = [
        {
            "nombre": lista,
            "rotulo": texto.rotulo_boca(bloque, lista, idioma),
            "etiqueta": i18n.t(f"BLQ.parte.{lista}", ui),
            "hijos": [
                _vista(h, idioma, ui, bloque.tipo == "si" and k > 0)
                for k, h in enumerate(bloque.listas[lista])
            ],
        }
        for lista in texto.bocas(bloque, idioma)
    ]
    return {
        "id": bloque.id,
        "tipo": bloque.tipo,
        "nombre": i18n.t(f"BLQ.tipo.{bloque.tipo}", ui),
        "categoria": desc.categoria,
        "forma": desc.forma,
        "salida": desc.salida,
        "linea": bloque.linea,
        "rotulo": texto.rotulo(bloque, idioma, rama_otra),
        "cabecera": cabecera,
        "bocas": bocas,
    }


def vista(modelo: Any, ui: str) -> list[dict[str, Any]]:
    """El programa como árbol dibujable (ver docstring del módulo)."""
    return [_vista(b, modelo.idioma, ui) for b in modelo.programa]


def paleta(idioma: str, ui: str) -> list[dict[str, Any]]:
    """Categorías (nombre, icono, colores por tema) con sus entradas de la paleta."""
    B = _b()  # noqa: N806
    catalogo = B.catalogo_dict(ui)
    texto = _m("texto")
    salida = []
    for clave, cat in catalogo["categorias"].items():
        entradas = []
        for e in catalogo["paleta"]:
            if e["categoria"] != clave:
                continue
            muestra = B.desde_paleta(e["clave"], idioma)
            entradas.append(
                {
                    "clave": e["clave"],
                    "nombre": e["nombre"],
                    "forma": B.TIPOS[e["tipo"]].forma,
                    "muestra": texto.rotulo(muestra, idioma) or e["nombre"],
                }
            )
        salida.append({"id": clave, **cat, "entradas": entradas})
    return salida


# ------------------------------------------------------------------ estado


def modelo_de(dato: Any) -> Any:
    """``ModeloBloques`` desde su ``dict`` (``ErrorBloques`` si no cumple el contrato)."""
    return _b().como_modelo(dato)


def estado(modelo: Any, ui: str) -> dict[str, Any]:
    """Modelo, vista, problemas (con el bloque culpable) y código si no hay problemas."""
    B = _b()  # noqa: N806
    problemas = B.validar(modelo)
    codigo = None if problemas else B.codigo_desde_bloques(modelo)
    return {
        "modelo": json.loads(B.a_json(modelo, None)),
        "vista": vista(modelo, ui),
        "problemas": [{"bloque": p.bloque, "mensaje": p.texto(ui)} for p in problemas],
        "codigo": codigo,
    }


def desde_codigo(codigo: str, idioma: str | None) -> Any:
    """Bloques de un código válido (``flujo.ErrorFlujo`` con diagnósticos si no compila)."""
    return _b().bloques_desde_codigo(codigo, idioma, ruta="programa.inv")


# ------------------------------------------------------------------ operaciones


def _destino(dato: Any) -> Any:
    if not isinstance(dato, dict) or not isinstance(dato.get("parte"), str):
        raise ValueError("destino")
    padre = dato.get("padre")
    indice = dato.get("indice")
    if padre is not None and not isinstance(padre, str):
        raise ValueError("destino.padre")
    if indice is not None and (not isinstance(indice, int) or isinstance(indice, bool)):
        raise ValueError("destino.indice")
    return _b().Destino(padre, dato["parte"], indice)


def _origen(modelo: Any, dato: Any) -> Any:
    """Bloque que se suelta: uno del modelo (``{"id"}``) o uno nuevo de la paleta."""
    B = _b()  # noqa: N806
    if isinstance(dato, dict) and isinstance(dato.get("id"), str):
        return modelo.buscar(dato["id"])
    if isinstance(dato, dict) and isinstance(dato.get("paleta"), str):
        return B.desde_paleta(dato["paleta"], modelo.idioma)
    raise ValueError("origen")


def operar(modelo: Any, op: str, args: dict[str, Any]) -> Any:
    """Aplica una operación de ``bloques.edicion`` y devuelve el modelo nuevo."""
    B = _b()  # noqa: N806
    if op == "insertar":
        return B.insertar(
            modelo, _origen(modelo, args.get("origen")), _destino(args.get("destino"))
        )
    if op == "mover":
        return B.mover(modelo, str(args.get("id")), _destino(args.get("destino")))
    if op == "eliminar":
        return B.eliminar(modelo, str(args.get("id")))
    if op == "duplicar":
        return B.duplicar(modelo, str(args.get("id")))
    if op == "envolver":
        ids = args.get("ids")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError("ids")
        return B.envolver(modelo, ids, str(args.get("tipo")))
    if op == "editar":
        valor = args.get("valor")
        if not isinstance(valor, (str, bool)):
            raise ValueError("valor")
        return B.editar(modelo, str(args.get("id")), str(args.get("campo")), valor)
    raise ValueError(f"operación desconocida: {op}")


# ------------------------------------------------------------------ encaje y destinos


def _contiene(bloque: Any, ident: str | None) -> bool:
    return ident is not None and any(b.id == ident for b in _b().recorrer([bloque]))


def _tiene_saltos(bloque: Any) -> bool:
    return any(b.tipo in ("romper", "continuar") for b in _b().recorrer([bloque]))


def encaje(modelo: Any, origen: dict[str, Any], destino: Any, ui: str) -> str | None:
    """Motivo (en ``ui``) por el que el bloque no se puede soltar en ``destino``; None si encaja."""
    B = _b()  # noqa: N806
    try:
        if "id" in origen:
            B.mover(modelo, origen["id"], _destino(destino))
        else:
            B.insertar(modelo, _origen(modelo, origen), _destino(destino))
    except B.ErrorBloques as e:
        return str(e.texto(ui))
    return None


def lugar(modelo: Any, padre: str | None, parte: str, indice: int | None, ui: str) -> str:
    """Descripción hablada de un sitio («En cuerpo de mientras, 2 de 3.»)."""
    if padre is None:
        return i18n.t(
            "BLQ.anuncio.lugar_programa",
            ui,
            posicion=(indice or 0) + 1,
            total=len(modelo.programa) + 1,
        )
    p = modelo.buscar(padre)
    nombre_padre = i18n.t(f"BLQ.tipo.{p.tipo}", ui)
    if indice is None:
        return i18n.t(
            "BLQ.anuncio.lugar_hueco",
            ui,
            hueco=i18n.t(f"BLQ.parte.{parte}", ui),
            padre=nombre_padre,
        )
    return i18n.t(
        "BLQ.anuncio.lugar_lista",
        ui,
        lista=i18n.t(f"BLQ.parte.{parte}", ui),
        padre=nombre_padre,
        posicion=indice + 1,
        total=len(p.listas[parte]) + 1,
    )


def destinos(modelo: Any, origen: dict[str, Any], ui: str) -> list[dict[str, Any]]:
    """Sitios válidos para ``origen`` en orden de lectura (zonas de ``bloques.diseno``).

    Para mover, los índices se devuelven ya «sin el bloque» (convención de
    ``edicion.mover``) y se omite el sitio que ocupa ahora. La comprobación
    rápida es ``reglas.motivo_rechazo``; solo si el bloque lleva ``romper`` o
    ``continuar`` se ensaya la operación completa (es la que vigila dónde
    quedan los saltos).
    """
    B = _b()  # noqa: N806
    reglas = _m("reglas")
    zonas = _m("diseno").disenar(modelo).zonas
    bloque = _origen(modelo, origen)
    moviendo = "id" in origen
    base = modelo
    actual = None
    if moviendo:
        padre_actual, ranura = B.donde_esta(modelo, bloque.id)
        actual = (None if padre_actual is None else padre_actual.id, ranura.nombre, ranura.indice)
        base = B.eliminar(modelo, bloque.id)
    ctx = reglas.Contexto(base)
    ensayar = _tiene_saltos(bloque)
    salida = []
    vistos = set()
    for z in zonas:
        if moviendo and (_contiene(bloque, z.padre) or z.padre == bloque.id):
            continue
        indice = z.indice
        if (
            moviendo
            and actual is not None
            and z.clase == "lista"
            and (z.padre, z.parte) == actual[:2]
        ):
            assert actual[2] is not None
            if indice in (actual[2], actual[2] + 1):
                continue  # es donde ya está
            if indice is not None and indice > actual[2]:
                indice -= 1
        if (
            moviendo
            and actual is not None
            and z.clase == "hueco"
            and (z.padre, z.parte) == actual[:2]
        ):
            continue
        clave = (z.padre, z.parte, indice)
        if clave in vistos:
            continue
        vistos.add(clave)
        padre = None if z.padre is None else base.buscar(z.padre)
        ranura = reglas.Ranura(z.clase, z.parte, indice)
        if reglas.motivo_rechazo(ctx, bloque, padre, ranura) is not None:
            continue
        destino = {"padre": z.padre, "parte": z.parte, "indice": indice}
        ocupado = padre is not None and z.clase == "hueco" and padre.huecos[z.parte] is not None
        if (ensayar or ocupado) and encaje(modelo, origen, destino, ui) is not None:
            continue
        salida.append({**destino, "lugar": lugar(base, z.padre, z.parte, indice, ui)})
    return salida
