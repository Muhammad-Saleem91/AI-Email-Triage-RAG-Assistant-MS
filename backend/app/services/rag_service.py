import json
import random
import time

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.services.retrieval_service import RetrievalService


NO_ANSWER = "I couldn't find this information in the available knowledge base."


class RagService:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        self.client = genai.Client(api_key=self.settings.gemini_api_key)
        self.retriever = RetrievalService()

    def _generate_with_retry(self, prompt: str, system_instruction: str):
        max_attempts = 4

        for attempt in range(max_attempts):
            try:
                return self.client.models.generate_content(
                    model=self.settings.gemini_llm_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
            except Exception as exc:
                message = str(exc)
                transient = any(
                    marker in message
                    for marker in ("429", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
                )
                if not transient:
                    raise
                if attempt == max_attempts - 1:
                    raise RuntimeError(
                        "The AI service is temporarily unavailable. Please try again shortly."
                    ) from exc

                delay = (2**attempt) + random.uniform(0, 0.5)
                time.sleep(delay)

    def answer(self, question: str, top_k: int | None = None) -> dict:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")

        hits = self.retriever.retrieve(question, top_k=top_k)
        if not hits:
            return {"answer": NO_ANSWER, "grounded": False, "sources": []}

        context_blocks = []
        for index, hit in enumerate(hits, start=1):
            page_number = hit.get("page_number")
            location = f"Page {page_number}" if page_number is not None else "Page unavailable"
            context_blocks.append(
                f"[SOURCE_{index}]\n"
                f"Document: {hit['document_name']}\n"
                f"{location}\n"
                f"Chunk ID: {hit['chunk_id']}\n"
                f"Content:\n{hit['text']}"
            )

        context = "\n\n".join(context_blocks)

        system_instruction = f"""
You are a document-grounded RAG assistant.

Answer the user's question ONLY from the supplied knowledge-base context.

STRICT RULES:
1. Do not use outside knowledge.
2. Do not invent or infer unsupported names, prices, policies, dates, services,
   properties, people, company information, or contractual information.
3. Select a source only when its content directly supports the answer.
4. Do not select a source merely because it is related to the topic.
5. If the supplied context does not explicitly contain enough information to
   answer the question, use exactly this answer:
   "{NO_ANSWER}"
6. Unsupported answer: grounded=false and source_numbers=[].
7. Supported answer: grounded=true and source_numbers contains ONLY directly
   supporting SOURCE numbers.
8. Prefer concise, professional answers.

Return ONLY valid JSON in this structure:
{{
  "answer": "answer text",
  "grounded": true,
  "source_numbers": [1, 2]
}}
"""

        prompt = f"USER QUESTION:\n{question}\n\nKNOWLEDGE BASE CONTEXT:\n{context}"
        response = self._generate_with_retry(prompt, system_instruction)
        raw_response = (response.text or "").strip()

        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            return {"answer": NO_ANSWER, "grounded": False, "sources": []}

        answer = str(result.get("answer", NO_ANSWER)).strip()
        model_grounded = bool(result.get("grounded", False))
        requested_sources = result.get("source_numbers", [])

        valid_source_numbers: list[int] = []
        if isinstance(requested_sources, list):
            for value in requested_sources:
                try:
                    source_number = int(value)
                except (TypeError, ValueError):
                    continue
                if 1 <= source_number <= len(hits) and source_number not in valid_source_numbers:
                    valid_source_numbers.append(source_number)

        if not model_grounded or answer == NO_ANSWER or not valid_source_numbers:
            return {"answer": NO_ANSWER, "grounded": False, "sources": []}

        sources = []
        for source_number in valid_source_numbers:
            hit = hits[source_number - 1]
            excerpt = hit["text"].strip()
            if len(excerpt) > 700:
                excerpt = excerpt[:697].rstrip() + "..."

            sources.append(
                {
                    "document_id": hit["document_id"],
                    "document_name": hit["document_name"],
                    "page_number": hit.get("page_number"),
                    "chunk_id": hit["chunk_id"],
                    "score": round(float(hit["score"]), 4),
                    "excerpt": excerpt,
                }
            )

        return {"answer": answer, "grounded": True, "sources": sources}
