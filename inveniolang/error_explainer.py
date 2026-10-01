# error_explainer.py — H1.1 Profesional mínimo viable
# Patrón Strategy + Factory + Template Method
# Cada IL-XXX-NNN es una Strategy con explicación, ejemplo y fix de 1 línea.
# Reusa ErrorManager Observer para inyección automática en IDE.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .patterns import Observer, RegistryFactory, Strategy


@dataclass(frozen=True)
class Explicacion:
    """Explicación de un error del catálogo."""

    codigo: str
    titulo: str
    por_que: str
    ejemplo_malo: str
    ejemplo_bueno: str
    fix: str
    nivel: str  # nivel curriculum: L1 Sintaxis, L2 Control, L3 Estructuras, L4 POO


class BaseExplainer(Strategy):
    """BaseExplainer como estrategia intercambiable."""

    def execute(self, *args, **kwargs) -> Explicacion | None:
        """Ejecuta la operación."""
        raise NotImplementedError


# Catálogo — Strategy por código. Fábrica centraliza.
_CATALOGO: dict[str, Explicacion] = {
    "IL-LEX-002": Explicacion(
        "IL-LEX-002",
        "Carácter inválido",
        "Usaste @ # $ no permitidos.",
        "int x = 5 @ 3;",
        "int x = 5 + 3;",
        "Reemplaza @ por operador válido (+ - * /).",
        "L1",
    ),
    "IL-LEX-004": Explicacion(
        "IL-LEX-004",
        "Identificador con digito",
        "Nombres no inician con numero.",
        "int 1x = 5;",
        "int x1 = 5;",
        "Renombra a x1.",
        "L1",
    ),
    "IL-SIN-010": Explicacion(
        "IL-SIN-010",
        "Falta punto y coma",
        "Toda instrucción termina en ;",
        "int x = 5",
        "int x = 5;",
        "Añade ; al final.",
        "L1",
    ),
    "IL-SIN-030": Explicacion(
        "IL-SIN-030",
        "Condición if sin paréntesis",
        "if requiere (cond).",
        "si x>0 { }",
        "si (x>0) { }",
        "Envuelve condición en ().",
        "L2",
    ),
    "IL-SIN-031": Explicacion(
        "IL-SIN-031",
        "Cuerpo sin llaves",
        "InvenioLang exige { }.",
        "si (x>0) imprimir(x);",
        "si (x>0) { imprimir(x); }",
        "Añade { }.",
        "L2",
    ),
    "IL-SEM-002": Explicacion(
        "IL-SEM-002",
        "Identificador duplicado",
        "Nombre ya declarado.",
        "int x; int x;",
        "int x; int y;",
        "Usa nombres distintos.",
        "L2",
    ),
    "IL-SEM-003": Explicacion(
        "IL-SEM-003",
        "No declarado",
        "Usas variable sin declarar.",
        "imprimir(z);",
        "int z=1; imprimir(z);",
        "Declara antes de usar.",
        "L2",
    ),
    "IL-SEM-031": Explicacion(
        "IL-SEM-031",
        "Asignar a constante",
        "const no se reasigna.",
        "const int N=5; N=6;",
        "int N=5; N=6;",
        "Quita const o no reasignes.",
        "L2",
    ),
    "IL-SEM-040": Explicacion(
        "IL-SEM-040",
        "break fuera de ciclo",
        "break solo en while/for/switch.",
        "void main(){ romper; }",
        "mientras(x>0){ romper; }",
        "Mueve break dentro de ciclo.",
        "L2",
    ),
    "IL-TIPO-001": Explicacion(
        "IL-TIPO-001",
        "Tipo incompatible",
        "int vs string no compatible.",
        'int x = "hola";',
        'texto x = "hola";',
        "Alinea tipo variable y expresión.",
        "L2",
    ),
    "IL-TIPO-016": Explicacion(
        "IL-TIPO-016",
        "++ sobre no entero",
        "Solo int admite ++.",
        "float f=1.5; f++;",
        "int i=5; i++;",
        "Usa int para ++.",
        "L2",
    ),
    "IL-TIPO-019": Explicacion(
        "IL-TIPO-019",
        "Condición no bool",
        "if/while exige bool.",
        "si (5) { }",
        "si (5>0) { }",
        "Usa comparación que dé bool.",
        "L2",
    ),
    "IL-EJE-010": Explicacion(
        "IL-EJE-010",
        "Variable no inicializada",
        "Lectura sin valor.",
        "int x; imprimir(x);",
        "int x=0; imprimir(x);",
        "Inicializa al declarar.",
        "L2",
    ),
    "IL-EJE-006": Explicacion(
        "IL-EJE-006",
        "División por cero entera",
        "Divisor 0 no permitido.",
        "int x=5/0;",
        "int x=5/2;",
        "Verifica divisor !=0.",
        "L2",
    ),
    "IL-EJE-050": Explicacion(
        "IL-EJE-050",
        "Índice fuera de rango",
        "Arreglo 0..n-1.",
        "int[3] a; a[5]=1;",
        "int[3] a; a[2]=1;",
        "Verifica límites.",
        "L3",
    ),
    "IL-POO-001": Explicacion(
        "IL-POO-001",
        "Clase duplicada",
        "Nombre ya usado.",
        "clase A{} clase A{}",
        "clase A{} clase B{}",
        "Renombra.",
        "L4",
    ),
    "IL-POO-005": Explicacion(
        "IL-POO-005",
        "Miembro privado",
        "No accesible fuera.",
        "obj.privado",
        "obj.publico",
        "Cambia a publico o usa getter.",
        "L4",
    ),
    "IL-POO-020": Explicacion(
        "IL-POO-020",
        "Instanciar abstracta",
        "No se puede con nuevo.",
        "nuevo Figura()",
        "nuevo Circulo()",
        "Instancia clase concreta.",
        "L4",
    ),
}


class ErrorExplainerFactory(RegistryFactory):
    """Factoría error explainer."""

    _default: ErrorExplainerFactory | None = None

    @classmethod
    def get_default(cls) -> ErrorExplainerFactory:
        """Retorna la instancia compartida."""
        if cls._default is None:
            cls._default = cls()
            for cod, exp in _CATALOGO.items():
                cls._default.register(cod, lambda e=exp: e)
        return cls._default

    def explicar(self, codigo: str) -> Explicacion | None:
        """Explica un código de error."""
        try:
            return self.create(codigo)
        except ValueError:
            prefix = codigo.split("-")[1] if "-" in codigo else ""
            fallback = {
                "LEX": Explicacion(
                    codigo,
                    "Error léxico",
                    "Revisa sintaxis básica.",
                    "",
                    "",
                    "Revisa léxico.",
                    "L1",
                ),
                "SIN": Explicacion(
                    codigo,
                    "Error sintáctico",
                    "Revisa gramática.",
                    "",
                    "",
                    "Revisa sintaxis.",
                    "L2",
                ),
                "SEM": Explicacion(
                    codigo,
                    "Error semántico",
                    "Revisa declaraciones/alcance.",
                    "",
                    "",
                    "Revisa semántica.",
                    "L3",
                ),
                "TIPO": Explicacion(
                    codigo,
                    "Error de tipos",
                    "Revisa compatibilidad.",
                    "",
                    "",
                    "Revisa tipos.",
                    "L3",
                ),
                "EJE": Explicacion(
                    codigo,
                    "Error en ejecución",
                    "Fallo runtime.",
                    "",
                    "",
                    "Revisa ejecución.",
                    "L3",
                ),
                "POO": Explicacion(
                    codigo, "Error POO", "Revisa clases/herencia.", "", "", "Revisa POO.", "L4"
                ),
            }
            return fallback.get(prefix)


def explicar(codigo: str) -> Explicacion | None:
    """Explica un código de error."""
    return ErrorExplainerFactory.get_default().explicar(codigo)


def explicar_mensaje(codigo: str, mensaje: str, linea: int, col: int) -> str:
    """Explica un error con su posición."""
    exp = explicar(codigo)
    if not exp:
        return f"[{codigo}] {mensaje} (L{linea}:C{col})"
    return (
        f"[{exp.codigo}] {exp.titulo}\n"
        f"Por qué: {exp.por_que}\n"
        f"Malo:  {exp.ejemplo_malo}\n"
        f"Bueno: {exp.ejemplo_bueno}\n"
        f"Fix: {exp.fix}\n"
        f"Nivel: {exp.nivel} | L{linea}:C{col} — {mensaje}"
    )


# Para IDE: Observer que inyecta explicación en tooltip


class ExplainerObserver(Observer):
    """Observador explainer."""

    def update(self, event: str, data: Any) -> None:
        """Recibe un evento del Subject."""
        if event in ("error", "error_ejecucion") and hasattr(data, "codigo"):
            exp = explicar(data.codigo)
            if exp:
                data._explicacion = exp  # adjunta para GUI
