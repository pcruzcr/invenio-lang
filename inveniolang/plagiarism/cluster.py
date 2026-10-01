# plagiarism/cluster.py — v10 cluster a escala 1000 envíos (Winnowing + Union-Find)
from __future__ import annotations

from ..evaluation import plagiarism_score


def cluster(codes: list[str], threshold: float = 0.7) -> list[set[int]]:
    """Agrupa entregas similares."""
    n = len(codes)
    parent = list(range(n))

    def find(x):
        """Busca el representante."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        """Une dos grupos."""
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if plagiarism_score(codes[i], codes[j]) >= threshold:
                union(i, j)
    groups: dict[int, set[int]] = {}
    for i in range(n):
        r = find(i)
        groups.setdefault(r, set()).add(i)
    return [g for g in groups.values() if len(g) > 1]
