# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path


from plane.app.views import UnsplashEndpoint
from plane.app.views import GPTIntegrationEndpoint, WorkspaceGPTIntegrationEndpoint
from plane.app.views import (
    IntakeTriageEndpoint,
    RephraseGrammarEndpoint,
    WorkItemCopilotEndpoint,
    WorkspaceAIAskEndpoint,
    WorkspaceAIAssistantEndpoint,
    WorkspaceAIChatEndpoint,
    WorkspaceAIConfigurationEndpoint,
    WorkspaceAISearchEndpoint,
    WorkspaceAIWorkItemsEndpoint,
)


urlpatterns = [
    path("unsplash/", UnsplashEndpoint.as_view(), name="unsplash"),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/ai-assistant/",
        GPTIntegrationEndpoint.as_view(),
        name="importer",
    ),
    path(
        "workspaces/<str:slug>/ai-assistant/",
        WorkspaceGPTIntegrationEndpoint.as_view(),
        name="importer",
    ),
    # AI settings + features
    path(
        "workspaces/<str:slug>/ai-settings/",
        WorkspaceAIConfigurationEndpoint.as_view(),
        name="workspace-ai-settings",
    ),
    path(
        "workspaces/<str:slug>/rephrase-grammar/",
        RephraseGrammarEndpoint.as_view(),
        name="rephrase-grammar",
    ),
    path(
        "workspaces/<str:slug>/ai/chat/",
        WorkspaceAIChatEndpoint.as_view(),
        name="workspace-ai-chat",
    ),
    path(
        "workspaces/<str:slug>/ai/search/",
        WorkspaceAISearchEndpoint.as_view(),
        name="workspace-ai-search",
    ),
    path(
        "workspaces/<str:slug>/ai/ask/",
        WorkspaceAIAskEndpoint.as_view(),
        name="workspace-ai-ask",
    ),
    path(
        "workspaces/<str:slug>/ai/assistant/",
        WorkspaceAIAssistantEndpoint.as_view(),
        name="workspace-ai-assistant",
    ),
    path(
        "workspaces/<str:slug>/ai/work-items/",
        WorkspaceAIWorkItemsEndpoint.as_view(),
        name="workspace-ai-work-items",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/ai/copilot/",
        WorkItemCopilotEndpoint.as_view(),
        name="work-item-copilot",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/ai/triage/",
        IntakeTriageEndpoint.as_view(),
        name="intake-triage",
    ),
]
