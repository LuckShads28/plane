# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Embedding index maintenance for semantic search / RAG."""

from __future__ import annotations

import hashlib

from plane.db.models import AIContextEmbedding, Cycle, Issue, IssueComment, Module, Page, Project, Workspace
from plane.utils.exception_logger import log_exception

from .chunking import split_text
from .client import embed
from .config import get_ai_config
from .tokens import count_tokens

SUPPORTED_ENTITY_TYPES = ("work_item", "comment", "page", "project", "cycle", "module")


def _user_label(user) -> str:
    if user is None:
        return "Unassigned"
    return getattr(user, "display_name", None) or getattr(user, "email", None) or getattr(user, "username", "")


def get_entity_content(entity_type: str, entity_id: str) -> tuple[str, str | None, str] | None:
    """Return ``(workspace_id, project_id, text)`` for an entity, or ``None``."""
    if entity_type == "work_item":
        issue = (
            Issue.objects.filter(id=entity_id, deleted_at__isnull=True)
            .select_related("project", "state", "created_by")
            .prefetch_related("assignees", "labels")
            .first()
        )
        if not issue:
            return None
        assignees = ", ".join(_user_label(user) for user in issue.assignees.all()) or "Unassigned"
        labels = ", ".join(label.name for label in issue.labels.all()) or "None"
        state_name = issue.state.name if issue.state else "None"
        text = (
            f"Work item {issue.project.identifier}-{issue.sequence_id}: {issue.name}\n"
            f"Project: {issue.project.name}\n"
            f"State: {state_name}\n"
            f"Priority: {issue.priority}\n"
            f"Assignees: {assignees}\n"
            f"Labels: {labels}\n"
            f"Created by: {_user_label(issue.created_by)}\n"
            f"Start date: {issue.start_date or 'None'}\n"
            f"Target date: {issue.target_date or 'None'}\n"
            f"Description:\n{issue.description_stripped or ''}"
        )
        return str(issue.workspace_id), str(issue.project_id), text

    if entity_type == "comment":
        comment = (
            IssueComment.objects.filter(id=entity_id, deleted_at__isnull=True)
            .select_related("actor", "issue", "issue__project")
            .first()
        )
        if not comment:
            return None
        issue = comment.issue
        text = (
            f"Comment by {_user_label(comment.actor)} on work item "
            f"{issue.project.identifier}-{issue.sequence_id} ({issue.name}):\n{comment.comment_stripped or ''}"
        )
        return str(comment.workspace_id), str(comment.project_id), text

    if entity_type == "page":
        page = Page.objects.filter(id=entity_id, deleted_at__isnull=True).first()
        if not page:
            return None
        return (
            str(page.workspace_id),
            str(page.project_id) if page.project_id else None,
            f"{page.name}\n{page.description_stripped or ''}",
        )

    if entity_type == "project":
        project = Project.objects.filter(id=entity_id, deleted_at__isnull=True).first()
        if not project:
            return None
        return str(project.workspace_id), str(project.id), f"{project.name}\n{project.description or ''}"

    if entity_type == "cycle":
        cycle = Cycle.objects.filter(id=entity_id, deleted_at__isnull=True).select_related("project").first()
        if not cycle:
            return None
        return str(cycle.workspace_id), str(cycle.project_id), f"{cycle.name}\n{cycle.description or ''}"

    if entity_type == "module":
        module = Module.objects.filter(id=entity_id, deleted_at__isnull=True).select_related("project").first()
        if not module:
            return None
        return str(module.workspace_id), str(module.project_id), f"{module.name}\n{module.description or ''}"

    return None


def delete_entity_embeddings(entity_type: str, entity_id: str) -> int:
    return AIContextEmbedding.objects.filter(entity_type=entity_type, entity_id=str(entity_id)).delete(soft=False)[0]


def schedule_entity_embedding(entity_type: str, entity_id: str) -> None:
    """Best-effort enqueue of an embedding refresh after a write."""
    try:
        from plane.bgtasks.ai_embedding_task import embed_entity_task

        embed_entity_task.delay(entity_type, str(entity_id))
    except Exception as exc:
        log_exception(exc)


def index_entity(entity_type: str, entity_id: str) -> int:
    """(Re)build embeddings for a single entity. Returns the number of chunks."""
    content = get_entity_content(entity_type, entity_id)
    if content is None:
        return 0
    workspace_id, project_id, text = content
    if not text or not text.strip():
        return 0

    workspace = Workspace.objects.filter(id=workspace_id).first()
    if workspace is None:
        return 0

    config = get_ai_config(workspace)
    if not config.embedding_model:
        return 0

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = AIContextEmbedding.objects.filter(entity_type=entity_type, entity_id=str(entity_id)).first()
    if existing and existing.content_hash == content_hash and existing.embedding_model == config.embedding_model:
        return 0

    AIContextEmbedding.objects.filter(entity_type=entity_type, entity_id=str(entity_id)).delete(soft=False)

    max_tokens = max(64, config.embedding_max_tokens - 8)
    chunks = split_text(text, max_tokens=max_tokens, overlap_tokens=min(64, max_tokens // 8), model=config.model)
    chunks = [chunk for chunk in chunks if chunk.strip()]
    if not chunks:
        return 0

    try:
        vectors = embed(chunks, config=config)
    except Exception as exc:
        log_exception(exc)
        raise

    rows = []
    for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
        rows.append(
            AIContextEmbedding(
                workspace_id=workspace_id,
                project_id=project_id,
                entity_type=entity_type,
                entity_id=str(entity_id),
                chunk_index=index,
                content_hash=content_hash,
                text=chunk,
                embedding=vector,
                embedding_model=config.embedding_model,
                embedding_dimensions=len(vector),
                token_count=count_tokens(chunk, config.model),
            )
        )
    AIContextEmbedding.objects.bulk_create(rows, batch_size=100)
    return len(rows)


def reindex_workspace(workspace_id: str, *, limit: int | None = None) -> int:
    """Reindex every supported entity in a workspace. Returns chunks written."""
    total = 0
    querysets = [
        ("work_item", Issue.objects.filter(workspace_id=workspace_id, deleted_at__isnull=True)),
        ("page", Page.objects.filter(workspace_id=workspace_id, deleted_at__isnull=True)),
        ("comment", IssueComment.objects.filter(workspace_id=workspace_id, deleted_at__isnull=True)),
        ("project", Project.objects.filter(workspace_id=workspace_id, deleted_at__isnull=True)),
        ("cycle", Cycle.objects.filter(workspace_id=workspace_id, deleted_at__isnull=True)),
        ("module", Module.objects.filter(workspace_id=workspace_id, deleted_at__isnull=True)),
    ]
    for entity_type, queryset in querysets:
        ids = list(queryset.values_list("id", flat=True))
        if limit:
            ids = ids[:limit]
        for entity_id in ids:
            try:
                total += index_entity(entity_type, str(entity_id))
            except Exception as exc:
                log_exception(exc)
    return total
