# InvenioLang para VS Code

Extensión para escribir programas InvenioLang en español o en inglés.

* **Diagnósticos** mientras escribes, con el código `IL-XXX-NNN` y el arreglo
  sugerido, **hover** sobre los códigos de error y **autocompletado** de
  palabras clave y funciones integradas: es el servidor LSP real
  (`python -m inveniolang.lsp`), lanzado con `vscode-languageclient`.
* **Resaltado** de las palabras clave de los dos idiomas (`si`/`if`,
  `mientras`/`while`…), textos, números, comentarios y funciones integradas.
  La gramática (`syntaxes/inveniolang.tmLanguage.json`) se genera del lexer con
  `python scripts/gramatica_vscode.py`; una prueba exige que esté al día.
* **Comandos** (paleta de comandos, categoría *InvenioLang*):
  * *Ejecutar programa*: en una terminal integrada, para que `leer` pida datos.
  * *Traza paso a paso (HTML)*: `inveniolang trazar archivo.inv --html …` y
    abre el reproductor en el navegador.
  * *Diagrama de flujo (SVG)*: `inveniolang flujo archivo.inv --svg …` y lo
    abre en VS Code.
* Textos en inglés y en español según el idioma de VS Code (`package.nls*.json`,
  `l10n/`).

## Requisitos e instalación

1. Python 3.10+ con InvenioLang instalado (`pip install -e .` en la raíz del
   proyecto). Si `python` no es ese intérprete, indica su ruta en el ajuste
   **`inveniolang.python`**.
2. Empaquetar e instalar la extensión:

   ```bash
   cd vscode-extension
   npm install                 # vscode-languageclient
   npx @vscode/vsce package    # genera inveniolang-vscode-0.2.0.vsix
   code --install-extension inveniolang-vscode-0.2.0.vsix
   ```

## Pruebas

`npm test` (es `node --test pruebas/*.test.mjs`; también lo lanza
`tests/web/test_estudio_node.py`):

* `extension.test.mjs`: `activate` con VS Code y `vscode-languageclient`
  simulados: servidor LSP lanzado con el intérprete configurado, los tres
  comandos registrados, argumentos de la CLI, terminal con rutas citadas de
  forma segura, avisos sin archivo abierto y errores de la CLI.
* `gramatica.test.mjs`: todas las expresiones compilan en JavaScript y un
  mini-motor TextMate colorea correctamente ejemplos en los dos idiomas y todo
  el currículo.
* `lsp.test.mjs`: arranca el servidor real por stdio con marcos
  `Content-Length` y comprueba `initialize`, los diagnósticos de `didOpen` y
  `shutdown`/`exit`.

---

**English:** real LSP client (diagnostics with fixes, hover, completion),
Spanish/English TextMate grammar generated from the lexer, and *Run*,
*Step-by-step trace (HTML)* and *Flowchart (SVG)* commands. Set
`inveniolang.python` to the interpreter that has InvenioLang installed.
