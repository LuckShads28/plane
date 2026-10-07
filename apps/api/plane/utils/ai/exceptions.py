# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.


class AIError(Exception):
    """Base class for every AI-layer failure."""


class AIConfigurationError(AIError):
    """Raised when no usable provider configuration could be resolved."""


class AIUnsupportedError(AIError):
    """Raised when a provider cannot perform the requested operation."""


class AIProviderError(AIError):
    """Raised when the upstream provider rejects or fails a request."""

    def __init__(self, message: str, *, provider: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class AIBudgetError(AIError):
    """Raised when the prompt cannot be made to fit the model context window."""
