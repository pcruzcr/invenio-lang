# Diagramas UML: del código al diagrama y del diagrama al código

InvenioLang convierte un programa orientado a objetos (en español o en inglés)
en un **diagrama de clases UML** y, en sentido contrario, convierte un diagrama
de clases (JSON o PlantUML) en un **esqueleto de programa que compila**. También
dibuja el **diagrama de objetos** de cualquier paso de una traza de ejecución
(ver [visualizacion.md](visualizacion.md)).

Paquete `inveniolang/uml/` (sustituye al antiguo `uml.py`):

| módulo | qué hace |
|---|---|
| `modelo.py` | contrato JSON v1 del diagrama de clases (ida y vuelta exacta) |
| `desde_codigo.py` | programa → modelo, con todas las relaciones |
| `plantuml.py` | subconjunto de PlantUML → modelo |
| `reglas.py` | normalización del modelo y validación previa a generar código |
| `exportar.py` | modelo → PlantUML y Mermaid `classDiagram` |
| `svg.py`, `texto.py` | dibujo SVG accesible y descripción en frases (es/en) |
| `generador.py` | modelo → esqueleto InvenioLang (es/en) |
| `objetos.py` | diagrama de objetos de un paso de una traza |

## Uso

### Línea de comandos

```
inveniolang archivo.inv --uml [plantuml|mermaid|svg|json|texto] [--idioma es|en]
inveniolang desde-uml diagrama.(json|puml) [--idioma es|en] [-o destino.inv]
```

* `--uml` sin valor escribe PlantUML. `svg` es un dibujo autónomo, `json` el
  modelo del contrato y `texto` la descripción accesible. Los `importar` se
  resuelven junto al archivo; las clases importadas aparecen marcadas con su
  módulo. `--idioma` fija cómo se escriben los tipos (`entero`/`int`) y el
  idioma del texto; sin él se usa el de las palabras clave del programa.
* `desde-uml` (alias `from-uml`) genera el esqueleto. `--idioma` es el idioma
  del código y de los mensajes; sin él, el del diagrama. Sin `-o`, el código se
  imprime. Sale con 1 si el diagrama no se puede leer o InvenioLang no puede
  expresarlo, explicando cada motivo.

```
$ inveniolang curriculum/es/nivel08/06_composicion.inv --uml texto
Diagrama de clases: 2 clases; 1 relación.
- Clase Motor. Atributos: potencia (público, entero), encendido (público, logico). ...
- Clase Auto. Atributos: marca (público, texto), motor (público, Motor), ...
Relaciones:
- Auto se compone de Motor mediante el atributo motor (multiplicidad 0..1: cero o uno): lo crea y lo contiene.
```

### API

```python
from inveniolang import api, uml

r = api.uml(codigo, ruta="<memoria>", formato="plantuml", config=DEFAULT_CONFIG,
            idioma=None, tema="claro", modulos=None, ruta_fuente=None)
r.ok, r.salida[0], r.errores          # ExecutionResult, como el resto de herramientas

g = api.codigo_desde_uml(modelo_o_plantuml, idioma=None)
g.ok                                   # True solo si el esqueleto compila
g.salida[0]                            # el código generado
g.errores                              # por qué no se pudo (en el idioma pedido)

svg = api.diagrama_objetos(codigo_o_traza, paso, formato="svg", idioma=None, tema="claro")
txt = api.diagrama_objetos(traza, paso, formato="texto")
```

* `api.uml` conserva la firma anterior (`codigo, ruta, formato, config`); los
  parámetros nuevos van detrás. Un formato desconocido es `ValueError`. Un
  programa con errores devuelve `ok=False` y los diagnósticos oficiales.
* `codigo_desde_uml` acepta un `uml.DiagramaClases`, su `dict`, su JSON (texto
  que empieza por `{`) o texto PlantUML.
* `diagrama_objetos` usa la misma convención que `api.traza_svg`: `paso` es la
  posición 0..N-1; `IndexError` si no existe. `codigo_o_traza` es código (se
  traza) o una traza ya hecha (`Traza` o su `dict`).
* Desde Python, `uml.exportar(modelo, formato, idioma, tema)`,
  `uml.cargar_diagrama(fuente)`, `uml.generar_codigo(modelo, idioma)` y
  `uml.a_json`/`uml.desde_json` trabajan directamente con el modelo.

### GUI Qt

Menú *Ver → Diagrama de clases UML* (o *Ejecutar → Diagrama de clases UML*)
abre el panel **Diagrama UML**:

* **Diagrama desde el código** dibuja las clases del editor (con sus
  `importar`) y muestra debajo la descripción accesible; si el programa tiene
  errores, los explica.
* **Exportar…** guarda el diagrama; el formato sale de la extensión: `.svg`,
  `.puml`, `.mmd` (Mermaid), `.json` o `.txt` (texto accesible).
* El cuadro inferior contiene el diagrama en **PlantUML editable**. Se puede
  cambiar, o cargar un `.puml`/`.json` con **Abrir PlantUML o JSON…**, elegir
  el idioma del código y pulsar **Generar esqueleto**: el código se abre en una
  pestaña nueva.
* El dibujo sigue el tema claro/oscuro del IDE.

## Contrato JSON (versión 1)

```
Diagrama     = {"version":1, "tipo":"diagrama_clases", "idioma":"es"|"en",
                "clasificadores":[Clasificador], "relaciones":[Relacion]}
Clasificador = {"nombre":str, "tipo":"clase"|"abstracta"|"interfaz"|"enumeracion",
                "parametros_tipo":[str], "atributos":[Atributo],
                "constructores":[Constructor], "metodos":[Metodo],
                "literales":[Literal], "modulo":str|null}
Atributo     = {"nombre", "tipo", "visibilidad":"+"|"-"|"#", "estatico":bool,
                "constante":bool, "valor_inicial":{"tipo":"int"|"float"|"string"|"bool"|"null",
                                                   "v":valor}|null}
Constructor  = {"visibilidad", "parametros":[{"nombre","tipo"}]}
Metodo       = {"nombre", "retorno", "visibilidad", "parametros", "estatico":bool,
                "abstracto":bool, "sobrescribe":bool}
Literal      = {"nombre", "parametros"}                 (parámetros = carga de un tipo suma)
Relacion     = {"tipo":"herencia"|"realizacion"|"composicion"|"agregacion"|
                       "asociacion"|"dependencia",
                "origen":str, "destino":str, "rol":str|null, "multiplicidad":"0..1"|"0..*"|null}
```

* **Tipos canónicos** e independientes del idioma: `int`, `float`, `string`,
  `bool`, `void`, nombres de clase, parámetros de tipo (`T`) y sufijos `[]` /
  `[][]`. Los renderizadores los escriben como `entero`/`int`, etc.
* La herencia y la realización viven **solo** en `relaciones` (`origen` es la
  subclase o la clase que implementa).
* Las relaciones estructurales (composición, agregación, asociación) llevan
  `rol` = nombre del atributo y su multiplicidad; las demás llevan `null` en
  ambos.
* `valor_inicial` solo guarda literales: cualquier otra expresión depende de
  código que el diagrama no tiene.
* `sobrescribe` es derivado (otro supertipo declara la misma firma) y se
  recalcula siempre.
* `desde_json` valida todo: versión, claves, valores admitidos, nombres
  repetidos y que cada relación nombre clasificadores existentes; el error dice
  la ruta del dato (`uml.relaciones[2].multiplicidad`) en es o en.
* `desde_json(a_json(m)) == m` siempre.

**Normalización** (`reglas.normalizar`, idempotente; el modelo que sale del
código ya está normalizado): los métodos de una interfaz son abstractos; cada
atributo cuyo tipo es un clasificador tiene su relación estructural (asociación
si no se dijo otra) con la multiplicidad que dicta su tipo; una relación
estructural cuyo rol no es un atributo crea ese atributo (privado); se quitan
relaciones repetidas y las dependencias que ya expresa una relación más fuerte.

## Del código al diagrama: criterio de cada relación

El modelo se construye desde el AST **antes** del análisis semántico (que
expande los genéricos en `Caja<entero>`... y convierte los tipos suma en
clases), pero solo después de comprobar que el programa completo es válido:
el diagrama muestra lo que el estudiante escribió.

| relación | cuándo | notación |
|---|---|---|
| herencia | `hereda` / `extends` | línea con triángulo hueco hacia el padre |
| realización | `implementa` / `implements` | discontinua con triángulo hueco |
| **composición** | el atributo de tipo `T` se crea con `nuevo T(...)` **dentro de un constructor** de la clase o en la inicialización del atributo: el todo crea a la parte y la parte vive con él | rombo lleno en el todo |
| **agregación** | el atributo recibe un objeto que llega como **parámetro** de un constructor o método (`este.motor = m`): la parte existe fuera y puede compartirse | rombo hueco en el todo |
| **asociación** | cualquier otro atributo cuyo tipo es un clasificador | flecha abierta |
| **dependencia** | el clasificador aparece en una firma (parámetro, retorno) o en un cuerpo (variable local, `nuevo`, acceso estático `Clase.x`, variante de tipo suma, `Caja<T>`) y no existe ya una relación de las anteriores | discontinua con flecha abierta |

Prioridad: composición > agregación > asociación. Multiplicidad: `0..1` para un
atributo objeto (puede ser `nulo`), `0..*` para un arreglo de objetos. Un
atributo de tipo enumeración también es una asociación.

Interfaces, clases abstractas, enumeraciones (y tipos suma, cuyos literales
llevan carga: `Circulo(radio : entero)`), genéricos (`Caja<T>`), atributos y
métodos estáticos, constructores (uno o varios, públicos o privados) y la
sobrecarga se representan tal cual.

### Correspondencia con InvenioLang

| UML | InvenioLang |
|---|---|
| `+` / `-` | `publico` / `privado` |
| `#` protegido | no existe; al generar código se usa `publico` (para que las subclases lo vean) con un comentario |
| `{static}` | `estatico` |
| `{abstract}` | `abstracto` (método) / `abstracta clase` |
| `{readOnly}` | no existe para atributos; se genera el atributo con un comentario |
| `«create» Clase(...)` | constructor (`privado constructor Clase(...)` si es privado) |
| `interface` | `interfaz` (solo métodos públicos abstractos) |
| `enum` | `enumeracion` |
| `Clase<T>` | clase genérica (un solo parámetro, sin herencia) |

## PlantUML admitido

```
@startuml                        ' (opcional; también @enduml)
' comentario   /' comentario de bloque '/
skinparam ... / hide ... / show ... / title ... / note ... / end note   (se ignoran)

class Nombre
class Nombre<T> {
abstract class Nombre extends Padre implements I1, I2 {
abstract Nombre {
interface Nombre {
enum Nombre {
class Nombre <<interface>> {      ' también <<abstract>>, <<enumeration>>
  -- separadores --   ==   ..   __
  [vis] [{static}] nombre : Tipo [= literal] [{readOnly}]
  [vis] [{static}] Tipo nombre [= literal]
  [vis] [{static}|{abstract}] nombre(p : Tipo, q : Tipo) : Retorno
  [vis] [{static}|{abstract}] Retorno nombre(Tipo p)
  [vis] <<create>> Nombre(p : Tipo)        ' o Nombre(p : Tipo) sin retorno
  VALOR, OTRO                              ' en un enum (uno o varios por línea)
  VARIANTE(campo : Tipo)                   ' variante con carga
}

A <|-- B      B --|> A      ' B hereda de A
I <|.. C      C ..|> I      ' C implementa I
A *-- "0..*" B : rol        ' composición (B --* A también)
A o-- B : rol               ' agregación
A --> B : rol    A -- B     ' asociación
A ..> B          A .. B     ' dependencia
```

* Visibilidad: `+`, `-`, `#`, `~` (este último se trata como público). Sin
  marca, los atributos son privados y los métodos públicos.
* Tipos en español, en inglés o con nombres habituales (`Integer`, `long`,
  `double`, `String`, `boolean`...). Una clase del diagrama gana a un alias:
  una clase llamada `Texto` no se confunde con `texto`.
* Multiplicidad: si el texto junto a la parte contiene `*`, `n` o `many` es
  `0..*`; si no, `0..1`. Sin rol, el rol es el nombre de la clase destino con
  la inicial en minúscula. Una relación estructural crea el atributo si falta.
* Las clases mencionadas solo en relaciones o en `extends`/`implements` se
  crean vacías.
* El idioma del modelo sale de los tipos escritos (`entero` → es, `int` → en).
* Cualquier otra línea es un error con su número de línea, en es o en
  (`PlantUML, línea 4: flecha no admitida «<<-->>»`).

## Del diagrama al código

`generar_codigo` (y `api.codigo_desde_uml`) escribe cada clasificador con sus
firmas exactas; los cuerpos llevan `// Por completar: ...` y devuelven el valor
por defecto del tipo (`0`, `0.0`, `""`, `falso`, `nulo`, el primer valor de una
enumeración; en un genérico, una variable `T valor;` sin inicializar). Para que
al volver a analizar el esqueleto salga **el mismo diagrama**, también escribe:

* composición → `este.parte = nuevo Parte(...)` en cada constructor (o en la
  inicialización del atributo si la clase no tiene constructores), con
  argumentos por defecto;
* agregación → el primer constructor o método con un parámetro de ese tipo lo
  guarda en el atributo;
* dependencia que no se ve en ninguna firma → una variable local comentada
  (`Caja<entero> usaCaja;`) en el primer cuerpo de la clase.

Lo que el diagrama dejaba incompleto pero InvenioLang exige se completa con un
comentario: una superclase sin constructor de 0 argumentos recibe
`padre(...)` (y la subclase un constructor si no tenía); una clase concreta
recibe los métodos abstractos heredados que no implementaba. El orden de
salida es: enumeraciones, interfaces, clases (cada padre antes que sus hijas)
y un `main` vacío. El código pasa por el formateador y se compila antes de
devolverlo.

Se rechaza, explicando cada motivo (todos juntos, en es o en): identificadores
inválidos o reservados, tipos desconocidos, `void` fuera de un retorno,
atributos que son arreglos de objetos, matrices o arreglos donde la gramática
no los admite, miembros o firmas repetidos, abstracto y estático a la vez,
métodos abstractos en una clase concreta, interfaces con atributos,
constructores o métodos no públicos, enumeraciones vacías o con miembros,
herencia múltiple, cíclica o entre tipos incompatibles, y genéricos con más de
un parámetro o con herencia.

**Garantía probada** (`tests/uml/test_uml_ida_vuelta.py`): para todos los
ejercicios POO de los niveles 8 a 12 (es y en) y todos los módulos de
estructuras de la biblioteca estándar, código → UML → código produce, en
español y en inglés, un programa que compila y cuyas clases tienen la misma
estructura (miembros, firmas y relaciones). También se comprueban la ida y
vuelta por PlantUML y por JSON.

## SVG del diagrama de clases

* **Jerárquico por herencia**: cada clasificador va en la fila
  `1 + fila más baja de sus supertipos` (padres e interfaces arriba); dentro de
  la fila se ordena por el baricentro de sus supertipos; una fila de más de
  1280 px se parte. Las cajas nunca se solapan y el resultado es determinista
  (mismo modelo → mismo SVG, byte a byte).
* **Notación UML**: estereotipos («abstracta», «interfaz», «enumeración»),
  nombre abstracto en cursiva, miembros estáticos subrayados, `{abstracto}`
  escrito, `«create»` en los constructores; triángulos, rombos y flechas según
  la tabla de relaciones; rol y multiplicidad junto a la parte, con fondo para
  leerse sobre las líneas; los lazos de una clase consigo misma van a su
  derecha con espacio reservado.
* **Accesible**: `role="img"`, `<title>` (resumen) y `<desc>` (la descripción
  completa), un grupo con nombre y `<title>` por clasificador, por miembro y
  por relación. Las relaciones se distinguen por forma y trazo, no por color, y
  una leyenda nombra las que aparecen.
* **Temas**: paleta clara u oscura de la Fase 2 (texto AAA) con las clases
  `f-`/`s-` que el CSS del reproductor sabe repintar.

## Diagrama de objetos

`api.diagrama_objetos` dibuja (o describe) lo que hay en memoria en un paso de
una traza: cada objeto, arreglo o matriz del montículo como instancia
subrayada `nombre : Clase` con el valor de sus campos o celdas, y los enlaces
entre ellas (flecha con el nombre del campo o `[i]`). Nombres: la variable que
la referencia, buscando del marco activo hacia `main` (`este`/`this` solo si
ninguna otra variable lo hace; si dos objetos distintos comparten nombre, el
segundo lleva la subrutina entre paréntesis); una instancia sin variable es
anónima y se nombra por su id (`#7 : Nodo`). Disposición por niveles de
recorrido desde las variables. Se muestran como mucho 60 instancias y 12
celdas por arreglo, y se dice cuántas hay.

Accesos (INV-4402): `inveniolang trazar prog.inv --objetos N objetos.svg`
(o `objetos.txt` para la descripción en texto) desde la línea de órdenes, y el
botón **Diagrama de objetos** (tecla `O`) del panel Visualizador de la GUI, que
alterna el dibujo del paso entre las estructuras de datos y el diagrama de
objetos sin perder el paso ni la descripción accesible.

---

## English summary

`inveniolang file.inv --uml [plantuml|mermaid|svg|json|texto]` prints the
class diagram of a program (Spanish or English keywords): PlantUML, Mermaid
`classDiagram`, a self-contained accessible SVG, the version-1 JSON model or an
accessible text description. `inveniolang desde-uml diagram.(json|puml)
[--idioma es|en] [-o out.inv]` (alias `from-uml`) turns a class diagram into an
InvenioLang skeleton that **compiles**, in Spanish or English.

Python: `api.uml(code, ruta, formato, config, idioma=None, tema="claro",
modulos=None, ruta_fuente=None)` (backwards-compatible signature),
`api.codigo_desde_uml(model_or_plantuml, idioma=None)` (`ok` only if the
generated code compiles; `errores` explains what cannot be expressed) and
`api.diagrama_objetos(code_or_trace, step, formato="svg"|"texto")` (object
diagram of a trace step, position 0..N-1; from the command line
`inveniolang trace prog.inv --objects N objects.svg|objects.txt`, step number
N as printed by `--texto`, and in the IDE's Visualizer panel with the
**Object diagram** toggle, key `O`). In the Qt IDE, *View → UML class
diagram* opens a panel that draws the editor's classes, exports them by file
extension and turns editable PlantUML into a skeleton opened in a new tab.

Relationship criteria: **composition** when the class creates the part with
`new T(...)` in a constructor or in the attribute initialiser; **aggregation**
when the attribute stores an object received as a constructor/method parameter;
**association** for any other attribute whose type is a classifier
(multiplicity `0..1`, or `0..*` for an array of objects); **dependency** when a
classifier appears in a signature or a body without a stronger relationship;
plus inheritance and realization. Supported PlantUML: `class`,
`abstract class`, `interface`, `enum`, generics `<T>`, `extends`/`implements`,
attributes and methods in UML (`name : Type`) or Java (`Type name`) style,
`{static}`, `{abstract}`, `{readOnly}`, `<<create>>` constructors and the arrows
`<|--`, `<|..`, `*--`, `o--`, `-->`, `--`, `..>` (and their reverses) with
quoted multiplicities and `: role`; anything else is an error with its line
number. InvenioLang has no `protected` (generated as `public` with a comment),
no constant attributes and no attributes that are arrays of objects (rejected
with an explanation). The round trip code → UML → code is tested on every OOP
exercise of curriculum levels 8–12 (es and en) and every data-structure module
of the standard library, in both languages, plus the PlantUML and JSON round
trips.
