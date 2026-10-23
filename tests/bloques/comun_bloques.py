"""Utilidades compartidas por las pruebas del editor de bloques (INV-4000..INV-4012)."""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests" / "flujo"))

from comun import TODO  # noqa: E402, F401 - se reexporta a las pruebas de bloques

from inveniolang import bloques  # noqa: E402

CURRICULO = sorted((RAIZ / "curriculum").glob("*/*/*.inv"))

# Además de TODO: POO completa (interfaz, abstracta, herencia, genéricos,
# estáticos, padre), arreglos/matrices en todas sus formas, importar,
# funciones anónimas, coalescencia, ternaria, ?. y operadores de bits.
COMPLETO = """
constante entero N = 3;
entero[3] global = {1, 2, 3};

interfaz Figura {
    publico abstracto real area();
}

abstracta clase Base implementa Figura {
    privado texto nombre;
    publico estatico entero creadas = 0;
    publico constructor Base(texto n) {
        este.nombre = n;
        Base.creadas += 1;
    }
    publico abstracto real area();
    publico texto describir() {
        retornar este.nombre;
    }
}

clase Cuadrado hereda Base {
    privado real lado;
    publico constructor Cuadrado(real l) {
        padre("cuadrado");
        este.lado = l;
    }
    publico real area() {
        retornar este.lado * este.lado;
    }
    publico texto describir() {
        retornar "lado de " + padre.describir();
    }
}

clase Caja<T> {
    publico T valor;
    publico constructor Caja(T v) {
        este.valor = v;
    }
    publico T obtener() {
        retornar este.valor;
    }
}

clase Pila {
    publico entero[] datos;
    Pila(entero n) {
        este.datos = nuevo entero[n];
    }
}

vacio main() {
    Cuadrado c = nuevo Cuadrado(2.0);
    imprimir(c.area());
    imprimir(c.describir());
    Caja<entero> k = nuevo Caja<entero>(7);
    imprimir(k.obtener());
    entero m[2][2] = {{1, 2}, {3, 4}};
    real[2][3] z;
    entero v[N];
    v[0] = m[1][0] + global[2];
    imprimir(v[0]);
    entero q = 1;
    entero a = 6;
    entero b = 3;
    imprimir(a & b);
    imprimir(a | b ^ 1);
    imprimir(a << 2 >> 1);
    imprimir(~a);
    imprimir(-(-a));
    imprimir(a > b ? "mayor" : "menor");
    imprimir(!(a == b) && (a != 0 || b < 0));
    Pila pila = nuevo Pila(4);
    pila.datos[1] = 9;
    imprimir(pila.datos[1]);
    funcion(entero x) entero f = funcion(entero x) entero { si (x > 0) { retornar x * 2; } retornar 0; };
    imprimir(f(5) + q);
    Cuadrado otro = nulo;
    imprimir(otro?.describir() ?? "sin figura");
    logico listo = verdadero;
    entero t = a++;
    imprimir(t);
    imprimir(listo);
    a++;
    --b;
    a %= 4;
    imprimir(a);
    imprimir(b);
    imprimir(Base.creadas);
}
"""


def entrada_de(inv: Path) -> tuple[str, ...]:
    """Líneas del ``.entrada`` del ejercicio (vacío si no tiene)."""
    ruta = inv.with_suffix(".entrada")
    return tuple(ruta.read_text(encoding="utf-8").splitlines()) if ruta.exists() else ()


@cache
def bloques_de(inv: Path, idioma: str | None = None) -> bloques.ModeloBloques:
    """Bloques (en caché) de un archivo del currículo."""
    return bloques.bloques_desde_codigo(inv.read_text(encoding="utf-8"), idioma, ruta=inv.name)
