# tutor_llm.py — v7 LLM guardarraíl (nunca da solución, solo Socrático)
from __future__ import annotations

from .complexity import analyze
from .error_explainer import explicar

SYSTEM = "Eres tutor Socrático InvenioLang. Nunca des código solución. Solo preguntas guía."


def guardrail(prompt: str, code: str) -> str:
    """Filtra la respuesta del tutor."""
    # bloquea si pide solución directa
    triggers = ["dame el código", "solución completa", "hazlo por mí"]
    if any(t in prompt.lower() for t in triggers):
        return "No puedo dar la solución. ¿Cuál es el invariante de tu ciclo?"
    return prompt


def tutor_turn(error_code: str, code: str, historial: list[dict] = None) -> str:
    """Genera un turno del tutor."""
    exp = explicar(error_code)
    comp = analyze(code) if "for" in code else {}
    ctx = f"Error {error_code}: {exp.fix if exp else ''}. Complejidad {comp.get('estimado', '')}."
    return f"{SYSTEM}\n{ctx}\nPregunta: ¿Qué caso base asegura que tu recursión termina?"
