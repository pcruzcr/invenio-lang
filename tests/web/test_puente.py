"""Puente JSON del estudio web (INV-4200, INV-4202, INV-4224)."""

from __future__ import annotations

import importlib.util
import json

import pytest

from inveniolang.core import CompileRequest, compile_pure
from inveniolang.web import CONTRATO, METODOS, llamar
from inveniolang.web.puente import diagnostico

TIENE_BLOQUES = importlib.util.find_spec("inveniolang.bloques") is not None
SIN_BLOQUES = "inveniolang.bloques (equipo BLOQUES) se incorpora al fusionar f4_bloques"


def pedir(metodo, **args):
    respuesta = json.loads(llamar(json.dumps({"metodo": metodo, "args": args})))
    assert respuesta["ok"], respuesta
    return respuesta["datos"]


def test_info_publica_version_y_contrato():
    datos = pedir("info")
    assert datos["contrato"] == CONTRATO
    assert datos["idiomas"] == ["es", "en"]


def test_ejecutar_con_entrada_y_salida():
    r = pedir(
        "ejecutar", codigo="vacio main() { entero x; leer(x); imprimir(x * 2); }", entrada=["21"]
    )
    assert r == {"ok": True, "salida": "42", "errores": []}


def test_error_de_ejecucion_conserva_la_salida_parcial_y_explica_en_el_idioma_pedido():
    codigo = 'vacio main() { imprimir("antes"); entero x = 1 / 0; }'
    r = pedir("ejecutar", codigo=codigo, idioma="en")
    assert r["ok"] is False
    assert r["salida"] == "antes"
    (e,) = r["errores"]
    assert e["codigo"] == "IL-EJE-006" and e["linea"] == 1 and e["columna"] > 1
    assert e["mensaje"] == "Division by zero"
    assert e["explicacion"]["titulo"] == "Integer division by zero"
    assert set(e["explicacion"]) == {"titulo", "por_que", "malo", "bueno", "arreglo", "nivel"}


def test_inv4202_compile_pure_no_descarta_la_salida_previa_a_un_error():
    # Antes de INV-4202 la salida era () al fallar en ejecución.
    r = compile_pure(
        CompileRequest("a.inv", 'vacio main() { imprimir("x"); entero y = 1 / 0; }', modo="run")
    )
    assert r.ok is False and r.salida == ("x",) and r.errores


def test_revisar_devuelve_diagnosticos_estructurados():
    r = pedir("revisar", codigo='vacio main() { entero x = "a"; }')
    assert r["ok"] is False
    assert r["errores"][0]["codigo"] == "IL-TIPO-001"
    assert pedir("revisar", codigo="vacio main() { }") == {"ok": True, "errores": []}


def test_diagnostico_que_no_sigue_el_formato_oficial_se_muestra_tal_cual():
    d = diagnostico("algo raro", "es")
    assert d == {
        "codigo": None,
        "linea": 0,
        "columna": 0,
        "mensaje": "algo raro",
        "explicacion": None,
    }


def test_traducir_y_formatear():
    r = pedir("traducir", codigo="vacio main() { si (verdadero) { imprimir(1); } }", destino="en")
    assert r == {"codigo": "void main() { if (true) { print(1); } }", "origen": "es"}
    f = pedir("formatear", codigo="vacio main() {\nimprimir(1);\n}")
    assert f["codigo"] == "vacio main() {\n    imprimir(1);\n}\n"
    assert pedir("formatear", codigo='vacio main() { "sin cerrar }')["ok"] is False


def test_flujo_svg_texto_y_claves():
    r = pedir(
        "flujo",
        codigo="entero f(entero x) { retornar x; }\nvacio main() { imprimir(f(1)); }",
        idioma="en",
        tema="oscuro",
    )
    assert [d["clave"] for d in r["diagramas"]] == ["f", "main"]
    assert r["svg"].startswith("<svg") and 'role="img"' in r["svg"]
    assert "Flowchart" in r["texto"] or "flowchart" in r["texto"].lower()
    solo = pedir("flujo", codigo="vacio main() { imprimir(1); }", subrutina="main")
    assert solo["ok"]
    malo = pedir("flujo", codigo="vacio main() { x = ; }")
    assert malo["ok"] is False and malo["errores"][0]["codigo"].startswith("IL-")


def test_uml_tres_formatos():
    r = pedir("uml", codigo="clase A { publico entero x; }\nvacio main() { }")
    assert r["ok"] and r["svg"].startswith("<svg") and "@startuml" in r["plantuml"] and r["texto"]
    assert pedir("uml", codigo="clase { }")["ok"] is False


def test_traza_devuelve_el_reproductor_autonomo():
    r = pedir("traza", codigo="vacio main() { entero x = 3; imprimir(x); }", max_pasos=50)
    assert r["ok"] and r["pasos"] >= 2 and not r["truncada"]
    assert r["html"].startswith("<!doctype html>") and 'data-tema="claro"' in r["html"]
    corta = pedir(
        "traza", codigo="vacio main() { entero i = 0; mientras (verdadero) { i++; } }", max_pasos=5
    )
    assert corta["truncada"] is True
    assert pedir("traza", codigo="vacio main() { x }")["ok"] is False


@pytest.mark.parametrize(
    "peticion",
    [
        "no es json",
        json.dumps([1, 2]),
        json.dumps({"metodo": "inventado"}),
        json.dumps({"metodo": "ejecutar", "args": []}),
        json.dumps({"metodo": "ejecutar", "args": {"codigo": 3}}),
        json.dumps({"metodo": "ejecutar", "args": {"codigo": "", "entrada": "x"}}),
        json.dumps({"metodo": "ejecutar", "args": {"codigo": "", "idioma": "fr"}}),
        json.dumps({"metodo": "flujo", "args": {"codigo": "", "tema": "rosa"}}),
        json.dumps({"metodo": "traza", "args": {"codigo": "", "max_pasos": "10"}}),
        json.dumps({"metodo": "ejecutar", "args": {"codigo": "x" * 200_001}}),
    ],
)
def test_peticiones_invalidas_se_rechazan_sin_excepciones(peticion):
    r = json.loads(llamar(peticion))
    assert r["ok"] is False and r["error"]["tipo"] == "peticion"


def test_un_fallo_interno_nunca_cruza_la_frontera(monkeypatch):
    def roto(args):
        raise KeyError("x")

    monkeypatch.setitem(METODOS, "info", roto)
    assert json.loads(llamar('{"metodo": "info"}')) == {
        "ok": False,
        "error": {"tipo": "interno", "mensaje": "KeyError"},
    }


def test_sin_paquete_de_bloques_lo_dice_con_su_propio_motivo(monkeypatch):
    import importlib as imp

    real = imp.import_module

    def falso(nombre, *a, **k):
        if nombre == "inveniolang.bloques":
            raise ModuleNotFoundError(nombre)
        return real(nombre, *a, **k)

    monkeypatch.setattr("inveniolang.web.puente.importlib.import_module", falso)
    r = json.loads(
        llamar(json.dumps({"metodo": "bloques", "args": {"codigo": "vacio main() { }"}}))
    )
    assert r["ok"] is False and r["error"]["tipo"] == "sin_bloques"


# ------------------------------------------------------------------ bloques (contrato de inveniolang.bloques)

PROG = "vacio main() {\n    entero x = 3;\n    si (x > 2) {\n        imprimir(x + 1);\n    }\n}\n"


@pytest.mark.skipif(not TIENE_BLOQUES, reason=SIN_BLOQUES)
def test_bloques_desde_codigo_trae_modelo_vista_paleta_y_codigo():
    r = pedir("bloques", codigo=PROG, idioma="en")
    assert r["ok"] and r["problemas"] == [] and r["codigo"]
    assert r["modelo"]["formato"] == "inveniolang-bloques"
    main = r["vista"][0]
    assert main["forma"] == "definicion" and main["nombre"] == "subroutine"
    assert {p["t"] for p in main["cabecera"]} >= {"texto", "campo", "lista"}
    assert [b["nombre"] for b in main["bocas"]] == ["cuerpo"]
    categorias = {c["id"] for c in r["paleta"]}
    assert {"control", "valores", "variables"} <= categorias
    assert all(c["entradas"] and c["claro"]["relleno"].startswith("#") for c in r["paleta"])
    malo = pedir("bloques", codigo="vacio main() { x = ; }")
    assert malo["ok"] is False and malo["errores"]


@pytest.mark.skipif(not TIENE_BLOQUES, reason=SIN_BLOQUES)
def test_operar_insertar_mover_editar_eliminar_y_rechazo_bilingue():
    m = pedir("bloques", codigo=PROG)["modelo"]
    main = m["programa"][0]["id"]
    ins = pedir(
        "bloques_operar",
        modelo=m,
        op="insertar",
        origen={"paleta": "romper"},
        destino={"padre": main, "parte": "cuerpo", "indice": 0},
        idioma="en",
    )
    assert ins["ok"] is False and "break" in ins["motivo"].lower()
    nuevo = pedir(
        "bloques_operar",
        modelo=m,
        op="insertar",
        origen={"paleta": "imprimir"},
        destino={"padre": main, "parte": "cuerpo", "indice": 2},
    )
    assert nuevo["ok"] and nuevo["codigo"] is None and nuevo["problemas"]  # hueco vacío
    decl = m["programa"][0]["listas"]["cuerpo"][0]
    valor = decl["huecos"]["valor"]["id"]
    ed = pedir("bloques_operar", modelo=m, op="editar", id=valor, campo="valor", valor="7")
    assert "entero x = 7;" in ed["codigo"]
    mv = pedir(
        "bloques_operar",
        modelo=m,
        op="mover",
        id=decl["id"],
        destino={"padre": main, "parte": "cuerpo", "indice": 1},
    )
    assert mv["ok"] and mv["problemas"]  # x se usa antes de declararse
    el = pedir("bloques_operar", modelo=m, op="eliminar", id=decl["id"])
    assert el["ok"] and el["problemas"]
    dup = pedir("bloques_operar", modelo=m, op="duplicar", id=decl["id"])
    assert dup["ok"]
    env = pedir("bloques_operar", modelo=m, op="envolver", ids=[decl["id"]], tipo="mientras")
    assert env["ok"]
    assert (
        json.loads(
            llamar(json.dumps({"metodo": "bloques_operar", "args": {"modelo": m, "op": "volar"}}))
        )["error"]["tipo"]
        == "peticion"
    )


@pytest.mark.skipif(not TIENE_BLOQUES, reason=SIN_BLOQUES)
def test_encaje_y_destinos_en_orden_de_lectura():
    m = pedir("bloques", codigo=PROG)["modelo"]
    rama = m["programa"][0]["listas"]["cuerpo"][1]["listas"]["ramas"][0]["id"]
    no = pedir(
        "bloques_encaje",
        modelo=m,
        origen={"paleta": "numero"},
        destino={"padre": rama, "parte": "condicion"},
        idioma="es",
    )
    assert no["ok"] is False and "lógico" in no["motivo"]
    destinos = pedir("bloques_destinos", modelo=m, origen={"paleta": "mientras"})["destinos"]
    assert destinos and all({"padre", "parte", "indice", "lugar"} <= set(d) for d in destinos)
    assert all(d["parte"] in ("cuerpo", "programa") for d in destinos)
    decl = m["programa"][0]["listas"]["cuerpo"][0]["id"]
    moverse = pedir("bloques_destinos", modelo=m, origen={"id": decl})["destinos"]
    actual = {"padre": m["programa"][0]["id"], "parte": "cuerpo", "indice": 0}
    assert not any(
        {k: d[k] for k in actual} == actual for d in moverse
    ), "su sitio actual no es un destino"
    # Cada destino que se ofrece se puede usar de verdad.
    for d in moverse:
        r = pedir(
            "bloques_operar",
            modelo=m,
            op="mover",
            id=decl,
            destino={k: d[k] for k in ("padre", "parte", "indice")},
        )
        assert r["ok"], d


@pytest.mark.skipif(not TIENE_BLOQUES, reason=SIN_BLOQUES)
def test_estado_y_paleta_en_otro_idioma_de_interfaz():
    m = pedir("bloques", codigo=PROG)["modelo"]
    es = pedir("bloques_estado", modelo=m, idioma="es")
    en = pedir("bloques_estado", modelo=m, idioma="en")
    assert es["codigo"] == en["codigo"] and es["vista"][0]["nombre"] != en["vista"][0]["nombre"]
    p = pedir("bloques_paleta", idioma_bloques="en", idioma="es")
    assert any(e["muestra"].startswith("print") for c in p["paleta"] for e in c["entradas"])
    roto = pedir("bloques_estado", modelo={"formato": "otro"})
    assert roto["ok"] is False and roto["motivo"]
