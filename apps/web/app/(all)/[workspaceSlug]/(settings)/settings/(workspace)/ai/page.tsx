/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import type { IWorkspaceAIConfiguration, TLLMProvider } from "@plane/types";
import { Button } from "@makeplane/propel/components/button";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { setToast } from "@plane/blocks/toast";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useUserPermissions } from "@/hooks/store/user";
import { useWorkspace } from "@/hooks/store/use-workspace";
// services
import { AIService } from "@/services/ai.service";
// local imports
import type { Route } from "./+types/page";
import { AIWorkspaceSettingsHeader } from "./header";

const aiService = new AIService();

const PROVIDERS: TLLMProvider[] = ["openai", "openai-compatible", "ollama", "anthropic", "gemini"];

type FieldProps = {
  label: string;
  description?: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "password";
  placeholder?: string;
  disabled?: boolean;
};

function Field(props: FieldProps) {
  const { label, description, value, onChange, type = "text", placeholder, disabled } = props;
  return (
    <div className="flex flex-col gap-1">
      <label className="text-13 text-tertiary" htmlFor={label}>
        {label}
      </label>
      <InputGroup size="lg">
        <Input
          size="lg"
          id={label}
          name={label}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
        />
      </InputGroup>
      {description && <p className="pt-0.5 text-11 text-tertiary">{description}</p>}
    </div>
  );
}

function WorkspaceAISettingsPage({ params }: Route.ComponentProps) {
  // router
  const { workspaceSlug } = params;
  // store hooks
  const { currentWorkspace } = useWorkspace();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  // states
  const [config, setConfig] = useState<IWorkspaceAIConfiguration | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // derived values
  const canManageWorkspace = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);
  const pageTitle = currentWorkspace?.name ? `${currentWorkspace.name} - AI` : undefined;

  useEffect(() => {
    if (!workspaceSlug || !canManageWorkspace) return;
    aiService
      .getWorkspaceAIConfiguration(workspaceSlug)
      .then((res) => setConfig(res))
      .catch(() => setConfig(null));
  }, [workspaceSlug, canManageWorkspace]);

  const updateField = useCallback(
    <K extends keyof IWorkspaceAIConfiguration>(key: K, value: IWorkspaceAIConfiguration[K]) => {
      setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
    },
    []
  );

  const handleSave = async () => {
    if (!config || !workspaceSlug) return;
    setIsSaving(true);
    try {
      const updated = await aiService.updateWorkspaceAIConfiguration(workspaceSlug, {
        provider: config.provider,
        base_url: config.base_url ?? "",
        model: config.model ?? "",
        embedding_model: config.embedding_model ?? "",
        embedding_dimensions: Number(config.embedding_dimensions) || 1536,
        embedding_max_tokens: Number(config.embedding_max_tokens) || 8191,
        context_window: Number(config.context_window) || 128000,
        max_output_tokens: Number(config.max_output_tokens) || 4096,
        reserved_tokens: Number(config.reserved_tokens) || 256,
        temperature: Number(config.temperature) || 0.2,
        is_active: config.is_active,
        ...(apiKey ? { api_key: apiKey } : {}),
      });
      setConfig(updated);
      setApiKey("");
      setToast({ type: "success", title: "Success", message: "AI settings updated successfully" });
    } catch {
      setToast({ type: "error", title: "Error", message: "Failed to update AI settings. Please try again." });
    } finally {
      setIsSaving(false);
    }
  };

  if (workspaceUserInfo && !canManageWorkspace) {
    return <NotAuthorizedView section="settings" className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<AIWorkspaceSettingsHeader />}>
      <PageHead title={pageTitle} />
      {!config ? (
        <div className="text-13 text-tertiary">Loading AI settings…</div>
      ) : (
        <div className="flex flex-col gap-8">
          <SettingsHeading
            title="AI provider"
            description="Override the instance AI configuration for this workspace. Workspace settings take precedence."
          />

          <div className="grid grid-cols-1 gap-x-12 gap-y-8 lg:grid-cols-3">
            <div className="flex flex-col gap-1">
              <label className="text-13 text-tertiary" htmlFor="provider">
                Provider
              </label>
              <select
                id="provider"
                name="provider"
                value={config.provider}
                onChange={(e) => updateField("provider", e.target.value as TLLMProvider)}
                className="focus:border-accent-primary h-9 rounded-md border border-subtle bg-surface-1 px-3 text-13 outline-none"
              >
                {PROVIDERS.map((provider) => (
                  <option key={provider} value={provider}>
                    {provider}
                  </option>
                ))}
              </select>
              <p className="pt-0.5 text-11 text-tertiary">
                Use <code>openai-compatible</code> for local servers (Ollama, vLLM).
              </p>
            </div>

            <Field
              label="API key"
              type="password"
              value={apiKey}
              onChange={setApiKey}
              placeholder={config.api_key_configured ? "•••••••• (stored)" : "sk-..."}
              description="Stored encrypted. Leave unchanged to keep the existing key."
            />
            <Field
              label="Base URL"
              value={config.base_url ?? ""}
              onChange={(value) => updateField("base_url", value)}
              placeholder="http://localhost:11434/v1"
              description="Required for local / self-hosted OpenAI-compatible servers."
            />
            <Field
              label="Chat model"
              value={config.model ?? ""}
              onChange={(value) => updateField("model", value)}
              placeholder="gpt-4o-mini"
            />
            <Field
              label="Embedding model"
              value={config.embedding_model ?? ""}
              onChange={(value) => updateField("embedding_model", value)}
              placeholder="text-embedding-3-small"
              description="Leave blank to disable semantic search."
            />
            <Field
              label="Embedding dimensions"
              value={String(config.embedding_dimensions)}
              onChange={(value) => updateField("embedding_dimensions", Number(value) || 0)}
              placeholder="1536"
            />
            <Field
              label="Embedding max tokens"
              value={String(config.embedding_max_tokens)}
              onChange={(value) => updateField("embedding_max_tokens", Number(value) || 0)}
              placeholder="8191"
            />
            <Field
              label="Context window"
              value={String(config.context_window)}
              onChange={(value) => updateField("context_window", Number(value) || 0)}
              placeholder="65000"
              description="Total tokens the model supports. Set 65000 for a 65k local model."
            />
            <Field
              label="Max output tokens"
              value={String(config.max_output_tokens)}
              onChange={(value) => updateField("max_output_tokens", Number(value) || 0)}
              placeholder="4096"
            />
            <Field
              label="Reserved tokens"
              value={String(config.reserved_tokens)}
              onChange={(value) => updateField("reserved_tokens", Number(value) || 0)}
              placeholder="256"
            />
            <Field
              label="Temperature"
              value={String(config.temperature)}
              onChange={(value) => updateField("temperature", Number(value) || 0)}
              placeholder="0.2"
            />

            <div className="flex flex-col gap-1">
              <label className="text-13 text-tertiary" htmlFor="is-active">
                Enable workspace override
              </label>
              <div className="flex h-9 items-center">
                <input
                  id="is-active"
                  name="is-active"
                  type="checkbox"
                  checked={config.is_active}
                  onChange={(e) => updateField("is_active", e.target.checked)}
                  className="size-4"
                />
              </div>
              <p className="pt-0.5 text-11 text-tertiary">
                When disabled, the instance-level AI configuration is used.
              </p>
            </div>
          </div>

          <div className="flex flex-col items-start gap-4">
            <Button
              variant="primary"
              size="md"
              stretch="auto"
              onClick={handleSave}
              loading={isSaving}
              label={isSaving ? "Saving" : "Save changes"}
            />
          </div>
        </div>
      )}
    </SettingsContentWrapper>
  );
}

export default observer(WorkspaceAISettingsPage);
