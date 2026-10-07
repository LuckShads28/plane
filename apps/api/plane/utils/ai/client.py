# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
High-level AI client.

Callers pass plain chat messages; this module resolves the provider, fits the
request into the configured context window, and returns text/JSON/embeddings.
"""

from __future__ import annotations

import json
import re
from typing import Iterator, Sequence

from .config import AIConfig, get_ai_config
from .exceptions import AIBudgetError, AIConfigurationError
from .providers import get_provider
from .tokens import TokenBudget, count_message_tokens, truncate_text

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _require_configured(config: AIConfig) -> None:
    if not config.configured:
        raise AIConfigurationError(
            "AI is not configured. Set an LLM provider, model, and API key in "
            "workspace AI settings or instance configuration."
        )


def fit_messages(messages: list[dict], config: AIConfig) -> list[dict]:
    """Trim messages so the request fits the configured context window."""
    budget = TokenBudget(
        context_window=config.context_window,
        max_output_tokens=config.max_output_tokens,
        reserved_tokens=config.reserved_tokens,
    )

    if budget.fits(count_message_tokens(messages, config.model)):
        return messages

    system = [message for message in messages if message.get("role") == "system"]
    conversation = [message for message in messages if message.get("role") != "system"]

    # Drop the oldest turns first, always keeping at least the latest message.
    while len(conversation) > 1 and not budget.fits(
        count_message_tokens(system + conversation, config.model)
    ):
        conversation = conversation[1:]

    if conversation and not budget.fits(count_message_tokens(system + conversation, config.model)):
        available = max(0, budget.input_budget - count_message_tokens(system, config.model) - 8)
        conversation[-1] = {
            **conversation[-1],
            "content": truncate_text(str(conversation[-1].get("content", "")), available, config.model),
        }

    fitted = system + conversation
    if not budget.fits(count_message_tokens(fitted, config.model)):
        raise AIBudgetError(
            "The prompt exceeds the configured context window. Increase "
            "LLM_CONTEXT_WINDOW or reduce the amount of context sent."
        )
    return fitted


def chat(
    messages: list[dict],
    *,
    workspace=None,
    config: AIConfig | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    config = config or get_ai_config(workspace)
    _require_configured(config)
    fitted = fit_messages(messages, config)
    return get_provider(config).chat(
        fitted, model=model, temperature=temperature, max_tokens=max_tokens
    )


def stream_chat(
    messages: list[dict],
    *,
    workspace=None,
    config: AIConfig | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Iterator[str]:
    config = config or get_ai_config(workspace)
    _require_configured(config)
    fitted = fit_messages(messages, config)
    yield from get_provider(config).stream_chat(
        fitted, model=model, temperature=temperature, max_tokens=max_tokens
    )


def parse_json(text: str | None) -> dict:
    """Extract a JSON object from a model response, tolerating prose/fences."""
    if not text:
        raise AIBudgetError("The model returned an empty response")
    fenced = _JSON_FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model response")
    return json.loads(candidate[start : end + 1])


def chat_json(
    messages: list[dict],
    *,
    workspace=None,
    config: AIConfig | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    """Run a chat call and parse the response as a JSON object."""
    raw = chat(
        messages,
        workspace=workspace,
        config=config,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return parse_json(raw)


def embed(
    texts: Sequence[str],
    *,
    workspace=None,
    config: AIConfig | None = None,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[list[float]]:
    config = config or get_ai_config(workspace)
    _require_configured(config)
    if not config.embedding_model:
        raise AIConfigurationError("No embedding model configured")
    return get_provider(config).embed(
        texts,
        model=model or config.embedding_model,
        dimensions=dimensions or config.embedding_dimensions,
    )
