# InvenioLang 2.0 - Punto de entrada principal
# Curso: TIIT2002.2 Lenguajes Formales II
# Universidad Invenio
#
# Permite ejecutar el compilador en modo GUI o CLI
#
# Uso:
#   python main.py                     # Modo GUI (por defecto, PySide6)
#   python main.py <archivo.inv>      # Modo CLI
#   python main.py --cli <archivo.inv> # Modo CLI (explícito)
#   python main.py --gui              # Modo GUI (explícito)
#   python main.py --tokens <archivo> # Mostrar tokens
#   python main.py --ast <archivo>    # Mostrar AST
#   python main.py --help             # Ayuda
#   python main.py --version          # Versión

import sys


def _forzar_utf8():
    """Fuerza UTF-8 en la salida estandar.

    La Seccion 2.1 admite cualquier caracter UTF-8 dentro de literales de texto
    y la salida esperada de la Seccion 17.9 incluye simbolos fuera de ASCII.
    En Windows, al redirigir la salida a un archivo o a una tuberia, Python usa
    la codificacion local (cp1252) y esos caracteres provocan
    UnicodeEncodeError. Reconfigurar los flujos evita que un programa valido
    falle solo por como se invoco al compilador.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass  # Flujo ya reemplazado o sin soporte de reconfiguracion


def main():
    """Punto de entrada principal."""
    _forzar_utf8()
    if '--cli' in sys.argv:
        args = [a for a in sys.argv if a != '--cli']
        if len(args) < 2:
            print("Uso: python main.py --cli <archivo.inv>")
            return 1
        sys.argv = args
        from inveniolang.cli import main as cli_main
        return cli_main()

    if len(sys.argv) < 2 or '--gui' in sys.argv:
        # GUI principal: PySide6 (Qt). Si no está disponible, respaldo a Tk.
        if '--gui-tk' in sys.argv:
            from inveniolang.gui_tk import main as gui_main
            gui_main()
            return 0
        try:
            from inveniolang.gui_qt import main as gui_main
        except Exception:
            from inveniolang.gui_tk import main as gui_main
        gui_main()
        return 0

    if '--version' in sys.argv:
        print("InvenioLang 10.0.0")
        return 0

    if '--help' in sys.argv:
        print("InvenioLang 10.0 - Compilador Educativo")
        print("Universidad Invenio - TIIT2002.2 Lenguajes Formales II")
        print("")
        print("Uso:")
        print("  python main.py                           Modo GUI (por defecto, PySide6)")
        print("  python main.py <archivo.inv> [entrada...]  Modo CLI")
        print("  python main.py --cli <archivo.inv>         Modo CLI (explícito)")
        print("  python main.py --check <archivo.inv>       Revisar sin ejecutar")
        print("  python main.py --step <archivo.inv>        Mostrar traza de ejecución")
        print("  python main.py --tokens <archivo>          Mostrar tokens")
        print("  python main.py --ast <archivo>             Mostrar AST")
        print("  python main.py --ir <archivo>              Código intermedio (TAC)")
        print("  python main.py --target <archivo>          Código objetivo")
        print("  python main.py --help                      Esta ayuda")
        print("  python main.py --version                   Versión")
        print("")
        print("Opciones:")
        print("  --gui        Iniciar interfaz gráfica (PySide6)")
        print("  --gui-tk     Iniciar la interfaz gráfica alternativa (Tkinter)")
        print("  --cli        Ejecutar en modo consola (requiere archivo)")
        print("  --check      Revisar el código sin ejecutarlo (estático)")
        print("  --step       Mostrar la traza (línea, variables, pila) por instrucción")
        print("  --tokens     Mostrar el análisis léxico")
        print("  --ast        Mostrar el AST")
        print("  --ir         Mostrar código intermedio (ver --help CLI para más flags)")
        print("  --target     Mostrar código objetivo")
        print("  --json       Salida de errores en JSON (CLI)")
        print("  --version    Mostrar versión")
        print("  --help       Mostrar esta ayuda")
        return 0

    from inveniolang.cli import main as cli_main
    return cli_main()


if __name__ == '__main__':
    sys.exit(main())
