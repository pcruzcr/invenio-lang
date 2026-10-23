# Módulos: `importar "ruta";` / `import "path";`

Desde la v11 un programa puede usar declaraciones de otros archivos `.inv`
(INV-1420).

```
// util/geometria.inv
constante real PI = 3.14159;
real area_circulo(real r) { retornar PI * r * r; }

// programa.inv
importar "util/geometria";
vacio main() { imprimir(area_circulo(2.0)); }
```

## Reglas

* **Ruta**: literal de texto relativo al archivo que importa; `.inv` es
  opcional. Si no existe junto a él se busca en la biblioteca estándar
  (`inveniolang/stdlib`, ver `biblioteca_estandar.md`).
* **Seguridad**: toda ruta pasa por `security.validar_ruta_relativa` (sin `..`,
  sin rutas absolutas ni `:`) y debe terminar en `.inv`; resuelta, debe quedar
  dentro de la carpeta del programa (o de la biblioteca): un enlace simbólico
  que salga de ella se rechaza. Máximo 64 módulos por programa.
* **Qué se importa**: funciones, procedimientos, clases, enumeraciones,
  interfaces y constantes. Las variables globales de un módulo no se exportan
  (IL-MOD-005). El `main` de un módulo se ignora al importarlo, así un módulo
  puede ser también un ejemplo ejecutable.
* **Visibilidad**: plana y transitiva (como `#include`): quien importa `a` ve lo
  que `a` importó. Un módulo importado por dos caminos (diamante) se carga una
  sola vez.
* **Aislamiento**: cada módulo se verifica (semántica y tipos) por separado,
  con sus propias importaciones: no puede usar nombres del programa que lo
  importa, y sus errores se informan con su nombre de archivo, también los de
  ejecución (`[IL-EJE-006] util/mates.inv:4:49 — División por cero`).
* **Código intermedio**: el enlace ocurre al analizar, así que `--ir`,
  `--run-ir` y `--target` ven el programa ya enlazado (con el alcance habitual
  del IR: sin clases).
* **Núcleo puro**: `compile_pure(req, cargador=...)` recibe el puerto
  `modulos.CargadorModulos`; `CargadorArchivos` (disco, por defecto) y
  `CargadorMemoria` (diccionario, para la web y las pruebas) son adaptadores.
  El enlace es la fase medida `modulos` de `--metrics`.

## Diagnósticos

| Código | Condición |
|---|---|
| `IL-MOD-001` | Módulo no encontrado (ni junto al importador ni en la biblioteca) |
| `IL-MOD-002` | Ruta no permitida (`..`, absoluta, `:`, extensión distinta de `.inv`, o enlace que sale de la carpeta) |
| `IL-MOD-003` | Importación circular (se muestra la cadena: `a.inv -> b.inv -> a.inv`) |
| `IL-MOD-004` | Un nombre declarado en dos archivos |
| `IL-MOD-005` | Variable global en un módulo |
| `IL-MOD-006` | El módulo no se pudo leer (permisos, UTF-8 inválido, tamaño) |
| `IL-MOD-007` | Más de 64 módulos |
