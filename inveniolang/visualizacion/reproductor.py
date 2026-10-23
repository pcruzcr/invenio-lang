"""Reproductor HTML autónomo de una Traza (equipo VISTA).

INV-2220: ``html_traza(traza)`` produce UNA página que se abre sin red (sin
CDN, fuentes ni scripts externos) para que el estudiante comparta o entregue
la ejecución de su programa: controles ⏮ ◀ ▶ ⏭, deslizador, reproducción
automática con velocidad, atajos de teclado (←/→, Inicio/Fin, Espacio),
código fuente con la línea actual resaltada (fondo + marca ▶ + negrita, no
sólo color), región ``aria-live`` con la descripción del paso, salida
acumulada, tema claro/oscuro y textos en el idioma de la traza.

Tamaño: los SVG de pasos consecutivos son casi idénticos, así que se
deduplican y se guardan comprimidos con gzip en base64; el navegador los
descomprime con ``DecompressionStream`` (API estándar, sin bibliotecas). La
descripción textual de todos los pasos va además en HTML plano dentro de un
``<details>``: la página sigue siendo útil sin JavaScript.
"""

from __future__ import annotations

import base64
import gzip
import json
from html import escape
from typing import Any

from .. import i18n
from . import render_svg, render_texto

_XMLNS = ' xmlns="http://www.w3.org/2000/svg"'

_CSS = """
:root{--fondo:#ffffff;--panel:#f6f8fa;--borde:#6e7781;--texto:#1f2328;--suave:#424a53;
--acento:#5a2d9c;--actual:#fff8c5;--actual-borde:#7d4e00;--foco:#0550ae;--error:#82071e;
--error-fondo:#ffebe9}
[data-tema="oscuro"]{--fondo:#0d1117;--panel:#161b22;--borde:#8b949e;--texto:#f0f6fc;--suave:#c9d1d9;
--acento:#d2a8ff;--actual:#3b2e00;--actual-borde:#e3b341;--foco:#79c0ff;--error:#ffdcd7;
--error-fondo:#5d0f12}
*{box-sizing:border-box}
html,body{margin:0;background:var(--fondo);color:var(--texto)}
body{font:16px/1.5 system-ui,"Segoe UI",Roboto,"Noto Sans",sans-serif}
a.saltar{position:absolute;left:-999px;top:0;background:var(--panel);color:var(--texto);padding:8px}
a.saltar:focus{left:8px;z-index:9}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;
padding:12px 16px;border-bottom:1px solid var(--borde)}
h1{font-size:1.25rem;margin:0}
h2{font-size:1rem;margin:0 0 8px}
main{padding:12px 16px;display:grid;gap:16px}
.controles{display:flex;flex-wrap:wrap;gap:8px;align-items:center;background:var(--panel);
border:1px solid var(--borde);border-radius:8px;padding:8px}
button,select{font:inherit;color:var(--texto);background:var(--fondo);border:2px solid var(--borde);
border-radius:6px;min-height:44px;min-width:44px;padding:4px 10px;cursor:pointer}
button[aria-pressed="true"]{background:var(--actual);border-color:var(--actual-borde)}
input[type=range]{flex:1 1 200px;min-height:44px;accent-color:var(--acento)}
:focus-visible{outline:3px solid var(--foco);outline-offset:2px}
output{font-variant-numeric:tabular-nums;font-weight:700}
.rejilla{display:grid;gap:16px;grid-template-columns:minmax(0,2fr) minmax(0,3fr)}
@media (max-width:900px){.rejilla{grid-template-columns:1fr}}
section{background:var(--panel);border:1px solid var(--borde);border-radius:8px;padding:12px;
min-width:0}
ol.codigo{list-style:none;margin:0;padding:0;
font:14px/1.6 ui-monospace,"Cascadia Mono",Consolas,monospace;
overflow:auto;max-height:70vh;background:var(--fondo);border-radius:6px}
ol.codigo li{display:flex;white-space:pre;border-left:4px solid transparent}
ol.codigo .num{display:inline-block;min-width:3.5em;padding-right:1em;text-align:right;
color:var(--suave);user-select:none}
ol.codigo .marca{display:inline-block;width:1.4em;color:var(--actual-borde)}
ol.codigo li.actual{background:var(--actual);border-left-color:var(--actual-borde);font-weight:700}
#lienzo{margin:0;overflow:auto;max-height:80vh;background:var(--fondo);border-radius:6px}
#lienzo svg{display:block;max-width:none}
#descripcion{margin:0;font-size:1.05rem}
pre#salida{margin:0;white-space:pre-wrap;font:14px/1.5 ui-monospace,Consolas,monospace;
max-height:30vh;overflow:auto}
.aviso{border:2px solid var(--actual-borde);background:var(--actual);border-radius:8px;
padding:8px 12px;margin:0}
.aviso.error{border-color:var(--error);background:var(--error-fondo);color:var(--error)}
.atajos{color:var(--suave);margin:0}
details li{margin-bottom:4px}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""

_JS = r"""
(function(){
"use strict";
var D=JSON.parse(document.getElementById("vis-datos").textContent);
var T=D.textos, pasos=D.pasos, svgs=[], actual=0, temporizador=null;
var $=function(id){return document.getElementById(id);};
var lienzo=$("lienzo"), desc=$("descripcion"), contador=$("contador"), deslizador=$("deslizador");
var btnPlay=$("btn-reproducir"), salida=$("salida"), codigo=$("codigo");
function formato(p,v){return p.replace(/\{(\w+)\}/g,function(_,k){return v[k];});}
function ir(i,anunciar){
  if(!pasos.length){return;}
  actual=Math.max(0,Math.min(pasos.length-1,i));
  var p=pasos[actual];
  if(svgs.length){lienzo.innerHTML=svgs[p.svg];}
  desc.textContent=p.descripcion;
  desc.setAttribute("aria-live",anunciar===false?"off":"polite");
  var c=formato(T.contador,{n:actual+1,total:pasos.length});
  contador.textContent=c;
  deslizador.value=String(actual);
  deslizador.setAttribute("aria-valuetext",c);
  salida.textContent=D.salida.slice(0,p.salida).join("\n");
  var previa=codigo.querySelector("li.actual");
  if(previa){previa.classList.remove("actual");previa.removeAttribute("aria-current");
    previa.querySelector(".marca").textContent="";}
  var li=$("vis-l"+p.linea);
  if(li){li.classList.add("actual");li.setAttribute("aria-current","step");
    li.querySelector(".marca").textContent="▶";
    li.scrollIntoView({block:"nearest"});}
}
function pausar(){
  if(temporizador!==null){clearInterval(temporizador);temporizador=null;}
  btnPlay.textContent="▶"; btnPlay.setAttribute("aria-label",T.reproducir);
  btnPlay.setAttribute("aria-pressed","false"); desc.setAttribute("aria-live","polite");
}
function reproducir(){
  if(actual>=pasos.length-1){ir(0,false);}
  btnPlay.textContent="⏸"; btnPlay.setAttribute("aria-label",T.pausar);
  btnPlay.setAttribute("aria-pressed","true");
  temporizador=setInterval(function(){
    if(actual>=pasos.length-1){pausar();return;}
    ir(actual+1,false);
  },1000/Number($("velocidad").value));
}
function alternar(){if(temporizador===null){reproducir();}else{pausar();}}
$("btn-inicio").addEventListener("click",function(){pausar();ir(0);});
$("btn-anterior").addEventListener("click",function(){pausar();ir(actual-1);});
$("btn-siguiente").addEventListener("click",function(){pausar();ir(actual+1);});
$("btn-fin").addEventListener("click",function(){pausar();ir(pasos.length-1);});
btnPlay.addEventListener("click",alternar);
deslizador.addEventListener("input",function(){pausar();ir(Number(deslizador.value));});
$("velocidad").addEventListener("change",function(){if(temporizador!==null){pausar();reproducir();}});
$("btn-tema").addEventListener("click",function(){
  var oscuro=document.documentElement.getAttribute("data-tema")!=="oscuro";
  document.documentElement.setAttribute("data-tema",oscuro?"oscuro":"claro");
  this.setAttribute("aria-pressed",oscuro?"true":"false");
});
document.addEventListener("keydown",function(e){
  var t=e.target, tag=t&&t.tagName;
  if(e.altKey||e.ctrlKey||e.metaKey){return;}
  if(tag==="SELECT"||tag==="TEXTAREA"||(tag==="INPUT"&&t.type!=="range")){return;}
  var k=e.key;
  if(k==="ArrowRight"){pausar();ir(actual+1);}
  else if(k==="ArrowLeft"){pausar();ir(actual-1);}
  else if(k==="Home"){pausar();ir(0);}
  else if(k==="End"){pausar();ir(pasos.length-1);}
  else if(k===" "&&tag!=="BUTTON"&&tag!=="SUMMARY"&&tag!=="A"){alternar();}
  else{return;}
  e.preventDefault();
});
if(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches){
  document.documentElement.setAttribute("data-tema","oscuro");$("btn-tema").setAttribute("aria-pressed","true");
}
function cargar(){
  if(!pasos.length){return Promise.resolve();}
  if(typeof DecompressionStream==="undefined"){
    lienzo.textContent=T.sin_soporte; return Promise.resolve();
  }
  var bin=atob(D.svgs), bytes=new Uint8Array(bin.length);
  for(var i=0;i<bin.length;i++){bytes[i]=bin.charCodeAt(i);}
  var flujo=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Response(flujo).text().then(function(txt){svgs=JSON.parse(txt);});
}
ir(0,false);
cargar().then(function(){ir(actual,false);},function(){lienzo.textContent=T.sin_soporte;});
})();
"""


def _json_script(datos: Any) -> str:
    """JSON seguro dentro de ``<script>``: ningún ``</script>`` ni ``<!--``."""
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    return texto.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def empaquetar_svgs(svgs: list[str]) -> tuple[str, list[int]]:
    """Deduplica los SVG y los comprime (gzip determinista + base64).

    Devuelve el blob y, para cada paso, el índice de su SVG en la lista
    deduplicada. ``mtime=0`` hace que el mismo SVG dé el mismo HTML siempre.
    """
    unicos: list[str] = []
    posicion: dict[str, int] = {}
    indices = []
    for s in svgs:
        if s not in posicion:
            posicion[s] = len(unicos)
            unicos.append(s)
        indices.append(posicion[s])
    crudo = json.dumps(unicos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    blob = base64.b64encode(gzip.compress(crudo, compresslevel=9, mtime=0)).decode("ascii")
    return blob, indices


def html_traza(traza: Any, idioma: str | None = None) -> str:
    """Página HTML autónoma que reproduce la traza paso a paso.

    ``traza`` puede ser un ``dict`` del contrato, su JSON o un objeto
    ``Traza``; ``idioma`` (por defecto, el de la traza) elige los textos.
    """
    t = render_texto.normalizar_traza(traza)
    idi = i18n.normalizar_idioma(idioma) if idioma is not None else t["idioma"]
    pasos = t["pasos"]
    svgs = [render_svg.svg_paso(p, idi).replace(_XMLNS, "", 1) for p in pasos]
    blob, indices = empaquetar_svgs(svgs)
    acumulada, meta = 0, []
    salida = list(t["salida"])
    for p, indice in zip(pasos, indices, strict=True):
        acumulada += len(p["salida_nueva"])
        meta.append(
            {
                "linea": p["linea"],
                "svg": indice,
                "salida": acumulada,
                "descripcion": render_texto.describir(p, idi),
            }
        )
    if acumulada > len(salida):
        salida = [s for p in pasos for s in p["salida_nueva"]]
    claves = ("contador", "reproducir", "pausar", "sin_soporte")
    datos = {
        "pasos": meta,
        "svgs": blob,
        "salida": salida,
        # plantillas crudas: el JS rellena {n}/{total} de "contador" en cada paso
        "textos": {k: i18n.REGISTRO.obtener(idi).mensajes[f"VIS.ui.{k}"] for k in claves},
    }
    return _documento(t, idi, meta, datos)


def _documento(
    t: dict[str, Any], idi: str, meta: list[dict[str, Any]], datos: dict[str, Any]
) -> str:
    def tx(clave: str, **args: Any) -> str:
        return escape(i18n.t(clave, idi, **args))

    total = len(meta)
    lineas = t["fuente"].split("\n")
    if lineas and lineas[-1] == "":
        lineas.pop()
    codigo = "".join(
        f'<li id="vis-l{i}"><span class="num" aria-hidden="true">{i}</span>'
        f'<span class="marca" aria-hidden="true"></span><code>{escape(linea) or " "}</code></li>'
        for i, linea in enumerate(lineas, 1)
    )
    avisos = ""
    if t["error"]:
        avisos += f'<p class="aviso error" role="alert">{tx("VIS.ui.error", error=t["error"])}</p>'
    if t["truncada"]:
        avisos += f'<p class="aviso">{tx("VIS.ui.truncada")}</p>'
    if not total:
        avisos += f'<p class="aviso">{tx("VIS.ui.sin_pasos")}</p>'
    todas = "".join(f"<li>{escape(m['descripcion'])}</li>" for m in meta)
    primera = escape(meta[0]["descripcion"]) if meta else ""
    contador = tx("VIS.ui.contador", n=1 if total else 0, total=total)
    css_oscuro = render_svg.css_tema('[data-tema="oscuro"] #lienzo', "oscuro")
    titulo = tx("VIS.ui.titulo")
    botones = "".join(
        f'<button type="button" id="btn-{ident}" aria-label="{tx(clave)}" title="{tx(clave)}"'
        + (' aria-pressed="false"' if ident == "reproducir" else "")
        + f">{icono}</button>"
        for ident, clave, icono in (
            ("inicio", "VIS.ui.inicio", "⏮"),
            ("anterior", "VIS.ui.anterior", "◀"),
            ("reproducir", "VIS.ui.reproducir", "▶"),
            ("siguiente", "VIS.ui.siguiente", "▶|"),
            ("fin", "VIS.ui.fin", "⏭"),
        )
    )
    return (
        f'<!doctype html><html lang="{idi}" data-tema="claro"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{titulo}</title><style>{_CSS}{css_oscuro}</style></head><body>"
        f'<a class="saltar" href="#vis-estructuras">{tx("VIS.ui.saltar")}</a>'
        f"<header><h1>{titulo}</h1>"
        '<button type="button" id="btn-tema" aria-pressed="false">'
        f'{tx("VIS.ui.tema")}</button></header>'
        f"<main>{avisos}"
        f'<div class="controles" role="toolbar" aria-label="{tx("VIS.ui.controles")}">'
        f"{botones}"
        f'<input type="range" id="deslizador" min="0" max="{max(total - 1, 0)}" value="0" step="1"'
        f' aria-label="{tx("VIS.ui.deslizador")}" aria-valuetext="{contador}">'
        f'<output id="contador" for="deslizador">{contador}</output>'
        f'<label for="velocidad">{tx("VIS.ui.velocidad")}</label>'
        '<select id="velocidad"><option value="0.5">0.5×</option>'
        '<option value="1" selected>1×</option>'
        '<option value="2">2×</option><option value="4">4×</option></select></div>'
        f'<p class="atajos">{tx("VIS.ui.atajos")}</p>'
        '<div class="rejilla">'
        f'<section aria-labelledby="vis-h-codigo"><h2 id="vis-h-codigo">{tx("VIS.ui.codigo")}</h2>'
        f'<ol class="codigo" id="codigo" aria-label="{tx("VIS.ui.codigo")}">{codigo}</ol></section>'
        '<section id="vis-estructuras" aria-labelledby="vis-h-est">'
        f'<h2 id="vis-h-est">{tx("VIS.ui.estructuras")}</h2>'
        '<figure id="lienzo" tabindex="0" aria-labelledby="vis-h-est">'
        f'{tx("VIS.ui.cargando")}</figure></section>'
        "</div>"
        f'<section aria-labelledby="vis-h-desc"><h2 id="vis-h-desc">{tx("VIS.ui.descripcion")}</h2>'
        f'<p id="descripcion" aria-live="polite" aria-atomic="true">{primera}</p></section>'
        f'<section aria-labelledby="vis-h-salida"><h2 id="vis-h-salida">{tx("VIS.ui.salida")}</h2>'
        '<pre id="salida"></pre></section>'
        f'<section><details><summary>{tx("VIS.ui.todas")}</summary><ol>{todas}</ol></details></section>'
        "</main>"
        f'<script type="application/json" id="vis-datos">{_json_script(datos)}</script>'
        f"<script>{_JS}</script></body></html>"
    )


__all__ = ["empaquetar_svgs", "html_traza"]
