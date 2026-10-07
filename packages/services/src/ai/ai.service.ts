/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { AI_EDITOR_TASKS } from "@plane/constants";
import { API_BASE_URL } from "@plane/constants";
import type { IWorkspaceAIConfiguration, TWorkspaceAIConfigurationInput } from "@plane/types";
// services
import { APIService } from "../api.service";

/**
 * Payload type for AI editor tasks
 * @typedef {Object} TTaskPayload
 * @property {number} [casual_score] - Optional score for casual tone analysis
 * @property {number} [formal_score] - Optional score for formal tone analysis
 * @property {AI_EDITOR_TASKS} task - Type of AI editor task to perform
 * @property {string} text_input - The input text to be processed
 */
export type TTaskPayload = {
  casual_score?: number;
  formal_score?: number;
  task: AI_EDITOR_TASKS;
  text_input: string;
};

export type TAICopilotResponse = {
  name?: string;
  description_html?: string;
  priority?: string;
  labels?: string[];
  label_ids?: string[];
  assignee_ids?: string[];
  assignee_hint?: string;
  estimate?: string;
  subtasks?: { name: string }[];
};

export type TAITriageResponse = {
  summary?: string;
  priority?: string;
  label_ids?: string[];
  assignee_ids?: string[];
  is_actionable?: boolean;
  duplicate_candidates?: { id: string; name: string; sequence_id: number }[];
};

export type TAISearchResult = {
  entity_type: string;
  entity_id: string;
  project_id: string | null;
  text: string;
  label: string;
};

export type TAIAskResponse = {
  answer: string;
  sources: { index: number; entity_type: string; entity_id: string; project_id: string | null; label: string }[];
};

export type TAssistantResult = {
  type: "create_work_item" | "update_work_item";
  status: "created" | "updated" | "error";
  issue_id?: string;
  project_id?: string;
  name?: string;
  code?: string;
  error?: string;
};

export type TAssistantResponse = {
  reply: string;
  results: TAssistantResult[];
};

export type TAssistantWorkItem = {
  id: string;
  project_id: string;
  code: string;
  name: string;
};

/**
 * Service class for handling AI-related API operations
 * @extends {APIService}
 */
export class AIService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  /**
   * Generic workspace AI prompt (legacy endpoint).
   */
  async prompt(workspaceSlug: string, data: { prompt: string; task: string }): Promise<any> {
    return this.post(`/api/workspaces/${workspaceSlug}/ai-assistant/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  /**
   * Backwards-compatible alias used by the issue modal and popovers.
   */
  async createGptTask(workspaceSlug: string, data: { prompt: string; task: string }): Promise<any> {
    return this.prompt(workspaceSlug, data);
  }

  /**
   * Performs an editor AI task (grammar, rewrite, tone, translate, ...).
   */
  async performEditorTask(workspaceSlug: string, data: TTaskPayload): Promise<{ response: string }> {
    return this.post(`/api/workspaces/${workspaceSlug}/rephrase-grammar/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Backwards-compatible alias for the editor task endpoint.
   */
  async rephraseGrammar(workspaceSlug: string, data: TTaskPayload): Promise<{ response: string }> {
    return this.performEditorTask(workspaceSlug, data);
  }

  /**
   * Free-form workspace chat.
   */
  async chat(workspaceSlug: string, data: { prompt?: string; messages?: unknown[] }): Promise<{ response: string }> {
    return this.post(`/api/workspaces/${workspaceSlug}/ai/chat/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Generate/complete a work item from rough input.
   */
  async copilot(
    workspaceSlug: string,
    projectId: string,
    data: { prompt: string; title?: string; description?: string; mode?: string }
  ): Promise<TAICopilotResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/ai/copilot/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Triage an incoming intake work item.
   */
  async triage(
    workspaceSlug: string,
    projectId: string,
    data: { name?: string; description?: string }
  ): Promise<TAITriageResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/ai/triage/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Semantic search across workspace content.
   */
  async search(
    workspaceSlug: string,
    data: { query: string; project_id?: string }
  ): Promise<{ results: TAISearchResult[] }> {
    return this.post(`/api/workspaces/${workspaceSlug}/ai/search/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * RAG Q&A with citations.
   */
  async ask(workspaceSlug: string, data: { question: string; project_id?: string }): Promise<TAIAskResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/ai/ask/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Standalone assistant: chat with optional action (create work item).
   */
  async assistant(
    workspaceSlug: string,
    data: { messages: { role: string; content: string }[]; project_id?: string }
  ): Promise<TAssistantResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/ai/assistant/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Work items for the assistant's `#` mention picker.
   */
  async workItems(
    workspaceSlug: string,
    params?: { query?: string; project_id?: string }
  ): Promise<{ results: TAssistantWorkItem[] }> {
    return this.get(`/api/workspaces/${workspaceSlug}/ai/work-items/`, { params })
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Read the workspace AI configuration (admin only).
   */
  async getWorkspaceAIConfiguration(workspaceSlug: string): Promise<IWorkspaceAIConfiguration> {
    return this.get(`/api/workspaces/${workspaceSlug}/ai-settings/`)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Update the workspace AI configuration (admin only).
   */
  async updateWorkspaceAIConfiguration(
    workspaceSlug: string,
    data: TWorkspaceAIConfigurationInput
  ): Promise<IWorkspaceAIConfiguration> {
    return this.patch(`/api/workspaces/${workspaceSlug}/ai-settings/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
