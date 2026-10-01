# types/gradual.py — v8 gradual typing dynamic 100% — all-in-one para C/Python/Java/C#/Pascal
from __future__ import annotations

Dynamic = "dynamic"


def is_dynamic(t: str) -> bool:
    """Indica si es dinámico."""
    return t == Dynamic or t is None or t == "?"


def consistent(a: str, b: str) -> bool:
    """Indica consistencia de tipos."""
    if a == b:
        return True
    if is_dynamic(a) or is_dynamic(b):
        return True
    # POO: subclase consistente con superclase
    # Para v10, usa symbol_table.es_subtipo_clase si disponible
    try:
        from ..symbol_table import SymbolTable

        st = SymbolTable()
        if st.es_clase(a) and st.es_clase(b):
            return st.es_subtipo_clase(a, b) or st.es_subtipo_clase(b, a)
    except Exception:  # noqa: S110 - sin tabla, se sigue con reglas sintácticas
        pass
    if a.endswith("[]") and b.endswith("[]"):
        return consistent(a[:-2], b[:-2])
    if {a, b} == {"int", "float"} or {a, b} == {"entero", "real"}:
        return True
    return False


def join(a: str, b: str) -> str:
    """Une dos tipos."""
    if a == b:
        return a
    if is_dynamic(a):
        return b
    if is_dynamic(b):
        return a
    if {a, b} == {"int", "float"} or {a, b} == {"entero", "real"}:
        return "float"
    if a.endswith("[]") and b.endswith("[]"):
        j = join(a[:-2], b[:-2])
        return j + "[]" if j != "dynamic" else "dynamic"
    # Para clases, el join es el ancestro común más cercano
    try:
        from ..symbol_table import SymbolTable

        st = SymbolTable()
        if st.es_clase(a) and st.es_clase(b):
            # ancestro común
            ca = set(st.cadena_ancestros(a) or [])
            cb = set(st.cadena_ancestros(b) or [])
            common = ca & cb
            if common:
                # el más específico (más cercano a a/b)
                for anc in st.cadena_ancestros(a) or []:
                    if anc in common:
                        return anc
    except Exception:  # noqa: S110 - fallback a dynamic si falla la jerarquía
        pass
    return "dynamic"


def meet(a: str, b: str) -> str:
    """Calcula el encuentro de tipos."""
    if a == b:
        return a
    if is_dynamic(a):
        return b
    if is_dynamic(b):
        return a
    return "dynamic"  # para gradual, meet de int y float es dynamic si no hay relación


def check_call(func_t: str, args: list) -> bool:
    """Verifica la llamada."""
    # func_t como "funcion(int,string)->bool"
    if not func_t.startswith("funcion("):
        return True
    inner = func_t[len("funcion(") :].split(")->")
    if len(inner) != 2:
        return True
    params = inner[0].rstrip(")").split(",") if inner[0].rstrip(")") else []
    if len(params) != len(args):
        return False
    return all(consistent(p.strip(), a) for p, a in zip(params, args, strict=True))
