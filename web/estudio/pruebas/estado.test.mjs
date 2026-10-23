// INV-4217: reductor puro del estado del estudio.
import { test } from "node:test";
import assert from "node:assert/strict";
import { crearTienda, estadoInicial, persistible, reducir } from "../js/estado.js";

test("estadoInicial acepta solo valores con la forma correcta", () => {
  const e = estadoInicial({ idioma: "fr", tema: "rosa", codigo: 5, pestana: "bloques", resueltos: ["N01-E01", 3], ejercicio: 9 });
  assert.equal(e.idioma, "es");
  assert.equal(e.tema, "sistema");
  assert.equal(e.codigo, "");
  assert.equal(e.pestana, "bloques");
  assert.deepEqual(e.resueltos, ["N01-E01"]);
  assert.equal(e.ejercicio, null);
  assert.equal(e.motor, "cargando");
});

test("editar marca modificado; abrir y guardar lo limpian", () => {
  let e = estadoInicial();
  e = reducir(e, { tipo: "codigo", codigo: "x" });
  assert.equal(e.modificado, true);
  assert.equal(reducir(e, { tipo: "codigo", codigo: "x" }), e, "mismo código: mismo objeto");
  e = reducir(e, { tipo: "guardado", nombre: "a.inv" });
  assert.equal(e.modificado, false);
  e = reducir(e, { tipo: "abrir", codigo: "y", nombre: "b.inv", ejercicio: "N01-E01", entrada: "3" });
  assert.deepEqual([e.codigo, e.nombre, e.ejercicio, e.entrada, e.resultado], ["y", "b.inv", "N01-E01", "3", null]);
});

test("valores inválidos se ignoran y acciones desconocidas fallan", () => {
  const e = estadoInicial();
  assert.equal(reducir(e, { tipo: "idioma", idioma: "xx" }), e);
  assert.equal(reducir(e, { tipo: "pestana", pestana: "nada" }), e);
  assert.equal(reducir(e, { tipo: "motor", estado: "raro" }), e);
  assert.throws(() => reducir(e, { tipo: "inventada" }));
});

test("resultado guarda salida, diagnósticos y si terminó bien", () => {
  const e = reducir(estadoInicial(), { tipo: "resultado", salida: "hola", diagnosticos: [{ linea: 1 }], ok: false });
  assert.deepEqual([e.salida, e.resultado, e.diagnosticos.length], ["hola", "error", 1]);
});

test("persistible no guarda resultados ni el estado del motor", () => {
  const p = persistible(reducir(estadoInicial(), { tipo: "motor", estado: "listo" }));
  assert.ok(!("motor" in p) && !("salida" in p) && !("diagnosticos" in p));
  assert.deepEqual(estadoInicial(p).motor, "cargando");
});

test("la tienda avisa solo cuando el estado cambia", () => {
  const tienda = crearTienda(estadoInicial());
  const vistos = [];
  const quitar = tienda.suscribir((e, previo) => vistos.push([previo.idioma, e.idioma]));
  tienda.despachar({ tipo: "idioma", idioma: "en" });
  tienda.despachar({ tipo: "idioma", idioma: "xx" });
  quitar();
  tienda.despachar({ tipo: "idioma", idioma: "es" });
  assert.deepEqual(vistos, [["es", "en"]]);
});
