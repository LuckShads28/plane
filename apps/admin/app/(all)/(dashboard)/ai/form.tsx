/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useForm } from "react-hook-form";
import { ThoughtsOutline } from "@makeplane/propel/icons";
import { Button } from "@makeplane/propel/components/button";
import type { IFormattedInstanceConfiguration, TInstanceAIConfigurationKeys } from "@plane/types";
// components
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
import { setToast } from "@plane/blocks/toast";
// hooks
import { useInstance } from "@/hooks/store";

type IInstanceAIForm = {
  config: IFormattedInstanceConfiguration;
};

type AIFormValues = Record<TInstanceAIConfigurationKeys, string>;

export function InstanceAIForm(props: IInstanceAIForm) {
  const { config } = props;
  // store
  const { updateInstanceConfigurations } = useInstance();
  // form data
  const {
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<AIFormValues>({
    defaultValues: {
      LLM_API_KEY: config["LLM_API_KEY"],
      LLM_PROVIDER: config["LLM_PROVIDER"] ?? "openai",
      LLM_MODEL: config["LLM_MODEL"],
      LLM_BASE_URL: config["LLM_BASE_URL"] ?? "",
      LLM_EMBEDDING_MODEL: config["LLM_EMBEDDING_MODEL"] ?? "",
      LLM_EMBEDDING_DIMENSIONS: config["LLM_EMBEDDING_DIMENSIONS"] ?? "1536",
      LLM_EMBEDDING_MAX_TOKENS: config["LLM_EMBEDDING_MAX_TOKENS"] ?? "8191",
      LLM_CONTEXT_WINDOW: config["LLM_CONTEXT_WINDOW"] ?? "128000",
      LLM_MAX_OUTPUT_TOKENS: config["LLM_MAX_OUTPUT_TOKENS"] ?? "4096",
      LLM_RESERVED_TOKENS: config["LLM_RESERVED_TOKENS"] ?? "256",
      LLM_TEMPERATURE: config["LLM_TEMPERATURE"] ?? "0.2",
    },
  });

  const aiFormFields: TControllerInputFormField<AIFormValues>[] = [
    {
      key: "LLM_PROVIDER",
      type: "text",
      label: "Provider",
      description: "One of: openai, openai-compatible, ollama, anthropic, gemini.",
      placeholder: "openai",
      error: Boolean(errors.LLM_PROVIDER),
      required: false,
    },
    {
      key: "LLM_BASE_URL",
      type: "text",
      label: "Base URL",
      description: "Required for local/self-hosted servers (e.g. http://localhost:11434/v1 for Ollama).",
      placeholder: "https://api.openai.com/v1",
      error: Boolean(errors.LLM_BASE_URL),
      required: false,
    },
    {
      key: "LLM_MODEL",
      type: "text",
      label: "Chat model",
      description: "Model used for chat, copilot, and summaries.",
      placeholder: "gpt-4o-mini",
      error: Boolean(errors.LLM_MODEL),
      required: false,
    },
    {
      key: "LLM_API_KEY",
      type: "password",
      label: "API key",
      description: "Stored encrypted. Leave unchanged to keep the existing key.",
      placeholder: "sk-...",
      error: Boolean(errors.LLM_API_KEY),
      required: false,
    },
    {
      key: "LLM_EMBEDDING_MODEL",
      type: "text",
      label: "Embedding model",
      description: "Used for semantic search / RAG. Leave blank to disable embeddings.",
      placeholder: "text-embedding-3-small",
      error: Boolean(errors.LLM_EMBEDDING_MODEL),
      required: false,
    },
    {
      key: "LLM_EMBEDDING_DIMENSIONS",
      type: "text",
      label: "Embedding dimensions",
      description: "Must match the embedding model output (e.g. 1536, 768).",
      placeholder: "1536",
      error: Boolean(errors.LLM_EMBEDDING_DIMENSIONS),
      required: false,
    },
    {
      key: "LLM_EMBEDDING_MAX_TOKENS",
      type: "text",
      label: "Embedding max tokens",
      description: "Maximum input tokens per chunk for the embedding model.",
      placeholder: "8191",
      error: Boolean(errors.LLM_EMBEDDING_MAX_TOKENS),
      required: false,
    },
    {
      key: "LLM_CONTEXT_WINDOW",
      type: "text",
      label: "Context window",
      description: "Total tokens the chat model supports (e.g. 65000 for a local model, 128000 for cloud).",
      placeholder: "128000",
      error: Boolean(errors.LLM_CONTEXT_WINDOW),
      required: false,
    },
    {
      key: "LLM_MAX_OUTPUT_TOKENS",
      type: "text",
      label: "Max output tokens",
      description: "Upper bound on generated tokens per response.",
      placeholder: "4096",
      error: Boolean(errors.LLM_MAX_OUTPUT_TOKENS),
      required: false,
    },
    {
      key: "LLM_RESERVED_TOKENS",
      type: "text",
      label: "Reserved tokens",
      description: "Safety margin subtracted from the context window before assembling prompts.",
      placeholder: "256",
      error: Boolean(errors.LLM_RESERVED_TOKENS),
      required: false,
    },
    {
      key: "LLM_TEMPERATURE",
      type: "text",
      label: "Temperature",
      description: "Sampling temperature (0 = deterministic, 1 = creative).",
      placeholder: "0.2",
      error: Boolean(errors.LLM_TEMPERATURE),
      required: false,
    },
  ];

  const onSubmit = async (formData: AIFormValues) => {
    const payload: Partial<AIFormValues> = { ...formData };

    await updateInstanceConfigurations(payload)
      .then(() =>
        setToast({
          type: "success",
          title: "Success",
          message: "AI Settings updated successfully",
        })
      )
      .catch((err) => console.error(err));
  };

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div>
          <div className="pb-1 text-18 font-medium text-primary">AI Provider</div>
          <div className="text-13 font-regular text-tertiary">
            Configure any OpenAI-compatible server (OpenAI, Ollama, vLLM, ...) or Anthropic / Gemini. Context length is
            fully configurable for local models.
          </div>
        </div>
        <div className="grid-col grid w-full grid-cols-1 items-center justify-between gap-x-12 gap-y-8 lg:grid-cols-3">
          {aiFormFields.map((field) => (
            <ControllerInput
              key={field.key}
              control={control}
              type={field.type}
              name={field.key}
              label={field.label}
              description={field.description}
              placeholder={field.placeholder}
              error={field.error}
              required={field.required}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col items-start gap-4">
        <Button
          variant="primary"
          size="md"
          stretch="auto"
          onClick={handleSubmit(onSubmit)}
          loading={isSubmitting}
          label={isSubmitting ? "Saving" : "Save changes"}
        />

        <div className="relative inline-flex items-center gap-1.5 rounded-sm border border-accent-subtle bg-accent-subtle px-4 py-2 text-caption-sm-regular text-accent-secondary">
          <ThoughtsOutline className="size-4" />
          <div>Workspace admins can override these settings per workspace.</div>
        </div>
      </div>
    </div>
  );
}
