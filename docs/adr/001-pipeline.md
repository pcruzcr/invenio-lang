# ADR 001 — Pipeline Hexagonal

**Estado:** Aceptado (v3.0)
**Contexto:** `cli.py:230` Facade acoplaba IO + lógica.
**Decisión:** `inveniolang/core/` puro (sin IO) + `ports/` (CLI/GUI/LSP) inyectan `ErrorManager`/`SymbolTable`.
**Consecuencia:** Testeable sin FS, LSP reusa core.
