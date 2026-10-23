"""Infraestructura mínima de patrones GoF que el compilador usa de verdad.

Observer (``Subject``/``Observer``: ErrorManager, SymbolTable, Interpreter,
LMS), Strategy (``Strategy``/``StrategyContext``: formateo de errores,
operaciones, emisores Rosetta, sandbox), Factory (``RegistryFactory``: tokens,
nodos AST, instrucciones TAC, catálogo de explicaciones), Visitor
(``Visitor``/``Visitable``: AST) y Memento (``Memento``/``Caretaker``:
instantáneas de la tabla de símbolos y del intérprete).

INV-1018: este módulo declaraba además Singleton, Command/CommandInvoker,
Facade, Builder, Template Method, Chain of Responsibility y cuatro
decoradores (``logged`` era un no-op "en producción se conectaría a
logging") que nada usaba, y ``Visitor.visit`` tenía la misma docstring
repetida 15 veces. Se eliminaron: el patrón Facade del pipeline vive en
``core/compiler.py`` y ``api.py``, no en una clase base vacía.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

__all__ = [
    "Caretaker",
    "Factory",
    "Memento",
    "Observer",
    "RegistryFactory",
    "Strategy",
    "StrategyContext",
    "Subject",
    "Visitable",
    "Visitor",
]


# ---------------------------------------------------------------- Observer
class Observer(ABC):
    """Receptor de eventos de un :class:`Subject`."""

    @abstractmethod
    def update(self, event: str, data: Any) -> None:
        """Recibe un evento del Subject."""


class Subject:
    """Sujeto observable y seguro entre hilos (la IDE ejecuta en un QThread)."""

    def __init__(self) -> None:
        self._observers: list[Observer] = []
        self._lock = threading.Lock()

    def attach(self, observer: Observer) -> None:
        """Suscribe un observador (una sola vez)."""
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def notify(self, event: str, data: Any = None) -> None:
        """Notifica un evento; un observador que falla no rompe al sujeto."""
        for obs in list(self._observers):
            try:
                obs.update(event, data)
            except Exception:  # noqa: S110 - un Observer nunca debe romper al Subject
                pass


# ---------------------------------------------------------------- Strategy
class Strategy(ABC):
    """Algoritmo intercambiable."""

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Ejecuta la operación."""


class StrategyContext:
    """Registro de estrategias con nombre y una estrategia activa."""

    def __init__(self, strategy: Strategy | None = None) -> None:
        self._strategy = strategy
        self._strategies: dict[str, Strategy] = {}

    def register(self, name: str, strategy: Strategy) -> None:
        """Registra una estrategia; la primera pasa a ser la activa si no había."""
        self._strategies[name] = strategy
        if self._strategy is None:
            self._strategy = strategy

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Ejecuta la estrategia activa."""
        if self._strategy is None:
            raise ValueError("No strategy set")
        return self._strategy.execute(*args, **kwargs)

    def execute_named(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Ejecuta la estrategia registrada como ``name``."""
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not registered")
        return self._strategies[name].execute(*args, **kwargs)


# ----------------------------------------------------------------- Factory
class Factory(ABC):
    """Creador de objetos por tipo."""

    @abstractmethod
    def create(self, kind: str, *args: Any, **kwargs: Any) -> Any:
        """Crea el objeto solicitado."""


class RegistryFactory(Factory):
    """Factoría por registro de creadores (claves sin distinguir mayúsculas)."""

    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., Any]] = {}

    def register(self, kind: str, creator: Callable[..., Any]) -> None:
        """Registra un creador en la factoría."""
        self._registry[kind.lower()] = creator

    def create(self, kind: str, *args: Any, **kwargs: Any) -> Any:
        """Crea el objeto solicitado; ``ValueError`` si el tipo no está registrado."""
        key = kind.lower()
        if key not in self._registry:
            raise ValueError(f"Factory: unknown kind '{kind}'. Registered: {list(self._registry)}")
        return self._registry[key](*args, **kwargs)


# ----------------------------------------------------------------- Visitor
class Visitor(ABC):  # noqa: B024 - base con despacho concreto por diseño
    """Visitante con doble despacho por nombre de clase: ``visit_<Clase>``."""

    def visit(self, node: Any) -> Any:
        """Despacha a ``visit_<Clase>`` o, si no existe, a :meth:`generic_visit`."""
        method = getattr(self, f"visit_{type(node).__name__}", self.generic_visit)
        return method(node)

    def generic_visit(self, node: Any) -> Any:
        """Visita los hijos estructurales conocidos de ``node``."""
        for attr in (
            "elementos",
            "bloque",
            "bloque_then",
            "bloque_else",
            "bloque_try",
            "bloque_catch",
            "casos",
            "bloque_default",
            "casos_match",
            "caso_comodin",
            "init_expr",
            "init_exprs",
            "init_filas",
            "condicion",
            "argumento",
            "argumentos",
            "izquierda",
            "derecha",
            "operando",
            "indice",
            "fila",
            "columna",
        ):
            val = getattr(node, attr, None)
            if isinstance(val, list):
                for item in val:
                    if hasattr(item, "accept"):
                        item.accept(self)
                    elif hasattr(item, "visit"):
                        self.visit(item)
            elif val is not None and hasattr(val, "accept"):
                val.accept(self)
        return None


class Visitable:
    """Elemento que acepta visitantes.

    INV-5011: clase simple, no ``ABC``. Todos los nodos del AST heredan de
    aquí y el intérprete hace decenas de ``isinstance`` por instrucción; con
    ``ABCMeta`` cada uno pasaba por ``__instancecheck__`` (~4× más lento) y
    ese costo era casi la mitad del tiempo de un ciclo. El contrato es el
    mismo: quien no redefine ``accept`` falla al usarlo.
    """

    def accept(self, visitor: Visitor) -> Any:
        """Acepta un visitante (doble despacho)."""
        raise NotImplementedError(f"{type(self).__name__} debe implementar accept()")


# ----------------------------------------------------------------- Memento
class Memento:
    """Instantánea opaca del estado (copia superficial; el creador decide)."""

    def __init__(self, state: Any) -> None:
        self._state = state
        self.timestamp = time.time()

    def get_state(self) -> Any:
        """Retorna el estado guardado."""
        return self._state


class Caretaker:
    """Guarda las últimas ``max_mementos`` instantáneas."""

    def __init__(self, max_mementos: int = 50) -> None:
        self._mementos: list[Memento] = []
        self._max = max_mementos

    def save(self, memento: Memento) -> None:
        """Guarda el memento descartando el más antiguo si se supera el máximo."""
        self._mementos.append(memento)
        if len(self._mementos) > self._max:
            self._mementos.pop(0)
