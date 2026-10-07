# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
AI configuration resolution.

Order of precedence (most specific wins):
    1. Per-workspace ``WorkspaceAIConfiguration`` (encrypted API key)
    2. Instance-level configuration (admin UI / env vars)
    3. Built-in defaults for the selected provider

Every numeric knob that controls context length is configurable, so a local
model limited to 65000 tokens is configured with ``context_window=65000`` while
a cloud model can use its native window.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .exceptions import AIConfigurationError

# ---------------------------------------------------------------------------
# Provider presets
# ---------------------------------------------------------------------------

# Defaults applied when the configuration does not specify a value.
PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "openai": {
        "base_url": None,
        "model": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "embedding_max_tokens": 8191,
        "context_window": 128000,
        "max_output_tokens": 4096,
    },
    "openai-compatible": {
        "base_url": None,
        "model": "gpt-4o-mini",
        "embedding_model": "",
        "embedding_dimensions": 1536,
        "embedding_max_tokens": 8191,
        "context_window": 128000,
        "max_output_tokens": 4096,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.1",
        "embedding_model": "nomic-embed-text",
        "embedding_dimensions": 768,
        "embedding_max_tokens": 8192,
        "context_window": 8192,
        "max_output_tokens": 2048,
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-3-5-sonnet-20240620",
        "embedding_model": "",
        "embedding_dimensions": 1536,
        "embedding_max_tokens": 8191,
        "context_window": 200000,
        "max_output_tokens": 4096,
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com",
        "model": "gemini-1.5-pro-latest",
        "embedding_model": "text-embedding-004",
        "embedding_dimensions": 768,
        "embedding_max_tokens": 2048,
        "context_window": 1000000,
        "max_output_tokens": 8192,
    },
}

SUPPORTED_PROVIDER_IDS = tuple(PROVIDER_DEFAULTS.keys())

# Config keys persisted through the instance configuration system.
INSTANCE_CONFIG_KEYS = (
    "LLM_API_KEY",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_BASE_URL",
    "LLM_EMBEDDING_MODEL",
    "LLM_EMBEDDING_DIMENSIONS",
    "LLM_EMBEDDING_MAX_TOKENS",
    "LLM_CONTEXT_WINDOW",
    "LLM_MAX_OUTPUT_TOKENS",
    "LLM_RESERVED_TOKENS",
    "LLM_TEMPERATURE",
)

DEFAULT_RESERVED_TOKENS = 256
DEFAULT_TEMPERATURE = 0.2


def normalize_provider(value: str | None) -> str:
    provider = (value or "openai").strip().lower()
    aliases = {
        "azure": "openai-compatible",
        "azure_openai": "openai-compatible",
        "openai_compatible": "openai-compatible",
        "local": "openai-compatible",
        "vllm": "openai-compatible",
        "lmstudio": "openai-compatible",
    }
    provider = aliases.get(provider, provider)
    if provider not in PROVIDER_DEFAULTS:
        raise AIConfigurationError(f"Unsupported LLM provider: {value}")
    return provider


def _as_int(value: Any, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class AIConfig:
    provider: str = "openai"
    api_key: str = ""
    base_url: str | None = None
    model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_max_tokens: int = 8191
    context_window: int = 128000
    max_output_tokens: int = 4096
    reserved_tokens: int = DEFAULT_RESERVED_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    source: str = "defaults"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        """A provider is usable when it has a model and, unless local, a key."""
        if not self.model:
            return False
        if self.provider in ("anthropic", "openai"):
            return bool(self.api_key)
        # openai-compatible / ollama may run without auth; require a base_url.
        if self.provider in ("openai-compatible", "ollama"):
            return bool(self.base_url)
        return bool(self.api_key)

    def redacted(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "source": self.source,
        }


def _resolve_from_values(values: dict[str, Any], source: str) -> AIConfig:
    provider = normalize_provider(values.get("provider"))
    defaults = PROVIDER_DEFAULTS[provider]

    base_url = values.get("base_url") or defaults.get("base_url")
    model = values.get("model") or defaults.get("model")
    embedding_model = values.get("embedding_model") or defaults.get("embedding_model")

    return AIConfig(
        provider=provider,
        api_key=(values.get("api_key") or "").strip(),
        base_url=base_url,
        model=model,
        embedding_model=embedding_model,
        embedding_dimensions=_as_int(
            values.get("embedding_dimensions"), defaults.get("embedding_dimensions", 1536)
        ),
        embedding_max_tokens=_as_int(
            values.get("embedding_max_tokens"), defaults.get("embedding_max_tokens", 8191)
        ),
        context_window=_as_int(values.get("context_window"), defaults.get("context_window", 128000)),
        max_output_tokens=_as_int(
            values.get("max_output_tokens"), defaults.get("max_output_tokens", 4096)
        ),
        reserved_tokens=_as_int(values.get("reserved_tokens"), DEFAULT_RESERVED_TOKENS),
        temperature=_as_float(values.get("temperature"), DEFAULT_TEMPERATURE),
        source=source,
    )


def _instance_values() -> dict[str, Any] | None:
    """Read instance config; returns ``None`` when nothing is configured."""
    from plane.license.utils.instance_value import get_configuration_value

    (
        api_key,
        provider,
        model,
        base_url,
        embedding_model,
        embedding_dimensions,
        embedding_max_tokens,
        context_window,
        max_output_tokens,
        reserved_tokens,
        temperature,
    ) = get_configuration_value(
        [
            {"key": "LLM_API_KEY", "default": os.environ.get("LLM_API_KEY")},
            {"key": "LLM_PROVIDER", "default": os.environ.get("LLM_PROVIDER", "openai")},
            {"key": "LLM_MODEL", "default": os.environ.get("LLM_MODEL")},
            {"key": "LLM_BASE_URL", "default": os.environ.get("LLM_BASE_URL")},
            {"key": "LLM_EMBEDDING_MODEL", "default": os.environ.get("LLM_EMBEDDING_MODEL")},
            {
                "key": "LLM_EMBEDDING_DIMENSIONS",
                "default": os.environ.get("LLM_EMBEDDING_DIMENSIONS"),
            },
            {
                "key": "LLM_EMBEDDING_MAX_TOKENS",
                "default": os.environ.get("LLM_EMBEDDING_MAX_TOKENS"),
            },
            {"key": "LLM_CONTEXT_WINDOW", "default": os.environ.get("LLM_CONTEXT_WINDOW")},
            {"key": "LLM_MAX_OUTPUT_TOKENS", "default": os.environ.get("LLM_MAX_OUTPUT_TOKENS")},
            {"key": "LLM_RESERVED_TOKENS", "default": os.environ.get("LLM_RESERVED_TOKENS")},
            {"key": "LLM_TEMPERATURE", "default": os.environ.get("LLM_TEMPERATURE")},
        ]
    )

    if not api_key and not base_url:
        return None

    return {
        "api_key": api_key,
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "embedding_model": embedding_model,
        "embedding_dimensions": embedding_dimensions,
        "embedding_max_tokens": embedding_max_tokens,
        "context_window": context_window,
        "max_output_tokens": max_output_tokens,
        "reserved_tokens": reserved_tokens,
        "temperature": temperature,
    }


def _workspace_values(workspace) -> dict[str, Any] | None:
    """Read an active per-workspace configuration, if one exists."""
    if workspace is None:
        return None
    try:
        from plane.db.models import WorkspaceAIConfiguration
        from plane.license.utils.encryption import decrypt_data
    except ImportError:
        return None

    try:
        config = WorkspaceAIConfiguration.objects.filter(workspace=workspace).first()
    except Exception:
        return None
    if config is None or not config.is_active:
        return None

    api_key = decrypt_data(config.api_key) if config.api_key else ""
    if not api_key and not config.base_url:
        return None

    return {
        "api_key": api_key,
        "provider": config.provider,
        "model": config.model,
        "base_url": config.base_url,
        "embedding_model": config.embedding_model,
        "embedding_dimensions": config.embedding_dimensions,
        "embedding_max_tokens": config.embedding_max_tokens,
        "context_window": config.context_window,
        "max_output_tokens": config.max_output_tokens,
        "reserved_tokens": config.reserved_tokens,
        "temperature": config.temperature,
    }


def get_ai_config(workspace=None) -> AIConfig:
    """Resolve the effective AI configuration for a workspace."""
    workspace_values = _workspace_values(workspace)
    if workspace_values:
        return _resolve_from_values(workspace_values, source="workspace")

    instance_values = _instance_values()
    if instance_values:
        return _resolve_from_values(instance_values, source="instance")

    # Nothing configured: return defaults so callers can report `configured`.
    return _resolve_from_values({}, source="defaults")
