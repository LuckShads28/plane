/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { CircleArrowUp } from "lucide-react";
import { AiStar1Outline, CornerRightDownOutline, RefreshOutline } from "@makeplane/propel/icons";
// ui
import { Tooltip } from "@makeplane/propel/components/tooltip";
// components
import { cn } from "@plane/utils";
import { RichTextEditor } from "@/components/editor/rich-text";
// helpers
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";

type Props = {
  handleInsertText: (insertOnNextLine: boolean) => void;
  handleRegenerate: () => Promise<void>;
  isRegenerating: boolean;
  response: string | undefined;
  workspaceSlug: string;
  onSubmit: (query: string) => Promise<void> | void;
};

export function AskPiMenu(props: Props) {
  const { handleInsertText, handleRegenerate, isRegenerating, response, workspaceSlug, onSubmit } = props;
  // states
  const [query, setQuery] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  // store hooks
  const { getWorkspaceBySlug } = useWorkspace();
  // derived values
  const workspaceId = getWorkspaceBySlug(workspaceSlug)?.id ?? "";

  const handleSend = async () => {
    const value = query.trim();
    if (!value || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onSubmit(value);
      setQuery("");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div
        className={cn("flex items-center gap-3 px-4 py-3.5", {
          "items-start": response,
        })}
      >
        <span className="grid size-7 flex-shrink-0 place-items-center rounded-full border border-subtle text-secondary">
          <AiStar1Outline className="size-3" />
        </span>
        {response ? (
          <div>
            <RichTextEditor
              editable={false}
              displayConfig={{
                fontSize: "small-font",
              }}
              id="editor-ai-response"
              initialValue={response}
              containerClassName="!p-0 border-none"
              editorClassName="!pl-0"
              workspaceId={workspaceId}
              workspaceSlug={workspaceSlug}
            />
            <div className="mt-3 flex items-center gap-4">
              <button
                type="button"
                className="rounded-sm p-1 text-13 font-medium text-tertiary outline-none hover:bg-layer-1"
                onClick={() => handleInsertText(false)}
              >
                Replace selection
              </button>
              <Tooltip label="Add to next line">
                <button
                  type="button"
                  className="grid size-6 flex-shrink-0 place-items-center rounded-sm outline-none hover:bg-layer-1"
                  onClick={() => handleInsertText(true)}
                >
                  <CornerRightDownOutline className="size-4 text-tertiary" />
                </button>
              </Tooltip>
              <Tooltip label="Re-generate response">
                <button
                  type="button"
                  className="grid size-6 flex-shrink-0 place-items-center rounded-sm outline-none hover:bg-layer-1"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleRegenerate();
                  }}
                  disabled={isRegenerating}
                >
                  <RefreshOutline
                    className={cn("size-4 text-tertiary", {
                      "animate-spin": isRegenerating,
                    })}
                  />
                </button>
              </Tooltip>
            </div>
          </div>
        ) : (
          <p className="text-13 text-secondary">{isSubmitting ? "AI is answering..." : "Ask Pi anything."}</p>
        )}
      </div>
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 rounded-md border border-subtle p-2">
          <span className="grid size-3 flex-shrink-0 place-items-center">
            <AiStar1Outline className="size-3 text-secondary" />
          </span>
          <input
            type="text"
            className="w-full border-none bg-transparent text-13 outline-none placeholder:text-placeholder"
            value={query}
            disabled={isSubmitting}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSend();
              }
            }}
            placeholder="Tell AI what to do..."
          />
          <button
            type="button"
            aria-label="Send"
            disabled={isSubmitting || !query.trim()}
            className="grid size-4 flex-shrink-0 place-items-center disabled:opacity-40"
            onClick={() => void handleSend()}
          >
            <CircleArrowUp className="size-4 text-secondary" />
          </button>
        </div>
      </div>
    </>
  );
}
