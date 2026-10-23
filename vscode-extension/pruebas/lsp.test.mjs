// INV-4241: lo que el cliente lanza (python -m inveniolang.lsp) responde de
// verdad por stdio con marcos Content-Length: initialize y diagnósticos.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("../../", import.meta.url));
const PYTHON = process.env.INVENIOLANG_PYTHON || "python3";
const disponible = spawnSync(PYTHON, ["-c", "import inveniolang, ply"], { cwd: RAIZ, env: { ...process.env, PYTHONPATH: RAIZ } }).status === 0;

function marco(obj) {
  const cuerpo = Buffer.from(JSON.stringify(obj), "utf8");
  return Buffer.concat([Buffer.from(`Content-Length: ${cuerpo.length}\r\n\r\n`, "ascii"), cuerpo]);
}

function leerMarcos(buffer) {
  const mensajes = [];
  let resto = buffer;
  for (;;) {
    const fin = resto.indexOf("\r\n\r\n");
    if (fin < 0) {
      break;
    }
    const largo = Number(/Content-Length: (\d+)/i.exec(resto.subarray(0, fin).toString("ascii"))[1]);
    if (resto.length < fin + 4 + largo) {
      break;
    }
    mensajes.push(JSON.parse(resto.subarray(fin + 4, fin + 4 + largo).toString("utf8")));
    resto = resto.subarray(fin + 4 + largo);
  }
  return mensajes;
}

test("initialize + didOpen devuelven capacidades y diagnósticos IL", { skip: !disponible && `sin ${PYTHON} con inveniolang y ply` }, async () => {
  const proc = spawn(PYTHON, ["-m", "inveniolang.lsp"], { cwd: RAIZ, env: { ...process.env, PYTHONPATH: RAIZ } });
  let salida = Buffer.alloc(0);
  proc.stdout.on("data", (d) => (salida = Buffer.concat([salida, d])));
  const uri = "file:///tmp/prueba.inv";
  proc.stdin.write(marco({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} }));
  proc.stdin.write(marco({ jsonrpc: "2.0", method: "textDocument/didOpen", params: { textDocument: { uri, languageId: "inveniolang", version: 1, text: 'vacio main() { entero x = "a"; }' } } }));
  proc.stdin.write(marco({ jsonrpc: "2.0", id: 2, method: "shutdown" }));
  proc.stdin.write(marco({ jsonrpc: "2.0", method: "exit" }));
  proc.stdin.end();
  const codigo = await new Promise((r) => proc.on("close", r));
  assert.equal(codigo, 0);
  const mensajes = leerMarcos(salida);
  assert.equal(mensajes[0].id, 1);
  assert.equal(mensajes[0].result.capabilities.textDocumentSync, 1);
  const diag = mensajes.find((m) => m.method === "textDocument/publishDiagnostics");
  assert.equal(diag.params.uri, uri);
  assert.equal(diag.params.diagnostics[0].code, "IL-TIPO-001");
  assert.equal(diag.params.diagnostics[0].range.start.line, 0);
  assert.ok(mensajes.some((m) => m.id === 2 && m.result === null));
});
