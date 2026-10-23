"""Panel Qt del diagrama de flujo: ver, editar y volver a código (INV-3010).

Sustituye a los dos docks anteriores de ``gui_qt.py`` («Diagrama de flujo»,
de solo lectura y solo con ``flowchart.py``, y «Constructor de diagramas»,
que editaba únicamente ``main`` mutando el AST): ahora un solo panel trabaja
sobre el modelo de ``inveniolang.flujo``:

* genera el diagrama del código del editor y deja elegir la subrutina, el
  método o el constructor;
* lo dibuja con el mismo SVG accesible que la CLI (tema claro/oscuro) y
  resalta la caja de la línea donde se detiene el depurador;
* edita el árbol con las operaciones estructuradas (insertar, eliminar,
  mover, envolver en si / en ciclo, ramas), con validación bilingüe y
  «Deshacer»;
* regenera el programa completo en español o en inglés.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import flujo, i18n
from ..flujo.modelo import recorrer
from ..flujo.render_svg import svg_esquema

__all__ = ["PanelFlujo"]

_ROL = Qt.ItemDataRole.UserRole
_TIPOS_PALETA = (
    "proceso",
    "declaracion",
    "leer",
    "escribir",
    "llamada",
    "si",
    "segun",
    "mientras",
    "hacer_mientras",
    "para",
    "para_cada",
    "intentar",
    "retornar",
    "romper",
    "continuar",
)


def _t(clave: str, **args: object) -> str:
    return i18n.t(clave, **args)


class _VistaDiagrama(QGraphicsView):
    """Vista con zoom en la rueda y selección de caja con un clic."""

    caja_pulsada = Signal(str)

    def __init__(self, escena: QGraphicsScene, panel: PanelFlujo):
        super().__init__(escena)
        self._panel = panel
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def wheelEvent(self, event):  # noqa: N802 - API de Qt
        """Zoom con la rueda del ratón."""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mouseDoubleClickEvent(self, event):  # noqa: N802 - API de Qt
        """Doble clic sobre una caja: la selecciona en el árbol."""
        punto = self.mapToScene(event.position().toPoint())
        origen = self._panel.origen_en(punto.x(), punto.y())
        if origen is not None:
            self.caja_pulsada.emit(origen)
        super().mouseDoubleClickEvent(event)


class PanelFlujo(QWidget):
    """Panel del diagrama de flujo (modelo ``inveniolang.flujo``)."""

    codigo_generado = Signal(str)
    # INV-4012: el panel «Bloques» es otra vista del mismo árbol: escucha los
    # cambios del diagrama y la caja elegida (mismos ids que sus bloques).
    modelo_cambiado = Signal(object)
    nodo_elegido = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.modelo: flujo.ModeloFlujo | None = None
        self._externo = False
        self._historial: list[flujo.ModeloFlujo] = []
        self._esquema: flujo.Esquema | None = None
        self._renderer: QSvgRenderer | None = None
        self._resaltado = None
        self._tema = "oscuro"
        self._problemas: list[flujo.Problema] = []
        self.proveedor_codigo = None  # callable -> (codigo, ruta) del editor activo

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        fila = QHBoxLayout()
        fila.addWidget(QLabel(_t("FLU.gui.subrutina")))
        self.combo = QComboBox()
        self.combo.setAccessibleName(_t("FLU.gui.subrutina"))
        self.combo.currentIndexChanged.connect(lambda _i: self._refrescar())
        fila.addWidget(self.combo, 1)
        fila.addWidget(QLabel(_t("FLU.gui.idioma")))
        self.combo_idioma = QComboBox()
        self.combo_idioma.addItems(list(i18n.IDIOMAS))
        self.combo_idioma.setAccessibleName(_t("FLU.gui.idioma"))
        self.combo_idioma.currentTextChanged.connect(self._cambiar_idioma)
        fila.addWidget(self.combo_idioma)
        lay.addLayout(fila)

        botones = QHBoxLayout()
        for clave, accion in (
            ("FLU.gui.desde_editor", self.generar_desde_editor),
            ("FLU.gui.nuevo", self.nuevo),
            ("FLU.gui.abrir", self.abrir_json),
            ("FLU.gui.exportar", self._menu_exportar),
            ("FLU.gui.deshacer", self.deshacer),
            ("FLU.gui.a_codigo", self.generar_codigo),
        ):
            b = QPushButton(_t(clave))
            b.clicked.connect(accion)
            botones.addWidget(b)
            if clave == "FLU.gui.exportar":
                self._boton_exportar = b
        lay.addLayout(botones)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.arbol = QTreeWidget()
        self.arbol.setHeaderHidden(True)
        self.arbol.setAccessibleName(_t("FLU.gui.arbol"))
        self.arbol.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.arbol.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.arbol.customContextMenuRequested.connect(self._menu_contextual)
        self.arbol.itemDoubleClicked.connect(lambda item, _c: self._editar_item(item))
        self.arbol.currentItemChanged.connect(self._al_elegir)
        split.addWidget(self.arbol)
        self.escena = QGraphicsScene()
        self.vista = _VistaDiagrama(self.escena, self)
        self.vista.setAccessibleName(_t("FLU.gui.lienzo"))
        self.vista.caja_pulsada.connect(self.seleccionar_nodo)
        split.addWidget(self.vista)
        split.setStretchFactor(1, 2)
        lay.addWidget(split, 1)

        self.lista_problemas = QListWidget()
        self.lista_problemas.setAccessibleName(_t("FLU.gui.problemas"))
        self.lista_problemas.setMaximumHeight(110)
        lay.addWidget(self.lista_problemas)

    # ------------------------------------------------------------ estado

    def establecer_tema(self, claro: bool) -> None:
        """Tema del dibujo (el SVG se repinta con la paleta pedida)."""
        self._tema = "claro" if claro else "oscuro"
        self._dibujar()

    def cargar_codigo(self, codigo: str, ruta: str | None = None) -> bool:
        """Construye el diagrama de ``codigo``; False (y los errores en la lista) si no compila."""
        idioma = self.combo_idioma.currentText()
        try:
            modelo = flujo.modelo_desde_codigo(
                codigo, idioma, ruta=ruta or "<editor>", ruta_fuente=ruta
            )
        except flujo.ErrorFlujo as e:
            self.lista_problemas.clear()
            self.lista_problemas.addItem(e.texto())
            self.lista_problemas.addItems(list(e.diagnosticos))
            return False
        self._historial.clear()
        self._fijar_modelo(modelo)
        return True

    def generar_desde_editor(self) -> None:
        """Diagrama del archivo del editor activo."""
        if self.proveedor_codigo is None:
            return
        datos = self.proveedor_codigo()
        if datos is not None:
            self.cargar_codigo(*datos)

    def nuevo(self) -> None:
        """Programa nuevo con un ``main`` vacío para construir desde cero."""
        if self.modelo is not None:
            self._historial.append(self.modelo)
        self._fijar_modelo(flujo.nuevo_modelo(self.combo_idioma.currentText()))

    def deshacer(self) -> None:
        """Vuelve al modelo anterior a la última operación."""
        if self._historial:
            self._fijar_modelo(self._historial.pop())

    def _fijar_modelo(self, modelo: flujo.ModeloFlujo, clave: str | None = None) -> None:
        self.modelo = modelo
        actual = clave or self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()
        for d in modelo.diagramas():
            self.combo.addItem(d.clave, d.clave)
        indice = self.combo.findData(actual)
        if indice < 0:
            indice = self.combo.findData("main")
        self.combo.setCurrentIndex(max(indice, 0))
        self.combo.blockSignals(False)
        self.combo_idioma.blockSignals(True)
        self.combo_idioma.setCurrentText(modelo.idioma)
        self.combo_idioma.blockSignals(False)
        self._problemas = flujo.validar(modelo)
        self._refrescar()
        if not self._externo:
            self.modelo_cambiado.emit(modelo)

    def mostrar_modelo(self, modelo: flujo.ModeloFlujo) -> None:
        """Muestra un modelo que viene de otra vista (bloques) sin reenviarlo."""
        if self.modelo is not None and flujo.a_json(self.modelo) == flujo.a_json(modelo):
            return
        self._externo = True
        try:
            if self.modelo is not None:
                self._historial.append(self.modelo)
            self._fijar_modelo(modelo)
        finally:
            self._externo = False

    def _al_elegir(self, item: QTreeWidgetItem | None, _previo=None) -> None:
        if item is not None and not self._externo:
            tipo, ident, _ = item.data(0, _ROL)
            if tipo == "nodo" and ident:
                self.nodo_elegido.emit(ident)

    def _aplicar(self, operacion) -> bool:
        """Ejecuta una operación de edición; muestra su error bilingüe si falla."""
        if self.modelo is None:
            return False
        try:
            nuevo = operacion(self.modelo)
        except flujo.ErrorFlujo as e:
            QMessageBox.warning(self, _t("FLU.gui.titulo"), e.texto())
            return False
        self._historial.append(self.modelo)
        self._fijar_modelo(nuevo)
        return True

    def _cambiar_idioma(self, idioma: str) -> None:
        if self.modelo is not None and idioma != self.modelo.idioma:
            self._historial.append(self.modelo)
            self._fijar_modelo(flujo.traducir_modelo(self.modelo, idioma))

    @property
    def clave(self) -> str | None:
        """Clave del diagrama elegido."""
        return self.combo.currentData()

    # ------------------------------------------------------------ dibujo y árbol

    def _refrescar(self) -> None:
        self._llenar_arbol()
        self._dibujar()
        self.lista_problemas.clear()
        for p in self._problemas:
            lugar = f"[{p.clave or '-'} · {p.nodo or '-'}] " if p.clave else ""
            self.lista_problemas.addItem(lugar + p.texto())

    def _dibujar(self) -> None:
        self.escena.clear()
        self._resaltado = None
        self._esquema = None
        if self.modelo is None or self.clave is None:
            return
        self._esquema = flujo.esquemas(self.modelo, self.clave)[0]
        svg = svg_esquema(self._esquema, self._tema)
        self._renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        item = QGraphicsSvgItem()
        item.setSharedRenderer(self._renderer)
        self.escena.addItem(item)
        self.escena.setSceneRect(0, 0, self._esquema.ancho, self._esquema.alto)
        self.vista.setAccessibleDescription(flujo.describir_esquema(self._esquema))

    def origen_en(self, x: float, y: float) -> str | None:
        """Id del nodo del modelo dibujado en (x, y), si lo hay."""
        if self._esquema is None:
            return None
        for n in self._esquema.nodos:
            if n.origen and n.x <= x <= n.x + n.w and n.y <= y <= n.y + n.h:
                return n.origen
        return None

    def resaltar(self, funcion: str | None, linea: int | None) -> None:
        """Resalta la caja de ``linea`` en el diagrama de ``funcion`` (depurador)."""
        self.quitar_resaltado()
        if self.modelo is None or linea is None:
            return
        claves = [d.clave for d in self.modelo.diagramas()]
        nombre = funcion or "main"
        candidata = next(
            (c for c in claves if c == nombre or c.split("#")[0] == nombre),
            next((d.clave for d in self.modelo.diagramas() if d.nombre == nombre), None),
        )
        if candidata is not None and candidata != self.clave:
            self.combo.setCurrentIndex(self.combo.findData(candidata))
        if self._esquema is None:
            return
        for n in self._esquema.nodos:
            if n.origen and n.linea == linea:
                pen = QPen(QColor("#e3b341"))
                pen.setWidth(3)
                self._resaltado = self.escena.addRect(n.x - 4, n.y - 4, n.w + 8, n.h + 8, pen)
                self._resaltado.setZValue(10)
                self.vista.centerOn(self._resaltado)
                return

    def quitar_resaltado(self) -> None:
        """Quita el resaltado del depurador."""
        if self._resaltado is not None:
            self.escena.removeItem(self._resaltado)
            self._resaltado = None

    def _texto_nodo(self, n: flujo.Nodo) -> str:
        nombre = _t(f"FLU.gui.tipo.{n.tipo}")
        partes = [getattr(n, a) for a in flujo.CAMPOS[n.tipo].values() if getattr(n, a)]
        if n.tipo == "si":
            partes = [n.ramas[0].etiqueta] if n.ramas else []
        return f"{nombre}: {' ; '.join(partes)}" if partes else nombre

    def _llenar_arbol(self) -> None:
        self.arbol.clear()
        if self.modelo is None or self.clave is None:
            return
        d = self.modelo.diagrama(self.clave)
        raiz = QTreeWidgetItem([d.firma])
        raiz.setData(0, _ROL, ("parte", None, "cuerpo"))
        self.arbol.addTopLevelItem(raiz)
        malos: dict[str, list[str]] = {}
        for p in self._problemas:
            if p.clave == self.clave and p.nodo:
                malos.setdefault(p.nodo, []).append(p.texto())
        self._llenar(raiz, d.cuerpo, malos)
        self.arbol.expandAll()

    def _llenar(self, padre: QTreeWidgetItem, nodos: list[flujo.Nodo], malos) -> None:
        for n in nodos:
            item = QTreeWidgetItem([self._texto_nodo(n)])
            item.setData(0, _ROL, ("nodo", n.id, None))
            if n.id in malos:
                item.setForeground(0, QColor("#ff5555"))
                item.setToolTip(0, "\n".join(malos[n.id]))
            padre.addChild(item)
            for parte, sec in n.secuencias():
                etiqueta = _t(f"FLU.gui.parte.{parte.split(':')[0]}")
                if ":" in parte:
                    rama = n.ramas[int(parte.split(":")[1])]
                    etiqueta = f"{etiqueta}: {rama.etiqueta}"
                hijo = QTreeWidgetItem([etiqueta])
                hijo.setData(0, _ROL, ("parte", n.id, parte))
                item.addChild(hijo)
                self._llenar(hijo, sec, malos)

    def seleccionar_nodo(self, nodo_id: str, emitir: bool = True) -> bool:
        """Selecciona en el árbol el ítem del nodo ``nodo_id`` (y su diagrama).

        ``emitir=False`` cuando la selección viene de otra vista (bloques),
        para no devolverle el eco.
        """
        if self.modelo is not None and self.clave is not None:
            for d in self.modelo.diagramas():
                if any(n.id == nodo_id for n in recorrer(d.cuerpo)):
                    if d.clave != self.clave:
                        self.combo.setCurrentIndex(self.combo.findData(d.clave))
                    break
        pila = [self.arbol.topLevelItem(i) for i in range(self.arbol.topLevelItemCount())]
        while pila:
            item = pila.pop()
            if item.data(0, _ROL)[1] == nodo_id and item.data(0, _ROL)[0] == "nodo":
                self._externo = not emitir
                try:
                    self.arbol.setCurrentItem(item)
                finally:
                    self._externo = False
                return True
            pila.extend(item.child(i) for i in range(item.childCount()))
        return False

    # ------------------------------------------------------------ edición

    def _ubicacion(self) -> flujo.Ubicacion:
        """Después del nodo seleccionado, o al inicio de la rama seleccionada."""
        item = self.arbol.currentItem()
        if item is None:
            return flujo.Ubicacion()
        tipo, ident, parte = item.data(0, _ROL)
        if tipo == "parte":
            return flujo.Ubicacion(ident, parte, 0)
        padre = item.parent()
        _, pid, pparte = padre.data(0, _ROL)
        return flujo.Ubicacion(pid, pparte, padre.indexOfChild(item) + 1)

    def _pedir(self, titulo: str, campos: list[tuple[str, str]]) -> dict[str, str] | None:
        """Formulario con un campo de texto por (nombre, valor inicial)."""
        if not campos:
            return {}
        d = QDialog(self)
        d.setWindowTitle(titulo)
        form = QFormLayout(d)
        edits = {}
        for nombre, valor in campos:
            e = QLineEdit(valor)
            e.setAccessibleName(_t(f"FLU.gui.campo.{nombre}"))
            form.addRow(_t(f"FLU.gui.campo.{nombre}"), e)
            edits[nombre] = e
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(d.accept)
        botones.rejected.connect(d.reject)
        form.addRow(botones)
        if d.exec() != QDialog.DialogCode.Accepted:
            return None
        return {k: e.text() for k, e in edits.items()}

    @staticmethod
    def _campos_de(tipo: str) -> list[str]:
        return ["condicion"] if tipo == "si" else list(flujo.CAMPOS[tipo])

    def insertar_tipo(self, tipo: str, valores: dict[str, str] | None = None) -> bool:
        """Inserta un nodo ``tipo`` en la posición seleccionada (pide sus textos)."""
        if self.modelo is None or self.clave is None:
            return False
        if valores is None:
            valores = self._pedir(
                _t(f"FLU.gui.tipo.{tipo}"), [(c, "") for c in self._campos_de(tipo)]
            )
            if valores is None:
                return False
        ubicacion = self._ubicacion()
        clave = self.clave
        return self._aplicar(
            lambda m: flujo.insertar(m, clave, ubicacion, flujo.nuevo_nodo(tipo, **valores))
        )

    def _seleccion(self) -> list[str]:
        return [
            it.data(0, _ROL)[1]
            for it in self.arbol.selectedItems()
            if it.data(0, _ROL)[0] == "nodo"
        ]

    def envolver(self, tipo: str, valores: dict[str, str] | None = None) -> bool:
        """Envuelve los nodos seleccionados en un ``si`` o en un ciclo ``tipo``."""
        ids = self._seleccion()
        if valores is None:
            valores = self._pedir(
                _t(f"FLU.gui.tipo.{tipo}"), [(c, "") for c in self._campos_de(tipo)]
            )
            if valores is None:
                return False
        clave = self.clave
        if tipo == "si":
            return self._aplicar(
                lambda m: flujo.envolver_en_si(m, clave, ids, valores.get("condicion", ""))
            )
        return self._aplicar(lambda m: flujo.envolver_en_ciclo(m, clave, ids, tipo, **valores))

    def _nodo(self, ident: str) -> flujo.Nodo:
        assert self.modelo is not None and self.clave is not None
        pila = list(self.modelo.diagrama(self.clave).cuerpo)
        while pila:
            n = pila.pop()
            if n.id == ident:
                return n
            for _, sec in n.secuencias():
                pila.extend(sec)
        raise KeyError(ident)

    def _editar_item(self, item: QTreeWidgetItem) -> None:
        tipo, ident, parte = item.data(0, _ROL)
        if ident is None:
            return
        n = self._nodo(ident)
        clave = self.clave
        if tipo == "parte":
            if ":" not in parte:
                return
            k = int(parte.split(":")[1])
            campo = "condicion" if n.tipo == "si" else "caso"
            valores = self._pedir(
                _t(f"FLU.gui.parte.{parte.split(':')[0]}"), [(campo, n.ramas[k].etiqueta)]
            )
            if valores is not None:
                self._aplicar(lambda m: flujo.editar(m, clave, ident, parte, valores[campo]))
            return
        actuales = [(c, getattr(n, a)) for c, a in flujo.CAMPOS[n.tipo].items()]
        valores = self._pedir(_t(f"FLU.gui.tipo.{n.tipo}"), actuales)
        if not valores:
            return

        def todas(m):
            for campo, valor in valores.items():
                m = flujo.editar(m, clave, ident, campo, valor)
            return m

        self._aplicar(todas)

    def _menu_contextual(self, punto) -> None:
        item = self.arbol.itemAt(punto)
        menu = QMenu(self)
        insertar = menu.addMenu(_t("FLU.gui.insertar"))
        for tipo in _TIPOS_PALETA:
            insertar.addAction(_t(f"FLU.gui.tipo.{tipo}"), lambda t=tipo: self.insertar_tipo(t))
        if item is not None:
            tipo, ident, parte = item.data(0, _ROL)
            clave = self.clave
            if tipo == "nodo":
                n = self._nodo(ident)
                menu.addAction(_t("FLU.gui.editar"), lambda: self._editar_item(item))
                menu.addAction(
                    _t("FLU.gui.eliminar"),
                    lambda: self._aplicar(lambda m: flujo.eliminar(m, clave, ident)),
                )
                menu.addAction(_t("FLU.gui.subir"), lambda: self.desplazar(ident, -1))
                menu.addAction(_t("FLU.gui.bajar"), lambda: self.desplazar(ident, 1))
                envolver = menu.addMenu(_t("FLU.gui.envolver"))
                for t in ("si", "mientras", "hacer_mientras", "para", "para_cada"):
                    envolver.addAction(_t(f"FLU.gui.tipo.{t}"), lambda t=t: self.envolver(t))
                for p in self._partes_nuevas(n):
                    menu.addAction(
                        _t(f"FLU.gui.agregar.{p}"), lambda p=p: self._agregar_parte(ident, p)
                    )
            elif ident is not None and parte not in ("cuerpo", "captura"):
                menu.addAction(
                    _t("FLU.gui.quitar_rama"),
                    lambda: self._aplicar(lambda m: flujo.quitar_rama(m, clave, ident, parte)),
                )
        menu.exec(self.arbol.viewport().mapToGlobal(punto))

    @staticmethod
    def _partes_nuevas(n: flujo.Nodo) -> list[str]:
        if n.tipo == "si":
            return ["rama"] + (["sino"] if n.alterno is None else [])
        if n.tipo in ("segun", "coincidir"):
            return ["caso"] + (["por_defecto"] if n.alterno is None else [])
        return []

    def _agregar_parte(self, ident: str, parte: str) -> None:
        etiqueta = ""
        if parte in ("rama", "caso"):
            campo = "condicion" if parte == "rama" else "caso"
            valores = self._pedir(_t(f"FLU.gui.agregar.{parte}"), [(campo, "")])
            if valores is None:
                return
            etiqueta = valores[campo]
        clave = self.clave
        self._aplicar(lambda m: flujo.agregar_rama(m, clave, ident, parte, etiqueta))

    def desplazar(self, ident: str, delta: int) -> bool:
        """Sube (-1) o baja (+1) un nodo dentro de su secuencia."""
        item = self.arbol.currentItem()
        if item is None or item.data(0, _ROL)[1] != ident:
            self.seleccionar_nodo(ident)
            item = self.arbol.currentItem()
        padre = item.parent()
        _, pid, parte = padre.data(0, _ROL)
        hermanos = [padre.child(i) for i in range(padre.childCount())]
        k = hermanos.index(item) + delta
        if not 0 <= k < len(hermanos):
            return False
        clave = self.clave
        return self._aplicar(lambda m: flujo.mover(m, clave, ident, flujo.Ubicacion(pid, parte, k)))

    # ------------------------------------------------------------ código y archivos

    def generar_codigo(self) -> str | None:
        """Programa completo en el idioma elegido; avisa si el diagrama tiene problemas."""
        if self.modelo is None:
            return None
        idioma = self.combo_idioma.currentText()
        problemas = flujo.validar(self.modelo)
        if problemas and (
            QMessageBox.question(
                self,
                _t("FLU.gui.titulo"),
                _t("FLU.gui.con_problemas", n=len(problemas)),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return None
        codigo = flujo.codigo_desde_modelo(self.modelo, idioma)
        self.codigo_generado.emit(codigo)
        return codigo

    def abrir_json(self) -> None:
        """Carga un diagrama JSON v1."""
        ruta, _ = QFileDialog.getOpenFileName(
            self, _t("FLU.gui.abrir"), "", _t("FLU.gui.filtro.json")
        )
        if not ruta:
            return
        try:
            with open(ruta, encoding="utf-8") as f:
                modelo = flujo.desde_json(f.read())
        except (OSError, flujo.ErrorFlujo) as e:
            QMessageBox.warning(self, _t("FLU.gui.titulo"), str(e))
            return
        if self.modelo is not None:
            self._historial.append(self.modelo)
        self._fijar_modelo(modelo)

    def _menu_exportar(self) -> None:
        menu = QMenu(self)
        for formato in flujo.FORMATOS:
            menu.addAction(_t(f"FLU.gui.formato.{formato}"), lambda f=formato: self.exportar(f))
        menu.exec(self._boton_exportar.mapToGlobal(self._boton_exportar.rect().bottomLeft()))

    def exportar(self, formato: str, ruta: str | None = None) -> bool:
        """Guarda el diagrama elegido (o el modelo, en JSON) en ``formato``."""
        if self.modelo is None:
            return False
        if ruta is None:
            ruta, _ = QFileDialog.getSaveFileName(
                self, _t("FLU.gui.exportar"), "", _t(f"FLU.gui.filtro.{formato}")
            )
            if not ruta:
                return False
        contenido = flujo.exportar(self.modelo, formato, self.clave, tema=self._tema)
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
        except OSError as e:
            QMessageBox.warning(self, _t("FLU.gui.titulo"), str(e))
            return False
        return True
