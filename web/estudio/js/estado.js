// INV-4217: estado del estudio como reductor puro + tienda mínima.
//
// Por qué un reductor: el estudio tiene muchas vistas que dependen de lo
// mismo (el código, los diagnósticos, el estado del motor, el idioma) y
// varias fuentes que lo cambian (teclado, bloques, Worker, currículo). Con
// un único `reducir(estado, accion)` puro, cada transición se prueba en Node
// sin DOM (pruebas/estado.test.mjs) y la persistencia sabe exactamente qué
// guardar (`persistible`).

export const TEMAS = Object.freeze(["sistema", "claro", "oscuro"]);
export const PESTANAS = Object.freeze(["salida", "errores", "bloques", "flujo", "uml", "pasos"]);
export const ESTADOS_MOTOR = Object.freeze(["cargando", "listo", "ocupado", "sin_red", "sin_paquete", "error"]);

export function estadoInicial(previo = {}) {
  const base = {
    idioma: "es",
    tema: "sistema",
    codigo: "",
    entrada: "",
    nombre: "programa.inv",
    modificado: false,
    motor: "cargando",
    diagnosticos: [],
    salida: "",
    resultado: null, // null (sin ejecutar) | "ok" | "error"
    pestana: "salida",
    ejercicio: null,
    idiomaCurriculo: "es",
    resueltos: [],
  };
  const e = { ...base };
  // Solo se aceptan del almacenamiento valores con la forma correcta: un
  // localStorage editado a mano o de otra versión no puede romper la página.
  for (const clave of ["codigo", "entrada", "nombre"]) {
    if (typeof previo[clave] === "string") {
      e[clave] = previo[clave];
    }
  }
  if (["es", "en"].includes(previo.idioma)) {
    e.idioma = previo.idioma;
  }
  if (["es", "en"].includes(previo.idiomaCurriculo)) {
    e.idiomaCurriculo = previo.idiomaCurriculo;
  }
  if (TEMAS.includes(previo.tema)) {
    e.tema = previo.tema;
  }
  if (PESTANAS.includes(previo.pestana)) {
    e.pestana = previo.pestana;
  }
  if (typeof previo.ejercicio === "string" || previo.ejercicio === null) {
    e.ejercicio = previo.ejercicio ?? null;
  }
  if (Array.isArray(previo.resueltos)) {
    e.resueltos = previo.resueltos.filter((x) => typeof x === "string");
  }
  return e;
}

/** Lo que se guarda entre sesiones (nunca resultados ni el estado del motor). */
export function persistible(e) {
  return {
    idioma: e.idioma,
    tema: e.tema,
    codigo: e.codigo,
    entrada: e.entrada,
    nombre: e.nombre,
    pestana: e.pestana,
    ejercicio: e.ejercicio,
    idiomaCurriculo: e.idiomaCurriculo,
    resueltos: e.resueltos,
  };
}

export function reducir(e, a) {
  switch (a.tipo) {
    case "codigo":
      if (a.codigo === e.codigo) {
        return e;
      }
      return { ...e, codigo: a.codigo, modificado: true };
    case "entrada":
      return { ...e, entrada: a.entrada };
    case "idioma":
      return ["es", "en"].includes(a.idioma) ? { ...e, idioma: a.idioma } : e;
    case "tema":
      return TEMAS.includes(a.tema) ? { ...e, tema: a.tema } : e;
    case "motor":
      return ESTADOS_MOTOR.includes(a.estado) ? { ...e, motor: a.estado } : e;
    case "pestana":
      return PESTANAS.includes(a.pestana) ? { ...e, pestana: a.pestana } : e;
    case "diagnosticos":
      return { ...e, diagnosticos: a.diagnosticos };
    case "resultado":
      return {
        ...e,
        salida: a.salida,
        diagnosticos: a.diagnosticos,
        resultado: a.ok ? "ok" : "error",
      };
    case "abrir":
      return {
        ...e,
        codigo: a.codigo,
        nombre: a.nombre,
        modificado: false,
        diagnosticos: [],
        salida: "",
        resultado: null,
        ejercicio: a.ejercicio ?? null,
        entrada: a.entrada ?? e.entrada,
      };
    case "guardado":
      return { ...e, nombre: a.nombre, modificado: false };
    case "idiomaCurriculo":
      return ["es", "en"].includes(a.idioma) ? { ...e, idiomaCurriculo: a.idioma } : e;
    case "resueltos":
      return { ...e, resueltos: a.resueltos };
    default:
      throw new Error(`acción desconocida: ${a.tipo}`);
  }
}

/** Tienda: estado actual, `despachar(accion)` y suscriptores. */
export function crearTienda(inicial) {
  let estado = inicial;
  const oyentes = new Set();
  return {
    obtener: () => estado,
    despachar(accion) {
      const previo = estado;
      estado = reducir(estado, accion);
      if (estado !== previo) {
        for (const f of oyentes) {
          f(estado, previo);
        }
      }
      return estado;
    },
    suscribir(f) {
      oyentes.add(f);
      return () => oyentes.delete(f);
    },
  };
}
