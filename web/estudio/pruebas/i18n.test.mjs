// INV-4213: textos de la interfaz (plantillas estilo str.format, idioma inicial).
import { test } from "node:test";
import assert from "node:assert/strict";
import { crearTraductor, idiomaInicial, interpolar, normalizar } from "../js/i18n.js";

test("interpolar rellena {nombre} y respeta {{ }} como en str.format", () => {
  assert.equal(interpolar("Paso {n} de {total}", { n: 2, total: 5 }), "Paso 2 de 5");
  assert.equal(interpolar("llaves {{x}} y {n}", { n: 1 }), "llaves {x} y 1");
  assert.equal(interpolar("sin {dato}", {}), "sin {dato}");
  assert.equal(interpolar("cero {n}", { n: 0 }), "cero 0");
});

test("normalizar reduce variantes regionales y rechaza idiomas no soportados", () => {
  assert.equal(normalizar("en-US"), "en");
  assert.equal(normalizar("ES_cr"), "es");
  assert.equal(normalizar("fr"), null);
  assert.equal(normalizar(undefined), null);
});

test("idiomaInicial: guardado, luego navegador, luego español", () => {
  assert.equal(idiomaInicial("en", ["es-ES"]), "en");
  assert.equal(idiomaInicial(null, ["fr-FR", "en-GB"]), "en");
  assert.equal(idiomaInicial("de", ["pt-BR"]), "es");
});

test("crearTraductor usa el idioma pedido y marca las claves que faltan", () => {
  const t = crearTraductor({ es: { hola: "Hola, {nombre}" }, en: { hola: "Hi, {nombre}" } }, "en");
  assert.equal(t("hola", { nombre: "Ana" }), "Hi, Ana");
  assert.equal(t("falta"), "[falta]");
  const t2 = crearTraductor({ es: { hola: "Hola" } }, "xx");
  assert.equal(t2("hola"), "Hola");
});
