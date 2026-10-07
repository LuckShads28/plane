# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Pluggable AI layer for Plane.

Public entry points live in ``plane.utils.ai.client``. Providers are resolved at
runtime from workspace/instance configuration so the same code path serves cloud
(OpenAI, Anthropic, Gemini) and local OpenAI-compatible servers (Ollama, vLLM,
LM Studio, ...).
"""

from .client import chat, chat_json, embed, stream_chat
from .config import AIConfig, get_ai_config
from .exceptions import (
    AIBudgetError,
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIUnsupportedError,
)
from .tokens import TokenBudget, count_tokens, count_message_tokens

__all__ = [
    "AIConfig",
    "AIBudgetError",
    "AIConfigurationError",
    "AIError",
    "AIProviderError",
    "AIUnsupportedError",
    "TokenBudget",
    "chat",
    "chat_json",
    "count_message_tokens",
    "count_tokens",
    "embed",
    "get_ai_config",
    "stream_chat",
]
