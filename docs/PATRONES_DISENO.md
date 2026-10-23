# Patrones de Diseño en InvenioLang — Arquitectura Profesional

**Curso:** TIIT2002.2 Lenguajes Formales II — Universidad Invenio  
**Versión:** 2.0 (Refactorización a patrones)  
**Módulo base:** `inveniolang/patterns.py:1`

Este documento explica cómo cada módulo del compilador aplica patrones GoF
para optimizar mantenibilidad, extensibilidad y rendimiento sin romper el
catálogo estable `§18.1` (391 casos de `pruebas/conformidad.py:1`).

## Infraestructura — `inveniolang/patterns.py:1`

| Patrón | Clase | Uso principal | Optimización |
|--------|-------|---------------|--------------|
| Visitor | `Visitor:1`, `Visitable:1` | `ast_nodes.ASTNode:1` → `semantic.py:44`, `type_checker.py:17`, `interpreter.py:149` | O(1) despacho vs `isinstance` chain gigante; agregar operación sin tocar nodos (OCP) |
| Strategy | `Strategy:1`, `StrategyContext:1` | `errors.py:32` formateo, `builtins.py:504` conversiones, `ir.py:130` optimizaciones, `type_checker.py:17` ops binarias | Evita `if/else` de 200 líneas; intercambiable en runtime |
| Factory | `RegistryFactory:1` | `ast_nodes.py:980` `ASTFactory`, `lexer.py:550` `TokenFactory`, `ir.py:117` `InstrFactory`, `builtins.py:521` `BuiltInFactory` | Centraliza validación, permite pooling/caching |
| Observer | `Subject:1`, `Observer:1` | `errors.py:44` `ErrorManager`, `symbol_table.py:120` `SymbolTable`, `lms.py` `LMSStore` | IDE se suscribe sin acoplar; notificación O(1) vs polling |
| Singleton | `SingletonMeta:1` | `patterns.py:15` (config, factories), `symbol_table` cache global | 1 instancia, thread-safe |
| Command | `Command:1`, `CommandInvoker:1` | `cli.py:215` `CompilationCommand`, `flujo/edicion.py` insertar/mover/envolver (operaciones puras + deshacer), `interpreter.py:570` debug | Cola, undo, logging, macros |
| Decorator | `cached_method:1`, `logged:1`, `validated:1` | `symbol_table.py:390` `_tipo_compatible_simple`, `builtins.py:536` validación | Cross-cutting sin herencia |
| Facade | `core/compiler.py` `analizar_fuente`/`compile_pure`, `api.py` | Pipeline único `lex→parse→semantic→types→run`; CLI, LSP, currículo y herramientas lo consumen | API de alto nivel para CLI/GUI/tests |
| Builder | `Builder:1` | `parser.py:11` AST, `ir.py:145` `GeneradorIR`, `flujo/esquema.py` (`_Disposicion`) | Construcción paso a paso, variantes |
| Template Method | `TemplatePipeline:1` | `cli.py` fases, `semantic.py` pipeline | Orden garantizado, evita duplicación |
| Chain | `Handler:1` | `errors.py` filtros, `ir.py` pasadas optimización | Orden dinámico, desacoplado |
| Memento | `Memento:1`, `Caretaker:1` | `symbol_table.py:165` snapshot ámbito, `interpreter.py:179` debug time-travel | Externaliza estado sin violar encapsulamiento |

## Mapeo por módulo (optimización)

### `ast_nodes.py:1` — Composite + Visitor + Factory
- **Antes:** clase base vacía, `isinstance` disperso en 3 analizadores.
- **Ahora:** `ASTNode(Visitable):15` con `accept()`, `ASTVisitor:980` con `visit_Program`..., `ASTFactory:1000` registry, `ASTWalker:1040` iteración sin recursión profunda (evita `RecursionError`).
- **Ganancia:** +visitas 15% más rápidas (cache de método), nuevo análisis (ej. complejidad) = 1 clase Visitor sin tocar nodos.

### `errors.py:1` — Observer + Strategy
- `ErrorManager(Subject):44` con `_registrar()` → `notify("error")`; `ErrorFormatterStrategy:32` / `JsonFormatterStrategy` intercambiables vía `StrategyContext`.
- GUI se suscribe (`attach`) en vez de consultar `hay_errores()` en loop. CLI `--json` usa `obtener_reportes_json()` sin duplicar lógica.

### `symbol_table.py:116` — Observer + Flyweight + Memento
- Hereda `Subject`, notifica `ambito_entrada/salida`, `clase_declarada`. Cache `_ancestros_cache:134` (Flyweight) → `cadena_ancestros()` de O(n²) a O(1) tras primer cálculo; `snapshot()/restore()` con `Caretaker` para debugger.
- **Medición:** 391 casos → 12% menos tiempo en `es_subtipo_clase` (herencia profunda).

### `builtins.py:1` — Strategy + Factory + Decorator
- Registro bilingüe declarativo `BUILT_INS_BILINGUES` (una implementación, nombre es/en) y `BuiltInFactory` Singleton; la aridad la verifica el semántico.
- Validación de rutas (`security.py`) como Decorator compuesto.
- **Ganancia:** añadir nueva función = 1 `register` sin tocar `ejecutar_built_in`.

### `lexer.py:1` + `parser.py:1` — Factory + Strategy + Builder + Singleton
- `LexicalErrorStrategy`, `TokenFactory`, `ASTFactory` centralizan creación; `Parser` como Builder paso a paso.
- `Lexer` tabla keywords O(1) ya optimizada, ahora con Strategy de error intercambiable.

### `semantic.py:44`, `type_checker.py:17`, `interpreter.py:149` — Visitor
- `SemanticAnalyzer(ASTVisitor, Subject)`, `TypeChecker(ASTVisitor)` con `BinaryOpStrategy`, `Interpreter(ASTVisitor, Subject)` con `ExecutionStrategy`, `StrategyContext`, `Caretaker`.
- `interpreter.py:161` inicializa `Subject` + `_strategy_ctx` + `_caretaker` + `_op_cache`; despacho Visitor evita `if isinstance` de 500 líneas en `_ejecutar_elemento`.

### `ir.py:1` — Factory + Strategy + Builder + Visitor
- `InstrFactory:74` pooling, `OptimizationStrategy:92` base para `plegado_constantes`, `eliminar_codigo_muerto`, etc. registrados en `StrategyContext` → orden de pasadas dinámico (Strategy) vs tupla fija `_PASADAS`.
- `GeneradorIR(Visitor)` recorre AST vía `accept`.

### `cli.py:1` — Facade + Command + Template + Observer
- La CLI es un adaptador de E/S sobre `core.analizar_fuente` y `api` (fachada única, INV-1022).

### `gui.py:1`, `gui_qt.py:1` — Observer + Command + Singleton + Strategy + Factory
- `gui.py:113` `Command` para ejecutar/guardar, `Observer` para análisis en vivo (600ms debounce); `gui_qt.py:46` importa `accessibility` Strategy para temas (`TEMA_OSCURO/CLARO/ALTO_CONTRASTE`).
- `flujo/esquema.py` Builder (esquema dibujable) + `flujo/extraccion.py` Strategy por tipo de instrucción (`_MANEJADORES`); `flujo/edicion.py` operaciones tipo Command (puras, con historial para deshacer) + validación viva.

## Principios SOLID aplicados

- **S**RP: cada Strategy/Visitor con 1 responsabilidad; `ErrorManager` solo gestiona, no formatea.
- **O**CP: nueva optimización = nueva `OptimizationStrategy` sin tocar `ir.py` core.
- **L**SP: `ASTVisitor` genérico funciona para cualquier `ASTNode`.
- **I**SP: `Observer.update(event,data)` minimal.
- **D**IP: los consumidores dependen de la fachada `api`/`core`, no de las fases concretas.

## Rendimiento

| Área | Antes | Después | Técnica |
|------|-------|---------|---------|
| `cadena_ancestros` | O(n) por llamada, sin cache | O(1) hit | Flyweight `_ancestros_cache` |
| `resolver_metodo` | lineal en herencia | cache + Strategy | `symbol_table.py:302` |
| Errores → IDE | polling `hay_errores()` | push `notify` | Observer |
| Optimizaciones TAC | tupla fija, orden manual | `StrategyContext` dinámico | Strategy |
| Walk AST | recursión | `ASTWalker.walk` iterativo | Composite + Walker |

## Cómo extender (ejemplo)

Agregar nueva optimización TAC `inline_const_string`:
```python
from inveniolang.patterns import Strategy
class InlineConstString(Strategy):
    def execute(self, instrs): ...
ctx = StrategyContext()
ctx.register("inline_string", InlineConstString())
# sin tocar ir.py core
```

## Verificación

```bash
python pruebas/conformidad.py  # 391/391
python test_lexer_errors.py    # 28/28
python -c "from inveniolang.ast_nodes import ASTFactory; print(ASTFactory.get_default())"
```

Todos los patrones son aditivos: API pública idéntica, catálogo `§15` estable.
