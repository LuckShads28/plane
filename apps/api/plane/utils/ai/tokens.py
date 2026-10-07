# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Token estimation and context budgeting.

Local models use a wide variety of tokenizers, so we never hardcode a model
assumption. When ``tiktoken`` is available and recognises the model we use it;
otherwise we fall back to a conservative character-based heuristic that works
for any OpenAI-compatible server. The budget itself is always driven by the
configured ``context_window`` so a 65k office model and a 200k cloud model both
work without code changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

# Conservative characters-per-token ratio. Real tokenizers vary between ~2.5 and
# ~4.5; 3.5 keeps us from under-estimating and overflowing a small local window.
_CHARS_PER_TOKEN = 3.5

# Rough per-message overhead (role, separators) used by chat APIs.
_MESSAGE_OVERHEAD_TOKENS = 4


def _get_encoder(model: str | None):
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return None
    try:
        if model:
            return tiktoken.encoding_for_model(model)
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None


def count_tokens(text: str | None, model: str | None = None) -> int:
    """Best-effort token count for ``text``."""
    if not text:
        return 0
    encoder = _get_encoder(model)
    if encoder is not None:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass
    return max(1, math.ceil(len(text) / _CHARS_PER_TOKEN))


def count_message_tokens(
    messages: Iterable[dict],
    model: str | None = None,
) -> int:
    """Approximate the number of tokens a chat request consumes."""
    total = 2  # priming tokens the chat format adds
    for message in messages:
        total += _MESSAGE_OVERHEAD_TOKENS
        content = message.get("content", "")
        if isinstance(content, list):
            # Multimodal content parts: count textual parts only.
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    total += count_tokens(part["text"], model)
        else:
            total += count_tokens(str(content), model)
    return total


def truncate_text(text: str | None, max_tokens: int, model: str | None = None) -> str:
    """Trim ``text`` so it fits ``max_tokens`` (keeps the head)."""
    if not text or max_tokens <= 0:
        return ""
    if count_tokens(text, model) <= max_tokens:
        return text
    encoder = _get_encoder(model)
    if encoder is not None:
        try:
            return encoder.decode(encoder.encode(text)[:max_tokens])
        except Exception:
            pass
    max_chars = max(1, int(max_tokens * _CHARS_PER_TOKEN))
    return text[:max_chars]


@dataclass
class TokenBudget:
    """Input budget derived from a model's full context window."""

    context_window: int
    max_output_tokens: int = 1024
    reserved_tokens: int = 256

    @property
    def input_budget(self) -> int:
        return max(0, self.context_window - self.max_output_tokens - self.reserved_tokens)

    def fits(self, tokens: int) -> bool:
        return tokens <= self.input_budget

    def remaining(self, tokens: int) -> int:
        return self.input_budget - tokens

    def truncate(self, text: str, model: str | None = None, share: float = 1.0) -> str:
        return truncate_text(text, max(0, int(self.input_budget * share)), model)
