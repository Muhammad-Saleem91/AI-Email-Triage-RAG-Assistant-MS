from functools import lru_cache
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.core.config import get_settings
from app.services.chunking_service import TextChunk


class VectorService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.qdrant_storage_path.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(self.settings.qdrant_storage_path))
        self.collection = self.settings.qdrant_collection
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=self.settings.embedding_dimension,
                    distance=models.Distance.COSINE,
                ),
            )

    def index_chunks(
        self,
        document_id: str,
        document_name: str,
        chunks: list[TextChunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk/vector count mismatch.")

        self.delete_document(document_id)
        points: list[models.PointStruct] = []

        for chunk, vector in zip(chunks, vectors, strict=True):
            payload = {
                "document_id": document_id,
                "document_name": document_name,
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
            }
            if chunk.page_number is not None:
                payload["page_number"] = chunk.page_number

            # Qdrant point IDs support UUIDs. Keep our readable chunk ID in payload,
            # and derive a deterministic UUID for the actual vector point ID.
            point_id = str(uuid5(NAMESPACE_URL, chunk.chunk_id))
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        if points:
            self.client.upsert(
                collection_name=self.collection,
                wait=True,
                points=points,
            )

    def delete_document(self, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def search(self, query_vector: list[float], limit: int) -> list[dict]:
        result = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )
        hits: list[dict] = []
        for point in result.points:
            payload = point.payload or {}
            hits.append(
                {
                    "score": float(point.score),
                    "document_id": str(payload.get("document_id", "")),
                    "document_name": str(payload.get("document_name", "")),
                    "page_number": payload.get("page_number"),
                    "chunk_id": str(payload.get("chunk_id", point.id)),
                    "text": str(payload.get("text", "")),
                }
            )
        return hits


@lru_cache
def get_vector_service() -> VectorService:
    # Local Qdrant storage should be opened once per application process.
    return VectorService()
