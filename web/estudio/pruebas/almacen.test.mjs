// INV-4214: almacenamiento local que nunca rompe la página.
import { test } from "node:test";
import assert from "node:assert/strict";
import { MAX_PROGRAMAS, crearAlmacen, nombreSeguro } from "../js/almacen.js";

function memoria() {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
    m,
  };
}

test("lee y escribe JSON con prefijo propio", () => {
  const s = memoria();
  const a = crearAlmacen(s);
  assert.equal(a.escribir("estado", { x: 1 }), true);
  assert.deepEqual(a.leer("estado", null), { x: 1 });
  assert.ok([...s.m.keys()].every((k) => k.startsWith("inveniolang.estudio.v1.")));
  assert.equal(a.disponible(), true);
});

test("JSON corrupto o almacenamiento que lanza: valor por defecto, sin excepciones", () => {
  const s = memoria();
  s.setItem("inveniolang.estudio.v1.estado", "{roto");
  assert.deepEqual(crearAlmacen(s).leer("estado", { d: 1 }), { d: 1 });
  const hostil = {
    getItem() { throw new Error("SecurityError"); },
    setItem() { throw new Error("QuotaExceededError"); },
    removeItem() { throw new Error("SecurityError"); },
  };
  const a = crearAlmacen(hostil);
  assert.equal(a.leer("estado", 7), 7);
  assert.equal(a.escribir("estado", 1), false);
  assert.equal(a.disponible(), false);
  assert.deepEqual(a.programas(), []);
  assert.equal(a.guardarPrograma("x", "codigo").ok, false);
});

test("sin localStorage (null) todo responde con normalidad", () => {
  const a = crearAlmacen(null);
  assert.equal(a.leer("x", "d"), "d");
  assert.equal(a.escribir("x", 1), false);
  assert.equal(a.disponible(), false);
});

test("programas guardados: reemplazo por nombre, orden y límite", () => {
  const a = crearAlmacen(memoria());
  a.guardarPrograma("uno", "a", 1);
  a.guardarPrograma("dos.inv", "b", 2);
  const r = a.guardarPrograma("uno.inv", "c", 3);
  assert.equal(r.nombre, "uno.inv");
  assert.deepEqual(a.programas().map((p) => [p.nombre, p.codigo]), [["uno.inv", "c"], ["dos.inv", "b"]]);
  for (let i = 0; i < MAX_PROGRAMAS; i++) {
    a.guardarPrograma(`p${i}`, "x", 10 + i);
  }
  assert.equal(a.programas().length, MAX_PROGRAMAS);
  assert.equal(a.guardarPrograma("otro", "x", 999).lleno, true);
  assert.equal(a.borrarPrograma("otro.inv"), true);
  assert.ok(!a.programas().some((p) => p.nombre === "otro.inv"));
});

test("la lista ignora entradas con forma incorrecta", () => {
  const s = memoria();
  s.setItem("inveniolang.estudio.v1.programas", JSON.stringify([{ nombre: 1 }, { nombre: "a.inv", codigo: "x", fecha: 1 }, null]));
  assert.deepEqual(crearAlmacen(s).programas().map((p) => p.nombre), ["a.inv"]);
});

test("nombreSeguro quita rutas y caracteres peligrosos", () => {
  assert.equal(nombreSeguro("../../etc/passwd"), ".._.._etc_passwd.inv");
  assert.equal(nombreSeguro("  "), "programa.inv");
  assert.equal(nombreSeguro("pila.INV"), "pila.INV");
  assert.equal(nombreSeguro("a\u0000b"), "a_b.inv");
  assert.ok(nombreSeguro("x".repeat(200)).length <= 84);
});
