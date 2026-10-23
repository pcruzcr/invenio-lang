// INV-2241: DOM mínimo para ejecutar el JavaScript del reproductor HTML en
// Node (sin navegador ni dependencias) y comprobar su comportamiento real:
// descompresión de los SVG, navegación por teclado y botones, resaltado de
// la línea actual y región aria-live. Uso: node dom_minimo.js pagina.html
"use strict";
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");

class ClassList {
  constructor() { this.s = new Set(); }
  add(c) { this.s.add(c); }
  remove(c) { this.s.delete(c); }
  contains(c) { return this.s.has(c); }
}
class Elemento {
  constructor(id, tag, attrs) {
    this.id = id; this.tagName = tag.toUpperCase(); this.attrs = attrs || {};
    this.textContent = ""; this.innerHTML = ""; this.value = this.attrs.value || "";
    this.type = this.attrs.type || ""; this.classList = new ClassList(); this.oyentes = {};
    this.hijos = {};
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(t, f) { (this.oyentes[t] = this.oyentes[t] || []).push(f); }
  disparar(t, e) { (this.oyentes[t] || []).forEach((f) => f.call(this, e || {})); }
  click() { this.disparar("click", { target: this }); }
  querySelector(sel) {
    if (sel === ".marca") { return this.hijos.marca; }
    if (sel === "li.actual") {
      return Object.values(elementos).find((e) => e.tagName === "LI" && e.classList.contains("actual")) || null;
    }
    return null;
  }
  scrollIntoView() {}
}
const elementos = {};
const re = /<(\w+)([^>]*?)\sid="([^"]+)"([^>]*)>/g;
let m;
while ((m = re.exec(html))) {
  const attrs = {};
  (m[2] + m[4]).replace(/([\w-]+)="([^"]*)"/g, (_, k, v) => { attrs[k] = v; });
  const el = new Elemento(m[3], m[1], attrs);
  if (m[1] === "li") { el.hijos.marca = new Elemento("", "span"); }
  elementos[m[3]] = el;
}
const datos = html.match(/<script type="application\/json" id="vis-datos">([\s\S]*?)<\/script>/)[1];
elementos["vis-datos"].textContent = datos;
elementos["velocidad"].value = "1";
const raiz = new Elemento("html", "html", { "data-tema": "claro" });
const oyentesDoc = {};
global.document = {
  documentElement: raiz,
  getElementById: (id) => elementos[id] || null,
  addEventListener: (t, f) => { (oyentesDoc[t] = oyentesDoc[t] || []).push(f); },
};
global.window = {};
global.atob = (b) => Buffer.from(b, "base64").toString("latin1");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new Function(script)();

function tecla(key, target) {
  let prevenido = false;
  const e = { key, target: target || raiz, preventDefault: () => { prevenido = true; } };
  (oyentesDoc.keydown || []).forEach((f) => f(e));
  return prevenido;
}
function estado() {
  const actual = Object.values(elementos).find((e) => e.tagName === "LI" && e.classList.contains("actual"));
  return {
    contador: elementos.contador.textContent,
    deslizador: elementos.deslizador.value,
    linea: actual ? actual.id : null,
    marca: actual ? actual.hijos.marca.textContent : null,
    aria_current: actual ? actual.getAttribute("aria-current") : null,
    svg: elementos.lienzo.innerHTML.slice(0, 4),
    paso_svg: (elementos.lienzo.innerHTML.match(/data-paso="(\d+)"/) || [])[1] || null,
    descripcion: elementos.descripcion.textContent,
    salida: elementos.salida.textContent,
    tema: raiz.getAttribute("data-tema"),
    reproduciendo: elementos["btn-reproducir"].getAttribute("aria-pressed"),
  };
}
setTimeout(() => {
  const r = { inicial: estado() };
  tecla("ArrowRight"); r.derecha = estado();
  tecla("End"); r.fin = estado();
  tecla("ArrowLeft"); r.izquierda = estado();
  tecla("Home"); r.inicio = estado();
  elementos["btn-siguiente"].click(); r.boton_siguiente = estado();
  r.espacio_prevenido = tecla(" ");
  r.espacio = estado();
  tecla(" ");
  r.espacio2 = estado();
  r.flecha_en_select = tecla("ArrowRight", elementos.velocidad);
  elementos["btn-tema"].click(); r.tema = estado().tema;
  elementos.deslizador.value = "0"; elementos.deslizador.disparar("input"); r.deslizador = estado();
  process.stdout.write(JSON.stringify(r));
  process.exit(0);
}, 200);
