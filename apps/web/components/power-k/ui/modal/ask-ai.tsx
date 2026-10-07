/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Command } from "cmdk";
import { useParams } from "next/navigation";
// plane imports
import { AiStar1Outline } from "@makeplane/propel/icons";
// services
import { AIService } from "@/services/ai.service";
// local imports
import { PowerKModalCommandItem } from "./command-item";

const aiService = new AIService();

type Props = {
  projectId?: string;
  searchTerm: string;
};

type TSource = {
  index: number;
  entity_type: string;
  entity_id: string;
  project_id: string | null;
  label: string;
};

/**
 * "Ask AI" action inside the command palette. Selecting it asks the workspace RAG
 * endpoint and renders the answer (with sources) inline.
 */
export function PowerKModalAskAI(props: Props) {
  const { projectId, searchTerm } = props;
  // navigation
  const { workspaceSlug } = useParams();
  // states
  const [isLoading, setIsLoading] = useState(false);
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<TSource[]>([]);

  if (!searchTerm.trim()) return null;

  const handleAsk = async () => {
    if (!workspaceSlug || !searchTerm.trim()) return;
    setIsLoading(true);
    setAnswer("");
    setSources([]);
    try {
      const res = await aiService.ask(workspaceSlug.toString(), {
        question: searchTerm,
        ...(projectId ? { project_id: projectId } : {}),
      });
      setAnswer(res.answer);
      setSources(res.sources ?? []);
    } catch {
      setAnswer("Could not get an AI answer. Check that AI is configured for this workspace.");
      setSources([]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Command.Group heading="AI">
      <PowerKModalCommandItem
        icon={AiStar1Outline}
        label={`Ask AI: “${searchTerm}”`}
        onSelect={handleAsk}
        value={`ask-ai-${searchTerm}`}
      />
      {(isLoading || answer) && (
        <div className="mx-4 my-2 rounded-md border border-subtle bg-layer-1 p-3 text-13 text-secondary">
          {isLoading ? "Pi is thinking…" : answer}
          {sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1 text-11 text-tertiary">
              Sources:{" "}
              {sources.map((source) => (
                <span key={`${source.entity_type}-${source.entity_id}`} className="rounded-sm bg-layer-2 px-1 py-0.5">
                  [{source.index}] {source.label}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </Command.Group>
  );
}
