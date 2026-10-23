# IR: CFG y forma SSA

- `ir.py` — `GeneradorIR`: AST → código de tres direcciones (TAC).
- `cfg.py` — `construir_cfg`: TAC → bloques básicos (líderes: primera instrucción, `label`, instrucción tras un salto; aristas de `goto`, `if_false`, `try_begin`). Los bloques inalcanzables se descartan.
- `ir_ssa.py` — dominadores (punto fijo), dominador inmediato, frontera de dominancia (Cooper–Harvey–Kennedy), inserción de φ podada por liveness y renombrado sobre el árbol de dominadores (Cytron et al.). Parámetros y globales entran como versión `_0`.

Uso: `python main.py --cli --ssa programa.inv` o `api.ssa(codigo)`. Igual que `--ir`, no cubre clases/POO (`NoSoportadoIR`).
