// INV-4216: lógica del currículo navegable del estudio (búsqueda,
// comprobación de la salida y progreso), sin DOM.
//
// La comparación es la MISMA que curriculum/runner.py (normalizar y
// primera_diferencia): un ejercicio que el estudio da por resuelto también
// lo da por resuelto el corrector del curso, y viceversa.

/** Minúsculas y sin tildes, para buscar «funcion» y encontrar «Función». */
export function plegar(texto) {
  return String(texto).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

/** Salida comparable: fin de línea Unix y sin saltos de línea finales. */
export function normalizar(texto) {
  return String(texto).replace(/\r\n/g, "\n").replace(/\n+$/, "");
}

/** Número (desde 1) de la primera línea en que difieren dos salidas. */
export function primeraDiferencia(a, b) {
  const la = normalizar(a).split("\n");
  const lb = normalizar(b).split("\n");
  const n = Math.min(la.length, lb.length);
  for (let i = 0; i < n; i++) {
    if (la[i] !== lb[i]) {
      return i + 1;
    }
  }
  return n + 1;
}

/**
 * Compara la salida del estudiante con la esperada. `{ok}` o `{ok: false,
 * linea, obtenido, esperado}` con la primera línea distinta de cada una.
 */
export function comparar(salida, esperado) {
  if (normalizar(salida) === normalizar(esperado)) {
    return { ok: true };
  }
  const linea = primeraDiferencia(salida, esperado);
  const de = (t) => normalizar(t).split("\n")[linea - 1] ?? "";
  return { ok: false, linea, obtenido: de(salida), esperado: de(esperado) };
}

/** Todos los ejercicios del currículo con su nivel, en orden. */
export function ejercicios(curriculo) {
  return curriculo.niveles.flatMap((n) => n.ejercicios.map((e) => ({ ...e, nivel: n.nivel })));
}

/** El ejercicio `id` (p. ej. "N04-E05") o null. */
export function buscarEjercicio(curriculo, id) {
  return ejercicios(curriculo).find((e) => e.id === id) ?? null;
}

/** Ejercicio anterior (-1) o siguiente (+1) a `id`, o null en los extremos. */
export function vecino(curriculo, id, paso) {
  const lista = ejercicios(curriculo);
  const k = lista.findIndex((e) => e.id === id);
  if (k < 0) {
    return null;
  }
  return lista[k + paso] ?? null;
}

/**
 * Niveles cuyos ejercicios coinciden con `consulta` (en título, id,
 * conceptos o enunciado; sin distinguir tildes ni mayúsculas). Los niveles
 * sin coincidencias desaparecen; una consulta vacía lo devuelve todo.
 */
export function filtrar(curriculo, consulta) {
  const q = plegar(consulta).trim();
  if (!q) {
    return curriculo.niveles;
  }
  const palabras = q.split(/\s+/);
  const coincide = (e, n) => {
    const pajar = plegar([e.id, e.titulo, e.enunciado, ...e.conceptos, n.titulo].join(" "));
    return palabras.every((p) => pajar.includes(p));
  };
  return curriculo.niveles
    .map((n) => ({ ...n, ejercicios: n.ejercicios.filter((e) => coincide(e, n)) }))
    .filter((n) => n.ejercicios.length);
}

/** Programa vacío con el que empieza un ejercicio, en el idioma del código. */
export function plantilla(idioma) {
  return idioma === "en" ? "void main() {\n    \n}\n" : "vacio main() {\n    \n}\n";
}

/** Lista de resueltos con `id` añadido (sin duplicados, ordenada). */
export function marcarResuelto(resueltos, id) {
  const conjunto = new Set(Array.isArray(resueltos) ? resueltos.filter((x) => typeof x === "string") : []);
  conjunto.add(id);
  return [...conjunto].sort();
}
