# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Prompt templates for every AI task. Kept separate so they are easy to review."""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Editor tasks
# ---------------------------------------------------------------------------

EDITOR_TASK_INSTRUCTIONS = {
    "IMPROVE_WRITING": "Rewrite the text to improve clarity, flow, and grammar while keeping the original meaning.",
    "FIX_SPELLING_GRAMMAR": "Fix all spelling and grammar mistakes. Keep the wording and meaning unchanged.",
    "SHORTEN": "Rewrite the text to be more concise without losing important information.",
    "EXPAND_WRITING": "Expand the text with more detail and clarity while keeping the same intent.",
    "SUMMARIZE": "Summarize the text into a short, clear summary.",
    "CHANGE_TONE": "Rewrite the text in the requested tone while preserving the meaning.",
    "TRANSLATE": "Translate the text into English. If it is already English, translate it into Spanish.",
    "ASK_ANYTHING": "Answer the user's request based on the provided text.",
}

DEFAULT_EDITOR_INSTRUCTION = "Help the user with the provided text."


def _tone_label(casual_score: int | None, formal_score: int | None) -> str:
    casual = casual_score or 0
    formal = formal_score or 0
    if formal > casual:
        return "professional and formal"
    if casual > formal:
        return "casual and friendly"
    return "neutral"


def build_editor_messages(
    task: str,
    text_input: str,
    *,
    casual_score: int | None = None,
    formal_score: int | None = None,
) -> list[dict]:
    instruction = EDITOR_TASK_INSTRUCTIONS.get(task, DEFAULT_EDITOR_INSTRUCTION)
    if task == "CHANGE_TONE":
        instruction = f"{instruction} Target tone: {_tone_label(casual_score, formal_score)}."

    system = (
        "You are Pi, an AI writing assistant inside the Plane project management tool. "
        "Return only the resulting text (Markdown allowed). Do not add explanations, "
        "preambles, or surround the answer with quotes."
    )
    user = f"Task: {instruction}\n\nText:\n{text_input}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Work item copilot
# ---------------------------------------------------------------------------

COPILOT_SYSTEM = (
    "You are Pi, an expert project manager embedded in Plane. You help turn rough input "
    "into well-structured work items. Always reply with a single valid JSON object and "
    "nothing else."
)

COPILOT_JSON_SCHEMA = """{
  "name": "short, action-oriented work item title",
  "description_html": "clear HTML description using <p>, <ul>, <li>, <strong> only",
  "priority": "urgent | high | medium | low | none",
  "labels": ["label names chosen only from the provided list"],
  "assignee_hint": "a member name/email from the provided list, or empty string",
  "estimate": "a short sizing hint or empty string",
  "subtasks": [{"name": "subtask title"}]
}"""


def build_copilot_messages(
    *,
    prompt: str,
    title: str | None = None,
    description: str | None = None,
    available_labels: list[str] | None = None,
    available_members: list[str] | None = None,
    mode: str = "full",
) -> list[dict]:
    available_labels = available_labels or []
    available_members = available_members or []

    if mode == "subtasks":
        instruction = (
            "Break the work item below into a concise list of actionable subtasks. "
            "Return only JSON with the `subtasks` key."
        )
    elif mode == "acceptance_criteria":
        instruction = (
            "Write acceptance criteria for the work item below as a JSON object with "
            "`description_html` containing a bulleted list."
        )
    else:
        instruction = "Produce a complete work item from the input below."

    context = [
        f"Project labels available: {', '.join(available_labels) if available_labels else '(none)'}",
        f"Project members available: {', '.join(available_members) if available_members else '(none)'}",
    ]
    user = (
        f"{instruction}\n\n"
        f"Rough input:\n{prompt}\n\n"
        + (f"Existing title: {title}\n" if title else "")
        + (f"Existing description:\n{description}\n" if description else "")
        + "\n".join(context)
        + f"\n\nRespond with JSON matching this schema:\n{COPILOT_JSON_SCHEMA}"
    )
    return [
        {"role": "system", "content": COPILOT_SYSTEM},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Intake triage
# ---------------------------------------------------------------------------

TRIAGE_SYSTEM = (
    "You are Pi, a triage assistant for the Plane project management tool. "
    "Analyze the incoming work item and reply with a single valid JSON object."
)

TRIAGE_JSON_SCHEMA = """{
  "summary": "one or two sentence summary",
  "priority": "urgent | high | medium | low | none",
  "labels": ["label names from the provided list"],
  "assignee_hint": "a member name/email from the provided list, or empty string",
  "is_actionable": true
}"""


def build_triage_messages(
    *,
    name: str,
    description: str,
    available_labels: list[str] | None = None,
    available_members: list[str] | None = None,
    duplicate_candidates: list[dict] | None = None,
) -> list[dict]:
    available_labels = available_labels or []
    available_members = available_members or []
    duplicates = duplicate_candidates or []

    duplicate_lines = "\n".join(
        f"- [{item.get('sequence_id', '?')}] {item.get('name', '')}" for item in duplicates
    )
    user = (
        f"Incoming work item:\nName: {name}\nDescription:\n{description or '(empty)'}\n\n"
        f"Project labels: {', '.join(available_labels) if available_labels else '(none)'}\n"
        f"Project members: {', '.join(available_members) if available_members else '(none)'}\n"
        f"Possible duplicates:\n{duplicate_lines or '(none found)'}\n\n"
        f"Respond with JSON matching this schema:\n{TRIAGE_JSON_SCHEMA}"
    )
    return [
        {"role": "system", "content": TRIAGE_SYSTEM},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Workspace Q&A (RAG)
# ---------------------------------------------------------------------------

ASK_SYSTEM = (
    "You are Pi, a helpful assistant with access to this workspace's work items, pages, "
    "and comments. Answer the question using ONLY the provided context. Cite sources with "
    "their bracketed numbers, e.g. [1]. If the answer is not in the context, say you could "
    "not find it."
)


def build_ask_messages(question: str, chunks: list[dict]) -> list[dict]:
    context_lines = []
    for index, chunk in enumerate(chunks, start=1):
        label = chunk.get("label") or chunk.get("entity_type", "item")
        context_lines.append(f"[{index}] ({label}) {chunk.get('text', '')}")
    context = "\n\n".join(context_lines) if context_lines else "(no context found)"
    user = f"Context:\n{context}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": ASK_SYSTEM},
        {"role": "user", "content": user},
    ]


def copilot_result_to_html(result: dict[str, Any]) -> str:
    """Normalize a copilot result's description into safe-ish HTML."""
    description = result.get("description_html") or ""
    if description:
        return description
    plain = result.get("description") or ""
    return f"<p>{plain}</p>" if plain else ""


# ---------------------------------------------------------------------------
# Standalone assistant (chat + actions)
# ---------------------------------------------------------------------------

ASSISTANT_SYSTEM = (
    "You are Pi, the assistant built into the Plane project management tool. "
    "You help ONLY with this workspace: its work items, projects, cycles, modules, members, and how to use Plane. "
    "If the user asks about anything unrelated (general knowledge, coding, news, other products), politely refuse in "
    "one sentence and steer back to Plane/tasks. Never invent data that is not in the provided context. "
    "You are given: the identity of the user you are talking to, the list of members, the list of projects, and "
    "retrieved workspace context. If the user asks who they are, their name, email, or username, answer from the "
    "`You are talking to` line. "
    "You can CREATE work items and UPDATE existing work items (rename, edit description, change priority, "
    "assign/reassign or unassign a member, change state, add labels). "
    "When the user asks to create a work item, set `action.type` to `create_work_item`. "
    "When the user asks to assign, reassign, unassign, edit, rename, reprioritize, or move a work item, set "
    "`action.type` to `update_work_item` and fill `issue_hint` with the work item's identifier (like TEST-1) or title. "
    "A request can target ONE OR MANY people: put every requested assignee in the `assignee_hints` array (use the "
    "member names/emails exactly as given, and only from the provided members list). Assign one or multiple as asked. "
    "A request can also create or change MULTIPLE work items: return one object in the `actions` array per work item. "
    "Never claim you cannot assign or edit — you can, by returning the actions. "
    "Otherwise leave `actions` empty. "
    "Answer in the same language the user used. Always reply with a single valid JSON object and nothing else."
)

ASSISTANT_JSON_SCHEMA = """{
  "reply": "the message shown to the user (same language as the user)",
  "actions": [
    {
      "type": "create_work_item",
      "name": "work item title",
      "description_html": "optional HTML description (use <p>, <ul>, <li>)",
      "priority": "urgent | high | medium | low | none",
      "assignee_hints": ["one or more member names/emails from the provided members list"],
      "project_hint": "a project name or identifier chosen ONLY from the provided projects list, or empty string"
    },
    {
      "type": "update_work_item",
      "issue_hint": "identifier (e.g. TEST-1) or title of the work item to change",
      "project_hint": "project name or identifier, or empty string",
      "name": "new title, or omit/empty to keep",
      "description_html": "new HTML description, or omit/empty to keep",
      "priority": "urgent | high | medium | low | none, or omit/empty to keep",
      "assignee_hints": ["one or more member names/emails to assign"],
      "unassign": true,
      "state_hint": "state name, or empty string to keep",
      "labels": ["label names to set"]
    }
  ]
}"""


def build_assistant_messages(
    *,
    messages: list[dict],
    members: list[str] | None = None,
    projects: list[str] | None = None,
    context_chunks: list[dict] | None = None,
    current_user: str | None = None,
) -> list[dict]:
    members = members or []
    projects = projects or []
    context_chunks = context_chunks or []

    context_lines = [
        f"[{index}] ({chunk.get('entity_type', 'item')}) {chunk.get('text', '')}"
        for index, chunk in enumerate(context_chunks, start=1)
    ]
    grounding = (
        f"You are talking to: {current_user or '(unknown user)'}\n"
        f"Workspace members: {', '.join(members) if members else '(none)'}\n"
        f"Projects: {', '.join(projects) if projects else '(none)'}\n"
        f"Retrieved context:\n" + ("\n\n".join(context_lines) if context_lines else "(none)")
    )

    result = [
        {
            "role": "system",
            "content": (
                ASSISTANT_SYSTEM
                + "\n\n"
                + grounding
                + f"\n\nRespond with JSON matching this schema:\n{ASSISTANT_JSON_SCHEMA}"
            ),
        }
    ]
    # Keep only user/assistant turns from the client conversation.
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            result.append({"role": role, "content": content})
    return result

