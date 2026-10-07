# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Provider adapters.

Every adapter exposes the same ``chat`` / ``stream_chat`` / ``embed`` surface,
so the rest of the codebase never branches on the upstream vendor. Only
OpenAI-compatible servers (which include Ollama, vLLM, LM Studio, OpenRouter,
Azure, Groq, Together, ...) are expected to serve embeddings in most
self-hosted setups.
"""

from __future__ import annotations

from typing import Iterator, Sequence

from .config import AIConfig
from .exceptions import AIProviderError, AIUnsupportedError


class BaseProvider:
    name = "base"

    def __init__(self, config: AIConfig):
        self.config = config

    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError

    def stream_chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        # Providers without native streaming fall back to a single chunk.
        yield self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        raise AIUnsupportedError(f"Provider '{self.name}' does not support embeddings")

    # -- helpers ---------------------------------------------------------
    def _resolved(self, model: str | None, temperature: float | None, max_tokens: int | None):
        return (
            model or self.config.model,
            temperature if temperature is not None else self.config.temperature,
            max_tokens or self.config.max_output_tokens,
        )


class OpenAICompatibleProvider(BaseProvider):
    name = "openai-compatible"

    def _client(self):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise AIProviderError("The 'openai' package is not installed") from exc

        kwargs = {"api_key": self.config.api_key or "not-needed"}
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        return OpenAI(**kwargs)

    def chat(self, messages, *, model=None, temperature=None, max_tokens=None):
        model, temperature, max_tokens = self._resolved(model, temperature, max_tokens)
        try:
            response = self._client().chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise AIProviderError(str(exc), provider=self.name) from exc

    def stream_chat(self, messages, *, model=None, temperature=None, max_tokens=None):
        model, temperature, max_tokens = self._resolved(model, temperature, max_tokens)
        try:
            stream = self._client().chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except Exception as exc:
            raise AIProviderError(str(exc), provider=self.name) from exc

    def embed(self, texts, *, model=None, dimensions=None):
        model = model or self.config.embedding_model
        if not model:
            raise AIUnsupportedError("No embedding model configured")
        kwargs = {}
        # Only OpenAI's own embeddings API accepts `dimensions`; many
        # OpenAI-compatible servers (Ollama, vLLM) reject unknown kwargs.
        if dimensions and self.config.provider == "openai":
            kwargs["dimensions"] = dimensions
        try:
            response = self._client().embeddings.create(model=model, input=list(texts), **kwargs)
            # Preserve input order regardless of provider ordering guarantees.
            return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
        except Exception as exc:
            raise AIProviderError(str(exc), provider=self.name) from exc


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def _endpoint(self) -> str:
        base = (self.config.base_url or "https://api.anthropic.com").rstrip("/")
        return f"{base}/v1/messages"

    def _split_system(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system_parts: list[str] = []
        conversation: list[dict] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role == "system":
                system_parts.append(str(content))
            elif role in ("user", "assistant"):
                conversation.append({"role": role, "content": content})
        return "\n\n".join(system_parts), conversation

    def chat(self, messages, *, model=None, temperature=None, max_tokens=None):
        import requests

        model, temperature, max_tokens = self._resolved(model, temperature, max_tokens)
        system, conversation = self._split_system(messages)
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": conversation,
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            response = requests.post(self._endpoint(), headers=headers, json=payload, timeout=120)
        except Exception as exc:
            raise AIProviderError(str(exc), provider=self.name) from exc
        if response.status_code >= 400:
            raise AIProviderError(response.text, provider=self.name, status_code=response.status_code)
        data = response.json()
        parts = data.get("content", [])
        return "".join(part.get("text", "") for part in parts if part.get("type") == "text")


class GeminiProvider(BaseProvider):
    name = "gemini"

    def _base(self) -> str:
        return (self.config.base_url or "https://generativelanguage.googleapis.com").rstrip("/")

    def _to_contents(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system_parts: list[str] = []
        contents: list[dict] = []
        for message in messages:
            role = message.get("role")
            content = str(message.get("content", ""))
            if role == "system":
                system_parts.append(content)
            else:
                contents.append(
                    {
                        "role": "model" if role == "assistant" else "user",
                        "parts": [{"text": content}],
                    }
                )
        return "\n\n".join(system_parts), contents

    def chat(self, messages, *, model=None, temperature=None, max_tokens=None):
        import requests

        model, temperature, max_tokens = self._resolved(model, temperature, max_tokens)
        system, contents = self._to_contents(messages)
        payload: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{self._base()}/v1beta/models/{model}:generateContent"
        try:
            response = requests.post(
                url, params={"key": self.config.api_key}, json=payload, timeout=120
            )
        except Exception as exc:
            raise AIProviderError(str(exc), provider=self.name) from exc
        if response.status_code >= 400:
            raise AIProviderError(response.text, provider=self.name, status_code=response.status_code)
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts)

    def embed(self, texts, *, model=None, dimensions=None):
        import requests

        model = model or self.config.embedding_model
        if not model:
            raise AIUnsupportedError("No embedding model configured")
        url = f"{self._base()}/v1beta/models/{model}:batchEmbedContents"
        payload = {
            "requests": [
                {"model": f"models/{model}", "content": {"parts": [{"text": text}]}}
                for text in texts
            ]
        }
        try:
            response = requests.post(
                url, params={"key": self.config.api_key}, json=payload, timeout=120
            )
        except Exception as exc:
            raise AIProviderError(str(exc), provider=self.name) from exc
        if response.status_code >= 400:
            raise AIProviderError(response.text, provider=self.name, status_code=response.status_code)
        data = response.json()
        return [item.get("values", []) for item in data.get("embeddings", [])]


_PROVIDER_CLASSES = {
    "openai": OpenAICompatibleProvider,
    "openai-compatible": OpenAICompatibleProvider,
    "ollama": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_provider(config: AIConfig) -> BaseProvider:
    provider_class = _PROVIDER_CLASSES.get(config.provider, OpenAICompatibleProvider)
    return provider_class(config)
