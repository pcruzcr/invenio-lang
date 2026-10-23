# Arreglos dinámicos (INV-1440)

Un arreglo declarado (`entero[10] a;`) tiene tamaño fijo conocido al compilar.
Para estructuras que crecen (un vector dinámico) una clase puede tener
**atributos arreglo sin tamaño** que se crean en ejecución:

```
clase Vector {
    privado entero[] datos;            // atributo arreglo (inicialmente nulo)
    Vector() { este.datos = nuevo entero[4]; }      // tamaño: cualquier expresión entera
    publico vacio poner(entero i, entero v) { este.datos[i] = v; }
    publico entero capacidad() { retornar longitud_arreglo(este.datos); }
}
```

* `nuevo tipo[n]` crea `n` elementos con el valor por defecto del tipo
  (`0`, `0.0`, `""`, `falso`). `n` fuera de `[0, 100000]` es IL-EJE-050.
* `obj.atributo[i]` / `este.atributo[i]` se lee y se asigna (también con
  `+=`, etc.); índice fuera de rango: IL-EJE-050; arreglo aún nulo: IL-EJE-010;
  indexar un atributo que no es arreglo: IL-TIPO-023.
* Un atributo arreglo se puede reasignar (`este.datos = este.otro;`) y pasar a
  un parámetro `entero[]` (por referencia, como cualquier arreglo).
* Alcance: atributos de clase de tipo primitivo; las variables locales y los
  parámetros siguen usando las formas de siempre. El backend de código
  intermedio no cubre clases, así que tampoco esta construcción.

`inveniolang/stdlib/estructuras/vector.inv` es el ejemplo completo (capacidad
que se duplica, inserción y borrado con corrimiento).
