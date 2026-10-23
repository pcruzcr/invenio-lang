// INV-4219: cliente del Worker de Pyodide (trabajador.js).
//
// Convierte el protocolo de mensajes en promesas `llamar(metodo, args)`,
// vigila un tiempo límite por petición y permite «Detener»: en ambos casos
// termina el Worker (la única forma de cortar un cálculo síncrono) y arranca
// otro limpio, rechazando lo pendiente con un motivo que la interfaz explica.
// `crearWorker` se inyecta para probar todo esto en Node con un Worker falso.

export class ErrorMotor extends Error {
  /** motivo: "tiempo" | "detenido" | "no_listo" | "peticion" | "interno" | "recursion" | "contrato" */
  constructor(motivo, detalle = "") {
    super(`${motivo}${detalle ? `: ${detalle}` : ""}`);
    this.motivo = motivo;
    this.detalle = detalle;
  }
}

export function crearMotor({
  pyodide,
  paquete,
  contrato,
  crearWorker,
  alCambiar = () => {},
  tiempoLimite = 30000,
  temporizador = globalThis,
}) {
  let worker = null;
  let estado = "cargando";
  let siguienteId = 1;
  let listo = null;
  const pendientes = new Map();

  function cambiar(nuevo, detalle) {
    estado = nuevo;
    alCambiar(nuevo, detalle);
  }

  function rechazarTodo(motivo) {
    for (const [, p] of pendientes) {
      temporizador.clearTimeout(p.reloj);
      p.rechazar(new ErrorMotor(motivo));
    }
    pendientes.clear();
  }

  function arrancar() {
    worker = crearWorker();
    cambiar("cargando");
    listo = new Promise((resolver) => {
      worker.onmessage = (evento) => {
        const m = evento.data;
        if (m.tipo === "listo") {
          if (contrato !== undefined && m.info.contrato !== contrato) {
            cambiar("error", `contrato ${m.info.contrato} ≠ ${contrato}`);
          } else {
            cambiar("listo");
          }
          resolver(estado === "listo");
        } else if (m.tipo === "fallo") {
          cambiar(m.motivo, m.detalle);
          resolver(false);
        } else if (m.tipo === "respuesta") {
          const p = pendientes.get(m.id);
          if (!p) {
            return; // respuesta de una petición ya cancelada
          }
          pendientes.delete(m.id);
          temporizador.clearTimeout(p.reloj);
          if (estado === "ocupado" && ![...pendientes.values()].some((q) => !q.fondo)) {
            cambiar("listo");
          }
          const r = JSON.parse(m.respuesta);
          if (r.ok) {
            p.resolver(r.datos);
          } else {
            p.rechazar(new ErrorMotor(r.error.tipo, r.error.mensaje));
          }
        }
      };
      worker.onerror = (e) => {
        cambiar("error", String(e && e.message ? e.message : e));
        rechazarTodo("interno");
        resolver(false);
      };
    });
    worker.postMessage({ tipo: "iniciar", pyodide, paquete });
    return listo;
  }

  /** Termina el Worker actual y arranca otro (cancela lo pendiente con `motivo`). */
  function reiniciar(motivo) {
    if (worker) {
      worker.terminate();
    }
    rechazarTodo(motivo);
    return arrancar();
  }

  /**
   * Llama a un método del puente. `fondo`: petición que el estudiante no
   * pidió (la revisión mientras escribe); no marca el motor como ocupado, para
   * que «Ejecutar» y «Detener» no parpadeen con cada pulsación.
   */
  async function llamar(metodo, args = {}, { limite = tiempoLimite, fondo = false } = {}) {
    if (!(await listo)) {
      throw new ErrorMotor("no_listo", estado);
    }
    const id = siguienteId++;
    return new Promise((resolver, rechazar) => {
      const reloj = temporizador.setTimeout(() => {
        if (pendientes.has(id)) {
          reiniciar("tiempo");
        }
      }, limite);
      pendientes.set(id, { resolver, rechazar, reloj, fondo });
      if (!fondo) {
        cambiar("ocupado");
      }
      worker.postMessage({ tipo: "llamar", id, peticion: JSON.stringify({ metodo, args }) });
    });
  }

  return {
    iniciar: arrancar,
    llamar,
    detener: () => reiniciar("detenido"),
    estado: () => estado,
  };
}
