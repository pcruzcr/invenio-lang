"""Módulos de InvenioLang: ``importar "ruta";`` / ``import "path";`` (INV-1420).

Hasta la v10 todo programa vivía en un único archivo .inv, lo que impedía
reutilizar código (y, por tanto, tener una biblioteca estándar escrita en el
propio lenguaje). Este módulo es el *enlazador*: resuelve cada importación,
analiza el archivo importado y agrega sus declaraciones al programa.

Reglas (documentadas en docs/modulos.md):

* La ruta es un literal de texto relativo al archivo que importa; la
  extensión ``.inv`` es opcional. Si no existe junto al importador se busca
  en la biblioteca estándar (``inveniolang/stdlib``), así que
  ``importar "estructuras/pila";`` funciona desde cualquier carpeta.
* Toda ruta pasa por :func:`security.validar_ruta_relativa` (sin ``..``, sin
  rutas absolutas, sin ``:``) y, una vez resuelta, debe quedar dentro de la
  carpeta raíz (la del programa o la de la biblioteca): un enlace simbólico
  que apunte afuera se rechaza.
* Un módulo puede declarar funciones, procedimientos, clases, enumeraciones,
  interfaces y constantes. Las variables globales no se exportan (estado
  compartido oculto entre archivos): IL-MOD-005. Si el módulo tiene ``main``,
  se ignora al importarlo (permite que un módulo sea además un ejemplo
  ejecutable por sí solo).
* La visibilidad es transitiva y plana (como ``#include`` de C): quien importa
  ``a`` ve también lo que ``a`` importó. Un nombre declarado en dos archivos
  es IL-MOD-004. Un módulo importado varias veces (diamante) se carga una vez.
* Los ciclos de importación son IL-MOD-003, con la cadena completa.
* Cada módulo se verifica (semántica y tipos) **por separado** antes de
  enlazarlo, para que sus errores se informen con su propio nombre de archivo
  y para que no pueda depender de nombres del programa que lo importa.

El núcleo (``core/compiler.py``) no hace IO: recibe el *puerto*
:class:`CargadorModulos`; :class:`CargadorArchivos` es el adaptador por
defecto que lee del disco.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field

from . import security
from .ast_nodes import (
    ArrayDecl,
    Bloque,
    ClassDecl,
    ConstDecl,
    EnumDecl,
    ImportDecl,
    MainDecl,
    Program,
)
from .config import DEFAULT_CONFIG
from .errors import ErrorManager
from .i18n import M

RAIZ_STDLIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdlib")
PREFIJO_STDLIB = "stdlib"
MAX_MODULOS = 64


class ErrorCargaModulo(Exception):
    """Fallo al leer un módulo, con su mensaje del catálogo."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


class CargadorModulos:
    """Puerto: obtiene el texto fuente de un módulo ya resuelto."""

    def existe(self, ruta: str) -> bool:
        """Indica si ``ruta`` (absoluta) es un archivo legible."""
        raise NotImplementedError

    def leer(self, ruta: str) -> str:
        """Texto UTF-8 del archivo; ErrorCargaModulo si no se puede."""
        raise NotImplementedError


class CargadorArchivos(CargadorModulos):
    """Adaptador por defecto: lee del sistema de archivos con límite de tamaño."""

    def __init__(self, limite_bytes: int = DEFAULT_CONFIG.max_fuente_bytes):
        self.limite_bytes = limite_bytes

    def existe(self, ruta: str) -> bool:
        """True si es un archivo regular."""
        return os.path.isfile(ruta)

    def leer(self, ruta: str) -> str:
        """Lee el módulo validando tamaño y codificación."""
        nombre = os.path.basename(ruta)
        try:
            if os.path.getsize(ruta) > self.limite_bytes:
                raise ErrorCargaModulo(
                    M("IL-MOD-006.demasiado_grande", ruta=nombre, limite=self.limite_bytes)
                )
            with open(ruta, encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError as e:
            raise ErrorCargaModulo(M("IL-MOD-006.no_utf8", ruta=nombre)) from e
        except OSError as e:
            raise ErrorCargaModulo(
                M("IL-MOD-006.no_legible", ruta=nombre, motivo=e.strerror or e)
            ) from e


class CargadorMemoria(CargadorModulos):
    """Adaptador sin disco: módulos en un diccionario {ruta absoluta: texto}.

    Para anfitriones sin sistema de archivos (playground web) y pruebas. La
    biblioteca estándar se sigue leyendo del paquete si ``con_stdlib``.
    """

    def __init__(self, archivos: dict[str, str], con_stdlib: bool = True):
        self.archivos = {os.path.abspath(k): v for k, v in archivos.items()}
        self._disco = CargadorArchivos() if con_stdlib else None

    def existe(self, ruta: str) -> bool:
        """True si la ruta está en el diccionario (o es de la biblioteca)."""
        ruta = os.path.abspath(ruta)
        if ruta in self.archivos:
            return True
        return (
            self._disco is not None and _dentro_de(ruta, RAIZ_STDLIB) and self._disco.existe(ruta)
        )

    def leer(self, ruta: str) -> str:
        """Texto del módulo."""
        ruta = os.path.abspath(ruta)
        if ruta in self.archivos:
            return self.archivos[ruta]
        if self._disco is not None and _dentro_de(ruta, RAIZ_STDLIB):
            return self._disco.leer(ruta)
        raise ErrorCargaModulo(M("IL-MOD-001.no_encontrado", ruta=os.path.basename(ruta)))


@dataclass
class Modulo:
    """Un archivo importado ya analizado."""

    ruta_real: str
    nombre: str  # nombre para mostrar en diagnósticos
    programa: Program
    dependencias: list[str] = field(default_factory=list)  # rutas reales
    valido: bool = True


def _con_extension(ruta: str) -> str:
    return ruta if os.path.splitext(ruta)[1] else ruta + ".inv"


def _dentro_de(ruta: str, raiz: str) -> bool:
    ruta_r, raiz_r = os.path.realpath(ruta), os.path.realpath(raiz)
    return ruta_r == raiz_r or ruta_r.startswith(raiz_r + os.sep)


def declaraciones_exportables(prog: Program) -> list:
    """Nodos de nivel superior que un módulo aporta a quien lo importa."""
    globales = list(prog.declaraciones_globales) + list(prog.declaraciones_posteriores)
    return list(prog.subrutinas) + list(prog.clases) + list(prog.enums) + globales


def _marcar_origen(prog: Program, nombre: str) -> None:
    """Anota el archivo de origen en cada declaración (y en métodos/constructores)."""
    for nodo in declaraciones_exportables(prog):
        nodo.archivo_origen = nombre
        if isinstance(nodo, ClassDecl):
            for miembro in list(nodo.metodos) + list(nodo.constructores) + list(nodo.atributos):
                miembro.archivo_origen = nombre


class Enlazador:
    """Resuelve las importaciones de un programa y le agrega sus declaraciones."""

    def __init__(self, error_manager: ErrorManager, cargador: CargadorModulos | None = None):
        self.em = error_manager
        self.cargador = cargador or CargadorArchivos()
        self._modulos: dict[str, Modulo | None] = {}  # ruta real -> módulo (None = en curso)
        self._orden: list[Modulo] = []  # post-orden: dependencias primero

    # ---- API ----

    def enlazar(self, prog: Program, ruta_fuente: str | None) -> Program:
        """Enlaza ``prog`` (analizado de ``ruta_fuente``) con sus módulos."""
        if not prog.importaciones:
            return prog
        dir_principal = self._directorio_de(ruta_fuente)
        nombre_principal = self.em.archivo_base
        # El propio programa encabeza la pila: importarse a sí mismo (o que
        # un módulo lo importe de vuelta) es un ciclo, no una carga más.
        real_principal = (
            os.path.realpath(ruta_fuente) if ruta_fuente and not ruta_fuente.startswith("<") else ""
        )
        pila = [(real_principal, nombre_principal)]
        for imp in prog.importaciones:
            self._importar(imp, dir_principal, dir_principal, pila, nombre_principal)
        if self.em.hay_errores():
            return prog
        self._fusionar(prog, nombre_principal)
        prog.modulos = [m.nombre for m in self._orden]
        prog.rutas_modulos = {m.nombre: m.ruta_real for m in self._orden}
        # Las advertencias del código de los módulos ya se informaron al
        # verificarlos por separado; no repetirlas en el análisis conjunto.
        self.em.avisos_solo_de = nombre_principal
        return prog

    # ---- resolución ----

    @staticmethod
    def _directorio_de(ruta_fuente: str | None) -> str:
        # "<en_vivo>", "<desconocido>"...: editores sin archivo guardado.
        if ruta_fuente and not ruta_fuente.startswith("<"):
            return os.path.dirname(os.path.abspath(ruta_fuente))
        return os.getcwd()

    def _resolver(self, texto: str, dir_imp: str, raiz: str):
        """Retorna (ruta_real, raiz_del_modulo, nombre_visible) o un Mensaje de error."""
        relativa = _con_extension(texto)
        try:
            security.validar_ruta_relativa(relativa)
        except ValueError:
            return M("IL-MOD-002.ruta_invalida", ruta=texto)
        if os.path.splitext(relativa)[1].lower() != ".inv":
            return M("IL-MOD-002.ruta_invalida", ruta=texto)
        candidatos = [(os.path.join(dir_imp, relativa), raiz)]
        if not _dentro_de(dir_imp, RAIZ_STDLIB):
            candidatos.append((os.path.join(RAIZ_STDLIB, relativa), RAIZ_STDLIB))
        for ruta, raiz_mod in candidatos:
            if self.cargador.existe(ruta):
                if not _dentro_de(ruta, raiz_mod):
                    return M("IL-MOD-002.fuera_de_carpeta", ruta=texto)
                real = os.path.realpath(ruta)
                rel = os.path.relpath(real, os.path.realpath(raiz_mod)).replace(os.sep, "/")
                nombre = f"{PREFIJO_STDLIB}/{rel}" if raiz_mod == RAIZ_STDLIB else rel
                return real, raiz_mod, nombre
        return M("IL-MOD-001.no_encontrado", ruta=texto)

    def _error(self, archivo: str, nodo, mensaje) -> None:
        previo = self.em.archivo_actual
        self.em.archivo_actual = archivo
        codigo = mensaje.clave.split(".")[0]
        self.em.error_semantico(codigo, mensaje, nodo.linea, nodo.columna)
        self.em.archivo_actual = previo

    def _importar(self, imp: ImportDecl, dir_imp: str, raiz: str, pila: list, archivo: str):
        resuelto = self._resolver(imp.ruta, dir_imp, raiz)
        if not isinstance(resuelto, tuple):
            self._error(archivo, imp, resuelto)
            return None
        real, raiz_mod, nombre = resuelto
        if real in [r for r, _ in pila]:
            cadena = " -> ".join([n for _, n in pila] + [nombre])
            self._error(archivo, imp, M("IL-MOD-003.ciclo", cadena=cadena))
            return None
        if real in self._modulos:
            return real
        if len(self._modulos) >= MAX_MODULOS:
            self._error(archivo, imp, M("IL-MOD-007.demasiados", limite=MAX_MODULOS))
            return None
        self._modulos[real] = None
        modulo = self._cargar(real, nombre, imp, archivo)
        if modulo is None:
            return real
        for sub in modulo.programa.importaciones:
            dep = self._importar(
                sub, os.path.dirname(real), raiz_mod, pila + [(real, nombre)], nombre
            )
            if dep is not None:
                modulo.dependencias.append(dep)
        if all(self._dependencia_valida(d) for d in modulo.dependencias):
            self._verificar_aislado(modulo)
        else:
            modulo.valido = False
        self._modulos[real] = modulo
        self._orden.append(modulo)
        return real

    def _dependencia_valida(self, ruta_real: str) -> bool:
        dep = self._modulos.get(ruta_real)
        return dep is not None and dep.valido

    def _cargar(self, real: str, nombre: str, imp: ImportDecl, archivo: str) -> Modulo | None:
        # Import diferido: parser.py importa este módulo para enlazar.
        from .lexer import Lexer
        from .parser import Parser

        try:
            codigo = self.cargador.leer(real)
        except ErrorCargaModulo as e:
            self._error(archivo, imp, e.mensaje)
            return None
        em_mod = ErrorManager(idioma=self.em.idioma_efectivo)
        lexer = Lexer(em_mod)
        prog, _ = Parser(lexer, em_mod).analizar(codigo, nombre, enlazar=False)
        if prog is not None and not em_mod.hay_errores():
            for d in list(prog.declaraciones_globales) + list(prog.declaraciones_posteriores):
                exportable = isinstance(d, ConstDecl) or (
                    isinstance(d, ArrayDecl) and getattr(d, "es_constante", False)
                )
                if not exportable:
                    em_mod.error_semantico(
                        "IL-MOD-005",
                        M("IL-MOD-005.no_importable", nombre=d.nombre),
                        d.linea,
                        d.columna,
                    )
        self.em.absorber(em_mod)
        if prog is None or em_mod.hay_errores():
            return None
        prog.main = None  # el main de un módulo no se importa
        _marcar_origen(prog, nombre)
        return Modulo(real, nombre, prog)

    # ---- verificación aislada ----

    def _transitivas(self, modulo: Modulo, vistos: set | None = None) -> list[Modulo]:
        vistos = vistos if vistos is not None else set()
        resultado = []
        for dep in modulo.dependencias:
            if dep in vistos:
                continue
            vistos.add(dep)
            m = self._modulos.get(dep)
            if m is not None:
                resultado.extend(self._transitivas(m, vistos))
                resultado.append(m)
        return resultado

    def _verificar_aislado(self, modulo: Modulo) -> None:
        """Semántica + tipos del módulo con sus dependencias y un main vacío."""
        from .semantic import SemanticAnalyzer
        from .type_checker import TypeChecker

        prueba = Program()
        for m in self._transitivas(modulo) + [modulo]:
            p = m.programa
            prueba.subrutinas += p.subrutinas
            prueba.clases += p.clases
            prueba.enums += p.enums
            prueba.declaraciones_globales += p.declaraciones_globales + p.declaraciones_posteriores
        prueba.main = MainDecl(Bloque([]), 0, 0)
        prueba = copy.deepcopy(prueba)  # el semántico reescribe genéricos y tipos suma
        em_mod = ErrorManager(idioma=self.em.idioma_efectivo)
        em_mod.set_archivo(modulo.nombre)
        em_mod.avisos_solo_de = modulo.nombre
        tabla = SemanticAnalyzer(em_mod).analizar(prueba)
        if not em_mod.hay_errores():
            TypeChecker(em_mod, tabla).verificar(prueba)
        self.em.absorber(em_mod)
        modulo.valido = not em_mod.hay_errores()

    # ---- fusión ----

    @staticmethod
    def _nombre_decl(nodo):
        return getattr(nodo, "nombre", None)

    def _fusionar(self, prog: Program, nombre_principal: str) -> None:
        vistos: dict[str, str] = {}
        subrutinas, clases, enums, globales = [], [], [], []
        for m in self._orden:
            p = m.programa
            for nodo in declaraciones_exportables(p):
                nombre = self._nombre_decl(nodo)
                if nombre in vistos:
                    self._error(
                        m.nombre,
                        nodo,
                        M(
                            "IL-MOD-004.conflicto",
                            nombre=nombre,
                            otro=vistos[nombre],
                            archivo=m.nombre,
                        ),
                    )
                    continue
                vistos[nombre] = m.nombre
                if isinstance(nodo, ClassDecl):
                    clases.append(nodo)
                elif isinstance(nodo, EnumDecl):
                    enums.append(nodo)
                elif isinstance(nodo, (ConstDecl, ArrayDecl)):
                    globales.append(nodo)
                else:
                    subrutinas.append(nodo)
        for nodo in declaraciones_exportables(prog):
            nombre = self._nombre_decl(nodo)
            if nombre in vistos:
                self._error(
                    nombre_principal,
                    nodo,
                    M(
                        "IL-MOD-004.conflicto",
                        nombre=nombre,
                        otro=vistos[nombre],
                        archivo=nombre_principal,
                    ),
                )
        prog.subrutinas = subrutinas + prog.subrutinas
        prog.clases = clases + prog.clases
        prog.enums = enums + prog.enums
        prog.declaraciones_globales = globales + prog.declaraciones_globales


def enlazar(prog, ruta_fuente, error_manager, cargador=None):
    """Atajo: enlaza ``prog`` con sus módulos usando ``cargador`` (o el disco)."""
    return Enlazador(error_manager, cargador).enlazar(prog, ruta_fuente)
