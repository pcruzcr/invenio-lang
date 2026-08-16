import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import re

from .lexer import Lexer
from .parser import Parser
from .errors import ErrorManager
from .semantic import SemanticAnalyzer
from .type_checker import TypeChecker
from .interpreter import Interpreter


from .docstrings import (_DOC_GUIA, _DOC_REFERENCIA, _DOC_FUNCIONES, 
                          _DOC_ERRORES, _DOC_ATAJOS, EJEMPLOS)


class InvenioLangGUI:
    FUENTE = ('Consolas', 11)
    FUENTE_PEQ = ('Consolas', 9)

    COLORES = {
        'fondo': '#1e1e1e',
        'gutter': '#252526',
        'gutter_linea': '#858585',
        'gutter_borde': '#3c3c3c',
        'texto': '#d4d4d4',
        'cursor': 'white',
        'keyword': '#569cd6',
        'string': '#ce9178',
        'comment': '#6a9955',
        'number': '#b5cea8',
        'builtin': '#dcdcaa',
        'type': '#4ec9b0',
        'operator': '#d4d4d4',
        # Subrayado/marcado de problemas (estilo IDE)
        'error_sub': '#f48771',
        'error_fondo': '#3a2020',
        'warn_sub': '#dcdcaa',
        'warn_fondo': '#3a3a20',
        'flash': '#264f78',
    }

    KEYWORDS = {
        'if', 'si', 'else', 'sino', 'while', 'mientras', 'for', 'para',
        'return', 'break', 'romper', 'continue', 'continuar',
        'int', 'entero', 'float', 'real', 'string', 'texto', 'bool', 'logico',
        'void', 'vacio', 'const', 'constante', 'main',
        'true', 'verdadero', 'false', 'falso',
    }

    BUILTINS = {
        'imprimir', 'print', 'leer', 'read',
        'int_a_float', 'float_a_int', 'int_a_texto', 'float_a_texto',
        'texto_a_int', 'texto_a_float', 'bool_a_texto', 'texto_a_bool',
    }

    def __init__(self, root):
        self.root = root
        self.root.title("InvenioLang 1.0 - Compilador Educativo")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        self.archivo_actual = None
        self.modificado = False
        self._resaltando = False
        # Análisis en vivo (debounce) y navegación de errores
        self._job_en_vivo = None
        self._errores_actuales = []
        self._idx_error = 0

        self._crear_menu()
        self._crear_widgets()

        self.root.bind('<Control-o>', lambda e: self.abrir_archivo())
        self.root.bind('<Control-s>', lambda e: self.guardar_archivo())
        self.root.bind('<Control-r>', lambda e: self.ejecutar())
        self.root.bind('<Control-g>', lambda e: self._ir_a_linea())
        self.root.bind('<F8>', lambda e: self._siguiente_error(1))
        self.root.bind('<Shift-F8>', lambda e: self._siguiente_error(-1))
        self.root.bind('<F1>', lambda e: self._abrir_documentacion())
        self.texto_errores.bind('<ButtonRelease-1>', self._al_hacer_click_error)

    def _crear_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        menu_archivo = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=menu_archivo)
        menu_archivo.add_command(label="Nuevo (Ctrl+N)", command=self.nuevo_archivo)
        menu_archivo.add_command(label="Abrir (Ctrl+O)", command=self.abrir_archivo)
        menu_archivo.add_command(label="Guardar (Ctrl+S)", command=self.guardar_archivo)
        menu_archivo.add_command(label="Guardar como...", command=self.guardar_como)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self.root.quit)

        menu_ejec = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ejecutar", menu=menu_ejec)
        menu_ejec.add_command(label="Ejecutar (Ctrl+R)", command=self.ejecutar)
        menu_ejec.add_separator()
        menu_ejec.add_command(label="Mostrar Tokens", command=self.mostrar_tokens)
        menu_ejec.add_command(label="Mostrar AST", command=self.mostrar_ast)

        menu_ayuda = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=menu_ayuda)
        menu_ayuda.add_command(label="Documentación / Ayuda (F1)",
                               command=self._abrir_documentacion)
        menu_ayuda.add_command(label="Guía rápida",
                               command=lambda: self._mostrar_ayuda(
                                   "Guía rápida", _DOC_GUIA))
        menu_ayuda.add_command(label="Referencia del lenguaje",
                               command=lambda: self._mostrar_ayuda(
                                   "Referencia del lenguaje", _DOC_REFERENCIA))
        menu_ayuda.add_command(label="Funciones integradas",
                               command=lambda: self._mostrar_ayuda(
                                   "Funciones integradas", _DOC_FUNCIONES))
        menu_ayuda.add_command(label="Catálogo de errores",
                               command=lambda: self._mostrar_ayuda(
                                   "Catálogo de errores", _DOC_ERRORES))
        menu_ayuda.add_command(label="Atajos de teclado",
                               command=lambda: self._mostrar_ayuda(
                                   "Atajos de teclado", _DOC_ATAJOS))
        menu_ayuda.add_separator()
        menu_ejemplos = tk.Menu(menu_ayuda, tearoff=0)
        menu_ayuda.add_cascade(label="Ejemplos", menu=menu_ejemplos)
        for nombre in EJEMPLOS:
            menu_ejemplos.add_command(
                label=nombre,
                command=lambda n=nombre: self._cargar_ejemplo(n))
        menu_ayuda.add_separator()
        menu_ayuda.add_command(label="Acerca de", command=self.mostrar_acerca)

    # ============================================================
    # Editor con lineas y coloreado
    # ============================================================

    def _crear_widgets(self):
        self.panel_principal = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.panel_principal.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # === Panel superior: Editor ===
        frame_editor = ttk.LabelFrame(self.panel_principal, text="Editor de Código")
        self.panel_principal.add(frame_editor, weight=3)

        # Contenedor del editor con gutter
        self._crear_editor_con_gutter(frame_editor)

        # Barra de estado
        self.barra_estado = ttk.Label(
            frame_editor, text="Listo", anchor=tk.W, relief=tk.SUNKEN
        )
        self.barra_estado.pack(fill=tk.X)

        # === Panel inferior: Resultados ===
        frame_resultados = ttk.LabelFrame(self.panel_principal, text="Resultados")
        self.panel_principal.add(frame_resultados, weight=2)

        self.notebook = ttk.Notebook(frame_resultados)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        frame_salida = ttk.Frame(self.notebook)
        self.notebook.add(frame_salida, text="Salida")
        self.texto_salida = tk.Text(
            frame_salida, wrap=tk.WORD, font=self.FUENTE_PEQ,
            bg=self.COLORES['fondo'], fg='#4ec9b0', state=tk.DISABLED,
            relief=tk.FLAT, borderwidth=0, padx=5, pady=5,
        )
        self.texto_salida.pack(fill=tk.BOTH, expand=True)
        scroll_salida = ttk.Scrollbar(frame_salida, orient=tk.VERTICAL,
                                      command=self.texto_salida.yview)
        self.texto_salida.config(yscrollcommand=scroll_salida.set)
        scroll_salida.pack(side=tk.RIGHT, fill=tk.Y)

        frame_errores = ttk.Frame(self.notebook)
        self.notebook.add(frame_errores, text="Errores")
        self.texto_errores = tk.Text(
            frame_errores, wrap=tk.WORD, font=self.FUENTE_PEQ,
            bg=self.COLORES['fondo'], fg='#f44747', state=tk.DISABLED,
            relief=tk.FLAT, borderwidth=0, padx=5, pady=5,
        )
        self.texto_errores.pack(fill=tk.BOTH, expand=True)
        scroll_err = ttk.Scrollbar(frame_errores, orient=tk.VERTICAL,
                                   command=self.texto_errores.yview)
        self.texto_errores.config(yscrollcommand=scroll_err.set)
        scroll_err.pack(side=tk.RIGHT, fill=tk.Y)

        frame_warn = ttk.Frame(self.notebook)
        self.notebook.add(frame_warn, text="Advertencias")
        self.texto_warn = tk.Text(
            frame_warn, wrap=tk.WORD, font=self.FUENTE_PEQ,
            bg=self.COLORES['fondo'], fg='#dcdcaa', state=tk.DISABLED,
            relief=tk.FLAT, borderwidth=0, padx=5, pady=5,
        )
        self.texto_warn.pack(fill=tk.BOTH, expand=True)
        scroll_warn = ttk.Scrollbar(frame_warn, orient=tk.VERTICAL,
                                    command=self.texto_warn.yview)
        self.texto_warn.config(yscrollcommand=scroll_warn.set)
        scroll_warn.pack(side=tk.RIGHT, fill=tk.Y)

        frame_input = ttk.LabelFrame(frame_resultados, text="Entrada (simulada)")
        self.entry_input = ttk.Entry(frame_input, font=self.FUENTE_PEQ)
        self.entry_input.pack(fill=tk.X, padx=5, pady=2)

        frame_botones = ttk.Frame(frame_resultados)
        ttk.Button(frame_botones, text="Ejecutar",
                   command=self.ejecutar).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame_botones, text="Limpiar",
                   command=self.limpiar_resultados).pack(side=tk.LEFT, padx=2)
        frame_botones.pack(fill=tk.X, padx=5, pady=2)

    def _crear_editor_con_gutter(self, parent):
        """Crea el editor con gutter de numeros de linea."""
        marco = tk.Frame(parent, bg=self.COLORES['gutter_borde'])
        marco.pack(fill=tk.BOTH, expand=True)

        # Gutter (numeros de linea)
        self.gutter = tk.Text(
            marco, width=5, padx=6, pady=6,
            font=self.FUENTE,
            bg=self.COLORES['gutter'],
            fg=self.COLORES['gutter_linea'],
            relief=tk.FLAT, state=tk.DISABLED,
            takefocus=0, highlightthickness=0,
            cursor='arrow',
        )
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)

        # Scrollbar vertical
        scroll_v = ttk.Scrollbar(marco, orient=tk.VERTICAL)
        scroll_v.pack(side=tk.RIGHT, fill=tk.Y)

        # Editor
        self.editor = tk.Text(
            marco,
            wrap=tk.NONE,
            font=self.FUENTE,
            bg=self.COLORES['fondo'],
            fg=self.COLORES['texto'],
            insertbackground=self.COLORES['cursor'],
            relief=tk.FLAT,
            borderwidth=0,
            padx=6,
            pady=6,
            undo=True,
            yscrollcommand=lambda *a: (
                scroll_v.set(*a),
                self._sincronizar_gutter(),
            ),
            tabs=('4c',),
        )
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_v.config(command=self._scroll_ambos)

        self._configurar_tags()

        self.editor.bind('<KeyRelease>', self._on_keyrelease)
        self.editor.bind('<<Modified>>', self._on_modified)
        self.editor.bind('<MouseWheel>', self._on_mousewheel)
        self.editor.bind('<Button-4>', self._on_mousewheel)
        self.editor.bind('<Button-5>', self._on_mousewheel)
        self.editor.bind('<Control-v>', lambda e: self.root.after(10, self._on_edit))
        self.editor.bind('<Control-x>', lambda e: self.root.after(10, self._on_edit))
        self.editor.bind('<Control-z>', lambda e: self.root.after(10, self._on_edit))
        self.editor.bind('<Control-y>', lambda e: self.root.after(10, self._on_edit))
        self.editor.bind('<BackSpace>', lambda e: self.root.after(10, self._on_edit))
        self.editor.bind('<Delete>', lambda e: self.root.after(10, self._on_edit))
        self.editor.bind('<Return>', lambda e: self.root.after(10, self._on_edit))
        self.editor.bind('<Tab>', lambda e: self._insertar_tabulacion(e))

    def _configurar_tags(self):
        self.editor.tag_config('keyword', foreground=self.COLORES['keyword'])
        self.editor.tag_config('string', foreground=self.COLORES['string'])
        self.editor.tag_config('comment', foreground=self.COLORES['comment'])
        self.editor.tag_config('number', foreground=self.COLORES['number'])
        self.editor.tag_config('builtin', foreground=self.COLORES['builtin'])
        self.editor.tag_config('type', foreground=self.COLORES['type'])
        # Marcado estilo IDE: subrayado + velo rojizo/ambarino para problemas
        self.editor.tag_config('error_sub', foreground=self.COLORES['error_sub'],
                               underline=True)
        self.editor.tag_config('error_fondo', background=self.COLORES['error_fondo'])
        self.editor.tag_config('warn_sub', foreground=self.COLORES['warn_sub'],
                               underline=True)
        self.editor.tag_config('warn_fondo', background=self.COLORES['warn_fondo'])
        self.editor.tag_config('flash', background=self.COLORES['flash'])

    def _scroll_ambos(self, *args):
        self.editor.yview(*args)
        self.gutter.yview(*args)

    def _sincronizar_gutter(self):
        try:
            self.gutter.yview_moveto(self.editor.yview()[0])
        except Exception:
            pass

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.editor.yview_scroll(-3, 'units')
        elif event.num == 5 or event.delta < 0:
            self.editor.yview_scroll(3, 'units')
        self._sincronizar_gutter()

    def _insertar_tabulacion(self, event):
        self.editor.insert(tk.INSERT, '    ')
        return 'break'

    def _on_keyrelease(self, event):
        if event.keysym in ('Control_L', 'Control_R', 'Shift_L', 'Shift_R', 'Alt_L', 'Alt_R'):
            return
        self.root.after_idle(self._on_edit)

    def _on_modified(self, event=None):
        if self.editor.edit_modified():
            if not self.modificado:
                self.modificado = True
                titulo = self.root.title()
                if not titulo.startswith('*'):
                    self.root.title('* ' + titulo)
            self.editor.edit_modified(False)

    def _on_edit(self):
        self._actualizar_gutter()
        self._resaltar_sintaxis()
        # Análisis en vivo diferido (debounce) para marcar errores/advertencias
        if self._job_en_vivo is not None:
            self.root.after_cancel(self._job_en_vivo)
        self._job_en_vivo = self.root.after(600, self._analizar_en_vivo)

    def _actualizar_gutter(self):
        """Redibuja los numeros de linea en el gutter."""
        n_lineas = int(self.editor.index('end-1c').split('.')[0])
        contenido = '\n'.join(str(i) for i in range(1, n_lineas + 1))
        self.gutter.config(state=tk.NORMAL)
        self.gutter.delete('1.0', tk.END)
        self.gutter.insert('1.0', contenido)
        # Alinear a la derecha usando tabs
        self.gutter.tag_add('gutter_line', '1.0', 'end-1c')
        self.gutter.tag_config('gutter_line', justify=tk.RIGHT)
        self.gutter.config(state=tk.DISABLED)
        self._sincronizar_gutter()

    def _resaltar_sintaxis(self):
        """Aplica coloreado sintactico usando el lexer."""
        if self._resaltando:
            return
        self._resaltando = True
        try:
            codigo = self.editor.get('1.0', 'end-1c')
            if not codigo.strip():
                return

            # Limpiar tags
            for tag in ('keyword', 'string', 'comment', 'number', 'builtin', 'type'):
                self.editor.tag_remove(tag, '1.0', tk.END)

            # Tokenizar con el lexer
            try:
                em_temp = ErrorManager()
                lexer = Lexer(em_temp)
                tokens = lexer.tokenizar(codigo, '<gui>')
            except Exception:
                self._resaltando = False
                return

            # Mapa de tipos de token -> tag
            mapa_keyword = {
                'KW_IF', 'KW_ELSE', 'KW_WHILE', 'KW_FOR', 'KW_RETURN',
                'KW_BREAK', 'KW_CONTINUE', 'KW_TRUE', 'KW_FALSE',
                'KW_CONST', 'KW_MAIN',
            }
            mapa_type = {'KW_INT', 'KW_FLOAT', 'KW_STRING', 'KW_BOOL', 'KW_VOID'}
            mapa_builtin = {'KW_PRINT', 'KW_READ'}

            for tok_tipo, tok_val, tok_lin, tok_col in tokens:
                inicio = f'{tok_lin}.{tok_col - 1}'
                if tok_tipo in ('TEXTO_LIT',):
                    # Hallar longitud real en el fuente (incluyendo comillas, escapes)
                    linea = codigo.split('\n')[tok_lin - 1]
                    quote = linea[tok_col - 1]
                    i = tok_col
                    while i < len(linea):
                        if linea[i] == '\\':
                            i += 2
                        elif linea[i] == quote:
                            i += 1
                            break
                        else:
                            i += 1
                    fin = f'{tok_lin}.{i}'
                else:
                    fin = f'{tok_lin}.{tok_col - 1 + len(str(tok_val))}'

                if tok_tipo in ('TEXTO_LIT',):
                    self.editor.tag_add('number', inicio, fin)
                elif tok_tipo in mapa_keyword:
                    self.editor.tag_add('keyword', inicio, fin)
                elif tok_tipo in mapa_type:
                    self.editor.tag_add('type', inicio, fin)
                elif tok_tipo in mapa_builtin:
                    self.editor.tag_add('builtin', inicio, fin)

            # Resaltar comentarios con regex (el lexer los descarta)
            for patron, tag_nombre in [
                (r'//[^\n]*', 'comment'),
                (r'/\*[\s\S]*?\*/', 'comment'),
            ]:
                for m in re.finditer(patron, codigo):
                    inicio_char = m.start()
                    # Convertir posicion char a posicion 'linea.columna'
                    antes = codigo[:inicio_char]
                    lin = antes.count('\n') + 1
                    col = inicio_char - antes.rfind('\n') if '\n' in antes else inicio_char
                    self.editor.tag_add(tag_nombre,
                                        f'{lin}.{col}',
                                        f'{lin}.{col + len(m.group())}')

        except Exception:
            pass
        finally:
            self._resaltando = False

    # ============================================================
    # Operaciones de archivo
    # ============================================================

    def nuevo_archivo(self):
        if self.modificado:
            if not messagebox.askyesno("Confirmar", "Descarta los cambios actuales?"):
                return
        self.editor.delete('1.0', tk.END)
        self.archivo_actual = None
        self.modificado = False
        self.root.title("InvenioLang 1.0 - [Sin título]")
        self.barra_estado.config(text="Nuevo archivo")
        self._on_edit()

    def abrir_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Abrir archivo InvenioLang",
            filetypes=[("InvenioLang", "*.inv"), ("Todos", "*.*")]
        )
        if not ruta:
            return
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                codigo = f.read()
        except UnicodeDecodeError as e:
            # §2.1: un archivo que no sea UTF-8 valido se rechaza con el codigo
            # del catalogo, el mismo que daria la CLI.
            messagebox.showerror(
                "Codificacion invalida",
                f"[IL-LEX-001] {os.path.basename(ruta)}\n\n"
                f"El archivo no esta codificado en UTF-8 valido "
                f"(byte invalido en la posicion {e.start}).\n\n"
                f"InvenioLang exige archivos fuente en UTF-8.")
            return
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}")
            return
        self.editor.delete('1.0', tk.END)
        self.editor.insert('1.0', codigo)
        self.editor.edit_modified(False)
        self.archivo_actual = ruta
        self.modificado = False
        self.root.title(f"InvenioLang 1.0 - {os.path.basename(ruta)}")
        self.barra_estado.config(text=f"Abierto: {ruta}")
        self._on_edit()

    def guardar_archivo(self):
        if self.archivo_actual:
            try:
                with open(self.archivo_actual, 'w', encoding='utf-8') as f:
                    f.write(self.editor.get('1.0', tk.END))
                self.modificado = False
                self.editor.edit_modified(False)
                self.root.title(self.root.title().lstrip('* '))
                self.barra_estado.config(text=f"Guardado: {self.archivo_actual}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
        else:
            self.guardar_como()

    def guardar_como(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar archivo InvenioLang",
            defaultextension=".inv",
            filetypes=[("InvenioLang", "*.inv"), ("Todos", "*.*")]
        )
        if not ruta:
            return
        try:
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(self.editor.get('1.0', tk.END))
            self.archivo_actual = ruta
            self.modificado = False
            self.editor.edit_modified(False)
            self.root.title(f"InvenioLang 1.0 - {os.path.basename(ruta)}")
            self.barra_estado.config(text=f"Guardado: {ruta}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    # ============================================================
    # Ejecucion
    # ============================================================

    def ejecutar(self):
        codigo = self.editor.get('1.0', tk.END).strip()
        if not codigo:
            messagebox.showwarning("Advertencia", "El editor está vacío")
            return

        entrada_str = self.entry_input.get().strip()
        entrada = entrada_str.split() if entrada_str else None

        nombre_archivo = self.archivo_actual or "<sin_titulo>"
        self.barra_estado.config(text="Compilando...")
        self.root.update()

        error_manager = ErrorManager()

        lexer = Lexer(error_manager)
        tokens = lexer.tokenizar(codigo, nombre_archivo)
        if error_manager.hay_errores():
            self._mostrar_errores(error_manager)
            self.notebook.select(1)
            self.barra_estado.config(text="Error léxico")
            return

        parser = Parser(lexer, error_manager)
        ast, error_manager = parser.analizar(codigo, nombre_archivo)
        if error_manager.hay_errores():
            self._mostrar_errores(error_manager)
            self.notebook.select(1)
            self.barra_estado.config(text="Error sintáctico")
            return

        semantico = SemanticAnalyzer(error_manager)
        tabla = semantico.analizar(ast)
        if error_manager.hay_errores():
            self._mostrar_errores(error_manager)
            if error_manager.warnings:
                self._mostrar_advertencias(error_manager)
            self.notebook.select(1)
            self.barra_estado.config(text="Error semántico")
            return

        if error_manager.warnings:
            self._mostrar_advertencias(error_manager)

        type_checker = TypeChecker(error_manager, tabla)
        type_checker.verificar(ast)
        if error_manager.hay_errores():
            self._mostrar_errores(error_manager)
            self.notebook.select(1)
            self.barra_estado.config(text="Error de tipos")
            return

        interprete = Interpreter(error_manager, tabla)
        try:
            salida = interprete.interpretar(ast, entrada)
        except Exception as e:
            self._agregar_texto(self.texto_errores, f"Error inesperado: {e}\n")
            self.notebook.select(1)
            self.barra_estado.config(text="Error de ejecución")
            return

        if error_manager.hay_errores():
            self._mostrar_errores(error_manager)
            self.notebook.select(1)
            self.barra_estado.config(text="Error de ejecución")
            return

        self.texto_salida.config(state=tk.NORMAL)
        self.texto_salida.delete('1.0', tk.END)
        self.texto_salida.insert('1.0', ''.join(salida))
        self.texto_salida.config(state=tk.DISABLED)
        self.notebook.select(0)
        self.barra_estado.config(text="Ejecución exitosa")

    # ============================================================
    # Mostrar Tokens / AST
    # ============================================================

    def mostrar_tokens(self):
        codigo = self.editor.get('1.0', tk.END)
        if not codigo.strip():
            return
        nombre_archivo = self.archivo_actual or "<sin_titulo>"
        error_manager = ErrorManager()
        lexer = Lexer(error_manager)
        tokens = lexer.tokenizar(codigo, nombre_archivo)
        self.texto_salida.config(state=tk.NORMAL)
        self.texto_salida.delete('1.0', tk.END)
        for tok in tokens:
            self.texto_salida.insert(tk.END,
                f"{tok[0]:20s} {repr(tok[1]):30s} L{tok[2]}:C{tok[3]}\n")
        if error_manager.hay_errores():
            self.texto_salida.insert(tk.END, "\n--- ERRORES LÉXICOS ---\n")
            for e in error_manager.obtener_reportes():
                self.texto_salida.insert(tk.END, f"{e}\n")
        self.texto_salida.config(state=tk.DISABLED)
        self.notebook.select(0)

    def mostrar_ast(self):
        codigo = self.editor.get('1.0', tk.END)
        if not codigo.strip():
            return
        nombre_archivo = self.archivo_actual or "<sin_titulo>"
        error_manager = ErrorManager()
        lexer = Lexer(error_manager)
        parser = Parser(lexer, error_manager)
        ast, _ = parser.analizar(codigo, nombre_archivo)
        self.texto_salida.config(state=tk.NORMAL)
        self.texto_salida.delete('1.0', tk.END)
        if ast:
            self.texto_salida.insert(tk.END, self._ast_a_texto(ast, 0))
        else:
            self.texto_salida.insert(tk.END, "No se pudo generar el AST\n")
        if error_manager.hay_errores():
            self.texto_salida.insert(tk.END, "\n--- ERRORES SINTÁCTICOS ---\n")
            for e in error_manager.obtener_reportes():
                self.texto_salida.insert(tk.END, f"{e}\n")
        self.texto_salida.config(state=tk.DISABLED)
        self.notebook.select(0)

    def _ast_a_texto(self, nodo, nivel):
        if nodo is None:
            return "  " * nivel + "None\n"
        texto = "  " * nivel + nodo.__class__.__name__
        if hasattr(nodo, 'nombre') and nodo.nombre:
            texto += f"({nodo.nombre})"
        if hasattr(nodo, 'tipo') and nodo.tipo:
            if hasattr(nodo, 'tipo_retorno'):
                texto += f" : {nodo.tipo_retorno}"
            elif isinstance(getattr(nodo, 'tipo', None), str):
                texto += f" : {nodo.tipo}"
        texto += "\n"
        if hasattr(nodo, 'elementos') and nodo.elementos:
            for e in nodo.elementos:
                texto += self._ast_a_texto(e, nivel + 1)
        if hasattr(nodo, 'bloque') and nodo.bloque:
            texto += self._ast_a_texto(nodo.bloque, nivel + 1)
        if hasattr(nodo, 'declaraciones_globales'):
            for d in nodo.declaraciones_globales:
                texto += self._ast_a_texto(d, nivel + 1)
        if hasattr(nodo, 'declaraciones_posteriores'):
            for d in nodo.declaraciones_posteriores:
                texto += self._ast_a_texto(d, nivel + 1)
        if hasattr(nodo, 'subrutinas'):
            for s in nodo.subrutinas:
                texto += self._ast_a_texto(s, nivel + 1)
        if hasattr(nodo, 'main') and nodo.main:
            texto += self._ast_a_texto(nodo.main, nivel + 1)
        return texto

    def _mostrar_errores(self, error_manager):
        self.texto_errores.config(state=tk.NORMAL)
        self.texto_errores.delete('1.0', tk.END)
        self._errores_actuales = list(error_manager.errores)
        for reporte in error_manager.obtener_reportes():
            self.texto_errores.insert(tk.END, reporte + "\n")
        self.texto_errores.config(state=tk.DISABLED)

    def _mostrar_advertencias(self, error_manager):
        self.texto_warn.config(state=tk.NORMAL)
        self.texto_warn.delete('1.0', tk.END)
        for warn in error_manager.obtener_advertencias():
            self.texto_warn.insert(tk.END, warn + "\n")
        self.texto_warn.config(state=tk.DISABLED)

    def _agregar_texto(self, widget, texto):
        widget.config(state=tk.NORMAL)
        widget.insert(tk.END, texto)
        widget.config(state=tk.DISABLED)

    def limpiar_resultados(self):
        for w in (self.texto_salida, self.texto_errores, self.texto_warn):
            w.config(state=tk.NORMAL)
            w.delete('1.0', tk.END)
            w.config(state=tk.DISABLED)
        self._errores_actuales = []
        self.barra_estado.config(text="Resultados limpiados")

    # ============================================================
    # Análisis en vivo y marcado de problemas (estilo IDE)
    # ============================================================

    def _limpiar_marcadores(self):
        """Elimina las marcas de error/advertencia del editor."""
        for tag in ('error_sub', 'error_fondo', 'warn_sub', 'warn_fondo'):
            self.editor.tag_remove(tag, '1.0', tk.END)

    def _longitud_token_en_linea(self, linea, col):
        """Longitud (en caracteres) del token que empieza en (linea, col)."""
        try:
            texto = self.editor.get(f'{linea}.0', f'{linea}.end')
        except tk.TclError:
            return 1
        if col < 0 or col >= len(texto):
            return 1
        i = col
        while i < len(texto) and not texto[i].isspace() \
                and texto[i] not in ';{}()[],+*-/%=<>&|!':
            i += 1
        return max(i - col, 1)

    def _marcar_problema(self, err, es_error):
        """Subraya + resalta un error (rojo) o advertencia (ámbar) en el editor."""
        linea = err.linea
        col = max(err.columna - 1, 0)
        fin = col + self._longitud_token_en_linea(linea, col)
        tag_sub = 'error_sub' if es_error else 'warn_sub'
        tag_fond = 'error_fondo' if es_error else 'warn_fondo'
        try:
            ini = f'{linea}.{col}'
            term = f'{linea}.{fin}'
            self.editor.tag_add(tag_sub, ini, term)
            self.editor.tag_add(tag_fond, ini, term)
        except tk.TclError:
            pass

    def _analizar_en_vivo(self):
        """Ejecuta el pipeline (sin interpretar) y marca errores/advertencias."""
        self._job_en_vivo = None
        codigo = self.editor.get('1.0', 'end-1c')
        self._limpiar_marcadores()
        if not codigo.strip():
            self.barra_estado.config(text="Listo")
            return
        em = ErrorManager()
        try:
            lexer = Lexer(em)
            lexer.tokenizar(codigo, '<en_vivo>')
            if not em.hay_errores():
                parser = Parser(lexer, em)
                ast, em = parser.analizar(codigo, '<en_vivo>')
                if ast is not None and not em.hay_errores():
                    sem = SemanticAnalyzer(em)
                    tabla = sem.analizar(ast)
                    tc = TypeChecker(em, tabla)
                    tc.verificar(ast)
        except Exception:
            pass
        self._errores_actuales = list(em.errores)
        for err in em.errores:
            self._marcar_problema(err, es_error=True)
        for warn in em.warnings:
            self._marcar_problema(warn, es_error=False)
        n_err = len(em.errores)
        n_warn = len(em.warnings)
        if n_err or n_warn:
            self.barra_estado.config(text=f"Errores: {n_err}  Advertencias: {n_warn}")
        else:
            self.barra_estado.config(text="Sin problemas")

    def _saltar_a_linea(self, linea, col=1):
        try:
            self.editor.mark_set(tk.INSERT, f'{linea}.{max(col - 1, 0)}')
            self.editor.see(tk.INSERT)
            self.editor.focus_set()
            self.editor.tag_add('flash', f'{linea}.0', f'{linea}.end')
            self.root.after(700, lambda l=linea: self.editor.tag_remove(
                'flash', f'{l}.0', f'{l}.end'))
        except tk.TclError:
            pass

    def _al_hacer_click_error(self, event):
        """Al hacer clic en un error, salta a su línea en el editor."""
        try:
            idx = event.widget.index(f'@{event.x},{event.y}')
            lin = int(str(idx).split('.')[0])
        except (tk.TclError, ValueError):
            return
        if 1 <= lin <= len(self._errores_actuales):
            err = self._errores_actuales[lin - 1]
            self._saltar_a_linea(err.linea, err.columna)

    def _siguiente_error(self, delta):
        """Salta al error siguiente (F8) o anterior (Shift+F8)."""
        if not self._errores_actuales:
            self.barra_estado.config(text="No hay errores para navegar")
            return
        n = len(self._errores_actuales)
        self._idx_error = (self._idx_error + delta) % n
        err = self._errores_actuales[self._idx_error]
        self._saltar_a_linea(err.linea, err.columna)

    def _ir_a_linea(self):
        num = simpledialog.askinteger("Ir a línea", "Número de línea:",
                                      parent=self.root, minvalue=1)
        if num:
            self._saltar_a_linea(num)

    # ============================================================
    # Ayuda y documentación
    # ============================================================

    def _crear_texto_ayuda(self, parent):
        """Crea un widget Text de solo lectura para documentación."""
        txt = tk.Text(parent, wrap=tk.WORD, font=self.FUENTE_PEQ,
                      bg=self.COLORES['fondo'], fg=self.COLORES['texto'],
                      relief=tk.FLAT, padx=8, pady=8, cursor='arrow')
        scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=txt.yview)
        txt.config(yscrollcommand=scroll.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        return txt

    def _mostrar_ayuda(self, titulo, contenido):
        """Abre una ventana con documentación de un solo tema."""
        win = tk.Toplevel(self.root)
        win.title(f"InvenioLang - {titulo}")
        win.geometry("680x520")
        win.transient(self.root)
        ttk.Label(win, text=titulo, font=("Consolas", 12, "bold")).pack(pady=6)
        txt = self._crear_texto_ayuda(win)
        txt.insert(tk.END, contenido)
        txt.config(state=tk.DISABLED)

    def _abrir_documentacion(self):
        """Ventana de documentación con pestañas (F1)."""
        win = tk.Toplevel(self.root)
        win.title("InvenioLang - Documentación y Ayuda")
        win.geometry("780x560")
        win.transient(self.root)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        secciones = [
            ("Guía rápida", _DOC_GUIA),
            ("Referencia", _DOC_REFERENCIA),
            ("Funciones integradas", _DOC_FUNCIONES),
            ("Catálogo de errores", _DOC_ERRORES),
            ("Atajos", _DOC_ATAJOS),
        ]
        for titulo, contenido in secciones:
            frame = ttk.Frame(nb)
            nb.add(frame, text=titulo)
            txt = self._crear_texto_ayuda(frame)
            txt.insert(tk.END, contenido)
            txt.config(state=tk.DISABLED)

    def _cargar_ejemplo(self, nombre):
        """Carga un programa de ejemplo de la carpeta pruebas/ en el editor."""
        base = os.path.dirname(os.path.abspath(__file__))
        ruta = os.path.join(base, '..', 'pruebas', f'{nombre}.inv')
        if not os.path.exists(ruta):
            messagebox.showerror("Ejemplo", f"No se encontró el ejemplo: {nombre}")
            return
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                codigo = f.read()
        except Exception as e:
            messagebox.showerror("Ejemplo", f"No se pudo leer: {e}")
            return
        if self.modificado and self.editor.get('1.0', 'end-1c').strip():
            if not messagebox.askyesno("Confirmar",
                                       "Se reemplazará el contenido actual. Continuar?"):
                return
        self.editor.delete('1.0', tk.END)
        self.editor.insert('1.0', codigo)
        self.editor.edit_modified(False)
        self.archivo_actual = os.path.abspath(ruta)
        self.modificado = False
        self.root.title(f"InvenioLang 1.0 - {nombre}.inv")
        self.barra_estado.config(text=f"Ejemplo cargado: {nombre}.inv")
        self._on_edit()

    def mostrar_acerca(self):
        messagebox.showinfo(
            "Acerca de InvenioLang 1.0",
            "InvenioLang 1.0 - Compilador Educativo\n"
            "Curso: TIIT2002.2 Lenguajes Formales II\n"
            "Universidad Invenio\n"
            "Profesor: Donny Núñez del Rosario\n\n"
            "Implementado con Python y PLY"
        )


def main():
    root = tk.Tk()
    app = InvenioLangGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
