// INV-4219: cliente del Worker con tiempo límite, «Detener» y reinicio.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ErrorMotor, crearMotor } from "../js/motor.js";

/** Worker falso: responde lo que le diga `responder(peticion)`. */
function fabrica({ inicio = { tipo: "listo", info: { contrato: 1 } }, responder = () => ({ ok: true, datos: 1 }), silencioso = new Set() } = {}) {
  const creados = [];
  const crearWorker = () => {
    const w = {
      terminado: false,
      postMessage(m) {
        queueMicrotask(() => {
          if (w.terminado) {
            return;
          }
          if (m.tipo === "iniciar") {
            w.onmessage({ data: inicio });
          } else {
            const p = JSON.parse(m.peticion);
            if (!silencioso.has(p.metodo)) {
              w.onmessage({ data: { tipo: "respuesta", id: m.id, respuesta: JSON.stringify(responder(p)) } });
            }
          }
        });
      },
      terminate() {
        w.terminado = true;
      },
    };
    creados.push(w);
    return w;
  };
  return { crearWorker, creados };
}

/** Temporizador manual: los plazos solo vencen cuando la prueba lo dice. */
function reloj() {
  const pend = new Map();
  let n = 0;
  return {
    setTimeout: (f) => { pend.set(++n, f); return n; },
    clearTimeout: (id) => pend.delete(id),
    vencer() { for (const [id, f] of [...pend]) { pend.delete(id); f(); } },
  };
}

test("arranca, pasa a listo y resuelve llamadas", async () => {
  const estados = [];
  const { crearWorker } = fabrica({ responder: (p) => ({ ok: true, datos: { eco: p.args.x } }) });
  const m = crearMotor({ pyodide: "p/", paquete: "z", contrato: 1, crearWorker, alCambiar: (e) => estados.push(e) });
  await m.iniciar();
  assert.equal(m.estado(), "listo");
  assert.deepEqual(await m.llamar("eco", { x: 5 }), { eco: 5 });
  assert.deepEqual(estados, ["cargando", "listo", "ocupado", "listo"]);
});

test("las peticiones de fondo no marcan el motor como ocupado", async () => {
  const estados = [];
  const { crearWorker } = fabrica();
  const m = crearMotor({ pyodide: "p/", paquete: "z", crearWorker, alCambiar: (e) => estados.push(e) });
  await m.iniciar();
  await m.llamar("revisar", {}, { fondo: true });
  assert.deepEqual(estados, ["cargando", "listo"]);
});

test("un error del puente se rechaza con su motivo", async () => {
  const { crearWorker } = fabrica({ responder: () => ({ ok: false, error: { tipo: "peticion", mensaje: "mal" } }) });
  const m = crearMotor({ pyodide: "p/", paquete: "z", crearWorker });
  await m.iniciar();
  await assert.rejects(m.llamar("x"), (e) => e instanceof ErrorMotor && e.motivo === "peticion" && e.detalle === "mal");
});

test("contrato distinto o fallo de carga dejan el motor sin usar", async () => {
  const a = crearMotor({ pyodide: "p/", paquete: "z", contrato: 2, crearWorker: fabrica().crearWorker });
  await a.iniciar();
  assert.equal(a.estado(), "error");
  await assert.rejects(a.llamar("x"), (e) => e.motivo === "no_listo");
  const b = crearMotor({ pyodide: "p/", paquete: "z", crearWorker: fabrica({ inicio: { tipo: "fallo", motivo: "sin_red", detalle: "" } }).crearWorker });
  await b.iniciar();
  assert.equal(b.estado(), "sin_red");
});

test("el tiempo límite termina el Worker, rechaza y arranca otro", async () => {
  const r = reloj();
  const f = fabrica({ silencioso: new Set(["colgado"]) });
  const m = crearMotor({ pyodide: "p/", paquete: "z", crearWorker: f.crearWorker, temporizador: r });
  await m.iniciar();
  const promesa = m.llamar("colgado");
  await new Promise((res) => setImmediate(res));
  r.vencer();
  await assert.rejects(promesa, (e) => e.motivo === "tiempo");
  assert.equal(f.creados.length, 2);
  assert.ok(f.creados[0].terminado);
  await new Promise((res) => setImmediate(res));
  assert.equal(m.estado(), "listo");
  assert.equal(await m.llamar("otra"), 1);
});

test("detener cancela lo pendiente con motivo «detenido»", async () => {
  const f = fabrica({ silencioso: new Set(["largo"]) });
  const m = crearMotor({ pyodide: "p/", paquete: "z", crearWorker: f.crearWorker, temporizador: reloj() });
  await m.iniciar();
  const promesa = m.llamar("largo");
  await new Promise((res) => setImmediate(res));
  m.detener();
  await assert.rejects(promesa, (e) => e.motivo === "detenido");
  assert.ok(f.creados[0].terminado);
});
