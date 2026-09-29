# gui/collab.py — v6 CRDT simple para pair programming (LWW)
from __future__ import annotations
import time, uuid


class LWWRegister:
    def __init__(self, value: str = ""):
        self.value = value
        self.ts = 0
        self.node = str(uuid.uuid4())[:4]

    def set(self, v: str):
        self.value = v
        self.ts = time.time()

    def merge(self, other: "LWWRegister"):
        if other.ts > self.ts:
            self.value = other.value
            self.ts = other.ts


class CollabDoc:
    def __init__(self):
        self.reg = LWWRegister()

    def edit(self, text: str):
        self.reg.set(text)

    def sync(self, other: "CollabDoc"):
        self.reg.merge(other.reg)
        other.reg.merge(self.reg)
