"""Esquema dibujable: símbolos ISO 5807 y layout sin solapes (INV-3003)."""

from __future__ import annotations

import pytest
from comun import CURRICULO, TODO, flujo, modelo_de

from inveniolang.flujo.esquema import ancho_texto


def _cruza(p, q, n, tol=1.0):
    x0, x1 = sorted((p[0], q[0]))
    y0, y1 = sorted((p[1], q[1]))
    return x0 < n.x + n.w - tol and x1 > n.x + tol and y0 < n.y + n.h - tol and y1 > n.y + tol


def _solapan(a, b, tol=0.5):
    return (
        a[0] < b[0] + b[2] - tol
        and b[0] < a[0] + a[2] - tol
        and a[1] < b[1] + b[3] - tol
        and b[1] < a[1] + a[3] - tol
    )


def _problemas(e):
    """Lista de defectos geométricos de un esquema (vacía si está bien)."""
    malos = []
    por_id = {n.id: n for n in e.nodos}
    cajas = [(n.x, n.y, n.w, n.h) for n in e.nodos]
    for i, a in enumerate(e.nodos):
        if a.x < 0 or a.y < 0 or a.x + a.w > e.ancho or a.y + a.h > e.alto:
            malos.append(f"fuera del lienzo: {a.texto}")
        for j in range(i + 1, len(e.nodos)):
            if _solapan(cajas[i], cajas[j]):
                malos.append(f"solape {a.texto!r} / {e.nodos[j].texto!r}")
    for ar in e.aristas:
        if ar.salto:
            assert por_id[ar.desde].simbolo == por_id[ar.hasta].simbolo == "conector"
            assert por_id[ar.desde].marca == por_id[ar.hasta].marca != ""
            continue
        ini, fin = ar.puntos[0], ar.puntos[-1]
        for punto, n in ((ini, por_id[ar.desde]), (fin, por_id[ar.hasta])):
            if not (
                n.x - 1.5 <= punto[0] <= n.x + n.w + 1.5
                and n.y - 1.5 <= punto[1] <= n.y + n.h + 1.5
            ):
                malos.append(f"flecha suelta en {n.texto!r}")
        for p, q in zip(ar.puntos, ar.puntos[1:], strict=False):
            if p[0] != q[0] and p[1] != q[1]:
                malos.append("tramo diagonal")
            for n in e.nodos:
                if n.id not in (ar.desde, ar.hasta) and _cruza(p, q, n):
                    malos.append(f"flecha atraviesa {n.texto!r}")
        if ar.etiqueta and ar.pos_etiqueta:
            x, y, ancla = ar.pos_etiqueta
            w = ancho_texto(ar.etiqueta)
            caja = (x - w if ancla == "end" else x, y - 11, w, 13)
            if any(_solapan(caja, c) for c in cajas):
                malos.append(f"etiqueta {ar.etiqueta!r} sobre un símbolo")
    return malos


@pytest.mark.parametrize("inv", CURRICULO, ids=lambda p: f"{p.parent.parent.name}/{p.stem}")
def test_sin_solapes_en_todo_el_curriculo(inv):
    modelo = modelo_de(inv)
    for e in flujo.esquemas(modelo):
        assert _problemas(e) == [], e.clave


def test_simbolos_iso_por_construccion():
    e = flujo.esquemas(flujo.modelo_desde_codigo(TODO), "main")[0]
    assert _problemas(e) == []
    simbolos = {n.rol: n.simbolo for n in e.nodos}
    assert simbolos["inicio"] == simbolos["fin"] == "terminal"
    assert simbolos["leer"] == simbolos["escribir"] == "datos"
    assert simbolos["llamada"] == "predefinido"
    assert simbolos["proceso"] == simbolos["declaracion"] == "proceso"
    for rol in ("si", "segun", "coincidir", "mientras", "hacer_mientras", "para", "para_cada"):
        assert simbolos[rol] == "decision"
    assert simbolos["romper"] == simbolos["continuar"] == "conector"
    # romper / continuar / caída de caso: pares de conectores con la misma letra.
    saltos = [a for a in e.aristas if a.salto]
    assert len(saltos) >= 4


def test_retorno_sin_fin_inalcanzable():
    m = flujo.modelo_desde_codigo(
        "entero f(entero x) { retornar x; } vacio main() { imprimir(f(1)); }"
    )
    e = flujo.esquemas(m, "f")[0]
    assert [n.rol for n in e.nodos if n.simbolo == "terminal"] == ["inicio", "retornar"]


def test_etiquetas_en_el_idioma_pedido():
    m = flujo.modelo_desde_codigo("vacio main() { si (verdadero) { imprimir(1); } }")
    etiquetas_en = {a.etiqueta for a in flujo.esquemas(m, idioma="en")[0].aristas}
    etiquetas_es = {a.etiqueta for a in flujo.esquemas(m)[0].aristas}
    assert {"Yes", "No"} <= etiquetas_en and {"Sí", "No"} <= etiquetas_es
