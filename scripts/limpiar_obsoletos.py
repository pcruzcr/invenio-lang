# scripts/limpiar_obsoletos.py — Restos de versiones anteriores del proyecto
"""Detecta y borra los módulos y carpetas que el proyecto ya retiró (INV-4409).

Quien actualiza una copia vieja de InvenioLang copiando los archivos nuevos
encima conserva los que se eliminaron: ``inveniolang/visual/``,
``flowchart.py``, ``uml.py`` junto al paquete ``uml/``... Esos restos se
pueden seguir importando, confunden al estudiante (código fingido que el
proyecto ya no mantiene) y rompen las puertas de calidad. Esta es la ÚNICA
lista de retirados (con su motivo); la usan ``tests/test_calidad_paquete.py``
y ``_audit.py`` para avisar, y este script para borrarlos.

Uso::

    python scripts/limpiar_obsoletos.py              # solo muestra (por defecto)
    python scripts/limpiar_obsoletos.py --aplicar    # borra SOLO la lista
    python scripts/limpiar_obsoletos.py --raiz DIR --idioma en

Garantías: nunca borra nada fuera de :data:`OBSOLETOS` (rutas exactas, sin
comodines), no sigue enlaces simbólicos (borra el enlace, no su destino) y
una entrada declarada como carpeta solo se borra si es una carpeta (y un
archivo solo si es un archivo).

La lista se calculó con ``git log --diff-filter=D --name-only f2f963d..`` (más
``ll1_demo.py``, que se renombró a ``ll1.py``): cada archivo retirado
aparece con su carpeta de nivel más alto que quedó vacía, más las tablas de
depuración ``parser.out`` que PLY dejaba sueltas (el parser ya no las
escribe; quien las necesite las regenera fuera del paquete, ver
``docs/InvenioLang_GramaticaFormal.md``).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from inveniolang import i18n  # noqa: E402


@dataclass(frozen=True)
class Obsoleto:
    """Ruta retirada del proyecto (relativa a la raíz, con ``/``)."""

    ruta: str
    carpeta: bool
    motivo: str  # clave del catálogo i18n (OBS.motivo.*)


def _carpetas(rutas: str, motivo: str) -> tuple[Obsoleto, ...]:
    return tuple(Obsoleto(r, True, motivo) for r in rutas.split())


def _archivos(rutas: str, motivo: str) -> tuple[Obsoleto, ...]:
    return tuple(Obsoleto(r, False, motivo) for r in rutas.split())


OBSOLETOS: tuple[Obsoleto, ...] = (
    *_carpetas(
        "curriculum/nivel1 curriculum/nivel2 curriculum/nivel3 curriculum/nivel4 "
        "curriculum/nivel5 curriculum/nivel6 curriculum/nivel7 curriculum/nivel8 "
        "curriculum/nivel9 curriculum/nivel10",
        "OBS.motivo.curriculo",
    ),
    *_carpetas(
        "inveniolang/analytics inveniolang/backend inveniolang/grammar inveniolang/studio "
        "inveniolang/toolchain inveniolang/transpiler inveniolang/types inveniolang/visual",
        "OBS.motivo.fingido",
    ),
    *_archivos(
        "inveniolang/gui/collab.py inveniolang/gui/editor.py inveniolang/ast_validator.py "
        "inveniolang/certification.py inveniolang/ds_visualizer.py inveniolang/ir_poo.py "
        "inveniolang/policy.py inveniolang/tutor_llm.py",
        "OBS.motivo.fingido",
    ),
    *_archivos("inveniolang/ll1_demo.py", "OBS.motivo.ll1"),
    *_archivos("inveniolang/flowchart.py inveniolang/flowchart_builder.py", "OBS.motivo.flujo"),
    *_archivos("inveniolang/uml.py", "OBS.motivo.uml"),
    # INV-4412: el estudio web (INV-4201) sustituyó a la página de prueba de Pyodide.
    *_archivos("web/pyodide.html", "OBS.motivo.web"),
    *_archivos("parser.out inveniolang/parser.out", "OBS.motivo.parser_out"),
)


def encontrar(raiz: Path = RAIZ) -> list[Obsoleto]:
    """Entradas de :data:`OBSOLETOS` presentes en ``raiz`` (del tipo declarado)."""
    presentes = []
    for o in OBSOLETOS:
        ruta = raiz / o.ruta
        if ruta.is_symlink() or (ruta.is_dir() if o.carpeta else ruta.is_file()):
            presentes.append(o)
    return presentes


def mensaje(presentes: list[Obsoleto], idioma: str | None = None) -> str:
    """Aviso claro de qué borrar y cómo (vacío si no queda nada)."""
    if not presentes:
        return ""
    lineas = [i18n.t("OBS.encontrados", idioma, n=len(presentes))]
    for o in presentes:
        ruta = o.ruta + ("/" if o.carpeta else "")
        lineas.append(f"  - {ruta}: {i18n.t(o.motivo, idioma)}")
    lineas.append(i18n.t("OBS.como_borrar", idioma))
    return "\n".join(lineas)


def limpiar(raiz: Path = RAIZ, aplicar: bool = False) -> list[Obsoleto]:
    """Borra (si ``aplicar``) las entradas presentes; devuelve las afectadas."""
    presentes = encontrar(raiz)
    if aplicar:
        for o in presentes:
            ruta = raiz / o.ruta
            if ruta.is_symlink() or not o.carpeta:
                ruta.unlink()
            else:
                shutil.rmtree(ruta)
    return presentes


def main(argv: list[str] | None = None) -> int:
    """CLI: muestra (por defecto) o borra con ``--aplicar`` la lista de retirados."""
    p = argparse.ArgumentParser(
        prog="python scripts/limpiar_obsoletos.py", description=i18n.t("OBS.descripcion")
    )
    p.add_argument("--aplicar", action="store_true", help=i18n.t("OBS.arg.aplicar"))
    p.add_argument("--raiz", default=str(RAIZ), help=i18n.t("OBS.arg.raiz"))
    p.add_argument("--idioma", choices=("es", "en"), default=None)
    args = p.parse_args(argv)
    raiz = Path(args.raiz).resolve()
    afectados = limpiar(raiz, aplicar=args.aplicar)
    if not afectados:
        print(i18n.t("OBS.nada", args.idioma))
        return 0
    for o in afectados:
        clave = "OBS.borrado" if args.aplicar else "OBS.se_borraria"
        print(i18n.t(clave, args.idioma, ruta=o.ruta, motivo=i18n.t(o.motivo, args.idioma)))
    if not args.aplicar:
        print(i18n.t("OBS.simulacro", args.idioma))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
