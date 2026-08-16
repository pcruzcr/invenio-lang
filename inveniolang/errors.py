# Módulo de gestión de errores de InvenioLang 1.0
# Implementa el catálogo oficial de errores (Sección 15)
# Formato oficial (§15.8.1): [IL-XXX-NNN] archivo:linea:columna — Mensaje

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


class ErrorManager:
    """Gestiona la recoleccion y reporte de errores durante la compilacion.
    Permite continuar el analisis despues de errores no fatales.
    """

    def __init__(self, max_errores=50):
        self.errores = []
        self.warnings = []
        self.max_errores = max_errores
        self.archivo_actual = "<desconocido>"
        self.detener = False

    def set_archivo(self, archivo):
        """Establece el archivo actual para los mensajes de error."""
        self.archivo_actual = archivo

    def error_lexico(self, codigo, mensaje, linea, columna):
        """Registra un error lexico (IL-LEX)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self.errores.append(err)
        if len(self.errores) >= self.max_errores:
            self.detener = True

    def error_sintactico(self, codigo, mensaje, linea, columna):
        """Registra un error sintactico (IL-SIN)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self.errores.append(err)
        if len(self.errores) >= self.max_errores:
            self.detener = True

    def error_semantico(self, codigo, mensaje, linea, columna):
        """Registra un error semantico (IL-SEM)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self.errores.append(err)
        if len(self.errores) >= self.max_errores:
            self.detener = True

    def error_tipo(self, codigo, mensaje, linea, columna):
        """Registra un error de tipos (IL-TIPO)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self.errores.append(err)
        if len(self.errores) >= self.max_errores:
            self.detener = True

    def error_ejecucion(self, codigo, mensaje, linea, columna):
        """Registra un error de ejecucion (IL-EJE)."""
        err = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self.errores.append(err)
        # Los errores de ejecucion detienen inmediatamente

    def advertencia(self, codigo, mensaje, linea, columna):
        """Registra una advertencia (IL-WARN)."""
        warn = InvenioLangError(codigo, mensaje, linea, columna, self.archivo_actual)
        self.warnings.append(warn)

    def hay_errores(self):
        """Indica si hay errores registrados."""
        return len(self.errores) > 0

    def hay_errores_fatales(self):
        """Indica si hay errores que impiden continuar."""
        return self.detener or self.hay_errores()

    def obtener_reportes(self):
        """Retorna los errores formateados, en orden de aparicion (§15.8.2)."""
        self.errores.sort(key=lambda e: (e.linea, e.columna))
        return [e.formato_oficial() for e in self.errores]

    def obtener_advertencias(self):
        """Retorna las advertencias formateadas, en orden de aparicion."""
        self.warnings.sort(key=lambda w: (w.linea, w.columna))
        return [w.formato_oficial() for w in self.warnings]

    def imprimir_reportes(self):
        """Imprime errores y advertencias en orden de aparicion (§15.8.2)."""
        for reporte in self.obtener_reportes():
            print(reporte)
        for aviso in self.obtener_advertencias():
            print(aviso)

    def limpiar(self):
        """Limpia todos los errores y advertencias."""
        self.errores.clear()
        self.warnings.clear()
        self.detener = False
