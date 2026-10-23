"""Registro xAPI local de intentos y panel docente (mapa de calor de errores).

Uso docente::

    python -m inveniolang.evaluation evaluar prog.inv casos.json --store aula.jsonl --actor a01
    python -m inveniolang.lms aula.jsonl      # intentos, errores más frecuentes, sugerencia

INV-1024: antes ningún código grababa intentos (el panel siempre estaba vacío),
el ``XAPIExporter`` se instanciaba y no se usaba (se persistía otro formato) y
el panel incluía la clave fija ``"plagio_check": "use plagiarism_score(a,b)"``.
Ahora ``evaluation.run_secure`` registra cada evaluación y lo que se persiste
es una sentencia xAPI 1.0 válida (actor/verb/object/result/timestamp).
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

from .patterns import Subject

__all__ = ["LMSStore", "XAPIStatement", "main"]

_VERBO_ID = "http://adlnet.gov/expapi/verbs/"
_CODIGO = re.compile(r"IL-[A-Z]+-\d+")


@dataclass(frozen=True)
class XAPIStatement:
    """Sentencia xAPI (Experience API 1.0) de un intento de ejercicio."""

    actor: str  # correo o identificador anonimizado
    verb: str  # attempted | passed | failed
    # INV-4410: la ruta de ejemplo apuntaba al currículo antiguo (carpeta
    # nivel1, retirada); tests/cierre/test_docs_enlaces.py comprueba que
    # toda ruta del currículo citada en el código exista.
    object: str  # id del ejercicio: ruta del .inv, p. ej. curriculum/es/nivel01/01_hola_mundo.inv
    result: dict[str, Any]
    timestamp: str

    def to_xapi(self) -> dict[str, Any]:
        """Serialización conforme a xAPI 1.0."""
        actor = (
            {"mbox": f"mailto:{self.actor}"}
            if "@" in self.actor
            else {"account": {"homePage": "urn:inveniolang", "name": self.actor}}
        )
        return {
            "actor": actor,
            "verb": {"id": _VERBO_ID + self.verb, "display": {"es-ES": self.verb}},
            "object": {"id": f"urn:inveniolang:{self.object}"},
            "result": self.result,
            "timestamp": self.timestamp,
        }


class LMSStore(Subject):
    """Almacén JSONL append-only de sentencias xAPI; notifica ``xapi`` a observadores.

    ``path=":memory:"`` mantiene las sentencias solo en memoria (sin IO).
    """

    def __init__(self, path: str = "lms_store.jsonl"):
        super().__init__()
        self.path = pathlib.Path(path)
        self._memoria = str(path) == ":memory:"
        self._buffer: list[dict[str, Any]] = []

    def record(self, actor: str, verb: str, obj: str, result: dict[str, Any]) -> XAPIStatement:
        """Registra un intento y lo persiste."""
        stmt = XAPIStatement(
            actor=actor,
            verb=verb,
            object=obj,
            result=result,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        datos = stmt.to_xapi()
        if self._memoria:
            self._buffer.append(datos)
        else:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(datos, ensure_ascii=False) + "\n")
        self.notify("xapi", stmt)
        return stmt

    def _sentencias(self) -> list[dict[str, Any]]:
        if self._memoria:
            return list(self._buffer)
        if not self.path.exists():
            return []
        sentencias = []
        for linea in self.path.read_text(encoding="utf-8").splitlines():
            try:
                sentencias.append(json.loads(linea))
            except json.JSONDecodeError:
                continue  # una línea corrupta no invalida el resto del registro
        return sentencias

    def heatmap_errores(self) -> dict[str, int]:
        """Frecuencia de cada código IL-XXX-NNN en los intentos fallidos."""
        conteo: dict[str, int] = {}
        for s in self._sentencias():
            if s.get("verb", {}).get("id") != _VERBO_ID + "failed":
                continue
            for texto in s.get("result", {}).get("errores", []):
                for codigo in _CODIGO.findall(str(texto)):
                    conteo[codigo] = conteo.get(codigo, 0) + 1
        return conteo

    def dashboard(self) -> dict[str, Any]:
        """Panel docente: intentos, mapa de calor y sugerencia de refuerzo."""
        hm = self.heatmap_errores()
        top = sorted(hm.items(), key=lambda x: (-x[1], x[0]))[:5]
        return {
            "total_intentos": len(self._sentencias()),
            "heatmap": hm,
            "top_errores": top,
            "sugerencia": f"Refuerzo en {top[0][0]}" if top else "Sin datos",
        }


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m inveniolang.lms [registro.jsonl]`` imprime el panel docente."""
    args = sys.argv[1:] if argv is None else argv
    d = LMSStore(args[0] if args else "lms_store.jsonl").dashboard()
    print(f"Intentos: {d['total_intentos']}")
    for codigo, n in d["top_errores"]:
        print(f"  {codigo}: {n}")
    print(d["sugerencia"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
