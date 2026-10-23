# InvenioLang en la web

Esta carpeta contiene el **estudio web** (`estudio/`), que ejecuta el
compilador real de InvenioLang en el navegador con
[Pyodide](https://pyodide.org) (CPython compilado a WebAssembly), sin instalar
nada. La configuración Docker para un aula compartida está en `../docker/`.

> `web/pyodide.html` (una página que solo cargaba Pyodide y mostraba «Web IDE
> listo») se retiró en INV-4201: el estudio la sustituye por completo.

## Estudio web (`web/estudio/`)

HTML + CSS + JavaScript con módulos ES, **sin frameworks ni paso de
compilación**. Ofrece:

| Parte | Qué hace |
|---|---|
| Editor | Resaltado (palabras clave del lexer real, en español y en inglés), números de línea, sangría automática, marca de las líneas con error, revisión mientras se escribe. `Tab` sangra; `Esc` y luego `Tab` sale del editor. |
| Ejecutar | Con la entrada del programa (una línea por cada `leer`), salida parcial aunque haya error, botón **Detener** (el intérprete corre en un *Web Worker*: un ciclo infinito nunca congela la página). |
| Errores | Cada diagnóstico `IL-XXX-NNN` con su línea (botón que lleva el cursor) y la explicación de `error_explainer` (qué pasa, por qué, así falla / así funciona, cómo arreglarlo) en el idioma de la interfaz. |
| Bloques | Editor de bloques sobre el contrato de `inveniolang/bloques` (`docs/bloques.md`): paleta por categorías (color + icono + forma), arrastrar y soltar desde la paleta, entre sitios y a la papelera, con el motivo bilingüe de por qué no encaja; edición de campos; envolver; deshacer/rehacer; zoom; y **todo con teclado**. Cada cambio válido reescribe el código del editor. |
| Diagrama de flujo / UML | Los SVG accesibles de la fase 3 (por subrutina o todos), con su descripción textual y descarga (SVG, PlantUML). |
| Paso a paso | El reproductor de la fase 2 incrustado y aislado (`iframe sandbox`), con el tema del estudio. |
| Traductor | Convierte el programa entre palabras clave en español e inglés (`traductor.py`). |
| Currículo | Los 13 niveles y 133 ejercicios de `curriculum/es` y `curriculum/en`: búsqueda sin tildes, enunciado, objetivos, pistas graduadas, solución de referencia, **Comprobar** (misma comparación que `curriculum/runner.py`), ejercicio anterior/siguiente y progreso. |
| Archivos | Abrir `.inv` del equipo, descargar, guardar y abrir en el navegador (`localStorage`, con todos los accesos en `try/catch`: en navegación privada o con el almacenamiento lleno lo dice y sigue funcionando). |
| Interfaz | Español e inglés (textos del catálogo `inveniolang/i18n`, claves `WEB.*`), tema claro, oscuro o del sistema. |

### Uso

```bash
python scripts/empaquetar_web.py         # genera web/estudio/generado/
python -m http.server -d web/estudio 8000
# abrir http://localhost:8000/
```

`generado/` no se versiona: se reconstruye con el script (determinista;
`--comprobar` termina con 1 si está desactualizado, útil en CI). Si falta, la
página lo dice en los dos idiomas. Para publicar el estudio basta copiar
`web/estudio/` completo (con `generado/`) a cualquier servidor estático.

Pyodide se descarga del CDN oficial (`cdn.jsdelivr.net/pyodide/v0.29.3/full/`).
Sin conexión, el estudio lo explica, deja escribir y guardar, y ofrece
«Reintentar». Para un aula sin Internet se puede servir una copia local de
Pyodide (el paquete npm `pyodide@0.29.3`) en el mismo servidor y abrir
`index.html?pyodide=/ruta/a/pyodide/`; por seguridad solo se aceptan rutas
del **mismo origen**.

### Arquitectura

```
index.html ─ app.js ──┬─ editor.js, resaltado.js        (editor, sin Pyodide)
                      ├─ estado.js, i18n.js, almacen.js, curriculo.js (lógica pura)
                      ├─ vista_bloques.js ─ bloques.js   (lienzo; lógica pura)
                      └─ motor.js ══ Web Worker: trabajador.js ══ Pyodide
                                         └─ inveniolang.web.puente.llamar(JSON) → JSON
```

* **Puente** (`inveniolang/web/puente.py`): único punto de entrada desde
  JavaScript, texto JSON de ida y vuelta (`{"metodo", "args"}` →
  `{"ok", "datos"|"error"}`), nunca lanza. Métodos: `info`, `ejecutar`,
  `revisar`, `traducir`, `formatear`, `flujo`, `uml`, `traza`, `bloques`,
  `bloques_estado`, `bloques_paleta`, `bloques_operar`, `bloques_encaje`,
  `bloques_destinos`. `CONTRATO` versiona la forma de las respuestas y el
  estudio lo comprueba al arrancar.
* **Bloques** (`inveniolang/web/bloques_web.py`): convierte el modelo de
  `inveniolang.bloques` en una *vista* dibujable (piezas de cabecera, huecos,
  listas en línea y bocas, con rótulos en el idioma de los bloques y nombres
  accesibles en el de la interfaz) y aplica las operaciones puras de
  `bloques.edicion`; los destinos para mover con el teclado son las zonas de
  `bloques.diseno` (las mismas que usa la GUI Qt) filtradas por
  `reglas.motivo_rechazo`. El JavaScript no duplica ninguna regla de encaje.
* **Empaquetado** (`scripts/empaquetar_web.py`): `inveniolang.zip` (el paquete
  sin los módulos de escritorio —Qt, Tk, LSP, sandbox, CLI— más `ply`),
  `textos.json`, `lexico.json`, `curriculo.es.json`, `curriculo.en.json` y
  `manifiesto.json` con el SHA-256 de cada uno (invalida la caché del navegador).

### Accesibilidad (WCAG 2.2 AA; AAA en contraste de texto)

* Todo se maneja con teclado: enlace «saltar al editor», pestañas con flechas,
  diálogos nativos (`<dialog>`), atajos sin trampas de foco (`F1` muestra la
  lista). En los bloques: flechas para recorrer, `Intro`/`F2` editar,
  `Espacio`/`M` recoger y elegir destino con las flechas entre los sitios
  válidos, `Intro` soltar, `Esc` cancelar, `Supr`, `Ctrl+D`, `Ctrl+Z/Y`,
  `Insert` para ir a la paleta; en la paleta, `Intro` elige dónde insertar.
* Roles ARIA (`tablist`, `tree`, `group`, `dialog`), regiones `aria-live` para
  cada resultado y cada cambio de bloques, foco visible de 3 px,
  `prefers-reduced-motion`, `forced-colors`, objetivos de 36 px.
* Contraste: el texto ≥ 7:1 en los dos temas y los controles ≥ 3:1
  (`tests/web/test_estudio_estatico.py` lo calcula desde `estilos.css`); los
  colores de los bloques son los del catálogo de `inveniolang/bloques`,
  también AAA. Nada se comunica solo con color.

### Pruebas

* Python (`tests/web/`): puente (`test_puente.py`), empaquetado determinista y
  zip usable sin Qt/Tk (`test_empaquetar_web.py`), textos/accesibilidad/
  contraste (`test_estudio_estatico.py`), contrato con `inveniolang.bloques`
  (`test_contrato_estudio.py`), VS Code (`test_vscode.py`).
* JavaScript con `node --test` (`web/estudio/pruebas/`): estado, i18n,
  almacenamiento, currículo, resaltado, motor (Worker falso, tiempo límite,
  Detener) y bloques (sobre una vista real, `pruebas/fixtures/bloques.json`,
  que regenera `python tests/web/fixtures_estudio.py`).
  `tests/web/test_estudio_node.py` las lanza desde pytest.
* Humo en Chromium (`test_humo_navegador.py`): recorre la página entera con
  Playwright, con un Pyodide **simulado** que reenvía cada llamada al puente
  real y, si hay una copia local (`INVENIOLANG_PYODIDE_DIR` o
  `~/.cache/inveniolang/pyodide-0.29.3`), también con **Pyodide real**. Se
  salta con su motivo si no hay Node, Playwright o Chromium.

## Extensión de VS Code (`../vscode-extension/`)

Cliente real del servidor LSP (`python -m inveniolang.lsp`) con
`vscode-languageclient`, gramática TextMate es/en generada del lexer
(`scripts/gramatica_vscode.py`) y comandos *Ejecutar*, *Traza paso a paso
(HTML)* y *Diagrama de flujo (SVG)*. Ver su `README.md`.

---

## English summary

`web/estudio/` is a static, build-free web studio that runs the real
InvenioLang compiler in the browser through Pyodide inside a Web Worker:
highlighted editor, run with input (partial output, Stop button), explained
errors, drag-and-drop **blocks** on the `inveniolang/bloques` contract (fully
keyboard operable, typed drop validation with bilingual reasons), flowchart
and UML SVGs, the embedded step-by-step player, Spanish⇄English translator,
the browsable curriculum with exercise checking, light/dark/system themes,
Spanish/English UI, and local files plus `localStorage`. Build the generated
files with `python scripts/empaquetar_web.py` (deterministic, `--comprobar`
for CI) and serve `web/estudio/` from any static server. WCAG 2.2 AA with AAA
text contrast (tested). The VS Code extension in `vscode-extension/` is a real
LSP client with an es/en TextMate grammar and run/trace/flowchart commands.
