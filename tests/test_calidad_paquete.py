"""Puertas estructurales del paquete: sin módulos huérfanos, sin código fingido.

INV-1000: el encargo exige que `inveniolang/` no tenga stubs, código fingido
ni código muerto. Estas pruebas lo convierten en una regresión verificable
con análisis AST (no grep ingenuo): si alguien vuelve a añadir un módulo que
nada importa, una función sin llamadores o un "demo"/"stub", la suite falla.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / "inveniolang"

# Ficheros generados o de otra capa que no se analizan:
#  - parsetab.py lo genera PLY;
#  - gui_qt.py / gui_tk.py son la capa GUI (fuera de este análisis, pero SÍ
#    cuentan como consumidores: ver _consumidores()).
_EXCLUIDOS = {"parsetab.py"}

# Puntos de entrada de producción: lo que un usuario ejecuta o importa.
_RAICES = {
    "inveniolang",
    "inveniolang.api",
    "inveniolang.cli",
    "inveniolang.gui_qt",
    "inveniolang.gui_tk",
    # INV-4200: entrada del estudio web; la importa el Web Worker
    # (web/estudio/js/trabajador.js) dentro de Pyodide.
    "inveniolang.web",
}

# Scripts de producción fuera del paquete que consumen su API.
_SCRIPTS = [
    RAIZ / "main.py",
    RAIZ / "curriculum" / "runner.py",
    RAIZ / "scripts" / "verify_release.py",
]


def _modulos() -> dict[str, Path]:
    mods: dict[str, Path] = {}
    for p in PAQUETE.rglob("*.py"):
        if p.name in _EXCLUIDOS or "__pycache__" in p.parts:
            continue
        partes = list(p.relative_to(RAIZ).with_suffix("").parts)
        if partes[-1] == "__init__":
            partes = partes[:-1]
        mods[".".join(partes)] = p
    return mods


def _importa(nombre: str, ruta: Path) -> set[str]:
    """Módulos del paquete que importa `nombre` (relativos y absolutos)."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    paquete = nombre if ruta.name == "__init__.py" else nombre.rpartition(".")[0]
    destinos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            destinos.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = paquete.split(".")
                base = base[: len(base) - (nodo.level - 1)]
                mod = ".".join(base + ([nodo.module] if nodo.module else []))
            else:
                mod = nodo.module or ""
            destinos.add(mod)
            destinos.update(f"{mod}.{a.name}" for a in nodo.names)
    return destinos


def _documentado(modulo: str) -> bool:
    """Una herramienta `python -m` cuenta como raíz solo si está documentada."""
    textos = [RAIZ / "README.md", *sorted((RAIZ / "docs").glob("*.md"))]
    return any(modulo in t.read_text(encoding="utf-8") for t in textos)


def _es_herramienta(ruta: Path) -> bool:
    return '__name__ == "__main__"' in ruta.read_text(encoding="utf-8")


def test_la_raiz_web_la_importa_de_verdad_el_estudio():
    """INV-4200: «inveniolang.web» solo es raíz porque el Worker del estudio la importa."""
    trabajador = RAIZ / "web" / "estudio" / "js" / "trabajador.js"
    assert "from inveniolang.web import llamar" in trabajador.read_text(encoding="utf-8")


def test_todo_modulo_es_alcanzable_desde_un_punto_de_entrada():
    """Ningún módulo del paquete queda huérfano (rule 2 del encargo)."""
    mods = _modulos()
    raices = set(_RAICES)
    raices.update(m for m, p in mods.items() if _es_herramienta(p) and _documentado(m))
    alcanzados: set[str] = set()
    pendientes = [r for r in raices if r in mods]
    while pendientes:
        actual = pendientes.pop()
        if actual in alcanzados:
            continue
        alcanzados.add(actual)
        # Importar un submódulo ejecuta los __init__ de sus paquetes padre.
        partes = actual.split(".")
        for i in range(1, len(partes)):
            pendientes.append(".".join(partes[:i]))
        for destino in _importa(actual, mods[actual]):
            if destino in mods and destino not in alcanzados:
                pendientes.append(destino)
    huerfanos = sorted(set(mods) - alcanzados)
    assert huerfanos == [], f"módulos que ningún punto de entrada importa: {huerfanos}"


def _nombres_usados(rutas: list[Path]) -> dict[Path, set[str]]:
    usados: dict[Path, set[str]] = {}
    for ruta in rutas:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        nombres: set[str] = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Name):
                nombres.add(nodo.id)
            elif isinstance(nodo, ast.Attribute):
                nombres.add(nodo.attr)
            elif isinstance(nodo, ast.alias):
                nombres.add(nodo.asname or nodo.name.rpartition(".")[2])
                nombres.add(nodo.name.rpartition(".")[2])
        usados[ruta] = nombres
    return usados


def _exportados(arbol: ast.Module) -> set[str]:
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in nodo.targets
        ):
            return {e.value for e in ast.walk(nodo.value) if isinstance(e, ast.Constant)}
    return set()


# Excepciones justificadas: consumidores que no son "producción" pero tampoco
# código muerto.
_PERMITIDOS = {
    # Máquina que ejecuta el código objetivo de --target para verificarlo
    # contra el intérprete (pruebas/conformidad.py §E12). Es el oráculo de la
    # Etapa 12.11; pertenece a ir.py (fase de lenguaje).
    "inveniolang.ir.MaquinaObjetivo",
}


def test_ninguna_funcion_ni_clase_de_modulo_sin_llamadores():
    """Toda función/clase de nivel módulo tiene un consumidor de producción.

    Cuenta como consumidor cualquier referencia desde otro punto del paquete
    (incluida la GUI) o desde los scripts de producción; la API pública
    declarada en `__all__` también cuenta. Las pruebas NO cuentan: una función
    que solo usan los tests es código muerto con cobertura.
    PLY descubre `p_*`/`t_*` por reflexión, así que parser/lexer se excluyen.
    """
    mods = _modulos()
    rutas = list(mods.values()) + [s for s in _SCRIPTS if s.exists()]
    usados = _nombres_usados(rutas)
    sin_uso: list[str] = []
    for nombre, ruta in mods.items():
        if ruta.name in ("parser.py", "lexer.py"):
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        publicos = _exportados(arbol)
        for nodo in arbol.body:
            if not isinstance(nodo, (ast.FunctionDef, ast.ClassDef)):
                continue
            ident = nodo.name
            if ident in publicos or ident == "main" or f"{nombre}.{ident}" in _PERMITIDOS:
                continue
            en_otros = any(ident in n for r, n in usados.items() if r != ruta)
            # Uso interno: una referencia en el propio módulo además de la definición.
            propio = sum(
                1
                for n in ast.walk(arbol)
                if (isinstance(n, ast.Name) and n.id == ident)
                or (isinstance(n, ast.Attribute) and n.attr == ident)
            )
            if not en_otros and propio == 0:
                sin_uso.append(f"{nombre}.{ident}")
    assert sin_uso == [], f"definiciones sin llamadores de producción: {sin_uso}"


_MARCAS_PROHIBIDAS = re.compile(
    r"\bdemo\b|\bstub\b|demostraci[oó]n|\b100 ?%(?! del)", re.IGNORECASE
)


def test_sin_marcas_de_codigo_fingido():
    """Nada de "demo", "stub", "(demostración)" ni "100 %" de marketing."""
    hallazgos = []
    for ruta in _modulos().values():
        if ruta.name in ("gui_qt.py", "gui_tk.py"):
            continue
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            if _MARCAS_PROHIBIDAS.search(linea):
                hallazgos.append(f"{ruta.relative_to(RAIZ)}:{n}: {linea.strip()}")
    assert hallazgos == [], "\n".join(hallazgos)


def _limpiador():
    """``scripts/limpiar_obsoletos.py``: la única lista de retirados (INV-4409)."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "limpiar_obsoletos", RAIZ / "scripts" / "limpiar_obsoletos.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["limpiar_obsoletos"] = modulo  # dataclass necesita su módulo
    spec.loader.exec_module(modulo)
    return modulo


def test_sin_restos_de_modulos_retirados():
    """INV-4409: una copia vieja actualizada encima conserva módulos retirados.

    ``inveniolang/visual/``, ``flowchart.py`` o un ``uml.py`` que tapa al
    paquete ``uml/`` se siguen pudiendo importar aunque el proyecto ya no los
    mantiene. El mensaje dice qué borrar, por qué y con qué orden.
    """
    limpiador = _limpiador()
    presentes = limpiador.encontrar(RAIZ)
    assert presentes == [], limpiador.mensaje(presentes)
