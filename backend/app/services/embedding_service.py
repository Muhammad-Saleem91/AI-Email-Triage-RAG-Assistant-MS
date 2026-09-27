from google import genai
from google.genai import types

from app.core.config import get_settings


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. Add it to backend/.env before indexing."
            )
        self.client = genai.Client(api_key=self.settings.gemini_api_key)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # gemini-embedding-2 aggregates a plain list[str] into ONE embedding.
        # Wrapping every input as its own Content object asks Gemini for one
        # embedding per chunk, which is what a vector database needs.
        contents = [
            types.Content(parts=[types.Part.from_text(text=text)])
            for text in texts
        ]

        result = self.client.models.embed_content(
            model=self.settings.gemini_embedding_model,
            contents=contents,
            config=types.EmbedContentConfig(
                output_dimensionality=self.settings.embedding_dimension
            ),
        )

        if not result.embeddings:
            raise RuntimeError("Embedding provider returned no vectors.")

        vectors = [list(item.values or []) for item in result.embeddings]
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Embedding provider returned {len(vectors)} vectors for "
                f"{len(texts)} inputs."
            )
        return vectors

    def embed_documents(
        self,
        texts: list[str],
        title: str | None = None,
    ) -> list[list[float]]:
        # Gemini Embedding 2 recommends asymmetric retrieval formatting.
        safe_title = title or "none"
        prepared = [f"title: {safe_title} | text: {text}" for text in texts]
        return self._embed(prepared)

    def embed_query(self, query: str) -> list[float]:
        prepared = f"task: question answering | query: {query}"
        vectors = self._embed([prepared])
        return vectors[0]
