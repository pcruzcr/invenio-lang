# Manual Docente — InvenioLang

## Flujo de clase (45 min)
1. **Live coding** (10'): `python main.py --cli --check curriculum/es/nivel01/01_hola_mundo.inv`
   — análisis estático completo sin ejecutar (errores `[IL-XXX-NNN]` con contexto).
2. **Razonar el algoritmo** (15'):
   - `python main.py --cli --step --maxpasos 40 programa.inv` — traza con variables y pila.
   - `python main.py --cli --complejidad programa.inv` — cota O(·) por subrutina y su
     porqué (ciclos, ciclos logarítmicos, recursión por resta o por división).
   - `python main.py --cli --efectos programa.inv` — qué subrutinas son puras y cuáles
     imprimen, leen, usan archivos, modifican globales o el arreglo recibido.
   - Añadir `--idioma en` para los informes en inglés.
3. **Entrega** (15'): cada estudiante entrega su `.inv`; el docente evalúa en sandbox
   (subproceso con límite de CPU/memoria) y registra el intento:
   ```
   python -m inveniolang.evaluation evaluar entrega.inv casos.json --store aula.jsonl --actor a01
   python -m inveniolang.evaluation plagio carpeta_entregas/ --umbral 0.7
   ```
   `casos.json` es una lista de `{"entrada": ["5"], "esperado": "25"}`.
4. **Panel** (5'): `python -m inveniolang.lms aula.jsonl` — intentos, códigos de error más
   frecuentes en intentos fallidos y sugerencia de refuerzo.

## Compiladores (Lenguajes Formales II)
- `--tokens`, `--ast`, `--tabla`, `--ir`, `--ir-opt`, `--ssa` (bloques básicos, dominadores y
  forma SSA con φ), `--target`, `--target-reg`.
- `python -m inveniolang.grammar_validator` — FIRST/FOLLOW y tabla LALR(1) reales de
  `parser.py`; falla si aparecen conflictos por encima del baseline documentado (20 s/r, 0 r/r)
  o símbolos sin definir.
- `python -m inveniolang.ll1` — parser LL(1) de descenso recursivo comparado con el LALR(1).
- `--uml [plantuml|mermaid|svg|json|texto]` (y `inveniolang desde-uml diagrama.puml` para generar el esqueleto de un diagrama, ver [uml.md](uml.md)) y `--ver-como python|c|java|csharp|pascal` (vista Rosetta).

## Instalación aula
```
pip install -e .[dev]
docker build -f docker/Dockerfile .   # imagen read-only para ejecutar entregas
python -m inveniolang.lsp             # servidor LSP (stdio) para el editor
```

## Accesibilidad (WCAG AA)
- `accessibility.py` `TEMA_ALTO_CONTRASTE` (7:1) y `validar_tema_accesible`; ver `ACCESSIBILITY.md`.
- Atajos: `Ctrl+Shift+P` paleta, `F8` error, `Ctrl+\`` terminal.

## Soporte
`SECURITY.md` contacto `tic@invenio.ac.cr`; versión única en `inveniolang/_version.py`.
