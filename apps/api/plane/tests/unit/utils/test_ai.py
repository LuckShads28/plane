# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.utils.ai.chunking import split_text
from plane.utils.ai.client import fit_messages, parse_json
from plane.utils.ai.config import (
    AIConfig,
    _resolve_from_values,
    get_ai_config,
    normalize_provider,
)
from plane.utils.ai.exceptions import AIConfigurationError
from plane.utils.ai.providers import OpenAICompatibleProvider, get_provider
from plane.utils.ai.tokens import TokenBudget, count_message_tokens, count_tokens, truncate_text


@pytest.mark.unit
class TestTokenBudget:
    def test_input_budget_subtracts_output_and_reserve(self):
        budget = TokenBudget(context_window=65000, max_output_tokens=4096, reserved_tokens=256)
        assert budget.input_budget == 65000 - 4096 - 256

    def test_budget_never_negative(self):
        assert TokenBudget(context_window=100, max_output_tokens=1000).input_budget == 0

    def test_count_tokens_scales_with_length(self):
        short = count_tokens("hello")
        long = count_tokens("hello " * 100)
        assert short >= 1
        assert long > short

    def test_count_message_tokens_includes_overhead(self):
        messages = [{"role": "user", "content": "hello"}]
        assert count_message_tokens(messages) > count_tokens("hello")

    def test_truncate_text_respects_limit(self):
        text = "word " * 1000
        truncated = truncate_text(text, 10)
        assert count_tokens(truncated) <= 10


@pytest.mark.unit
class TestChunking:
    def test_split_respects_max_tokens(self):
        text = "\n\n".join(f"Paragraph number {i} with some words." for i in range(50))
        chunks = split_text(text, max_tokens=20)
        assert chunks
        assert all(count_tokens(chunk) <= 20 for chunk in chunks)

    def test_empty_text_returns_no_chunks(self):
        assert split_text("", max_tokens=100) == []
        assert split_text(None, max_tokens=100) == []


@pytest.mark.unit
class TestParseJson:
    def test_parses_plain_json(self):
        assert parse_json('{"a": 1}') == {"a": 1}

    def test_parses_fenced_json_with_prose(self):
        raw = 'Here you go:\n```json\n{"name": "Test", "priority": "high"}\n```'
        assert parse_json(raw)["name"] == "Test"

    def test_extracts_json_object_from_surrounding_text(self):
        raw = 'Sure: {"subtasks": [{"name": "one"}]} thanks'
        assert parse_json(raw)["subtasks"][0]["name"] == "one"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            parse_json("no json here")


@pytest.mark.unit
class TestFitMessages:
    def test_small_request_is_unchanged(self):
        config = AIConfig(context_window=10000, max_output_tokens=500, reserved_tokens=100)
        messages = [{"role": "user", "content": "hello"}]
        assert fit_messages(messages, config) == messages

    def test_oversized_history_drops_oldest_turns(self):
        config = AIConfig(context_window=120, max_output_tokens=10, reserved_tokens=10)
        messages = [{"role": "user", "content": f"message {i} " * 20} for i in range(10)]
        fitted = fit_messages(messages, config)
        assert len(fitted) < len(messages)
        assert fitted[-1]["content"].startswith("message 9")


@pytest.mark.unit
class TestConfig:
    def test_normalize_provider_aliases(self):
        assert normalize_provider("azure") == "openai-compatible"
        assert normalize_provider("Ollama") == "ollama"
        assert normalize_provider("openai") == "openai"

    def test_unknown_provider_raises(self):
        with pytest.raises(AIConfigurationError):
            normalize_provider("does-not-exist")

    def test_resolve_uses_provider_defaults(self):
        config = _resolve_from_values({"provider": "ollama"}, source="test")
        assert config.base_url == "http://localhost:11434/v1"
        assert config.embedding_dimensions == 768

    def test_ollama_is_configured_without_api_key(self):
        config = _resolve_from_values({"provider": "ollama", "base_url": "http://box:11434/v1"}, source="test")
        assert config.configured is True

    def test_openai_requires_api_key(self):
        assert _resolve_from_values({"provider": "openai"}, source="test").configured is False

    def test_get_ai_config_reads_instance_values(self, monkeypatch):
        def fake_get_configuration_value(keys):
            values = {
                "LLM_API_KEY": "sk-test",
                "LLM_PROVIDER": "openai",
                "LLM_MODEL": "gpt-4o-mini",
                "LLM_BASE_URL": "",
                "LLM_EMBEDDING_MODEL": "text-embedding-3-small",
                "LLM_EMBEDDING_DIMENSIONS": "1536",
                "LLM_EMBEDDING_MAX_TOKENS": "8191",
                "LLM_CONTEXT_WINDOW": "65000",
                "LLM_MAX_OUTPUT_TOKENS": "2048",
                "LLM_RESERVED_TOKENS": "128",
                "LLM_TEMPERATURE": "0.1",
            }
            return tuple(values[key["key"]] if values[key["key"]] != "" else key["default"] for key in keys)

        monkeypatch.setattr("plane.license.utils.instance_value.get_configuration_value", fake_get_configuration_value)
        config = get_ai_config()
        assert config.source == "instance"
        assert config.context_window == 65000
        assert config.max_output_tokens == 2048
        assert config.embedding_model == "text-embedding-3-small"
        assert config.configured is True


@pytest.mark.unit
class TestProviderRegistry:
    def test_openai_and_ollama_use_compatible_provider(self):
        assert isinstance(get_provider(AIConfig(provider="openai")), OpenAICompatibleProvider)
        assert isinstance(get_provider(AIConfig(provider="ollama")), OpenAICompatibleProvider)
