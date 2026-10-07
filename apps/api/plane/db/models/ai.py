# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""AI models: workspace provider config, RAG embeddings, and usage logs."""

# Django imports
from django.db import models
from django.db.models import Q

# Third party imports
from pgvector.django import VectorField

# Module imports
from .base import BaseModel


class WorkspaceAIConfiguration(BaseModel):
    """Per-workspace AI provider configuration.

    When active, this takes precedence over the instance-level configuration
    (admin UI / env vars). ``api_key`` is stored encrypted using the instance
    ``SECRET_KEY`` (see ``plane.license.utils.encryption``).
    """

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="workspace_ai_configuration",
    )
    provider = models.CharField(max_length=32, default="openai")
    api_key = models.TextField(blank=True, null=True)
    base_url = models.CharField(max_length=512, blank=True, null=True)
    model = models.CharField(max_length=255, blank=True, null=True)
    embedding_model = models.CharField(max_length=255, blank=True, null=True)
    embedding_dimensions = models.PositiveIntegerField(default=1536)
    embedding_max_tokens = models.PositiveIntegerField(default=8191)
    context_window = models.PositiveIntegerField(default=128000)
    max_output_tokens = models.PositiveIntegerField(default=4096)
    reserved_tokens = models.PositiveIntegerField(default=256)
    temperature = models.FloatField(default=0.2)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Workspace AI Configuration"
        verbose_name_plural = "Workspace AI Configurations"
        db_table = "workspace_ai_configurations"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace"],
                condition=Q(deleted_at__isnull=True),
                name="workspace_ai_config_unique_workspace_when_not_deleted",
            )
        ]

    def __str__(self):
        return f"{self.workspace_id} - {self.provider}"


class AIContextEmbedding(BaseModel):
    """A single embedded chunk of workspace content for semantic search.

    ``embedding`` is intentionally dimension-unconstrained: different workspaces
    may use embedding models with different dimensions. Queries always filter by
    ``embedding_model`` so vectors of different dimensions are never compared.
    """

    class EntityType(models.TextChoices):
        WORK_ITEM = "work_item", "Work Item"
        COMMENT = "comment", "Comment"
        PAGE = "page", "Page"
        PROJECT = "project", "Project"
        CYCLE = "cycle", "Cycle"
        MODULE = "module", "Module"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="ai_embeddings")
    project = models.ForeignKey(
        "db.Project", on_delete=models.CASCADE, related_name="ai_embeddings", null=True, blank=True
    )
    entity_type = models.CharField(max_length=32, choices=EntityType.choices)
    entity_id = models.CharField(max_length=255, db_index=True)
    chunk_index = models.PositiveIntegerField(default=0)
    content_hash = models.CharField(max_length=64)
    text = models.TextField()
    embedding = VectorField(dimensions=None, null=True)
    embedding_model = models.CharField(max_length=255)
    embedding_dimensions = models.PositiveIntegerField(default=1536)
    token_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "AI Context Embedding"
        verbose_name_plural = "AI Context Embeddings"
        db_table = "ai_context_embeddings"
        constraints = [
            models.UniqueConstraint(
                fields=["entity_type", "entity_id", "chunk_index"],
                condition=Q(deleted_at__isnull=True),
                name="ai_embedding_unique_entity_chunk_when_not_deleted",
            )
        ]
        indexes = [
            models.Index(fields=["workspace", "entity_type"], name="ai_embed_ws_entity_idx"),
            models.Index(fields=["embedding_model"], name="ai_embed_model_idx"),
        ]

    def __str__(self):
        return f"{self.entity_type}:{self.entity_id}#{self.chunk_index}"


class AITaskLog(BaseModel):
    """Usage/audit log for every AI call (for quotas and cost tracking)."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        ERROR = "error", "Error"

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.SET_NULL,
        related_name="ai_task_logs",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        "db.Project", on_delete=models.SET_NULL, related_name="ai_task_logs", null=True, blank=True
    )
    user = models.ForeignKey(
        "db.User", on_delete=models.SET_NULL, related_name="ai_task_logs", null=True, blank=True
    )
    task = models.CharField(max_length=64)
    provider = models.CharField(max_length=32, blank=True, null=True)
    model = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUCCESS)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "AI Task Log"
        verbose_name_plural = "AI Task Logs"
        db_table = "ai_task_logs"
        indexes = [
            models.Index(fields=["workspace", "user", "created_at"], name="ai_task_log_ws_user_idx"),
        ]

    def __str__(self):
        return f"{self.task} - {self.status}"
