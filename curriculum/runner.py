"""Ejecutor del currículo bilingüe de InvenioLang.

INV-1201: el ejecutor anterior solo conocía `nivelN/` en español, comparaba
la salida con `strip()` (aceptaba "1373031" para siete números pegados),
no mostraba enunciados ni pistas, terminaba siempre con código 0 aunque
fallara y se bloqueaba esperando teclado si un ejercicio usaba `leer`.
Este módulo recorre las dos versiones de cada ejercicio
(`es/nivelNN/` con palabras clave en español y `en/levelNN/` con palabras
clave en inglés), compara la salida EXACTA contra `.expected`, comprueba que
ambas versiones produzcan lo mismo, muestra enunciado y pistas graduadas en
el idioma elegido y devuelve un código de salida distinto de 0 si algo falla.

Uso:
    python curriculum/runner.py                 # todo, ambas versiones
    python curriculum/runner.py 3 nivel4        # solo los niveles 3 y 4
    python curriculum/runner.py --idioma en     # mensajes y pistas en inglés
    python curriculum/runner.py --version es    # solo la versión en español
    python curriculum/runner.py --ejercicio N04-E05 --enunciado --pistas 3

Estructura de cada ejercicio (misma base de nombre, distinta extensión):
    NN_nombre.inv       solución de referencia comentada
    NN_nombre.expected  salida exacta esperada
    NN_nombre.json      metadatos: id, titulo, enunciado, objetivos,
                        pistas (graduadas), conceptos
    NN_nombre.entrada   (opcional) una línea por cada `leer`
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))

from inveniolang import api  # noqa: E402

IDIOMAS = ("es", "en")
# Prefijo de las carpetas de nivel en cada idioma: es/nivel03, en/level03.
PREFIJO_NIVEL = {"es": "nivel", "en": "level"}
CLAVES_METADATOS = ("id", "titulo", "enunciado", "objetivos", "pistas", "conceptos")

MENSAJES = {
    "es": {
        "ok": "OK",
        "fallo": "FALLO",
        "nivel": "Nivel",
        "enunciado": "Enunciado",
        "objetivos": "Objetivos",
        "pista": "Pista",
        "esperado": "esperado",
        "obtenido": "obtenido",
        "linea": "primera diferencia en la línea",
        "errores": "errores de compilación/ejecución",
        "distintas": "las versiones es y en producen salidas distintas",
        "sin_pareja": "falta la versión en otro idioma",
        "falta": "falta el archivo",
        "meta_invalida": "metadatos inválidos",
        "sin_ejercicios": "No se encontró ningún ejercicio con esos filtros.",
        "nivel_invalido": "Nivel no reconocido",
        "resumen": "Resumen",
        "correctos": "correctos",
        "problemas": "problemas de estructura",
    },
    "en": {
        "ok": "OK",
        "fallo": "FAIL",
        "nivel": "Level",
        "enunciado": "Statement",
        "objetivos": "Learning goals",
        "pista": "Hint",
        "esperado": "expected",
        "obtenido": "got",
        "linea": "first difference at line",
        "errores": "compile/run errors",
        "distintas": "the es and en versions produce different output",
        "sin_pareja": "missing version in the other language",
        "falta": "missing file",
        "meta_invalida": "invalid metadata",
        "sin_ejercicios": "No exercise matches those filters.",
        "nivel_invalido": "Unknown level",
        "resumen": "Summary",
        "correctos": "passed",
        "problemas": "structure problems",
    },
}


@dataclass(frozen=True)
class Ejercicio:
    """Una versión (es o en) de un ejercicio del currículo."""

    id: str
    nivel: int
    numero: int
    idioma: str
    inv: pathlib.Path
    meta: dict = field(compare=False, hash=False)

    @property
    def esperado(self) -> pathlib.Path:
        """Ruta del archivo con la salida esperada."""
        return self.inv.with_suffix(".expected")

    @property
    def entrada(self) -> pathlib.Path:
        """Ruta del archivo opcional con la entrada simulada."""
        return self.inv.with_suffix(".entrada")


@dataclass
class Resultado:
    """Resultado de ejecutar una versión de un ejercicio."""

    ejercicio: Ejercicio
    ok: bool
    salida: str | None
    esperado: str
    errores: list = field(default_factory=list)


def numero_nivel(nombre: str) -> int | None:
    """Acepta '3', '03', 'nivel3', 'nivel03', 'level3'... y devuelve 3."""
    m = re.fullmatch(r"(?:nivel|level)?0*(\d+)", nombre.strip().lower())
    return int(m.group(1)) if m else None


def descubrir(raiz: pathlib.Path = RAIZ, idiomas=IDIOMAS, niveles=None):
    """Devuelve (ejercicios, problemas) encontrados bajo `raiz`.

    `problemas` es una lista de pares (clave de mensaje, detalle) con
    archivos faltantes, metadatos inválidos o ejercicios sin pareja.
    """
    ejercicios: list[Ejercicio] = []
    problemas: list[tuple[str, str]] = []
    for idioma in idiomas:
        base = raiz / idioma
        if not base.is_dir():
            continue
        for carpeta in sorted(base.iterdir()):
            if not carpeta.is_dir() or not carpeta.name.startswith(PREFIJO_NIVEL[idioma]):
                continue
            nivel = numero_nivel(carpeta.name)
            if nivel is None or (niveles and nivel not in niveles):
                continue
            for inv in sorted(carpeta.glob("*.inv")):
                ruta_meta = inv.with_suffix(".json")
                for requerido in (inv.with_suffix(".expected"), ruta_meta):
                    if not requerido.exists():
                        problemas.append(("falta", str(requerido)))
                if not ruta_meta.exists():
                    continue
                try:
                    meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
                except ValueError as e:
                    problemas.append(("meta_invalida", f"{ruta_meta}: {e}"))
                    continue
                faltan = [c for c in CLAVES_METADATOS if not meta.get(c)]
                if faltan:
                    problemas.append(("meta_invalida", f"{ruta_meta}: {', '.join(faltan)}"))
                    continue
                numero = int(inv.name.split("_", 1)[0])
                ejercicios.append(Ejercicio(meta["id"], nivel, numero, idioma, inv, meta))
    # INV-1203: cada id debe existir en todos los idiomas pedidos; un
    # ejercicio solo en español no es parte de un currículo bilingüe.
    if len(idiomas) > 1:
        por_id: dict[str, set] = {}
        for e in ejercicios:
            por_id.setdefault(e.id, set()).add(e.idioma)
        for ident, presentes in sorted(por_id.items()):
            for idioma in idiomas:
                if idioma not in presentes:
                    problemas.append(("sin_pareja", f"{ident} ({idioma})"))
    ejercicios.sort(key=lambda e: (e.nivel, e.numero, IDIOMAS.index(e.idioma)))
    return ejercicios, problemas


def normalizar(texto: str) -> str:
    """Salida comparable: fin de línea Unix y sin saltos de línea finales.

    No se recortan espacios internos ni al inicio de línea: en ejercicios
    de figuras o tablas esos espacios SON la respuesta.
    """
    return texto.replace("\r\n", "\n").rstrip("\n")


def ejecutar(ej: Ejercicio) -> Resultado:
    """Compila y ejecuta una versión de un ejercicio con el intérprete real."""
    entrada: list[str] = []
    if ej.entrada.exists():
        entrada = ej.entrada.read_text(encoding="utf-8").splitlines()
    esperado = ej.esperado.read_text(encoding="utf-8") if ej.esperado.exists() else ""
    # INV-1202: sin entrada simulada, `leer` caería a input() y el ejecutor
    # quedaría bloqueado esperando teclado (p. ej. en CI). Con stdin vacío
    # una lectura sobrante produce un error de conversión, no un cuelgue.
    stdin_previo = sys.stdin
    sys.stdin = io.StringIO("")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            # INV-1022: `api.ejecutar` es la fachada única del pipeline (la
            # `CompilerFacade` de la CLI era una copia y se eliminó). La ruta
            # completa permite resolver `importar` relativo al ejercicio.
            r = api.ejecutar(
                ej.inv.read_text(encoding="utf-8"), ruta=str(ej.inv), entrada=tuple(entrada)
            )
    finally:
        sys.stdin = stdin_previo
    if not r.ok:
        return Resultado(ej, False, None, esperado, list(r.errores))
    salida = "".join(r.salida)
    ok = ej.esperado.exists() and normalizar(salida) == normalizar(esperado)
    return Resultado(ej, ok, salida, esperado)


def primera_diferencia(a: str, b: str) -> int:
    """Número (desde 1) de la primera línea en que difieren dos salidas."""
    la, lb = normalizar(a).split("\n"), normalizar(b).split("\n")
    for i, (x, y) in enumerate(zip(la, lb, strict=False), 1):
        if x != y:
            return i
    return min(len(la), len(lb)) + 1


def metadatos_en(ej: Ejercicio, idioma: str) -> dict:
    """Metadatos del mismo ejercicio en `idioma` (los propios si no hay pareja)."""
    if idioma == ej.idioma:
        return ej.meta
    carpeta = ej.inv.parent.parent.parent / idioma / f"{PREFIJO_NIVEL[idioma]}{ej.nivel:02d}"
    for ruta in sorted(carpeta.glob(f"{ej.numero:02d}_*.json")):
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except ValueError:
            break
    return ej.meta


def _mostrar_enunciado(meta: dict, m: dict, n_pistas: int, out) -> None:
    print(f"    {m['enunciado']}: {meta['enunciado']}", file=out)
    print(f"    {m['objetivos']}:", file=out)
    for o in meta["objetivos"]:
        print(f"      - {o}", file=out)
    for i, p in enumerate(meta["pistas"][:n_pistas], 1):
        print(f"    {m['pista']} {i}: {p}", file=out)


def construir_parser() -> argparse.ArgumentParser:
    """Parser de la línea de órdenes."""
    p = argparse.ArgumentParser(
        description="Ejecuta y verifica el currículo bilingüe de InvenioLang "
        "/ Runs and checks the bilingual InvenioLang curriculum."
    )
    p.add_argument(
        "niveles", nargs="*", help="niveles: 3, nivel3, level03, todos (por defecto todos)"
    )
    p.add_argument(
        "--idioma", choices=IDIOMAS, default="es", help="idioma de mensajes, enunciados y pistas"
    )
    p.add_argument(
        "--version",
        choices=IDIOMAS + ("ambas",),
        default="ambas",
        help="versiones a ejecutar: palabras clave en es, en o ambas",
    )
    p.add_argument(
        "--ejercicio", action="append", default=[], help="id a ejecutar, p. ej. N04-E05 (repetible)"
    )
    p.add_argument(
        "--enunciado",
        action="store_true",
        help="mostrar enunciado y objetivos también de los que pasan",
    )
    p.add_argument(
        "--pistas",
        type=int,
        default=1,
        help="pistas graduadas a mostrar (en fallos o con --enunciado)",
    )
    p.add_argument("--raiz", type=pathlib.Path, default=RAIZ, help="carpeta raíz del currículo")
    return p


def main(argv=None, out=None) -> int:
    """Punto de entrada: 0 si todo pasa, 1 si algo falla, 2 si no hay qué ejecutar."""
    out = out or sys.stdout
    args = construir_parser().parse_args(argv)
    m = MENSAJES[args.idioma]
    niveles: set[int] = set()
    for nombre in args.niveles:
        if nombre.lower() in ("todos", "all"):
            niveles = set()
            break
        num = numero_nivel(nombre)
        if num is None:
            print(f"{m['nivel_invalido']}: {nombre}", file=out)
            return 2
        niveles.add(num)
    idiomas = IDIOMAS if args.version == "ambas" else (args.version,)
    ejercicios, problemas = descubrir(args.raiz, idiomas, niveles or None)
    if args.ejercicio:
        pedidos = {e.upper() for e in args.ejercicio}
        ejercicios = [e for e in ejercicios if e.id.upper() in pedidos]
        problemas = [p for p in problemas if any(i in p[1].upper() for i in pedidos)]
    if not ejercicios and not problemas:
        print(m["sin_ejercicios"], file=out)
        return 2

    for clave, detalle in problemas:
        print(f"{m['fallo']} {m[clave]}: {detalle}", file=out)

    salidas: dict[str, dict[str, str | None]] = {}
    por_nivel: dict[int, list[int]] = {}
    fallos = len(problemas)
    nivel_actual = None
    for ej in ejercicios:
        if ej.nivel != nivel_actual:
            nivel_actual = ej.nivel
            print(f"== {m['nivel']} {ej.nivel}", file=out)
        r = ejecutar(ej)
        salidas.setdefault(ej.id, {})[ej.idioma] = r.salida
        cuenta = por_nivel.setdefault(ej.nivel, [0, 0])
        cuenta[1] += 1
        meta = metadatos_en(ej, args.idioma)
        etiqueta = f"{ej.id} [{ej.idioma}] {ej.inv.name} — {meta['titulo']}"
        if r.ok:
            cuenta[0] += 1
            print(f"{m['ok']} {etiqueta}", file=out)
            if args.enunciado:
                _mostrar_enunciado(meta, m, args.pistas, out)
            continue
        fallos += 1
        print(f"{m['fallo']} {etiqueta}", file=out)
        if r.salida is None:
            print(f"    {m['errores']}:", file=out)
            for e in r.errores:
                print(f"      {e}", file=out)
        else:
            print(f"    {m['linea']} {primera_diferencia(r.salida, r.esperado)}", file=out)
            print(f"    {m['esperado']}: {normalizar(r.esperado)!r}", file=out)
            print(f"    {m['obtenido']}: {normalizar(r.salida)!r}", file=out)
        _mostrar_enunciado(meta, m, max(args.pistas, 1), out)

    # INV-1203: las dos versiones del mismo ejercicio deben producir la
    # misma salida, aunque cada una coincida con su propio .expected.
    for ident, por_idioma in salidas.items():
        if set(por_idioma) == set(IDIOMAS) and None not in por_idioma.values():
            if normalizar(por_idioma["es"] or "") != normalizar(por_idioma["en"] or ""):
                fallos += 1
                print(f"{m['fallo']} {ident}: {m['distintas']}", file=out)

    print(f"== {m['resumen']}", file=out)
    for nivel, (ok, total) in sorted(por_nivel.items()):
        print(f"{m['nivel']} {nivel}: {ok}/{total} {m['correctos']}", file=out)
    total_ok = sum(c[0] for c in por_nivel.values())
    total = sum(c[1] for c in por_nivel.values())
    print(f"TOTAL: {total_ok}/{total} {m['correctos']}", file=out)
    if problemas:
        print(f"{len(problemas)} {m['problemas']}", file=out)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
