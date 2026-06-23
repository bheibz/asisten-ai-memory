import math
import time
from typing import Optional


class VectorStore:

    def __init__(self):
        self._vectors: dict[str, dict] = {}
        self._real_client = None

    async def connect(self):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            from app.config import settings
            self._real_client = QdrantClient(url=settings.qdrant_url, prefer_grpc=True, timeout=2)
            self._real_client.get_collections()
            print("[Qdrant] Connected to", settings.qdrant_url)
        except Exception:
            print("[Qdrant] Not available, using in-memory fallback")
            self._real_client = None

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0

    def _keyword_score(self, query_words: set, content: str) -> float:
        content_lower = content.lower()
        matches = sum(1 for w in query_words if w in content_lower)
        return matches / max(len(query_words), 1)

    async def upsert(self, collection: str, point_id: str, vector: list[float], payload: dict):
        if self._real_client:
            from qdrant_client.http import models
            self._real_client.upsert(
                collection_name=collection,
                points=[models.PointStruct(id=point_id, vector=vector, payload=payload)],
            )
        else:
            self._vectors[point_id] = {
                "vector": vector,
                "payload": payload,
                "collection": collection,
                "timestamp": time.time(),
            }

    async def search(self, collection: str, vector: list[float], filter_condition: dict = None, top_k: int = 5, query_text: str = ""):
        if self._real_client:
            from qdrant_client.http import models
            q_filter = None
            if filter_condition:
                must = []
                for key, value in filter_condition.items():
                    if isinstance(value, dict) and "$gt" in value:
                        must.append(models.FieldCondition(key=key, range=models.Range(gt=value["$gt"])))
                    else:
                        must.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
                q_filter = models.Filter(must=must)
            results = self._real_client.search(
                collection_name=collection,
                query_vector=vector,
                query_filter=q_filter,
                limit=top_k,
                with_payload=True,
            )
            return [
                {"id": r.id, "content": r.payload.get("content", ""), "score": r.score}
                for r in results if r.score > 0.5
            ]

        items = [v for v in self._vectors.values() if v["collection"] == collection]
        if filter_condition:
            for key, cond in filter_condition.items():
                if isinstance(cond, dict) and "$gt" in cond:
                    items = [v for v in items if v["payload"].get(key, 0) > cond["$gt"]]
                else:
                    items = [v for v in items if v["payload"].get(key) == cond]

        query_words = set(w.lower() for w in query_text.split() if len(w) > 2)
        scored = []
        for item in items:
            content = item["payload"].get("content", "")
            kw_score = self._keyword_score(query_words, content) if query_words else 0
            vec_score = self._cosine_sim(vector, item["vector"])
            score = max(kw_score, vec_score)
            if score > 0:
                scored.append({
                    "id": item["payload"].get("id"),
                    "content": content,
                    "score": score,
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def delete(self, point_id: str):
        if self._real_client:
            from qdrant_client.http import models
            self._real_client.delete(
                collection_name="user_memories",
                points_selector=models.PointIdsList(points=[point_id]),
            )
        else:
            self._vectors.pop(point_id, None)


vector_store = VectorStore()
