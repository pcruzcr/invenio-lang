# certification.py — H3.9 Micro-credencial con rúbrica automatizada
# Patrones: Strategy (rúbricas), Factory (certificados), Observer (progreso), Template
from __future__ import annotations
import json, hashlib, time, pathlib
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from .patterns import Strategy
from .cli import CompilerFacade


@dataclass
class RubricaItem:
    id: str
    peso: float
    descripcion: str
    passed: bool = False
    detalle: str = ""


class RubricaStrategy(Strategy):
    def execute(self, *args, **kwargs) -> RubricaItem:
        raise NotImplementedError


class CompilaStrategy(RubricaStrategy):
    def execute(self, ruta: str, *args, **kwargs) -> RubricaItem:
        fac = CompilerFacade()
        r = fac.execute(ruta)
        ok = r.get("ok", False)
        return RubricaItem("compila", 0.2, "Compila sin errores", ok, "" if ok else str(r.get("errores")))


class TestOcultoStrategy(RubricaStrategy):
    def __init__(self, casos: List[Dict[str, Any]]):
        self.casos = casos

    def execute(self, ruta: str, *args, **kwargs) -> RubricaItem:
        fac = CompilerFacade()
        passed = 0
        for c in self.casos:
            entrada = c.get("entrada", [])
            esperado = c.get("esperado", "")
            r = fac.execute(ruta, entrada)
            salida = "".join(r.get("salida", [])).strip() if r.get("ok") else ""
            if salida == esperado:
                passed += 1
        ok = passed == len(self.casos)
        return RubricaItem(
            "tests_ocultos", 0.5, f"Tests ocultos {passed}/{len(self.casos)}", ok, f"{passed}/{len(self.casos)}"
        )


class ComplejidadStrategy(RubricaStrategy):
    def execute(self, ruta: str, *args, **kwargs) -> RubricaItem:
        try:
            from .complexity import analyze

            text = pathlib.Path(ruta).read_text(encoding="utf-8")
            r = analyze(text)
            ok = r.get("max_depth", 0) <= 2  # exige O(n2) max para micro-credencial basica
            return RubricaItem("complejidad", 0.15, f"Complejidad {r.get('estimado')} <= O(n2)", ok, str(r))
        except Exception as e:
            return RubricaItem("complejidad", 0.15, "Complejidad", False, str(e))


class EstiloStrategy(RubricaStrategy):
    def execute(self, ruta: str, *args, **kwargs) -> RubricaItem:
        text = pathlib.Path(ruta).read_text(encoding="utf-8")
        issues = []
        if "    " not in text:
            issues.append("indentación")
        if text.count(";") < 2:
            issues.append("pocos ;")
        ok = len(issues) == 0
        return RubricaItem("estilo", 0.15, "Estilo básico", ok, ",".join(issues))


def certificar(ruta: str, casos_ocultos: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    casos_ocultos = casos_ocultos or []
    # registra estrategias
    strategies = [CompilaStrategy(), TestOcultoStrategy(casos_ocultos), ComplejidadStrategy(), EstiloStrategy()]
    items: List[RubricaItem] = [s.execute(ruta) for s in strategies]
    nota = sum(it.peso for it in items if it.passed) / sum(it.peso for it in items) * 10
    passed = nota >= 6 and all(it.passed for it in items if it.id == "compila")
    cert = {
        "ruta": ruta,
        "nota": round(nota, 2),
        "aprobado": passed,
        "items": [asdict(i) for i in items],
        "hash": hashlib.sha256((ruta + str(nota)).encode()).hexdigest()[:12],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return cert


def emitir_pdf(ruta: str, out: str = "certificado.pdf") -> str:
    """Sprint0: PDF simple (reportlab si disponible, fallback txt) con firma docente."""
    cert = certificar(ruta)
    try:
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(out)
        c.drawString(50, 800, f"Certificado InvenioLang 3.0 — {cert["ruta"]}")
        c.drawString(50, 780, f"Nota: {cert["nota"]} Aprobado: {cert["aprobado"]} Hash: {cert["hash"]}")
        c.drawString(50, 760, "Firma docente: ___________________")
        c.save()
        return out
    except Exception:
        pathlib.Path(out.replace(".pdf", ".txt")).write_text(emitir_json(ruta), encoding="utf-8")
        return out.replace(".pdf", ".txt")


def emitir_json(ruta: str, out: str = None) -> str:
    cert = certificar(ruta)
    js = json.dumps(cert, indent=2, ensure_ascii=False)
    if out:
        pathlib.Path(out).write_text(js, encoding="utf-8")
    return js
