// INV-4214: almacenamiento local del estudio (preferencias, borrador y
// programas guardados) sobre localStorage.
//
// Por qué todo con try/catch y un almacenamiento inyectable: localStorage
// lanza excepciones en navegación privada de algunos navegadores, con la
// cuota llena o si el usuario bloqueó los datos del sitio; el estudio debe
// seguir funcionando igual (solo sin recordar nada) y decirlo. Inyectar el
// `Storage` permite probar todos esos fallos en Node (pruebas/almacen.test.mjs).

const PREFIJO = "inveniolang.estudio.v1.";
export const MAX_PROGRAMAS = 50;

/** Nombre de archivo seguro: sin rutas ni caracteres de control, con .inv. */
export function nombreSeguro(nombre) {
  let limpio = String(nombre ?? "")
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_")
    .trim()
    .slice(0, 80);
  if (!limpio || limpio === "." || limpio === "..") {
    limpio = "programa";
  }
  return limpio.toLowerCase().endsWith(".inv") ? limpio : `${limpio}.inv`;
}

/**
 * Almacén sobre `storage` (por defecto, globalThis.localStorage si existe).
 * Cada operación devuelve un resultado y nunca lanza.
 */
export function crearAlmacen(storage) {
  let s = storage;
  if (s === undefined) {
    try {
      s = globalThis.localStorage ?? null;
    } catch {
      s = null; // acceder a la propiedad ya puede lanzar SecurityError
    }
  }

  function leer(clave, defecto) {
    if (!s) {
      return defecto;
    }
    try {
      const crudo = s.getItem(PREFIJO + clave);
      return crudo === null ? defecto : JSON.parse(crudo);
    } catch {
      return defecto; // JSON corrupto o acceso denegado: como si no hubiera nada
    }
  }

  function escribir(clave, valor) {
    if (!s) {
      return false;
    }
    try {
      s.setItem(PREFIJO + clave, JSON.stringify(valor));
      return true;
    } catch {
      return false; // QuotaExceededError o acceso denegado
    }
  }

  /** Programas guardados: [{nombre, codigo, fecha}] del más reciente al más antiguo. */
  function programas() {
    const lista = leer("programas", []);
    if (!Array.isArray(lista)) {
      return [];
    }
    return lista.filter(
      (p) => p && typeof p.nombre === "string" && typeof p.codigo === "string" && typeof p.fecha === "number",
    );
  }

  /** Guarda (o reemplaza) un programa. `{ok, nombre, lleno}`. */
  function guardarPrograma(nombre, codigo, fecha = Date.now()) {
    const limpio = nombreSeguro(nombre);
    const resto = programas().filter((p) => p.nombre !== limpio);
    const lista = [{ nombre: limpio, codigo, fecha }, ...resto];
    const lleno = lista.length > MAX_PROGRAMAS;
    const ok = escribir("programas", lista.slice(0, MAX_PROGRAMAS));
    return { ok, nombre: limpio, lleno };
  }

  function borrarPrograma(nombre) {
    return escribir(
      "programas",
      programas().filter((p) => p.nombre !== nombre),
    );
  }

  return {
    disponible: () => {
      if (!s) {
        return false;
      }
      try {
        s.setItem(PREFIJO + "prueba", "1");
        s.removeItem(PREFIJO + "prueba");
        return true;
      } catch {
        return false;
      }
    },
    leer,
    escribir,
    programas,
    guardarPrograma,
    borrarPrograma,
  };
}
