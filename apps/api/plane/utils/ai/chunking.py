# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Text chunking for embeddings.

Chunk sizes are derived from the configured embedding model's input limit
(``embedding_max_tokens``) rather than a literal, so switching between a 512
token and an 8191 token embedding model needs no code change.
"""

from __future__ import annotations

import re

from .tokens import count_tokens

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_units(text: str) -> list[str]:
    units: list[str] = []
    for paragraph in _PARAGRAPH_SPLIT.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if count_tokens(paragraph) <= 0:
            continue
        units.append(paragraph)
    return units


def _hard_split(text: str, max_tokens: int, model: str | None) -> list[str]:
    """Last-resort split for a single oversized unit."""
    chunks: list[str] = []
    sentences = _SENTENCE_SPLIT.split(text)
    buffer = ""
    for sentence in sentences:
        candidate = f"{buffer} {sentence}".strip() if buffer else sentence
        if count_tokens(candidate, model) <= max_tokens:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
        if count_tokens(sentence, model) <= max_tokens:
            buffer = sentence
            continue
        # A single sentence still overflows: split by characters.
        approx_chars = max(1, int(max_tokens * 3.5))
        for start in range(0, len(sentence), approx_chars):
            chunks.append(sentence[start : start + approx_chars])
        buffer = ""
    if buffer:
        chunks.append(buffer)
    return chunks


def split_text(
    text: str | None,
    *,
    max_tokens: int,
    overlap_tokens: int = 0,
    model: str | None = None,
) -> list[str]:
    """Split ``text`` into chunks no larger than ``max_tokens``."""
    if not text or max_tokens <= 0:
        return []

    chunks: list[str] = []
    buffer = ""

    for unit in _split_units(text):
        if count_tokens(unit, model) > max_tokens:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_hard_split(unit, max_tokens, model))
            continue

        candidate = f"{buffer}\n\n{unit}" if buffer else unit
        if count_tokens(candidate, model) <= max_tokens:
            buffer = candidate
        else:
            if buffer:
                chunks.append(buffer)
            buffer = unit

    if buffer:
        chunks.append(buffer)

    if overlap_tokens > 0 and len(chunks) > 1:
        chunks = _apply_overlap(chunks, overlap_tokens, model)

    return [chunk for chunk in chunks if chunk.strip()]


def _apply_overlap(chunks: list[str], overlap_tokens: int, model: str | None) -> list[str]:
    """Prepend the tail of the previous chunk to preserve context."""
    result = [chunks[0]]
    for previous, current in zip(chunks, chunks[1:]):
        tail = previous[-max(1, int(overlap_tokens * 3.5)) :]
        combined = f"{tail}\n{current}"
        if count_tokens(combined, model) <= count_tokens(current, model) + overlap_tokens:
            result.append(combined)
        else:
            result.append(current)
    return result
