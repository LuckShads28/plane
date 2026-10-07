# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Usage logging for AI calls (quotas, auditing, cost tracking)."""

from __future__ import annotations

from typing import Any


def log_ai_task(
    *,
    task: str,
    workspace=None,
    project=None,
    user=None,
    provider: str | None = None,
    model: str | None = None,
    status: str = "success",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: int = 0,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort AI usage log; never raises into the caller."""
    try:
        from plane.db.models import AITaskLog

        AITaskLog.objects.create(
            workspace=workspace,
            project=project,
            user=user,
            task=task,
            provider=provider,
            model=model,
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            error=error,
            metadata=metadata or {},
        )
    except Exception:
        pass
