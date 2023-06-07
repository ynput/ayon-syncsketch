# -*- coding: utf-8 -*-
"""Validate a SyncSketch connection."""
import pyblish.api
from openpype_modules.ayon_syncsketch.api.server_handler import ServerCommunication
import requests


class ValidateServerConnection(pyblish.api.ContextPlugin):
    """Validate SyncSketch server connection.

    Validation is done by trying to connect to the server.
    syncsketch_id is required to be set on context.data.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate SyncSketch Connection"

    def process(self, context):
        syncsketch_id = context.data.get("syncsketchProjectId")
        server_config = context.data.get("syncsketchServerConfig")

        if not syncsketch_id:
            raise RuntimeError("SyncSketch ID is not set.")

        if not server_config:
            raise RuntimeError("SyncSketch server config is not set.")

        self.log.info("Validating SyncSketch connection...")
        self.log.info("SyncSketch ID: {}".format(syncsketch_id))
        self.log.info("SyncSketch server config: {}".format(server_config))

        server_handler = ServerCommunication(
            user_auth=server_config.get("auth_user"),
            api_key=server_config.get("auth_token"),
            host=server_config.get("url")
        )

        response = server_handler.is_connected()

        if not response:
            raise requests.exceptions.ConnectionError("SyncSketch connection failed.")
