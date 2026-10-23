"""Panel Qt «Bloques»: editor de arrastrar y soltar con teclado completo (INV-4012).

Antes la GUI sólo tenía el editor de texto y el diagrama de flujo editable
por menús; no había forma de programar **construyendo** con bloques. Este
panel trabaja sobre el modelo de ``inveniolang.bloques`` (el mismo árbol que
el diagrama de flujo):

* lienzo ``QGraphicsView`` dibujado con la geometría pura de
  ``bloques/diseno.py``: cada categoría con su color, su icono y la silueta
  de su forma (muesca de pila, «C», sombrero, valor redondeado, valor
  lógico hexagonal), nunca sólo el color;
* arrastrar y soltar real (desde la paleta, entre sitios del lienzo y a la
  papelera) con la validación tipada de ``reglas.motivo_rechazo``: mientras
  se arrastra, la zona se marca como válida o no y el motivo se anuncia;
* todo se puede hacer con el teclado: flechas para recorrer los bloques en
  orden de lectura, ``M`` para recoger un bloque y flechas para elegir el
  destino entre las MISMAS zonas que usa el ratón, Intro para soltar,
  Insert para insertar desde la paleta, Supr, Ctrl+D, Ctrl+Z/Ctrl+Y y zoom;
  cada cambio se anuncia al lector de pantalla;
* sincronía con el editor de texto (código ⇄ bloques) y con el panel de
  diagrama de flujo (mismos ids), ejecución y paso a paso desde los bloques.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QByteArray, QMimeData, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QAccessible,
    QAccessibleAnnouncementEvent,
    QBrush,
    QColor,
    QDrag,
    QFont,
    QFontMetricsF,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QCheckBox,
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
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import api, bloques, i18n
from ..bloques import catalogo, diseno, edicion, reglas, texto
from ..flujo import ErrorFlujo

__all__ = ["LienzoBloques", "MIME_BLOQUE", "MIME_PALETA", "PanelBloques"]

MIME_PALETA = "application/x-inveniolang-paleta"
MIME_BLOQUE = "application/x-inveniolang-bloque"
_ROL = Qt.ItemDataRole.UserRole
_FOCO = {"claro": "#0B4FD8", "oscuro": "#FFD43B"}
_VALIDA = "#1B8A3A"
# Texto de los campos editables, sobre el fondo del lienzo (contraste AAA).
_TEXTO_CAMPO = {"claro": "#111111", "oscuro": "#F5F5F5"}
_INVALIDA = "#C62828"


def _t(clave: str, **args: object) -> str:
    return i18n.t(clave, **args)


def _redondeado(t: diseno.Trozo, radio: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(t.x, t.y, t.w, t.h), radio, radio)
    return path


def _anunciar(widget: QWidget, mensaje: str) -> None:
    """Anuncio para lectores de pantalla (Qt ≥ 6.8) además del texto visible."""
    QAccessible.updateAccessibility(QAccessibleAnnouncementEvent(widget, mensaje))


# ====================================================================== paleta y papelera


class _Paleta(QTreeWidget):
    """Paleta por categorías; arrastrable y operable con Intro."""

    def __init__(self, panel: PanelBloques):
        super().__init__()
        self._panel = panel
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAccessibleName(_t("BLQ.gui.paleta"))
        self.itemActivated.connect(self._activar)

    def mimeData(self, items):  # noqa: N802 - API de Qt
        """El arrastre lleva la clave de la entrada de paleta."""
        claves = [it.data(0, _ROL) for it in items if it.data(0, _ROL)]
        return mime_paleta(claves[0]) if claves else QMimeData()

    def mimeTypes(self):  # noqa: N802 - API de Qt
        """Tipos de arrastre que produce."""
        return [MIME_PALETA]

    def _activar(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        clave = item.data(0, _ROL)
        if clave:
            self._panel.empezar_colocacion(("paleta", clave))

    def llenar(self, idioma: str, tema: str, filtro: str = "") -> None:
        """Rellena la paleta (``filtro``: busca en el nombre de la entrada)."""
        self.clear()
        grupos: dict[str, QTreeWidgetItem] = {}
        for e in catalogo.PALETA:
            nombre = i18n.t(f"BLQ.paleta.{e.clave}", idioma)
            if filtro and filtro.lower() not in nombre.lower():
                continue
            cat = catalogo.CATEGORIAS[e.categoria]
            if e.categoria not in grupos:
                g = QTreeWidgetItem(
                    [f"{cat.icono}  {i18n.t(f'BLQ.categoria.{cat.nombre}', idioma)}"]
                )
                g.setFlags(Qt.ItemFlag.ItemIsEnabled)
                relleno, letra, _ = getattr(cat, tema)
                g.setBackground(0, QBrush(QColor(relleno)))
                g.setForeground(0, QBrush(QColor(letra)))
                self.addTopLevelItem(g)
                grupos[e.categoria] = g
            hijo = QTreeWidgetItem([f"{cat.icono} {nombre}"])
            hijo.setData(0, _ROL, e.clave)
            hijo.setToolTip(0, i18n.t(f"BLQ.categoria.{cat.nombre}", idioma))
            grupos[e.categoria].addChild(hijo)
        self.expandAll()


class _Papelera(QLabel):
    """Destino de arrastre que borra el bloque soltado."""

    def __init__(self, panel: PanelBloques):
        super().__init__("🗑 " + _t("BLQ.gui.papelera"))
        self._panel = panel
        self.setAcceptDrops(True)
        self.setAccessibleName(_t("BLQ.gui.papelera"))
        self.setFrameShape(QLabel.Shape.Box)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(40)

    def dragEnterEvent(self, event):  # noqa: N802 - API de Qt
        """Acepta bloques del lienzo."""
        if event.mimeData().hasFormat(MIME_BLOQUE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802 - API de Qt
        """Elimina el bloque soltado."""
        datos = event.mimeData()
        if datos.hasFormat(MIME_BLOQUE):
            ident = bytes(datos.data(MIME_BLOQUE).data()).decode("utf-8")
            if self._panel.eliminar(ident):
                event.acceptProposedAction()
                return
        event.ignore()


# ====================================================================== lienzo


class LienzoBloques(QGraphicsView):
    """Lienzo: dibuja el diseño, arrastra y suelta, y navega con el teclado."""

    def __init__(self, panel: PanelBloques):
        self.escena = QGraphicsScene()
        super().__init__(self.escena)
        self._panel = panel
        self._pulsado: tuple[str, QPointF] | None = None
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(_t("BLQ.gui.lienzo"))
        self.setToolTip(_t("BLQ.gui.ayuda_teclado"))

    # ---- ratón

    def mousePressEvent(self, event):  # noqa: N802 - API de Qt
        """Selecciona el bloque pulsado (Ctrl: añade a la selección)."""
        p = self.mapToScene(event.position().toPoint())
        caja = self._panel.diseno.caja_en(p.x(), p.y()) if self._panel.diseno else None
        if caja is not None:
            aditivo = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self._panel.seleccionar(caja.id, aditivo=aditivo)
            self._pulsado = (caja.id, event.position())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - API de Qt
        """Inicia el arrastre de un bloque del lienzo."""
        if self._pulsado is not None and event.buttons() & Qt.MouseButton.LeftButton:
            ident, origen = self._pulsado
            if (event.position() - origen).manhattanLength() > 8:
                self._pulsado = None
                drag = QDrag(self)
                drag.setMimeData(mime_bloque(ident))
                drag.exec(Qt.DropAction.MoveAction)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - API de Qt
        """Fin de pulsación sin arrastre."""
        self._pulsado = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802 - API de Qt
        """Doble clic: edita los campos del bloque."""
        p = self.mapToScene(event.position().toPoint())
        caja = self._panel.diseno.caja_en(p.x(), p.y()) if self._panel.diseno else None
        if caja is not None:
            self._panel.editar_campos(caja.id)

    def wheelEvent(self, event):  # noqa: N802 - API de Qt
        """Ctrl + rueda: zoom; sin Ctrl, desplazamiento normal."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._panel.zoom(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
        else:
            super().wheelEvent(event)

    # ---- arrastrar y soltar

    def _zona_evento(self, event) -> diseno.Zona | None:
        p = self.mapToScene(event.position().toPoint())
        return self._panel.diseno.zona_en(p.x(), p.y()) if self._panel.diseno else None

    def dragEnterEvent(self, event):  # noqa: N802 - API de Qt
        """Acepta bloques de la paleta o del propio lienzo."""
        if origen_de(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # noqa: N802 - API de Qt
        """Marca la zona bajo el puntero como válida o no (con el motivo)."""
        origen = origen_de(event.mimeData())
        zona = self._zona_evento(event)
        if origen is None or zona is None:
            self._panel.marcar_zona(None, None)
            event.ignore()
            return
        motivo = self._panel.motivo(origen, zona)
        self._panel.marcar_zona(zona, motivo)
        if motivo is None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):  # noqa: N802 - API de Qt
        """Quita la marca de zona."""
        self._panel.marcar_zona(None, None)

    def dropEvent(self, event):  # noqa: N802 - API de Qt
        """Suelta en la zona bajo el puntero."""
        origen = origen_de(event.mimeData())
        zona = self._zona_evento(event)
        self._panel.marcar_zona(None, None)
        if origen is not None and zona is not None and self._panel.soltar(origen, zona):
            event.acceptProposedAction()
        else:
            event.ignore()

    # ---- teclado

    def keyPressEvent(self, event):  # noqa: N802 - API de Qt
        """Navegación, colocación y edición por teclado (ver ``BLQ.gui.ayuda_teclado``)."""
        if self._panel.tecla(event.key(), event.modifiers()):
            event.accept()
            return
        super().keyPressEvent(event)


def mime_bloque(ident: str) -> QMimeData:
    """Datos de arrastre de un bloque del lienzo."""
    datos = QMimeData()
    datos.setData(MIME_BLOQUE, QByteArray(ident.encode("utf-8")))
    return datos


def mime_paleta(clave: str) -> QMimeData:
    """Datos de arrastre de una entrada de la paleta."""
    datos = QMimeData()
    datos.setData(MIME_PALETA, QByteArray(clave.encode("utf-8")))
    return datos


def origen_de(datos: QMimeData) -> tuple[str, str] | None:
    """(``paleta``|``mover``, clave o id) de unos datos de arrastre."""
    for mime, clase in ((MIME_PALETA, "paleta"), (MIME_BLOQUE, "mover")):
        if datos.hasFormat(mime):
            return clase, bytes(datos.data(mime).data()).decode("utf-8")
    return None


# ====================================================================== panel


class PanelBloques(QWidget):
    """Panel «Bloques» (modelo ``inveniolang.bloques``)."""

    codigo_generado = Signal(str)
    bloque_elegido = Signal(str, int)
    modelo_flujo = Signal(object)
    trazar_codigo = Signal(str, object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.modelo: bloques.ModeloBloques | None = None
        self.diseno: diseno.Diseno | None = None
        self.foco: str | None = None
        self.seleccion: list[str] = []
        self.lineas: dict[str, int] = {}
        self._deshacer: list[bloques.ModeloBloques] = []
        self._rehacer: list[bloques.ModeloBloques] = []
        self._tema = "oscuro"
        self._escala = 1.0
        self._colocando: tuple[str, str] | None = None
        self._zonas_validas: list[diseno.Zona] = []
        self._zona_actual = 0
        self._marca = None
        self._motivos: dict[tuple, Any] = {}
        self._problemas: list[edicion.Problema] = []
        # Último código que los bloques mandaron al editor: cuando el análisis
        # en vivo del editor lo devuelve, no hay nada que recargar (y recargar
        # renovaría los ids y perdería el foco del teclado).
        self._ultimo_codigo: str | None = None
        self.proveedor_codigo: Callable[[], tuple[str, str | None] | None] | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        barra = QHBoxLayout()
        self.botones: dict[str, QPushButton] = {}
        for clave, accion in (
            ("desde_editor", self.generar_desde_editor),
            ("nuevo", self.nuevo),
            ("abrir", self.abrir_json),
            ("guardar", self.guardar_json),
            ("deshacer", self.deshacer),
            ("rehacer", self.rehacer),
            ("alejar", lambda: self.zoom(1 / 1.2)),
            ("acercar", lambda: self.zoom(1.2)),
            ("a_codigo", self.enviar_codigo),
            ("ejecutar", self.ejecutar),
            ("paso_a_paso", self.paso_a_paso),
        ):
            b = QPushButton(_t(f"BLQ.gui.{clave}"))
            b.setAccessibleName(_t(f"BLQ.gui.{clave}"))
            b.clicked.connect(accion)
            barra.addWidget(b)
            self.botones[clave] = b
        barra.addWidget(QLabel(_t("BLQ.gui.idioma")))
        self.combo_idioma = QComboBox()
        self.combo_idioma.addItems(list(i18n.IDIOMAS))
        self.combo_idioma.setAccessibleName(_t("BLQ.gui.idioma"))
        self.combo_idioma.currentTextChanged.connect(self._cambiar_idioma)
        barra.addWidget(self.combo_idioma)
        self.sincronizar = QCheckBox(_t("BLQ.gui.sincronizar"))
        self.sincronizar.setChecked(True)
        barra.addWidget(self.sincronizar)
        barra.addStretch(1)
        lay.addLayout(barra)

        split = QSplitter(Qt.Orientation.Horizontal)
        izq = QWidget()
        lizq = QVBoxLayout(izq)
        lizq.setContentsMargins(0, 0, 0, 0)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText(_t("BLQ.gui.buscar"))
        self.buscar.setAccessibleName(_t("BLQ.gui.buscar"))
        self.buscar.textChanged.connect(self._filtrar)
        self.buscar.returnPressed.connect(self._primera_de_paleta)
        lizq.addWidget(self.buscar)
        self.paleta = _Paleta(self)
        lizq.addWidget(self.paleta, 1)
        self.papelera = _Papelera(self)
        lizq.addWidget(self.papelera)
        split.addWidget(izq)
        self.lienzo = LienzoBloques(self)
        split.addWidget(self.lienzo)
        split.setStretchFactor(1, 3)
        lay.addWidget(split, 1)

        self.estado = QLabel(_t("BLQ.gui.vacio"))
        self.estado.setWordWrap(True)
        self.estado.setAccessibleName(_t("BLQ.gui.estado"))
        lay.addWidget(self.estado)
        abajo = QSplitter(Qt.Orientation.Horizontal)
        self.lista_problemas = QListWidget()
        self.lista_problemas.setAccessibleName(_t("BLQ.gui.problemas"))
        self.lista_problemas.itemActivated.connect(
            lambda it: it.data(_ROL) and self.seleccionar(it.data(_ROL))
        )
        abajo.addWidget(self.lista_problemas)
        cont = QWidget()
        lcont = QVBoxLayout(cont)
        lcont.setContentsMargins(0, 0, 0, 0)
        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText(_t("BLQ.gui.entrada"))
        self.entrada.setAccessibleName(_t("BLQ.gui.entrada"))
        lcont.addWidget(self.entrada)
        self.salida = QPlainTextEdit()
        self.salida.setReadOnly(True)
        self.salida.setAccessibleName(_t("BLQ.gui.salida"))
        lcont.addWidget(self.salida)
        abajo.addWidget(cont)
        abajo.setMaximumHeight(150)
        lay.addWidget(abajo)

        for secuencia, accion in (
            (QKeySequence.StandardKey.Undo, self.deshacer),
            (QKeySequence.StandardKey.Redo, self.rehacer),
        ):
            atajo = QShortcut(secuencia, self)
            atajo.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            atajo.activated.connect(accion)
        self.paleta.llenar(self.idioma, self._tema_paleta())

    # ------------------------------------------------------------ estado

    @property
    def idioma(self) -> str:
        """Idioma de los bloques y de los rótulos."""
        return self.combo_idioma.currentText()

    def _tema_paleta(self) -> str:
        return "claro" if self._tema == "claro" else "oscuro"

    def establecer_tema(self, claro: bool) -> None:
        """Tema del lienzo y de la paleta."""
        self._tema = "claro" if claro else "oscuro"
        self.paleta.llenar(self.idioma, self._tema_paleta(), self.buscar.text())
        self._dibujar()

    def anunciar(self, mensaje: str) -> None:
        """Muestra y anuncia un mensaje de estado."""
        self.estado.setText(mensaje)
        _anunciar(self.estado, mensaje)

    def _filtrar(self, texto: str) -> None:
        self.paleta.llenar(self.idioma, self._tema_paleta(), texto)

    def _primera_de_paleta(self) -> None:
        for i in range(self.paleta.topLevelItemCount()):
            g = self.paleta.topLevelItem(i)
            if g.childCount():
                self.paleta.setCurrentItem(g.child(0))
                self.paleta.setFocus()
                return

    # ------------------------------------------------------------ cargar

    def cargar_codigo(self, codigo: str, ruta: str | None = None, silencioso: bool = False) -> bool:
        """Bloques de ``codigo``; False (y los diagnósticos) si no compila."""
        try:
            modelo = bloques.bloques_desde_codigo(
                codigo, self.idioma, ruta=ruta or "<editor>", ruta_fuente=ruta
            )
        except ErrorFlujo as e:
            if silencioso:
                self.anunciar(_t("BLQ.gui.errores_codigo"))
            else:
                self.lista_problemas.clear()
                self.lista_problemas.addItem(e.texto())
                self.lista_problemas.addItems(list(e.diagnosticos))
            return False
        if (
            self.modelo is not None
            and silencioso
            and bloques.a_dict(modelo) == bloques.a_dict(self.modelo)
        ):
            return True
        if self.modelo is not None:
            self._deshacer.append(self.modelo)
        self._rehacer.clear()
        self._fijar(modelo, emitir_codigo=False)
        return True

    def generar_desde_editor(self) -> None:
        """Bloques del archivo del editor activo."""
        if self.proveedor_codigo is None:
            return
        datos = self.proveedor_codigo()
        if datos is not None:
            self.cargar_codigo(*datos)

    def sincronizar_desde_codigo(self, codigo: str, ruta: str | None = None) -> None:
        """Editor → bloques (en vivo): sólo si está activada la sincronía."""
        if self.sincronizar.isChecked() and codigo.strip() and codigo != self._ultimo_codigo:
            self.cargar_codigo(codigo, ruta, silencioso=True)

    def cargar_flujo(self, modelo_flujo: Any) -> bool:
        """Diagrama de flujo → bloques (el panel de flujo cambió el árbol)."""
        try:
            modelo = bloques.desde_flujo(modelo_flujo)
        except bloques.ErrorBloques:
            return False  # el diagrama tiene un texto a medio escribir
        if self.modelo is not None and bloques.a_dict(modelo) == bloques.a_dict(self.modelo):
            return True
        if self.modelo is not None:
            self._deshacer.append(self.modelo)
        self._fijar(modelo, emitir_flujo=False)
        return True

    def nuevo(self) -> None:
        """Programa nuevo con un ``main`` vacío."""
        if self.modelo is not None:
            self._deshacer.append(self.modelo)
        self._fijar(edicion.nuevo_modelo(self.idioma))

    def _fijar(self, modelo, emitir_codigo: bool = True, emitir_flujo: bool = True) -> None:
        self.modelo = modelo
        self.combo_idioma.blockSignals(True)
        self.combo_idioma.setCurrentText(modelo.idioma)
        self.combo_idioma.blockSignals(False)
        self._motivos.clear()
        self._problemas = edicion.validar(modelo)
        self.lineas = {}
        if not self._problemas:
            codigo, self.lineas = bloques.codigo_con_lineas(modelo)
            if emitir_codigo and self.sincronizar.isChecked():
                self._ultimo_codigo = codigo
                self.codigo_generado.emit(codigo)
        if emitir_flujo:
            self.modelo_flujo.emit(bloques.a_flujo(modelo))
        if self.foco is not None and not any(
            b.id == self.foco for b in bloques.recorrer(modelo.programa)
        ):
            self.foco = None
        self.seleccion = [i for i in self.seleccion if self._existe(i)]
        self._mostrar_problemas()
        self._dibujar()

    def _existe(self, ident: str) -> bool:
        return self.modelo is not None and any(
            b.id == ident for b in bloques.recorrer(self.modelo.programa)
        )

    def _mostrar_problemas(self) -> None:
        self.lista_problemas.clear()
        for p in self._problemas:
            self.lista_problemas.addItem(f"[{p.bloque or '-'}] {p.texto(self.idioma)}")
            self.lista_problemas.item(self.lista_problemas.count() - 1).setData(_ROL, p.bloque)
        if self._problemas:
            self.anunciar(_t("BLQ.anuncio.problemas", n=len(self._problemas)))

    def aplicar(self, operacion: Callable[[Any], Any], anuncio: str = "") -> bool:
        """Ejecuta una operación pura; si falla, explica el motivo (bilingüe)."""
        if self.modelo is None:
            return False
        try:
            nuevo = operacion(self.modelo)
        except (bloques.ErrorBloques, ErrorFlujo) as e:
            self.anunciar(_t("BLQ.anuncio.rechazo", motivo=e.texto(self.idioma)))
            return False
        self._deshacer.append(self.modelo)
        self._rehacer.clear()
        self._fijar(nuevo)
        if anuncio:
            self.anunciar(anuncio)
        return True

    def deshacer(self) -> None:
        """Vuelve al modelo anterior."""
        if self._deshacer and self.modelo is not None:
            self._rehacer.append(self.modelo)
            self._fijar(self._deshacer.pop())
            self.anunciar(_t("BLQ.anuncio.deshecho"))

    def rehacer(self) -> None:
        """Rehace lo deshecho."""
        if self._rehacer and self.modelo is not None:
            self._deshacer.append(self.modelo)
            self._fijar(self._rehacer.pop())
            self.anunciar(_t("BLQ.anuncio.rehecho"))

    def _cambiar_idioma(self, idioma: str) -> None:
        self.paleta.llenar(idioma, self._tema_paleta(), self.buscar.text())
        if self.modelo is not None and idioma != self.modelo.idioma:
            self.aplicar(lambda m: bloques.traducir_bloques(m, idioma))

    # ------------------------------------------------------------ dibujo

    def zoom(self, factor: float) -> None:
        """Escala el lienzo (entre 0.3 y 3)."""
        nueva = min(3.0, max(0.3, self._escala * factor))
        self.lienzo.scale(nueva / self._escala, nueva / self._escala)
        self._escala = nueva

    def _colores(self, categoria: str) -> tuple[str, str, str]:
        return getattr(catalogo.CATEGORIAS[categoria], self._tema_paleta())

    def _dibujar(self) -> None:
        escena = self.lienzo.escena
        escena.clear()
        self._marca = None
        fondo = catalogo.FONDO_LIENZO[self._tema_paleta()]
        escena.setBackgroundBrush(QBrush(QColor(fondo)))
        if self.modelo is None:
            self.diseno = None
            return
        metrica = QFontMetricsF(QFont(self.font()))
        self.diseno = diseno.disenar(self.modelo, self.idioma, metrica.horizontalAdvance)
        malos = {p.bloque for p in self._problemas}
        for caja in self.diseno.todas():
            self._dibujar_caja(caja, caja.id in malos)
        escena.setSceneRect(0, 0, self.diseno.ancho, self.diseno.alto)
        if self.foco is not None:
            self._dibujar_foco()

    def _silueta(self, c: diseno.Caja) -> QPainterPath:
        r = QRectF(c.x, c.y, c.w, c.h)
        path = QPainterPath()
        if c.forma == "valor" and c.salida == "logico":
            m = min(10.0, c.h / 2)
            path.moveTo(r.left() + m, r.top())
            path.lineTo(r.right() - m, r.top())
            path.lineTo(r.right(), r.center().y())
            path.lineTo(r.right() - m, r.bottom())
            path.lineTo(r.left() + m, r.bottom())
            path.lineTo(r.left(), r.center().y())
            path.closeSubpath()
        elif c.forma == "valor":
            path.addRoundedRect(r, min(12.0, c.h / 2), min(12.0, c.h / 2))
        elif c.forma == "definicion":
            path.moveTo(r.left(), r.top() + 10)
            path.quadTo(r.left() + 40, r.top() - 10, r.left() + 90, r.top() + 4)
            path.lineTo(r.right(), r.top() + 4)
            path.lineTo(r.right(), r.bottom())
            path.lineTo(r.left(), r.bottom())
            path.closeSubpath()
        else:
            # Pieza de pila: muesca arriba (encaja con la anterior) y saliente abajo.
            path.moveTo(r.left(), r.top())
            path.lineTo(r.left() + 12, r.top())
            path.lineTo(r.left() + 16, r.top() + 4)
            path.lineTo(r.left() + 28, r.top() + 4)
            path.lineTo(r.left() + 32, r.top())
            path.lineTo(r.right(), r.top())
            path.lineTo(r.right(), r.bottom())
            if c.forma in ("instruccion", "c"):
                path.lineTo(r.left() + 32, r.bottom())
                path.lineTo(r.left() + 28, r.bottom() + 4)
                path.lineTo(r.left() + 16, r.bottom() + 4)
                path.lineTo(r.left() + 12, r.bottom())
            path.lineTo(r.left(), r.bottom())
            path.closeSubpath()
        return path

    def _dibujar_caja(self, c: diseno.Caja, con_problema: bool) -> None:
        escena = self.lienzo.escena
        relleno, letra, borde = self._colores(c.categoria)
        pen = QPen(QColor(_INVALIDA if con_problema else borde))
        pen.setWidthF(2.5 if con_problema else 1.2)
        if con_problema:
            pen.setStyle(Qt.PenStyle.DashLine)
        item = escena.addPath(self._silueta(c), pen, QBrush(QColor(relleno)))
        item.setData(0, c.id)
        item.setToolTip(self._anuncio_de(c.id))
        if c.forma in ("parte", "miembro"):
            escena.addRect(QRectF(c.x, c.y, 4, c.h), QPen(Qt.PenStyle.NoPen), QBrush(QColor(borde)))
        fondo = QColor(catalogo.FONDO_LIENZO[self._tema_paleta()])
        icono = catalogo.CATEGORIAS[c.categoria].icono
        if c.forma != "valor":
            marca = escena.addSimpleText(icono)
            marca.setBrush(QBrush(QColor(letra)))
            marca.setPos(c.x + c.w - 16, c.y + 4)
        for t in c.trozos + c.rotulos:
            if t.clase == "texto":
                txt = escena.addSimpleText(t.texto)
                txt.setBrush(QBrush(QColor(letra)))
                txt.setPos(t.x, t.y + 5)
            elif t.clase in ("campo", "mas"):
                escena.addPath(_redondeado(t, 4), QPen(QColor(borde)), QBrush(fondo))
                txt = escena.addSimpleText(t.texto)
                txt.setBrush(QBrush(QColor(_TEXTO_CAMPO[self._tema_paleta()])))
                txt.setPos(t.x + 4, t.y + 2)
            elif t.clase == "hueco":
                pen_h = QPen(QColor(borde))
                pen_h.setStyle(Qt.PenStyle.DashLine)
                hueco = escena.addPath(_redondeado(t, 8), pen_h, QBrush(fondo))
                hueco.setToolTip(_t("BLQ.gui.hueco_vacio", hueco=_t(f"BLQ.parte.{t.ref}")))

    def _dibujar_foco(self) -> None:
        caja = self.diseno.caja(self.foco) if self.diseno and self.foco else None
        if caja is None:
            return
        for ident in self.seleccion:
            otra = self.diseno.caja(ident) if self.diseno else None
            if otra is not None and otra.id != caja.id:
                pen = QPen(QColor(_FOCO[self._tema_paleta()]))
                pen.setWidthF(2)
                self.lienzo.escena.addRect(
                    QRectF(otra.x - 2, otra.y - 2, otra.w + 4, otra.h + 4), pen
                ).setZValue(9)
        pen = QPen(QColor(_FOCO[self._tema_paleta()]))
        pen.setWidthF(3)
        pen.setStyle(Qt.PenStyle.DashLine)
        marco = self.lienzo.escena.addRect(
            QRectF(caja.x - 3, caja.y - 3, caja.w + 6, caja.h + 6), pen
        )
        marco.setZValue(10)
        self.lienzo.ensureVisible(marco)

    def marcar_zona(self, zona: diseno.Zona | None, motivo: Any, mostrar: bool = False) -> None:
        """Marca la zona de destino (verde: válida; rojo: no encaja, con el motivo).

        ``mostrar`` desplaza el lienzo hasta ella (colocación con teclado); al
        arrastrar con el ratón no se desplaza, para no mover el lienzo bajo
        el puntero.
        """
        if self._marca is not None:
            self.lienzo.escena.removeItem(self._marca)
            self._marca = None
        if zona is None:
            return
        pen = QPen(QColor(_VALIDA if motivo is None else _INVALIDA))
        pen.setWidthF(3)
        self._marca = self.lienzo.escena.addRect(
            QRectF(zona.x, zona.y, zona.w, zona.h), pen, QBrush(Qt.BrushStyle.NoBrush)
        )
        self._marca.setZValue(20)
        if mostrar:
            self.lienzo.ensureVisible(self._marca)
        if motivo is not None:
            self.estado.setText(_t("BLQ.anuncio.rechazo", motivo=motivo.texto(self.idioma)))

    # ------------------------------------------------------------ anuncios

    def _anuncio_de(self, ident: str) -> str:
        if self.modelo is None:
            return ""
        b = self.modelo.buscar(ident)
        padre, ranura = edicion.donde_esta(self.modelo, ident)
        if padre is None:
            lugar = _t(
                "BLQ.anuncio.lugar_programa",
                posicion=(ranura.indice or 0) + 1,
                total=len(self.modelo.programa),
            )
        elif ranura.clase == "hueco":
            lugar = _t(
                "BLQ.anuncio.lugar_hueco",
                hueco=_t(f"BLQ.parte.{ranura.nombre}"),
                padre=_t(f"BLQ.tipo.{padre.tipo}"),
            )
        else:
            lugar = _t(
                "BLQ.anuncio.lugar_lista",
                lista=_t(f"BLQ.parte.{ranura.nombre}"),
                padre=_t(f"BLQ.tipo.{padre.tipo}"),
                posicion=(ranura.indice or 0) + 1,
                total=len(padre.listas[ranura.nombre]),
            )
        problemas = [p.texto(self.idioma) for p in self._problemas if p.bloque == ident]
        return " ".join(
            [
                _t(
                    "BLQ.anuncio.foco",
                    tipo=_t(f"BLQ.tipo.{b.tipo}"),
                    texto=texto.rotulo(b, self.idioma),
                    lugar=lugar,
                ),
                *problemas,
            ]
        )

    # ------------------------------------------------------------ selección

    def seleccionar(self, ident: str | None, aditivo: bool = False, emitir: bool = True) -> None:
        """Pone el foco en el bloque (con ``aditivo`` lo suma a la selección)."""
        if ident is None or not self._existe(ident):
            return
        if aditivo:
            if ident in self.seleccion:
                self.seleccion.remove(ident)
            else:
                self.seleccion.append(ident)
        else:
            self.seleccion = [ident]
        self.foco = ident
        self._dibujar()
        anuncio = self._anuncio_de(ident)
        self.lienzo.setAccessibleDescription(anuncio)
        self.anunciar(anuncio)
        if emitir:
            self.bloque_elegido.emit(ident, self._linea_de(ident))

    def _linea_de(self, ident: str) -> int:
        if ident in self.lineas:
            return self.lineas[ident]
        if self.modelo is None:
            return 0
        b: Any = self.modelo.buscar(ident)
        ctx = reglas.Contexto(self.modelo)
        for anc in [b, *ctx.ancestros(b)]:
            if anc.id in self.lineas:
                return self.lineas[anc.id]
        return 0

    def seleccionar_linea(self, linea: int) -> None:
        """Editor → bloques: foco en la instrucción de esa línea (sin reemitir)."""
        for ident, n in self.lineas.items():
            if n == linea:
                if ident != self.foco:
                    self.seleccionar(ident, emitir=False)
                return

    def resaltar_linea(self, linea: int) -> None:
        """Paso a paso: resalta el bloque que se está ejecutando."""
        self.seleccionar_linea(linea)

    # ------------------------------------------------------------ operaciones

    def _bloque_origen(self, origen: tuple[str, str]) -> bloques.Bloque:
        return edicion.desde_paleta(origen[1], self.idioma)

    def _destino(self, zona: diseno.Zona) -> edicion.Destino:
        return edicion.Destino(zona.padre, zona.parte, zona.indice)

    def _operacion(self, origen: tuple[str, str], zona: diseno.Zona):
        destino = self._destino(zona)
        if origen[0] == "paleta":
            nuevo = self._bloque_origen(origen)
            return lambda m: edicion.insertar(m, nuevo, destino)
        ident = origen[1]
        if self.modelo is not None and zona.clase == "lista":
            padre, ranura = edicion.donde_esta(self.modelo, ident)
            mismo = (padre.id if padre is not None else None) == zona.padre
            if mismo and ranura.nombre == zona.parte and ranura.indice is not None:
                indice = zona.indice or 0
                if indice > ranura.indice:
                    destino = edicion.Destino(zona.padre, zona.parte, indice - 1)
        return lambda m: edicion.mover(m, ident, destino)

    def motivo(self, origen: tuple[str, str], zona: diseno.Zona) -> Any:
        """Por qué ``origen`` no se puede soltar en ``zona`` (``None``: sí se puede)."""
        clave = (origen, zona.padre, zona.parte, zona.indice)
        if clave not in self._motivos:
            try:
                self._operacion(origen, zona)(self.modelo)
                self._motivos[clave] = None
            except (bloques.ErrorBloques, ErrorFlujo) as e:
                self._motivos[clave] = e
        return self._motivos[clave]

    def soltar(self, origen: tuple[str, str], zona: diseno.Zona) -> bool:
        """Suelta ``origen`` (entrada de paleta o bloque) en ``zona``."""
        if self.modelo is None:
            self.nuevo()
        assert self.modelo is not None
        antes = {b.id for b in bloques.recorrer(self.modelo.programa)}
        tipo = (
            catalogo.TIPOS[next(e.tipo for e in catalogo.PALETA if e.clave == origen[1])]
            if origen[0] == "paleta"
            else catalogo.TIPOS[self.modelo.buscar(origen[1]).tipo]
        )
        clave = "BLQ.anuncio.insertado" if origen[0] == "paleta" else "BLQ.anuncio.movido"
        ok = self.aplicar(
            self._operacion(origen, zona), _t(clave, tipo=_t(f"BLQ.tipo.{tipo.tipo}"))
        )
        if ok:
            assert self.modelo is not None
            nuevos = [b.id for b in bloques.recorrer(self.modelo.programa) if b.id not in antes]
            foco = nuevos[0] if origen[0] == "paleta" and nuevos else origen[1]
            self.foco = foco
            self.seleccion = [foco]
            self._dibujar()
        return ok

    def eliminar(self, ident: str) -> bool:
        """Elimina un bloque (papelera o Supr)."""
        if self.modelo is None or not self._existe(ident):
            return False
        tipo = self.modelo.buscar(ident).tipo
        siguiente = self._vecino(ident, 1) or self._vecino(ident, -1)
        ok = self.aplicar(
            lambda m: edicion.eliminar(m, ident),
            _t("BLQ.anuncio.eliminado", tipo=_t(f"BLQ.tipo.{tipo}")),
        )
        if ok and siguiente is not None and self._existe(siguiente):
            self.foco = siguiente
            self._dibujar()
        return ok

    def duplicar(self, ident: str) -> bool:
        """Duplica un bloque junto a él."""
        if self.modelo is None:
            return False
        tipo = self.modelo.buscar(ident).tipo
        return self.aplicar(
            lambda m: edicion.duplicar(m, ident),
            _t("BLQ.anuncio.duplicado", tipo=_t(f"BLQ.tipo.{tipo}")),
        )

    def envolver(self, tipo: str) -> bool:
        """Envuelve la selección (bloques consecutivos) en un contenedor ``tipo``."""
        ids = list(self.seleccion) or ([self.foco] if self.foco else [])
        if self.modelo is not None and ids:
            padre, ranura = edicion.donde_esta(self.modelo, ids[0])
            lista = self.modelo.programa if padre is None else padre.listas.get(ranura.nombre, [])
            orden = {b.id: k for k, b in enumerate(lista)}
            ids.sort(key=lambda i: orden.get(i, 0))
        return self.aplicar(
            lambda m: edicion.envolver(m, ids, tipo),
            _t("BLQ.anuncio.envuelto", tipo=_t(f"BLQ.tipo.{tipo}")),
        )

    def editar_campos(self, ident: str, valores: dict[str, Any] | None = None) -> bool:
        """Edita los campos del bloque (formulario o ``valores`` dados)."""
        if self.modelo is None:
            return False
        b = self.modelo.buscar(ident)
        desc = catalogo.TIPOS[b.tipo]
        if not desc.campos:
            return False
        if valores is None:
            valores = self._formulario(b)
            if valores is None:
                return False
        cambios = {k: v for k, v in valores.items() if b.campos.get(k) != v}
        if not cambios:
            return False

        def todas(m):
            for campo, valor in cambios.items():
                m = edicion.editar(m, ident, campo, valor)
            return m

        anuncio = "; ".join(
            _t("BLQ.anuncio.editado", campo=_t(f"BLQ.parte.{k}"), valor=str(v))
            for k, v in cambios.items()
        )
        return self.aplicar(todas, anuncio)

    def _formulario(self, b: bloques.Bloque) -> dict[str, Any] | None:
        d = QDialog(self)
        d.setWindowTitle(_t(f"BLQ.tipo.{b.tipo}"))
        form = QFormLayout(d)
        lectores: dict[str, Callable[[], Any]] = {}
        for c in catalogo.TIPOS[b.tipo].campos:
            etiqueta = _t(f"BLQ.parte.{c.nombre}")
            if c.clase == "bandera":
                w: QWidget = QCheckBox()
                w.setChecked(bool(b.campos[c.nombre]))
                lectores[c.nombre] = w.isChecked
            elif c.clase == "opcion":
                w = QComboBox()
                opciones = ([""] if c.vacio_ok else []) + list(c.opciones)
                for o in opciones:
                    nombre = (
                        i18n.t(f"BLQ.valor.{o}")
                        if i18n.REGISTRO.obtener("es").tiene(f"BLQ.valor.{o}")
                        else o
                    )
                    w.addItem(nombre or "—", o)
                w.setCurrentIndex(
                    max(
                        0,
                        opciones.index(b.campos[c.nombre]) if b.campos[c.nombre] in opciones else 0,
                    )
                )
                lectores[c.nombre] = w.currentData
            else:
                w = QLineEdit(str(b.campos[c.nombre]))
                lectores[c.nombre] = w.text
            w.setAccessibleName(etiqueta)
            form.addRow(etiqueta, w)
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(d.accept)
        botones.rejected.connect(d.reject)
        form.addRow(botones)
        if d.exec() != QDialog.DialogCode.Accepted:
            return None
        return {k: leer() for k, leer in lectores.items()}

    # ------------------------------------------------------------ teclado

    def _orden(self) -> list[str]:
        return [c.id for c in self.diseno.todas()] if self.diseno else []

    def _vecino(self, ident: str, paso: int) -> str | None:
        orden = self._orden()
        if ident not in orden:
            return None
        k = orden.index(ident) + paso
        return orden[k] if 0 <= k < len(orden) else None

    def empezar_colocacion(self, origen: tuple[str, str]) -> None:
        """Modo teclado: recoge ``origen`` y deja elegir su destino con las flechas."""
        if self.modelo is None:
            self.nuevo()
        if self.diseno is None:
            return
        self._colocando = origen
        self._zonas_validas = [z for z in self.diseno.zonas if self.motivo(origen, z) is None]
        self._zona_actual = 0
        if origen[0] == "mover":
            tipo = self.modelo.buscar(origen[1]).tipo if self.modelo else ""
        else:
            tipo = next(e.tipo for e in catalogo.PALETA if e.clave == origen[1])
        self.lienzo.setFocus()
        self.anunciar(_t("BLQ.anuncio.recogido", tipo=_t(f"BLQ.tipo.{tipo}")))
        if not self._zonas_validas:
            self._colocando = None
            self.anunciar(_t("BLQ.anuncio.cancelado"))
            return
        self._mostrar_zona()

    def _mostrar_zona(self) -> None:
        zona = self._zonas_validas[self._zona_actual]
        self.marcar_zona(zona, None, mostrar=True)
        if zona.padre is None:
            lugar = _t(
                "BLQ.anuncio.lugar_programa",
                posicion=(zona.indice or 0) + 1,
                total=len(self.modelo.programa) + 1 if self.modelo else 1,
            )
        else:
            assert self.modelo is not None
            padre = self.modelo.buscar(zona.padre)
            if zona.clase == "hueco":
                lugar = _t(
                    "BLQ.anuncio.lugar_hueco",
                    hueco=_t(f"BLQ.parte.{zona.parte}"),
                    padre=texto.rotulo(padre, self.idioma),
                )
            else:
                lugar = _t(
                    "BLQ.anuncio.lugar_lista",
                    lista=_t(f"BLQ.parte.{zona.parte}"),
                    padre=texto.rotulo(padre, self.idioma),
                    posicion=(zona.indice or 0) + 1,
                    total=len(padre.listas[zona.parte]) + 1,
                )
        self.anunciar(_t("BLQ.anuncio.destino", lugar=lugar))

    def tecla(self, tecla: int, mods: Any) -> bool:
        """Atiende una tecla del lienzo; True si la consumió."""
        K = Qt.Key  # noqa: N806 - alias corto de la enumeración de Qt
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if self._colocando is not None:
            if tecla in (K.Key_Down, K.Key_Right, K.Key_Tab):
                self._zona_actual = (self._zona_actual + 1) % len(self._zonas_validas)
                self._mostrar_zona()
            elif tecla in (K.Key_Up, K.Key_Left, K.Key_Backtab):
                self._zona_actual = (self._zona_actual - 1) % len(self._zonas_validas)
                self._mostrar_zona()
            elif tecla in (K.Key_Return, K.Key_Enter, K.Key_Space):
                origen, zona = self._colocando, self._zonas_validas[self._zona_actual]
                self._colocando = None
                self.marcar_zona(None, None)
                self.soltar(origen, zona)
            elif tecla == K.Key_Escape:
                self._colocando = None
                self.marcar_zona(None, None)
                self.anunciar(_t("BLQ.anuncio.cancelado"))
            return True
        if ctrl and tecla in (K.Key_Plus, K.Key_Equal):
            self.zoom(1.2)
            return True
        if ctrl and tecla == K.Key_Minus:
            self.zoom(1 / 1.2)
            return True
        if ctrl and tecla == K.Key_0:
            self.zoom(1 / self._escala)
            return True
        if ctrl and tecla == K.Key_Z:
            self.deshacer()
            return True
        if ctrl and tecla == K.Key_Y:
            self.rehacer()
            return True
        if tecla in (K.Key_Insert,) or (ctrl and tecla == K.Key_I):
            self.buscar.setFocus()
            self.buscar.selectAll()
            return True
        orden = self._orden()
        if not orden:
            if tecla in (K.Key_N,):
                self.nuevo()
                return True
            return False
        if self.foco is None or self.foco not in orden:
            if tecla in (K.Key_Down, K.Key_Up, K.Key_Home, K.Key_End, K.Key_Right, K.Key_Left):
                self.seleccionar(orden[0])
                return True
            return False
        if tecla in (K.Key_Down, K.Key_Up):
            vecino = self._vecino(self.foco, 1 if tecla == K.Key_Down else -1)
            if vecino is not None:
                self.seleccionar(vecino, aditivo=shift)
            return True
        if tecla == K.Key_Home:
            self.seleccionar(orden[0])
            return True
        if tecla == K.Key_End:
            self.seleccionar(orden[-1])
            return True
        if tecla == K.Key_Left and self.modelo is not None:
            padre, _ = edicion.donde_esta(self.modelo, self.foco)
            if padre is not None:
                self.seleccionar(padre.id)
            return True
        if tecla == K.Key_Right and self.diseno is not None:
            caja = self.diseno.caja(self.foco)
            if caja is not None and caja.hijas:
                self.seleccionar(caja.hijas[0].id)
            return True
        if tecla in (K.Key_Return, K.Key_Enter, K.Key_F2):
            self.editar_campos(self.foco)
            return True
        if tecla in (K.Key_Delete, K.Key_Backspace):
            self.eliminar(self.foco)
            return True
        if ctrl and tecla == K.Key_D:
            self.duplicar(self.foco)
            return True
        if tecla == K.Key_M and not ctrl:
            self.empezar_colocacion(("mover", self.foco))
            return True
        if tecla == K.Key_Menu or (shift and tecla == K.Key_F10):
            self.menu_contextual(self.foco)
            return True
        return False

    def menu_contextual(self, ident: str) -> None:
        """Menú del bloque: editar, duplicar, mover, eliminar, envolver, insertar."""
        menu = QMenu(self)
        menu.addAction(
            _t(
                "BLQ.gui.editar_campo",
                campo=_t(f"BLQ.tipo.{self.modelo.buscar(ident).tipo}") if self.modelo else "",
            ),
            lambda: self.editar_campos(ident),
        )
        menu.addAction(_t("BLQ.gui.duplicar"), lambda: self.duplicar(ident))
        menu.addAction(_t("BLQ.gui.mover"), lambda: self.empezar_colocacion(("mover", ident)))
        menu.addAction(_t("BLQ.gui.eliminar"), lambda: self.eliminar(ident))
        sub = menu.addMenu(_t("BLQ.gui.envolver"))
        for t in ("si", "mientras", "hacer_mientras", "para", "para_cada", "intentar"):
            sub.addAction(_t(f"BLQ.tipo.{t}"), lambda t=t: self.envolver(t))
        caja = self.diseno.caja(ident) if self.diseno else None
        punto = self.lienzo.mapFromScene(QPointF(caja.x, caja.y + caja.h)) if caja else None
        menu.popup(
            self.lienzo.viewport().mapToGlobal(punto)
            if punto is not None
            else self.mapToGlobal(self.rect().center())
        )

    def contextMenuEvent(self, event):  # noqa: N802 - API de Qt
        """Clic derecho sobre el lienzo: menú del bloque con foco."""
        if self.foco is not None:
            self.menu_contextual(self.foco)

    # ------------------------------------------------------------ código, archivos, ejecución

    def _codigo(self) -> str | None:
        if self.modelo is None:
            return None
        if self._problemas:
            self.anunciar(_t("BLQ.gui.con_problemas", n=len(self._problemas)))
            return None
        return bloques.codigo_desde_bloques(self.modelo, self.idioma)

    def enviar_codigo(self) -> str | None:
        """Genera el programa y lo manda al editor."""
        codigo = self._codigo()
        if codigo is not None:
            self._ultimo_codigo = codigo
            self.codigo_generado.emit(codigo)
        return codigo

    def _entrada(self) -> tuple[str, ...]:
        texto_entrada = self.entrada.text().strip()
        return tuple(texto_entrada.split()) if texto_entrada else ()

    def ejecutar(self) -> bool:
        """Ejecuta el programa de los bloques y muestra su salida."""
        codigo = self._codigo()
        if codigo is None:
            return False
        r = api.ejecutar(codigo, entrada=self._entrada())
        self.salida.setPlainText(
            "".join(r.salida) if r.ok else "\n".join([_t("BLQ.gui.no_ejecutable"), *r.errores])
        )
        self.anunciar(_t("BLQ.gui.ejecutado") if r.ok else _t("BLQ.gui.no_ejecutable"))
        return r.ok

    def paso_a_paso(self) -> bool:
        """Pide a la ventana visualizar paso a paso el programa de los bloques."""
        codigo = self._codigo()
        if codigo is None:
            return False
        self.trazar_codigo.emit(codigo, self._entrada())
        return True

    def abrir_json(self, ruta: str | None = None) -> bool:
        """Carga un archivo de bloques JSON v1."""
        if ruta is None:
            ruta, _ = QFileDialog.getOpenFileName(
                self, _t("BLQ.gui.abrir"), "", _t("BLQ.gui.filtro_json")
            )
            if not ruta:
                return False
        try:
            with open(ruta, encoding="utf-8") as f:
                modelo = bloques.desde_json(f.read())
        except (OSError, bloques.ErrorBloques) as e:
            QMessageBox.warning(
                self,
                _t("BLQ.gui.titulo"),
                e.texto() if isinstance(e, bloques.ErrorBloques) else str(e),
            )
            return False
        if self.modelo is not None:
            self._deshacer.append(self.modelo)
        self._fijar(modelo)
        return True

    def guardar_json(self, ruta: str | None = None) -> bool:
        """Guarda los bloques en JSON v1."""
        if self.modelo is None:
            return False
        if ruta is None:
            ruta, _ = QFileDialog.getSaveFileName(
                self, _t("BLQ.gui.guardar"), "", _t("BLQ.gui.filtro_json")
            )
            if not ruta:
                return False
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(bloques.a_json(self.modelo))
        except OSError as e:
            QMessageBox.warning(self, _t("BLQ.gui.titulo"), str(e))
            return False
        return True
