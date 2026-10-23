"""Catálogo de tipos de bloque: forma, categoría, campos, huecos y listas (INV-4001).

Es la **única** descripción de qué bloques existen y cómo encajan; de él
salen el contrato JSON (qué claves lleva cada bloque, ``modelo.py``), la
validación al soltar (``tipos.py``/``edicion.py``), la paleta de la GUI y la
de la web (``catalogo_dict`` se publica tal cual en el JSON del catálogo).
Así el editor de Qt y el del navegador no pueden discrepar sobre qué cabe
dónde.

Vocabulario:

* **campo**: dato atómico del bloque (nombre, operador, tipo, literal,
  bandera). Los valores que son palabras clave (visibilidad, modificador,
  ``verdadero``/``falso``…) se guardan en forma **neutral** (la española
  canónica de ``traductor.PALABRAS_CLAVE``) y se escriben en el idioma del
  modelo al generar código; los tipos, nombres y literales se guardan tal
  como se escriben en el idioma del modelo.
* **hueco**: sitio para UN bloque de valor (expresión anidable) con el tipo
  que acepta (``valor``, ``logico``, ``numero``, ``asignable``, ``llamada``,
  ``variable``).
* **lista**: secuencia ordenada de bloques: una pila de instrucciones
  (``cuerpo``), argumentos, ramas de un ``si``, casos, parámetros, miembros…
  ``acepta`` dice qué familia de bloques admite.

Formas (dibujo y encaje, como en Scratch/Blockly): ``valor`` (bloque
redondeado que devuelve algo; los lógicos se dibujan hexagonales),
``instruccion`` (pieza de pila con muesca), ``c`` (instrucción que abraza
pilas), ``definicion`` (sombrero: subrutinas, clases…), ``miembro`` (dentro
de una clase) y ``parte`` (rama, caso, fila, parámetro: sólo dentro de su
contenedor).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import i18n

__all__ = [
    "ACEPTA_HUECO",
    "ACEPTA_LISTA",
    "CATEGORIAS",
    "FORMAS",
    "PALETA",
    "TIPOS",
    "Campo",
    "Categoria",
    "EntradaPaleta",
    "Hueco",
    "Lista",
    "TipoBloque",
    "catalogo_dict",
    "contraste",
    "familia_de_lista",
]

FORMAS = ("valor", "instruccion", "c", "definicion", "miembro", "parte")

# Tipos de valor que puede pedir un hueco.
ACEPTA_HUECO = ("valor", "logico", "numero", "asignable", "llamada", "variable")

# Familias que admite una lista -> tipos de bloque concretos (None: por forma).
ACEPTA_LISTA: dict[str, tuple[str, ...]] = {
    "instruccion": (),  # cualquier bloque de forma instruccion o c
    "valor": (),  # cualquier bloque de forma valor
    "definicion": (),  # forma definicion + declaraciones globales (abajo)
    "miembro": ("atributo", "metodo", "constructor"),
    "rama_si": ("rama_si",),
    "caso": ("caso",),
    "caso_patron": ("caso_patron",),
    "fila": ("fila",),
    "parametro": ("parametro",),
    "miembro_enum": ("miembro_enum",),
    "inicio_para": ("declarar", "asignar"),
    "paso_para": ("asignar", "incrementar"),
}
# Declaraciones que también pueden ir sueltas en el programa (globales).
GLOBALES = ("declarar", "arreglo")


@dataclass(frozen=True)
class Campo:
    """Dato atómico de un bloque.

    ``clase``: ``identificador``, ``identificadores`` (lista con comas),
    ``nombre_subrutina`` (identificador o ``main``), ``tipo``,
    ``tipo_retorno`` (tipo o ``vacio``), ``numero``, ``texto``, ``literal_caso``,
    ``dimensiones`` (``3`` o ``3, n``), ``opcion`` (una de ``opciones``) o
    ``bandera`` (verdadero/falso JSON). ``vacio_ok``: admite ``""``.
    """

    nombre: str
    clase: str
    opciones: tuple[str, ...] = ()
    vacio_ok: bool = False
    defecto: Any = ""


@dataclass(frozen=True)
class Hueco:
    """Sitio para un bloque de valor; ``acepta`` es uno de ``ACEPTA_HUECO``."""

    nombre: str
    acepta: str = "valor"
    opcional: bool = False


@dataclass(frozen=True)
class Lista:
    """Secuencia de bloques; ``acepta`` es una clave de ``ACEPTA_LISTA``."""

    nombre: str
    acepta: str
    minimo: int = 0
    maximo: int | None = None


@dataclass(frozen=True)
class TipoBloque:
    """Descripción de un tipo de bloque."""

    tipo: str
    categoria: str
    forma: str
    salida: str | None = None  # familia de valor que produce (bloques de forma valor)
    campos: tuple[Campo, ...] = ()
    huecos: tuple[Hueco, ...] = ()
    listas: tuple[Lista, ...] = ()

    def campo(self, nombre: str) -> Campo | None:
        """El campo ``nombre`` o ``None``."""
        return next((c for c in self.campos if c.nombre == nombre), None)

    def hueco(self, nombre: str) -> Hueco | None:
        """El hueco ``nombre`` o ``None``."""
        return next((h for h in self.huecos if h.nombre == nombre), None)

    def lista(self, nombre: str) -> Lista | None:
        """La lista ``nombre`` o ``None``."""
        return next((x for x in self.listas if x.nombre == nombre), None)


OPS_ASIGNACION = ("=", "+=", "-=", "*=", "/=", "%=")
OPS_BINARIOS = (
    "+",
    "-",
    "*",
    "/",
    "%",
    "==",
    "!=",
    "<",
    ">",
    "<=",
    ">=",
    "&&",
    "||",
    "&",
    "|",
    "^",
    "<<",
    ">>",
    "??",
)
OPS_UNARIOS = ("-", "!", "~")
VISIBILIDAD = ("publico", "privado")
MODIFICADOR = ("estatico", "abstracto")

_I = Campo("nombre", "identificador")
_CUERPO = Lista("cuerpo", "instruccion")
_ARGS = Lista("argumentos", "valor")
_PARAMS = Lista("parametros", "parametro")
_INC = (Campo("op", "opcion", ("++", "--"), defecto="++"),)
_POS = Campo("posicion", "opcion", ("prefijo", "sufijo"), defecto="sufijo")
_SEGURO = Campo("seguro", "bandera", defecto=False)
_VIS = Campo("visibilidad", "opcion", VISIBILIDAD, defecto="publico")
_MOD = Campo("modificador", "opcion", MODIFICADOR, vacio_ok=True)


def _t(*tipos: TipoBloque) -> dict[str, TipoBloque]:
    return {t.tipo: t for t in tipos}


TIPOS: dict[str, TipoBloque] = _t(
    # ---------------------------------------------------------------- valores
    TipoBloque("numero", "valores", "valor", "numero", (Campo("valor", "numero", defecto="0"),)),
    TipoBloque("texto", "valores", "valor", "texto", (Campo("valor", "texto", defecto='""'),)),
    TipoBloque(
        "logico",
        "valores",
        "valor",
        "logico",
        (Campo("valor", "opcion", ("verdadero", "falso"), defecto="verdadero"),),
    ),
    TipoBloque("nulo", "valores", "valor", "nulo"),
    # ---------------------------------------------------------------- variables
    TipoBloque("variable", "variables", "valor", "cualquiera", (_I,)),
    TipoBloque(
        "declarar",
        "variables",
        "instruccion",
        campos=(
            Campo("constante", "bandera", defecto=False),
            Campo("tipo", "tipo", defecto="entero"),
            Campo("nombre", "identificador"),
        ),
        huecos=(Hueco("valor", "valor", opcional=True),),
    ),
    TipoBloque(
        "asignar",
        "variables",
        "instruccion",
        campos=(Campo("op", "opcion", OPS_ASIGNACION, defecto="="),),
        huecos=(Hueco("destino", "asignable"), Hueco("valor")),
    ),
    TipoBloque(
        "incrementar",
        "variables",
        "instruccion",
        campos=_INC + (_POS,),
        huecos=(Hueco("objetivo", "variable"),),
    ),
    TipoBloque(
        "incremento",
        "variables",
        "valor",
        "numero",
        campos=_INC + (_POS,),
        huecos=(Hueco("objetivo", "asignable"),),
    ),
    # ---------------------------------------------------------------- operadores
    TipoBloque(
        "binaria",
        "operadores",
        "valor",
        "cualquiera",
        (Campo("op", "opcion", OPS_BINARIOS, defecto="+"),),
        (Hueco("izquierda"), Hueco("derecha")),
    ),
    TipoBloque(
        "unaria",
        "operadores",
        "valor",
        "cualquiera",
        (Campo("op", "opcion", OPS_UNARIOS, defecto="!"),),
        (Hueco("valor"),),
    ),
    TipoBloque(
        "ternaria",
        "operadores",
        "valor",
        "cualquiera",
        huecos=(Hueco("condicion", "logico"), Hueco("si_verdadero"), Hueco("si_falso")),
    ),
    # ---------------------------------------------------------------- entrada y salida
    TipoBloque("leer", "entrada_salida", "instruccion", huecos=(Hueco("destino", "asignable"),)),
    TipoBloque("imprimir", "entrada_salida", "instruccion", huecos=(Hueco("valor"),)),
    # ---------------------------------------------------------------- control
    TipoBloque(
        "si",
        "control",
        "c",
        campos=(Campo("tiene_sino", "bandera", defecto=False),),
        listas=(Lista("ramas", "rama_si", minimo=1), Lista("sino", "instruccion")),
    ),
    TipoBloque(
        "rama_si", "control", "parte", huecos=(Hueco("condicion", "logico"),), listas=(_CUERPO,)
    ),
    TipoBloque(
        "segun",
        "control",
        "c",
        campos=(Campo("tiene_defecto", "bandera", defecto=False),),
        huecos=(Hueco("expresion"),),
        listas=(Lista("casos", "caso"), Lista("por_defecto", "instruccion")),
    ),
    TipoBloque(
        "caso",
        "control",
        "parte",
        campos=(Campo("valor", "literal_caso", defecto="0"),),
        listas=(_CUERPO,),
    ),
    TipoBloque(
        "coincidir",
        "control",
        "c",
        campos=(Campo("tiene_defecto", "bandera", defecto=False),),
        huecos=(Hueco("expresion"),),
        listas=(Lista("casos", "caso_patron"), Lista("por_defecto", "instruccion")),
    ),
    TipoBloque(
        "caso_patron",
        "control",
        "parte",
        campos=(_I, Campo("variables", "identificadores", vacio_ok=True)),
        listas=(_CUERPO,),
    ),
    TipoBloque(
        "mientras", "control", "c", huecos=(Hueco("condicion", "logico"),), listas=(_CUERPO,)
    ),
    TipoBloque(
        "hacer_mientras", "control", "c", huecos=(Hueco("condicion", "logico"),), listas=(_CUERPO,)
    ),
    TipoBloque(
        "para",
        "control",
        "c",
        huecos=(Hueco("condicion", "logico", opcional=True),),
        listas=(
            Lista("inicio", "inicio_para", maximo=1),
            Lista("paso", "paso_para", maximo=1),
            _CUERPO,
        ),
    ),
    TipoBloque(
        "para_cada",
        "control",
        "c",
        campos=(Campo("tipo", "tipo", defecto="entero"), Campo("variable", "identificador")),
        huecos=(Hueco("coleccion"),),
        listas=(_CUERPO,),
    ),
    TipoBloque("romper", "control", "instruccion"),
    TipoBloque("continuar", "control", "instruccion"),
    TipoBloque(
        "intentar",
        "control",
        "c",
        campos=(Campo("variable", "identificador", defecto="e"),),
        listas=(_CUERPO, Lista("captura", "instruccion")),
    ),
    # ---------------------------------------------------------------- subrutinas
    TipoBloque(
        "subrutina",
        "subrutinas",
        "definicion",
        campos=(
            Campo("retorno", "tipo_retorno", defecto="vacio"),
            Campo("nombre", "nombre_subrutina"),
        ),
        listas=(_PARAMS, _CUERPO),
    ),
    TipoBloque(
        "parametro",
        "subrutinas",
        "parte",
        campos=(Campo("tipo", "tipo", defecto="entero"), _I),
    ),
    TipoBloque("llamada", "subrutinas", "valor", "cualquiera", (_I,), listas=(_ARGS,)),
    TipoBloque("llamar", "subrutinas", "instruccion", huecos=(Hueco("llamada", "llamada"),)),
    TipoBloque(
        "retornar", "subrutinas", "instruccion", huecos=(Hueco("valor", "valor", opcional=True),)
    ),
    TipoBloque(
        "lambda",
        "subrutinas",
        "valor",
        "funcion",
        (Campo("retorno", "tipo_retorno", defecto="entero"),),
        listas=(_PARAMS, _CUERPO),
    ),
    # ---------------------------------------------------------------- clases y objetos
    TipoBloque(
        "clase",
        "clases",
        "definicion",
        campos=(
            _I,
            Campo("abstracta", "bandera", defecto=False),
            Campo("generico", "identificador", vacio_ok=True),
            Campo("hereda", "identificador", vacio_ok=True),
            Campo("implementa", "identificadores", vacio_ok=True),
        ),
        listas=(Lista("miembros", "miembro"),),
    ),
    TipoBloque(
        "interfaz", "clases", "definicion", campos=(_I,), listas=(Lista("miembros", "miembro"),)
    ),
    TipoBloque(
        "atributo",
        "clases",
        "miembro",
        campos=(_VIS, _MOD, Campo("tipo", "tipo", defecto="entero"), _I),
        huecos=(Hueco("valor", "valor", opcional=True),),
    ),
    TipoBloque(
        "metodo",
        "clases",
        "miembro",
        campos=(
            _VIS,
            _MOD,
            Campo("retorno", "tipo_retorno", defecto="vacio"),
            _I,
            Campo("con_cuerpo", "bandera", defecto=True),
        ),
        listas=(_PARAMS, _CUERPO),
    ),
    TipoBloque(
        "constructor",
        "clases",
        "miembro",
        campos=(Campo("visibilidad", "opcion", VISIBILIDAD, vacio_ok=True, defecto="publico"), _I),
        listas=(_PARAMS, _CUERPO),
    ),
    TipoBloque(
        "nuevo",
        "clases",
        "valor",
        "objeto",
        (Campo("clase", "identificador"), Campo("generico", "tipo", vacio_ok=True)),
        listas=(_ARGS,),
    ),
    TipoBloque("propiedad", "clases", "valor", "cualquiera", (_I, _SEGURO), (Hueco("objeto"),)),
    TipoBloque(
        "llamada_metodo",
        "clases",
        "valor",
        "cualquiera",
        (_I, _SEGURO),
        (Hueco("objeto"),),
        (_ARGS,),
    ),
    TipoBloque("este", "clases", "valor", "objeto"),
    TipoBloque("padre", "clases", "valor", "objeto"),
    TipoBloque("llamar_padre", "clases", "instruccion", listas=(_ARGS,)),
    TipoBloque(
        "enumeracion",
        "clases",
        "definicion",
        campos=(_I,),
        listas=(Lista("miembros", "miembro_enum", minimo=1),),
    ),
    TipoBloque(
        "miembro_enum",
        "clases",
        "parte",
        campos=(_I, Campo("con_parametros", "bandera", defecto=False)),
        listas=(_PARAMS,),
    ),
    # ---------------------------------------------------------------- arreglos
    TipoBloque(
        "arreglo",
        "arreglos",
        "instruccion",
        campos=(
            Campo("constante", "bandera", defecto=False),
            Campo("tipo", "tipo", defecto="entero"),
            _I,
            Campo("dimensiones", "dimensiones", defecto="3"),
            Campo("estilo", "opcion", ("tipo", "nombre"), defecto="tipo"),
        ),
        listas=(Lista("valores", "valor"), Lista("filas", "fila")),
    ),
    TipoBloque("fila", "arreglos", "parte", listas=(Lista("valores", "valor", minimo=1),)),
    TipoBloque(
        "indice",
        "arreglos",
        "valor",
        "cualquiera",
        huecos=(Hueco("coleccion"), Hueco("posicion", "numero")),
    ),
    TipoBloque(
        "nuevo_arreglo",
        "arreglos",
        "valor",
        "arreglo",
        (Campo("tipo", "tipo", defecto="entero"),),
        (Hueco("tamano", "numero"),),
    ),
    # ---------------------------------------------------------------- módulos
    TipoBloque(
        "importar",
        "modulos",
        "definicion",
        campos=(Campo("ruta", "texto", defecto='"modulo.inv"'),),
    ),
)


def familia_de_lista(acepta: str, tipo: str) -> bool:
    """¿Un bloque ``tipo`` cabe en una lista que ``acepta`` esa familia?"""
    desc = TIPOS[tipo]
    if acepta == "instruccion":
        return desc.forma in ("instruccion", "c")
    if acepta == "valor":
        return desc.forma == "valor"
    if acepta == "definicion":
        return desc.forma == "definicion" or tipo in GLOBALES
    return tipo in ACEPTA_LISTA[acepta]


# ====================================================================== categorías y colores


@dataclass(frozen=True)
class Categoria:
    """Categoría de la paleta: icono textual y colores por tema (relleno, texto, borde)."""

    nombre: str
    icono: str
    claro: tuple[str, str, str]
    oscuro: tuple[str, str, str]


# INV-4004: el color nunca es la única pista: cada categoría lleva además un
# icono de texto y cada forma su silueta (muesca, hexágono, sombrero, «C»).
# Los colores se eligieron para que el texto tenga contraste >= 7:1 (AAA)
# con su relleno en ambos temas y el borde >= 3:1 con el fondo del lienzo
# (lo comprueba tests/bloques/test_bloques_catalogo.py con ``contraste``).
CATEGORIAS: dict[str, Categoria] = {
    c.nombre: c
    for c in (
        Categoria(
            "valores", "#", ("#E6E6E6", "#111111", "#5C5C5C"), ("#3A3A3A", "#F5F5F5", "#B0B0B0")
        ),
        Categoria(
            "variables", "x", ("#FFC98F", "#111111", "#8A4A00"), ("#7A3E00", "#FFFFFF", "#FFB066")
        ),
        Categoria(
            "operadores", "±", ("#B5E6AC", "#111111", "#2F6B26"), ("#235A1C", "#FFFFFF", "#7FD06E")
        ),
        Categoria(
            "control", "↻", ("#FFE38A", "#111111", "#7A6000"), ("#5E4A00", "#FFFFFF", "#E8C640")
        ),
        Categoria(
            "entrada_salida",
            "⇄",
            ("#A9D8F2", "#111111", "#1D5E80"),
            ("#16496A", "#FFFFFF", "#6FBDE8"),
        ),
        Categoria(
            "subrutinas", "ƒ", ("#F7BCCB", "#111111", "#8A2D48"), ("#74203A", "#FFFFFF", "#F08AA6")
        ),
        Categoria(
            "clases", "◇", ("#D6C6F5", "#111111", "#55399A"), ("#4A2F80", "#FFFFFF", "#B79BEF")
        ),
        Categoria(
            "arreglos", "▦", ("#A6E3D6", "#111111", "#1B6658"), ("#16564A", "#FFFFFF", "#62CDB6")
        ),
        Categoria(
            "modulos", "⎘", ("#DCCDB0", "#111111", "#6B5530"), ("#56442A", "#FFFFFF", "#CDB383")
        ),
    )
}
FONDO_LIENZO = {"claro": "#FFFFFF", "oscuro": "#1E1E1E"}


def _luminancia(color: str) -> float:
    canales = [int(color[k : k + 2], 16) / 255 for k in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(a: str, b: str) -> float:
    """Razón de contraste WCAG entre dos colores ``#RRGGBB``."""
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ====================================================================== paleta


@dataclass(frozen=True)
class EntradaPaleta:
    """Bloque de la paleta: un tipo con campos preestablecidos.

    ``clave`` identifica la entrada (``BLQ.paleta.<clave>`` es su nombre).
    """

    clave: str
    tipo: str
    campos: tuple[tuple[str, Any], ...] = ()

    @property
    def categoria(self) -> str:
        """Categoría de su tipo."""
        return TIPOS[self.tipo].categoria


def _p(clave: str, tipo: str | None = None, **campos: Any) -> EntradaPaleta:
    return EntradaPaleta(clave, tipo or clave, tuple(campos.items()))


PALETA: tuple[EntradaPaleta, ...] = (
    _p("numero"),
    _p("texto"),
    _p("verdadero", "logico", valor="verdadero"),
    _p("falso", "logico", valor="falso"),
    _p("nulo"),
    _p("variable"),
    _p("declarar"),
    _p("constante", "declarar", constante=True),
    _p("asignar"),
    _p("sumar_a", "asignar", op="+="),
    _p("incrementar"),
    _p("decrementar", "incrementar", op="--"),
    _p("incremento"),
    _p("suma", "binaria", op="+"),
    _p("resta", "binaria", op="-"),
    _p("producto", "binaria", op="*"),
    _p("division", "binaria", op="/"),
    _p("modulo", "binaria", op="%"),
    _p("igual", "binaria", op="=="),
    _p("distinto", "binaria", op="!="),
    _p("menor", "binaria", op="<"),
    _p("mayor", "binaria", op=">"),
    _p("menor_igual", "binaria", op="<="),
    _p("mayor_igual", "binaria", op=">="),
    _p("y", "binaria", op="&&"),
    _p("o", "binaria", op="||"),
    _p("no", "unaria", op="!"),
    _p("negativo", "unaria", op="-"),
    _p("ternaria"),
    _p("leer"),
    _p("imprimir"),
    _p("si"),
    _p("si_sino", "si", tiene_sino=True),
    _p("rama_si"),
    _p("mientras"),
    _p("hacer_mientras"),
    _p("para"),
    _p("para_cada"),
    _p("segun"),
    _p("caso"),
    _p("coincidir"),
    _p("caso_patron"),
    _p("romper"),
    _p("continuar"),
    _p("intentar"),
    _p("subrutina"),
    _p("parametro"),
    _p("llamada"),
    _p("llamar"),
    _p("retornar"),
    _p("lambda"),
    _p("clase"),
    _p("interfaz"),
    _p("atributo"),
    _p("metodo"),
    _p("constructor"),
    _p("nuevo"),
    _p("propiedad"),
    _p("llamada_metodo"),
    _p("este"),
    _p("padre"),
    _p("llamar_padre"),
    _p("enumeracion"),
    _p("miembro_enum"),
    _p("arreglo"),
    _p("matriz", "arreglo", dimensiones="3, 3"),
    _p("fila"),
    _p("indice"),
    _p("nuevo_arreglo"),
    _p("importar"),
)


def catalogo_dict(idioma: str = "es") -> dict[str, Any]:
    """Catálogo serializable (para la web y la documentación) en ``idioma``.

    Incluye cada tipo con su forma, categoría, salida, campos, huecos y
    listas, su plantilla de texto (``BLQ.plantilla.<tipo>``), las categorías
    con icono y colores por tema y las entradas de la paleta con su nombre.
    """
    idioma = i18n.normalizar_idioma(idioma)
    return {
        "formato": "inveniolang-bloques-catalogo",
        "version": 1,
        "idioma": idioma,
        "tipos": {
            t.tipo: {
                "categoria": t.categoria,
                "forma": t.forma,
                "salida": t.salida,
                # Plantilla sin formatear: sus {marcadores} los rellena quien dibuja.
                "plantilla": i18n.REGISTRO.obtener(idioma).mensajes[f"BLQ.plantilla.{t.tipo}"],
                "nombre": i18n.t(f"BLQ.tipo.{t.tipo}", idioma),
                "campos": [
                    {
                        "nombre": c.nombre,
                        "clase": c.clase,
                        "opciones": list(c.opciones),
                        "vacio_ok": c.vacio_ok,
                        "defecto": c.defecto,
                    }
                    for c in t.campos
                ],
                "huecos": [
                    {"nombre": h.nombre, "acepta": h.acepta, "opcional": h.opcional}
                    for h in t.huecos
                ],
                "listas": [
                    {"nombre": x.nombre, "acepta": x.acepta, "minimo": x.minimo, "maximo": x.maximo}
                    for x in t.listas
                ],
            }
            for t in TIPOS.values()
        },
        "familias": {k: (list(v) if v else None) for k, v in ACEPTA_LISTA.items()},
        "globales": list(GLOBALES),
        "categorias": {
            c.nombre: {
                "nombre": i18n.t(f"BLQ.categoria.{c.nombre}", idioma),
                "icono": c.icono,
                "claro": {"relleno": c.claro[0], "texto": c.claro[1], "borde": c.claro[2]},
                "oscuro": {"relleno": c.oscuro[0], "texto": c.oscuro[1], "borde": c.oscuro[2]},
            }
            for c in CATEGORIAS.values()
        },
        "paleta": [
            {
                "clave": e.clave,
                "tipo": e.tipo,
                "categoria": e.categoria,
                "nombre": i18n.t(f"BLQ.paleta.{e.clave}", idioma),
                "campos": dict(e.campos),
            }
            for e in PALETA
        ],
    }
