// INV-4223: arranque y cableado del estudio web de InvenioLang.
//
// Une las piezas puras (estado, i18n, almacén, currículo, bloques) con el
// DOM y con el motor de Pyodide. Ningún texto para el estudiante se escribe
// aquí: todos vienen de generado/textos.json (catálogo inveniolang/i18n).
// La única excepción es el aviso bilingüe de abajo, que se muestra cuando
// faltan precisamente esos archivos generados.

import { crearAlmacen } from "./almacen.js";
import * as C from "./curriculo.js";
import { crearEditor } from "./editor.js";
import { crearTienda, estadoInicial, persistible } from "./estado.js";
import { crearTraductor, idiomaInicial } from "./i18n.js";
import { ErrorMotor, crearMotor } from "./motor.js";
import { idiomaDelCodigo } from "./resaltado.js";
import { crearVistaBloques } from "./vista_bloques.js";

const PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v0.29.3/full/";
const SIN_GENERADOS =
  "Faltan los archivos generados: ejecuta «python scripts/empaquetar_web.py». / " +
  "Generated files are missing: run “python scripts/empaquetar_web.py”.";
const MAX_ARCHIVO = 1_000_000;

const $ = (id) => document.getElementById(id);

/**
 * URL base de Pyodide. `?pyodide=/ruta/` permite servir una copia local
 * (aulas sin Internet, pruebas), pero solo del MISMO origen: un enlace
 * malicioso no puede hacer que el estudio cargue código de otro sitio.
 */
function urlPyodide() {
  const pedido = new URLSearchParams(location.search).get("pyodide");
  if (!pedido) {
    return PYODIDE_CDN;
  }
  try {
    const url = new URL(pedido, location.href);
    if (url.origin === location.origin) {
      return url.href.endsWith("/") ? url.href : `${url.href}/`;
    }
  } catch {
    // URL ilegible: se usa la oficial
  }
  return PYODIDE_CDN;
}

async function cargarJSON(ruta) {
  const r = await fetch(ruta, { cache: "no-cache" });
  if (!r.ok) {
    throw new Error(`${ruta}: HTTP ${r.status}`);
  }
  return r.json();
}

/** Copia segura de un SVG generado por Python: sin scripts ni manejadores. */
function svgSeguro(texto) {
  const doc = new DOMParser().parseFromString(texto, "image/svg+xml");
  const svg = doc.documentElement;
  if (svg.nodeName !== "svg") {
    return null;
  }
  for (const malo of svg.querySelectorAll("script, foreignObject")) {
    malo.remove();
  }
  for (const nodo of [svg, ...svg.querySelectorAll("*")]) {
    for (const attr of [...nodo.attributes]) {
      if (/^on/i.test(attr.name) || /^\s*javascript:/i.test(attr.value)) {
        nodo.removeAttribute(attr.name);
      }
    }
  }
  return document.importNode(svg, true);
}

function descargar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function iniciar() {
  let textos;
  let lexico;
  let manifiesto;
  try {
    [textos, lexico, manifiesto] = await Promise.all([
      cargarJSON("generado/textos.json"),
      cargarJSON("generado/lexico.json"),
      cargarJSON("generado/manifiesto.json"),
    ]);
  } catch {
    const aviso = $("aviso-motor");
    aviso.dataset.estado = "sin_paquete";
    $("aviso-motor-texto").textContent = SIN_GENERADOS;
    return;
  }

  const almacen = crearAlmacen();
  const guardado = almacen.leer("estado", {});
  const tienda = crearTienda(
    estadoInicial({
      idiomaCurriculo: idiomaInicial(guardado.idioma, navigator.languages || []),
      ...guardado,
      idioma: idiomaInicial(guardado.idioma, navigator.languages || []),
    }),
  );
  let t = crearTraductor(textos, tienda.obtener().idioma);
  const version = (nombre) => `generado/${nombre}?v=${manifiesto.archivos[nombre].slice(0, 16)}`;

  // ------------------------------------------------------------ anuncios

  function anunciar(texto, urgente = false) {
    const region = urgente ? $("anuncios-urgentes") : $("anuncios");
    region.textContent = "";
    // Un cambio en el siguiente fotograma garantiza que se lea aunque se repita el texto.
    requestAnimationFrame(() => {
      region.textContent = texto;
    });
  }

  // ------------------------------------------------------------ textos e idioma

  function aplicarTextos() {
    document.documentElement.lang = tienda.obtener().idioma;
    for (const n of document.querySelectorAll("[data-t]")) {
      n.textContent = t(n.dataset.t);
    }
    for (const [attr, dato] of [
      ["aria-label", "tAriaLabel"],
      ["title", "tTitle"],
      ["placeholder", "tPlaceholder"],
    ]) {
      for (const n of document.querySelectorAll(`[data-t-${attr}]`)) {
        n.setAttribute(attr, t(n.dataset[dato]));
      }
    }
    $("version").textContent = `v${manifiesto.version}`;
    pintarAtajos();
  }

  // Teclas con nombre propio en cada idioma («Intro»/«Enter», «Supr»/«Delete»):
  // las marcadas con {clave} se traducen con WEB.tecla.<clave>.
  const ATAJOS_GENERALES = [
    ["Ctrl+{intro}", "atajo.ejecutar"],
    ["Ctrl+S", "atajo.guardar"],
    ["Ctrl+O", "atajo.abrir"],
    ["Shift+Alt+F", "atajo.formatear"],
    ["Tab / Shift+Tab", "atajo.sangria"],
    ["Esc, Tab", "atajo.salir_editor"],
    ["F1", "atajo.ayuda"],
  ];
  const ATAJOS_BLOQUES = [
    ["↑ ↓ ← →", "atajo.bloques_navegar"],
    ["{intro} / F2", "atajo.bloques_editar"],
    ["{espacio} / M", "atajo.bloques_mover"],
    ["{supr}", "atajo.bloques_eliminar"],
    ["Ctrl+D", "atajo.bloques_duplicar"],
    ["Ctrl+Z / Ctrl+Y", "atajo.bloques_deshacer"],
    ["Insert", "atajo.bloques_paleta"],
  ];
  const teclas = (texto) =>
    texto.replace(/\{(intro|espacio|supr)\}/g, (_, k) => t(`tecla.${k}`));

  function pintarAtajos() {
    const lista = (atajos) =>
      atajos.flatMap(([combinacion, clave]) => {
        const dt = document.createElement("dt");
        for (const [i, parte] of teclas(combinacion).split(" / ").entries()) {
          if (i) {
            dt.append(" / ");
          }
          const k = document.createElement("kbd");
          k.textContent = parte;
          dt.append(k);
        }
        const dd = document.createElement("dd");
        dd.textContent = t(clave);
        return [dt, dd];
      });
    $("ayuda-atajos").replaceChildren(...lista([...ATAJOS_GENERALES, ...ATAJOS_BLOQUES]));
    $("bloques-atajos").replaceChildren(...lista(ATAJOS_BLOQUES));
  }

  // ------------------------------------------------------------ tema

  const oscuroSistema = window.matchMedia("(prefers-color-scheme: dark)");
  function temaEfectivo() {
    const tema = tienda.obtener().tema;
    if (tema === "sistema") {
      return oscuroSistema.matches ? "oscuro" : "claro";
    }
    return tema;
  }
  function aplicarTema() {
    document.documentElement.dataset.tema = tienda.obtener().tema;
    for (const r of document.querySelectorAll('input[name="tema"]')) {
      r.checked = r.value === tienda.obtener().tema;
    }
  }
  oscuroSistema.addEventListener("change", () => refrescarVisibles());

  // ------------------------------------------------------------ editor

  let versionCodigo = 0;
  const editor = crearEditor({
    texto: $("codigo"),
    resaltado: $("editor-resaltado-codigo"),
    numeros: $("editor-numeros"),
    marcas: $("editor-marcas"),
    alCambiar: (codigo) => {
      versionCodigo++;
      tienda.despachar({ tipo: "codigo", codigo });
      programarRevision();
      pintarEstadoEditor();
    },
    alMoverCursor: ({ linea, columna }) => {
      $("estado-posicion").textContent = t("editor.posicion", { linea, columna });
    },
  });
  editor.establecerLexico(lexico);
  if (!tienda.obtener().codigo) {
    // Primera visita: programa vacío en el idioma de la interfaz, sin marcarlo como modificado.
    tienda.despachar({ tipo: "abrir", codigo: C.plantilla(tienda.obtener().idioma), nombre: "programa.inv" });
  }
  editor.establecer(tienda.obtener().codigo);

  function idiomaCodigo() {
    return idiomaDelCodigo(editor.valor(), lexico.pares) || tienda.obtener().idioma;
  }

  function pintarEstadoEditor() {
    const idi = idiomaCodigo();
    $("estado-idioma-codigo").textContent = t("editor.idioma_codigo", { lengua: t(`idioma.${idi}`) });
    const e = tienda.obtener();
    $("estado-archivo").textContent = e.modificado ? t("editor.archivo_modificado", { nombre: e.nombre }) : e.nombre;
    $("btn-traducir-texto").textContent = t("editor.traducir_a", { lengua: t(`idioma.${idi === "es" ? "en" : "es"}`) });
  }

  // ------------------------------------------------------------ motor

  const motor = crearMotor({
    pyodide: urlPyodide(),
    // URL absoluta: el Worker resuelve las relativas desde js/, no desde la página.
    paquete: new URL(version("inveniolang.zip"), location.href).href,
    contrato: manifiesto.contrato,
    crearWorker: () => new Worker(new URL("./trabajador.js", import.meta.url), { type: "module" }),
    alCambiar: (estado) => tienda.despachar({ tipo: "motor", estado }),
  });

  function pintarMotor() {
    const estado = tienda.obtener().motor;
    const aviso = $("aviso-motor");
    aviso.dataset.estado = estado;
    $("aviso-motor-texto").textContent = t(`motor.${estado}`);
    $("btn-reintentar").hidden = !["sin_red", "error"].includes(estado);
    const marca = $("estado-motor");
    marca.dataset.estado = estado;
    marca.textContent = t(`motor.corto.${estado}`);
    const listo = estado === "listo" || estado === "ocupado";
    for (const id of ["btn-ejecutar", "btn-pasos", "btn-formatear", "btn-traducir", "btn-comprobar", "btn-pasos-generar"]) {
      $(id).disabled = !listo;
    }
    $("btn-detener").disabled = estado !== "ocupado";
  }

  async function llamar(metodo, args, opciones) {
    try {
      return await motor.llamar(metodo, args, opciones);
    } catch (e) {
      if (e instanceof ErrorMotor) {
        const msg = t(`motor.error.${e.motivo}`);
        anunciar(msg, true);
        mostrarResultado("error", msg);
        return null;
      }
      throw e;
    }
  }

  // ------------------------------------------------------------ revisión en vivo

  let relojRevision = null;
  function programarRevision() {
    clearTimeout(relojRevision);
    relojRevision = setTimeout(async () => {
      if (motor.estado() !== "listo") {
        return;
      }
      const v = versionCodigo;
      const r = await llamar("revisar", { codigo: editor.valor(), idioma: tienda.obtener().idioma }, { fondo: true });
      if (r && v === versionCodigo) {
        tienda.despachar({ tipo: "diagnosticos", diagnosticos: r.errores });
        if (r.ok) {
          refrescarVisibles(); // diagramas y bloques siguen al código mientras se escribe
        }
      }
    }, 700);
  }

  // ------------------------------------------------------------ errores

  function pintarErrores() {
    const diags = tienda.obtener().diagnosticos;
    editor.marcarErrores(diags.map((d) => d.linea));
    const insignia = $("insignia-errores");
    insignia.hidden = !diags.length;
    insignia.textContent = String(diags.length);
    insignia.setAttribute("aria-label", t("errores.cuenta", { n: diags.length }));
    $("errores-vacio").hidden = diags.length > 0;
    $("lista-errores").replaceChildren(...diags.map(errorItem));
  }

  function errorItem(d) {
    const li = document.createElement("li");
    li.className = "error-item";
    const cab = document.createElement("div");
    cab.className = "error-cabecera";
    if (d.codigo) {
      const cod = document.createElement("span");
      cod.className = "error-codigo";
      cod.textContent = d.codigo;
      cab.append(cod);
    }
    if (d.linea > 0) {
      const ir = document.createElement("button");
      ir.type = "button";
      ir.className = "boton boton-texto error-ir";
      ir.textContent = t("errores.ir_a", { linea: d.linea, columna: d.columna });
      ir.addEventListener("click", () => editor.irA(d.linea, d.columna));
      cab.append(ir);
    }
    const msg = document.createElement("p");
    msg.className = "error-mensaje";
    msg.textContent = d.mensaje;
    li.append(cab, msg);
    if (d.explicacion) {
      const x = d.explicacion;
      const dl = document.createElement("dl");
      dl.className = "explicacion";
      const fila = (clave, valor, codigo = false) => {
        const dt = document.createElement("dt");
        dt.textContent = t(clave);
        const dd = document.createElement("dd");
        if (codigo) {
          const c = document.createElement("code");
          c.textContent = valor;
          dd.append(c);
        } else {
          dd.textContent = valor;
        }
        dl.append(dt, dd);
      };
      fila("errores.que_es", x.titulo);
      fila("errores.por_que", x.por_que);
      fila("errores.mal", x.malo, true);
      fila("errores.bien", x.bueno, true);
      fila("errores.arreglo", x.arreglo);
      li.append(dl);
    }
    return li;
  }

  // ------------------------------------------------------------ ejecutar

  function mostrarResultado(estado, texto) {
    const r = $("resultado");
    r.dataset.estado = estado;
    r.textContent = texto;
  }

  function lineasEntrada() {
    const v = $("entrada").value.replace(/\r\n/g, "\n");
    return v ? v.replace(/\n$/, "").split("\n") : [];
  }

  async function ejecutar() {
    if (motor.estado() !== "listo") {
      anunciar(t(`motor.${motor.estado()}`), true);
      return null;
    }
    elegirPestana("salida");
    mostrarResultado("", t("salida.ejecutando"));
    $("salida").textContent = "";
    const r = await llamar("ejecutar", { codigo: editor.valor(), entrada: lineasEntrada(), idioma: tienda.obtener().idioma });
    if (!r) {
      return null;
    }
    tienda.despachar({ tipo: "resultado", salida: r.salida, diagnosticos: r.errores, ok: r.ok });
    $("salida").textContent = r.salida;
    if (r.ok) {
      mostrarResultado("ok", t("salida.terminado"));
      anunciar(t("salida.terminado_anuncio", { lineas: r.salida ? r.salida.split("\n").length : 0 }));
    } else {
      const primero = r.errores[0];
      const resumen = t("salida.con_errores", { n: r.errores.length, mensaje: primero ? primero.mensaje : "" });
      mostrarResultado("error", resumen);
      anunciar(resumen, true);
      if (!r.salida) {
        elegirPestana("errores");
      }
    }
    return r;
  }

  // ------------------------------------------------------------ pestañas

  const pestanas = [...document.querySelectorAll('[role="tab"]')];
  const vigentes = new Map(); // pestaña → versión de código que muestra

  function elegirPestana(nombre, enfocar = false) {
    tienda.despachar({ tipo: "pestana", pestana: nombre });
    if (enfocar) {
      $(`tab-${nombre}`).focus();
    }
  }

  function pintarPestanas() {
    const actual = tienda.obtener().pestana;
    // Los bloques necesitan más ancho: el panel crece mientras están a la vista.
    $("estudio").dataset.pestana = actual;
    for (const p of pestanas) {
      const sel = p.dataset.pestana === actual;
      p.setAttribute("aria-selected", String(sel));
      p.tabIndex = sel ? 0 : -1;
      $(p.getAttribute("aria-controls")).hidden = !sel;
    }
  }

  for (const p of pestanas) {
    p.addEventListener("click", () => elegirPestana(p.dataset.pestana));
    p.addEventListener("keydown", (e) => {
      const k = pestanas.indexOf(p);
      const destino = { ArrowRight: k + 1, ArrowLeft: k - 1, Home: 0, End: pestanas.length - 1 }[e.key];
      if (destino === undefined) {
        return;
      }
      e.preventDefault();
      const q = pestanas[(destino + pestanas.length) % pestanas.length];
      elegirPestana(q.dataset.pestana, true);
    });
  }

  function refrescarVisibles() {
    const p = tienda.obtener().pestana;
    if (motor.estado() !== "listo" && motor.estado() !== "ocupado") {
      return;
    }
    if (p === "flujo" && vigentes.get("flujo") !== clave("flujo")) {
      dibujarFlujo();
    } else if (p === "uml" && vigentes.get("uml") !== clave("uml")) {
      dibujarUML();
    } else if (p === "bloques" && vigentes.get("bloques") !== versionCodigo) {
      cargarBloques();
    }
  }

  const clave = (panel) => `${versionCodigo}|${temaEfectivo()}|${tienda.obtener().idioma}|${panel === "flujo" ? $("sel-subrutina").value : ""}`;

  // ------------------------------------------------------------ diagramas

  let svgFlujo = null;
  async function dibujarFlujo() {
    const k = clave("flujo");
    const r = await llamar("flujo", {
      codigo: editor.valor(),
      idioma: tienda.obtener().idioma,
      tema: temaEfectivo(),
      subrutina: $("sel-subrutina").value || null,
    });
    if (!r) {
      return;
    }
    vigentes.set("flujo", k);
    const lienzo = $("lienzo-flujo");
    if (!r.ok) {
      svgFlujo = null;
      lienzo.replaceChildren(mensajeErrores(r.errores));
      $("texto-flujo").textContent = "";
      $("btn-flujo-descargar").disabled = true;
      return;
    }
    const sel = $("sel-subrutina");
    const elegido = sel.value;
    sel.replaceChildren(
      new Option(t("flujo.todas"), ""),
      ...r.diagramas.map((d) => new Option(`${d.firma}`, d.clave)),
    );
    sel.value = r.diagramas.some((d) => d.clave === elegido) ? elegido : "";
    svgFlujo = r.svg;
    const svg = svgSeguro(r.svg);
    lienzo.replaceChildren(...(svg ? [svg] : []));
    $("texto-flujo").textContent = r.texto;
    $("btn-flujo-descargar").disabled = false;
  }

  function mensajeErrores(errores) {
    const p = document.createElement("p");
    p.className = "vacio";
    p.textContent = t("diagrama.con_errores", { n: errores.length });
    return p;
  }

  let umlActual = null;
  async function dibujarUML() {
    const k = clave("uml");
    const r = await llamar("uml", { codigo: editor.valor(), idioma: tienda.obtener().idioma, tema: temaEfectivo() });
    if (!r) {
      return;
    }
    vigentes.set("uml", k);
    const lienzo = $("lienzo-uml");
    if (!r.ok) {
      umlActual = null;
      lienzo.replaceChildren(mensajeErrores(r.errores));
      $("texto-uml").textContent = "";
    } else {
      umlActual = r;
      const svg = svgSeguro(r.svg);
      lienzo.replaceChildren(...(svg ? [svg] : []));
      $("texto-uml").textContent = r.texto;
    }
    $("btn-uml-descargar").disabled = !umlActual;
    $("btn-uml-plantuml").disabled = !umlActual;
  }

  const base = () => tienda.obtener().nombre.replace(/\.inv$/i, "");
  $("btn-flujo-actualizar").addEventListener("click", dibujarFlujo);
  $("sel-subrutina").addEventListener("change", dibujarFlujo);
  $("btn-flujo-descargar").addEventListener("click", () => svgFlujo && descargar(`${base()}-flujo.svg`, svgFlujo, "image/svg+xml"));
  $("btn-uml-actualizar").addEventListener("click", dibujarUML);
  $("btn-uml-descargar").addEventListener("click", () => umlActual && descargar(`${base()}-uml.svg`, umlActual.svg, "image/svg+xml"));
  $("btn-uml-plantuml").addEventListener("click", () => umlActual && descargar(`${base()}.puml`, umlActual.plantuml, "text/plain"));

  // ------------------------------------------------------------ paso a paso

  async function generarPasos() {
    elegirPestana("pasos");
    $("pasos-resumen").textContent = t("pasos.generando");
    const r = await llamar("traza", { codigo: editor.valor(), entrada: lineasEntrada(), idioma: tienda.obtener().idioma });
    if (!r) {
      $("pasos-resumen").textContent = "";
      return;
    }
    const marco = $("marco-pasos");
    if (!r.ok) {
      tienda.despachar({ tipo: "diagnosticos", diagnosticos: r.errores });
      $("pasos-resumen").textContent = t("diagrama.con_errores", { n: r.errores.length });
      marco.hidden = true;
      return;
    }
    // El reproductor es una página autónoma: se muestra aislada (sin acceso
    // a esta página ni a su almacenamiento) y con el tema del estudio.
    marco.srcdoc = r.html.replace('data-tema="claro"', `data-tema="${temaEfectivo()}"`);
    marco.hidden = false;
    const resumen = t(r.truncada ? "pasos.resumen_truncada" : "pasos.resumen", { n: r.pasos });
    $("pasos-resumen").textContent = resumen;
    anunciar(resumen);
  }

  // ------------------------------------------------------------ bloques

  const vista = crearVistaBloques({
    el: {
      raiz: $("panel-bloques"),
      arbol: $("arbol-bloques"),
      lienzo: $("lienzo-bloques"),
      paleta: $("paleta"),
      estilos: $("estilos-categorias"),
      estado: $("bloques-estado"),
      problemas: $("bloques-problemas"),
      papelera: $("papelera"),
      deshacer: $("btn-bloques-deshacer"),
      rehacer: $("btn-bloques-rehacer"),
      acercar: $("btn-bloques-acercar"),
      alejar: $("btn-bloques-alejar"),
      zoom: $("bloques-zoom"),
    },
    t: (k, a) => t(k, a),
    anunciar,
    puente: (metodo, args) => llamar(metodo, { ...args, idioma: tienda.obtener().idioma }),
    alCodigo: (codigo) => {
      // Los bloques sin problemas reescriben el editor (una edición deshacible).
      editor.reemplazarTodo(codigo);
      vigentes.set("bloques", versionCodigo);
    },
  });

  async function cargarBloques() {
    const v = versionCodigo;
    const r = await llamar("bloques", { codigo: editor.valor(), idioma: tienda.obtener().idioma });
    if (!r) {
      return;
    }
    vigentes.set("bloques", v);
    if (r.ok) {
      vista.cargar(r);
    } else if (r.errores) {
      vista.vaciar(t("bloques.codigo_invalido", { n: r.errores.length }));
      tienda.despachar({ tipo: "diagnosticos", diagnosticos: r.errores });
    } else {
      vista.vaciar(r.motivo);
    }
  }

  $("btn-bloques-desde-codigo").addEventListener("click", cargarBloques);
  $("btn-envolver").addEventListener("click", () => {
    const sel = $("sel-envolver");
    vista.envolverEn(sel.value, sel.selectedOptions[0].textContent);
  });
  $("btn-bloques-ayuda").addEventListener("click", (e) => {
    const abierto = e.currentTarget.getAttribute("aria-expanded") === "true";
    e.currentTarget.setAttribute("aria-expanded", String(!abierto));
    $("bloques-ayuda").hidden = abierto;
  });

  // ------------------------------------------------------------ diálogos

  function confirmar(texto, boton) {
    const d = $("dialogo-confirmar");
    $("dialogo-confirmar-texto").textContent = texto;
    $("dialogo-confirmar-si").textContent = boton;
    d.returnValue = "";
    d.showModal();
    return new Promise((resolver) => {
      d.addEventListener("close", () => resolver(d.returnValue === "si"), { once: true });
    });
  }

  async function puedeDescartar() {
    if (!tienda.obtener().modificado) {
      return true;
    }
    return confirmar(t("archivo.descartar_pregunta", { nombre: tienda.obtener().nombre }), t("archivo.descartar"));
  }

  function abrirCodigo(codigo, nombre, extra = {}) {
    editor.establecer(codigo);
    versionCodigo++;
    tienda.despachar({ tipo: "abrir", codigo, nombre, ...extra });
    $("entrada").value = tienda.obtener().entrada;
    $("salida").textContent = "";
    mostrarResultado("", "");
    programarRevision();
    pintarEstadoEditor();
    refrescarVisibles();
  }

  $("btn-nuevo").addEventListener("click", async () => {
    if (await puedeDescartar()) {
      abrirCodigo(C.plantilla(tienda.obtener().idioma), "programa.inv", { ejercicio: null, entrada: "" });
      anunciar(t("archivo.nuevo_anuncio"));
      editor.irA(2, 5);
    }
  });

  function pintarGuardados() {
    const lista = almacen.programas();
    $("guardados-vacio").hidden = lista.length > 0;
    const fmt = new Intl.DateTimeFormat(tienda.obtener().idioma, { dateStyle: "medium", timeStyle: "short" });
    $("lista-guardados").replaceChildren(
      ...lista.map((p) => {
        const li = document.createElement("li");
        const abrir = document.createElement("button");
        abrir.type = "button";
        abrir.className = "boton";
        const nombre = document.createElement("span");
        nombre.textContent = p.nombre;
        const fecha = document.createElement("time");
        fecha.dateTime = new Date(p.fecha).toISOString();
        fecha.textContent = fmt.format(new Date(p.fecha));
        abrir.append(nombre, fecha);
        abrir.addEventListener("click", async () => {
          $("dialogo-abrir").close();
          if (await puedeDescartar()) {
            abrirCodigo(p.codigo, p.nombre, { ejercicio: null });
            anunciar(t("archivo.abierto", { nombre: p.nombre }));
          }
        });
        const borrar = document.createElement("button");
        borrar.type = "button";
        borrar.className = "boton boton-icono";
        borrar.setAttribute("aria-label", t("abrir.borrar", { nombre: p.nombre }));
        borrar.title = borrar.getAttribute("aria-label");
        borrar.innerHTML = '<svg class="icono" aria-hidden="true"><use href="#i-papelera"/></svg>';
        borrar.addEventListener("click", () => {
          almacen.borrarPrograma(p.nombre);
          pintarGuardados();
          anunciar(t("abrir.borrado", { nombre: p.nombre }));
          $("archivo-local").focus();
        });
        li.append(abrir, borrar);
        return li;
      }),
    );
  }

  function abrirDialogoAbrir() {
    pintarGuardados();
    $("dialogo-abrir").showModal();
  }

  $("btn-abrir").addEventListener("click", abrirDialogoAbrir);
  $("archivo-local").addEventListener("change", async (e) => {
    const archivo = e.target.files[0];
    e.target.value = "";
    if (!archivo) {
      return;
    }
    $("dialogo-abrir").close();
    if (archivo.size > MAX_ARCHIVO) {
      anunciar(t("archivo.demasiado_grande", { nombre: archivo.name }), true);
      mostrarResultado("error", t("archivo.demasiado_grande", { nombre: archivo.name }));
      return;
    }
    if (await puedeDescartar()) {
      abrirCodigo(await archivo.text(), archivo.name, { ejercicio: null });
      anunciar(t("archivo.abierto", { nombre: archivo.name }));
    }
  });

  function abrirDialogoGuardar() {
    $("nombre-guardar").value = tienda.obtener().nombre;
    $("dialogo-guardar").showModal();
    $("nombre-guardar").select();
  }

  $("btn-guardar").addEventListener("click", abrirDialogoGuardar);
  $("dialogo-guardar").addEventListener("close", () => {
    if ($("dialogo-guardar").returnValue !== "guardar") {
      return;
    }
    const r = almacen.guardarPrograma($("nombre-guardar").value, editor.valor());
    if (r.ok) {
      tienda.despachar({ tipo: "guardado", nombre: r.nombre });
      anunciar(t(r.lleno ? "guardar.hecho_lleno" : "guardar.hecho", { nombre: r.nombre }));
      mostrarResultado("ok", t("guardar.hecho", { nombre: r.nombre }));
    } else {
      anunciar(t("guardar.fallo"), true);
      mostrarResultado("error", t("guardar.fallo"));
    }
    pintarEstadoEditor();
  });

  $("btn-descargar").addEventListener("click", () => {
    descargar(tienda.obtener().nombre, editor.valor(), "text/plain;charset=utf-8");
    anunciar(t("archivo.descargado", { nombre: tienda.obtener().nombre }));
  });

  $("btn-ayuda").addEventListener("click", () => $("dialogo-ayuda").showModal());

  // ------------------------------------------------------------ herramientas

  $("btn-ejecutar").addEventListener("click", ejecutar);
  $("btn-detener").addEventListener("click", () => {
    motor.detener();
    anunciar(t("motor.detenido"), true);
  });
  $("btn-reintentar").addEventListener("click", () => motor.iniciar());
  $("btn-pasos").addEventListener("click", generarPasos);
  $("btn-pasos-generar").addEventListener("click", generarPasos);

  async function formatear() {
    const r = await llamar("formatear", { codigo: editor.valor(), idioma: tienda.obtener().idioma });
    if (!r) {
      return;
    }
    if (r.ok) {
      editor.reemplazarTodo(r.codigo);
      anunciar(t("editor.formateado"));
    } else {
      tienda.despachar({ tipo: "diagnosticos", diagnosticos: r.errores });
      anunciar(t("diagrama.con_errores", { n: r.errores.length }), true);
    }
  }
  $("btn-formatear").addEventListener("click", formatear);

  $("btn-traducir").addEventListener("click", async () => {
    const destino = idiomaCodigo() === "es" ? "en" : "es";
    const r = await llamar("traducir", { codigo: editor.valor(), destino });
    if (r) {
      editor.reemplazarTodo(r.codigo);
      anunciar(t("editor.traducido", { lengua: t(`idioma.${destino}`) }));
      pintarEstadoEditor();
    }
  });

  $("entrada").value = tienda.obtener().entrada;
  $("entrada").addEventListener("input", (e) => tienda.despachar({ tipo: "entrada", entrada: e.target.value }));

  // ------------------------------------------------------------ preferencias

  $("sel-idioma").value = tienda.obtener().idioma;
  $("sel-idioma").addEventListener("change", (e) => {
    tienda.despachar({ tipo: "idioma", idioma: e.target.value });
  });
  for (const r of document.querySelectorAll('input[name="tema"]')) {
    r.addEventListener("change", () => tienda.despachar({ tipo: "tema", tema: r.value }));
  }

  const estudio = $("estudio");
  const btnCurriculo = $("btn-curriculo");
  function mostrarCurriculo(visible) {
    estudio.classList.toggle("sin-curriculo", !visible);
    btnCurriculo.setAttribute("aria-expanded", String(visible));
  }
  mostrarCurriculo(window.innerWidth > 1100);
  btnCurriculo.addEventListener("click", () => {
    const visible = btnCurriculo.getAttribute("aria-expanded") !== "true";
    mostrarCurriculo(visible);
    if (visible) {
      $("buscar-curriculo").focus();
    }
  });

  // ------------------------------------------------------------ currículo

  const curriculos = {};
  async function curriculo() {
    const idi = tienda.obtener().idiomaCurriculo;
    if (!curriculos[idi]) {
      curriculos[idi] = await cargarJSON(version(`curriculo.${idi}.json`));
    }
    return curriculos[idi];
  }

  async function pintarCurriculo() {
    for (const r of document.querySelectorAll('input[name="idioma-curriculo"]')) {
      r.checked = r.value === tienda.obtener().idiomaCurriculo;
    }
    let cur;
    try {
      cur = await curriculo();
    } catch {
      $("arbol-curriculo").textContent = t("curriculo.no_disponible");
      return;
    }
    const e = tienda.obtener();
    const consulta = $("buscar-curriculo").value;
    const niveles = C.filtrar(cur, consulta);
    const total = C.ejercicios(cur).length;
    const resueltos = new Set(e.resueltos);
    $("progreso-curriculo").textContent = t("curriculo.progreso", {
      n: C.ejercicios(cur).filter((x) => resueltos.has(x.id)).length,
      total,
    });
    const arbol = $("arbol-curriculo");
    if (!niveles.length) {
      arbol.textContent = t("curriculo.sin_resultados");
      return;
    }
    arbol.replaceChildren(
      ...niveles.map((n) => {
        const det = document.createElement("details");
        det.className = "nivel";
        det.open = Boolean(consulta) || n.ejercicios.some((x) => x.id === e.ejercicio);
        const sum = document.createElement("summary");
        const num = document.createElement("span");
        num.className = "nivel-num";
        num.textContent = String(n.nivel).padStart(2, "0");
        sum.append(num, n.titulo);
        const desc = document.createElement("p");
        desc.className = "nivel-desc";
        desc.textContent = n.descripcion;
        const ul = document.createElement("ul");
        ul.className = "lista-ejercicios";
        for (const ej of n.ejercicios) {
          const li = document.createElement("li");
          const b = document.createElement("button");
          b.type = "button";
          b.dataset.id = ej.id;
          if (ej.id === e.ejercicio) {
            b.setAttribute("aria-current", "true");
          }
          const titulo = document.createElement("span");
          titulo.textContent = `${ej.numero}. ${ej.titulo}`;
          b.append(titulo);
          if (resueltos.has(ej.id)) {
            const m = document.createElement("span");
            m.className = "marca-resuelto";
            m.textContent = "✓";
            m.setAttribute("aria-label", t("curriculo.resuelto"));
            m.setAttribute("role", "img");
            b.append(m);
          }
          b.addEventListener("click", () => abrirEjercicio(ej.id));
          li.append(b);
          ul.append(li);
        }
        det.append(sum, desc, ul);
        return det;
      }),
    );
  }

  let pistasVistas = 0;
  async function pintarEjercicio() {
    const id = tienda.obtener().ejercicio;
    const art = $("ejercicio");
    $("btn-comprobar").hidden = !id;
    if (!id) {
      art.hidden = true;
      return;
    }
    const ej = C.buscarEjercicio(await curriculo(), id);
    if (!ej) {
      art.hidden = true;
      return;
    }
    art.hidden = false;
    art.lang = tienda.obtener().idiomaCurriculo;
    $("ejercicio-id").textContent = t("ejercicio.nivel", { id: ej.id, nivel: ej.nivel });
    $("ejercicio-titulo").textContent = ej.titulo;
    $("ejercicio-enunciado").textContent = ej.enunciado;
    $("ejercicio-objetivos").replaceChildren(
      ...ej.objetivos.map((o) => {
        const li = document.createElement("li");
        li.textContent = o;
        return li;
      }),
    );
    $("ejercicio-pistas").replaceChildren(
      ...ej.pistas.slice(0, pistasVistas).map((p) => {
        const li = document.createElement("li");
        li.textContent = p;
        return li;
      }),
    );
    const cur = await curriculo();
    $("btn-ejercicio-anterior").disabled = !C.vecino(cur, id, -1);
    $("btn-ejercicio-siguiente").disabled = !C.vecino(cur, id, 1);
    const btnPista = $("btn-pista");
    btnPista.hidden = pistasVistas >= ej.pistas.length;
    btnPista.textContent = t("ejercicio.pista", { n: pistasVistas + 1, total: ej.pistas.length });
  }

  async function abrirEjercicio(id) {
    if (!(await puedeDescartar())) {
      return;
    }
    const ej = C.buscarEjercicio(await curriculo(), id);
    pistasVistas = 0;
    abrirCodigo(C.plantilla(tienda.obtener().idiomaCurriculo), `${ej.archivo.split("/").pop()}`, {
      ejercicio: id,
      entrada: ej.entrada.join("\n"),
    });
    $("ejercicio-veredicto").textContent = "";
    if (window.innerWidth <= 1100) {
      mostrarCurriculo(false);
    }
    anunciar(t("ejercicio.abierto", { titulo: ej.titulo }));
    editor.irA(2, 5);
  }

  for (const [boton, paso] of [["btn-ejercicio-anterior", -1], ["btn-ejercicio-siguiente", 1]]) {
    $(boton).addEventListener("click", async () => {
      const otro = C.vecino(await curriculo(), tienda.obtener().ejercicio, paso);
      if (otro) {
        await abrirEjercicio(otro.id);
      }
    });
  }

  $("btn-pista").addEventListener("click", async () => {
    pistasVistas++;
    await pintarEjercicio();
    const pistas = $("ejercicio-pistas").children;
    anunciar(pistas[pistas.length - 1]?.textContent ?? "");
  });

  $("btn-solucion").addEventListener("click", async () => {
    const ej = C.buscarEjercicio(await curriculo(), tienda.obtener().ejercicio);
    if (ej && (await confirmar(t("ejercicio.solucion_pregunta"), t("ejercicio.ver_solucion")))) {
      editor.reemplazarTodo(ej.solucion);
      anunciar(t("ejercicio.solucion_cargada"));
    }
  });

  $("btn-cerrar-ejercicio").addEventListener("click", () => {
    tienda.despachar({ tipo: "abrir", codigo: editor.valor(), nombre: tienda.obtener().nombre, ejercicio: null });
    $("btn-ejecutar").focus();
  });

  $("btn-comprobar").addEventListener("click", async () => {
    const ej = C.buscarEjercicio(await curriculo(), tienda.obtener().ejercicio);
    if (!ej) {
      return;
    }
    $("entrada").value = ej.entrada.join("\n");
    tienda.despachar({ tipo: "entrada", entrada: $("entrada").value });
    const r = await ejecutar();
    if (!r) {
      return;
    }
    const v = $("ejercicio-veredicto");
    const cmp = C.comparar(r.salida, ej.esperado);
    if (r.ok && cmp.ok) {
      v.dataset.ok = "true";
      v.textContent = t("ejercicio.correcto");
      tienda.despachar({ tipo: "resueltos", resueltos: C.marcarResuelto(tienda.obtener().resueltos, ej.id) });
    } else {
      v.dataset.ok = "false";
      v.textContent = r.ok
        ? t("ejercicio.diferente", { linea: cmp.linea, obtenido: cmp.obtenido, esperado: cmp.esperado })
        : t("ejercicio.con_errores");
    }
    anunciar(v.textContent, true);
  });

  $("buscar-curriculo").addEventListener("input", pintarCurriculo);
  for (const r of document.querySelectorAll('input[name="idioma-curriculo"]')) {
    r.addEventListener("change", () => tienda.despachar({ tipo: "idiomaCurriculo", idioma: r.value }));
  }

  // ------------------------------------------------------------ atajos globales

  document.addEventListener("keydown", (e) => {
    const ctrl = e.ctrlKey || e.metaKey;
    if (document.querySelector("dialog[open]")) {
      return;
    }
    if (ctrl && e.key === "Enter") {
      e.preventDefault();
      ejecutar();
    } else if (ctrl && (e.key === "s" || e.key === "S")) {
      e.preventDefault();
      abrirDialogoGuardar();
    } else if (ctrl && (e.key === "o" || e.key === "O")) {
      e.preventDefault();
      abrirDialogoAbrir();
    } else if (e.shiftKey && e.altKey && (e.key === "F" || e.key === "f" || e.code === "KeyF")) {
      e.preventDefault();
      formatear();
    } else if (e.key === "F1") {
      e.preventDefault();
      $("dialogo-ayuda").showModal();
    }
  });

  window.addEventListener("beforeunload", (e) => {
    // El borrador ya está guardado en localStorage; solo se avisa si no se pudo.
    if (tienda.obtener().modificado && !almacen.disponible()) {
      e.preventDefault();
    }
  });

  // ------------------------------------------------------------ reacción al estado

  let relojPersistir = null;
  tienda.suscribir((e, previo) => {
    if (e.idioma !== previo.idioma) {
      t = crearTraductor(textos, e.idioma);
      aplicarTextos();
      pintarMotor();
      pintarEstadoEditor();
      pintarCurriculo();
      pintarEjercicio();
      vista.retraducir();
      refrescarVisibles();
      programarRevision();
    }
    if (e.tema !== previo.tema) {
      aplicarTema();
      refrescarVisibles();
    }
    if (e.motor !== previo.motor) {
      pintarMotor();
      if (e.motor === "listo" && previo.motor === "cargando") {
        anunciar(t("motor.listo_anuncio"));
        programarRevision();
        refrescarVisibles();
      }
    }
    if (e.pestana !== previo.pestana) {
      pintarPestanas();
      refrescarVisibles();
    }
    if (e.diagnosticos !== previo.diagnosticos) {
      pintarErrores();
    }
    if (e.ejercicio !== previo.ejercicio || e.idiomaCurriculo !== previo.idiomaCurriculo) {
      pintarEjercicio();
      pintarCurriculo();
    }
    if (e.resueltos !== previo.resueltos) {
      pintarCurriculo();
    }
    if (e.modificado !== previo.modificado || e.nombre !== previo.nombre) {
      pintarEstadoEditor();
    }
    clearTimeout(relojPersistir);
    relojPersistir = setTimeout(() => almacen.escribir("estado", persistible(tienda.obtener())), 400);
  });

  aplicarTextos();
  aplicarTema();
  pintarPestanas();
  pintarMotor();
  pintarErrores();
  pintarEstadoEditor();
  pintarCurriculo();
  pintarEjercicio();
  $("estado-posicion").textContent = t("editor.posicion", { linea: 1, columna: 1 });
  if (!almacen.disponible()) {
    mostrarResultado("error", t("almacen.no_disponible"));
  }
  motor.iniciar();
}

iniciar();
