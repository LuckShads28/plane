# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""AI endpoints: workspace provider settings, editor tasks, copilot, triage, RAG."""

# Python imports
import json
import re
import time

# Django imports
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueCreateSerializer, IssueDetailSerializer, WorkspaceAIConfigurationSerializer
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import (
    AIContextEmbedding,
    Issue,
    IssueComment,
    Label,
    Page,
    Project,
    ProjectMember,
    State,
    Workspace,
    WorkspaceAIConfiguration,
    WorkspaceMember,
)
from plane.throttles.ai import AIServiceThrottle
from plane.utils.ai import chat, chat_json, get_ai_config
from plane.utils.ai.exceptions import AIBudgetError, AIConfigurationError, AIError
from plane.utils.ai.prompts import (
    build_ask_messages,
    build_assistant_messages,
    build_copilot_messages,
    build_editor_messages,
    build_triage_messages,
    copilot_result_to_html,
)
from plane.utils.ai.usage import log_ai_task
from plane.utils.ai.client import embed, parse_json
from plane.utils.exception_logger import log_exception
from plane.utils.host import base_host
from plane.utils.issue_search import search_issues

from ..base import BaseAPIView


def _error_response(exc: Exception) -> Response:
    if isinstance(exc, AIConfigurationError):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, AIBudgetError):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, AIError):
        log_exception(exc)
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    if isinstance(exc, ValueError):
        # Unparseable model output (e.g. prose where JSON was required).
        log_exception(exc)
        return Response(
            {"error": "The AI returned an unexpected response. Please try again."},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    log_exception(exc)
    return Response({"error": "An internal error has occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_workspace(slug):
    return Workspace.objects.filter(slug=slug).first()


def _project_context(project):
    labels = list(Label.objects.filter(project=project).values_list("name", flat=True))
    members = list(
        ProjectMember.objects.filter(project=project, is_active=True).select_related("member")
    )
    member_names = []
    for membership in members:
        user = membership.member
        member_names.append(getattr(user, "display_name", None) or user.email)
    return labels, member_names


def _resolve_labels(project, names):
    if not names:
        return []
    labels = Label.objects.filter(project=project)
    by_name = {label.name.strip().lower(): str(label.id) for label in labels}
    resolved = []
    for name in names:
        if not isinstance(name, str):
            continue
        label_id = by_name.get(name.strip().lower())
        if label_id:
            resolved.append(label_id)
    return resolved


def _resolve_assignee(project, hint):
    if not hint:
        return None
    hint = str(hint).strip().lower()
    for membership in ProjectMember.objects.filter(project=project, is_active=True).select_related("member"):
        user = membership.member
        candidates = {
            (user.email or "").lower(),
            (getattr(user, "display_name", "") or "").lower(),
            (getattr(user, "first_name", "") or "").lower(),
            (getattr(user, "last_name", "") or "").lower(),
        }
        if hint in candidates:
            return str(user.id)
    return None


def _retrieve_chunks(workspace, query, *, project_id=None, limit=8):
    """Return context chunks for RAG, preferring vector search with an ILIKE fallback."""
    config = get_ai_config(workspace)
    chunks = []

    if config.embedding_model:
        try:
            query_vector = embed([query], config=config)[0]
            qs = AIContextEmbedding.objects.filter(
                workspace=workspace,
                embedding_model=config.embedding_model,
                embedding__isnull=False,
            )
            if project_id:
                qs = qs.filter(Q(project_id=project_id) | Q(project__isnull=True))
            from pgvector.django import CosineDistance

            rows = (
                qs.annotate(distance=CosineDistance("embedding", query_vector))
                .order_by("distance")
                .select_related("project")[:limit]
            )
            for row in rows:
                chunks.append(
                    {
                        "entity_type": row.entity_type,
                        "entity_id": row.entity_id,
                        "project_id": str(row.project_id) if row.project_id else None,
                        "text": row.text,
                        "label": f"{row.entity_type} {row.entity_id}",
                    }
                )
            if chunks:
                return chunks
        except Exception as exc:
            log_exception(exc)

    # Fallback: keyword search across work items, pages, and comments.
    if project_id:
        issues = search_issues(query, Issue.objects.filter(project_id=project_id, deleted_at__isnull=True))[:limit]
    else:
        issues = search_issues(query, Issue.objects.filter(workspace=workspace, deleted_at__isnull=True))[:limit]
    for issue in issues:
        text = f"{issue.name}\n{issue.description_stripped or ''}".strip()
        chunks.append(
            {
                "entity_type": "work_item",
                "entity_id": str(issue.id),
                "project_id": str(issue.project_id),
                "text": text[:4000],
                "label": f"{issue.project.identifier}-{issue.sequence_id} {issue.name}",
            }
        )

    pages = Page.objects.filter(workspace=workspace, deleted_at__isnull=True).filter(
        Q(name__icontains=query) | Q(description_stripped__icontains=query)
    )[: max(0, limit - len(chunks))]
    for page in pages:
        text = f"{page.name}\n{page.description_stripped or ''}".strip()
        chunks.append(
            {
                "entity_type": "page",
                "entity_id": str(page.id),
                "project_id": str(page.project_id) if page.project_id else None,
                "text": text[:4000],
                "label": f"page {page.name}",
            }
        )

    if not chunks:
        comments = IssueComment.objects.filter(workspace=workspace, deleted_at__isnull=True).filter(
            comment_stripped__icontains=query
        )[:limit]
        for comment in comments:
            chunks.append(
                {
                    "entity_type": "comment",
                    "entity_id": str(comment.id),
                    "project_id": str(comment.project_id),
                    "text": (comment.comment_stripped or "")[:4000],
                    "label": f"comment on {comment.issue_id}",
                }
            )

    return chunks


class WorkspaceAIConfigurationEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        workspace = _get_workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        config = WorkspaceAIConfiguration.objects.filter(workspace=workspace).first()
        effective = get_ai_config(workspace)
        if config:
            data = dict(WorkspaceAIConfigurationSerializer(config).data)
        else:
            data = {
                "id": None,
                "workspace": str(workspace.id),
                "provider": effective.provider,
                "base_url": effective.base_url,
                "model": effective.model,
                "embedding_model": effective.embedding_model,
                "embedding_dimensions": effective.embedding_dimensions,
                "embedding_max_tokens": effective.embedding_max_tokens,
                "context_window": effective.context_window,
                "max_output_tokens": effective.max_output_tokens,
                "reserved_tokens": effective.reserved_tokens,
                "temperature": effective.temperature,
                "is_active": True,
                "api_key_configured": False,
            }
        data["effective"] = effective.redacted()
        return Response(data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def patch(self, request, slug):
        workspace = _get_workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        config = WorkspaceAIConfiguration.objects.filter(workspace=workspace).first()
        serializer = WorkspaceAIConfigurationSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if config is None:
            serializer.save(workspace=workspace)
        else:
            serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class RephraseGrammarEndpoint(BaseAPIView):
    throttle_classes = [AIServiceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        task = request.data.get("task")
        text_input = request.data.get("text_input", "")
        if not task:
            return Response({"error": "Task is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not text_input:
            return Response({"error": "Text input is required"}, status=status.HTTP_400_BAD_REQUEST)

        workspace = _get_workspace(slug)
        messages = build_editor_messages(
            task,
            text_input,
            casual_score=request.data.get("casual_score"),
            formal_score=request.data.get("formal_score"),
        )
        started = time.monotonic()
        try:
            response_text = chat(messages, workspace=workspace)
        except Exception as exc:
            log_ai_task(task=task, workspace=workspace, user=request.user, status="error", error=str(exc))
            return _error_response(exc)

        log_ai_task(
            task=task,
            workspace=workspace,
            user=request.user,
            provider=get_ai_config(workspace).provider,
            model=get_ai_config(workspace).model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return Response({"response": response_text}, status=status.HTTP_200_OK)


class WorkspaceAIChatEndpoint(BaseAPIView):
    throttle_classes = [AIServiceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = _get_workspace(slug)
        messages = request.data.get("messages")
        if not messages:
            prompt = request.data.get("prompt", "")
            if not prompt:
                return Response({"error": "prompt or messages is required"}, status=status.HTTP_400_BAD_REQUEST)
            messages = [{"role": "user", "content": prompt}]

        try:
            response_text = chat(messages, workspace=workspace)
        except Exception as exc:
            log_ai_task(task="chat", workspace=workspace, user=request.user, status="error", error=str(exc))
            return _error_response(exc)
        return Response({"response": response_text}, status=status.HTTP_200_OK)


class WorkItemCopilotEndpoint(BaseAPIView):
    throttle_classes = [AIServiceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        project = Project.objects.filter(pk=project_id, workspace__slug=slug).first()
        if project is None:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        prompt = request.data.get("prompt") or request.data.get("title") or ""
        if not prompt:
            return Response({"error": "prompt is required"}, status=status.HTTP_400_BAD_REQUEST)

        available_labels, available_members = _project_context(project)
        messages = build_copilot_messages(
            prompt=prompt,
            title=request.data.get("title"),
            description=request.data.get("description"),
            available_labels=available_labels,
            available_members=available_members,
            mode=request.data.get("mode", "full"),
        )

        started = time.monotonic()
        try:
            result = chat_json(messages, workspace=project.workspace)
        except Exception as exc:
            log_ai_task(
                task="copilot",
                workspace=project.workspace,
                project=project,
                user=request.user,
                status="error",
                error=str(exc),
            )
            return _error_response(exc)

        result["description_html"] = copilot_result_to_html(result)
        result["label_ids"] = _resolve_labels(project, result.get("labels") or [])
        assignee_id = _resolve_assignee(project, result.get("assignee_hint"))
        if assignee_id:
            result["assignee_ids"] = [assignee_id]

        log_ai_task(
            task="copilot",
            workspace=project.workspace,
            project=project,
            user=request.user,
            provider=get_ai_config(project.workspace).provider,
            model=get_ai_config(project.workspace).model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return Response(result, status=status.HTTP_200_OK)


class IntakeTriageEndpoint(BaseAPIView):
    throttle_classes = [AIServiceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        project = Project.objects.filter(pk=project_id, workspace__slug=slug).first()
        if project is None:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        name = request.data.get("name", "")
        description = request.data.get("description", "")
        if not name and not description:
            return Response({"error": "name or description is required"}, status=status.HTTP_400_BAD_REQUEST)

        available_labels, available_members = _project_context(project)
        duplicates_qs = search_issues(
            name or description,
            Issue.objects.filter(project=project, deleted_at__isnull=True).select_related("project"),
        )[:5]
        duplicate_candidates = [
            {"id": str(issue.id), "name": issue.name, "sequence_id": issue.sequence_id} for issue in duplicates_qs
        ]

        messages = build_triage_messages(
            name=name,
            description=description,
            available_labels=available_labels,
            available_members=available_members,
            duplicate_candidates=duplicate_candidates,
        )
        try:
            result = chat_json(messages, workspace=project.workspace)
        except Exception as exc:
            log_ai_task(
                task="triage",
                workspace=project.workspace,
                project=project,
                user=request.user,
                status="error",
                error=str(exc),
            )
            return _error_response(exc)

        result["label_ids"] = _resolve_labels(project, result.get("labels") or [])
        assignee_id = _resolve_assignee(project, result.get("assignee_hint"))
        if assignee_id:
            result["assignee_ids"] = [assignee_id]
        result["duplicate_candidates"] = duplicate_candidates
        return Response(result, status=status.HTTP_200_OK)


class WorkspaceAISearchEndpoint(BaseAPIView):
    throttle_classes = [AIServiceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = _get_workspace(slug)
        query = request.data.get("query", "")
        if not query:
            return Response({"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST)
        project_id = request.data.get("project_id")
        chunks = _retrieve_chunks(workspace, query, project_id=project_id)
        return Response({"results": chunks}, status=status.HTTP_200_OK)


class WorkspaceAIAskEndpoint(BaseAPIView):
    throttle_classes = [AIServiceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = _get_workspace(slug)
        question = request.data.get("question") or request.data.get("query") or ""
        if not question:
            return Response({"error": "question is required"}, status=status.HTTP_400_BAD_REQUEST)
        project_id = request.data.get("project_id")

        chunks = _retrieve_chunks(workspace, question, project_id=project_id)
        messages = build_ask_messages(question, chunks)
        try:
            answer = chat(messages, workspace=workspace)
        except Exception as exc:
            log_ai_task(task="ask", workspace=workspace, user=request.user, status="error", error=str(exc))
            return _error_response(exc)

        sources = [
            {
                "index": index,
                "entity_type": chunk.get("entity_type"),
                "entity_id": chunk.get("entity_id"),
                "project_id": chunk.get("project_id"),
                "label": chunk.get("label"),
            }
            for index, chunk in enumerate(chunks, start=1)
        ]
        return Response({"answer": answer, "sources": sources}, status=status.HTTP_200_OK)


def _resolve_workspace_assignee(workspace, hint):
    if not hint:
        return None
    hint = str(hint).strip().lower()
    for membership in WorkspaceMember.objects.filter(workspace=workspace, is_active=True).select_related("member"):
        user = membership.member
        candidates = {
            (user.email or "").lower(),
            (getattr(user, "display_name", "") or "").lower(),
            (getattr(user, "first_name", "") or "").lower(),
            (getattr(user, "last_name", "") or "").lower(),
            (user.username or "").lower(),
        }
        if hint in candidates:
            return str(user.id)
    return None


def _collect_assignee_hints(action):
    hints = action.get("assignee_hints")
    collected: list[str] = []
    if isinstance(hints, list):
        collected.extend(str(item).strip() for item in hints if item)
    single = action.get("assignee_hint")
    if single:
        collected.append(str(single).strip())
    seen = set()
    result = []
    for hint in collected:
        if hint and hint.lower() not in seen:
            seen.add(hint.lower())
            result.append(hint)
    return result


def _resolve_project(workspace, hint, fallback_project_id=None):
    projects = Project.objects.filter(workspace=workspace)
    if hint:
        hint = str(hint).strip().lower()
        for project in projects:
            if hint in {project.name.lower(), project.identifier.lower()}:
                return project
    if fallback_project_id:
        return projects.filter(id=fallback_project_id).first()
    return None


_WORK_ITEM_IDENTIFIER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-(\d+)$")


def _resolve_work_item(workspace, issue_hint, project_hint=None, fallback_project_id=None):
    if not issue_hint:
        return None
    # Accept "#TEST-8", "@TEST-8", "TEST-8" or a title.
    hint = str(issue_hint).strip().lstrip("#@").strip()
    queryset = (
        Issue.objects.filter(workspace=workspace, deleted_at__isnull=True)
        .select_related("project")
        .order_by("-created_at")
    )

    match = _WORK_ITEM_IDENTIFIER_RE.match(hint.upper())
    if match:
        identifier, sequence = match.group(1), int(match.group(2))
        issue = queryset.filter(project__identifier__iexact=identifier, sequence_id=sequence).first()
        if issue:
            return issue

    candidates = queryset.filter(name__icontains=hint)
    project = _resolve_project(workspace, project_hint, fallback_project_id) if project_hint else None
    if project:
        candidates = candidates.filter(project=project)
    elif fallback_project_id:
        candidates = candidates.filter(project_id=fallback_project_id)
    return candidates.first()


def _resolve_state(project, hint):
    if not hint or project is None:
        return None
    state = State.objects.filter(project=project, name__iexact=str(hint).strip()).first()
    return str(state.id) if state else None


def _ensure_project_member(project, user_id):
    """Make sure a workspace member is also a member of the project so assignment succeeds."""
    if project is None or not user_id:
        return
    existing = ProjectMember.all_objects.filter(project=project, member_id=user_id).first()
    if existing:
        existing.deleted_at = None
        existing.is_active = True
        existing.role = max(existing.role or 0, 15)
        existing.save(update_fields=["deleted_at", "is_active", "role"])
        return
    ProjectMember.objects.create(project=project, member_id=user_id, role=15, is_active=True)


def _serializer_errors(serializer) -> str:
    try:
        return "; ".join(f"{field}: {', '.join(str(e) for e in errors)}" for field, errors in serializer.errors.items())
    except Exception:
        return "Invalid data"


def _create_work_item_via_assistant(workspace, action, default_project_id, request):
    project = _resolve_project(workspace, action.get("project_hint"), default_project_id)
    if project is None:
        return {
            "type": "create_work_item",
            "status": "error",
            "name": action.get("name"),
            "error": "No matching project. Mention a project name or identifier.",
        }

    assignee_ids = []
    for hint in _collect_assignee_hints(action):
        assignee_id = _resolve_workspace_assignee(workspace, hint)
        if assignee_id and assignee_id not in assignee_ids:
            _ensure_project_member(project, assignee_id)
            assignee_ids.append(assignee_id)

    data = {
        "name": action.get("name") or "Untitled",
        "description_html": action.get("description_html") or "<p></p>",
        "priority": action.get("priority") or "none",
        "assignee_ids": assignee_ids,
    }
    if project.default_state_id:
        data["state_id"] = str(project.default_state_id)

    serializer = IssueCreateSerializer(
        data=data,
        context={
            "project_id": str(project.id),
            "workspace_id": str(workspace.id),
            "default_assignee_id": None,
        },
    )
    if not serializer.is_valid():
        return {
            "type": "create_work_item",
            "status": "error",
            "name": data["name"],
            "error": _serializer_errors(serializer),
        }
    issue = serializer.save()
    try:
        issue_activity.delay(
            type="issue.activity.created",
            requested_data=json.dumps({**data, "source": "pi"}, cls=DjangoJSONEncoder),
            current_instance=None,
            issue_id=str(issue.id),
            actor_id=str(request.user.id),
            project_id=str(project.id),
            epoch=int(timezone.now().timestamp()),
            notification=False,
            origin=base_host(request=request, is_app=True),
        )
    except Exception as exc:
        log_exception(exc)
    return {
        "type": "create_work_item",
        "status": "created",
        "issue_id": str(issue.id),
        "project_id": str(project.id),
        "name": issue.name,
        "code": f"{project.identifier}-{issue.sequence_id}",
    }


def _update_work_item_via_assistant(workspace, action, default_project_id, request):
    issue = _resolve_work_item(workspace, action.get("issue_hint"), action.get("project_hint"), default_project_id)
    if issue is None:
        return {
            "type": "update_work_item",
            "status": "error",
            "error": f"Work item not found: {action.get('issue_hint')}. Mention its ID (e.g. TEST-1).",
        }

    data = {}
    if action.get("name"):
        data["name"] = action["name"]
    if action.get("description_html"):
        data["description_html"] = action["description_html"]
    if action.get("priority"):
        data["priority"] = action["priority"]

    assignee_ids = []
    for hint in _collect_assignee_hints(action):
        assignee_id = _resolve_workspace_assignee(workspace, hint)
        if assignee_id and assignee_id not in assignee_ids:
            _ensure_project_member(issue.project, assignee_id)
            assignee_ids.append(assignee_id)
    if assignee_ids:
        data["assignee_ids"] = assignee_ids
    elif action.get("unassign"):
        data["assignee_ids"] = []
    if action.get("labels"):
        data["label_ids"] = _resolve_labels(issue.project, action.get("labels"))
    state_id = _resolve_state(issue.project, action.get("state_hint"))
    if state_id:
        data["state_id"] = state_id

    if not data:
        return {"type": "update_work_item", "status": "error", "name": issue.name, "error": "No changes specified."}

    current_instance = json.dumps(IssueDetailSerializer(issue).data, cls=DjangoJSONEncoder)
    serializer = IssueCreateSerializer(
        issue,
        data=data,
        partial=True,
        context={
            "project_id": str(issue.project_id),
            "workspace_id": str(issue.workspace_id),
            "default_assignee_id": None,
        },
    )
    if not serializer.is_valid():
        return {
            "type": "update_work_item",
            "status": "error",
            "name": issue.name,
            "error": _serializer_errors(serializer),
        }
    serializer.save()
    try:
        issue_activity.delay(
            type="issue.activity.updated",
            requested_data=json.dumps({**data, "source": "pi"}, cls=DjangoJSONEncoder),
            current_instance=current_instance,
            issue_id=str(issue.id),
            actor_id=str(request.user.id),
            project_id=str(issue.project_id),
            epoch=int(timezone.now().timestamp()),
            notification=False,
            origin=base_host(request=request, is_app=True),
        )
    except Exception as exc:
        log_exception(exc)

    issue.refresh_from_db()
    return {
        "type": "update_work_item",
        "status": "updated",
        "issue_id": str(issue.id),
        "project_id": str(issue.project_id),
        "name": issue.name,
        "code": f"{issue.project.identifier}-{issue.sequence_id}",
    }


class WorkspaceAIAssistantEndpoint(BaseAPIView):
    """Standalone assistant: chat + optional create-work-item action."""

    throttle_classes = [AIServiceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = _get_workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        messages = request.data.get("messages") or []
        if not isinstance(messages, list) or not messages:
            return Response({"error": "messages is required"}, status=status.HTTP_400_BAD_REQUEST)
        project_id = request.data.get("project_id")

        last_user = next(
            (message.get("content", "") for message in reversed(messages) if message.get("role") == "user"), ""
        )

        memberships = WorkspaceMember.objects.filter(workspace=workspace, is_active=True).select_related("member")
        member_names = [
            (getattr(m.member, "display_name", None) or m.member.email) for m in memberships
        ]
        projects = list(Project.objects.filter(workspace=workspace))
        project_names = [f"{project.name} ({project.identifier})" for project in projects]

        chunks = _retrieve_chunks(workspace, last_user, project_id=project_id)

        user = request.user
        display_name = getattr(user, "display_name", None) or f"{user.first_name} {user.last_name}".strip()
        current_user = " | ".join(
            str(bit)
            for bit in [display_name, user.email, f"username: {user.username}" if user.username else None]
            if bit
        )

        ai_messages = build_assistant_messages(
            messages=messages,
            members=member_names,
            projects=project_names,
            context_chunks=chunks,
            current_user=current_user,
        )

        started = time.monotonic()
        try:
            raw = chat(ai_messages, workspace=workspace)
        except Exception as exc:
            log_ai_task(task="assistant", workspace=workspace, user=request.user, status="error", error=str(exc))
            return _error_response(exc)

        try:
            result = parse_json(raw)
        except ValueError:
            # The model answered in plain prose instead of JSON — surface it as the reply.
            result = {"reply": raw.strip(), "actions": []}

        raw_actions = result.get("actions")
        if raw_actions is None:
            legacy_action = result.get("action")
            raw_actions = [legacy_action] if isinstance(legacy_action, dict) else []
        if not isinstance(raw_actions, list):
            raw_actions = []

        results = []
        for action in raw_actions:
            if not isinstance(action, dict):
                continue
            try:
                if action.get("type") == "create_work_item":
                    results.append(_create_work_item_via_assistant(workspace, action, project_id, request))
                elif action.get("type") == "update_work_item":
                    results.append(_update_work_item_via_assistant(workspace, action, project_id, request))
            except Exception as exc:
                log_exception(exc)
                results.append({"type": action.get("type"), "status": "error", "error": "Failed to apply the change."})

        config = get_ai_config(workspace)
        log_ai_task(
            task="assistant",
            workspace=workspace,
            user=request.user,
            provider=config.provider,
            model=config.model,
            latency_ms=int((time.monotonic() - started) * 1000),
            metadata={"actions": len(raw_actions), "results": len(results)},
        )
        return Response({"reply": result.get("reply", ""), "results": results}, status=status.HTTP_200_OK)


class WorkspaceAIWorkItemsEndpoint(BaseAPIView):
    """Lightweight work-item lookup for the assistant's `#` mention picker."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        workspace = _get_workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        query = (request.GET.get("query") or "").strip()
        project_id = request.GET.get("project_id")
        queryset = Issue.objects.filter(workspace=workspace, deleted_at__isnull=True).select_related("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if query:
            condition = Q(name__icontains=query) | Q(project__identifier__icontains=query)
            digits = re.findall(r"\d+", query)
            if digits:
                condition |= Q(sequence_id__in=[int(digit) for digit in digits])
            queryset = queryset.filter(condition)

        rows = queryset.order_by("-updated_at")[:20]
        results = [
            {
                "id": str(issue.id),
                "project_id": str(issue.project_id),
                "code": f"{issue.project.identifier}-{issue.sequence_id}",
                "name": issue.name,
            }
            for issue in rows
        ]
        return Response({"results": results}, status=status.HTTP_200_OK)
