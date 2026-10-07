/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TLLMProvider = "openai" | "openai-compatible" | "ollama" | "anthropic" | "gemini";

export type TInstanceAIConfigurationKeys =
  | "LLM_API_KEY"
  | "LLM_PROVIDER"
  | "LLM_MODEL"
  | "LLM_BASE_URL"
  | "LLM_EMBEDDING_MODEL"
  | "LLM_EMBEDDING_DIMENSIONS"
  | "LLM_EMBEDDING_MAX_TOKENS"
  | "LLM_CONTEXT_WINDOW"
  | "LLM_MAX_OUTPUT_TOKENS"
  | "LLM_RESERVED_TOKENS"
  | "LLM_TEMPERATURE";

export interface IWorkspaceAIConfiguration {
  id: string;
  workspace: string;
  provider: TLLMProvider;
  base_url: string | null;
  model: string | null;
  embedding_model: string | null;
  embedding_dimensions: number;
  embedding_max_tokens: number;
  context_window: number;
  max_output_tokens: number;
  reserved_tokens: number;
  temperature: number;
  is_active: boolean;
  // Secrets are never returned; `api_key_configured` reports whether one is stored.
  api_key_configured: boolean;
  created_at?: string;
  updated_at?: string;
}

export type TWorkspaceAIConfigurationInput = Partial<
  Pick<
    IWorkspaceAIConfiguration,
    | "provider"
    | "base_url"
    | "model"
    | "embedding_model"
    | "embedding_dimensions"
    | "embedding_max_tokens"
    | "context_window"
    | "max_output_tokens"
    | "reserved_tokens"
    | "temperature"
    | "is_active"
  >
> & {
  api_key?: string;
};
