# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from celery import shared_task

# Module imports
from plane.utils.exception_logger import log_exception


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_jitter=True,
    max_retries=3,
)
def embed_entity_task(self, entity_type: str, entity_id: str) -> int:
    """(Re)build embeddings for one workspace entity."""
    from plane.utils.ai.indexing import index_entity

    try:
        return index_entity(entity_type, entity_id)
    except Exception as exc:
        log_exception(exc)
        raise


@shared_task
def reindex_workspace_task(workspace_id: str) -> int:
    """Reindex all supported entities in a workspace."""
    from plane.utils.ai.indexing import reindex_workspace

    return reindex_workspace(workspace_id)
