# Accesibilidad — InvenioLang IDE

**Objetivo:** WCAG 2.1 AA para la IDE Qt (y degradación razonable en Tk).

## Estado actual (v2.0)

| Criterio | Implementado | Detalle |
|----------|--------------|---------|
| **Nombres accesibles** | ✅ | `accessibility.py::describir_widget` asigna `AccessibleName/Description` a cada widget interactivo; lectores NVDA/JAWS/Orca anuncian correctamente |
| **Alto contraste** | ✅ | Tema `TEMA_ALTO_CONTRASTE` 7:1 (negro #000 / blanco #fff / amarillo #ff0) — menú Ver → Tema |
| **Escalado de fuente** | ✅ | `Ctrl++`/`Ctrl+-`/`Ctrl+0` (9–24 pt), se persiste en `QSettings`; fuente dislexia-friendly si está instalada |
| **Foco visible** | ✅ | `linea_activa` + borde de gutter; navegación `Tab`/`Shift+Tab` completa |
| **Atajos de teclado** | ✅ | `Ctrl+N/O/S/R/G`, `F1` ayuda, `F8/Shift+F8` navegar errores, `Ctrl+Shift+P` paleta, `Ctrl+\`` terminal |
| **Tooltips** | ✅ | Cada acción con tooltip + atajo |
| **Subrayado de errores** | ✅ | Rojo ondulado (error) / ámbar punteado (advertencia) + lista navegable |
| **Minimapa navegable** | ⚠️ parcial | Clic/arrastre, pero aún sin control por teclado (mejora futura) |
| **Contraste verificado** | ✅ | `accessibility.py::validar_tema_accesible` comprueba 4.5:1 |

## Uso

- **Cambiar tamaño de fuente:** `Ctrl++` / `Ctrl+-` / menú Archivo → Configuración
- **Tema alto contraste:** Ver → Tema → Alto contraste
- **Navegar errores sin mouse:** `F8` / `Shift+F8`, `Enter` salta a la línea
- **Paleta de comandos:** `Ctrl+Shift+P` (búsqueda difusa)

## Verificación

```bash
python -c "from inveniolang.accessibility import validar_tema_accesible, TEMA_ALTO_CONTRASTE; print(validar_tema_accesible(TEMA_ALTO_CONTRASTE))"
# debe imprimir [] (sin advertencias)
```

## Roadmap

- Navegación completa del diagrama de flujo por teclado
- Soporte para Orca en Linux (propiedades `QAccessible::Role`)
- Tema oscuro con contraste verificado AA
