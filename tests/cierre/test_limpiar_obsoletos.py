"""INV-4409: detección y limpieza de módulos/carpetas retirados del proyecto.

Antes nada avisaba si una copia vieja conservaba ``inveniolang/visual/``,
``flowchart.py`` o un ``uml.py`` que tapa al paquete ``uml/``. Ahora
``scripts/limpiar_obsoletos.py`` tiene la lista (con motivo), la usan
``tests/test_calidad_paquete.py`` y ``_audit.py``, y el script borra SOLO esa
lista (simulacro por defecto, ``--aplicar`` para borrar).
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

_spec = importlib.util.spec_from_file_location(
    "limpiar_obsoletos", RAIZ / "scripts" / "limpiar_obsoletos.py"
)
assert _spec is not None and _spec.loader is not None
lo = importlib.util.module_from_spec(_spec)
sys.modules["limpiar_obsoletos"] = lo
_spec.loader.exec_module(lo)


def _copia_vieja(raiz: Path) -> list[Path]:
    """Árbol mínimo con todos los retirados y archivos legítimos alrededor."""
    for o in lo.OBSOLETOS:
        ruta = raiz / o.ruta
        if o.carpeta:
            (ruta / "__pycache__").mkdir(parents=True)
            (ruta / "viejo.py").write_text("x = 1\n", encoding="utf-8")
        else:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text("viejo\n", encoding="utf-8")
    legitimos = [
        raiz / "inveniolang" / "uml" / "__init__.py",
        raiz / "inveniolang" / "gui" / "panel_flujo.py",
        raiz / "inveniolang" / "ll1.py",
        raiz / "curriculum" / "es" / "nivel01" / "01_hola_mundo.inv",
        raiz / "curriculum" / "nivel11" / "propio.inv",  # no está en la lista
        raiz / "pruebas" / "parser.out",  # no está en la lista: no se toca
    ]
    for f in legitimos:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("ok\n", encoding="utf-8")
    return legitimos


def test_simulacro_no_borra_y_aplicar_borra_solo_la_lista(tmp_path, capsys):
    legitimos = _copia_vieja(tmp_path)
    assert len(lo.encontrar(tmp_path)) == len(lo.OBSOLETOS)
    assert lo.main(["--raiz", str(tmp_path)]) == 0
    salida = capsys.readouterr().out
    assert "Simulacro" in salida and "inveniolang/visual" in salida
    assert all((tmp_path / o.ruta).exists() for o in lo.OBSOLETOS)

    assert lo.main(["--raiz", str(tmp_path), "--aplicar", "--idioma", "en"]) == 0
    assert "Deleted inveniolang/uml.py" in capsys.readouterr().out
    assert lo.encontrar(tmp_path) == []
    assert not any((tmp_path / o.ruta).exists() for o in lo.OBSOLETOS)
    assert all(f.exists() for f in legitimos)
    assert lo.main(["--raiz", str(tmp_path), "--aplicar"]) == 0  # idempotente
    assert "No quedan restos" in capsys.readouterr().out


def test_mensaje_claro_con_motivo_y_orden(tmp_path):
    (tmp_path / "inveniolang" / "visual").mkdir(parents=True)
    (tmp_path / "inveniolang" / "flowchart.py").write_text("", encoding="utf-8")
    texto = lo.mensaje(lo.encontrar(tmp_path), "es")
    assert "inveniolang/visual/:" in texto and "inveniolang/flowchart.py:" in texto
    assert "inveniolang/flujo/" in texto  # dice por qué se sustituyó
    assert "python scripts/limpiar_obsoletos.py --aplicar" in texto


def test_tipo_declarado_y_enlaces_simbolicos(tmp_path):
    # Una carpeta llamada como un archivo retirado (o al revés) no se toca.
    (tmp_path / "inveniolang" / "uml.py").mkdir(parents=True)
    (tmp_path / "inveniolang" / "visual").write_text("", encoding="utf-8")
    assert lo.encontrar(tmp_path) == []
    # Un enlace simbólico se borra como enlace, sin seguirlo.
    destino = tmp_path / "fuera"
    destino.mkdir()
    (destino / "importante.txt").write_text("no borrar", encoding="utf-8")
    try:
        (tmp_path / "inveniolang" / "studio").symlink_to(destino, target_is_directory=True)
    except OSError as e:  # Windows sin modo desarrollador: crear enlaces exige privilegio
        pytest.skip(f"el sistema no permite crear enlaces simbólicos: {e}")
    lo.limpiar(tmp_path, aplicar=True)
    assert not (tmp_path / "inveniolang" / "studio").exists()
    assert (destino / "importante.txt").read_text(encoding="utf-8") == "no borrar"


def _retirados_segun_git() -> set[str]:
    """Rutas retiradas desde la base, con la carpeta más alta que quedó vacía."""

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True
        ).stdout

    salida = git("log", "--diff-filter=DR", "--name-status", "--format=", "f2f963d..HEAD")
    borrados = set()
    for linea in salida.splitlines():
        partes = linea.split("\t")
        if partes and partes[0][:1] in ("D", "R"):
            borrados.add(partes[1])
    actuales = set(git("ls-files").splitlines())
    dirs_actuales = {str(Path(f).parent) for f in actuales} | {
        str(p) for f in actuales for p in Path(f).parents
    }
    resultado = set()
    for ruta in borrados:
        if ruta in actuales:
            continue
        tope = Path(ruta)
        for padre in Path(ruta).parents:
            if str(padre) == "." or str(padre) in dirs_actuales:
                break
            tope = padre
        resultado.add(str(tope).replace(os.sep, "/"))
    return resultado


@pytest.mark.skipif(shutil.which("git") is None or not (RAIZ / ".git").exists(), reason="sin git")
def test_la_lista_es_exactamente_lo_retirado_en_el_proyecto():
    try:
        esperado = _retirados_segun_git()
    except subprocess.CalledProcessError:
        pytest.skip("la historia de git no incluye la base f2f963d")
    lista = {o.ruta for o in lo.OBSOLETOS if o.motivo != "OBS.motivo.parser_out"}
    assert lista == esperado
