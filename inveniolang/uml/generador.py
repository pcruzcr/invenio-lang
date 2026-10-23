"""Modelo UML → esqueleto InvenioLang que compila, en español o en inglés.

INV-3206: es la otra mitad de la ida y vuelta. Cada clase se escribe con
sus atributos, constructores y métodos con la firma exacta del diagrama; los
cuerpos devuelven el valor por defecto del tipo y llevan un comentario «Por
completar» para el estudiante. Además el esqueleto **reproduce las
relaciones** del diagrama para que, al volver a analizarlo, salga el mismo
modelo (mismo criterio que :mod:`.desde_codigo`):

* composición → el atributo se inicializa con ``nuevo Parte(...)``;
* agregación → el primer constructor (o método) que recibe un parámetro del
  tipo de la parte lo guarda en el atributo;
* dependencia que no se ve en ninguna firma → una variable local de ese
  tipo en el primer cuerpo de la clase.

Lo que InvenioLang no puede expresar se rechaza antes con
:func:`.reglas.validar_generable`; lo que sí puede pero el diagrama dejaba
incompleto (métodos abstractos sin implementar en una clase concreta, una
superclase que exige argumentos) se completa y se explica en un comentario.
"""

from __future__ import annotations

from ..formatter import formatear
from ..i18n import t
from .modelo import (
    PRIMITIVOS,
    Clasificador,
    Constructor,
    DiagramaClases,
    ErrorUML,
    Metodo,
    Parametro,
    Relacion,
)
from .presentacion import literal_codigo, palabra, tipo_visible
from .reglas import abstractos_pendientes, normalizar, tipo_base, validar_generable

__all__ = ["ModeloNoGenerable", "generar_codigo"]


class ModeloNoGenerable(ValueError):
    """El diagrama no se puede escribir en InvenioLang; ``errores`` dice por qué."""

    def __init__(self, errores: list[ErrorUML]):
        self.errores = errores
        super().__init__("\n".join(str(e) for e in errores))


class _Escritor:
    """Escribe el programa línea a línea (Builder); el formateador pone la sangría."""

    def __init__(self, modelo: DiagramaClases, idioma: str):
        self.m = modelo
        self.idioma = idioma
        self.lineas: list[str] = []
        self.clases = {c.nombre: c for c in modelo.clasificadores}

    # ------------------------------------------------------------ piezas

    def kw(self, token: str) -> str:
        return palabra(token, self.idioma)

    def tipo(self, tipo: str) -> str:
        return tipo_visible(tipo, self.idioma)

    def txt(self, clave: str, **args: object) -> str:
        return t(clave, self.idioma, **args)

    def comentario(self, clave: str, **args: object) -> None:
        self.lineas.append("// " + self.txt(clave, **args))

    def vis(self, visibilidad: str) -> str:
        return self.kw("KW_PRIVATE" if visibilidad == "-" else "KW_PUBLIC")

    def parametros(self, params: tuple[Parametro, ...]) -> str:
        return ", ".join(f"{self.tipo(p.tipo)} {p.nombre}" for p in params)

    def defecto(self, tipo: str) -> str | None:
        """Valor por defecto de ``tipo`` como argumento o retorno (None si no existe)."""
        if tipo == "int":
            return "0"
        if tipo == "float":
            return "0.0"
        if tipo == "string":
            return '""'
        if tipo == "bool":
            return self.kw("KW_FALSE")
        if tipo == "int[]" or tipo == "float[]" or tipo == "string[]" or tipo == "bool[]":
            return f"{self.kw('KW_NEW')} {self.tipo(tipo[:-2])}[0]"
        if tipo.endswith("[]"):
            return None
        return self.kw("KW_NULL")

    def argumentos(self, clase: str) -> str | None:
        """Argumentos por defecto para el constructor más sencillo de ``clase``."""
        c = self.clases.get(clase)
        if c is None or not c.constructores:
            return ""
        for ctor in sorted(c.constructores, key=lambda k: len(k.parametros)):
            args = [self.defecto(p.tipo) for p in ctor.parametros]
            if all(a is not None for a in args):
                return ", ".join(str(a) for a in args)
        return None

    # ------------------------------------------------------------ programa

    def orden(self) -> list[Clasificador]:
        """Enumeraciones, interfaces y después clases con cada superclase antes que sus hijas."""
        enums = [c for c in self.m.clasificadores if c.tipo == "enumeracion"]
        ifaces = [c for c in self.m.clasificadores if c.tipo == "interfaz"]
        clases: list[Clasificador] = []

        def visitar(c: Clasificador) -> None:
            if c in clases:
                return
            padre = self.m.padre(c.nombre)
            if padre is not None and padre in self.clases:
                visitar(self.clases[padre])
            clases.append(c)

        for c in self.m.clasificadores:
            if c.tipo in ("clase", "abstracta"):
                visitar(c)
        return enums + ifaces + clases

    def programa(self) -> str:
        self.comentario("UML.gen.cabecera")
        self.comentario("UML.gen.instrucciones")
        for c in self.orden():
            self.lineas.append("")
            if c.tipo == "enumeracion":
                self.enumeracion(c)
            elif c.tipo == "interfaz":
                self.interfaz(c)
            else:
                self.clase(c)
        self.lineas.append("")
        self.lineas.append(f"{self.kw('KW_VOID')} main() {{")
        self.comentario("UML.gen.main")
        self.lineas.append("}")
        return formatear("\n".join(self.lineas))

    def enumeracion(self, c: Clasificador) -> None:
        self.lineas.append(f"{self.kw('KW_ENUM')} {c.nombre} {{")
        for i, lit in enumerate(c.literales):
            carga = f"({self.parametros(lit.parametros)})" if lit.parametros else ""
            coma = "," if i < len(c.literales) - 1 else ""
            self.lineas.append(f"{lit.nombre}{carga}{coma}")
        self.lineas.append("}")

    def interfaz(self, c: Clasificador) -> None:
        self.lineas.append(f"{self.kw('KW_INTERFACE')} {c.nombre} {{")
        for x in c.metodos:
            abstracto = "abstracto" if self.idioma == "es" else "abstract"
            self.lineas.append(
                f"{self.vis(x.visibilidad)} {abstracto} {self.tipo(x.retorno)} "
                f"{x.nombre}({self.parametros(x.parametros)});"
            )
        self.lineas.append("}")

    # ------------------------------------------------------------ clases

    def clase(self, c: Clasificador) -> None:
        cabecera = ""
        if c.tipo == "abstracta":
            cabecera = ("abstracta" if self.idioma == "es" else "abstract") + " "
        cabecera += f"{self.kw('KW_CLASS')} {c.nombre}"
        if c.parametros_tipo:
            cabecera += f"<{c.parametros_tipo[0]}>"
        padre = self.m.padre(c.nombre)
        if padre is not None:
            cabecera += f" {self.kw('KW_EXTENDS')} {padre}"
        interfaces = self.m.interfaces(c.nombre)
        if interfaces:
            cabecera += f" {self.kw('KW_IMPLEMENTS')} {', '.join(interfaces)}"
        self.lineas.append(cabecera + " {")
        inicio = len(self.lineas)
        propias = [r for r in self.m.relaciones if r.origen == c.nombre]
        creaciones = self.atributos(c, propias)
        notas: list[str] = []
        cuerpos = self.cuerpos_extra(c, propias, notas)
        constructores = list(c.constructores)
        llamada_padre = self.llamada_padre(c)
        if llamada_padre is not None and not constructores:
            # Sin constructor propio, la subclase no compila si el padre exige
            # argumentos: se añade uno vacío que se los pasa.
            constructores = [Constructor("+", ())]
            self.comentario("UML.gen.constructor_anadido", padre=padre)
        for i, ctor in enumerate(constructores):
            self.lineas.append("")
            extra = creaciones + cuerpos.get(("ctor", i), [])
            self.constructor(c, ctor, llamada_padre, extra)
        for i, x in enumerate(c.metodos):
            self.lineas.append("")
            self.metodo(c, x, cuerpos.get(("metodo", i), []))
        if c.tipo == "clase":
            for origen, x in abstractos_pendientes(self.m, c):
                self.lineas.append("")
                self.comentario("UML.gen.exigido", origen=origen)
                self.metodo(c, Metodo(x.nombre, x.retorno, "+", x.parametros), [])
        self.lineas.extend("// " + nota for nota in notas)
        if len(self.lineas) > inicio and self.lineas[inicio] == "":
            del self.lineas[inicio]  # sin atributos, el primer miembro va pegado a la cabecera
        self.lineas.append("}")

    def creacion(self, destino: str) -> str | None:
        """``nuevo Parte(args)`` para una composición, o None si la parte no se puede crear."""
        parte = self.clases.get(destino)
        args = self.argumentos(destino)
        if parte is None or parte.tipo != "clase" or args is None:
            return None
        return f"{self.kw('KW_NEW')} {destino}({args})"

    def atributos(self, c: Clasificador, propias: list[Relacion]) -> list[str]:
        """Escribe los atributos; devuelve las creaciones que van en cada constructor.

        Criterio de composición (el mismo de ``desde_codigo``): la clase crea la
        parte con ``nuevo``. Si tiene constructores, cada uno la crea; si no, se
        crea en la inicialización del atributo.
        """
        compuestos = {r.rol: r.destino for r in propias if r.tipo == "composicion"}
        en_constructor: list[str] = []
        este = self.kw("KW_THIS")
        for a in c.atributos:
            if a.visibilidad == "#":
                self.comentario("UML.gen.protegido", nombre=a.nombre)
            if a.constante:
                self.comentario("UML.gen.constante", nombre=a.nombre)
            estatico = f"{self.kw('KW_STATIC')} " if a.estatico else ""
            linea = f"{self.vis(a.visibilidad)} {estatico}{self.tipo(a.tipo)} {a.nombre}"
            if a.valor_inicial is not None:
                linea += " = " + literal_codigo(a.valor_inicial, self.idioma)
            elif a.nombre in compuestos:
                creacion = self.creacion(compuestos[a.nombre])
                if creacion is None:
                    self.comentario("UML.gen.composicion_imposible", nombre=a.nombre)
                elif c.constructores and not a.estatico:
                    en_constructor.append(f"{este}.{a.nombre} = {creacion};")
                else:
                    linea += f" = {creacion}"
            self.lineas.append(linea + ";")
        return en_constructor

    def cuerpos_extra(
        self, c: Clasificador, propias: list[Relacion], notas: list[str]
    ) -> dict[tuple[str, int], list[str]]:
        """Líneas que cada cuerpo necesita para reproducir agregaciones y dependencias.

        Claves ``("ctor", i)`` / ``("metodo", i)``. Lo que no cabe en ningún
        cuerpo se explica en ``notas`` (comentarios al final de la clase).
        """
        miembros: list[tuple[tuple[str, int], tuple[Parametro, ...]]] = [
            (("ctor", i), k.parametros) for i, k in enumerate(c.constructores)
        ]
        miembros += [
            (("metodo", i), x.parametros)
            for i, x in enumerate(c.metodos)
            if not x.abstracto and c.tipo != "interfaz"
        ]
        extra: dict[tuple[str, int], list[str]] = {}
        este = self.kw("KW_THIS")
        for r in propias:
            if r.tipo != "agregacion":
                continue
            for clave, params in miembros:
                p = next((p for p in params if p.tipo == r.destino), None)
                if p is not None:
                    extra.setdefault(clave, []).append(f"{este}.{r.rol} = {p.nombre};")
                    break
            else:
                notas.append(self.txt("UML.gen.agregacion_sin_parametro", nombre=r.rol))
        en_firmas = {tipo_base(p.tipo) for k in c.constructores for p in k.parametros}
        en_firmas |= {tipo_base(p.tipo) for x in c.metodos for p in x.parametros}
        en_firmas |= {tipo_base(x.retorno) for x in c.metodos}
        prefijo = "usa" if self.idioma == "es" else "uses"
        for r in propias:
            if r.tipo != "dependencia" or r.destino in en_firmas:
                continue
            if not miembros:
                notas.append(self.txt("UML.gen.dependencia_sin_cuerpo", destino=r.destino))
                continue
            clave, params = miembros[0]
            ocupados = {p.nombre for p in params}
            nombre = prefijo + r.destino
            while nombre in ocupados:
                nombre += "_"
            destino = self.clases.get(r.destino)
            tipo = r.destino
            if destino is not None and destino.parametros_tipo:
                tipo += f"<{self.tipo('int')}>"
            nota = "// " + self.txt("UML.gen.dependencia", destino=r.destino)
            extra.setdefault(clave, []).extend([nota, f"{tipo} {nombre};"])
        return extra

    def llamada_padre(self, c: Clasificador) -> str | None:
        """``padre(...)`` si la superclase no tiene constructor sin argumentos."""
        padre = self.m.padre(c.nombre)
        sup = self.clases.get(padre) if padre is not None else None
        if sup is None or not sup.constructores:
            return None
        if any(not k.parametros for k in sup.constructores):
            return None
        args = self.argumentos(sup.nombre)
        if args is None:
            raise ModeloNoGenerable(
                [ErrorUML("UML.val.padre_sin_argumentos", clase=c.nombre, padre=sup.nombre)]
            )
        return f"{self.kw('KW_SUPER')}({args});"

    def constructor(
        self, c: Clasificador, ctor: Constructor, llamada_padre: str | None, extra: list[str]
    ) -> None:
        params = self.parametros(ctor.parametros)
        if ctor.visibilidad == "-":
            self.lineas.append(f"{self.vis('-')} constructor {c.nombre}({params}) {{")
        else:
            self.lineas.append(f"{c.nombre}({params}) {{")
        if llamada_padre is not None:
            self.lineas.append(llamada_padre)
        self.lineas.extend(extra)
        self.comentario("UML.gen.completar_constructor")
        self.lineas.append("}")

    def metodo(self, c: Clasificador, x: Metodo, extra: list[str]) -> None:
        mod = ""
        if x.estatico:
            mod = self.kw("KW_STATIC") + " "
        elif x.abstracto:
            mod = ("abstracto" if self.idioma == "es" else "abstract") + " "
        firma = (
            f"{self.vis(x.visibilidad)} {mod}{self.tipo(x.retorno)} "
            f"{x.nombre}({self.parametros(x.parametros)})"
        )
        if x.abstracto:
            self.lineas.append(firma + ";")
            return
        self.lineas.append(firma + " {")
        self.lineas.extend(extra)
        self.comentario("UML.gen.completar_metodo", nombre=x.nombre)
        retorno = self.retorno(c, x)
        self.lineas.extend(retorno)
        self.lineas.append("}")

    def retorno(self, c: Clasificador, x: Metodo) -> list[str]:
        ret = self.kw("KW_RETURN")
        if x.retorno == "void":
            return []
        if x.retorno in PRIMITIVOS:
            return [f"{ret} {self.defecto(x.retorno)};"]
        if x.retorno in c.parametros_tipo:
            # Un genérico no tiene un literal válido para todo T: una variable
            # sin inicializar toma el valor por defecto del tipo concreto.
            ocupados = {p.nombre for p in x.parametros}
            nombre = "valor" if self.idioma == "es" else "value"
            while nombre in ocupados:
                nombre += "_"
            return [f"{x.retorno} {nombre};", f"{ret} {nombre};"]
        enum = self.clases.get(x.retorno)
        if enum is not None and enum.tipo == "enumeracion" and enum.literales:
            if not any(lit.parametros for lit in enum.literales):
                return [f"{ret} {enum.nombre}.{enum.literales[0].nombre};"]
        return [f"{ret} {self.kw('KW_NULL')};"]


def generar_codigo(modelo: DiagramaClases, idioma: str = "es") -> str:
    """Esqueleto InvenioLang del diagrama en ``idioma``.

    :class:`ModeloNoGenerable` (con todos los motivos) si no se puede escribir.
    """
    normal = normalizar(modelo)
    errores = validar_generable(normal)
    if errores:
        raise ModeloNoGenerable(errores)
    return _Escritor(normal, idioma).programa()
