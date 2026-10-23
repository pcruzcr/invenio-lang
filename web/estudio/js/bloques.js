// INV-4225: lógica pura del lienzo de bloques del estudio (sin DOM).
//
// El estudio consume el contrato JSON v1 de inveniolang/bloques
// (docs/bloques.md). Las operaciones de edición, el encaje tipado y la
// validación los hace Python (puente «bloques_*», inveniolang/web/
// bloques_web.py): son las mismas que usa la GUI Qt y no se duplican aquí.
// Este módulo solo sabe recorrer la VISTA que devuelve el puente (el árbol
// ya resuelto en piezas dibujables), ubicar bloques y zonas, convertir los
// índices «sin el bloque» de un movimiento en la zona dibujada, generar el
// CSS de las categorías y llevar el historial de deshacer/rehacer.
//
// Vista de un bloque: {id, tipo, nombre, categoria, forma, salida, linea,
//   rotulo, cabecera: [pieza], bocas: [{nombre, rotulo, etiqueta, hijos}]}
// Pieza: {t: "texto", texto} | {t: "campo", nombre, clase, valor, texto,
//   etiqueta, opciones?} | {t: "hueco", nombre, etiqueta, acepta, hijo} |
//   {t: "lista", nombre, etiqueta, hijos}

/** Hijos de un bloque en orden de lectura: huecos y listas en línea, luego bocas. */
export function* hijos(v) {
  for (const p of v.cabecera) {
    if (p.t === "hueco" && p.hijo) {
      yield { bloque: p.hijo, parte: p.nombre, indice: null };
    } else if (p.t === "lista") {
      for (const [k, h] of p.hijos.entries()) {
        yield { bloque: h, parte: p.nombre, indice: k };
      }
    }
  }
  for (const b of v.bocas) {
    for (const [k, h] of b.hijos.entries()) {
      yield { bloque: h, parte: b.nombre, indice: k };
    }
  }
}

/** Todos los bloques de la vista en preorden (el orden de navegación con flechas). */
export function* recorrer(vista) {
  for (const v of vista) {
    yield v;
    for (const h of hijos(v)) {
      yield* recorrer([h.bloque]);
    }
  }
}

/**
 * Dónde está el bloque `id`: {bloque, padre (id o null), parte, indice}
 * (`indice` null en un hueco). null si no existe.
 */
export function ubicar(vista, id) {
  for (const [k, v] of vista.entries()) {
    if (v.id === id) {
      return { bloque: v, padre: null, parte: "programa", indice: k };
    }
  }
  for (const v of recorrer(vista)) {
    for (const h of hijos(v)) {
      if (h.bloque.id === id) {
        return { bloque: h.bloque, padre: v.id, parte: h.parte, indice: h.indice };
      }
    }
  }
  return null;
}

/** Clave única de un sitio (padre|parte|índice) para buscar su zona dibujada. */
export function claveZona({ padre, parte, indice }) {
  return `${padre ?? ""}|${parte}|${indice ?? ""}`;
}

/**
 * Un destino de «mover» viene con el índice contado SIN el bloque (como
 * edicion.mover); la zona dibujada cuenta CON él. En la misma lista, tras su
 * sitio original, hay una zona más.
 */
export function zonaDeDestino(vista, idMovido, destino) {
  if (destino.indice === null || destino.indice === undefined || !idMovido) {
    return claveZona(destino);
  }
  const u = ubicar(vista, idMovido);
  if (u && u.indice !== null && (u.padre ?? null) === (destino.padre ?? null) && u.parte === destino.parte && destino.indice >= u.indice) {
    return claveZona({ ...destino, indice: destino.indice + 1 });
  }
  return claveZona(destino);
}

/** Destino de «mover» a partir de una zona dibujada (inversa de zonaDeDestino). */
export function destinoDeZona(vista, idMovido, zona) {
  const destino = { padre: zona.padre ?? null, parte: zona.parte, indice: zona.indice ?? null };
  if (!idMovido || destino.indice === null) {
    return destino;
  }
  const u = ubicar(vista, idMovido);
  if (u && u.indice !== null && (u.padre ?? null) === destino.padre && u.parte === destino.parte && destino.indice > u.indice) {
    return { ...destino, indice: destino.indice - 1 };
  }
  return destino;
}

/** ¿La zona está dentro del propio bloque que se mueve (o es su sitio actual)? */
export function zonaPropia(vista, idMovido, zona) {
  const u = ubicar(vista, idMovido);
  if (!u) {
    return false;
  }
  for (const b of recorrer([u.bloque])) {
    if (b.id === zona.padre) {
      return true;
    }
  }
  if ((u.padre ?? null) !== (zona.padre ?? null) || u.parte !== zona.parte) {
    return false;
  }
  return u.indice === null || zona.indice === u.indice || zona.indice === u.indice + 1;
}

/** Nombre accesible de un bloque («mientras: mientras i < 3»). */
export function etiqueta(v) {
  return v.rotulo && v.rotulo !== v.nombre ? `${v.nombre}: ${v.rotulo}` : v.nombre;
}

const COLOR = /^#[0-9a-fA-F]{3,8}$/;

/**
 * CSS de las categorías a partir de la paleta del puente: cada una con sus
 * colores claro y oscuro (los del catálogo de bloques, AAA probados en
 * Python). Un color que no es hexadecimal se descarta: el texto va dentro
 * de una hoja de estilos y no debe poder inyectar nada.
 */
export function cssCategorias(paleta) {
  const reglas = { claro: [], oscuro: [] };
  for (const c of paleta) {
    if (!/^[a-z_]+$/.test(c.id)) {
      continue;
    }
    for (const tema of ["claro", "oscuro"]) {
      const col = c[tema];
      if (!col || ![col.relleno, col.texto, col.borde].every((x) => COLOR.test(x))) {
        continue;
      }
      reglas[tema].push(`.cat-${c.id}{--cat-fondo:${col.relleno};--cat-texto:${col.texto};--cat:${col.borde}}`);
    }
  }
  const oscuro = reglas.oscuro.map((r) => `:root[data-tema="oscuro"] ${r}`).join("");
  const sistema = reglas.oscuro.map((r) => `:root[data-tema="sistema"] ${r}`).join("");
  return `${reglas.claro.join("")}${oscuro}@media (prefers-color-scheme: dark){${sistema}}`;
}

// ------------------------------------------------------------------ historial

/**
 * Historial inmutable de modelos para deshacer/rehacer. `limite` evita que
 * una sesión larga acumule memoria sin fin.
 */
export function crearHistorial(actual, limite = 100) {
  return { pasado: [], actual, futuro: [], limite };
}

export function empujar(h, nuevo) {
  return { ...h, pasado: [...h.pasado, h.actual].slice(-h.limite), actual: nuevo, futuro: [] };
}

export function deshacer(h) {
  if (!h.pasado.length) {
    return h;
  }
  return { ...h, pasado: h.pasado.slice(0, -1), actual: h.pasado[h.pasado.length - 1], futuro: [h.actual, ...h.futuro] };
}

export function rehacer(h) {
  if (!h.futuro.length) {
    return h;
  }
  return { ...h, pasado: [...h.pasado, h.actual], actual: h.futuro[0], futuro: h.futuro.slice(1) };
}
