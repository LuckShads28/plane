# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings

# Third party imports
from rest_framework.throttling import SimpleRateThrottle


class AIServiceThrottle(SimpleRateThrottle):
    """Per-user throttle for AI endpoints (default 50 requests/month)."""

    scope = "ai"

    def get_rate(self):
        return getattr(settings, "AI_RATE_LIMIT", "50/month")

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return f"throttle_ai_{user.id}"
