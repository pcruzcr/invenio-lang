# Módulo de gestión de errores de InvenioLang 1.0
# Implementa el catálogo oficial de errores (Sección 15)
# Formato oficial (§15.8.1): [IL-XXX-NNN] archivo:linea:columna — Mensaje
# Patrones aplicados: Observer (notificación desacoplada), Strategy (formateo),
# Singleton (instancia global opcional), Chain of Responsibility (filtros)
from __future__ import annotations

from typing import Any

from .patterns import Observer, Strategy, StrategyContext, Subject


class InvenioLangError(Exception):
    """Clase base para errores de InvenioLang."""

    def __init__(self, codigo, mensaje, linea=1, columna=1, archivo="<desconocido>"):
        self.codigo = codigo
        self.mensaje = mensaje
        self.linea = linea
        self.columna = columna
        self.archivo = archivo
        super().__init__(str(self))

    def __str__(self):
        return f"[{self.codigo}] {self.archivo}:{self.linea}:{self.columna} — {self.mensaje}"

    def formato_oficial(self):
        """Retorna el mensaje en el formato oficial definido en §15.8."""
        return f"[{self.codigo}] {self.archivo}:{self.linea}:{self.columna} — {self.mensaje}"


class ErrorFormatterStrategy(Strategy):
    """Strategy para formateo de errores — intercambiable (texto, JSON, HTML)."""

    def execute(self, error: InvenioLangError, *args, **kwargs) -> str:
        """Ejecuta la operación."""
        return error.formato_oficial()


class JsonFormatterStrategy(Strategy):
    """Estrategia json formatter."""

    def execute(self, error: InvenioLangError, *args, **kwargs) -> dict[str, Any]:
        """Ejecuta la operación."""
        return {
            "codigo": error.codigo,
            "mensaje": error.mensaje,
            "linea": error.linea,
            "columna": error.columna,
            "archivo": error.archivo,
            "formato": error.formato_oficial(),
        }


class ErrorObserver(Observer):
    """Observer base para IDE/CLI/logger — suscribirse a ErrorManager."""

    def update(self, event: str, data: Any) -> None:
        """Recibe un evento del Subject."""
        pass


class ErrorManager(Subject):
    """Gestiona la recoleccion y reporte de errores durante la compilacion.

    Permite continuar el analisis despues de errores no fatales.
    Patrones: Subject/Observer (notifica a IDE/CLI), Strategy (formateo).
    Optimización: notificación O(1) por error, sin polling.
    """

    def __init__(self, max_errores=50):
        super().__init__()
        self.errores: list[InvenioLangError] = []
        self.warnings: list[InvenioLangError] = []
        self.max_errores = max_errores
        self.archivo_actual = "<desconocido>"
        self.detener = False
        # Strategy para formateo extensible
        self._formatter_ctx = StrategyContext(ErrorFormatterStrategy())
        self._formatter_ctx.register("texto", ErrorFormatterStrategy())
        self._formatter_ctx.register("json", JsonFormatterStrategy())

    def set_archivo(self, archivo):
        """Establece el archivo actual para los mensajes de error."""
        self.archivo_actual = archivo

    def _registrar(self, err: InvenioLangError) -> None:
        """Template method interno — registra y notifica (Observer)."""
        self.errores.append(err)
        self.notify("error", err)
        if len(self.errores) >= self.max_errores:
            self.detener = True
            self.notify("limite_alcanzado", self.max_errores)

    def error_lexico(self, codigo, mensaje, linea, columna):
        """Registra un error lexico (IL-LEX)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self._registrar(err)

    def error_sintactico(self, codigo, mensaje, linea, columna):
        """Registra un error sintactico (IL-SIN)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self._registrar(err)

    def error_semantico(self, codigo, mensaje, linea, columna):
        """Registra un error semantico (IL-SEM)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self._registrar(err)

    def error_tipo(self, codigo, mensaje, linea, columna):
        """Registra un error de tipos (IL-TIPO)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self._registrar(err)

    def error_poo(self, codigo, mensaje, linea, columna):
        """Registra un error de POO (IL-POO, InvenioLang 2.0 -- docs/.

        InvenioLang_2.0_POO.md).
        """
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self._registrar(err)

    def error_estructurado(self, codigo, mensaje, linea, columna):
        """Registra un error IL-EST (Etapa 6).

        Etapa 6 -- switch/do-while/ternario/try-catch). Prefijo propio, igual
        que IL-POO, para no perturbar el catálogo v1.0 (§18.1: estable entre
        versiones).
        """
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self._registrar(err)

    def error_ejecucion(self, codigo, mensaje, linea, columna):
        """Registra un error de ejecucion (IL-EJE)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self.errores.append(err)
        self.notify("error_ejecucion", err)
        # Los errores de ejecucion detienen inmediatamente

    def advertencia(self, codigo, mensaje, linea, columna):
        """Registra una advertencia (IL-WARN)."""
        warn = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self.warnings.append(warn)
        self.notify("advertencia", warn)

    def hay_errores(self):
        """Indica si hay errores registrados."""
        return len(self.errores) > 0

    def hay_errores_fatales(self):
        """Indica si hay errores que impiden continuar."""
        return self.detener or self.hay_errores()

    def obtener_reportes(self):
        """Retorna los errores formateados, en orden de aparicion (§15.8.2). Strategy texto."""
        self.errores.sort(key=lambda e: (e.linea, e.columna))
        return [self._formatter_ctx.execute_named("texto", e) for e in self.errores]

    def obtener_advertencias(self):
        """Retorna las advertencias formateadas, en orden de aparicion."""
        self.warnings.sort(key=lambda w: (w.linea, w.columna))
        return [w.formato_oficial() for w in self.warnings]

    def obtener_reportes_json(self):
        """Retorna errores como lista de dicts (para --json / IDE). Strategy json."""
        self.errores.sort(key=lambda e: (e.linea, e.columna))
        return [self._formatter_ctx.execute_named("json", e) for e in self.errores]

    def imprimir_reportes(self):
        """Imprime errores y advertencias en orden de aparicion (§15.8.2)."""
        for reporte in self.obtener_reportes():
            print(reporte)
        for aviso in self.obtener_advertencias():
            print(aviso)
        self.notify(
            "impresion_completa", {"errores": len(self.errores), "warnings": len(self.warnings)}
        )

    def resumen(self):
        """Resumen rápido para barra de estado / accesibilidad."""
        return {
            "errores": len(self.errores),
            "advertencias": len(self.warnings),
            "detener": self.detener,
        }

    def limpiar(self):
        """Limpia todos los errores y advertencias."""
        self.errores.clear()
        self.warnings.clear()
        self.detener = False
        self.notify("limpieza", None)

    # Facade para suscripción rápida (útil para GUI)
    def suscribir_consola(self) -> ErrorObserver:
        """Suscribe la consola a los errores."""
        obs = _ConsolaObserver()
        self.attach(obs)
        return obs


class _ConsolaObserver(ErrorObserver):
    def update(self, event: str, data: Any) -> None:
        """Recibe un evento del Subject."""
        if event == "error":
            pass  # hook para logging futuro
