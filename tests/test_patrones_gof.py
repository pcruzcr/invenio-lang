# test_patrones_gof.py — Los 18 patrones GoF como programas .inv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inveniolang import api

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pruebas")

ESPERADOS = {
    "patron_singleton.inv": ["misma instancia: true"],
    "patron_factory.inv": ["perro -> Hace: Guau"],
    "patron_observer.inv": ["[Pantalla] Temperatura actual: 22"],
    "patron_strategy.inv": ["sin descuento: 100.0"],
    "patron_decorator.inv": ["Cafe + leche + chocolate: $2.75"],
    "patron_adapter.inv": ["adapter:viejo:Hola"],
    "patron_bridge.inv": ["bridge-A bridge-B"],
    "patron_composite.inv": ["7"],
    "patron_facade.inv": ["facade:motor;luces;"],
    "patron_proxy.inv": ["proxy:ok proxy:denegado"],
    "patron_command.inv": ["cmd:on cmd:off"],
    "patron_iterator.inv": ["it: 1 2 3"],
    "patron_mediator.inv": ["med:a+b"],
    "patron_memento.inv": ["mem:2 1"],
    "patron_state.inv": ["state:A state:B"],
    "patron_template.inv": ["template:ini+fin"],
    "patron_prototype.inv": ["proto:5 5"],
    "patron_builder.inv": ["builder:pan+leche+"],
}


def test_todos_los_patrones():
    """Cada patrón ejecuta y contiene su fragmento esperado."""
    for nombre, fragmentos in ESPERADOS.items():
        cod = open(os.path.join(BASE, nombre), encoding="utf-8").read()
        r = api.ejecutar(cod)
        assert r.ok, (nombre, r.errores)
        salida = "".join(r.salida)
        for frag in fragmentos:
            assert frag in salida, (nombre, frag, salida)
