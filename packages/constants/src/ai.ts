/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum AI_EDITOR_TASKS {
  IMPROVE_WRITING = "IMPROVE_WRITING",
  FIX_SPELLING_GRAMMAR = "FIX_SPELLING_GRAMMAR",
  SHORTEN = "SHORTEN",
  EXPAND_WRITING = "EXPAND_WRITING",
  SUMMARIZE = "SUMMARIZE",
  CHANGE_TONE = "CHANGE_TONE",
  TRANSLATE = "TRANSLATE",
  ASK_ANYTHING = "ASK_ANYTHING",
}

export const LOADING_TEXTS = {
  [AI_EDITOR_TASKS.IMPROVE_WRITING]: "Pi is improving your writing",
  [AI_EDITOR_TASKS.FIX_SPELLING_GRAMMAR]: "Pi is fixing spelling and grammar",
  [AI_EDITOR_TASKS.SHORTEN]: "Pi is shortening your text",
  [AI_EDITOR_TASKS.EXPAND_WRITING]: "Pi is expanding your text",
  [AI_EDITOR_TASKS.SUMMARIZE]: "Pi is summarizing your text",
  [AI_EDITOR_TASKS.CHANGE_TONE]: "Pi is changing the tone",
  [AI_EDITOR_TASKS.TRANSLATE]: "Pi is translating your text",
  [AI_EDITOR_TASKS.ASK_ANYTHING]: "Pi is generating response",
} satisfies { [key in AI_EDITOR_TASKS]: string };
