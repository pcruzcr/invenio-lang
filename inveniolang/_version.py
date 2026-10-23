# _version.py — fuente única de la versión del compilador.
#
# Antes la cadena "10.0.0" estaba repetida en cinco módulos (__init__, cli,
# config, core, sbom); un bump olvidado en cualquiera de ellos producía
# versiones inconsistentes en --version, el SBOM y los CompileResult.
# INV-4408: InvenioLang 11 (Fase 4: acceso encadenado, estudio visual, cierre).
__version__ = "11.0.0"
