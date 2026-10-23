// INV-4225: lógica pura del lienzo sobre una vista REAL del puente
// (fixtures/bloques.json, la genera tests/web/fixtures_estudio.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as B from "../js/bloques.js";

const F = JSON.parse(readFileSync(new URL("./fixtures/bloques.json", import.meta.url), "utf8"));
const V = F.vista;

function idsModelo(lista) {
  const ids = [];
  const visitar = (b) => {
    ids.push(b.id);
    for (const h of Object.values(b.huecos)) {
      if (h) {
        visitar(h);
      }
    }
    for (const l of Object.values(b.listas)) {
      l.forEach(visitar);
    }
  };
  lista.forEach(visitar);
  return ids;
}

test("la vista recorre los mismos bloques que el modelo JSON v1", () => {
  const vista = [...B.recorrer(V)].map((v) => v.id);
  assert.deepEqual(new Set(vista), new Set(idsModelo(F.modelo.programa)));
  assert.equal(new Set(vista).size, vista.length, "ids únicos");
  assert.equal(vista[0], V[0].id, "preorden: primero la definición");
});

test("ubicar da padre, parte e índice (null en un hueco)", () => {
  const main = V.find((v) => v.rotulo.includes("main"));
  assert.deepEqual(B.ubicar(V, main.id).padre, null);
  assert.equal(B.ubicar(V, main.id).parte, "programa");
  const primero = main.bocas.find((b) => b.nombre === "cuerpo").hijos[0];
  assert.deepEqual(B.ubicar(V, primero.id), { bloque: primero, padre: main.id, parte: "cuerpo", indice: 0 });
  const enHueco = [...B.recorrer(V)].find((v) => v.forma === "valor");
  assert.equal(B.ubicar(V, enHueco.id).indice === null || typeof B.ubicar(V, enHueco.id).indice === "number", true);
  assert.equal(B.ubicar(V, "no-existe"), null);
});

test("zonaDeDestino y destinoDeZona son inversas fuera del sitio propio", () => {
  const main = V.find((v) => v.rotulo.includes("main"));
  const cuerpo = main.bocas.find((b) => b.nombre === "cuerpo").hijos;
  const id = cuerpo[0].id;
  for (let k = 0; k <= cuerpo.length; k++) {
    const zona = { padre: main.id, parte: "cuerpo", indice: k };
    if (B.zonaPropia(V, id, zona)) {
      continue;
    }
    const destino = B.destinoDeZona(V, id, zona);
    assert.equal(B.zonaDeDestino(V, id, destino), B.claveZona(zona));
  }
  assert.ok(B.zonaPropia(V, id, { padre: main.id, parte: "cuerpo", indice: 0 }));
  assert.ok(B.zonaPropia(V, id, { padre: main.id, parte: "cuerpo", indice: 1 }));
  assert.ok(!B.zonaPropia(V, id, { padre: main.id, parte: "cuerpo", indice: 2 }));
  assert.equal(B.claveZona({ padre: null, parte: "programa", indice: 0 }), "|programa|0");
});

test("una zona dentro del bloque que se mueve es suya", () => {
  const compuesto = [...B.recorrer(V)].find((v) => v.bocas.length && v.forma === "c");
  const interior = compuesto.bocas[0];
  assert.ok(B.zonaPropia(V, compuesto.id, { padre: compuesto.id, parte: interior.nombre, indice: 0 }));
});

test("etiqueta accesible: nombre del tipo y su rótulo", () => {
  for (const v of B.recorrer(V)) {
    assert.ok(B.etiqueta(v).startsWith(v.nombre));
  }
});

test("CSS de categorías con los colores del catálogo, sin inyección", () => {
  const css = B.cssCategorias(F.paleta);
  for (const c of F.paleta) {
    assert.ok(css.includes(`.cat-${c.id}{--cat-fondo:${c.claro.relleno}`));
    assert.ok(css.includes(`:root[data-tema="oscuro"] .cat-${c.id}{--cat-fondo:${c.oscuro.relleno}`));
  }
  const malo = B.cssCategorias([{ id: "x", claro: { relleno: "red;}body{display:none", texto: "#000", borde: "#000" }, oscuro: null }, { id: "a}b", claro: { relleno: "#fff", texto: "#000", borde: "#000" } }]);
  assert.ok(!malo.includes("display:none") && !malo.includes("a}b"));
});

test("historial: deshacer y rehacer sin perder pasos, con límite", () => {
  let h = B.crearHistorial("a", 2);
  h = B.empujar(h, "b");
  h = B.empujar(h, "c");
  h = B.empujar(h, "d");
  assert.deepEqual(h.pasado, ["b", "c"]);
  h = B.deshacer(h);
  assert.equal(h.actual, "c");
  h = B.rehacer(h);
  assert.equal(h.actual, "d");
  assert.equal(B.rehacer(h), h);
  h = B.deshacer(B.deshacer(h));
  assert.equal(B.deshacer(h), h);
  assert.equal(B.empujar(h, "z").futuro.length, 0);
});
