// INV-4230: prueba de humo del estudio en Chromium (la lanza test_humo_navegador.py).
// Uso: node humo_navegador.mjs <ruta de playwright> <chromium> <url> <con bloques: 0|1>
// Imprime un JSON con lo comprobado; termina con 1 al primer fallo.
const [modulo, chromium, url, conBloques] = process.argv.slice(2);
const { chromium: navegador } = await import(modulo);
const fallos = [];
const consola = [];
const comprobar = (cond, msg) => { if (!cond) { fallos.push(msg); } };

const browser = await navegador.launch({ executablePath: chromium, args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1366, height: 860 }, locale: "es-ES", colorScheme: "light" });
page.on("console", (m) => { if (m.type() === "error") { consola.push(m.text()); } });
page.on("pageerror", (e) => consola.push(`pageerror: ${e.message}`));
try {
  await page.goto(url);
  await page.waitForFunction(() => document.getElementById("aviso-motor").dataset.estado === "listo", null, { timeout: 120000 });
  comprobar((await page.getAttribute("html", "lang")) === "es", "lang=es");

  // Ejecutar con entrada y error explicado
  await page.fill("#codigo", "vacio main() {\n    entero x;\n    leer(x);\n    imprimir(x * 2);\n}\n");
  await page.fill("#entrada", "21");
  await page.keyboard.press("Control+Enter");
  await page.waitForFunction(() => document.getElementById("salida").textContent === "42", null, { timeout: 60000 });
  comprobar((await page.getAttribute("#resultado", "data-estado")) === "ok", "resultado ok");
  await page.fill("#codigo", "vacio main() {\n    entero x = \"a\";\n}\n");
  await page.click("#btn-ejecutar");
  await page.waitForSelector("#lista-errores .error-item", { timeout: 60000 });
  comprobar((await page.textContent("#lista-errores")).includes("IL-TIPO-001"), "error con código");
  comprobar((await page.locator("#lista-errores .explicacion").count()) === 1, "explicación pedagógica");
  comprobar((await page.getAttribute("#tab-errores", "aria-selected")) === "true", "pestaña de errores activa");
  await page.click("#lista-errores .error-ir");
  comprobar(await page.evaluate(() => document.activeElement.id === "codigo"), "ir a la línea enfoca el editor");

  // Traducir
  await page.fill("#codigo", "vacio main() {\n    si (verdadero) {\n        imprimir(1);\n    }\n}\n");
  await page.click("#btn-traducir");
  await page.waitForFunction(() => document.getElementById("codigo").value.startsWith("void main"), null, { timeout: 60000 });

  // Diagrama de flujo, UML y paso a paso
  await page.click("#tab-flujo");
  await page.waitForSelector("#lienzo-flujo svg[role=img]", { timeout: 60000 });
  await page.click("#tab-uml");
  await page.waitForSelector("#lienzo-uml svg", { timeout: 60000 });
  await page.click("#btn-pasos");
  await page.waitForFunction(() => !document.getElementById("marco-pasos").hidden, null, { timeout: 60000 });
  comprobar((await page.getAttribute("#marco-pasos", "sandbox")) === "allow-scripts", "reproductor aislado");

  // Bloques
  await page.fill("#codigo", "vacio main() {\n    entero x = 3;\n    imprimir(x);\n}\n");
  await page.click("#tab-bloques");
  if (conBloques === "1") {
    await page.waitForSelector("#arbol-bloques [role=treeitem]", { timeout: 60000 });
    const decl = page.locator("#arbol-bloques li[role=treeitem].forma-instruccion").first();
    await decl.focus();
    await page.keyboard.press("Space");
    await page.waitForSelector("#arbol-bloques .zona.destino", { timeout: 30000 });
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Escape");
    comprobar((await page.locator("#arbol-bloques .zona.destino").count()) === 0, "Escape cancela el movimiento");
    await page.locator("#arbol-bloques .campo", { hasText: "3" }).first().click();
    await page.keyboard.press("Control+a");
    await page.keyboard.type("8");
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => document.getElementById("codigo").value.includes("entero x = 8;"), null, { timeout: 60000 });
  } else {
    await page.waitForFunction(() => document.getElementById("resultado").textContent.includes("inveniolang.bloques"), null, { timeout: 60000 });
  }

  // Currículo: abrir, ver solución, comprobar
  await page.fill("#buscar-curriculo", "N01-E01");
  await page.click("#arbol-curriculo .lista-ejercicios button");
  // El programa anterior tenía cambios: el estudio pide confirmación antes de reemplazarlo.
  await page.waitForSelector("#dialogo-confirmar[open]", { timeout: 10000 });
  await page.click("#dialogo-confirmar-si");
  await page.waitForSelector("#ejercicio:not([hidden])", { timeout: 30000 });
  await page.click("#btn-solucion");
  await page.click("#dialogo-confirmar-si");
  await page.click("#btn-comprobar");
  await page.waitForFunction(() => document.getElementById("ejercicio-veredicto").dataset.ok === "true", null, { timeout: 60000 });

  // Tema oscuro e idioma inglés
  await page.click('input[name="tema"][value="oscuro"]', { force: true });
  comprobar((await page.getAttribute("html", "data-tema")) === "oscuro", "tema oscuro");
  await page.selectOption("#sel-idioma", "en");
  comprobar((await page.getAttribute("html", "lang")) === "en", "lang=en");
  comprobar((await page.textContent("#btn-ejecutar")).includes("Run"), "textos en inglés");

  // Teclado: las pestañas se recorren con flechas
  await page.focus("#tab-salida");
  await page.keyboard.press("ArrowRight");
  comprobar(await page.evaluate(() => document.activeElement.id === "tab-errores"), "flechas en las pestañas");
} catch (e) {
  fallos.push(String(e));
}
comprobar(consola.length === 0, `errores en la consola: ${consola.join(" | ")}`);
await browser.close();
console.log(JSON.stringify({ fallos }));
process.exit(fallos.length ? 1 : 0);
