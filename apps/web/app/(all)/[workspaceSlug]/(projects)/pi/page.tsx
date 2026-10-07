/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// components
import { AIAssistantRoot } from "@/components/ai-assistant/root";
import { PageHead } from "@/components/core/page-title";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
// local imports
import type { Route } from "./+types/page";

function AIAssistantPage({ params }: Route.ComponentProps) {
  // store hooks
  const { currentWorkspace } = useWorkspace();
  // derived values
  const title = currentWorkspace?.name ? `${currentWorkspace.name} - Pi` : "Pi";

  return (
    <>
      <PageHead title={title} />
      <AIAssistantRoot workspaceSlug={params.workspaceSlug} />
    </>
  );
}

export default observer(AIAssistantPage);
