"""INV-5005: el detector de plagio no borra el programa a partir del primer ``//``.

``normalizar`` usaba ``//.*`` con ``re.S``: el punto cruzaba saltos de línea,
así que una entrega con un comentario quedaba vacía y toda similitud era 0.
Como todo el currículo lleva comentarios, el detector no detectaba nada.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from inveniolang.plagiarism.cluster import cluster, normalizar, plagiarism_score  # noqa: E402

ORIGINAL = """// Suma de un arreglo
vacio main() {
    entero [3] datos = {1, 2, 3}; /* datos de prueba,
                                     en dos líneas */
    entero suma = 0;
    para (entero i = 0; i < 3; i++) {
        suma = suma + datos[i];   // acumula
    }
    imprimir("total: //no es comentario ");
    imprimir(suma);
}
"""

# Misma solución: otros nombres, otros tipos (inglés) y otros comentarios.
COPIA = """// Mi solución propia, lo juro
vacio main() {
    int [3] valores = {1, 2, 3};
    int acumulado = 0;
    para (int k = 0; k < 3; k++) {
        acumulado = acumulado + valores[k];
    }
    imprimir("total: //no es comentario ");
    imprimir(acumulado);
}
"""

DISTINTO = """vacio main() {
    entero n = 10;
    mientras (n > 0) {
        si (n % 2 == 0) { imprimir(n); }
        n--;
    }
}
"""


def test_los_comentarios_se_quitan_sin_borrar_el_resto():
    s = normalizar(ORIGINAL)
    assert "main" not in s  # identificadores normalizados
    assert s.count("X") > 10, s  # el cuerpo sigue ahí
    assert "acumula" not in s and "prueba" not in s


def test_un_literal_con_barras_no_es_un_comentario():
    assert "//" in normalizar('vacio main() { imprimir("a // b"); }')


def test_copia_con_comentarios_distintos_se_detecta():
    assert plagiarism_score(ORIGINAL, COPIA) >= 0.95
    assert plagiarism_score(ORIGINAL, DISTINTO) < 0.7


def test_cluster_agrupa_la_copia_y_deja_fuera_lo_distinto():
    assert cluster([ORIGINAL, DISTINTO, COPIA]) == [{0, 2}]


def test_el_curriculo_con_comentarios_ya_no_queda_vacio():
    burbuja = (RAIZ / "curriculum" / "es" / "nivel05" / "01_burbuja.inv").read_text(
        encoding="utf-8"
    )
    assert "//" in burbuja
    assert len(normalizar(burbuja)) > 100
