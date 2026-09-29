# lms.py — H2.5 LMS xAPI + Dashboard docente
# Patrones: Observer (eventos), Strategy (exportadores), Facade (dashboard), Singleton (store)
from __future__ import annotations
import json
import time
import pathlib
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from .patterns import Subject, Strategy


@dataclass
class XAPIStatement:
    actor: str  # email o id anonimizado
    verb: str  # attempted, completed, failed
    object: str  # id ejercicio: curriculum/nivel1/01_hola.inv
    result: Dict[str, Any]
    timestamp: str

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


class XAPIExporter(Strategy):
    def execute(self, stmt: XAPIStatement, *args, **kwargs) -> Dict[str, Any]:
        return {
            "actor": {"mbox": f"mailto:{stmt.actor}"} if "@" in stmt.actor else {"account": {"name": stmt.actor}},
            "verb": {"id": f"http://adlnet.gov/expapi/verbs/{stmt.verb}", "display": {"es": stmt.verb}},
            "object": {"id": stmt.object},
            "result": stmt.result,
            "timestamp": stmt.timestamp,
        }


class LMSStore(Subject):
    """Store xAPI local (JSONL) + Observer para dashboard. Singleton opcional."""

    def __init__(self, path: str = "lms_store.jsonl"):
        super().__init__()
        self.path = pathlib.Path(path)
        self._exporter = XAPIExporter()
        self._buffer: List[XAPIStatement] = []

    def record(self, actor: str, verb: str, obj: str, result: Dict[str, Any]) -> XAPIStatement:
        stmt = XAPIStatement(
            actor=actor,
            verb=verb,
            object=obj,
            result=result,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self._buffer.append(stmt)
        # persistencia append-only (soporta :memory: para tests sin IO)
        if str(self.path) != ":memory:":
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(stmt.to_json(), ensure_ascii=False) + "\n")
        self.notify("xapi", stmt)
        return stmt

    def heatmap_errores(self) -> Dict[str, int]:
        # Agrega conteo por código IL-XXX de todos los statements failed
        counts: Dict[str, int] = {}
        if str(self.path) == ":memory:" or not self.path.exists():
            return counts
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                j = json.loads(line)
                if j.get("verb") == "failed":
                    for cod in j.get("result", {}).get("errores", []):
                        c = cod.split()[0].strip("[]") if cod.startswith("[") else cod
                        counts[c] = counts.get(c, 0) + 1
            except Exception:
                continue
        return counts

    def dashboard(self) -> Dict[str, Any]:
        hm = self.heatmap_errores()
        if str(self.path) == ":memory:":
            total = len(self._buffer)
        else:
            total = sum(1 for _ in open(self.path, encoding="utf-8")) if self.path.exists() else 0
        top = sorted(hm.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "total_intentos": total,
            "heatmap": hm,
            "top_errores": top,
            "sugerencia": f"Refuerzo en {top[0][0]}" if top else "Sin datos",
            "plagio_check": "use plagiarism_score(a,b)",
        }


# Dashboard CLI
def print_dashboard(path: str = "lms_store.jsonl"):
    store = LMSStore(path)
    d = store.dashboard()
    print(f"Intentos: {d['total_intentos']}")
    for cod, cnt in d["top_errores"]:
        print(f"  {cod}: {cnt}")
    print(d["sugerencia"])
