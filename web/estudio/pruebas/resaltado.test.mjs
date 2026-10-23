// INV-4215: resaltado sin pérdida de caracteres y siempre escapado.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { escaparHTML, idiomaDelCodigo, resaltarHTML, tokenizar } from "../js/resaltado.js";
import { fileURLToPath } from "node:url";

const LEXICO = {
  palabras: { si: "clave", if: "clave", mientras: "clave", while: "clave", entero: "tipo", int: "tipo", verdadero: "literal", true: "literal", vacio: "tipo", void: "tipo", imprimir: "clave", print: "clave" },
  integradas: ["longitud", "length"],
};
const PARES = [["si", "if"], ["mientras", "while"], ["entero", "int"], ["imprimir", "print"], ["vacio", "void"]];
// fileURLToPath y no .pathname: en Windows .pathname da "/C:/..." (ruta inválida).
const RAIZ = fileURLToPath(new URL("../../../curriculum/", import.meta.url));

function archivos(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
    d.isDirectory() ? archivos(join(dir, d.name)) : d.name.endsWith(".inv") ? [join(dir, d.name)] : [],
  );
}

test("concatenar los tokens devuelve el código exacto (todo el currículo)", () => {
  const lista = archivos(RAIZ);
  assert.ok(lista.length > 200);
  for (const f of lista) {
    const codigo = readFileSync(f, "utf8");
    assert.equal(tokenizar(codigo, LEXICO).map((t) => t.texto).join(""), codigo, f);
  }
});

test("clasifica palabras clave, tipos, literales, textos, números y comentarios", () => {
  const tipos = (c) => tokenizar(c, LEXICO).filter((t) => t.tipo !== "espacio").map((t) => `${t.tipo}:${t.texto}`);
  assert.deepEqual(tipos('si (x) { imprimir("a // b"); } // fin'), [
    "clave:si", "puntuacion:(", "identificador:x", "puntuacion:)", "puntuacion:{", "clave:imprimir",
    "puntuacion:(", 'cadena:"a // b"', "puntuacion:)", "puntuacion:;", "puntuacion:}", "comentario:// fin",
  ]);
  assert.deepEqual(tipos("entero n = 3.5e2;").slice(0, 4), ["tipo:entero", "identificador:n", "operador:=", "numero:3.5e2"]);
  assert.deepEqual(tipos("longitud(a) longitud"), ["integrada:longitud", "puntuacion:(", "identificador:a", "puntuacion:)", "identificador:longitud"]);
});

test("textos y comentarios sin cerrar se colorean hasta donde llegan", () => {
  assert.deepEqual(tokenizar('"abc\nx', LEXICO).map((t) => t.tipo), ["cadena", "espacio", "identificador"]);
  assert.deepEqual(tokenizar("/* abierto\nsi", LEXICO).map((t) => t.tipo), ["comentario"]);
});

test("el HTML resaltado siempre está escapado", () => {
  const html = resaltarHTML('imprimir("<script>alert(1)</script>"); // <b>', LEXICO);
  assert.ok(!html.includes("<script>") && !html.includes("<b>"));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.equal(escaparHTML(`<a href="x">'&`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;");
  assert.ok(resaltarHTML("x\n", LEXICO).endsWith(" "), "un salto final necesita un carácter detrás");
});

test("idiomaDelCodigo cuenta palabras clave exclusivas de cada idioma", () => {
  assert.equal(idiomaDelCodigo("vacio main() { si (x) { imprimir(1); } }", PARES), "es");
  assert.equal(idiomaDelCodigo("void main() { while (true) { print(1); } }", PARES), "en");
  assert.equal(idiomaDelCodigo("main()", PARES), null);
  assert.equal(idiomaDelCodigo('// si mientras\nvoid main() { }', PARES), "en", "los comentarios no cuentan");
});
