// INV-4240: la gramática TextMate colorea programas en español e inglés.
// Mini-motor TextMate (patrones match/begin/end con include) sobre RegExp de
// JavaScript: además prueba que ningún patrón usa sintaxis exclusiva de
// Oniguruma que un navegador o Monaco no entenderían.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const G = JSON.parse(readFileSync(new URL("../syntaxes/inveniolang.tmLanguage.json", import.meta.url), "utf8"));
const CURRICULO = new URL("../../curriculum/", import.meta.url).pathname;

function aplanar(patrones) {
  return patrones.flatMap((p) => (p.include ? aplanar(G.repository[p.include.slice(1)].patterns) : [p]));
}
const PATRONES = aplanar(G.patterns);

function tokenizar(linea) {
  const tokens = [];
  let i = 0;
  while (i < linea.length) {
    let mejor = null;
    for (const p of PATRONES) {
      const re = new RegExp(p.match ?? p.begin, "g");
      re.lastIndex = i;
      const m = re.exec(linea);
      if (m && m[0].length && (!mejor || m.index < mejor.m.index)) {
        mejor = { p, m };
      }
    }
    if (!mejor) {
      break;
    }
    let fin = mejor.m.index + mejor.m[0].length;
    if (mejor.p.begin) {
      const internos = (mejor.p.patterns || []).map((q) => new RegExp(q.match, "y"));
      const cierre = new RegExp(mejor.p.end, "y");
      while (fin < linea.length) {
        cierre.lastIndex = fin;
        if (cierre.exec(linea)) {
          fin = cierre.lastIndex;
          break;
        }
        const escape = internos.find((r) => ((r.lastIndex = fin), r.exec(linea)));
        fin = escape ? escape.lastIndex : fin + 1;
      }
    }
    tokens.push([linea.slice(mejor.m.index, fin), mejor.p.name.replace(/\.inveniolang$/, "")]);
    i = fin;
  }
  return tokens;
}

const ambito = (linea, texto) => tokenizar(linea).find(([t]) => t === texto)?.[1];

test("todas las expresiones compilan en JavaScript", () => {
  for (const p of PATRONES) {
    for (const clave of ["match", "begin", "end"]) {
      if (p[clave]) {
        assert.doesNotThrow(() => new RegExp(p[clave]), `${p.name}: ${p[clave]}`);
      }
    }
  }
  assert.equal(G.scopeName, "source.inveniolang");
});

test("palabras clave, tipos y literales en los dos idiomas", () => {
  for (const [es, en] of [["mientras", "while"], ["si", "if"], ["para_cada", "foreach"], ["retornar", "return"]]) {
    assert.equal(ambito(`${es} (x)`, es), "keyword.control");
    assert.equal(ambito(`${en} (x)`, en), "keyword.control");
  }
  assert.equal(ambito("entero n = 0;", "entero"), "storage.type");
  assert.equal(ambito("int n = 0;", "int"), "storage.type");
  assert.equal(ambito("clase Pila {", "clase"), "storage.type.class");
  assert.equal(ambito("x = verdadero;", "verdadero"), "constant.language");
  assert.equal(ambito("este.n = 1;", "este"), "variable.language");
  assert.equal(ambito("y = absoluto(a);", "absoluto"), "support.function.builtin");
  assert.equal(ambito("y = abs(a);", "abs"), "support.function.builtin");
  assert.equal(ambito("absoluto = 3;", "absoluto"), undefined, "solo es integrada si se llama");
  assert.equal(ambito("si_no = 1;", "si"), undefined, "\\b: no colorea dentro de identificadores");
});

test("textos, escapes y comentarios no colorean lo de dentro", () => {
  const t = tokenizar('imprimir("si \\"mientras\\" // no"); // si fin');
  assert.equal(t[0][1], "support.function.io");
  assert.ok(t.some(([s, a]) => a === "string.quoted.double" && s === '"si \\"mientras\\" // no"'));
  assert.ok(t.some(([s, a]) => a === "comment.line.double-slash" && s === "// si fin"));
  assert.equal(ambito("x = 3.5e2;", "3.5e2"), "constant.numeric");
});

test("todo el currículo se tokeniza sin colgarse y con palabras clave", () => {
  const dir = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? dir(join(d, e.name)) : e.name.endsWith(".inv") ? [join(d, e.name)] : []));
  let claves = 0;
  for (const f of dir(CURRICULO)) {
    for (const linea of readFileSync(f, "utf8").split("\n")) {
      claves += tokenizar(linea).filter(([, a]) => a.startsWith("keyword.control")).length;
    }
  }
  assert.ok(claves > 1000, `palabras clave coloreadas: ${claves}`);
});
