# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import serializers

# Module imports
from plane.db.models import WorkspaceAIConfiguration
from plane.license.utils.encryption import MASKED_VALUE, encrypt_data
from plane.utils.ai.config import SUPPORTED_PROVIDER_IDS

from .base import BaseSerializer


class WorkspaceAIConfigurationSerializer(BaseSerializer):
    """Read/update a workspace's AI provider settings.

    The API key is write-only; ``api_key_configured`` reports whether one is
    stored without ever returning it.
    """

    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    api_key_configured = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceAIConfiguration
        fields = [
            "id",
            "workspace",
            "provider",
            "base_url",
            "model",
            "embedding_model",
            "embedding_dimensions",
            "embedding_max_tokens",
            "context_window",
            "max_output_tokens",
            "reserved_tokens",
            "temperature",
            "is_active",
            "api_key",
            "api_key_configured",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "api_key_configured", "created_at", "updated_at"]

    def get_api_key_configured(self, obj) -> bool:
        return bool(obj.api_key)

    def validate_provider(self, value):
        if value and value not in SUPPORTED_PROVIDER_IDS:
            raise serializers.ValidationError(
                f"Unsupported provider. Choose one of: {', '.join(SUPPORTED_PROVIDER_IDS)}"
            )
        return value

    def _encrypt_api_key(self, validated_data):
        api_key = validated_data.get("api_key", None)
        if api_key in (None, "", MASKED_VALUE):
            # Omit so create/update leaves the stored key untouched.
            validated_data.pop("api_key", None)
        else:
            validated_data["api_key"] = encrypt_data(api_key)
        return validated_data

    def create(self, validated_data):
        validated_data = self._encrypt_api_key(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._encrypt_api_key(validated_data)
        return super().update(instance, validated_data)
