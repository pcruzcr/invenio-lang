// INV-4218: Web Worker que ejecuta InvenioLang dentro de Pyodide.
//
// Por qué en un Worker: el intérprete corre de forma síncrona; en el hilo
// principal un ciclo largo congelaría la página (y con ella el lector de
// pantalla y el botón «Detener»). Aquí la página sigue respondiendo y, si
// algo se cuelga, motor.js termina este Worker y arranca otro.
//
// Protocolo (solo datos clonables):
//   ← {tipo: "iniciar", pyodide: URL base de Pyodide, paquete: URL del zip}
//   → {tipo: "listo", info} | {tipo: "fallo", motivo: "sin_red"|"sin_paquete"|"error", detalle}
//   ← {tipo: "llamar", id, peticion: JSON}
//   → {tipo: "respuesta", id, respuesta: JSON}

let llamar = null;

async function iniciar({ pyodide, paquete }) {
  let modulo;
  try {
    modulo = await import(`${pyodide}pyodide.mjs`);
  } catch (e) {
    return { tipo: "fallo", motivo: "sin_red", detalle: String(e) };
  }
  let zip;
  try {
    const r = await fetch(paquete);
    if (!r.ok) {
      return { tipo: "fallo", motivo: "sin_paquete", detalle: `HTTP ${r.status}` };
    }
    zip = new Uint8Array(await r.arrayBuffer());
  } catch (e) {
    return { tipo: "fallo", motivo: "sin_paquete", detalle: String(e) };
  }
  try {
    // PLY avisa por stderr al generar sus tablas; no es un error del
    // estudiante y no debe llenar la consola.
    const py = await modulo.loadPyodide({ indexURL: pyodide, stdout: () => {}, stderr: () => {} });
    py.unpackArchive(zip, "zip", { extractDir: "/inveniolang_web" });
    llamar = py.runPython(
      "import sys\nsys.path.insert(0, '/inveniolang_web')\nfrom inveniolang.web import llamar\nllamar",
    );
    const info = JSON.parse(llamar(JSON.stringify({ metodo: "info", args: {} }))).datos;
    // Construye las tablas LALR ahora y no en la primera ejecución del estudiante.
    llamar(JSON.stringify({ metodo: "revisar", args: { codigo: "vacio main() { }" } }));
    return { tipo: "listo", info };
  } catch (e) {
    const texto = String(e);
    const motivo = /fetch|network|Failed to load|NetworkError/i.test(texto) ? "sin_red" : "error";
    return { tipo: "fallo", motivo, detalle: texto };
  }
}

self.onmessage = async (evento) => {
  const m = evento.data;
  if (m.tipo === "iniciar") {
    self.postMessage(await iniciar(m));
  } else if (m.tipo === "llamar") {
    let respuesta;
    if (llamar === null) {
      respuesta = JSON.stringify({ ok: false, error: { tipo: "no_listo", mensaje: "" } });
    } else {
      respuesta = llamar(m.peticion);
    }
    self.postMessage({ tipo: "respuesta", id: m.id, respuesta });
  }
};
