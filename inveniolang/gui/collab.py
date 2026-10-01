# gui/collab.py — v6 CRDT simple para pair programming (LWW)
from __future__ import annotations

import time
import uuid


class LWWRegister:
    """Registro última escritura gana."""

    def __init__(self, value: str = ""):
        self.value = value
        self.ts = 0
        self.node = str(uuid.uuid4())[:4]

    def set(self, v: str):
        """Asigna el valor con marca temporal."""
        self.value = v
        self.ts = time.time()

    def merge(self, other: LWWRegister):
        """Fusiona otro registro (LWW)."""
        if other.ts > self.ts:
            self.value = other.value
            self.ts = other.ts


class CollabDoc:
    """Documento colaborativo."""

    def __init__(self):
        self.reg = LWWRegister()

    def edit(self, text: str):
        """Edita el documento colaborativo."""
        self.reg.set(text)

    def sync(self, other: CollabDoc):
        """Sincroniza con otro documento."""
        self.reg.merge(other.reg)
        other.reg.merge(self.reg)
