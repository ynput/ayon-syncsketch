import json
from pprint import pformat
import socket
from typing import Type, Any

import httpx
from nxtools import logging, log_traceback

from ayon_server.config import ayonconfig
from ayon_server.secrets import Secrets
from ayon_server.addons import BaseServerAddon
from ayon_server.events import dispatch_event
from ayon_server.lib.postgres import Postgres

from .common import constants
from .settings import SyncsketchSettings, DEFAULT_VALUES


class SyncsketchAddon(BaseServerAddon):
    settings_model: Type[SyncsketchSettings] = SyncsketchSettings

    async def resolved_secrets(self):
        addon_settings = await self.get_studio_settings()
        syncsk_server_config = addon_settings.syncsketch_server_config
        syncsk_server_config = dict(syncsk_server_config)
        all_secrets = await Secrets.all()
        secrets = dict(dict(all_secrets.items()))

        # resolve all secrets from the server config
        resolved_secrets = {
            key_: secrets[syncsk_server_config[key_]]
            for key_ in constants.required_secret_keys
            if syncsk_server_config[key_] in secrets
        }

        return resolved_secrets

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def setup(self):
        need_restart = await self.create_syncsketch_id_attribute()
        if need_restart:
            self.request_server_restart()

        await self.create_syncsketch_webhook()

    def initialize(self):
        logging.info("Initializing SyncSketch Addon.")

        self.add_endpoint(
            "syncsketch-event",
            self._syncsketch_event,
            method="POST",
            name="receive-syncsketch-event",
            description="Create an Ayon Event, from a SyncSketch event.",
        )
        logging.info("Added Event Listener Webhook.")


    async def create_syncsketch_webhook(self):
        """Create a SyncSketch Webhook for new events.

        The Ayon SyncSketch integration will create an end point
        that will listen for events coming from SyncSketch and later
        process them with the processor.

        Here we use the  REST API to check if the webhook exists, and if not,
        we create it.
        """
        addon_settings = await self.get_studio_settings()
        syncsk_server_config = addon_settings.syncsketch_server_config
        all_secrets = await self.resolved_secrets()
        timeout = ayonconfig.http_timeout


        # is manageable via server env variable AYON_HTTP_LISTEN_ADDRESS
        ayon_endpoint = (f"{ayonconfig.http_listen_address}/api/addons/"
                         f"{self.name}/{self.version}/syncsketch-event")

        if not syncsk_server_config:
            logging.error(f"Unable to get Studio Settings: {self.name} addon.")
            return

        if not all((
            syncsk_server_config.url,
        )):
            logging.error("Missing data in the Addon settings.")
            return

        # make sure all config secrets are present otherwise return
        # TODO: this is just a workaround until we create correct workflow
        # for the secrets. We need to first set settings to get secrets.
        if len(all_secrets.keys()) != len(constants.required_secret_keys):
            logging.warning("Missing secrets in the server config.")
            return

        syncsketch_endpoint = (
            f"{syncsk_server_config.url}/api/v2/notifications/"
            f"{all_secrets['account_id']}/webhooks/"
        )

        headers = {
            "Authorization": (
                f"apikey {all_secrets['auth_user']}:"
                f"{all_secrets['auth_token']}"
            ),
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(
                    syncsketch_endpoint,
                    headers=headers,
                )
                res.raise_for_status()
                existing_webhooks = res.json()
        except Exception:
            log_traceback("Unable to get existing Webhooks in SyncSketch.")
            return

        if existing_webhooks:
            for webhook in existing_webhooks:
                if (
                    webhook.get("url") == ayon_endpoint
                    and webhook.get("type") == "all"
                ):
                    logging.info(f"AYON Webhook already exists: {webhook}")
                    return

        # Create the Webhook that sends an event when a session ends

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                webhook_created = await client.post(
                    syncsketch_endpoint,
                    headers=headers,
                    json={
                        "url": ayon_endpoint,
                        "type": "all",
                    }
                )
                webhook_created.raise_for_status()
        except Exception:
            log_traceback("Unable to create a Webhook in SyncSketch.")
            return

        logging.info(
            "Successfully created a Webhook in "
            f"SyncSketch {webhook_created.json()}"
        )

    async def _syncsketch_event(self, request: dict[str, Any]):
        """Dispatch an Ayon event from a SyncSketch one.
        """

        if request["action"] in [
            "review_session_end",
            "item_approval_status_changed"
        ]:
            logging.info(
                f"Webhook received with a payload: {pformat(request)}.")
            project_name = request["project"]["name"]

            event_id = await dispatch_event(
                f"syncsketch.{request['action']}",
                sender=socket.gethostname(),
                project=project_name,
                user="",
                description=(
                    "SyncSketch source webhook event "
                    f"\'{request['action']}\' received."
                ),
                summary=None,
                payload=request,
            )
            logging.info(f"Dispatched event {event_id}")
            return event_id

        logging.warning(
            f"Received a SyncSketch event that we don't handle. {request}"
        )

    async def create_syncsketch_id_attribute(self) -> bool:
        """Make sure there are required attributes which ftrack addon needs.

        Returns:
            bool: 'True' if an attribute was created or updated.
        """
        query = "SELECT name, position, scope, data from public.attributes"

        id_attrib_name = "syncsketchId"

        id_attribute_data = {
            "type": "string",
            "title": "SyncSketch ID",
            "inherit": False,
        }

        id_scope = ["project", "version"]

        id_match_position = None
        id_matches = False

        position = 1

        async for row in Postgres.iterate(query):
            position += 1
            if row["name"] == id_attrib_name:
                # Check if scope is matching ftrack addon requirements
                if set(row["scope"]) == set(id_scope):
                    id_matches = True
                id_match_position = row["position"]

        if id_matches:
            return False

        postgres_query = "\n".join(
            (
                "INSERT INTO public.attributes",
                "    (name, position, scope, data)",
                "VALUES",
                "    ($1, $2, $3, $4)",
                "ON CONFLICT (name)",
                "DO UPDATE SET",
                "    scope = $3,",
                "    data = $4",
            )
        )
        # Reuse position from found attribute
        if id_match_position is None:
            id_match_position = position
            position += 1

        await Postgres.execute(
            postgres_query,
            id_attrib_name,
            id_match_position,
            id_scope,
            id_attribute_data,
        )

        return True
