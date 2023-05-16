# -*- coding: utf-8 -*-
"""Collect active SyncSketch server config."""
import pyblish.api


class CollectActiveServerConfig(pyblish.api.ContextPlugin):
    """Collect active SyncSketch server config from settings."""

    order = pyblish.api.CollectorOrder
    label = "Active SyncSketch Server"

    single = False

    def process(self, context):
        try:
            syncsketch_module = (
                context.data.get("openPypeModules")["syncsketch"])
        except AttributeError:
            self.log.error("Cannot get Ayon SyncSketch module.")
            raise AssertionError("Ayon SyncSketch module not found.")

        # get first active syncsketch server url from settings
        server_config = None
        for item in syncsketch_module.syncsketch_server_configs:
            if item["active"]:
                server_config = item
                break

        if server_config is None:
            context.data["syncsketchServerConfig"] = server_config
