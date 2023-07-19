import json
from typing import Type, Any

from ayon_server.addons import BaseServerAddon, AddonLibrary
from ayon_server.config import ayonconfig
from ayon_server.lib.postgres import Postgres
from ayon_server.types import OPModel

from .settings import SyncsketchSettings, DEFAULT_VALUES

from nxtools import logging
import requests


class SyncsketchRequestModel(OPModel):
    """ TODO: Once we get the corerct acces for the SyncSketch API implement a proper
        model to handle the webhook POST paylaod.
    """
    payload: dict[str, Any]


class SyncsketchAddon(BaseServerAddon):
    name = "syncsketch"
    title = "SyncSketch"
    version = "1.0.0"
    settings_model: Type[SyncsketchSettings] = SyncsketchSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def setup(self):
        need_restart = await self.create_applications_attribute()
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

        The Ayon SynckSketch integration will create an endoint that will listen
        for events coming from SyncSketch and later process them with the processor.

        Here we use the  REST API to check if the webhook exists, and if not, we
        create it.
        """
        addon_settings = await self.get_studio_settings()
        addon_settings = addon_settings.syncsketch_server_configs[0]

        # This really doenst work in local
        ayon_endpoint = f"{ayonconfig.http_listen_address}/api/addons/{self.name}/{self.version}/syncsketch-event"

        if not addon_settings:
            logging.error(f"Unable to get Studio Settings: {self.name} addon.")
            return

        if not all((addon_settings.url, addon_settings.auth_token, addon_settings.auth_user, addon_settings.account_id)):
            logging.error("Missing data in the Addon settings.")
            return

        sk_endpoint = f"{addon_settings.url}/api/v2/notifications/{addon_settings.account_id}/webhooks/"

        headers = {
            "Authorization": f"apikey {addon_settings.auth_user}:{addon_settings.auth_token}",
            "Content-Type": "application/json",
        }

        existing_webhooks = requests.request("GET", sk_endpoint, headers=headers)

        if existing_webhooks.status_code == 400:
            logging.error(existing_webhooks.json())
            return

        if existing_webhooks.text:
            # Check if the webhook we care already exists and return early
            print(existing_webhooks.text)
            print(existing_webhooks.json())
            pass

        # Create the Webhook that sends an event when a session ends
        webhook_created = requests.request(
            "POST",
            sk_endpoint,
            headers=headers,
            data={
                "url": ayon_endpoint,
                "type": "review_ended",
            },
        )

        if webhook_created.status_code != 200:
            logging.info("Something went wrong when trying to create the Webhook.")
            raise ValueError(webhook_created.json())

        logging.info(
            f"Succesfully created a Webhook in SyncSketch {webhook_created.json()}"
        )

    async def _syncsketch_event(self, request: SyncsketchRequestModel):
        """Dispatch an Ayon event from a SyncSketch one.
        """
        print("syncsketch locals", locals())
        # event_id = await dispatch_event(
        #     "syncsketch.event",
        #     sender=socket.gethostname(),
        #     project=project_name,
        #     user=user_name,
        #     description=description,
        #     summary=None,
        #     payload={
        #         "action": action,
        #         "user_name": user_name,
        #         "project_name": project_name,
        #     },
        # )
        # logging.info(f"Dispatched event {event_id}")
        # return event_id

    async def create_applications_attribute(self) -> bool:
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
        if not id_matches:
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
