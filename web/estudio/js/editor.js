// INV-4221: editor de código del estudio (textarea + capa resaltada).
//
// Por qué un <textarea> real bajo el resaltado y no un editor de terceros:
// el textarea es un control nativo que los lectores de pantalla, el
// corrector del sistema, el portapapeles, la entrada por voz y los métodos
// de entrada de idiomas asiáticos ya entienden; el color se pinta en un
// <pre aria-hidden> exactamente debajo. Sin dependencias ni compilación.
//
// Tabulador: inserta sangría, pero NO atrapa el foco (WCAG 2.1.2): Escape
// seguido de Tab sale del editor, como anuncia la ayuda del campo.

import { resaltarHTML } from "./resaltado.js";

const SANGRIA = "    ";

export function crearEditor({ texto, resaltado, numeros, marcas, alCambiar, alMoverCursor }) {
  let lexico = { palabras: {}, integradas: [] };
  let lineasConError = new Set();
  let salirConTab = false;

  function pintar() {
    resaltado.innerHTML = resaltarHTML(texto.value, lexico);
    const total = texto.value.split("\n").length;
    let html = "";
    for (let i = 1; i <= total; i++) {
      html += lineasConError.has(i) ? `<span class="con-error">${i}</span>\n` : `${i}\n`;
    }
    numeros.innerHTML = html;
    pintarMarcas();
    sincronizarDesplazamiento();
  }

  function altoLinea() {
    return parseFloat(getComputedStyle(texto).lineHeight) || 21;
  }

  function pintarMarcas() {
    const alto = altoLinea();
    const relleno = parseFloat(getComputedStyle(texto).paddingTop) || 0;
    marcas.replaceChildren(
      ...[...lineasConError].map((n) => {
        const d = document.createElement("div");
        d.className = "marca-linea";
        d.style.top = `${relleno + (n - 1) * alto - texto.scrollTop}px`;
        return d;
      }),
    );
  }

  function sincronizarDesplazamiento() {
    resaltado.scrollTop = texto.scrollTop;
    resaltado.scrollLeft = texto.scrollLeft;
    numeros.scrollTop = texto.scrollTop;
    pintarMarcas();
  }

  function posicion() {
    const antes = texto.value.slice(0, texto.selectionStart);
    const lineas = antes.split("\n");
    return { linea: lineas.length, columna: lineas[lineas.length - 1].length + 1 };
  }

  /**
   * Reemplaza el rango [ini, fin) por `nuevo` conservando el historial de
   * deshacer del navegador (execCommand es la única vía que lo conserva;
   * si no existe se usa setRangeText).
   */
  function reemplazar(ini, fin, nuevo, cursor = ini + nuevo.length) {
    texto.focus({ preventScroll: true });
    texto.setSelectionRange(ini, fin);
    let hecho = false;
    try {
      hecho = document.execCommand("insertText", false, nuevo);
    } catch {
      hecho = false;
    }
    if (!hecho) {
      texto.setRangeText(nuevo, ini, fin, "end");
      texto.dispatchEvent(new Event("input"));
    }
    texto.setSelectionRange(cursor, cursor);
  }

  function inicioDeLinea(pos) {
    return texto.value.lastIndexOf("\n", pos - 1) + 1;
  }

  function sangrar(quitar) {
    const v = texto.value;
    const ini = inicioDeLinea(texto.selectionStart);
    let fin = texto.selectionEnd;
    if (fin > ini && v[fin - 1] === "\n") {
      fin -= 1;
    }
    const bloque = v.slice(ini, fin);
    const lineas = bloque.split("\n");
    const nuevas = lineas.map((l) => (quitar ? l.replace(/^ {1,4}|^\t/, "") : SANGRIA + l));
    const nuevo = nuevas.join("\n");
    if (texto.selectionStart === texto.selectionEnd && !quitar) {
      reemplazar(texto.selectionStart, texto.selectionEnd, SANGRIA);
      return;
    }
    reemplazar(ini, fin, nuevo, ini + nuevo.length);
  }

  texto.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      salirConTab = true;
      return;
    }
    if (e.key === "Tab" && !e.ctrlKey && !e.altKey && !e.metaKey) {
      if (salirConTab) {
        salirConTab = false;
        return; // deja que el navegador mueva el foco
      }
      e.preventDefault();
      sangrar(e.shiftKey);
      return;
    }
    salirConTab = false;
    if (e.key === "Enter" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
      const v = texto.value;
      const ini = inicioDeLinea(texto.selectionStart);
      const linea = v.slice(ini, texto.selectionStart);
      let sangria = /^[ \t]*/.exec(linea)[0];
      if (/\{\s*$/.test(linea)) {
        sangria += SANGRIA;
      }
      e.preventDefault();
      reemplazar(texto.selectionStart, texto.selectionEnd, `\n${sangria}`);
    } else if (e.key === "}" && !e.ctrlKey && !e.metaKey) {
      const ini = inicioDeLinea(texto.selectionStart);
      const linea = texto.value.slice(ini, texto.selectionStart);
      if (/^ {4,}$/.test(linea) && texto.selectionStart === texto.selectionEnd) {
        e.preventDefault();
        reemplazar(texto.selectionStart - 4, texto.selectionStart, "}");
      }
    }
  });

  texto.addEventListener("input", () => {
    pintar();
    alCambiar(texto.value);
  });
  texto.addEventListener("scroll", sincronizarDesplazamiento);
  for (const ev of ["keyup", "click", "select", "focus"]) {
    texto.addEventListener(ev, () => alMoverCursor(posicion()));
  }

  return {
    valor: () => texto.value,
    /** Cambia todo el texto como una edición deshacible (Ctrl+Z la revierte). */
    reemplazarTodo(nuevo) {
      if (nuevo === texto.value) {
        return;
      }
      const cursor = Math.min(texto.selectionStart, nuevo.length);
      reemplazar(0, texto.value.length, nuevo, cursor);
    },
    /** Pone el texto sin historial (al abrir un archivo o arrancar). */
    establecer(nuevo) {
      texto.value = nuevo;
      texto.setSelectionRange(0, 0);
      texto.scrollTop = 0;
      pintar();
    },
    establecerLexico(nuevo) {
      lexico = nuevo;
      pintar();
    },
    marcarErrores(lineas) {
      lineasConError = new Set(lineas.filter((n) => n > 0));
      pintar();
    },
    /** Lleva el cursor a una línea y columna (desde 1) y enfoca el editor. */
    irA(linea, columna = 1) {
      const lineas = texto.value.split("\n");
      const n = Math.min(Math.max(linea, 1), lineas.length);
      let pos = 0;
      for (let i = 0; i < n - 1; i++) {
        pos += lineas[i].length + 1;
      }
      pos += Math.min(Math.max(columna - 1, 0), lineas[n - 1].length);
      texto.focus();
      texto.setSelectionRange(pos, pos);
      const alto = altoLinea();
      const objetivo = (n - 1) * alto;
      if (objetivo < texto.scrollTop || objetivo > texto.scrollTop + texto.clientHeight - alto * 2) {
        texto.scrollTop = Math.max(objetivo - texto.clientHeight / 3, 0);
      }
      alMoverCursor(posicion());
    },
    enfocar: () => texto.focus(),
    repintar: pintar,
  };
}
