// INV-4215: resaltado de sintaxis del editor del estudio.
//
// Por qué un tokenizador en JavaScript y no el lexer de Python: el
// resaltado tiene que responder en cada pulsación y existir antes de que
// Pyodide termine de cargar (varios segundos la primera vez). Las palabras
// clave y las funciones integradas NO se copian a mano: llegan en
// generado/lexico.json, extraídas del lexer real por empaquetar_web.py.
// Las reglas léxicas (comentarios, textos, números, identificadores) son las
// de inveniolang/lexer.py; un texto o comentario sin cerrar se colorea hasta
// donde llega, igual que lo marcaría el lexer.

const PATRONES = [
  ["comentario", /\/\/[^\n]*/y],
  ["comentario", /\/\*[\s\S]*?(?:\*\/|$)/y],
  ["cadena", /"(?:[^"\\\n]|\\.)*(?:"|$)/my],
  ["cadena", /'(?:[^'\\\n]|\\.)*(?:'|$)/my],
  ["numero", /\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/y],
  ["identificador", /[A-Za-z_][A-Za-z0-9_]*/y],
  ["espacio", /\s+/y],
  ["operador", /\?\.|\?\?|\+\+|--|[+\-*/%]=|==|!=|<=|>=|&&|\|\||<<|>>|[-+*/%=<>!&|^~?:]/y],
  ["puntuacion", /[{}()[\];,.]/y],
];

/**
 * Divide `codigo` en `[{tipo, texto}]`. `lexico` = `{palabras: {lexema:
 * "clave"|"tipo"|"literal"}, integradas: [nombres]}`. Concatenar los textos
 * devuelve exactamente el código (no se pierde ni un carácter).
 */
export function tokenizar(codigo, lexico) {
  const palabras = lexico?.palabras ?? {};
  const integradas = new Set(lexico?.integradas ?? []);
  const tokens = [];
  let i = 0;
  while (i < codigo.length) {
    let tipo = "otro";
    let texto = codigo[i];
    for (const [nombre, re] of PATRONES) {
      re.lastIndex = i;
      const m = re.exec(codigo);
      if (m && m[0].length) {
        tipo = nombre;
        texto = m[0];
        break;
      }
    }
    if (tipo === "identificador") {
      if (Object.prototype.hasOwnProperty.call(palabras, texto)) {
        tipo = palabras[texto];
      } else if (integradas.has(texto) && codigo.slice(i + texto.length).trimStart().startsWith("(")) {
        tipo = "integrada"; // como el traductor: solo cuenta como integrada si se llama
      }
    }
    const ultimo = tokens[tokens.length - 1];
    if (ultimo && ultimo.tipo === tipo && (tipo === "espacio" || tipo === "otro")) {
      ultimo.texto += texto;
    } else {
      tokens.push({ tipo, texto });
    }
    i += texto.length;
  }
  return tokens;
}

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escapa texto para insertarlo como HTML. */
export function escaparHTML(texto) {
  return String(texto).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

const SIN_CLASE = new Set(["espacio", "identificador", "puntuacion", "otro"]);

/** HTML resaltado (`<span class="tk-…">`) del código, siempre escapado. */
export function resaltarHTML(codigo, lexico) {
  let html = "";
  for (const { tipo, texto } of tokenizar(codigo, lexico)) {
    const seguro = escaparHTML(texto);
    html += SIN_CLASE.has(tipo) ? seguro : `<span class="tk-${tipo}">${seguro}</span>`;
  }
  // Un salto final necesita un carácter detrás para que el <pre> mida igual
  // que el <textarea> que tiene encima.
  return codigo.endsWith("\n") ? `${html} ` : html;
}

/** Idioma de las palabras clave de un código ("es", "en" o null si empata). */
export function idiomaDelCodigo(codigo, pares) {
  const cuenta = { es: 0, en: 0 };
  const es = new Set(pares.map((p) => p[0]));
  const en = new Set(pares.map((p) => p[1]));
  for (const { tipo, texto } of tokenizar(codigo, { palabras: {}, integradas: [] })) {
    if (tipo !== "identificador") {
      continue;
    }
    if (es.has(texto) && !en.has(texto)) {
      cuenta.es++;
    } else if (en.has(texto) && !es.has(texto)) {
      cuenta.en++;
    }
  }
  if (cuenta.es === cuenta.en) {
    return null;
  }
  return cuenta.es > cuenta.en ? "es" : "en";
}
