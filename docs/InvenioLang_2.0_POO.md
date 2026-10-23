# InvenioLang 2.0 — Programación Orientada a Objetos

**Curso:** TIIT2002.2 Lenguajes Formales II
**Universidad:** Invenio — Tecnologías de Información y Comunicación Empresarial (TICEC)
**Estado:** especificación de la Etapa 2 (Fase 2), en implementación

## 0. Por qué existe este documento

La especificación de InvenioLang 1.0 declara, en dos lugares distintos, que la
programación orientada a objetos queda **excluida permanentemente** del
lenguaje:

> §1.3 "Alcance": *"Programación orientada a objetos: clases, objetos,
> herencia, polimorfismo o interfaces"* (listada entre las características
> fuera de alcance de la v1.0).
>
> §18.3.3 "Características Explícitamente Excluidas": *"Programación
> orientada a objetos: clases, herencia, polimorfismo. InvenioLang es y
> seguirá siendo un lenguaje de programación estructurada."*

A diferencia de `function`/`funcion` y `procedure`/`procedimiento` — que la
v1.0 sí reserva como palabras "futuras" (Apéndice A) pensando en una v1.1 —
no existe ningún gancho léxico ni de gramática para POO en la v1.0. La
ausencia de herencia es, según la propia §1.3, una decisión deliberada para
evitar la complejidad de una tabla de despacho virtual en el intérprete.

**InvenioLang 2.0 revierte esa decisión de forma deliberada y documentada**,
igual que `docs/ERRATAS.md` documenta las contradicciones de la v1.0: aquí no
hay una contradicción que resolver, sino una extensión consciente del
lenguaje motivada por su uso en cursos de Programación 2, Estructuras de
Datos y Algoritmos. Los 92 códigos de error y los 175 casos de conformidad de
la v1.0 (§18.1: "estables entre versiones") **no se tocan**; todo lo nuevo
vive bajo el prefijo `IL-POO-NNN` y un grupo nuevo en
`pruebas/conformidad.py`.

## 1. Palabras reservadas nuevas

Siete pares bilingües nuevos, siguiendo la misma convención léxica que el
resto del lenguaje (minúsculas, sin tilde):

| Concepto | Inglés | Español |
|---|---|---|
| Declarar clase | `class` | `clase` |
| Herencia | `extends` | `hereda` |
| Instanciar | `new` | `nuevo` |
| Instancia actual | `this` | `este` |
| Superclase | `super` | `padre` |
| Visibilidad pública | `public` | `publico` |
| Visibilidad privada | `private` | `privado` |

Como cualquier palabra reservada del lenguaje, usarlas como identificador
produce `IL-LEX-006` (mecanismo ya existente, sin cambios).

Se agrega además el delimitador `.` (token nuevo, InvenioLang 1.0 no lo
tenía como símbolo independiente — solo aparecía dentro del literal de
`float`).

## 2. Gramática (extensión de §16, forma EBNF simplificada)

```
programa            ::= (declaracion_global | subrutina | class_decl)*  main  (...)*

class_decl           ::= "clase" IDENTIFICADOR ("hereda" IDENTIFICADOR)? "{" miembro_clase* "}"

miembro_clase         ::= visibilidad tipo IDENTIFICADOR ";"                      (* atributo *)
                        | visibilidad tipo IDENTIFICADOR "(" params? ")" bloque   (* metodo *)
                        | IDENTIFICADOR "(" params? ")" bloque                    (* constructor:
                                                                                      mismo nombre
                                                                                      que la clase,
                                                                                      sin tipo *)

visibilidad           ::= "publico" | "privado"

receptor              ::= IDENTIFICADOR | "este" | "padre"
                        | IDENTIFICADOR "[" expresion "]"      (* §8 *)

acceso                ::= receptor "." IDENTIFICADOR
                        | receptor "." IDENTIFICADOR "(" args? ")"
                        | acceso "." IDENTIFICADOR               (* §14, encadenado *)
                        | acceso "." IDENTIFICADOR "(" args? ")"

expr_primaria         ::= ...(formas de la v1.0)...
                        | "nuevo" IDENTIFICADOR "(" args? ")"
                        | acceso
                        | acceso "." IDENTIFICADOR "[" expresion "]"

lvalue                ::= ...(formas de la v1.0)...
                        | receptor "." IDENTIFICADOR
                        | acceso "." IDENTIFICADOR
                        | acceso "." IDENTIFICADOR "[" expresion "]"

instruccion_llamada    ::= ...(formas de la v1.0)...
                        | "padre" "(" args? ")" ";"           (* super(...), solo como
                                                                   primera instruccion de
                                                                   un constructor *)
                        | receptor "." IDENTIFICADOR "(" args? ")" ";"
                        | acceso "." IDENTIFICADOR "(" args? ")" ";"
```

El acceso a miembros fue de **un solo nivel** hasta InvenioLang 10: el
receptor era siempre un identificador simple, `este`, `padre` o un elemento
de arreglo, y había que copiar cada eslabón en una variable local. Desde
InvenioLang 11 (INV-4406) se puede **encadenar**: `a.b.c`, `a.b.c = v`,
`a.b.m()`, `a.m().c`, `este.cola.siguiente` y `a.b.datos[i]`. Las reglas
están en §14. El acceso seguro `?.` (§12.2) sigue siendo de un solo nivel.

## 3. Reglas semánticas

1. **Una clase es un tipo nuevo.** El nombre de una clase declarada es válido
   donde antes solo cabían `int`/`entero`, `float`/`real`, etc.: tipo de
   variable, de parámetro, de retorno de método.
2. **Herencia simple.** Una clase declara a lo sumo un padre con
   `hereda`/`extends`. No hay interfaces ni herencia múltiple. La herencia
   circular (directa o transitiva) es un error (`IL-POO-003`).
3. **Visibilidad.** `publico`/`privado` en cada atributo y método. Un
   miembro privado solo es accesible dentro del cuerpo de la clase que lo
   declara — **ni siquiera una subclase** puede acceder a un privado
   heredado (equivalente a `private` estricto de Java, no `protected`).
   Acceso indebido: `IL-POO-005`.
4. **Constructor.** Método con el mismo nombre que la clase, sin tipo de
   retorno — misma forma sintáctica que ya usa `MainDecl` (`void main()` es
   una producción de gramática dedicada, no genérica; el constructor es
   análogo). Si una clase no declara constructor, se sintetiza uno implícito
   sin parámetros que inicializa cada atributo a su valor por defecto
   (§5.2.3 de la v1.0, sin cambios).
5. **`padre(...)` (super) en el constructor.** Si la primera instrucción del
   constructor de una subclase es `padre(...)`, invoca ese constructor del
   padre con esos argumentos. Si no está presente y la clase tiene padre, se
   inserta implícitamente una llamada a `padre()` sin argumentos (debe
   existir un constructor del padre compatible, si no: `IL-POO-007`/`008`).
   `padre(...)` en cualquier otra posición, en una clase sin padre, o fuera
   de un constructor: `IL-POO-009`/`IL-POO-010`.
6. **`este` (this).** Válido solo dentro del cuerpo de un método o
   constructor; referencia a la instancia actual. Fuera de ese contexto:
   `IL-POO-011`.
7. **Sobrescritura de métodos.** Una subclase puede redeclarar un método con
   el mismo nombre que uno heredado. Debe conservar el mismo tipo de retorno
   (`IL-POO-014`) y la misma lista de tipos de parámetros (`IL-POO-015`) que
   la versión del padre — InvenioLang 2.0 no tiene sobrecarga, así que
   "mismo nombre, distinta firma" es siempre un error, nunca una sobrecarga.
8. **Polimorfismo (despacho virtual).** Toda llamada a método
   (`receptor.metodo(args)`) se resuelve en tiempo de ejecución según el
   tipo dinámico (real) del objeto, no el tipo estático de la variable —
   esto es lo que permite que `Animal a = nuevo Perro(...); a.sonido();`
   ejecute la versión de `Perro`. `padre.metodo(args)` es la única forma de
   invocar explícitamente la implementación del padre, saltándose el
   despacho virtual (para reutilizar lógica desde una sobrescritura).
9. **Compatibilidad de tipos (upcasting).** Una instancia de una subclase es
   asignable a una variable del tipo de cualquier ancestro. La verificación
   de tipos camina la cadena de herencia (nueva regla `es_subtipo`, además
   de la ya existente `int → float`). Asignación entre clases no
   emparentadas: `IL-POO-013`.
10. **Sin:** miembros/atributos estáticos, clases abstractas o interfaces,
   sobrecarga de operadores (`==`/`!=` entre objetos comparan identidad de
   referencia, no contenido), excepciones, arreglos de objetos. Quedan como
   candidatos para incrementos futuros de la hoja de ruta.

## 4. Semántica de ejecución

- **Instanciación (`nuevo Clase(args)`):** se reservan todos los atributos
  de la cadena de herencia (del ancestro más lejano al más cercano) con su
  valor por defecto, y luego se ejecuta la cadena de constructores (padre
  antes que hijo, vía `padre(...)` explícito o implícito).
- **Paso por referencia:** igual que los arreglos (§12.2 de la v1.0), una
  variable de tipo clase contiene una referencia al objeto — asignarla o
  pasarla como argumento no copia el objeto.
- **`imprimir(objeto)`:** imprime `NombreClase(campo1=valor1, campo2=valor2, ...)`
  con los atributos en orden de declaración (incluye los heredados, del
  ancestro al descendiente) — utilidad de depuración para que el estudiante
  pueda inspeccionar objetos, no parte formal de los cuatro pilares.

## 5. Catálogo de errores `IL-POO-NNN`

| Código | Condición |
|---|---|
| `IL-POO-001` | Nombre de clase ya declarado (duplicado) |
| `IL-POO-002` | `hereda`/`extends` de un nombre que no es una clase declarada |
| `IL-POO-003` | Herencia circular (directa o transitiva) |
| `IL-POO-004` | Atributo o método duplicado dentro de la misma clase |
| `IL-POO-005` | Acceso a un atributo o método `privado` desde fuera de la clase que lo declara |
| `IL-POO-006` | Miembro (atributo o método) inexistente en la clase ni en sus ancestros |
| `IL-POO-007` | Llamada a constructor (`nuevo`/`padre(...)`) con número de argumentos incorrecto |
| `IL-POO-008` | Llamada a constructor con tipo de argumento incompatible |
| `IL-POO-009` | `padre(...)` (super) usado fuera de la primera instrucción de un constructor |
| `IL-POO-010` | `padre(...)` usado en una clase sin clase padre |
| `IL-POO-011` | `este`/`this` usado fuera de un método o constructor |
| `IL-POO-012` | `padre.metodo(...)` usado en una clase sin clase padre, o el método no existe en el padre |
| `IL-POO-013` | Asignación/paso de argumento entre tipos de clase no emparentados |
| `IL-POO-014` | Sobrescritura de método con tipo de retorno distinto al del padre |
| `IL-POO-015` | Sobrescritura de método con parámetros de tipo distinto a los del padre |
| `IL-POO-016` | `nuevo` de un nombre que no es una clase declarada |
| `IL-POO-017` | Llamada a método con número de argumentos incorrecto |
| `IL-POO-018` | Llamada a método con tipo de argumento incompatible |
| `IL-POO-019` | El constructor no se llama igual que la clase, o hay más de un constructor |

Todos se reportan vía un nuevo método `ErrorManager.error_poo(codigo,
mensaje, linea, columna)`, mismo patrón y formato oficial
(`[CODIGO] archivo:linea:columna — mensaje`) que las demás categorías.

## 6. Programa de referencia

```
clase Animal {
    privado texto nombre;
    publico entero edad;

    Animal(texto n, entero e) {
        this.nombre = n;
        this.edad = e;
    }

    publico texto obtener_nombre() {
        return this.nombre;
    }

    publico texto sonido() {
        return "...";
    }
}

clase Perro hereda Animal {
    Perro(texto n, entero e) {
        super(n, e);
    }

    publico texto sonido() {
        return "Guau";
    }
}

void main() {
    Animal a = nuevo Perro("Rex", 3);
    imprimir(a.sonido());          // "Guau" -- despacho virtual
    imprimir(a.obtener_nombre());  // "Rex" -- heredado sin sobrescribir
}
```

Salida esperada:

```
Guau
Rex
```

Este programa (y una variante con acceso indebido a `privado` que debe
producir `IL-POO-005`) forma parte del grupo `clases` de
`pruebas/conformidad.py`.

## 7. Referencia nula (`nulo` / `null`)

Añadida junto con los arreglos de objetos (Estructuras de Datos) porque una
estructura enlazada (lista, pila, cola, árbol) no puede detectar su propio
final sin ella. `nulo`/`null` representa la ausencia de objeto:

- Es válido en cualquier posición donde se espere un tipo de clase:
  inicializador, asignación, argumento, comparación `==`/`!=`.
- **Nunca** es compatible con un tipo primitivo (`5 == nulo` es
  `IL-TIPO-012`, igual que comparar tipos incompatibles cualesquiera).
- Un atributo o variable de tipo clase que nunca recibió una instancia vale
  `nulo` — **no** es un error leerlo (a diferencia de una variable de tipo
  primitivo sin inicializar, que sigue siendo `IL-EJE-010`, sin cambios).
  El error solo ocurre al intentar *usar* la referencia nula: acceder a un
  atributo o invocar un método sobre ella produce `IL-EJE-010`
  ("referencia nula o no inicializada"), igual que sobre cualquier
  variable no asignada.
- Este es el patrón esperado para recorrer una estructura enlazada:

```
Nodo actual = cabeza;
mientras (actual != nulo) {
    imprimir(entero_a_texto(actual.valor));
    actual = actual.siguiente;
}
```

## 8. Arreglos de objetos

Un nombre de clase es válido como tipo base de un arreglo
(`Persona[10] personas;`), con dos restricciones deliberadas frente a los
arreglos de tipo primitivo:

- **Solo declaración postfija**: `Clase nombre[tam];` /
  `Clase nombre[tam] = { nuevo A(...), nuevo B(...) };`. La forma prefija
  (`Clase[tam] nombre;`) **no existe** para tipos de clase: como un nombre
  de clase es sintácticamente un `IDENTIFICADOR` igual que una variable,
  `Clase[tam] nombre;` colisionaría letra por letra con una asignación a
  elemento de arreglo ya existente (`arr[i] = x;`, que también arranca
  `IDENTIFICADOR '['`) — un conflicto reduce/reduce en la gramática LALR(1)
  que se evita por completo no ofreciendo esa alternativa. La postfija
  (`Clase nombre[tam]`) no tiene ese problema porque empieza con **dos**
  identificadores antes del corchete. A diferencia del postfijo de
  primitivos (`int arr[5];`), aquí no se emite `IL-WARN-040`: no existe una
  forma canónica alternativa de la cual desviarse, la postfija simplemente
  es la única.
- **Parámetros** (`Clase[] nombre`) sí admiten la misma forma que los
  primitivos — dentro de una lista de parámetros no hay asignaciones con
  las que colisionar. Se pasan por referencia, igual que cualquier arreglo
  (§12.2 de la v1.0).
- **Acceso a miembro sobre un elemento de arreglo**
  (`personas[i].saludar()`, `personas[i].edad = 30`) es válido: el
  receptor de un acceso a miembro ahora también puede ser
  `IDENTIFICADOR '[' expresion ']'`, además de `IDENTIFICADOR`/`este`/
  `padre` (§2). Desde InvenioLang 11 se puede seguir encadenando
  después del método/atributo (`personas[i].mascota.nombre`, §14).
- **Fuera de alcance**: arreglos de matrices de objetos
  (`Clase[f][c] nombre`).

## 9. Etapa 7 — POO completo

Cuatro características que completan los "cuatro pilares" con lo que un
curso real de Programación 2 espera después de la introducción a POO
(Etapa 2): abstracción real (clases/métodos abstractos), miembros de
clase (estáticos), sobrecarga de métodos y genéricos. Todo es **aditivo**
sobre la Etapa 2/3/6 — cero cambios a lo ya construido.

### 9.1 Palabras reservadas nuevas

| Concepto | Inglés | Español |
|---|---|---|
| Clase/método abstracto | `abstract` | `abstracta` (clase) / `abstracto` (método) |
| Miembro estático | `static` | `estatico` |

(`abstracta`/`abstracto` son la misma palabra reservada internamente —
solo cambia la concordancia de género según se use en una clase o un
método; ambas formas, más `abstract`, son intercambiables.)

### 9.2 Clases y métodos abstractos

```
[abstracta] clase Nombre [hereda Padre] { miembro* }
visibilidad abstracto tipo_retorno nombre(params);   // método SIN cuerpo
```

- Una clase `abstracta` **no es instanciable** (`nuevo` sobre ella es
  `IL-POO-020`).
- Un método `abstracto` no lleva cuerpo (termina en `;`) y solo puede
  declararse dentro de una clase `abstracta` (`IL-POO-024`); un método
  abstracto con cuerpo, o uno no marcado abstracto sin cuerpo, es
  `IL-POO-022`.
- Una subclase **concreta** (no abstracta) debe implementar (dar cuerpo
  a) todo método abstracto heredado que no esté ya implementado en algún
  nivel intermedio de la jerarquía — si no, `IL-POO-021`. Una clase
  abstracta puede dejar métodos heredados sin implementar (los pasa hacia
  abajo).
- No existe una palabra `interfaz`/`interface` separada: una "interfaz" es
  simplemente una clase abstracta donde todos los métodos son abstractos
  — se documenta esta decisión explícitamente en vez de duplicar
  gramática para un concepto que ya se puede expresar con lo que existe.
- **Limitación documentada**: el análisis de "toda ruta retorna"
  (`IL-SEM-050`, §10.4 v1.0) no reconoce un `switch` exhaustivo como
  cierre de ruta (ya documentado en la Etapa 6) — igual de relevante aquí
  cuando un método concreto despacha por tipo con un `switch`.

### 9.3 Miembros estáticos

```
visibilidad estatico tipo nombre [= expr];              // atributo de clase
visibilidad estatico tipo_retorno nombre(params) { }     // metodo de clase
```

- Un atributo `estatico` vive en la **clase**, no en cada instancia: una
  sola copia compartida, inicializada una vez al arrancar el programa (o
  con su valor por defecto si no tiene inicializador — mismas reglas de
  §5.2.3 v1.0).
- Acceso: `NombreClase.miembro` — reutiliza la gramática de acceso a
  miembro ya existente (`receptor '.' IDENT`); la ambigüedad entre "es un
  nombre de clase" y "es una variable" se resuelve en `semantic.py`, no en
  la gramática (si el identificador coincide con una clase declarada y no
  hay una variable con ese nombre visible en el ámbito actual, es acceso
  estático) — **sin riesgo de gramática nueva**.
- Acceder a un miembro estático a través de una **instancia**
  (`objeto.estatico`) también es válido (permisivo, igual criterio que
  otros lenguajes) — misma copia compartida. Al revés — acceder a un
  miembro de **instancia** a través del **nombre de la clase**
  (`NombreClase.instancia_attr`) — no tiene sentido (no hay una instancia
  particular) y es `IL-POO-026`.
- `este`/`this` y `padre`/`super` no pueden usarse dentro de un método
  estático (no hay instancia) — `IL-POO-025`.
- Un atributo estático heredado es la **misma** copia compartida para
  toda la jerarquía (`A.total` y `B.total`, con `B hereda A`, son el mismo
  valor).

### 9.4 Sobrecarga de métodos

```
clase C {
    publico entero f(entero x) { ... }
    publico entero f(entero x, entero y) { ... }   // sobrecarga: distinta aridad
    publico texto f(texto x) { ... }                // sobrecarga: distinto tipo
}
```

- Varios métodos con el **mismo nombre** y **distinta firma** (aridad y/o
  tipos de parámetros) conviven en la misma clase. La misma firma exacta
  repetida sigue siendo `IL-POO-004` (duplicado, no sobrecarga).
- La sobrecarga aplicable en cada llamada se elige por los tipos de los
  argumentos: coincidencia **exacta** primero; si no hay ninguna exacta,
  una coincidencia **compatible** por promoción `int→float` o upcasting de
  clases. Si ninguna sobrecarga coincide (o hay más de una igual de
  buena), `IL-POO-027`.
- La sobrecarga se resuelve **solo dentro de la clase que primero
  declara ese nombre** en la cadena de herencia: una subclase que
  redeclara el nombre no hereda además las sobrecargas del padre (mismo
  criterio que ya regía la sobrescritura simple antes de esta etapa).
- **Sobrecarga y sobrescritura (polimorfismo) conviven sin conflicto**:
  la sobrecarga se resuelve por firma en tiempo de **compilación**
  (`type_checker.py`, según los tipos estáticos de los argumentos); la
  sobrescritura/despacho virtual se resuelve por la clase **real** del
  objeto en tiempo de **ejecución** (`interpreter.py`) — son dos ejes
  independientes. `IL-POO-014`/`IL-POO-015` (sobrescritura con tipo de
  retorno o parámetros distintos al padre) ahora solo se compara **firma
  contra firma**: una firma nueva que no coincide con ninguna del padre ya
  no es un error — es sencillamente una sobrecarga nueva, no un intento
  de sobrescritura roto.

### 9.5 Genéricos

```
clase Caja<T> {
    privado T contenido;
    publico void guardar(T valor) { this.contenido = valor; }
    publico T obtener() { return this.contenido; }
}
void main() {
    Caja<entero> cajaNum = nuevo Caja<entero>();
    Caja<texto> cajaTxt = nuevo Caja<texto>();
}
```

**Diseño**: sustitución sintáctica en tiempo de compilación (al estilo de
cómo C++ expande templates), **no** un sistema de tipos genérico real con
inferencia — la opción de menor riesgo dado el sistema de tipos simple de
InvenioLang, y suficiente para el propósito pedagógico. Antes de
cualquier otra validación (`SemanticAnalyzer._expandir_genericos`), cada
uso de `Pila<entero>` en el programa genera una copia **especializada**
de la clase genérica con el parámetro de tipo (`T`) sustituido por
`entero` en todo el cuerpo, registrada como una clase normal más bajo el
nombre interno `"Pila<entero>"` (nunca colisiona con un identificador real
— la sintaxis de InvenioLang no admite `<`/`>` en un nombre). El resto del
compilador (este mismo analizador, `type_checker.py`, `interpreter.py`)
nunca ve una clase genérica sin especializar.

- **Un solo parámetro de tipo** por clase (no `Mapa<K,V>`).
- La sintaxis `Nombre<Arg>` (con `Arg` un tipo primitivo o el nombre de
  otra clase) solo es válida en **dos posiciones**: declaración de
  variable y `nuevo`. *Dentro* del cuerpo de la clase genérica, `T` se usa
  como cualquier otro nombre de tipo (atributo, parámetro, tipo de
  retorno) — eso **no** necesita gramática nueva, porque un nombre de
  clase ya es sintácticamente indistinguible de cualquier `IDENTIFICADOR`.
- **Fuera de alcance** (documentado, no un descuido): genéricos con más de
  un parámetro de tipo; `Nombre<Arg>` en atributos/parámetros/tipos de
  retorno (solo en variable/`nuevo`); genéricos anidados o
  auto-referenciados (p. ej. un nodo enlazado genérico, que necesitaría
  `Nodo<T> siguiente;` como atributo); herencia combinada con genéricos.
- Una clase genérica **nunca instanciada** en el programa no se valida en
  absoluto — no genera ninguna especialización, así que su cuerpo (aunque
  tenga errores) simplemente no se analiza, igual que un template de C++
  nunca instanciado.
- Usar el nombre de la plantilla **sin** especializar (`Caja` en vez de
  `Caja<entero>`) es `IL-POO-016` ("no es una clase declarada") — la
  plantilla en sí nunca queda registrada como clase utilizable.
- El backend de código intermedio (`inveniolang/ir.py`, `--run-ir`) sigue
  excluyendo POO por completo (`ast.clases` no vacío ⇒ `NoSoportadoIR`) —
  una clase genérica especializada es una clase más a todos los efectos,
  así que cae en el mismo rechazo sin necesitar un caso especial.

### 9.6 Catálogo de errores — nuevos códigos `IL-POO-NNN`

| Código | Condición |
|---|---|
| `IL-POO-020` | `nuevo` sobre una clase `abstracta` |
| `IL-POO-021` | Clase concreta no implementa un método abstracto heredado |
| `IL-POO-022` | Método `abstracto` con cuerpo, o método sin cuerpo no marcado `abstracto` |
| `IL-POO-023` | Modificador `abstracto` usado en un atributo (solo válido en métodos) |
| `IL-POO-024` | Método `abstracto` declarado fuera de una clase `abstracta` |
| `IL-POO-025` | `este`/`this` o `padre`/`super` usado dentro de un método `estatico` |
| `IL-POO-026` | Acceso a un miembro de instancia (no estático) a través del nombre de la clase |
| `IL-POO-027` | Ninguna sobrecarga de un método coincide con los tipos de los argumentos (o hay ambigüedad) |

### 9.7 Programa de referencia

Ver [`pruebas/poo_completo.inv`](../pruebas/poo_completo.inv): combina una
jerarquía abstracta (`Figura` → `Circulo`/`Cuadrado`) con contador estático
de instancias, una clase `Sumador` con un método sobrecargado tres veces,
y una `Caja<T>` genérica instanciada con `entero` y `texto` en el mismo
programa.

## 10. Etapa 10 — Cierre de brechas de Fase 1/Fase 2

Un análisis de completitud de Fase 1 y Fase 2 (con las Etapas 1-9 ya
construidas) encontró dos huecos genuinos en POO: la Etapa 7 agregó
sobrecarga de **métodos** pero dejó el constructor con un límite artificial
de uno solo por clase, y no existía forma de que una clase controlara cómo
se representa a sí misma en `imprimir(objeto)`. Esta etapa los cierra —
aditiva sobre la Etapa 2/7, cero cambios de gramática (la gramática de
`lista_miembros_clase` ya aceptaba varios `ConstructorDecl`; solo la
validación semántica colapsaba a uno).

### 10.1 Sobrecarga de constructores

```
clase C {
    C() { ... }                    // constructor sin argumentos
    C(entero x) { ... }             // sobrecarga por aridad
    C(entero x, entero y) { ... }   // sobrecarga por aridad
    C(texto s) { ... }              // sobrecarga por tipo
}
```

- Mismo mecanismo que la sobrecarga de métodos (§9.4): la firma que
  coincide con los argumentos de `nuevo C(...)` se resuelve por tipos —
  exacta primero, si no compatible por promoción `int→float`/upcasting.
  Dos constructores con la **misma** firma exacta son `IL-POO-019`
  (mismo código que "el constructor debe llamarse igual que la clase",
  ampliado — ambos son problemas de declaración de constructor).
- **A diferencia de los métodos, los constructores NUNCA se heredan**: una
  subclase no hereda los constructores del padre — ya era así con un solo
  constructor (`padre(...)`/`super(...)` siempre fue una llamada
  explícita, nunca automática salvo el caso de 0 argumentos).
- `padre(...)` (o el `padre()` implícito cuando el constructor de la
  subclase no lo llama explícitamente) también resuelve la sobrecarga
  correcta del constructor del padre por los tipos de los argumentos
  pasados. Si el padre declara constructores pero **ninguno** de 0
  argumentos, y la subclase no llama a `padre(...)` explícitamente, es
  `IL-POO-007` (igual que antes, ahora consciente de sobrecarga).
- Si ninguna sobrecarga del constructor coincide con los tipos de los
  argumentos (o hay ambigüedad), `IL-POO-029` — mismo criterio que
  `IL-POO-027` para métodos.

### 10.2 `imprimir(objeto)` personalizable — `aTexto()` / `toString()`

Por defecto, `imprimir(objeto)` sigue usando el formato automático de la
Etapa 2 (`NombreClase(campo1=valor1, campo2=valor2, ...)`). Si la clase
(o algún ancestro) declara **públicamente** un método sin parámetros que
retorna `texto`, llamado `aTexto()` (español) o `toString()` (alias en
inglés, mismo criterio bilingüe que el resto del lenguaje), `imprimir`
usa esa representación en su lugar:

```
clase Punto {
    publico entero x; publico entero y;
    Punto(entero a, entero b) { this.x = a; this.y = b; }
    publico texto aTexto() {
        return "(" + entero_a_texto(this.x) + ", " + entero_a_texto(this.y) + ")";
    }
}
void main() {
    Punto p = nuevo Punto(3, 4);
    imprimir(p);   // "(3, 4)", no "Punto(x=3, y=4)"
}
```

- Sigue el despacho **virtual** de siempre: si `aTexto()`/`toString()` está
  sobrescrito en una subclase, `imprimir` sobre una variable declarada del
  tipo padre usa la versión de la clase real de la instancia (igual que
  cualquier otro método, §3 de este documento).
- Solo cuenta un método público, sin parámetros, que retorne `texto` — un
  método con ese nombre pero otra firma (por ejemplo, sobrecargado con
  parámetros) no activa esta convención; `imprimir` sigue usando el
  formato automático.
- No es una palabra reservada ni una entrada nueva en la gramática: es
  pura convención de nombre, resuelta en `interpreter.py` con la misma
  tabla de símbolos que ya resuelve cualquier otra llamada a método.

### 10.3 Librería estándar: entrada/salida de archivos y `invertir_texto`

Ver [`docs/InvenioLang_Etapa6_Estructurado.md`](InvenioLang_Etapa6_Estructurado.md)
§6 para el resto de la librería estándar (cadenas/matemática, Etapa 6).
Nuevo en esta etapa, mismo patrón bilingüe canónico-español + alias-inglés:

| Español | Inglés | Firma | Descripción |
|---|---|---|---|
| `existe_archivo` | `file_exists` | `(string) -> bool` | Si la ruta existe y es un archivo |
| `leer_archivo` | `read_file` | `(string) -> string` | Contenido completo como texto (`IL-EST-015` si falla) |
| `escribir_archivo` | `write_file` | `(string, string) -> bool` | Reemplaza el archivo (`IL-EST-016` si falla) |
| `agregar_archivo` | `append_file` | `(string, string) -> bool` | Agrega al final (`IL-EST-017` si falla) |
| `invertir_texto` | `reverse_string` | `(string) -> string` | Cadena invertida |

Alcance deliberadamente simple: texto plano completo por llamada (sin
lectura línea a línea ni un tipo "manejador de archivo" nuevo), UTF-8
siempre. Ver [`pruebas/archivo_io.inv`](../pruebas/archivo_io.inv).

### 10.4 Catálogo de errores — nuevos códigos

| Código | Condición |
|---|---|
| `IL-POO-019` | (ampliado) Constructor con nombre distinto al de la clase, **o** dos constructores con la misma firma exacta |
| `IL-POO-029` | Ninguna sobrecarga de un constructor coincide con los tipos de los argumentos (o hay ambigüedad) |
| `IL-EST-015` | `leer_archivo`: no se pudo leer (no existe, permisos, no es UTF-8 válido) |
| `IL-EST-016` | `escribir_archivo`: no se pudo escribir |
| `IL-EST-017` | `agregar_archivo`: no se pudo escribir |

### 10.5 Programas de referencia

- [`pruebas/poo_extendido.inv`](../pruebas/poo_extendido.inv): combina
  sobrecarga de constructores (`Punto` con 3 constructores) y `aTexto()`
  con despacho virtual (`Figura`/`Circulo`).
- [`pruebas/monticulo.inv`](../pruebas/monticulo.inv): montículo binario
  mínimo (min-heap) con arreglo, usado como cola de prioridad.
- [`pruebas/heapsort.inv`](../pruebas/heapsort.inv): ordenamiento por
  montículo, mismo caso de prueba que insertion/selection/quick/mergesort
  (Etapa 8) para comparar los cinco algoritmos.
- [`pruebas/archivo_io.inv`](../pruebas/archivo_io.inv): las cuatro
  funciones de archivo, incluyendo el manejo de un error de lectura con
  `intentar`/`capturar` (Etapa 6).
programa. Forma parte del grupo `poo_completo` de `pruebas/conformidad.py`.

## 11. Etapa 11 — Patrones de diseño y mejoras finales de Fase 2

Un segundo análisis de completitud de Fase 1 y Fase 2 (con las Etapas 1-10
ya construidas) encontró huecos reales que no ameritaban una fase nueva
(la Fase 3 propuesta — herramientas gráficas separadas — fue descartada
explícitamente por el usuario): sin visibilidad de constructor (bloqueando
Singleton correcto), sin convención de igualdad personalizable, cero
programas de referencia de patrones de diseño, sin algoritmos de grafos con
peso, sin backtracking/programación dinámica, sin lista doblemente
enlazada/deque, sin árbol AVL, sin enumeraciones, sin operadores bit a bit,
sin arreglos constantes. Todo aditivo sobre las Etapas 2/6/7/10 — cada
cambio de gramática se verificó contra el baseline de conflictos LALR(1)
(20 shift/reduce, 0 reduce/reduce) antes de darse por bueno.

### 11.1 Visibilidad de constructores (`publico`/`privado`)

```
clase Config {
    publico estatico Config instancia;
    privado constructor Config() { ... }   // solo invocable desde la propia clase
    publico estatico Config obtenerInstancia() {
        si (Config.instancia == nulo) { Config.instancia = nuevo Config(); }
        return Config.instancia;
    }
}
```

- Nueva palabra reservada `constructor` (misma grafía en español/inglés),
  requerida cuando el constructor lleva visibilidad explícita:
  `visibilidad KW_CONSTRUCTOR IDENTIFICADOR(...)`. Es un punto de
  desambiguación deliberado — sin él, `publico Clase nombre(...)` (un
  constructor con visibilidad) y `publico Clase atributo;` (un atributo de
  tipo clase con visibilidad) comparten el mismo prefijo
  `visibilidad IDENTIFICADOR` y producen un conflicto shift/reduce real en
  LALR(1) que PLY resuelve mal (rompe el atributo). El constructor **sin**
  visibilidad explícita (forma preexistente, `Clase(...)`) sigue siendo
  público implícito y no requiere la palabra `constructor`.
- Un constructor `privado` solo puede invocarse desde dentro de la propia
  clase que lo declara: `nuevo Clase(...)` externo, `padre(...)` explícito
  desde una subclase, y el `padre()` implícito de 0 argumentos insertado al
  inicio de un constructor de subclase, los tres se rechazan igual
  (`IL-POO-030`) si el constructor del padre es privado.
- Habilita el patrón **Singleton** de verdad (constructor privado + método
  de fábrica estático) — antes cualquier código externo podía instanciar la
  clase directamente sin que hubiera forma de impedirlo.

### 11.2 `esIgual()`/`equals()` personalizable

Mismo mecanismo bilingüe por convención de nombre que `aTexto()`/
`toString()` (§10.2): si la clase declara públicamente un método con
exactamente un parámetro (del tipo de la propia clase o compatible) que
retorna `bool`, llamado `esIgual()` o `equals()`, los operadores `==`/`!=`
entre dos instancias lo invocan en vez de comparar por identidad de
referencia:

```
clase Punto {
    publico entero x; publico entero y;
    Punto(entero a, entero b) { this.x = a; this.y = b; }
    publico bool esIgual(Punto otro) { return this.x == otro.x && this.y == otro.y; }
}
void main() {
    Punto p1 = nuevo Punto(1, 2); Punto p2 = nuevo Punto(1, 2);
    imprimir(p1 == p2);   // true -- por valor, no por identidad
}
```

- Solo se activa entre dos valores que son **ambos** `InstanciaObjeto`;
  comparar un objeto contra `nulo` sigue siendo el chequeo de nulidad
  seguro de siempre y nunca invoca `esIgual()` (evita ejecutar código de
  usuario, y una posible excepción por acceso a miembro nulo, al hacer un
  simple `if (obj != nulo)`).
- Sin `esIgual()`/`equals()` declarado, `==`/`!=` entre objetos siguen
  siendo identidad de referencia, comportamiento de la Etapa 2 sin cambios.
- No es palabra reservada ni gramática nueva — se resuelve en
  `interpreter.py` con la misma tabla de símbolos que ya resuelve cualquier
  llamada a método.

### 11.3 Patrones de diseño — programas de referencia

Sin mecanismo de lenguaje nuevo: los cinco patrones clásicos ya eran
expresables con las Etapas 2/7/11.1 (clases, herencia, polimorfismo,
miembros estáticos, visibilidad de constructor). Programas de referencia:
[`pruebas/patron_singleton.inv`](../pruebas/patron_singleton.inv),
[`patron_factory.inv`](../pruebas/patron_factory.inv),
[`patron_observer.inv`](../pruebas/patron_observer.inv) (lista enlazada de
observadores — los atributos de tipo arreglo siguen sin soportarse, §8),
[`patron_strategy.inv`](../pruebas/patron_strategy.inv),
[`patron_decorator.inv`](../pruebas/patron_decorator.inv). `strategy` y
`decorator` se escribieron cuando el acceso a miembro era de un solo nivel
y resuelven `this.estrategia.calcular(...)` con una variable local intermedia
(`Estrategia e = this.estrategia; return e.calcular(...);`); desde
InvenioLang 11 la forma directa también es válida (§14).

### 11.4 Algoritmos de grafos con peso y MST

Sin objetos, sobre las estructuras de la Etapa 8 (matriz/lista de
adyacencia): [`pruebas/dijkstra.inv`](../pruebas/dijkstra.inv) (camino más
corto desde un origen), [`kruskal.inv`](../pruebas/kruskal.inv) (árbol de
expansión mínima con Union-Find; el nombre clásico `padre[]` para el
arreglo de representantes choca con la palabra reservada `padre` —
español de `super` — y se renombró `parentesco[]`),
[`orden_topologico.inv`](../pruebas/orden_topologico.inv) (algoritmo de
Kahn).

### 11.5 Backtracking y programación dinámica

[`pruebas/n_reinas.inv`](../pruebas/n_reinas.inv),
[`permutaciones.inv`](../pruebas/permutaciones.inv),
[`fibonacci_memo.inv`](../pruebas/fibonacci_memo.inv),
[`mochila.inv`](../pruebas/mochila.inv) (0/1 knapsack). `mochila.inv`
ilustra que las dimensiones de arreglo/matriz solo aceptan un literal o un
identificador `const` (§12.4 de la spec v1.0), nunca una expresión general
(`int [N + 1] tabla;` no se parsea) — se declararon constantes con el
tamaño ya calculado (`const int FILAS = 5;`) en vez de una expresión.

### 11.6 Lista doblemente enlazada y deque

[`pruebas/lista_doble.inv`](../pruebas/lista_doble.inv) (nodo con
`anterior`/`siguiente`, recorrido en ambos sentidos),
[`deque.inv`](../pruebas/deque.inv) (inserción/remoción en ambos extremos
sobre la lista doble).

### 11.7 Árbol AVL

[`pruebas/arbol_avl.inv`](../pruebas/arbol_avl.inv): árbol binario de
búsqueda auto-balanceado con las cuatro rotaciones (izquierda, derecha,
izquierda-derecha, derecha-izquierda) y factor de balance recalculado tras
cada inserción. Se escribió antes del acceso encadenado y resuelve
`n.izquierda.valor` con una variable local intermedia; desde InvenioLang 11
`n.izquierda.valor` es válido directamente (§14).

### 11.8 Enumeraciones (`enum`/`enumeracion`)

```
enum DiaSemana { LUNES, MARTES, MIERCOLES, JUEVES, VIERNES, SABADO, DOMINGO }
void main() {
    DiaSemana hoy = DiaSemana.SABADO;
    imprimir(hoy == DiaSemana.SABADO);   // true
}
```

- Nueva gramática (`elemento_programa`): `enum IDENTIFICADOR { lista_ident }`
  — palabra de apertura única (`enum`/`enumeracion`), sin ambigüedad con
  nada existente, cero conflictos LALR nuevos.
- Implementado como **azúcar sintáctica** sobre el mecanismo de clases ya
  existente en vez de un tipo nativo nuevo: cada `enum` se registra
  internamente como una `ClaseInfo` marcada `es_enum=True`, con un miembro
  estático público por valor (`LUNES`, `MARTES`, ...) inicializado a su
  posición ordinal (0, 1, 2, ...) — reutiliza `NombreEnum.MIEMBRO`, la
  misma resolución de acceso estático de la Etapa 7 (§9.2).
- **Nominalmente tipado**, deliberadamente NO compatible de forma implícita
  con `int` (a diferencia de C): `DiaSemana.LUNES == 0` es `IL-TIPO-012`
  (tipos incompatibles), igual que comparar dos clases sin relación de
  herencia. Los valores ordinales existen para el layout interno, no para
  aritmética directa del usuario.
- `nuevo NombreEnum()` se rechaza (`IL-POO-032`): un enum no es
  instanciable. Un miembro duplicado dentro del mismo `enum` es
  `IL-POO-031`.
- Ver [`pruebas/enumeraciones.inv`](../pruebas/enumeraciones.inv) (dos
  enums, uno usado como tipo de atributo de clase).

### 11.9 Operadores bit a bit

Nuevos tokens/operadores `&` (and), `|` (or), `^` (xor), `~` (not unario),
`<<` (desplazamiento izquierda), `>>` (desplazamiento derecha), todos
exclusivos de `int` — mismo código `IL-TIPO-010` (operando de tipo
incorrecto) que el resto de operadores aritméticos si se usan con `real`,
`texto` o `bool`.

- Precedencia clásica de C, insertada en la cadena explícita de descenso
  recursivo del parser: `expr_or → expr_and → expr_bitor → expr_bitxor →
  expr_bitand → expr_igual → expr_rel → expr_shift → expr_sum → expr_mul →
  expr_unaria`. Cero conflictos LALR nuevos (extensión puramente aditiva de
  una cadena ya no ambigua) — a diferencia de §11.1, aquí no hizo falta
  ningún punto de desambiguación.
- `&&`/`||` (lógicos) siguen sin colisionar con `&`/`|` (bit a bit): PLY
  ordena las reglas de patrón simple por longitud de expresión regular
  decreciente, así que el patrón de dos caracteres siempre gana. Lo mismo
  protege `<<`/`>>` frente a los ya existentes `<`/`>` — se verificó que
  `Cola<entero>` (genéricos, §9.5) sigue analizando correctamente después
  del cambio.
- El resultado de cualquier operador bit a bit pasa por la misma
  verificación de rango de 32 bits que el resto de la aritmética entera
  (`IL-EJE-001` si se desborda) — en la práctica solo `<<` puede
  desbordar.
- Ver [`pruebas/bit_a_bit.inv`](../pruebas/bit_a_bit.inv) (banderas de
  permisos con máscaras de bits).

### 11.10 `const` sobre arreglos

```
const int [3] DIAS_LABORALES = { 5, 6, 7 };
void main() {
    imprimir(DIAS_LABORALES[0]);   // 5, lectura normal
    DIAS_LABORALES[0] = 10;        // IL-SEM-031
}
```

- Nueva gramática: `const tipo [tam] IDENTIFICADOR = { lista_expr_init };`
  — el arreglo completo debe inicializarse en la propia declaración (mismo
  criterio que una constante escalar, §5 de la spec v1.0). Cero conflictos
  LALR nuevos.
- Reasignar **cualquier elemento** del arreglo (`DIAS_LABORALES[0] = 10;`)
  reutiliza `IL-SEM-031` — el mismo código que ya existía para reasignar
  una constante escalar, en vez de un código nuevo, siguiendo el mismo
  criterio de reuso de §10.1/§10.2. Leer elementos (`DIAS_LABORALES[i]`)
  no tiene restricción, igual que un arreglo normal.
- Un arreglo declarado sin `const` (forma preexistente desde la v1.0) no se
  ve afectado — se verificó explícitamente contra toda la suite de
  conformidad, ya que una implementación inicial de este punto introdujo
  una regresión real (un parámetro nuevo insertado en medio de la firma de
  `ArrayDecl.__init__` desalineaba los argumentos posicionales de los
  demás sitios de construcción existentes, marcando arreglos ordinarios
  como constantes); quedó corregida colocando el parámetro nuevo al final
  de la firma.

### 11.11 Catálogo de errores — nuevos códigos

| Código | Condición |
|---|---|
| `IL-POO-030` | Constructor privado invocado desde fuera de la propia clase (`nuevo`, `padre(...)` explícito o implícito) |
| `IL-POO-031` | Miembro duplicado dentro del mismo `enum` |
| `IL-POO-032` | `nuevo` sobre un `enum` (no es instanciable) |
| `IL-TIPO-010` | (reutilizado) Operando de tipo incorrecto para un operador bit a bit (`&`, `\|`, `^`, `~`, `<<`, `>>`) |
| `IL-SEM-031` | (reutilizado) Asignación a una constante escalar **o** a un elemento de un arreglo `const` |
| `IL-TIPO-012` | (reutilizado) `enum` comparado/asignado contra un tipo incompatible (incluyendo `int`, sin conversión implícita) |

### 11.12 Fase 3 — descartada

El usuario evaluó explícitamente una Fase 3 (dos herramientas gráficas
separadas: un editor de bloques estilo Scratch para principiantes, y una
herramienta de prototipado UI/UX) y decidió **no construirla**: un clon de
Scratch no aporta frente a las alternativas gratuitas ya maduras que
existen, y una herramienta de solo-prototipos (sin generar programas
InvenioLang reales y ejecutables) no tiene valor pedagógico dentro de este
proyecto. El esfuerzo se redirigió en su lugar a cerrar brechas reales de
Fase 1/Fase 2 — esta Etapa 11.

## 12. Etapa 12 — Paradigma funcional, tipos suma y rigor de compiladores

Evaluado con criterio de teoría de lenguajes formales (Etapas 1-11 ya
completas y verificadas, 321/321 en `pruebas/conformidad.py`), el hueco
real no era de contenido de asignaturas — ya cubierto — sino de
**paradigma**: sin funciones de primera clase, sin tipos suma/*pattern
matching*, y un backend de compilador (`ir.py`) que se detenía antes del
tramo que un curso de Lenguajes Formales/Compiladores más quiere mostrar
(generación a un objetivo real y análisis de flujo de datos). Esta etapa
cierra las cuatro líneas: quick wins de bajo riesgo (12.1-12.3), rigor de
compiladores documental (12.4), paradigma funcional (12.5-12.8), tipos
suma + *pattern matching* (12.9-12.10), y el resto del back end clásico
(12.11-12.13) — misma disciplina de verificación LALR(1) (20 shift/reduce,
0 reduce/reduce) + conformidad + programas de referencia que las 11 etapas
anteriores. Cierre final: **372/372** en `pruebas/conformidad.py`, 28/28 en
`test_lexer_errors.py`.

### 12.1 `para_cada`/`foreach`

```
entero [4] nums = {10, 20, 30, 40};
entero suma = 0;
para_cada (entero x : nums) { suma = suma + x; }
```

Nueva palabra de apertura `foreach`/`para_cada` (`KW_FOREACH`), sin
colisión de prefijo con nada existente (mismo perfil de riesgo que
`switch`). Funciona sobre arreglos locales, arreglos pasados por
parámetro y arreglos de objetos; `romper`/`continuar` se comportan igual
que dentro de un `while`.

### 12.2 Operadores de seguridad nula `?.` y `??`

```
texto n = persona?.nombre ?? "desconocido";
```

`?.` (acceso seguro): si el receptor es `nulo`, toda la cadena de acceso
produce `nulo` en vez de lanzar `IL-EJE-010`. `??` (coalescencia nula):
`a ?? b` evalúa `b` **solo** si `a` es `nulo` (cortocircuito real, mismo
mecanismo que `&&`/`||`). Nuevos tokens `OP_ACCESO_SEGURO`/
`OP_COALESCENCIA`, protegidos del `?` ternario existente por el orden de
patrones de PLY (más largo primero) — mismo mecanismo que ya protegía
`<<`/`>>` frente a `<`/`>` desde la Etapa 11.9.

### 12.3 Interfaces múltiples (`implementa`/`implements`)

```
interfaz Comparable { publico abstracto entero comparar(Objeto otro); }
interfaz Imprimible { publico abstracto texto describir(); }
clase Producto hereda Base implementa Comparable, Imprimible { ... }
```

`interfaz`/`interface` es sintácticamente un alias de "clase abstracta
con todos los métodos abstractos" (`ClaseInfo.es_interfaz`, solo para
mensajes de error más claros). `ClaseInfo.interfaces` es una lista
aparte de `padre` (que sigue siendo herencia simple, sin cambios) —
`es_subtipo_clase` se extiende para reconocer que implementar una
interfaz también satisface asignaciones/paso de argumentos, evitando el
problema del diamante por diseño (mismo criterio que Java/C#/Kotlin).

### 12.4 Documentación formal de gramática

[`docs/InvenioLang_GramaticaFormal.md`](InvenioLang_GramaticaFormal.md):
EBNF completa extraída programáticamente de los 138 docstrings `p_*` de
`parser.py`, FIRST/FOLLOW trabajados a mano, y fragmentos reales de
`parser.out` (dangling-else, la desambiguación `visibilidad
KW_CONSTRUCTOR` de la Etapa 11.1) — con la comprobación empírica de que
la tabla `precedence` es vestigial excepto para `UMINUS`/`OP_NOT`.

### 12.5/12.6 Funciones de primera clase (closures)

```
funcion(entero a, entero b) entero operar;
operar = funcion(entero x, entero y) entero { return x + y; };
imprimir(operar(3, 4));   // 7
```

- **Tipo función** (`funcion(tipo1 nombre1, tipo2 nombre2) tipoRetorno`)
  con equivalencia **estructural**, no nominal — la única excepción
  deliberada a que InvenioLang es nominal en todo lo demás. *Errata
  (INV-4407):* versiones anteriores de este documento escribían el tipo como
  `funcion(entero, entero) entero`, que el parser rechaza (IL-SIN-010): la
  lista del tipo función usa la misma regla `lista_params` que cualquier
  subrutina, así que cada parámetro lleva nombre. El nombre no forma parte
  del tipo: `funcion(entero a, entero b) entero` y `funcion(entero x, entero
  y) entero` son el mismo tipo `funcion(int,int)->int`.
- **Captura por referencia**: al crear un lambda se guarda
  `list(self.pila_marcos)` (referencia a los mismos diccionarios de
  ámbito, no una copia) — una variable capturada que cambia después
  sigue viéndose actualizada desde el closure.
- Una función/procedimiento de nivel superior también es un valor-función
  válido (`operar = sumar;`), sin gramática nueva (un `IDENTIFICADOR` en
  posición de expresión ya era válido).
- `funcion`/`function` activa una palabra que llevaba reservada como
  futura desde la v1.0 (`reservadas_futuras`).
- **Fuera de alcance para `ir.py`**: cerraduras requieren registros de
  entorno en el heap — `NoSoportadoIR` se lanza limpiamente al intentar
  `--run-ir` sobre un programa que usa closures, mismo criterio que la
  exclusión de POO.
- Auditoría incidental: se descubrió y cerró un hueco preexistente donde
  **ningún** tipo de retorno (función, método o lambda) se validaba
  contra lo que la subrutina realmente retornaba (`int f() { return
  "texto"; }` pasaba sin ningún error) — `IL-TIPO-001` ahora lo cubre de
  forma general.

### 12.7 Orden superior: `mapear`/`filtrar`/`reducir`

```
entero [5] nums = {1, 2, 3, 4, 5}; entero [5] dobles;
mapear(nums, dobles, funcion(entero n) entero { return n * 2; });
```

Como InvenioLang no permite que una función RETORNE un arreglo (límite
confirmado en la gramática formal), `mapear`/`filtrar` escriben en un
arreglo de salida provisto por quien llama en vez de "retornar" uno
nuevo — reutiliza el paso de arreglos por referencia ya existente.
Reconocidas por nombre fijo (no por la tabla genérica de funciones
integradas, que no soporta parámetros de tipo función).

### 12.8 Recursión de cola (TCO) en `ir.py`

Pasada de `ir.py::eliminar_recursion_cola`: cuando la última instrucción
antes de un `return t` es exactamente `t = call SELF, N`, se reescribe
como reasignación de parámetros + `goto` al inicio de la subrutina — la
transformación clásica de eliminación de recursión de cola. Programa de
referencia [`pruebas/suma_cola.inv`](../pruebas/suma_cola.inv): con
`--run-ir-opt`, `sumaCola(n, acc)` corre con profundidad de pila
CONSTANTE; `sumaNormal(n)` (misma respuesta, pero la suma ocurre
DESPUÉS de la llamada recursiva) sigue limitada — ni el intérprete de
árbol ni `--run-ir` sin optimizar aplican esta transformación.

### 12.9/12.10 Tipos suma (enum con carga) + *pattern matching*

```
enum Forma {
    Circulo(entero radio),
    Rectangulo(entero base, entero altura),
    Punto
}
entero area(Forma f) {
    entero r = 0;
    emparejar (f) {
        caso Circulo(rad): r = 3 * rad * rad;
        caso Rectangulo(b, h): r = b * h;
        caso Punto: r = 0;
    }
    return r;
}
```

- Un `enum` con **al menos una** variante con campos se desazucara
  completo (`semantic.py::_desazucarar_tipos_suma`) a una clase
  abstracta base + una clase concreta por variante que hereda de ella —
  reutiliza el 100 % del mecanismo de herencia/clases abstractas/
  despacho virtual de la Etapa 7, cero mecanismo de runtime nuevo.
  `nuevo Circulo(3)` construye la variante exactamente como cualquier
  `nuevo` sobre una clase real, porque a partir de ahí ES una clase real.
- Un `enum` **sin** ninguna variante con carga sigue el camino sin
  cambios de la Etapa 11.8 (atributos estáticos ordinales).
- `emparejar`/`match` es una construcción **separada** de `switch`
  (reutiliza el vocabulario `caso`/`default`, pero no su semántica de
  fallthrough) — funciona tanto sobre tipos suma con carga como sobre
  enums puros.
- **Exhaustividad** (`IL-TIPO-022`): sin un `default`, todas las
  variantes/miembros declarados deben estar cubiertos — la razón de ser
  pedagógica de este mecanismo frente a un `switch` normal: el
  compilador prueba cobertura completa, no el programador.
- Contraste con herencia + polimorfismo: [`pruebas/tipos_suma.inv`](../pruebas/tipos_suma.inv)
  resuelve el mismo problema (área de una figura) que
  [`pruebas/poo_completo.inv`](../pruebas/poo_completo.inv), documentando
  cuándo conviene cada mecanismo (conjunto de variantes cerrado y
  operaciones abiertas → tipos suma; conjunto de variantes abierto y
  operaciones cerradas → herencia).

### 12.11 Generación de código a un objetivo de juguete

`ir.py::generar_objetivo_programa` traduce TAC (optimizado o no) a un
ISA de juguete de pila de operandos — 26 instrucciones (`PUSH`, `LOAD`,
`STORE`, `ADD`/`SUB`/`MUL`/`DIV`/`MOD`, `CALL`/`CALLV`, `RET`/`RETV`,
`PRINT`, ...), documentado íntegro como comentario en `ir.py`. Cierra el
pipeline canónico fuente → AST → TAC → TAC optimizado → código objetivo
que antes se cortaba en el paso anterior. `MaquinaObjetivo` lo ejecuta;
verificado con paridad exacta de salida contra el intérprete de árbol y
`MaquinaTAC` (incluida la recursión de cola de la Etapa 12.8, que se ve
como un `JMP` en vez de una cadena de `CALL`). Mismo alcance que
`generar_programa`, MENOS arreglos y try/catch. Nuevo flag `--target` /
acción de menú "Mostrar código objetivo".

### 12.12 Análisis de flujo de datos: *liveness* + asignación de registros

`ir.py::calcular_liveness` — conjuntos USE/DEF por instrucción de TAC y
un punto fijo hacia atrás sobre las ecuaciones clásicas `IN[i] = USE[i]
∪ (OUT[i] - DEF[i])`, `OUT[i] = ∪ IN[sucesores(i)]` — seguido de
`asignar_registros`, un asignador *linear-scan* (Poletto & Sarkar) que
mapea variables/temporales a un conjunto fijo de registros (`R0`..`Rk-1`,
por defecto 4), con *spill* a memoria (bajo el nombre original) cuando no
alcanzan, usando la heurística "spill del fin más lejano". El ISA de
juguete no distingue registro de memoria en tiempo de ejecución — solo
en el nombre que usa `LOAD`/`STORE` — así que la asignación de registros
es puramente un renombrado antes de la traducción a `InstrObjetivo`.
Nuevo flag `--target-reg` (4 registros) / acción de menú equivalente,
verificado con un caso que fuerza al menos un *spill* real (más valores
simultáneamente vivos que registros) y produce el mismo resultado.

### 12.13 Parser LL(1) de comparación

[`inveniolang/ll1.py`](../inveniolang/ll1.py) — módulo
completamente aparte, no conectado al pipeline principal, acotado a
expresiones aritméticas (`+ - * / ( )` con precedencia y unario `-`).
Recursivo-descendente escrito a mano sobre la gramática sin recursión
izquierda `E -> T E' ; E' -> + T E' | - T E' | ε ; ...`, con sus propios
FIRST/FOLLOW derivados a mano en la cabecera del archivo — el contraste
directo con la tabla LALR(1) real de la misma subgramática (documentada
en `docs/InvenioLang_GramaticaFormal.md`, §12.4). Verificado: el mismo
conjunto de expresiones de prueba produce el mismo resultado numérico
en ambos analizadores (`ll1.py::verificar_contra_lalr`).

### 12.14 Catálogo de códigos de error nuevos

| Código | Condición |
|---|---|
| `IL-POO-033` | `implementa` sobre una clase concreta (no abstracta/interfaz) |
| `IL-POO-034` | Interfaz con atributos, constructores o métodos con cuerpo |
| `IL-TIPO-022` | `emparejar`/`match`: variante desconocida, aridad incorrecta, o no exhaustivo sin `default` |

## 13. Etapa 13 — Constructor de diagramas de flujo

> **Nota (Fase 3, INV-3011):** `flowchart.py` y `flowchart_builder.py`, descritos
> abajo como registro histórico, se sustituyeron por el paquete `inveniolang/flujo/`
> (modelo JSON v1 de todo el programa, ida y vuelta código ⇄ diagrama en es/en,
> edición estructurada y un único panel en la GUI). Ver `docs/diagramas_de_flujo.md`.

Al revisar qué faltaba para dar por concluidas Fase 1 y Fase 2 (Etapas
1-12, todas completas y verificadas) surgió un hueco real: el panel
"Diagrama de flujo" existente desde la Etapa 4
(el antiguo `flowchart.py`, retirado en INV-3011 y sustituido por
`inveniolang/flujo/`, + el dock de solo lectura de `gui_qt.py`) era
una herramienta de **revelar** — toma el AST de un archivo `.inv` ya
escrito y genera automáticamente las cajas y flechas — nunca de
**dibujar**: el estudiante solo hace panorámica/zoom, no coloca ni
conecta una figura. El objetivo pedagógico identificado es el opuesto:
que el estudiante dibuje el diagrama **primero**, como paso de
planeación, y que el diagrama **genere** el esqueleto de código
InvenioLang (flujo inverso al que ya existía). Esta etapa cierra ese
hueco con un constructor de diagramas nuevo, integrado al IDE existente
(no una herramienta separada — no reabre la discusión de la Fase 3, ya
evaluada y descartada explícitamente en la Etapa 11).

### 13.1 Decisión de diseño: paleta + inserción, no dibujo libre de flechas

Un diagrama de flujo dibujado libremente (cajas + flechas arbitrarias) es
un **grafo**; InvenioLang es un lenguaje **estructurado** (sin `goto`).
Convertir un grafo arbitrario a código estructurado es un problema de
*structuring* de flujo de control genuinamente difícil y con casos sin
solución limpia (equivalente a "goto elimination" sobre un CFG
arbitrario). Se evita por completo NO permitiendo dibujo libre de
flechas: el estudiante construye el diagrama insertando bloques de una
paleta (Proceso, Decisión, Mientras, Hacer-mientras, Para, Entrada,
Salida) en una posición de una secuencia — la caja seleccionada, o el
inicio de una rama/cuerpo seleccionado — igual que herramientas
educativas ya consolidadas (RAPTOR y similares). El diagrama es
**estructuralmente válido por construcción**, nunca ambiguo, y el layout
+ las flechas se calculan solos: el estudiante nunca traza una flecha a
mano.

### 13.2 Arquitectura: reuso total, cero motor de análisis nuevo

El estado interno del diagrama que arma el estudiante es literalmente un
`Bloque` real de `ast_nodes.py` — las mismas clases (`IfStmt`,
`WhileStmt`, `DoWhileStmt`, `ForStmt`, `PrintStmt`, `ReadStmt`,
`AssignStmt`, ...) que produce el parser real sobre cualquier archivo
`.inv`. Esto habilita tres reusos directos, documentados en detalle en
el antiguo `flowchart_builder.py` (retirado en INV-3011; hoy la edición
estructurada vive en [`inveniolang/flujo/edicion.py`](../inveniolang/flujo/edicion.py)
y la validación en `flujo/modelo.py`):

- **Validación de cada fragmento** que escribe el estudiante (una
  instrucción, una condición, ...): se envuelve en un programa mínimo
  (`void main() { ... }`, o `si (...) { }`/`mientras (...) { }` para una
  condición, etc.) y se corre por el `Lexer`/`Parser` REALES — mismo
  patrón que ya usaban `pruebas/conformidad.py::analizar()` e
  `inveniolang/ll1.py::_evaluar_lalr()`. Nunca se escribe un segundo
  analizador.
- **Validación de todo el diagrama junto** (no caja por caja aislada —
  así una caja que lee una variable declarada en una caja anterior no se
  marca como error falso): se genera el texto completo
  (`generar_texto_main`; hoy `flujo.codigo_desde_modelo`) y se corre el pipeline entero (`Lexer` →
  `Parser` → `SemanticAnalyzer` → `TypeChecker`), reasignando cada error
  a la caja que lo originó vía un mapa de números de línea.
- **Vista previa en vivo**: `construir_diagrama(bloque)` del antiguo
  `flowchart.py` (retirado; hoy `flujo.modelo_desde_codigo` + `flujo/esquema.py`)
  ya sabía construir un diagrama a partir de CUALQUIER `Bloque` — funciona
  sin cambios sobre el `Bloque` que arma el estudiante.
  `gui_qt.py::_pintar_diagrama` se generalizó (antes solo pintaba en la
  escena del dock de solo lectura) para aceptar la escena/vista como
  parámetro, y así el panel nuevo reusa exactamente el mismo dibujo —
  cero código de layout/pintura duplicado.

### 13.3 Uso

Menú Ver → "Constructor de diagramas" (o Ejecutar → "Constructor de
diagramas de flujo") abre el panel: una paleta de 7 botones, un árbol
editable (doble clic para editar el texto de una caja; clic derecho para
eliminar/mover/agregar-quitar rama "sino"), una vista previa que se
redibuja sola en cada cambio, y un botón "Generar código InvenioLang" que
abre el resultado en una pestaña nueva del editor — desde ahí el flujo
normal del IDE (editar, `--check`, ejecutar, depurar, comparar contra el
panel de diagrama de solo lectura) sigue igual, sin caso especial.

### 13.4 Alcance v1

Soportado: secuencia, si/si-sino, mientras, hacer-mientras, para, entrada
(`leer`), salida (`imprimir`), proceso (una instrucción o declaración
suelta). Genera siempre el cuerpo de `void main()`.

Fuera de alcance v1 (documentado, no a medias — mismo criterio que
excluye POO/matrices de `ir.py`): `switch`/`case`, `try`/`catch`,
`romper`/`continuar` dentro del constructor, múltiples funciones/
procedimientos por diagrama, clases/POO/arreglos dentro del diagrama.
Generar una función/procedimiento con nombre y firma propios (en vez de
siempre `main`) quedó cubierto por el sustituto: `inveniolang/flujo/`
modela el programa completo (todas las subrutinas y clases), ver
[`diagramas_de_flujo.md`](diagramas_de_flujo.md).


## 14. InvenioLang 11 — Acceso a miembro encadenado (INV-4406)

```
clase Motor { publico entero potencia; publico entero doble() { retornar este.potencia * 2; } }
clase Auto  { publico Motor motor; publico Motor getMotor() { retornar este.motor; } }
clase Garaje { publico Auto auto; }

imprimir(g.auto.motor.potencia);       // lectura encadenada
g.auto.motor.potencia = 150;           // escritura (también +=, -=, ...)
imprimir(g.auto.motor.doble());        // llamada al final de la cadena
imprimir(g.auto.getMotor().potencia);  // la cadena sigue tras una llamada
g.auto.km[1] = 7;                      // atributo arreglo al final de la cadena
este.cola.siguiente = n;               // dentro de un método
```

**Gramática.** Un `acceso` (§2) es un acceso a atributo o una llamada a método
completos sobre los que se puede seguir encadenando con `.`. Tras un `acceso`
el punto solo puede continuar la cadena (`.` no pertenece a FOLLOW de
`expr_primaria`), así que la tabla LALR(1) conserva sus 20 resoluciones
shift/reduce documentadas y 0 reduce/reduce.

**Semántica estática.** Cada eslabón se resuelve de izquierda a derecha con
las reglas de §3: la clase del eslabón siguiente es el tipo declarado del
atributo o el tipo de retorno del método anterior.

* El atributo o método debe existir en esa clase o en sus ancestros
  (`IL-POO-006`) y ser accesible desde el punto de uso (`IL-POO-005`):
  `g.secreto.x` falla si `secreto` es privado, aunque `x` sea público.
* Un eslabón intermedio que no es de tipo clase (`a.edad.x`) es
  `IL-POO-006` ("no es una instancia de una clase").
* El tipo de toda la expresión es el del último eslabón y se verifica como
  cualquier otro (`IL-POO-013`, `IL-TIPO-001`, `IL-POO-017`/`018` para los
  argumentos de la llamada final).

**Semántica de ejecución.** Los eslabones se evalúan de izquierda a derecha,
una sola vez cada uno; si uno intermedio es `nulo` se lanza `IL-EJE-010`
(acceso a miembro sobre una referencia nula), como en un acceso de un nivel.
En una asignación compuesta (`g.auto.motor.potencia += 5`) la cadena del
receptor se evalúa una vez.

**Alcance.** El acceso seguro `?.` y la coalescencia `??` (§12.2) siguen
aplicándose a un receptor variable de un solo nivel (`a?.b.c` no es válido):
su cortocircuito está definido sobre la variable. El código intermedio
(`--ir`) sigue sin cubrir POO (§12.5). Casos de conformidad: grupo
"InvenioLang 11 — acceso encadenado" de `pruebas/conformidad.py`.
