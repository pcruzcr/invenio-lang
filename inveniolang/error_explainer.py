# error_explainer.py — explicación pedagógica de cada código IL-XXX-NNN
# Patrón Strategy + Factory + Template Method
# Cada IL-XXX-NNN es una Strategy con explicación, ejemplo y fix de 1 línea.
# INV-1403: los textos (título, porqué, ejemplos, arreglo) ya no están
# escritos aquí en español: viven en el catálogo i18n bajo las claves
# ``EXP.<código>.<campo>`` y se presentan en el idioma pedido. Los ejemplos de
# código también se traducen (en inglés usan las palabras clave inglesas),
# porque un ejemplo con "si"/"mientras" no ayuda a quien programa en inglés.
# INV-1018: se eliminó ExplainerObserver (nadie lo usaba); explicar_mensaje
# la consume el hover del servidor LSP.

from __future__ import annotations

from dataclasses import dataclass

from .i18n import t
from .patterns import RegistryFactory, Strategy


@dataclass(frozen=True)
class Explicacion:
    """Explicación de un error del catálogo, ya presentada en un idioma."""

    codigo: str
    titulo: str
    por_que: str
    ejemplo_malo: str
    ejemplo_bueno: str
    fix: str
    nivel: str  # nivel curriculum: L1 Sintaxis, L2 Control, L3 Estructuras, L4 POO


class BaseExplainer(Strategy):
    """Strategy de explicación de un código: presenta sus textos en un idioma."""

    def __init__(self, codigo: str, clave: str, nivel: str):
        self.codigo = codigo
        self.clave = clave  # prefijo de claves del catálogo: EXP.<clave>.<campo>
        self.nivel = nivel

    def execute(self, *args, **kwargs) -> Explicacion:
        """Construye la explicación en ``idioma`` (kwarg; None = idioma actual)."""
        idioma = kwargs.get("idioma")

        def campo(nombre: str) -> str:
            return t(f"EXP.{self.clave}.{nombre}", idioma)

        return Explicacion(
            self.codigo,
            campo("titulo"),
            campo("por_que"),
            campo("malo"),
            campo("bueno"),
            campo("fix"),
            self.nivel,
        )


# Códigos con explicación propia -> nivel del currículo.
NIVELES: dict[str, str] = {
    "IL-LEX-002": "L1",
    "IL-LEX-004": "L1",
    "IL-SIN-010": "L1",
    "IL-SIN-030": "L2",
    "IL-SIN-031": "L2",
    "IL-SEM-002": "L2",
    "IL-SEM-003": "L2",
    "IL-SEM-031": "L2",
    "IL-SEM-040": "L2",
    "IL-TIPO-001": "L2",
    "IL-TIPO-016": "L2",
    "IL-TIPO-019": "L2",
    "IL-EJE-010": "L2",
    "IL-EJE-006": "L2",
    "IL-EJE-050": "L3",
    "IL-POO-001": "L4",
    "IL-POO-005": "L4",
    "IL-POO-020": "L4",
    "IL-MOD-001": "L3",
    "IL-MOD-003": "L3",
    "IL-MOD-004": "L3",
}

# Familias con explicación genérica cuando el código concreto no tiene una.
NIVELES_FAMILIA: dict[str, str] = {
    "LEX": "L1",
    "SIN": "L2",
    "SEM": "L3",
    "TIPO": "L3",
    "EJE": "L3",
    "POO": "L4",
    "EST": "L2",
    "MOD": "L3",
    "WARN": "L2",
}


class ErrorExplainerFactory(RegistryFactory):
    """Factoría error explainer (Registry: código -> Strategy)."""

    _default: ErrorExplainerFactory | None = None

    @classmethod
    def get_default(cls) -> ErrorExplainerFactory:
        """Retorna la instancia compartida."""
        if cls._default is None:
            cls._default = cls()
            for cod, nivel in NIVELES.items():
                cls._default.register(cod, lambda c=cod, n=nivel: BaseExplainer(c, c, n))
        return cls._default

    def explicar(self, codigo: str, idioma: str | None = None) -> Explicacion | None:
        """Explica un código de error en ``idioma`` (None = idioma actual)."""
        try:
            estrategia = self.create(codigo)
        except ValueError:
            familia = codigo.split("-")[1] if codigo.count("-") >= 2 else ""
            nivel = NIVELES_FAMILIA.get(familia)
            if nivel is None:
                return None
            estrategia = BaseExplainer(codigo, familia, nivel)
        return estrategia.execute(idioma=idioma)


def explicar(codigo: str, idioma: str | None = None) -> Explicacion | None:
    """Explica un código de error."""
    return ErrorExplainerFactory.get_default().explicar(codigo, idioma)


def explicar_mensaje(
    codigo: str, mensaje: str, linea: int, col: int, idioma: str | None = None
) -> str:
    """Explicación completa de un diagnóstico (la usa el hover del LSP)."""
    exp = explicar(codigo, idioma)
    if not exp:
        return f"[{codigo}] {mensaje} (L{linea}:C{col})"
    return (
        f"[{exp.codigo}] {exp.titulo}\n"
        f"{t('EXP.etiqueta.por_que', idioma)}: {exp.por_que}\n"
        f"{t('EXP.etiqueta.malo', idioma)}: {exp.ejemplo_malo}\n"
        f"{t('EXP.etiqueta.bueno', idioma)}: {exp.ejemplo_bueno}\n"
        f"{t('EXP.etiqueta.fix', idioma)}: {exp.fix}\n"
        f"{t('EXP.etiqueta.nivel', idioma)}: {exp.nivel} | L{linea}:C{col} — {mensaje}"
    )
