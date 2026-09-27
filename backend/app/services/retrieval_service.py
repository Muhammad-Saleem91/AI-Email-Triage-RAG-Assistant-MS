from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import get_vector_service


class RetrievalService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.embeddings = EmbeddingService()
        self.vector_store = get_vector_service()

    def retrieve(self, question: str, top_k: int | None = None) -> list[dict]:
        vector = self.embeddings.embed_query(question)
        hits = self.vector_store.search(vector, top_k or self.settings.top_k)
        return [
            hit for hit in hits if hit["score"] >= self.settings.min_retrieval_score
        ]
