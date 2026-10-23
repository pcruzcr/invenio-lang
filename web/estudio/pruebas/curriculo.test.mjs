// INV-4216: currículo navegable con la misma comparación que curriculum/runner.py.
import { test } from "node:test";
import assert from "node:assert/strict";
import * as C from "../js/curriculo.js";

const CUR = {
  niveles: [
    { nivel: 1, titulo: "Fundamentos", ejercicios: [
      { id: "N01-E01", titulo: "Hola, mundo", enunciado: "Imprime dos líneas", conceptos: ["salida"] },
      { id: "N01-E02", titulo: "Variables", enunciado: "Intercambia", conceptos: ["asignación"] },
    ] },
    { nivel: 3, titulo: "Funciones y recursión", ejercicios: [
      { id: "N03-E01", titulo: "Función cuadrado", enunciado: "Devuelve", conceptos: ["función"] },
    ] },
  ],
};

test("comparar tolera \\r\\n y saltos finales, no espacios", () => {
  assert.deepEqual(C.comparar("a\r\nb\n\n", "a\nb"), { ok: true });
  assert.deepEqual(C.comparar("a\nb ", "a\nb"), { ok: false, linea: 2, obtenido: "b ", esperado: "b" });
  assert.deepEqual(C.comparar("a", "a\nb"), { ok: false, linea: 2, obtenido: "", esperado: "b" });
  assert.equal(C.primeraDiferencia("x\ny", "x\ny\nz"), 3);
});

test("filtrar sin tildes ni mayúsculas, por título, id, concepto o nivel", () => {
  assert.deepEqual(C.filtrar(CUR, "funcion").map((n) => n.nivel), [3]);
  assert.deepEqual(C.filtrar(CUR, "RECURSION").flatMap((n) => n.ejercicios.map((e) => e.id)), ["N03-E01"]);
  assert.deepEqual(C.filtrar(CUR, "n01-e02").flatMap((n) => n.ejercicios.map((e) => e.id)), ["N01-E02"]);
  assert.equal(C.filtrar(CUR, "  ").length, 2);
  assert.equal(C.filtrar(CUR, "zzz").length, 0);
});

test("buscar, vecino y plantilla", () => {
  assert.equal(C.buscarEjercicio(CUR, "N01-E02").nivel, 1);
  assert.equal(C.buscarEjercicio(CUR, "N99-E99"), null);
  assert.equal(C.vecino(CUR, "N01-E02", 1).id, "N03-E01");
  assert.equal(C.vecino(CUR, "N01-E01", -1), null);
  assert.match(C.plantilla("en"), /^void main\(\)/);
  assert.match(C.plantilla("es"), /^vacio main\(\)/);
});

test("marcarResuelto sin duplicados y tolerante a datos raros", () => {
  assert.deepEqual(C.marcarResuelto(["N02-E01", "N01-E01"], "N01-E01"), ["N01-E01", "N02-E01"]);
  assert.deepEqual(C.marcarResuelto("roto", "N01-E01"), ["N01-E01"]);
});
