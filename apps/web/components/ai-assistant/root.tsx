/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { observer } from "mobx-react";
import { CircleArrowUp, ExternalLink } from "lucide-react";
// plane imports
import type { IUserLite } from "@plane/types";
import { AiStar1Outline } from "@makeplane/propel/icons";
import { setToast } from "@plane/blocks/toast";
import { cn } from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
// services
import type { TAssistantResult, TAssistantWorkItem } from "@/services/ai.service";
import { AIService } from "@/services/ai.service";

const aiService = new AIService();

const newMessageId = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;

type TMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  results?: TAssistantResult[];
};

type Props = {
  workspaceSlug: string;
};

const SUGGESTIONS = [
  "What work items are open in this workspace?",
  "Siapa yang mengerjakan task ini?",
  "Create a task for the team: fix the login bug",
  "How do I create a cycle in Plane?",
];

export const AIAssistantRoot = observer(function AIAssistantRoot(props: Props) {
  const { workspaceSlug } = props;
  // refs
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // store hooks
  const { workspace: workspaceMemberStore, memberMap, getUserDetails } = useMember();
  // states
  const [messages, setMessages] = useState<TMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi, I'm Pi. I can answer questions about this workspace's work items, projects, and how to use Plane — and I can create work items for your teammates. What do you need?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [mention, setMention] = useState<{ kind: "user" | "work_item"; query: string } | null>(null);
  const [mentionIndex, setMentionIndex] = useState(0);
  const [workItems, setWorkItems] = useState<TAssistantWorkItem[]>([]);

  // workspace members available for @-mentions
  const members = useMemo(() => {
    const ids = workspaceMemberStore.getWorkspaceMemberIds(workspaceSlug) ?? [];
    return ids.map((id) => getUserDetails(id)).filter((member): member is IUserLite => Boolean(member));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceSlug, workspaceMemberStore, getUserDetails, memberMap]);

  const filteredMembers = useMemo(() => {
    if (mention?.kind !== "user") return [];
    const query = mention.query.toLowerCase();
    return members
      .filter((member) => `${member.display_name} ${member.email ?? ""}`.toLowerCase().includes(query))
      .slice(0, 6);
  }, [members, mention]);

  const filteredWorkItems = useMemo(() => {
    if (mention?.kind !== "work_item") return [];
    const query = mention.query.toLowerCase();
    return workItems.filter((item) => `${item.code} ${item.name}`.toLowerCase().includes(query)).slice(0, 6);
  }, [workItems, mention]);

  const optionCount = mention?.kind === "work_item" ? filteredWorkItems.length : filteredMembers.length;

  useEffect(() => {
    void workspaceMemberStore.fetchWorkspaceMembers(workspaceSlug);
    aiService
      .workItems(workspaceSlug)
      .then((res) => setWorkItems(res.results ?? []))
      .catch(() => setWorkItems([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceSlug]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isSending]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleInputChange = (value: string, caret: number) => {
    setInput(value);
    // Look for an @token/#token ending at the caret; fall back to the end of the value when the
    // caret is stale (0 after a programmatic clear), so mentions keep working after sending.
    const userMatch = value.slice(0, caret).match(/@([\w.@-]*)$/) ?? value.match(/@([\w.@-]*)$/);
    const itemMatch = value.slice(0, caret).match(/#([\w.-]*)$/) ?? value.match(/#([\w.-]*)$/);
    if (itemMatch) {
      setMention({ kind: "work_item", query: itemMatch[1] ?? "" });
      setMentionIndex(0);
    } else if (userMatch) {
      setMention({ kind: "user", query: userMatch[1] ?? "" });
      setMentionIndex(0);
    } else {
      setMention(null);
    }
  };

  const selectMention = (label: string) => {
    if (!mention) return;
    const trigger = mention.kind === "work_item" ? "#" : "@";
    const pattern = mention.kind === "work_item" ? /#([\w.-]*)$/ : /@([\w.@-]*)$/;
    const caret = inputRef.current?.selectionStart ?? input.length;
    const caretHasToken = pattern.test(input.slice(0, caret));
    const target = caretHasToken ? caret : input.length;
    const before = input.slice(0, target).replace(pattern, `${trigger}${label} `);
    const after = input.slice(target);
    setInput(before + after);
    setMention(null);
    requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange(before.length, before.length);
    });
  };

  const handleSend = async (prompt?: string) => {
    const content = (prompt ?? input).trim();
    if (!content || isSending) return;

    const nextMessages: TMessage[] = [...messages, { id: newMessageId(), role: "user", content }];
    setMessages(nextMessages);
    setInput("");
    setMention(null);
    if (inputRef.current) inputRef.current.style.height = "auto";
    setIsSending(true);

    try {
      const res = await aiService.assistant(workspaceSlug, {
        messages: nextMessages.map((message) => ({ role: message.role, content: message.content })),
      });
      setMessages((prev) => [
        ...prev,
        { id: newMessageId(), role: "assistant", content: res.reply || "…", results: res.results ?? [] },
      ]);
    } catch (error) {
      const message =
        (error as { error?: string })?.error || "I couldn't reach the AI service. Check that AI is configured.";
      setToast({ type: "error", title: "Error", message });
      setMessages((prev) => [...prev, { id: newMessageId(), role: "assistant", content: message }]);
    } finally {
      setIsSending(false);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  };

  const renderResults = (message: TMessage) => {
    if (!message.results || message.results.length === 0) return null;
    return (
      <div className="mt-3 flex flex-col gap-2">
        {message.results.map((result) => {
          const isError = result.status === "error";
          const label = result.type === "update_work_item" ? "Task Updated" : "Task Created";
          const href =
            result.project_id && result.issue_id
              ? `/${workspaceSlug}/projects/${result.project_id}/issues/${result.issue_id}/`
              : undefined;
          return (
            <div
              key={`${result.type}-${result.issue_id ?? result.code ?? result.name ?? result.error ?? "result"}`}
              className={cn("rounded-md border p-3 text-13", {
                "border-subtle bg-surface-1": !isError,
                "border-danger-strong bg-danger-primary/5": isError,
              })}
            >
              {isError ? (
                <div className="text-danger-primary">Couldn&apos;t apply: {result.error || "unknown error"}</div>
              ) : (
                <div className="flex flex-wrap items-center gap-1.5 text-secondary">
                  <span className="text-11 font-medium tracking-wide text-tertiary uppercase">{label}:</span>
                  {href ? (
                    <a
                      href={href}
                      className="inline-flex items-center gap-1 font-medium text-accent-primary hover:underline"
                    >
                      {result.code} <ExternalLink className="size-3" />
                    </a>
                  ) : (
                    <span className="font-medium text-accent-primary">{result.code}</span>
                  )}
                  {result.name && <span className="text-tertiary">— {result.name}</span>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex size-full flex-col bg-surface-1">
      <div className="flex items-center gap-2 border-b border-subtle px-6 py-4">
        <span className="grid size-7 place-items-center rounded-full bg-accent-primary/10 text-accent-primary">
          <AiStar1Outline className="size-4" />
        </span>
        <div>
          <div className="text-14 font-medium text-primary">Pi Assistant</div>
          <div className="text-11 text-tertiary">
            Ask about this workspace, or create and assign work items. Chats aren't saved.
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="vertical-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn("flex gap-3", {
                "justify-end": message.role === "user",
              })}
            >
              {message.role === "assistant" && (
                <span className="mt-0.5 grid size-6 flex-shrink-0 place-items-center rounded-full bg-layer-2 text-secondary">
                  <AiStar1Outline className="size-3.5" />
                </span>
              )}
              <div
                className={cn("max-w-[80%] rounded-lg px-3.5 py-2.5 text-13 whitespace-pre-wrap", {
                  "bg-accent-primary/10 text-primary": message.role === "user",
                  "bg-layer-1 text-secondary": message.role === "assistant",
                })}
              >
                {message.content}
                {renderResults(message)}
              </div>
            </div>
          ))}
          {isSending && (
            <div className="flex gap-3">
              <span className="mt-0.5 grid size-6 place-items-center rounded-full bg-layer-2 text-secondary">
                <AiStar1Outline className="size-3.5 animate-pulse" />
              </span>
              <div className="rounded-lg bg-layer-1 px-3.5 py-2.5 text-13 text-tertiary">Pi is thinking…</div>
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-subtle px-6 py-4">
        <div className="mx-auto max-w-3xl">
          {messages.length <= 1 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="rounded-full border border-subtle px-3 py-1 text-12 text-secondary hover:bg-layer-1"
                  onClick={() => handleSend(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}
          {mention !== null && optionCount > 0 && (
            <div className="mb-2 max-h-56 overflow-y-auto rounded-md border border-subtle bg-surface-1 shadow-raised-200">
              <div className="px-3 py-1.5 text-11 font-medium text-tertiary">
                {mention.kind === "work_item" ? "Work items" : "Members"}
              </div>
              {mention.kind === "work_item"
                ? filteredWorkItems.map((item, index) => (
                    <button
                      key={item.id}
                      type="button"
                      onMouseDown={(event) => {
                        event.preventDefault();
                        selectMention(item.code);
                      }}
                      className={cn("flex w-full items-center gap-2 px-3 py-2 text-left text-13 hover:bg-layer-1", {
                        "bg-layer-1": index === mentionIndex,
                      })}
                    >
                      <span className="flex-shrink-0 rounded-sm bg-layer-2 px-1.5 py-0.5 text-11 font-medium text-secondary">
                        {item.code}
                      </span>
                      <span className="truncate text-primary">{item.name}</span>
                    </button>
                  ))
                : filteredMembers.map((member, index) => (
                    <button
                      key={member.id}
                      type="button"
                      onMouseDown={(event) => {
                        event.preventDefault();
                        selectMention(member.display_name);
                      }}
                      className={cn("flex w-full items-center gap-2 px-3 py-2 text-left text-13 hover:bg-layer-1", {
                        "bg-layer-1": index === mentionIndex,
                      })}
                    >
                      <span className="grid size-6 flex-shrink-0 place-items-center rounded-full bg-layer-2 text-11 text-secondary">
                        {(member.display_name || member.first_name || "?").charAt(0).toUpperCase()}
                      </span>
                      <span className="text-primary">{member.display_name}</span>
                      {member.email && <span className="truncate text-11 text-tertiary">{member.email}</span>}
                    </button>
                  ))}
            </div>
          )}
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              id="pi-assistant-input"
              name="pi-assistant-input"
              value={input}
              rows={1}
              onChange={(e) => {
                handleInputChange(e.target.value, e.target.selectionStart ?? e.target.value.length);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
              }}
              onKeyDown={(e) => {
                if (mention !== null && optionCount > 0 && !e.shiftKey) {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setMentionIndex((index) => (index + 1) % optionCount);
                    return;
                  }
                  if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setMentionIndex((index) => (index - 1 + optionCount) % optionCount);
                    return;
                  }
                  if (e.key === "Enter" || e.key === "Tab") {
                    e.preventDefault();
                    if (mention.kind === "work_item") {
                      const item = filteredWorkItems[mentionIndex];
                      if (item) selectMention(item.code);
                    } else {
                      const member = filteredMembers[mentionIndex];
                      if (member) selectMention(member.display_name);
                    }
                    return;
                  }
                  if (e.key === "Escape") {
                    e.preventDefault();
                    setMention(null);
                    return;
                  }
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              placeholder="Ask about your tasks — type @ for a teammate or # for a work item. (Shift+Enter for a new line)"
              className="focus:border-accent-primary max-h-40 min-h-9 w-full resize-none rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary outline-none placeholder:text-placeholder"
            />
            <button
              type="button"
              aria-label="Send"
              disabled={isSending || !input.trim()}
              onClick={() => void handleSend()}
              className="grid size-9 flex-shrink-0 place-items-center rounded-md bg-accent-primary text-on-color disabled:opacity-50"
            >
              <CircleArrowUp className="size-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
});
