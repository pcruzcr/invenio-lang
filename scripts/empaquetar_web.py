"""Empaqueta InvenioLang para el estudio web (INV-4201).

Genera en ``web/estudio/generado/`` (o en ``--destino``) todo lo que el
estudio carga en el navegador y que NO se escribe a mano:

* ``inveniolang.zip`` — el paquete Python ``inveniolang`` (sin los módulos que
  necesitan Qt, Tk, procesos o stdio del sistema, ver ``EXCLUIDOS``) más
  ``ply`` (lex/yacc, licencia BSD en la cabecera de cada archivo). Pyodide lo
  descomprime y lo importa: no hace falta ``micropip`` ni red para el
  compilador, solo para el propio Pyodide.
* ``textos.json`` — los textos de la interfaz (claves ``WEB.*``) en es y en,
  sacados del catálogo ``inveniolang/i18n``: una sola fuente de verdad para
  la GUI Qt, la CLI y la web.
* ``lexico.json`` — palabras clave y funciones integradas de cada idioma, del
  lexer real, para el resaltado del editor (que debe funcionar al instante,
  antes de que Pyodide cargue).
* ``curriculo.es.json`` / ``curriculo.en.json`` — niveles y ejercicios
  (enunciado, objetivos, pistas, conceptos, solución, entrada y salida
  esperada) de ``curriculum/es`` y ``curriculum/en``.
* ``manifiesto.json`` — versión, contrato del puente y SHA-256 de cada
  archivo (el estudio lo usa para invalidar la caché del navegador).

Determinista: mismas fuentes → mismos bytes (entradas del zip ordenadas, con
fecha fija y permisos fijos; JSON con claves ordenadas). Así el resultado se
puede comparar con ``--comprobar`` en CI y la caché del navegador solo se
invalida cuando algo cambia de verdad.

Uso::

    python scripts/empaquetar_web.py                 # escribe web/estudio/generado/
    python scripts/empaquetar_web.py --destino DIR   # otro directorio
    python scripts/empaquetar_web.py --comprobar     # 1 si lo generado está desactualizado
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DESTINO = RAIZ / "web" / "estudio" / "generado"
PAQUETE = RAIZ / "inveniolang"
CURRICULO = RAIZ / "curriculum"

# Módulos que no se empaquetan, con su porqué. Ninguno lo usa el puente web
# (lo comprueba tests/web/test_empaquetar_web.py importando el zip con
# PySide6 y tkinter bloqueados).
EXCLUIDOS: dict[str, str] = {
    "gui_qt.py": "GUI de escritorio: necesita PySide6 (Qt), que no existe en el navegador",
    "gui_tk.py": "GUI de respaldo: necesita tkinter, que no existe en el navegador",
    "gui": "paneles de la GUI Qt: necesitan PySide6",
    "lsp.py": "servidor LSP sobre stdio para editores de escritorio",
    "sandbox.py": "aislamiento con subprocesos y límites del SO; Pyodide no crea procesos",
    "cli.py": "interfaz de línea de órdenes; el estudio usa la API vía el puente",
    "parsetab.py": "tablas de PLY generadas localmente; se regeneran en el navegador",
    "parser.out": "informe de depuración de PLY",
}
EXTENSIONES = (".py", ".inv")
PLY = ("__init__.py", "lex.py", "yacc.py")
FECHA_ZIP = (1980, 1, 1, 0, 0, 0)  # la mínima de ZIP: ningún dato del momento de empaquetar


def _excluido(relativa: Path) -> bool:
    return relativa.parts[0] in EXCLUIDOS or "__pycache__" in relativa.parts


def archivos_paquete() -> list[tuple[str, Path]]:
    """(ruta dentro del zip, ruta en disco) del paquete y de ply, ordenados."""
    lista: list[tuple[str, Path]] = []
    for ruta in PAQUETE.rglob("*"):
        rel = ruta.relative_to(PAQUETE)
        if ruta.is_file() and ruta.suffix in EXTENSIONES and not _excluido(rel):
            lista.append((f"inveniolang/{rel.as_posix()}", ruta))
    import ply

    base = Path(ply.__file__).resolve().parent
    lista += [(f"ply/{nombre}", base / nombre) for nombre in PLY]
    return sorted(lista)


def zip_paquete() -> bytes:
    """Zip determinista del paquete (orden, fecha y permisos fijos)."""
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as z:
        for nombre, ruta in archivos_paquete():
            info = zipfile.ZipInfo(nombre, FECHA_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3  # Unix: el mismo zip en Windows y en Linux
            # Fin de línea normalizado: algunos fuentes son CRLF y el zip no
            # debe depender de cómo los extrajo git en cada máquina.
            datos = ruta.read_bytes().replace(b"\r\n", b"\n")
            z.writestr(info, datos, compresslevel=9)
    return memoria.getvalue()


def textos_interfaz() -> dict[str, dict[str, str]]:
    """Claves ``WEB.*`` del catálogo, por idioma (sin el prefijo)."""
    from inveniolang import i18n

    salida: dict[str, dict[str, str]] = {}
    for idioma in i18n.IDIOMAS:
        mensajes = i18n.REGISTRO.obtener(idioma).mensajes
        salida[idioma] = {k[4:]: v for k, v in sorted(mensajes.items()) if k.startswith("WEB.")}
    return salida


def lexico() -> dict[str, Any]:
    """Palabras clave (lexema → categoría) e integradas de cada idioma, del lexer real."""
    from inveniolang.builtins import PARES_BUILT_IN, PARES_ORDEN_SUPERIOR
    from inveniolang.lexer import Lexer
    from inveniolang.traductor import PALABRAS_CLAVE

    tipos = {"KW_INT", "KW_FLOAT", "KW_STRING", "KW_BOOL", "KW_VOID"}
    literales = {"KW_TRUE", "KW_FALSE", "KW_NULL"}

    def categoria(token: str) -> str:
        if token in tipos:
            return "tipo"
        if token in literales:
            return "literal"
        return "clave"

    palabras = {lexema: categoria(token) for lexema, token in Lexer.keywords.items()}
    pares = (*PARES_BUILT_IN.values(), *PARES_ORDEN_SUPERIOR.values())
    integradas = sorted({nombre for par in pares for nombre in par})
    # Pares (es, en) que distinguen el idioma de un programa (main o
    # constructor se escriben igual en los dos y no cuentan).
    distintos = sorted({par for par in PALABRAS_CLAVE.values() if par[0] != par[1]})
    return {
        "palabras": dict(sorted(palabras.items())),
        "integradas": integradas,
        "pares": [list(par) for par in distintos],
    }


def _leer_json(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _texto_opcional(ruta: Path) -> str | None:
    return ruta.read_text(encoding="utf-8").replace("\r\n", "\n") if ruta.exists() else None


def curriculo(idioma: str) -> dict[str, Any]:
    """Niveles y ejercicios de ``curriculum/<idioma>`` en orden."""
    carpeta = CURRICULO / idioma
    niveles = []
    for dir_nivel in sorted(p for p in carpeta.iterdir() if p.is_dir()):
        meta = _leer_json(dir_nivel / "nivel.json")
        ejercicios = []
        for inv in sorted(dir_nivel.glob("*.inv")):
            datos = _leer_json(inv.with_suffix(".json"))
            entrada = _texto_opcional(inv.with_suffix(".entrada"))
            ejercicios.append(
                {
                    "id": datos["id"],
                    "numero": datos["numero"],
                    "archivo": f"{dir_nivel.name}/{inv.name}",
                    "titulo": datos["titulo"],
                    "enunciado": datos["enunciado"],
                    "objetivos": datos["objetivos"],
                    "pistas": datos["pistas"],
                    "conceptos": datos["conceptos"],
                    "solucion": _texto_opcional(inv),
                    "esperado": _texto_opcional(inv.with_suffix(".expected")) or "",
                    "entrada": [] if entrada is None else entrada.splitlines(),
                }
            )
        niveles.append(
            {
                "nivel": meta["nivel"],
                "titulo": meta["titulo"],
                "descripcion": meta["descripcion"],
                "temas": meta["temas"],
                "ejercicios": ejercicios,
            }
        )
    return {"idioma": idioma, "niveles": niveles}


def _json(dato: Any) -> bytes:
    return (json.dumps(dato, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode("utf-8")


def generar() -> dict[str, bytes]:
    """Nombre de archivo → contenido de todo lo generado (sin escribir nada)."""
    from inveniolang._version import __version__
    from inveniolang.web import CONTRATO

    archivos = {
        "inveniolang.zip": zip_paquete(),
        "textos.json": _json(textos_interfaz()),
        "lexico.json": _json(lexico()),
        "curriculo.es.json": _json(curriculo("es")),
        "curriculo.en.json": _json(curriculo("en")),
    }
    manifiesto = {
        "version": __version__,
        "contrato": CONTRATO,
        "archivos": {n: hashlib.sha256(d).hexdigest() for n, d in sorted(archivos.items())},
    }
    archivos["manifiesto.json"] = _json(manifiesto)
    return archivos


def diferencias(destino: Path, archivos: dict[str, bytes]) -> list[str]:
    """Archivos que faltan o difieren en ``destino``."""
    return [
        nombre
        for nombre, datos in sorted(archivos.items())
        if not (destino / nombre).is_file() or (destino / nombre).read_bytes() != datos
    ]


def escribir(destino: Path, archivos: dict[str, bytes]) -> None:
    """Escribe los archivos en ``destino`` (lo crea si no existe)."""
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, datos in archivos.items():
        (destino / nombre).write_bytes(datos)


def _partes(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Empaqueta InvenioLang para el estudio web.")
    p.add_argument("--destino", type=Path, default=DESTINO, help="directorio de salida")
    p.add_argument(
        "--comprobar",
        action="store_true",
        help="no escribe: termina con 1 si lo generado falta o está desactualizado",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada; 0 si todo fue bien."""
    args = _partes(argv)
    archivos = generar()
    if args.comprobar:
        cambios = diferencias(args.destino, archivos)
        for nombre in cambios:
            print(f"desactualizado: {nombre}")
        return 1 if cambios else 0
    escribir(args.destino, archivos)
    for nombre, datos in sorted(archivos.items()):
        print(f"{len(datos):>9} B  {args.destino / nombre}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
