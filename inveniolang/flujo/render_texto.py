"""Descripción textual accesible de un diagrama de flujo (es/en) (INV-3004).

Pensada para lectores de pantalla y para quien no puede ver el dibujo: cada
símbolo recibe un número en orden de lectura y se dice qué es, en qué línea
del programa está, su texto y a qué número sigue el flujo por cada salida
(«Sí → 4; No → 9»). Los conectores de unión y de salto no se numeran: el
flujo «los atraviesa» hasta el siguiente símbolo con contenido, de modo que
un ``romper`` se lee como «salta a 12».
"""

from __future__ import annotations

from collections import Counter

from .. import i18n
from .esquema import Esquema, NodoEsquema

__all__ = ["describir_esquema", "nombre_rol"]

# Conectores sin contenido propio: el flujo los atraviesa.
_DE_PASO = frozenset({"union", "destino", "caida"})


def nombre_rol(nodo: NodoEsquema, idioma: str) -> str:
    """Nombre del papel del símbolo («Decisión del ciclo mientras»…)."""
    return i18n.t(f"FLU.rol.{nodo.rol or nodo.simbolo}", idioma)


def _sucesores(esquema: Esquema) -> dict[str, list[tuple[str, str]]]:
    salida: dict[str, list[tuple[str, str]]] = {n.id: [] for n in esquema.nodos}
    for a in esquema.aristas:
        salida[a.desde].append((a.etiqueta, a.hasta))
    return salida


def describir_esquema(esquema: Esquema) -> str:
    """Texto accesible completo del diagrama, en el idioma del esquema."""
    idioma = esquema.idioma
    visibles = [n for n in esquema.nodos if n.rol not in _DE_PASO]
    numero = {n.id: k + 1 for k, n in enumerate(visibles)}
    sucesores = _sucesores(esquema)

    def destinos(ident: str, vistos: frozenset[str] = frozenset()) -> list[str]:
        """Números de los símbolos visibles a los que se llega desde ``ident``."""
        if ident in numero:
            return [str(numero[ident])]
        if ident in vistos:
            return []
        resultado: list[str] = []
        for _, siguiente in sucesores[ident]:
            for d in destinos(siguiente, vistos | {ident}):
                if d not in resultado:
                    resultado.append(d)
        return resultado

    cuenta = Counter(n.simbolo for n in visibles)
    resumen = ", ".join(
        i18n.t("FLU.desc.cuenta", idioma, n=c, simbolo=i18n.t(f"FLU.sim.{s}", idioma))
        for s, c in sorted(cuenta.items())
    )
    lineas = [i18n.t("FLU.desc.cabecera", idioma, titulo=esquema.titulo, resumen=resumen)]
    for n in visibles:
        k = numero[n.id]
        donde = i18n.t("FLU.desc.linea", idioma, linea=n.linea) if n.linea and n.origen else ""
        texto = n.texto if n.rol not in ("romper", "continuar", "inicio", "fin") else ""
        rol = n.texto if n.rol in ("inicio", "fin") else nombre_rol(n, idioma)
        partes = [
            i18n.t(
                "FLU.desc.nodo",
                idioma,
                n=k,
                rol=rol,
                donde=donde,
                texto=f": {texto}" if texto else "",
            )
        ]
        salidas = sucesores[n.id]
        if n.rol in ("retornar", "fin"):
            partes.append(i18n.t("FLU.desc.termina", idioma))
        elif n.rol in ("romper", "continuar"):
            objetivo = ", ".join(d for _, h in salidas for d in destinos(h))
            partes.append(i18n.t("FLU.desc.salta", idioma, destino=objetivo or "—"))
        elif len(salidas) == 1 and not salidas[0][0]:
            objetivo = ", ".join(destinos(salidas[0][1]))
            clave = (
                "FLU.desc.vuelve"
                if objetivo and int(objetivo.split(",")[0]) <= k
                else "FLU.desc.sigue"
            )
            partes.append(i18n.t(clave, idioma, destino=objetivo))
        elif salidas:
            ramas = []
            for etiqueta, hasta in salidas:
                objetivo = ", ".join(destinos(hasta)) or i18n.t("FLU.desc.fuera", idioma)
                ramas.append(i18n.t("FLU.desc.rama", idioma, etiqueta=etiqueta, destino=objetivo))
            partes.append(i18n.t("FLU.desc.ramas", idioma, ramas="; ".join(ramas)))
        lineas.append(" ".join(partes))
    return "\n".join(lineas)
