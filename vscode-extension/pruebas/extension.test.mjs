// INV-4241: el cliente de VS Code con los módulos de VS Code simulados.
import { test } from "node:test";
import assert from "node:assert/strict";
import Module, { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const registro = { comandos: {}, mensajes: [], terminal: [], abiertos: [], ejecuciones: [] };
let respuestaCli = { error: null, stdout: "", stderr: "" };

const vscodeFalso = {
  l10n: { t: (m, ...a) => m.replace(/\{(\d+)\}/g, (_, i) => String(a[Number(i)])) },
  workspace: { getConfiguration: () => ({ get: () => "/usr/bin/python3" }) },
  window: {
    activeTextEditor: null,
    terminals: [],
    createTerminal: (op) => ({ name: op.name, show() {}, sendText: (t) => registro.terminal.push(t) }),
    showWarningMessage: (m) => registro.mensajes.push(["aviso", m]),
    showErrorMessage: (m) => registro.mensajes.push(["error", m]),
    showInformationMessage: (m) => registro.mensajes.push(["info", m]),
  },
  commands: {
    registerCommand: (id, f) => {
      registro.comandos[id] = f;
      return { dispose() {} };
    },
    executeCommand: (id, uri) => registro.abiertos.push([id, uri.fsPath]),
  },
  env: { openExternal: (uri) => registro.abiertos.push(["externo", uri.fsPath]) },
  Uri: { file: (p) => ({ fsPath: p }) },
};

class ClienteFalso {
  constructor(id, nombre, servidor, opciones) {
    Object.assign(this, { id, nombre, servidor, opciones });
    ClienteFalso.ultimo = this;
  }
  start() {
    this.iniciado = true;
    return Promise.resolve();
  }
  stop() {
    this.detenido = true;
    return Promise.resolve();
  }
}

const procesoFalso = {
  execFile: (cmd, args, op, cb) => {
    registro.ejecuciones.push([cmd, args, op.cwd]);
    setImmediate(() => cb(respuestaCli.error, respuestaCli.stdout, respuestaCli.stderr));
  },
};

const cargarOriginal = Module._load;
Module._load = function (pedido, ...resto) {
  if (pedido === "vscode") {
    return vscodeFalso;
  }
  if (pedido === "vscode-languageclient/node") {
    return { LanguageClient: ClienteFalso, TransportKind: { stdio: 0 } };
  }
  if (pedido === "child_process") {
    return procesoFalso;
  }
  return cargarOriginal.call(this, pedido, ...resto);
};
const ext = require("../extension.js");

function documento(ruta, lenguaje = "inveniolang") {
  return { document: { languageId: lenguaje, isUntitled: false, save: async () => true, uri: { fsPath: ruta } } };
}

test("activate lanza el servidor LSP real y registra los tres comandos", async () => {
  const contexto = { subscriptions: [] };
  await ext.activate(contexto);
  const c = ClienteFalso.ultimo;
  assert.equal(c.iniciado, true);
  assert.deepEqual(c.servidor.run, { command: "/usr/bin/python3", args: ["-m", "inveniolang.lsp"], transport: 0 });
  assert.deepEqual(c.opciones.documentSelector.map((d) => d.language), ["inveniolang", "inveniolang"]);
  assert.deepEqual(Object.keys(registro.comandos).sort(), ["inveniolang.ejecutar", "inveniolang.flujoSvg", "inveniolang.trazarHtml"]);
  assert.equal(contexto.subscriptions.length, 3);
  await ext.deactivate();
  assert.equal(c.detenido, true);
});

test("los comandos de archivo llaman a la CLI con los argumentos correctos", async () => {
  vscodeFalso.window.activeTextEditor = documento("/tmp/mi prog/pila.inv");
  await registro.comandos["inveniolang.flujoSvg"]();
  assert.deepEqual(registro.ejecuciones.at(-1), [
    "/usr/bin/python3",
    ["-m", "inveniolang.cli", "flujo", "/tmp/mi prog/pila.inv", "--svg", "/tmp/mi prog/pila.flujo.svg"],
    "/tmp/mi prog",
  ]);
  assert.deepEqual(registro.abiertos.at(-1), ["vscode.open", "/tmp/mi prog/pila.flujo.svg"]);
  await registro.comandos["inveniolang.trazarHtml"]();
  assert.deepEqual(registro.abiertos.at(-1), ["externo", "/tmp/mi prog/pila.traza.html"]);
  respuestaCli = { error: new Error("1"), stdout: "", stderr: "[IL-SIN-010] pila.inv:1:1 — falta ;" };
  await registro.comandos["inveniolang.flujoSvg"]();
  assert.deepEqual(registro.mensajes.at(-1)[0], "error");
  assert.match(registro.mensajes.at(-1)[1], /IL-SIN-010/);
  respuestaCli = { error: null, stdout: "", stderr: "" };
});

test("ejecutar usa una terminal (para que leer() pida datos) con la ruta citada", async () => {
  vscodeFalso.window.activeTextEditor = documento("/tmp/a'b.inv");
  await registro.comandos["inveniolang.ejecutar"]();
  assert.equal(registro.terminal.at(-1), ext.lineaEjecutar("/usr/bin/python3", "/tmp/a'b.inv", process.platform));
});

test("sin un archivo InvenioLang abierto solo se avisa", async () => {
  vscodeFalso.window.activeTextEditor = documento("/tmp/x.py", "python");
  const antes = registro.ejecuciones.length;
  await registro.comandos["inveniolang.flujoSvg"]();
  assert.equal(registro.ejecuciones.length, antes);
  assert.equal(registro.mensajes.at(-1)[0], "aviso");
});

test("rutas de salida y comillas seguras en cada sistema", () => {
  assert.equal(ext.rutaSalida("/x/Pila.INV", "flujo.svg"), "/x/Pila.flujo.svg");
  assert.equal(ext.citar("a'b c", "linux"), "'a'\\''b c'");
  assert.equal(ext.citar("a'b c", "win32"), "'a''b c'");
  assert.equal(ext.lineaEjecutar("py", "C:\\p q.inv", "win32"), "& 'py' -m inveniolang.cli 'C:\\p q.inv'");
  assert.throws(() => ext.argumentosCli("otro", "x.inv"));
});
