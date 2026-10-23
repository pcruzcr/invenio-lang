// INV-4241: cliente de VS Code para InvenioLang.
//
// Antes la extensión solo declaraba el lenguaje: no tenía cliente, así que
// el servidor LSP (python -m inveniolang.lsp) nunca se lanzaba y no había
// ni diagnósticos ni resaltado. Este cliente:
//   * arranca el servidor LSP real con vscode-languageclient (diagnósticos
//     IL-XXX-NNN con su arreglo, hover y autocompletado);
//   * registra la gramática TextMate generada del lexer (syntaxes/);
//   * ofrece tres comandos que llaman a la CLI real: ejecutar (en una
//     terminal, para que leer() pueda pedir datos), traza paso a paso en HTML
//     y diagrama de flujo en SVG.
// Los textos para el estudiante están en inglés (por defecto) y en español
// (l10n/bundle.l10n.es.json, package.nls.es.json), según el idioma de VS Code.
"use strict";

const path = require("path");
const { execFile } = require("child_process");
const vscode = require("vscode");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let cliente = null;

/** Ruta de salida junto al programa: «pila.inv» → «pila.traza.html». */
function rutaSalida(archivo, sufijo) {
  const base = archivo.replace(/\.inv$/i, "");
  return `${base}.${sufijo}`;
}

/** Argumentos de la CLI para cada comando que genera un archivo. */
function argumentosCli(comando, archivo) {
  if (comando === "trazarHtml") {
    return ["-m", "inveniolang.cli", "trazar", archivo, "--html", rutaSalida(archivo, "traza.html")];
  }
  if (comando === "flujoSvg") {
    return ["-m", "inveniolang.cli", "flujo", archivo, "--svg", rutaSalida(archivo, "flujo.svg")];
  }
  throw new Error(`comando desconocido: ${comando}`);
}

/**
 * Comillas para la terminal: en Windows (PowerShell) con «'» doblando las
 * internas; en Unix, «'» cerrando y reabriendo. Un nombre de archivo con
 * espacios o comillas no puede convertirse en otra orden.
 */
function citar(texto, plataforma) {
  if (plataforma === "win32") {
    return `'${texto.replace(/'/g, "''")}'`;
  }
  return `'${texto.replace(/'/g, `'\\''`)}'`;
}

/** Línea que se envía a la terminal para ejecutar el programa. */
function lineaEjecutar(python, archivo, plataforma) {
  const prefijo = plataforma === "win32" ? "& " : "";
  return `${prefijo}${citar(python, plataforma)} -m inveniolang.cli ${citar(archivo, plataforma)}`;
}

function python() {
  return vscode.workspace.getConfiguration("inveniolang").get("python") || "python";
}

async function documentoActivo() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "inveniolang") {
    vscode.window.showWarningMessage(vscode.l10n.t("Open an InvenioLang (.inv) file first."));
    return null;
  }
  if (editor.document.isUntitled || !(await editor.document.save())) {
    vscode.window.showWarningMessage(vscode.l10n.t("Save the program to a .inv file first."));
    return null;
  }
  return editor.document.uri.fsPath;
}

async function ejecutar() {
  const archivo = await documentoActivo();
  if (!archivo) {
    return;
  }
  const terminal =
    vscode.window.terminals.find((t) => t.name === "InvenioLang") ||
    vscode.window.createTerminal({ name: "InvenioLang", cwd: path.dirname(archivo) });
  terminal.show();
  terminal.sendText(lineaEjecutar(python(), archivo, process.platform));
}

/** Genera un archivo con la CLI y lo abre (HTML en el navegador, SVG en VS Code). */
function generar(comando) {
  return async () => {
    const archivo = await documentoActivo();
    if (!archivo) {
      return;
    }
    const args = argumentosCli(comando, archivo);
    const salida = args[args.length - 1];
    await new Promise((resolver) => {
      execFile(python(), args, { cwd: path.dirname(archivo), timeout: 60000 }, (error, stdout, stderr) => {
        if (error) {
          const detalle = (stderr || stdout || String(error)).trim().split("\n").slice(-6).join("\n");
          vscode.window.showErrorMessage(vscode.l10n.t("InvenioLang could not generate the file:\n{0}", detalle));
        } else {
          const uri = vscode.Uri.file(salida);
          if (comando === "trazarHtml") {
            vscode.env.openExternal(uri);
          } else {
            vscode.commands.executeCommand("vscode.open", uri);
          }
          vscode.window.showInformationMessage(vscode.l10n.t("Created {0}", path.basename(salida)));
        }
        resolver();
      });
    });
  };
}

function activate(contexto) {
  const servidor = { command: python(), args: ["-m", "inveniolang.lsp"], transport: TransportKind.stdio };
  cliente = new LanguageClient(
    "inveniolang",
    "InvenioLang",
    { run: servidor, debug: servidor },
    { documentSelector: [{ scheme: "file", language: "inveniolang" }, { scheme: "untitled", language: "inveniolang" }] },
  );
  contexto.subscriptions.push(
    vscode.commands.registerCommand("inveniolang.ejecutar", ejecutar),
    vscode.commands.registerCommand("inveniolang.trazarHtml", generar("trazarHtml")),
    vscode.commands.registerCommand("inveniolang.flujoSvg", generar("flujoSvg")),
  );
  return cliente.start().catch((error) => {
    vscode.window.showErrorMessage(
      vscode.l10n.t("Could not start the InvenioLang language server with “{0}”. Check the inveniolang.python setting.\n{1}", python(), String(error)),
    );
  });
}

function deactivate() {
  return cliente ? cliente.stop() : undefined;
}

module.exports = { activate, deactivate, argumentosCli, rutaSalida, lineaEjecutar, citar };
