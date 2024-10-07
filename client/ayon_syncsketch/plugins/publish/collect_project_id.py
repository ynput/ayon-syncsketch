# -*- coding: utf-8 -*-
"""Collect active SyncSketch server config."""
from pprint import pformat
import pyblish.api


class CollectSyncSketchProjectID(pyblish.api.ContextPlugin):
    """Collect SyncSketch project id from project's anatomy attributes."""

    order = pyblish.api.CollectorOrder + 0.003
    label = "Collect SyncSketch Project ID"

    def process(self, context):
        project_doc = context.data["projectEntity"]
        self.log.debug(pformat(project_doc["data"]))

        project_id = project_doc["data"].get("syncsketchId")
        self.log.debug(project_id)

        if project_id:
            context.data["syncsketchProjectId"] = project_id
