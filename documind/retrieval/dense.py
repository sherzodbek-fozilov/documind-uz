"""Dense vector index in Qdrant (server via URL, or in-process ``:memory:`` for eval/tests)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


class QdrantIndex:
    def __init__(self, collection: str, dim: int, url: str | None = None):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self.client = QdrantClient(url=url) if url else QdrantClient(location=":memory:")
        self.collection = collection
        if self.client.collection_exists(collection):
            self.client.delete_collection(collection)
        self.client.create_collection(collection, vectors_config=VectorParams(
            size=dim, distance=Distance.COSINE))

    def add(self, ids: Sequence[str], vectors: np.ndarray, payloads: Sequence[dict]) -> None:
        from qdrant_client.models import PointStruct

        points = [PointStruct(id=i, vector=v.tolist(), payload={**p, "chunk_id": cid})
                  for i, (cid, v, p) in enumerate(zip(ids, vectors, payloads, strict=True))]
        for start in range(0, len(points), 256):
            self.client.upsert(self.collection, points[start:start + 256])

    def search(self, vector: np.ndarray, k: int = 10,
               doc_id: str | None = None) -> list[tuple[str, float]]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        flt = (Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
               if doc_id else None)
        res = self.client.query_points(self.collection, query=vector.tolist(), limit=k,
                                       query_filter=flt)
        return [(p.payload["chunk_id"], p.score) for p in res.points]
