# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.core.management.base import BaseCommand, CommandError

# Module imports
from plane.db.models import Workspace


class Command(BaseCommand):
    help = "Build/refresh AI embeddings for a workspace's work items, pages, and comments."

    def add_arguments(self, parser):
        parser.add_argument("slug", type=str, help="workspace slug")
        parser.add_argument(
            "--sync",
            action="store_true",
            help="run inline instead of enqueueing a Celery task",
        )

    def handle(self, *args, **options):
        slug = options.get("slug")
        workspace = Workspace.objects.filter(slug=slug).first()
        if not workspace:
            raise CommandError(f"Error: Workspace with slug '{slug}' does not exist")

        if options.get("sync"):
            from plane.utils.ai.indexing import reindex_workspace

            count = reindex_workspace(str(workspace.id))
            self.stdout.write(self.style.SUCCESS(f"Indexed {count} chunks for workspace '{slug}'"))
            return

        from plane.bgtasks.ai_embedding_task import reindex_workspace_task

        reindex_workspace_task.delay(str(workspace.id))
        self.stdout.write(self.style.SUCCESS(f"Enqueued reindex for workspace '{slug}'"))
