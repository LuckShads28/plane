/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// The single source of truth for the AI client lives in @plane/services so the
// web app and any other consumer cannot drift. Re-exported here to keep existing
// `@/services/ai.service` imports working.
export { AIService } from "@plane/services";
export type {
  TTaskPayload,
  TAICopilotResponse,
  TAITriageResponse,
  TAISearchResult,
  TAIAskResponse,
  TAssistantResult,
  TAssistantResponse,
  TAssistantWorkItem,
} from "@plane/services";
