# runner.py — Ejecuta curriculum con CompilerFacade (Facade pattern)
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from inveniolang.cli import CompilerFacade

def run_nivel(nivel: str):
    base = pathlib.Path(__file__).parent / nivel
    fac = CompilerFacade()
    ok = 0; total = 0
    for inv in sorted(base.glob("*.inv")):
        exp = inv.with_suffix(".expected")
        total += 1
        r = fac.execute(str(inv))
        salida = "".join(r.get("salida",[])) if r.get("ok") else "ERROR "+str(r.get("errores"))
        esperado = exp.read_text(encoding="utf-8").strip() if exp.exists() else ""
        if salida.strip()==esperado:
            print(f"OK {inv.name} -> {salida.strip()}")
            ok+=1
        else:
            print(f"FAIL {inv.name}: got '{salida.strip()}' exp '{esperado}'")
    print(f"{nivel}: {ok}/{total}")
    return ok==total

if __name__=="__main__":
    import sys
    nivel = sys.argv[1] if len(sys.argv)>1 else "nivel1"
    run_nivel(nivel)
