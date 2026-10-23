// INV-4230: Pyodide SIMULADO para la prueba de humo del estudio.
//
// Implementa solo lo que usa web/estudio/js/trabajador.js (loadPyodide,
// unpackArchive y runPython devolviendo la función `llamar`), pero cada
// llamada se reenvía al servidor de la prueba, que ejecuta el puente REAL
// (inveniolang.web.puente.llamar) en CPython. Así la prueba ejercita toda la
// página, el Worker, el protocolo y el compilador sin descargar Pyodide.
export async function loadPyodide() {
  return {
    unpackArchive() {},
    runPython() {
      return (peticion) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/__puente", false); // síncrono, como una llamada a Python
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(peticion);
        return xhr.responseText;
      };
    },
  };
}
