"""INV-4410 / INV-4411: documentación sin enlaces rotos ni módulos retirados.

* Todo enlace interno ``[texto](ruta#ancla)`` de ``docs/`` (y de los README
  de currículo, web y extensión) apunta a un archivo existente y, si lleva
  ancla hacia un ``.md``, a un encabezado existente.
* Toda ruta entre comillas invertidas que parezca un archivo del proyecto
  (``inveniolang/flujo/edicion.py``, ``tests/x.py:12``) existe.
* Toda ruta ``curriculum/...`` citada en el código o la documentación existe
  (``lms.py`` citaba ``curriculum/nivel1/01_hola.inv``, retirado).
* Un módulo o carpeta retirado (lista de ``scripts/limpiar_obsoletos.py``)
  solo se menciona diciendo que se retiró o con qué se sustituyó.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCS = sorted((RAIZ / "docs").rglob("*.md")) + [
    p
    for p in (
        RAIZ / "curriculum" / "README.md",
        RAIZ / "curriculum" / "README.en.md",
        RAIZ / "ACCESSIBILITY.md",
        RAIZ / "CONTRIBUTING.md",
        RAIZ / "SECURITY.md",
    )
    if p.exists()
]
_ENLACE = re.compile(r"\]\(([^)\s]+)\)")
_CODIGO = re.compile(
    r"`([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.(?:py|md|inv|json|ebnf|toml|txt|js|html))(?::\d+)?"
)
_RETIRO = re.compile(r"retirad|sustitu|eliminad|retired|replaced|removed|antiguo", re.I)
_CURRICULO = re.compile(r"curriculum/[A-Za-z0-9_/.-]+\.(?:inv|json|expected)")
# INV-5004: docs/informes/ son fotos fechadas de una auditoría y su plan: citan
# módulos que se retiraron después y archivos que el plan aún va a crear. Sus
# enlaces internos se siguen verificando; las rutas citadas y los retirados, no.
_INFORMES = RAIZ / "docs" / "informes"


def _es_informe(doc: Path) -> bool:
    return _INFORMES in doc.parents


def _ancla(titulo: str) -> str:
    """Ancla estilo GitHub de un encabezado."""
    t = unicodedata.normalize("NFC", titulo.strip().lower())
    t = re.sub(r"[^\w\- ]", "", t)
    return t.replace(" ", "-")


def _anclas(md: Path) -> set[str]:
    return {
        _ancla(linea.lstrip("#"))
        for linea in md.read_text(encoding="utf-8").splitlines()
        if linea.startswith("#")
    }


def test_enlaces_internos_existen():
    rotos = []
    for doc in DOCS:
        for n, linea in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for m in _ENLACE.finditer(linea):
                destino = m.group(1)
                if re.match(r"[a-z]+:", destino):
                    continue
                ruta, _, ancla = destino.partition("#")
                archivo = (doc.parent / ruta) if ruta else doc
                if not archivo.exists():
                    rotos.append(f"{doc.relative_to(RAIZ)}:{n}: {destino}")
                elif ancla and archivo.suffix == ".md" and ancla not in _anclas(archivo):
                    rotos.append(f"{doc.relative_to(RAIZ)}:{n}: ancla #{ancla}")
    assert rotos == [], "\n".join(rotos)


def test_rutas_citadas_en_docs_existen():
    faltan = []
    for doc in (d for d in DOCS if not _es_informe(d)):
        for n, linea in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for m in _CODIGO.finditer(linea):
                ruta = m.group(1)
                if "NN" in ruta or _RETIRO.search(linea):
                    continue  # plantilla (nivelNN/MM_nombre) o mención histórica de un retirado
                if not any(
                    c.exists()
                    for c in (RAIZ / ruta, doc.parent / ruta, RAIZ / "inveniolang" / ruta)
                ):
                    faltan.append(f"{doc.relative_to(RAIZ)}:{n}: {ruta}")
    assert faltan == [], "\n".join(faltan)


def test_rutas_del_curriculo_citadas_existen():
    fuentes = list((RAIZ / "inveniolang").rglob("*.py")) + DOCS
    faltan = [
        f"{f.relative_to(RAIZ)}: {m}"
        for f in fuentes
        if "__pycache__" not in f.parts
        for m in _CURRICULO.findall(f.read_text(encoding="utf-8"))
        if not (RAIZ / m).exists()
    ]
    assert faltan == [], "\n".join(faltan)


def _retirados() -> list[str]:
    spec = importlib.util.spec_from_file_location(
        "limpiar_obsoletos", RAIZ / "scripts" / "limpiar_obsoletos.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["limpiar_obsoletos"] = modulo
    spec.loader.exec_module(modulo)
    nombres = []
    for o in modulo.OBSOLETOS:
        if o.ruta.endswith("parser.out") or o.ruta.startswith("curriculum/"):
            continue  # parser.out es pedagógico (§7 de la gramática); currículo: otra prueba
        nombres.append(o.ruta.removeprefix("inveniolang/") + ("/" if o.carpeta else ""))
    return nombres


def test_modulos_retirados_solo_como_historia():
    """Cada mención a un módulo retirado dice que se retiró o qué lo sustituye."""
    patrones = [re.compile(r"(?<![\w/.])(?:inveniolang/)?" + re.escape(n)) for n in _retirados()]
    sueltas = []
    for doc in (d for d in DOCS if not _es_informe(d)):
        parrafos = re.split(r"\n\s*\n", doc.read_text(encoding="utf-8"))
        for parrafo in parrafos:
            if any(p.search(parrafo) for p in patrones) and not _RETIRO.search(parrafo):
                sueltas.append(f"{doc.relative_to(RAIZ)}: {parrafo.strip()[:120]}")
    assert sueltas == [], "\n".join(sueltas)
