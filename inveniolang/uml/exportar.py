"""Exportación del diagrama de clases a PlantUML y a Mermaid ``classDiagram``.

INV-3204: los exportadores anteriores perdían interfaces, enumeraciones,
constructores, genéricos y toda relación que no fuera la herencia (Mermaid
ni siquiera mostraba parámetros ni visibilidad). Ahora escriben el modelo
completo. La salida PlantUML usa exactamente el subconjunto que lee
:mod:`.plantuml`, así que ``leer_plantuml(a_plantuml(m))`` reconstruye el
mismo modelo (lo comprueban las pruebas de ida y vuelta).
"""

from __future__ import annotations

from .modelo import Atributo, Clasificador, Constructor, DiagramaClases, Metodo, Parametro
from .presentacion import literal_codigo, tipo_visible

__all__ = ["a_mermaid", "a_plantuml"]

FLECHAS_PLANTUML = {
    "herencia": "<|--",
    "realizacion": "<|..",
    "composicion": "*--",
    "agregacion": "o--",
    "asociacion": "-->",
    "dependencia": "..>",
}


def _params(params: tuple[Parametro, ...], idioma: str) -> str:
    return ", ".join(f"{p.nombre} : {tipo_visible(p.tipo, idioma)}" for p in params)


def _atributo_puml(a: Atributo, idioma: str) -> str:
    estatico = "{static} " if a.estatico else ""
    inicial = "" if a.valor_inicial is None else " = " + literal_codigo(a.valor_inicial, idioma)
    constante = " {readOnly}" if a.constante else ""
    tipo = tipo_visible(a.tipo, idioma)
    return f"  {a.visibilidad} {estatico}{a.nombre} : {tipo}{inicial}{constante}"


def _constructor_puml(c: Constructor, clase: str, idioma: str) -> str:
    return f"  {c.visibilidad} <<create>> {clase}({_params(c.parametros, idioma)})"


def _metodo_puml(x: Metodo, interfaz: bool, idioma: str) -> str:
    mod = "{static} " if x.estatico else "{abstract} " if x.abstracto and not interfaz else ""
    retorno = tipo_visible(x.retorno, idioma)
    return f"  {x.visibilidad} {mod}{x.nombre}({_params(x.parametros, idioma)}) : {retorno}"


def _cabecera_puml(c: Clasificador) -> str:
    genericos = f"<{', '.join(c.parametros_tipo)}>" if c.parametros_tipo else ""
    palabra = {
        "clase": "class",
        "abstracta": "abstract class",
        "interfaz": "interface",
        "enumeracion": "enum",
    }[c.tipo]
    return f"{palabra} {c.nombre}{genericos} {{"


def a_plantuml(modelo: DiagramaClases, idioma: str | None = None) -> str:
    """Texto PlantUML del diagrama (tipos en ``idioma``; por defecto, el del modelo)."""
    idi = idioma or modelo.idioma
    out = ["@startuml", "skinparam classAttributeIconSize 0"]
    for c in modelo.clasificadores:
        out.append(_cabecera_puml(c))
        for lit in c.literales:
            carga = f"({_params(lit.parametros, idi)})" if lit.parametros else ""
            out.append(f"  {lit.nombre}{carga}")
        out.extend(_atributo_puml(a, idi) for a in c.atributos)
        out.extend(_constructor_puml(k, c.nombre, idi) for k in c.constructores)
        out.extend(_metodo_puml(x, c.tipo == "interfaz", idi) for x in c.metodos)
        out.append("}")
    for r in modelo.relaciones:
        flecha = FLECHAS_PLANTUML[r.tipo]
        if r.tipo in ("herencia", "realizacion"):
            out.append(f"{r.destino} {flecha} {r.origen}")
        elif r.rol is not None:
            out.append(f'{r.origen} {flecha} "{r.multiplicidad}" {r.destino} : {r.rol}')
        else:
            out.append(f"{r.origen} {flecha} {r.destino}")
    out.append("@enduml")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------- Mermaid


def _params_mermaid(params: tuple[Parametro, ...], idioma: str) -> str:
    return ", ".join(f"{tipo_visible(p.tipo, idioma)} {p.nombre}" for p in params)


def a_mermaid(modelo: DiagramaClases, idioma: str | None = None) -> str:
    """Texto Mermaid ``classDiagram`` (estereotipos, firmas, multiplicidades y roles)."""
    idi = idioma or modelo.idioma
    out = ["classDiagram"]
    estereotipos = {"abstracta": "abstract", "interfaz": "interface", "enumeracion": "enumeration"}
    for c in modelo.clasificadores:
        genericos = f"~{','.join(c.parametros_tipo)}~" if c.parametros_tipo else ""
        out.append(f"  class {c.nombre}{genericos} {{")
        if c.tipo in estereotipos:
            out.append(f"    <<{estereotipos[c.tipo]}>>")
        for lit in c.literales:
            carga = f"({_params_mermaid(lit.parametros, idi)})" if lit.parametros else ""
            out.append(f"    {lit.nombre}{carga}")
        for a in c.atributos:
            estatico = "$" if a.estatico else ""
            out.append(f"    {a.visibilidad}{tipo_visible(a.tipo, idi)} {a.nombre}{estatico}")
        for k in c.constructores:
            out.append(f"    {k.visibilidad}{c.nombre}({_params_mermaid(k.parametros, idi)})")
        for x in c.metodos:
            marca = "$" if x.estatico else "*" if x.abstracto else ""
            retorno = tipo_visible(x.retorno, idi)
            params = _params_mermaid(x.parametros, idi)
            out.append(f"    {x.visibilidad}{x.nombre}({params}) {retorno}{marca}")
        out.append("  }")
    for r in modelo.relaciones:
        flecha = FLECHAS_PLANTUML[r.tipo]
        if r.tipo in ("herencia", "realizacion"):
            out.append(f"  {r.destino} {flecha} {r.origen}")
        elif r.rol is not None:
            out.append(f'  {r.origen} {flecha} "{r.multiplicidad}" {r.destino} : {r.rol}')
        else:
            out.append(f"  {r.origen} {flecha} {r.destino}")
    return "\n".join(out) + "\n"
