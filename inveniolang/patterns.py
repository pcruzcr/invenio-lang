# patterns.py — Infraestructura de Patrones de Diseño para InvenioLang
#
# Centraliza implementaciones profesionales de patrones GoF optimizados
# para el compilador educativo. Todos los patrones son ligeros, sin
# dependencias externas y con docstring pedagógico (útil para clase de
# Diseño de Software).
#
# Patrones implementados:
#   Visitor, Strategy, Factory, Observer, Singleton, Command, Decorator,
#   Facade, Builder, Template Method, Chain of Responsibility, Memento
#
# Uso: importar y extender; no modifica comportamiento existente, solo
# estructura el código para optimizar mantenibilidad, testabilidad y
# extensibilidad (abierto/cerrado).

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")

# ============================================================
# Singleton — Para gestores globales (ErrorManager, SymbolTable,
# configuración IDE). Thread-safe vía lock.
# Pedagogía: garantiza 1 instancia, evita estado global disperso.
# ============================================================


class SingletonMeta(type):
    """Metaclase Singleton thread-safe."""

    _instances: dict[type, Any] = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        """Crea o retorna la instancia única."""
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


# ============================================================
# Observer — Para desacoplar productores de errores/eventos de
# consumidores (IDE, CLI, logger, analítica). Optimiza al evitar
# acoplamiento directo y permitir múltiples suscriptores.
# ============================================================


class Observer(ABC):
    """Observador observer."""

    @abstractmethod
    def update(self, event: str, data: Any) -> None:
        """Recibe un evento del Subject."""
        pass


class Subject:
    """Sujeto observable."""

    def __init__(self):
        self._observers: list[Observer] = []
        self._lock = threading.Lock()

    def attach(self, observer: Observer) -> None:
        """Suscribe un observador."""
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """Elimina un observador suscrito."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def notify(self, event: str, data: Any = None) -> None:
        """Notifica un evento a los observadores."""
        for obs in list(self._observers):
            try:
                obs.update(event, data)
            except Exception:  # noqa: S110 - Observer nunca debe romper al Subject
                pass  # Observer nunca debe romper al Subject

    def observer_count(self) -> int:
        """Cuenta los observadores suscritos."""
        return len(self._observers)


# ============================================================
# Strategy — Encapsula algoritmos intercambiables (formateo de
# errores, optimizaciones TAC, operaciones aritméticas, validación).
# Optimiza al evitar if/else gigantes y permitir OCP.
# ============================================================


class Strategy(ABC):
    """Estrategia strategy."""

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Ejecuta la operación."""
        pass


class StrategyContext:
    """Contexto de estrategias intercambiables."""

    def __init__(self, strategy: Strategy | None = None):
        self._strategy = strategy
        self._strategies: dict[str, Strategy] = {}

    def register(self, name: str, strategy: Strategy) -> None:
        """Registra un creador en la factoría."""
        self._strategies[name] = strategy
        if self._strategy is None:
            self._strategy = strategy

    def set_strategy(self, name_or_strategy) -> None:
        """Fija la estrategia activa."""
        if isinstance(name_or_strategy, str):
            if name_or_strategy in self._strategies:
                self._strategy = self._strategies[name_or_strategy]
        else:
            self._strategy = name_or_strategy

    def execute(self, *args, **kwargs) -> Any:
        """Ejecuta la operación."""
        if self._strategy is None:
            raise ValueError("No strategy set")
        return self._strategy.execute(*args, **kwargs)

    def execute_named(self, name: str, *args, **kwargs) -> Any:
        """Ejecuta la estrategia nombrada."""
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not registered")
        return self._strategies[name].execute(*args, **kwargs)


# ============================================================
# Factory — Creación centralizada de objetos (nodos AST, tokens,
# instrucciones TAC, widgets). Optimiza al centralizar validación
# y permitir pooling/caching si se necesita.
# ============================================================


class Factory(ABC):
    """Factoría factory."""

    @abstractmethod
    def create(self, kind: str, *args, **kwargs) -> Any:
        """Crea el objeto solicitado."""
        pass


class RegistryFactory(Factory):
    """Factoría registry."""

    def __init__(self):
        self._registry: dict[str, Callable] = {}
        self._cache: dict[str, Any] = {}

    def register(self, kind: str, creator: Callable) -> None:
        """Registra un creador en la factoría."""
        self._registry[kind.lower()] = creator

    def create(self, kind: str, *args, **kwargs) -> Any:
        """Crea el objeto solicitado."""
        key = kind.lower()
        if key not in self._registry:
            raise ValueError(f"Factory: unknown kind '{kind}'. Registered: {list(self._registry)}")
        return self._registry[key](*args, **kwargs)

    def create_cached(self, kind: str, cache_key: str, *args, **kwargs) -> Any:
        """Crea o reutiliza el objeto en caché."""
        if cache_key in self._cache:
            return self._cache[cache_key]
        obj = self.create(kind, *args, **kwargs)
        self._cache[cache_key] = obj
        return obj


# ============================================================
# Visitor — Separa algoritmos de estructura de nodos (AST).
# Optimiza al evitar isinstance gigantes en semantic/type_checker/
# interpreter y permitir agregar operaciones sin modificar nodos.
# Doble despacho: nodo.accept(visitor) → visitor.visit_Nodo(nodo)
# ============================================================


class Visitor(ABC):  # noqa: B024 - base con despacho concreto por diseño
    """Visitante con despacho por nombre de clase."""

    def visit(self, node: Any) -> Any:
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        """Visitante visitor."""
        method_name = f"visit_{type(node).__name__}"
        method = getattr(self, method_name, self.generic_visit)
        return method(node)

    def generic_visit(self, node: Any) -> Any:
        """Visita genérica por introspección."""
        # Introspección genérica para nodos compuestos
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


class Visitable(ABC):
    """Elemento que acepta visitantes."""

    @abstractmethod
    def accept(self, visitor: Visitor) -> Any:
        """Acepta un visitante (doble despacho)."""
        pass


# ============================================================
# Command — Encapsula operaciones como objetos (ejecutar, deshacer,
# cola de comandos para IDE, historial, macros). Optimiza al
# permitir desacoplamiento invocador/receptor y logging.
# ============================================================


class Command(ABC):
    """Comando ejecutable con deshacer."""

    @abstractmethod
    def execute(self) -> Any:
        """Ejecuta la operación."""
        pass

    def undo(self) -> None:  # noqa: B027 - hook opcional con no-op por defecto
        """Deshace el comando."""
        pass

    def can_undo(self) -> bool:
        """Indica si se puede deshacer."""
        return False


class CommandInvoker:
    """Invoca comandos con historial."""

    def __init__(self, max_history: int = 100):
        self._history: list[Command] = []
        self._max_history = max_history

    def execute(self, cmd: Command) -> Any:
        """Ejecuta la operación."""
        result = cmd.execute()
        if cmd.can_undo():
            self._history.append(cmd)
            if len(self._history) > self._max_history:
                self._history.pop(0)
        return result

    def undo_last(self) -> bool:
        """Deshace el último comando."""
        if not self._history:
            return False
        cmd = self._history.pop()
        cmd.undo()
        return True

    def clear_history(self) -> None:
        """Limpia el historial."""
        self._history.clear()


# ============================================================
# Decorator — Añade comportamiento sin modificar clase base
# (logging, validación, caching, seguridad, métricas). Optimiza
# al aplicar cross-cutting concerns de forma composable.
# ============================================================


def decorator_chain(*decorators):
    """Encadena decoradores."""

    def wrapper(func):
        """Envuelve la función con traza."""
        for dec in reversed(decorators):
            func = dec(func)
        return func

    return wrapper


def cached_method(func):
    """Cachea el método."""
    cache = {}

    @wraps(func)
    def wrapped(*args, **kwargs):
        """Envuelve la función con traza."""
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    wrapped._cache = cache  # type: ignore[attr-defined]
    wrapped.cache_clear = lambda: cache.clear()  # type: ignore[attr-defined]
    return wrapped


def logged(level: str = "INFO"):
    """Registra la llamada."""

    def dec(func):
        """Decorador parametrizado."""

        @wraps(func)
        def wrapped(*args, **kwargs):
            """Envuelve la función con traza."""
            # En producción se conectaría a logging; aquí es no-op para no penalizar
            return func(*args, **kwargs)

        return wrapped

    return dec


def validated(validator: Callable):
    """Valida antes de ejecutar."""

    def dec(func):
        """Decorador parametrizado."""

        @wraps(func)
        def wrapped(*args, **kwargs):
            """Envuelve la función con traza."""
            validator(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapped

    return dec


# ============================================================
# Facade — Simplifica subsistemas complejos (pipeline del
# compilador: lex → parse → semantic → type → interpret). Optimiza
# al dar API de alto nivel para CLI/GUI/tests.
# ============================================================


class Facade(ABC):
    """Fachada del subsistema."""

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Ejecuta la operación."""
        pass


# ============================================================
# Builder — Construcción paso a paso de objetos complejos (AST,
# diagramas, informes). Optimiza al separar construcción de
# representación y permitir variantes.
# ============================================================


class Builder(ABC):
    """Constructor builder."""

    @abstractmethod
    def reset(self) -> None:
        """Reinicia el constructor."""
        pass

    @abstractmethod
    def build(self) -> Any:
        """Construye el objeto."""
        pass


# ============================================================
# Template Method — Esqueleto de algoritmo con pasos customizables
# (pipeline de compilación, verificación de tipos). Optimiza al
# evitar duplicación y garantizar orden de fases.
# ============================================================


class TemplatePipeline(ABC):
    """Pipeline con pasos customizables."""

    def run(self, ctx: Any) -> Any:
        """Ejecuta el flujo."""
        self.pre_process(ctx)
        for step in self.steps():
            self.execute_step(ctx, step)
            if self.should_stop(ctx):
                break
        return self.post_process(ctx)

    def pre_process(self, ctx: Any) -> None:  # noqa: B027 - hook opcional con no-op por defecto
        """Prepara el contexto."""
        pass

    def post_process(self, ctx: Any) -> Any:
        """Procesa el resultado final."""
        return ctx

    @abstractmethod
    def steps(self) -> list[str]:
        """Pasos del pipeline."""
        pass

    @abstractmethod
    def execute_step(self, ctx: Any, step: str) -> None:
        """Ejecuta un paso del pipeline."""
        pass

    def should_stop(self, ctx: Any) -> bool:
        """Indica si detener el pipeline."""
        return False


# ============================================================
# Chain of Responsibility — Cadena de manejadores (errores,
# validaciones, optimizaciones). Optimiza al desacoplar emisor
# de manejadores y permitir orden dinámico.
# ============================================================


class Handler(ABC):
    """Manejador de cadena de responsabilidad."""

    def __init__(self):
        self._next: Handler | None = None

    def set_next(self, handler: Handler) -> Handler:
        """Encadena el siguiente manejador."""
        self._next = handler
        return handler

    def handle(self, request: Any) -> Any | None:
        """Atiende la solicitud o la delega."""
        result = self._handle(request)
        if result is not None:
            return result
        if self._next:
            return self._next.handle(request)
        return None

    @abstractmethod
    def _handle(self, request: Any) -> Any | None:
        pass


# ============================================================
# Memento — Captura y restaura estado (interpreter snapshots,
# undo en editor, debug time-travel). Optimiza al externalizar
# estado sin violar encapsulamiento.
# ============================================================


class Memento:
    """Instantánea opaca del estado."""

    def __init__(self, state: Any):
        # Copia superficial optimizada; para estado profundo usar copy.deepcopy
        self._state = state
        import time

        self.timestamp = time.time()

    def get_state(self) -> Any:
        """Retorna el estado guardado."""
        return self._state


class Caretaker:
    """Guarda mementos."""

    def __init__(self, max_mementos: int = 50):
        self._mementos: list[Memento] = []
        self._max = max_mementos

    def save(self, memento: Memento) -> None:
        """Guarda el memento."""
        self._mementos.append(memento)
        if len(self._mementos) > self._max:
            self._mementos.pop(0)

    def restore_last(self) -> Memento | None:
        """Restaura el último memento."""
        if not self._mementos:
            return None
        return self._mementos.pop()

    def count(self) -> int:
        """Cuenta los mementos."""
        return len(self._mementos)

    def clear(self) -> None:
        """Limpia el almacenamiento."""
        self._mementos.clear()
