// INV-4213: textos de la interfaz del estudio en español e inglés.
//
// Los textos NO se escriben en JavaScript: vienen de generado/textos.json,
// que scripts/empaquetar_web.py extrae de las claves WEB.* del catálogo
// inveniolang/i18n (la misma fuente que la GUI Qt y la CLI). Este módulo
// solo elige el idioma y rellena las plantillas, que usan la sintaxis de
// str.format de Python con argumentos con nombre ({n}, y {{ }} literales).

export const IDIOMAS = Object.freeze(["es", "en"]);

/** Rellena una plantilla estilo str.format: "{n} de {total}", "{{" → "{". */
export function interpolar(plantilla, args = {}) {
  return plantilla.replace(/\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (todo, nombre) => {
    if (todo === "{{") {
      return "{";
    }
    if (todo === "}}") {
      return "}";
    }
    return Object.prototype.hasOwnProperty.call(args, nombre) ? String(args[nombre]) : todo;
  });
}

/** "en-US" → "en"; null si no es un idioma soportado. */
export function normalizar(valor) {
  if (typeof valor !== "string") {
    return null;
  }
  const base = valor.trim().toLowerCase().split(/[-_.]/)[0];
  return IDIOMAS.includes(base) ? base : null;
}

/**
 * Idioma inicial: el guardado por el estudiante; si no, el primero de los
 * idiomas del navegador que soportamos; si no, español.
 */
export function idiomaInicial(guardado, idiomasNavegador = []) {
  const elegido = normalizar(guardado);
  if (elegido) {
    return elegido;
  }
  for (const v of idiomasNavegador) {
    const n = normalizar(v);
    if (n) {
      return n;
    }
  }
  return "es";
}

/**
 * Traductor para `idioma` sobre el catálogo `{es: {...}, en: {...}}`. Una
 * clave que falta se devuelve tal cual entre corchetes, visible pero sin
 * romper la página (las pruebas garantizan que no ocurre).
 */
export function crearTraductor(catalogo, idioma) {
  const tabla = catalogo[idioma] || catalogo.es || {};
  return (clave, args) => {
    const plantilla = tabla[clave];
    return plantilla === undefined ? `[${clave}]` : interpolar(plantilla, args);
  };
}
