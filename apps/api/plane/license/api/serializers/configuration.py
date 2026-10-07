# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from .base import BaseSerializer
from plane.license.models import InstanceConfiguration
from plane.license.utils.encryption import MASKED_VALUE


class InstanceConfigurationSerializer(BaseSerializer):
    class Meta:
        model = InstanceConfiguration
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Never return stored secrets in plaintext. Report whether a value is set
        # so the admin UI can render a "configured" state without exposing it.
        if instance.is_encrypted:
            data["is_set"] = bool(instance.value)
            data["value"] = MASKED_VALUE if instance.value else ""

        return data
