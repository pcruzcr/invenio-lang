# visual/uml.py — v10 UML + patrones + diagrama de flujo all-in-one
from __future__ import annotations
from typing import List


def to_plantuml(clases) -> str:
    out = ["@startuml", "skinparam classAttributeIconSize 0"]
    for c in clases:
        her = f" extends {c.padre}" if c.padre else ""
        out.append(f"class {c.nombre}{her} {{")
        for a in c.atributos:
            vis = "+" if a.visibilidad == "publico" else "-"
            static = " {static}" if a.es_estatico else ""
            out.append(f"  {vis} {a.nombre}: {a.tipo}{static}")
        for m in c.metodos:
            vis = "+" if m.visibilidad == "publico" else "-"
            static = " {static}" if m.es_estatico else ""
            abstract = " {abstract}" if m.es_abstracto else ""
            params = ", ".join(f"{p.nombre}: {p.tipo}" for p in m.parametros)
            out.append(f"  {vis} {m.nombre}({params}): {m.tipo_retorno}{static}{abstract}")
        out.append("}")
        if c.padre:
            out.append(f"{c.padre} <|-- {c.nombre}")
        for iface in c.interfaces:
            out.append(f"{iface} <|.. {c.nombre} : implements")
    out.append("@enduml")
    return "\n".join(out)


def to_mermaid(clases) -> str:
    out = ["classDiagram"]
    for c in clases:
        out.append(f"class {c.nombre} {{")
        for a in c.atributos:
            out.append(f"  {a.tipo} {a.nombre}")
        for m in c.metodos:
            out.append(f"  {m.tipo_retorno} {m.nombre}()")
        out.append("}")
        if c.padre:
            out.append(f"{c.padre} <|-- {c.nombre}")
    return "\n".join(out)


def patrones_detectados(clases) -> List[str]:
    pats = []
    for c in clases:
        if any(m.es_abstracto for m in c.metodos):
            pats.append(f"{c.nombre}: Template/Strategy (método abstracto)")
        if any(a.es_estatico for a in c.atributos):
            pats.append(f"{c.nombre}: Singleton (estático)")
        if len(c.metodos) > 3:
            pats.append(f"{c.nombre}: Observer candidate (muchos métodos)")
    return pats
