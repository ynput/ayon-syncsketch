# -*- coding: utf-8 -*-
"""Validate a SyncSketch connection."""
import pyblish.api
from ayon_syncsketch.api.server_handler import ServerCommunication
import requests


class ValidateServerConnection(pyblish.api.ContextPlugin):
    """Validate SyncSketch server connection.

    Validation is done by trying to connect to the server.
    syncsketch_id is required to be set on context.data.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate SyncSketch Connection"

    def process(self, context):
        syncsketch_id = context.data.get("projectSyncsketchId")
        server_config = context.data.get("syncsketchServerConfig")

        if not syncsketch_id:
            raise RuntimeError("SyncSketch ID is not set.")

        if not server_config:
            raise RuntimeError("SyncSketch server config is not set.")

        self.log.info("Validating SyncSketch connection...")
        self.log.info("SyncSketch ID: {}".format(syncsketch_id))
        self.log.info("SyncSketch server config: {}".format(server_config))

        response = self.get_json(server_config.get("url"))

        context.data["syncsketchServerResponse"] = response

    def get_json(self, url):
        resp = requests.get(url)
        assert resp.status_code == 200
        return resp.json()