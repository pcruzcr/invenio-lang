"""Utilidades compartidas por las pruebas de diagramas de flujo (INV-3000..INV-3011)."""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang import flujo  # noqa: E402

CURRICULO = sorted((RAIZ / "curriculum").glob("*/*/*.inv"))

# Programa con TODAS las construcciones de control del lenguaje.
TODO = """
enumeracion Forma { Circulo(real r), Cuadrado(real lado) }

clase Contador {
    privado entero n;
    Contador(entero inicio) {
        este.n = inicio;
    }
    publico vacio sumar(entero k) {
        este.n = este.n + k;
    }
    publico entero valor() {
        retornar este.n;
    }
}

entero doble(entero x) {
    retornar x * 2;
}

vacio main() {
    entero n = 0;
    leer(n);
    Contador c = nuevo Contador(1);
    entero[3] datos = {4, 5, 6};
    para (entero i = 0; i < n; i++) {
        si (i % 2 == 0) {
            continuar;
        } sino {
            si (i > 7) {
                romper;
            } sino {
                c.sumar(i);
            }
        }
    }
    mientras (n > 0) {
        n--;
    }
    hacer {
        n = n + 1;
    } mientras (n < 2);
    para_cada (entero d : datos) {
        imprimir(d);
    }
    segun (n) {
        caso 1:
            imprimir("uno");
        caso 2:
            imprimir("dos");
            romper;
        por_defecto:
            imprimir("otro");
    }
    Forma f = nuevo Circulo(2.0);
    emparejar (f) {
        caso Circulo(r):
            imprimir(r);
        caso Cuadrado(lado):
            imprimir(lado);
    }
    intentar {
        imprimir(10 / n);
    } capturar (e) {
        imprimir(e.mensaje);
    }
    imprimir(doble(c.valor()));
}
"""


def entrada_de(inv: Path) -> tuple[str, ...]:
    """Líneas del ``.entrada`` del ejercicio (vacío si no tiene)."""
    ruta = inv.with_suffix(".entrada")
    return tuple(ruta.read_text(encoding="utf-8").splitlines()) if ruta.exists() else ()


@cache
def modelo_de(inv: Path, idioma: str | None = None) -> flujo.ModeloFlujo:
    """Modelo (en caché) de un archivo del currículo."""
    return flujo.modelo_desde_codigo(inv.read_text(encoding="utf-8"), idioma, ruta=inv.name)
