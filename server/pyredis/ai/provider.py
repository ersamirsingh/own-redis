"""Google Gemini LLM & Embedding provider supporting sync/async completions and heuristic fallback."""

import hashlib
import logging
import math
import os
from typing import Any, Dict, List, Optional
from pyredis.core.config import settings

logger = logging.getLogger("pyredis.ai.provider")


def _heuristic_embedding(text: str, dim: int = 64) -> List[float]:
    """Generate a deterministic normalized pseudo-embedding vector for offline fallback."""
    words = text.lower().split()
    vec = [0.0] * dim
    for i, word in enumerate(words):
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % dim
        vec[idx] += 1.0 / (i + 1.0)

    # Normalize vector to unit length
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        return [round(x / norm, 4) for x in vec]
    return [0.0] * dim


class GeminiProvider:
    """Google Gemini AI integration supporting text completions and embeddings."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or settings.GEMINI_MODEL
        self.embedding_model = embedding_model or settings.GEMINI_EMBEDDING_MODEL
        self._client: Optional[Any] = None
        self._init_client()

    def _init_client(self) -> None:
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google GenAI client")
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client: {e}")
                self._client = None
        else:
            self._client = None

    def update_config(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        """Update API key and model at runtime."""
        if api_key is not None:
            self.api_key = api_key
        if model is not None:
            self.model_name = model
        self._init_client()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self._client is not None)

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """Synchronously generate response from Gemini or heuristic fallback."""
        if self._client:
            try:
                from google.genai import types
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                ) if system_instruction else None

                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.warning(f"Gemini API call failed, using heuristic response: {e}")

        # Heuristic fallback response
        return (
            "PyRedis Intelligent DBA Assistant:\n"
            "System telemetry analyzed. All metrics are nominal. For real-time autonomous reasoning "
            "and deep insights, please configure your Google Gemini API key in Settings -> AI Provider."
        )

    async def generate_text_async(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """Asynchronously generate response from Gemini or heuristic fallback."""
        if self._client:
            try:
                from google.genai import types
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                ) if system_instruction else None

                response = await self._client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.warning(f"Gemini async API call failed, using heuristic response: {e}")

        return self.generate_text(prompt, system_instruction)

    def embed_text(self, text: str) -> List[float]:
        """Synchronously generate vector embedding using Gemini or fallback."""
        if self._client:
            try:
                response = self._client.models.embed_content(
                    model=self.embedding_model,
                    contents=text,
                )
                if response and response.embedding and response.embedding.values:
                    return list(response.embedding.values)
            except Exception as e:
                logger.warning(f"Gemini embedding call failed, using heuristic: {e}")

        return _heuristic_embedding(text)

    async def embed_text_async(self, text: str) -> List[float]:
        """Asynchronously generate vector embedding using Gemini or fallback."""
        if self._client:
            try:
                response = await self._client.aio.models.embed_content(
                    model=self.embedding_model,
                    contents=text,
                )
                if response and response.embedding and response.embedding.values:
                    return list(response.embedding.values)
            except Exception as e:
                logger.warning(f"Gemini async embedding call failed, using heuristic: {e}")

        return _heuristic_embedding(text)


# Global Gemini provider singleton
gemini_provider = GeminiProvider()
