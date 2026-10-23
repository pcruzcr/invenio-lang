// INV-4226: lienzo de bloques del estudio (arrastrar y soltar + teclado).
//
// Dibuja la VISTA que entrega el puente (inveniolang/web/bloques_web.py,
// sobre el contrato de inveniolang/bloques) como un árbol ARIA y convierte
// cada gesto en una operación del puente («bloques_operar»): Python decide
// si encaja (con el mismo motivo bilingüe que la GUI Qt), devuelve el modelo
// nuevo, sus problemas y, si no hay ninguno, el código para el editor.
//
// Todo lo que se hace con el puntero se puede hacer con el teclado (WCAG
// 2.1.1, 2.5.7):
//   ↑ ↓            bloque anterior / siguiente en orden de lectura
//   ← →            bloque padre / primer bloque interior
//   Intro o F2     editar los campos del bloque (Intro guarda, Esc cancela)
//   Espacio o M    recoger el bloque; las flechas eligen entre los destinos
//                  VÁLIDOS (los mismos sitios que con el ratón); Intro suelta
//   Supr           eliminar      Ctrl+D  duplicar      Insert  ir a la paleta
//   Ctrl+Z/Ctrl+Y  deshacer/rehacer
//   Paleta: Intro  elegir con las flechas dónde insertar el bloque nuevo
// Cada destino y cada cambio se anuncian en una región aria-live.

import * as B from "./bloques.js";
import { escaparHTML as e } from "./resaltado.js";

const UMBRAL_ARRASTRE = 5;
const ZOOMS = [0.6, 0.75, 0.9, 1, 1.15, 1.3, 1.5];
const PILA = new Set(["instruccion", "c", "definicion", "miembro", "parte"]);

export function crearVistaBloques({ el, t, anunciar, puente, alCodigo }) {
  let historial = null; // de modelos (dict JSON v1)
  let vista = [];
  let problemas = new Map();
  let foco = null;
  let modo = null; // {origen, nombre, destinos, k}
  let zoom = 3;
  let arrastre = null;
  let editando = null;
  let ocupado = false;

  const modelo = () => (historial ? historial.actual : null);

  function estado(mensaje, tipo = "info") {
    el.estado.textContent = mensaje;
    el.estado.dataset.tipo = tipo;
  }

  function avisar(mensaje, urgente = false) {
    estado(mensaje, urgente ? "error" : "info");
    anunciar(mensaje, urgente);
  }

  // ------------------------------------------------------------ operaciones

  /** Aplica una respuesta con estado nuevo: historial, dibujo, código y anuncio. */
  function aplicar(r, anuncio, { empujar = true, sincronizar = true } = {}) {
    if (empujar) {
      historial = B.empujar(historial, r.modelo);
    }
    vista = r.vista;
    problemas = new Map();
    for (const p of r.problemas) {
      if (p.bloque) {
        problemas.set(p.bloque, [...(problemas.get(p.bloque) || []), p.mensaje]);
      }
    }
    dibujar();
    pintarProblemas(r.problemas);
    // Al cargar desde el código no se reescribe el editor: se perderían sus
    // comentarios y su formato; solo un cambio hecho en los bloques lo reescribe.
    if (sincronizar && r.codigo !== null) {
      alCodigo(r.codigo);
    }
    const resumen = r.problemas.length ? t("bloques.con_problemas", { n: r.problemas.length }) : t("bloques.sincronizado");
    const texto = anuncio ? `${anuncio} ${resumen}` : resumen;
    estado(texto, r.problemas.length ? "error" : "info");
    if (anuncio) {
      anunciar(texto);
    }
  }

  async function operar(op, args, anuncio, enfocarDespues) {
    if (ocupado || !modelo()) {
      return false;
    }
    ocupado = true;
    const antes = new Set([...B.recorrer(vista)].map((v) => v.id));
    try {
      const r = await puente("bloques_operar", { modelo: modelo(), op, ...args });
      if (!r) {
        return false;
      }
      if (!r.ok) {
        avisar(r.motivo, true);
        dibujar();
        return false;
      }
      aplicar(r, anuncio);
      let destino = enfocarDespues;
      if (destino === "nuevo") {
        destino = [...B.recorrer(vista)].map((v) => v.id).find((id) => !antes.has(id)) ?? null;
      }
      if (destino) {
        enfocar(destino);
      }
      return true;
    } finally {
      ocupado = false;
    }
  }

  function nombreDe(id) {
    const u = B.ubicar(vista, id);
    return u ? u.bloque.nombre : "";
  }

  function nombrePaleta(clave) {
    for (const nodo of el.paleta.querySelectorAll(".pieza")) {
      if (nodo.dataset.clave === clave) {
        return nodo.dataset.nombre;
      }
    }
    return clave;
  }

  function eliminar(id) {
    const items = navegables();
    const k = items.findIndex((x) => x.dataset.id === id);
    const u = B.ubicar(vista, id);
    const dentro = new Set(u ? [...B.recorrer([u.bloque])].map((b) => b.id) : [id]);
    const vecino = items.slice(k + 1).find((x) => !dentro.has(x.dataset.id)) || items[k - 1];
    operar("eliminar", { id }, t("bloques.anuncio.eliminado", { tipo: nombreDe(id) }), vecino ? vecino.dataset.id : null);
  }

  function duplicar(id) {
    operar("duplicar", { id }, t("bloques.anuncio.duplicado", { tipo: nombreDe(id) }), "nuevo");
  }

  async function envolverEn(tipo, nombre) {
    const id = foco;
    if (!id || !B.ubicar(vista, id)) {
      avisar(t("bloques.error.sin_seleccion"), true);
      return;
    }
    await operar("envolver", { ids: [id], tipo }, t("bloques.anuncio.envuelto", { tipo: nombre }), id);
  }

  // ------------------------------------------------------------ dibujo

  function campoHTML(p, idBloque) {
    const texto = p.clase === "bandera" ? `${p.valor ? "☑" : "☐"} ${p.etiqueta}` : p.texto || "…";
    const leido = p.clase === "bandera" ? t(p.valor ? "bloques.si" : "bloques.no") : p.texto || "…";
    return `<button type="button" class="campo" tabindex="-1" data-campo="${e(p.nombre)}" data-bloque="${e(idBloque)}" aria-label="${e(t("bloques.editar_campo", { campo: p.etiqueta, valor: leido }))}">${e(texto)}</button>`;
  }

  function zonaAttrs(padre, parte, indice) {
    return `data-padre="${e(padre ?? "")}" data-parte="${e(parte)}"${indice === null ? "" : ` data-indice="${indice}"`}`;
  }

  function cabeceraHTML(v) {
    return v.cabecera
      .map((p) => {
        if (p.t === "texto") {
          return `<span class="pt">${e(p.texto)}</span>`;
        }
        if (p.t === "campo") {
          return campoHTML(p, v.id);
        }
        if (p.t === "hueco") {
          const dentro = p.hijo
            ? bloqueHTML(p.hijo, true)
            : `<span class="sr-only">${e(t("bloques.hueco_vacio", { hueco: p.etiqueta }))}</span>`;
          return `<span role="group" class="zona zona-hueco${p.hijo ? "" : " vacia"}" ${zonaAttrs(v.id, p.nombre, null)} aria-label="${e(p.etiqueta)}" title="${e(p.etiqueta)}">${dentro}</span>`;
        }
        // lista en línea (argumentos, parámetros, valores)
        let html = `<span role="group" class="lista-linea" aria-label="${e(p.etiqueta)}">`;
        p.hijos.forEach((h, k) => {
          html += `<span class="zona zona-linea" ${zonaAttrs(v.id, p.nombre, k)}></span>`;
          html += bloqueHTML(h, true);
          if (k < p.hijos.length - 1) {
            html += `<span class="pt">,</span>`;
          }
        });
        html += `<span class="zona zona-linea zona-mas" ${zonaAttrs(v.id, p.nombre, p.hijos.length)} title="${e(t("bloques.agregar_a", { lista: p.etiqueta }))}" aria-hidden="true">+</span></span>`;
        return html;
      })
      .join("");
  }

  function pilaHTML(padre, parte, hijos, etiqueta) {
    let html = `<ul role="group" class="pila" aria-label="${e(etiqueta)}">`;
    hijos.forEach((h, k) => {
      html += `<li role="none" class="zona zona-pila" ${zonaAttrs(padre, parte, k)}></li>`;
      html += bloqueHTML(h, false);
    });
    return `${html}<li role="none" class="zona zona-pila final" ${zonaAttrs(padre, parte, hijos.length)}></li></ul>`;
  }

  function bloqueHTML(v, enLinea) {
    const msgs = problemas.get(v.id) || [];
    const etiq = B.etiqueta(v);
    const etiquetaAria = msgs.length ? `${etiq}. ${t("bloques.tiene_problema")}: ${msgs.join(". ")}` : etiq;
    const tag = enLinea ? "span" : "li";
    const clases = ["bloque", `forma-${v.forma}`, `cat-${v.categoria}`];
    if (v.salida === "logico") {
      clases.push("valor-logico");
    }
    if (msgs.length) {
      clases.push("con-problema");
    }
    let html = `<${tag} role="treeitem" class="${clases.join(" ")}" id="bq-${e(v.id)}" data-id="${e(v.id)}" tabindex="-1" aria-label="${e(etiquetaAria)}"><span class="cabecera">`;
    if (PILA.has(v.forma)) {
      html += `<span class="asa" aria-hidden="true">⠿</span>`;
    }
    html += cabeceraHTML(v);
    if (msgs.length) {
      html += `<span class="marca-problema" aria-hidden="true" title="${e(msgs.join("\n"))}">⚠</span>`;
    }
    if (!enLinea) {
      const dup = e(t("bloques.accion.duplicar"));
      const eli = e(t("bloques.accion.eliminar"));
      html += `<span class="acciones-bloque"><button type="button" class="boton boton-texto" tabindex="-1" data-accion="duplicar" aria-label="${dup}" title="${dup}">⧉</button><button type="button" class="boton boton-texto" tabindex="-1" data-accion="eliminar" aria-label="${eli}" title="${eli}">✕</button></span>`;
    }
    html += `</span>`;
    for (const b of v.bocas) {
      html += `<span class="boca">`;
      if (b.rotulo) {
        html += `<span class="boca-rotulo">${e(b.rotulo)}</span>`;
      }
      html += `${pilaHTML(v.id, b.nombre, b.hijos, b.rotulo || b.etiqueta)}</span>`;
    }
    if (v.bocas.length) {
      html += `<span class="brazo" aria-hidden="true"></span>`;
    }
    return `${html}</${tag}>`;
  }

  function dibujar() {
    if (!historial) {
      el.arbol.innerHTML = "";
      el.deshacer.disabled = true;
      el.rehacer.disabled = true;
      return;
    }
    let html = "";
    vista.forEach((v, k) => {
      html += `<li role="none" class="zona zona-pila zona-programa" ${zonaAttrs(null, "programa", k)}></li>`;
      html += bloqueHTML(v, false);
    });
    html += `<li role="none" class="zona zona-pila zona-programa final" ${zonaAttrs(null, "programa", vista.length)}></li>`;
    el.arbol.innerHTML = html;
    el.arbol.style.zoom = String(ZOOMS[zoom]);
    el.zoom.textContent = `${Math.round(ZOOMS[zoom] * 100)} %`;
    const items = navegables();
    const actual = items.find((x) => x.dataset.id === foco) || items[0];
    if (actual) {
      actual.tabIndex = 0;
      foco = actual.dataset.id;
    }
    el.deshacer.disabled = !historial.pasado.length;
    el.rehacer.disabled = !historial.futuro.length;
  }

  function pintarProblemas(lista) {
    el.problemas.replaceChildren(
      ...lista.map((p) => {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = p.mensaje;
        if (p.bloque && B.ubicar(vista, p.bloque)) {
          b.addEventListener("click", () => enfocar(p.bloque));
        } else {
          b.disabled = true;
        }
        li.append(b);
        return li;
      }),
    );
  }

  function dibujarPaleta(paleta) {
    el.estilos.textContent = B.cssCategorias(paleta);
    el.paleta.innerHTML = paleta
      .map((c) => {
        const piezas = c.entradas
          .map(
            (x) =>
              `<li><button type="button" class="pieza forma-${e(x.forma)} cat-${e(c.id)}" data-clave="${e(x.clave)}" data-nombre="${e(x.nombre)}" aria-label="${e(t("bloques.paleta_insertar", { tipo: x.nombre }))}"><span class="icono-cat" aria-hidden="true">${e(c.icono)}</span><span aria-hidden="true">${e(x.muestra)}</span></button></li>`,
          )
          .join("");
        return `<section class="cat-${e(c.id)}"><h3><span class="icono-cat" aria-hidden="true">${e(c.icono)}</span>${e(c.nombre)}</h3><ul>${piezas}</ul></section>`;
      })
      .join("");
  }

  // ------------------------------------------------------------ foco y teclado

  /**
   * Lleva a la vista la cabecera de un bloque o una zona. Un bloque «c» puede
   * ser más ancho que el lienzo: se alinea su inicio, no su centro, para que el
   * estudiante vea siempre dónde empieza.
   */
  function asegurarVisible(nodo) {
    const objetivo = nodo.querySelector?.(":scope > .cabecera") || nodo;
    const r = objetivo.getBoundingClientRect();
    const l = el.lienzo.getBoundingClientRect();
    if (r.top < l.top + 8 || r.bottom > l.bottom - 8) {
      el.lienzo.scrollTop += r.top - l.top - l.height / 3;
    }
    if (r.left < l.left + 8 || r.left > l.right - 48) {
      el.lienzo.scrollLeft += r.left - l.left - 16;
    }
  }

  function navegables() {
    return [...el.arbol.querySelectorAll('[role="treeitem"]')];
  }

  function enfocar(id) {
    const items = navegables();
    const nodo = items.find((x) => x.dataset.id === id);
    if (!nodo) {
      return;
    }
    for (const x of items) {
      x.tabIndex = x === nodo ? 0 : -1;
    }
    foco = id;
    nodo.focus({ preventScroll: true });
    asegurarVisible(nodo);
  }

  function navegar(tecla, actual) {
    const items = navegables();
    const k = items.indexOf(actual);
    const destinos = {
      ArrowDown: () => items[k + 1],
      ArrowUp: () => items[k - 1],
      Home: () => items[0],
      End: () => items[items.length - 1],
      ArrowLeft: () => actual.parentElement.closest('[role="treeitem"]'),
      ArrowRight: () => actual.querySelector('[role="treeitem"]'),
    };
    if (!(tecla in destinos)) {
      return false;
    }
    const destino = destinos[tecla]();
    if (destino) {
      enfocar(destino.dataset.id);
    }
    return true;
  }

  // ---- edición de campos

  function editar(id, campoInicial = null) {
    const nodo = el.arbol.querySelector(`[data-id="${CSS.escape(id)}"]`);
    const u = B.ubicar(vista, id);
    if (!nodo || !u) {
      return;
    }
    const botones = [...nodo.querySelectorAll(":scope > .cabecera > .campo")];
    if (!botones.length) {
      avisar(t("bloques.sin_campos"));
      return;
    }
    const piezas = new Map(u.bloque.cabecera.filter((p) => p.t === "campo").map((p) => [p.nombre, p]));
    editando = { id, controles: [] };
    for (const boton of botones) {
      const p = piezas.get(boton.dataset.campo);
      let control;
      if (p.clase === "bandera") {
        control = document.createElement("input");
        control.type = "checkbox";
        control.checked = Boolean(p.valor);
      } else if (p.clase === "opcion") {
        control = document.createElement("select");
        for (const o of p.opciones) {
          control.append(new Option(o.texto, o.valor, false, o.valor === p.valor));
        }
      } else {
        control = document.createElement("input");
        control.type = "text";
        control.spellcheck = false;
        control.value = String(p.valor);
        control.size = Math.max(String(p.valor).length + 2, 6);
        control.addEventListener("input", () => {
          control.size = Math.max(control.value.length + 2, 6);
        });
      }
      control.className = "editor-campo";
      control.setAttribute("aria-label", p.etiqueta);
      control.addEventListener("keydown", (ev) => {
        ev.stopPropagation();
        if (ev.key === "Enter") {
          ev.preventDefault();
          confirmarEdicion();
        } else if (ev.key === "Escape") {
          ev.preventDefault();
          cancelarEdicion();
        }
      });
      boton.replaceWith(control);
      editando.controles.push({ control, pieza: p });
    }
    const primero = editando.controles.find((c) => c.pieza.nombre === campoInicial) || editando.controles[0];
    primero.control.focus();
    primero.control.select?.();
    anunciar(t("bloques.anuncio.editando"));
  }

  async function confirmarEdicion() {
    if (!editando) {
      return;
    }
    const { id, controles } = editando;
    editando = null;
    const cambios = controles
      .map(({ control, pieza }) => ({
        campo: pieza.nombre,
        valor: control.type === "checkbox" ? control.checked : control.value,
        antes: pieza.valor,
      }))
      .filter((c) => c.valor !== c.antes);
    if (!cambios.length) {
      dibujar();
      enfocar(id);
      anunciar(t("bloques.anuncio.sin_cambios"));
      return;
    }
    // Varios campos son varias operaciones, pero UN solo paso de deshacer.
    let actual = modelo();
    let r = null;
    for (const c of cambios) {
      r = await puente("bloques_operar", { modelo: actual, op: "editar", id, campo: c.campo, valor: c.valor });
      if (!r) {
        return;
      }
      if (!r.ok) {
        avisar(r.motivo, true);
        dibujar();
        enfocar(id);
        return;
      }
      actual = r.modelo;
    }
    aplicar(r, t("bloques.anuncio.editado"));
    enfocar(id);
  }

  function cancelarEdicion() {
    const id = editando?.id;
    editando = null;
    dibujar();
    if (id) {
      enfocar(id);
    }
    anunciar(t("bloques.anuncio.cancelado"));
  }

  // ---- mover / insertar con el teclado: destinos válidos que calcula Python

  function zonaElemento(destino, idMovido) {
    const clave = idMovido ? B.zonaDeDestino(vista, idMovido, destino) : B.claveZona(destino);
    const [padre, parte, indice] = clave.split("|");
    let sel = `.zona[data-padre="${CSS.escape(padre)}"][data-parte="${CSS.escape(parte)}"]`;
    sel += indice === "" ? ":not([data-indice])" : `[data-indice="${indice}"]`;
    return el.arbol.querySelector(sel);
  }

  async function iniciarModo(origen, desdeId) {
    const r = await puente("bloques_destinos", { modelo: modelo(), origen });
    if (!r) {
      return;
    }
    if (!r.ok || !r.destinos.length) {
      avisar(r.ok ? t("bloques.anuncio.sin_destinos") : r.motivo, true);
      return;
    }
    // Empieza en el primer destino que sigue al bloque con foco.
    const ref = desdeId ? el.arbol.querySelector(`[data-id="${CSS.escape(desdeId)}"]`) : null;
    let k = 0;
    if (ref) {
      const siguiente = r.destinos.findIndex((d) => {
        const z = zonaElemento(d, origen.id ?? null);
        return z && !ref.contains(z) && ref.compareDocumentPosition(z) & Node.DOCUMENT_POSITION_FOLLOWING;
      });
      k = Math.max(siguiente, 0);
    }
    const nombre = origen.id ? nombreDe(origen.id) : nombrePaleta(origen.paleta);
    modo = { origen, nombre, destinos: r.destinos, k };
    el.raiz.classList.add("moviendo");
    if (origen.id) {
      el.arbol.querySelector(`[data-id="${CSS.escape(origen.id)}"]`)?.classList.add("recogido");
    }
    el.lienzo.focus({ preventScroll: true });
    marcarDestino();
    anunciar(`${t("bloques.anuncio.recogido", { tipo: nombre })} ${t("bloques.anuncio.destino", { lugar: r.destinos[k].lugar })}`);
  }

  function marcarDestino() {
    for (const z of el.arbol.querySelectorAll(".zona.destino")) {
      z.classList.remove("destino");
    }
    const z = zonaElemento(modo.destinos[modo.k], modo.origen.id ?? null);
    if (z) {
      z.classList.add("destino");
      asegurarVisible(z);
    }
  }

  function moverDestino(paso) {
    modo.k = (modo.k + paso + modo.destinos.length) % modo.destinos.length;
    marcarDestino();
    anunciar(t("bloques.anuncio.destino", { lugar: modo.destinos[modo.k].lugar }));
  }

  function terminarModo() {
    modo = null;
    el.raiz.classList.remove("moviendo");
    for (const x of el.arbol.querySelectorAll(".recogido, .zona.destino")) {
      x.classList.remove("recogido", "destino");
    }
  }

  async function soltarModo() {
    const m = modo;
    terminarModo();
    const { padre, parte, indice } = m.destinos[m.k];
    const destino = { padre, parte, indice };
    if (m.origen.id) {
      await operar("mover", { id: m.origen.id, destino }, t("bloques.anuncio.movido", { tipo: m.nombre }), m.origen.id);
    } else {
      await operar("insertar", { origen: m.origen, destino }, t("bloques.anuncio.insertado", { tipo: m.nombre }), "nuevo");
    }
  }

  function cancelarModo() {
    const id = modo?.origen.id;
    terminarModo();
    if (id) {
      enfocar(id);
    }
    anunciar(t("bloques.anuncio.cancelado"));
  }

  el.lienzo.addEventListener("keydown", (ev) => {
    if (!modo) {
      return;
    }
    const pasos = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
    if (ev.key in pasos) {
      moverDestino(pasos[ev.key]);
    } else if (ev.key === "Enter" || ev.key === " ") {
      soltarModo();
    } else if (ev.key === "Escape") {
      cancelarModo();
    } else if (ev.key === "Tab") {
      cancelarModo();
      return; // el foco sale con normalidad
    } else {
      return;
    }
    ev.preventDefault();
    ev.stopPropagation();
  });

  el.arbol.addEventListener("keydown", (ev) => {
    if (editando || modo) {
      return;
    }
    const actual = ev.target.closest('[role="treeitem"]');
    if (!actual || ev.target !== actual) {
      return;
    }
    const id = actual.dataset.id;
    const ctrl = ev.ctrlKey || ev.metaKey;
    const z = ev.key === "z" || ev.key === "Z";
    if (ctrl && z && !ev.shiftKey) {
      deshacer();
    } else if (ctrl && (ev.key === "y" || ev.key === "Y" || (z && ev.shiftKey))) {
      rehacer();
    } else if (ctrl && (ev.key === "d" || ev.key === "D")) {
      duplicar(id);
    } else if (ctrl || ev.altKey) {
      return;
    } else if (navegar(ev.key, actual)) {
      // navegación hecha
    } else if (ev.key === "Enter" || ev.key === "F2") {
      editar(id);
    } else if (ev.key === " " || ev.key === "m" || ev.key === "M") {
      iniciarModo({ id }, id);
    } else if (ev.key === "Delete" || ev.key === "Backspace") {
      eliminar(id);
    } else if (ev.key === "Insert") {
      el.paleta.querySelector(".pieza")?.focus();
    } else {
      return;
    }
    ev.preventDefault();
    ev.stopPropagation();
  });

  el.arbol.addEventListener("focusin", (ev) => {
    const item = ev.target.closest('[role="treeitem"]');
    if (item && item === ev.target) {
      for (const x of navegables()) {
        x.tabIndex = x === item ? 0 : -1;
      }
      foco = item.dataset.id;
    }
  });

  el.arbol.addEventListener("click", (ev) => {
    if (editando || modo || ultimoArrastreFueReal()) {
      return;
    }
    const item = ev.target.closest('[role="treeitem"]');
    if (!item) {
      return;
    }
    const accion = ev.target.closest("[data-accion]");
    if (accion) {
      (accion.dataset.accion === "eliminar" ? eliminar : duplicar)(item.dataset.id);
      return;
    }
    const campo = ev.target.closest(".campo");
    if (campo) {
      enfocar(campo.dataset.bloque);
      editar(campo.dataset.bloque, campo.dataset.campo);
      return;
    }
    enfocar(item.dataset.id);
  });

  el.paleta.addEventListener("click", (ev) => {
    const pieza = ev.target.closest(".pieza");
    if (pieza && modelo() && !ultimoArrastreFueReal()) {
      iniciarModo({ paleta: pieza.dataset.clave }, foco);
    }
  });

  // ------------------------------------------------------------ deshacer

  async function restaurar(h, anuncio) {
    const r = await puente("bloques_estado", { modelo: h.actual });
    if (!r || !r.ok) {
      return;
    }
    historial = h;
    aplicar(r, anuncio, { empujar: false });
    if (foco) {
      enfocar(foco);
    }
  }

  function deshacer() {
    if (historial?.pasado.length) {
      restaurar(B.deshacer(historial), t("bloques.anuncio.deshecho"));
    }
  }

  function rehacer() {
    if (historial?.futuro.length) {
      restaurar(B.rehacer(historial), t("bloques.anuncio.rehecho"));
    }
  }

  // ------------------------------------------------------------ arrastrar y soltar

  let marcaArrastre = 0;
  function ultimoArrastreFueReal() {
    return Date.now() - marcaArrastre < 300;
  }

  /** Zona bajo el puntero: la más interior; sobre un bloque de pila, la de antes o después. */
  function zonaEn(x, y) {
    const bajo = document.elementFromPoint(x, y);
    if (!bajo || !el.arbol.contains(bajo)) {
      return null;
    }
    const zona = bajo.closest(".zona");
    const item = bajo.closest('li[role="treeitem"]');
    if (zona && (!item || item.contains(zona))) {
      return zona;
    }
    if (!item) {
      return null;
    }
    const cab = item.querySelector(":scope > .cabecera").getBoundingClientRect();
    if (y < cab.top + cab.height / 2) {
      return item.previousElementSibling;
    }
    const dentro = item.querySelector(":scope > .boca > .pila > .zona");
    if (dentro && y < cab.bottom + 6) {
      return dentro;
    }
    return item.nextElementSibling;
  }

  function datosZona(z) {
    return {
      padre: z.dataset.padre || null,
      parte: z.dataset.parte,
      indice: z.dataset.indice === undefined ? null : Number(z.dataset.indice),
    };
  }

  function marcarZona(z, valida) {
    for (const x of el.arbol.querySelectorAll(".zona.destino, .zona.destino-invalido")) {
      x.classList.remove("destino", "destino-invalido");
    }
    if (z) {
      z.classList.add(valida ? "destino" : "destino-invalido");
    }
  }

  async function evaluar(x, y) {
    const a = arrastre;
    const sobrePapelera = Boolean(a.origen.id && document.elementFromPoint(x, y)?.closest("#papelera"));
    el.papelera.classList.toggle("encima", sobrePapelera);
    a.papelera = sobrePapelera;
    const z = sobrePapelera ? null : zonaEn(x, y);
    if (!z || !z.classList.contains("zona") || (a.origen.id && B.zonaPropia(vista, a.origen.id, datosZona(z)))) {
      a.zona = null;
      marcarZona(null);
      estado(sobrePapelera ? t("bloques.soltar_papelera") : "");
      return;
    }
    const destino = a.origen.id ? B.destinoDeZona(vista, a.origen.id, datosZona(z)) : datosZona(z);
    const clave = B.claveZona(destino);
    a.zona = destino;
    if (!a.veredictos.has(clave)) {
      a.veredictos.set(clave, null);
      const r = await puente("bloques_encaje", { modelo: modelo(), origen: a.origen, destino });
      a.veredictos.set(clave, r || { ok: false, motivo: "" });
    }
    const v = a.veredictos.get(clave);
    if (arrastre !== a || !a.zona || B.claveZona(a.zona) !== clave || !v) {
      return; // el puntero ya está en otra zona o la respuesta aún no llega
    }
    marcarZona(z, v.ok);
    estado(v.ok ? t("bloques.soltar_aqui") : v.motivo, v.ok ? "info" : "error");
  }

  function autodesplazar(y) {
    const r = el.lienzo.getBoundingClientRect();
    if (y < r.top + 30) {
      el.lienzo.scrollTop -= 12;
    } else if (y > r.bottom - 30) {
      el.lienzo.scrollTop += 12;
    }
  }

  function empezar(ev, origen, nodo) {
    arrastre = { origen, nodo, x0: ev.clientX, y0: ev.clientY, activo: false, puntero: ev.pointerId, veredictos: new Map() };
  }

  el.arbol.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0 || editando || modo || !modelo()) {
      return;
    }
    const item = ev.target.closest('[role="treeitem"]');
    if (item && !ev.target.closest(".campo, [data-accion], input, select")) {
      empezar(ev, { id: item.dataset.id }, item);
      ev.stopPropagation();
    }
  });

  el.paleta.addEventListener("pointerdown", (ev) => {
    const pieza = ev.target.closest(".pieza");
    if (pieza && ev.button === 0 && modelo()) {
      empezar(ev, { paleta: pieza.dataset.clave }, pieza);
    }
  });

  document.addEventListener("pointermove", (ev) => {
    if (!arrastre || ev.pointerId !== arrastre.puntero) {
      return;
    }
    if (!arrastre.activo) {
      if (Math.hypot(ev.clientX - arrastre.x0, ev.clientY - arrastre.y0) < UMBRAL_ARRASTRE) {
        return;
      }
      arrastre.activo = true;
      el.raiz.classList.add("arrastrando");
      const fantasma = arrastre.nodo.cloneNode(true);
      fantasma.classList.add("fantasma");
      fantasma.setAttribute("aria-hidden", "true");
      for (const x of [fantasma, ...fantasma.querySelectorAll("[id]")]) {
        x.removeAttribute("id");
      }
      document.body.append(fantasma);
      arrastre.fantasma = fantasma;
      if (arrastre.origen.id) {
        arrastre.nodo.classList.add("recogido");
      }
    }
    arrastre.fantasma.style.left = `${ev.clientX + 10}px`;
    arrastre.fantasma.style.top = `${ev.clientY + 10}px`;
    autodesplazar(ev.clientY);
    evaluar(ev.clientX, ev.clientY);
  });

  function terminarArrastre(cancelar) {
    const a = arrastre;
    arrastre = null;
    el.raiz.classList.remove("arrastrando");
    el.papelera.classList.remove("encima");
    marcarZona(null);
    a.fantasma?.remove();
    a.nodo.classList.remove("recogido");
    if (!a.activo) {
      return;
    }
    marcaArrastre = Date.now();
    const nombre = a.origen.id ? nombreDe(a.origen.id) : nombrePaleta(a.origen.paleta);
    if (cancelar) {
      anunciar(t("bloques.anuncio.cancelado"));
    } else if (a.papelera) {
      eliminar(a.origen.id);
    } else if (a.zona && a.origen.id) {
      operar("mover", { id: a.origen.id, destino: a.zona }, t("bloques.anuncio.movido", { tipo: nombre }), a.origen.id);
    } else if (a.zona) {
      operar("insertar", { origen: a.origen, destino: a.zona }, t("bloques.anuncio.insertado", { tipo: nombre }), "nuevo");
    }
  }

  document.addEventListener("pointerup", (ev) => {
    if (arrastre && ev.pointerId === arrastre.puntero) {
      terminarArrastre(false);
    }
  });
  document.addEventListener("pointercancel", (ev) => {
    if (arrastre && ev.pointerId === arrastre.puntero) {
      terminarArrastre(true);
    }
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && arrastre?.activo) {
      terminarArrastre(true);
    }
  });

  // ------------------------------------------------------------ barra

  el.deshacer.addEventListener("click", deshacer);
  el.rehacer.addEventListener("click", rehacer);
  el.acercar.addEventListener("click", () => {
    zoom = Math.min(zoom + 1, ZOOMS.length - 1);
    dibujar();
    anunciar(el.zoom.textContent);
  });
  el.alejar.addEventListener("click", () => {
    zoom = Math.max(zoom - 1, 0);
    dibujar();
    anunciar(el.zoom.textContent);
  });

  return {
    /** Respuesta de «bloques» (código → bloques): reinicia el historial. */
    cargar(r) {
      historial = B.crearHistorial(r.modelo);
      if (modo) {
        terminarModo();
      }
      dibujarPaleta(r.paleta);
      aplicar(r, "", { empujar: false, sincronizar: false });
    },
    /** Sin bloques (el código no compila): se vacía el lienzo con el motivo. */
    vaciar(mensaje) {
      historial = null;
      vista = [];
      if (modo) {
        terminarModo();
      }
      dibujar();
      pintarProblemas([]);
      estado(mensaje, "error");
    },
    /** Vuelve a pedir vista y paleta con el idioma nuevo de la interfaz (conserva el modelo). */
    async retraducir() {
      if (!historial) {
        return;
      }
      const r = await puente("bloques_estado", { modelo: modelo() });
      const p = await puente("bloques_paleta", { idioma_bloques: modelo().idioma });
      if (r?.ok) {
        aplicar(r, "", { empujar: false, sincronizar: false });
      }
      if (p?.ok) {
        dibujarPaleta(p.paleta);
      }
    },
    envolverEn,
  };
}
