# Módulo de gestión de errores de InvenioLang 1.0
# Implementa el catálogo oficial de errores (Sección 15)
# Formato oficial (§15.8.1): [IL-XXX-NNN] archivo:linea:columna — Mensaje
# Patrones aplicados: Observer (notificación desacoplada), Strategy (formateo).
# INV-1019: se eliminaron hay_errores_fatales, imprimir_reportes (print desde
# el modelo), resumen, suscribir_consola y su observador no-op ("hook para
# logging futuro"): ningún consumidor los usaba.
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from .i18n import Mensaje, idioma_actual, normalizar_idioma
from .patterns import Strategy, StrategyContext, Subject


class InvenioLangError(Exception):
    """Clase base para errores de InvenioLang.

    ``mensaje`` es siempre texto ya presentado en un idioma; si el error se
    creó desde un :class:`~inveniolang.i18n.Mensaje`, ``clave`` y ``args``
    conservan su forma independiente del idioma (INV-1400) para que un IDE o
    el explicador puedan volver a presentarlo en otro idioma.
    """

    def __init__(self, codigo, mensaje, linea=1, columna=1, archivo="<desconocido>", idioma=None):
        self.codigo = codigo
        self.clave = mensaje.clave if isinstance(mensaje, Mensaje) else None
        self.args_mensaje = dict(mensaje.args) if isinstance(mensaje, Mensaje) else {}
        self.mensaje = mensaje.texto(idioma) if isinstance(mensaje, Mensaje) else str(mensaje)
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


class ErrorManager(Subject):
    """Gestiona la recoleccion y reporte de errores durante la compilacion.

    Permite continuar el analisis despues de errores no fatales.
    Patrones: Subject/Observer (notifica a IDE/CLI), Strategy (formateo).
    Optimización: notificación O(1) por error, sin polling.
    """

    def __init__(self, max_errores=50, idioma=None):
        super().__init__()
        # INV-1400: idioma en que se presentan los diagnosticos. None = el
        # idioma del proceso (--idioma / INVENIO_IDIOMA / "es") consultado en
        # cada registro, para no congelar el valor al crear el gestor.
        self.idioma = normalizar_idioma(idioma) if idioma is not None else None
        self.errores: list[InvenioLangError] = []
        self.warnings: list[InvenioLangError] = []
        self.max_errores = max_errores
        self.archivo_actual = "<desconocido>"
        # INV-1420: archivo del programa principal. Con modulos importados,
        # `archivo_actual` cambia temporalmente al del modulo cuyo codigo se
        # analiza (en_origen) y vuelve aqui al terminar.
        self.archivo_base = "<desconocido>"
        # Si no es None, solo se registran advertencias de este archivo: las
        # de un modulo importado ya se informaron al verificarlo por separado.
        self.avisos_solo_de: str | None = None
        self.detener = False
        # Strategy para formateo extensible
        self._formatter_ctx = StrategyContext(ErrorFormatterStrategy())
        self._formatter_ctx.register("texto", ErrorFormatterStrategy())
        self._formatter_ctx.register("json", JsonFormatterStrategy())

    def set_archivo(self, archivo):
        """Establece el archivo actual para los mensajes de error."""
        self.archivo_actual = archivo
        self.archivo_base = archivo

    @contextmanager
    def en_origen(self, nodo):
        """Atribuye los diagnosticos emitidos dentro al archivo de `nodo` (INV-1420).

        Un nodo traido por `importar` lleva `archivo_origen`; los del
        programa principal no, y se atribuyen a `archivo_base`.
        """
        previo = self.archivo_actual
        self.archivo_actual = getattr(nodo, "archivo_origen", None) or self.archivo_base
        try:
            yield
        finally:
            self.archivo_actual = previo

    def absorber(self, otro: ErrorManager) -> None:
        """Incorpora errores y advertencias de otro gestor (p. ej. de un modulo)."""
        for err in otro.errores:
            self._registrar(err)
        for warn in otro.warnings:
            self.warnings.append(warn)
            self.notify("advertencia", warn)

    @property
    def idioma_efectivo(self) -> str:
        """Idioma en que este gestor presenta los mensajes (INV-1400)."""
        return self.idioma or idioma_actual()

    def texto(self, mensaje) -> str:
        """Presenta un ``Mensaje`` (o cualquier objeto) en el idioma del gestor."""
        if isinstance(mensaje, Mensaje):
            return mensaje.texto(self.idioma_efectivo)
        return str(mensaje)

    def _crear(self, codigo, mensaje, linea, columna, archivo=None) -> InvenioLangError:
        """Factory de errores: fija archivo e idioma de presentacion."""
        return InvenioLangError(
            codigo,
            mensaje,
            linea,
            columna,
            archivo if archivo is not None else self.archivo_actual,
            self.idioma_efectivo,
        )

    def _registrar(self, err: InvenioLangError) -> None:
        """Template method interno — registra y notifica (Observer)."""
        self.errores.append(err)
        self.notify("error", err)
        if len(self.errores) >= self.max_errores:
            self.detener = True
            self.notify("limite_alcanzado", self.max_errores)

    def error_lexico(self, codigo, mensaje, linea, columna):
        """Registra un error lexico (IL-LEX)."""
        err = self._crear(codigo, mensaje, linea, columna)
        self._registrar(err)

    def error_sintactico(self, codigo, mensaje, linea, columna):
        """Registra un error sintactico (IL-SIN)."""
        err = self._crear(codigo, mensaje, linea, columna)
        self._registrar(err)

    def error_semantico(self, codigo, mensaje, linea, columna):
        """Registra un error semantico (IL-SEM)."""
        err = self._crear(codigo, mensaje, linea, columna)
        self._registrar(err)

    def error_tipo(self, codigo, mensaje, linea, columna):
        """Registra un error de tipos (IL-TIPO)."""
        err = self._crear(codigo, mensaje, linea, columna)
        self._registrar(err)

    def error_poo(self, codigo, mensaje, linea, columna):
        """Registra un error de POO (IL-POO, InvenioLang 2.0 -- docs/.

        InvenioLang_2.0_POO.md).
        """
        err = self._crear(codigo, mensaje, linea, columna)
        self._registrar(err)

    def error_estructurado(self, codigo, mensaje, linea, columna):
        """Registra un error IL-EST (Etapa 6).

        Etapa 6 -- switch/do-while/ternario/try-catch). Prefijo propio, igual
        que IL-POO, para no perturbar el catálogo v1.0 (§18.1: estable entre
        versiones).
        """
        err = self._crear(codigo, mensaje, linea, columna)
        self._registrar(err)

    def error_ejecucion(self, codigo, mensaje, linea, columna, archivo=None):
        """Registra un error de ejecucion (IL-EJE).

        ``archivo`` permite atribuir el error al modulo importado donde vive
        la subrutina que fallo (INV-1420) en vez de al programa principal.
        """
        err = self._crear(codigo, mensaje, linea, columna, archivo)
        self.errores.append(err)
        self.notify("error_ejecucion", err)
        # Los errores de ejecucion detienen inmediatamente

    def advertencia(self, codigo, mensaje, linea, columna):
        """Registra una advertencia (IL-WARN)."""
        if self.avisos_solo_de is not None and self.archivo_actual != self.avisos_solo_de:
            return
        warn = self._crear(codigo, mensaje, linea, columna)
        self.warnings.append(warn)
        self.notify("advertencia", warn)

    def hay_errores(self):
        """Indica si hay errores registrados."""
        return len(self.errores) > 0

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

    def limpiar(self):
        """Limpia todos los errores y advertencias."""
        self.errores.clear()
        self.warnings.clear()
        self.detener = False
        self.avisos_solo_de = None
        self.notify("limpieza", None)
