# Sistema de Tipos — Juicios Formales (v3.0)

``
Γ ⊢ e : T
``

- Γ ⊢ n : int si n literal entero
- Γ ⊢ e1+e2 : int si Γ⊢e1:int ∧ Γ⊢e2:int
- Γ ⊢ e1+e2 : float si uno es float (promocion int→float)
- Γ ⊢ x : T si (x:T)∈Γ
- Γ ⊢ new C(args) : C si C ∈ clases y args : params(C)
- Γ ⊢ null : null compatible con clase (null <: C)
- Γ ⊢ e.m : T si Γ⊢e:C ∧ (m:T)∈C o ancestro
- Γ ⊢ e.m(args) : T si metodo (args:Targs)→T en C
- Γ ⊢ C <: D si C=D o C hereda D (symbol_table.py:275 es_subtipo_clase)
- Γ ⊢ int[] <: int[] invariante; 
ull <: C[] 

**POO (herencia):** Γ ⊢ (Sub) x = new Super() ok si Super <: Sub? No, solo Sub <: Super (upcasting). symbol_table.py:275 ya implementa.

**Preservación:** si Γ ⊢ e:T y  → e' entonces Γ ⊢ e'':T. Testeado con Hypothesis sobre ASTFactory + diferencial interpreter.py vs ir.py:145.

