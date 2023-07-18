import json
from typing import Type

from ayon_server.addons import BaseServerAddon, AddonLibrary
from ayon_server.config import ayonconfig
from ayon_server.lib.postgres import Postgres

from .settings import SyncsketchSettings, DEFAULT_VALUES

import requests


class SyncsketchAddon(BaseServerAddon):
    name = "syncsketch"
    title = "SyncSketch"
    version = "1.0.0"
    settings_model: Type[SyncsketchSettings] = SyncsketchSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def setup(self):
        self.create_syncsketch_webhook()
        need_restart = await self.create_applications_attribute()
        if need_restart:
            self.request_server_restart()

    def initialize(self):
        logging.info("Initializing SyncSketch Addon.")

        self.add_endpoint(
            "syncsketch-event",
            self._receive_syncsketch_event,
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
        ayon_endpoint = f"{ayonconfig.http_listen_address}/addons/{self.name}/{self.version}/syncsketch-event"

        if not addon_settings:
            logging.error(f"Unable to get Studio Settings: {self.name} addon.")
            return


        syncsketch_webhooks_endpoint = f"{addon_settings.syncsketch_url}/api/v2/notifications/{addon_settings.account_id}/webhooks/"

        payload={}
        headers = {
            'Authorization': 'apikey {{addon_settings.username}}:{{addon_settings.api_key}}',
            'Content-Type': 'application/json'
        }

        existing_webhooks = requests.request("GET", syncsketch_webhooks_endpoint, headers=headers, data=payload)
        if response.text:
            print(response.text)
            pass
        else:
            # Create the Webhook
            payload = json.dumps({
                "url": ayon_endpoint,
                "type": "item_created",
                "headers": {
                    "X-My-Custom-Header": "some-auth-token-etc" # Grab Ayon Auth token
                }
            })

            response = requests.request("POST", url, headers=headers, data=payload)

            print(response.text)


    async def _syncsketch_event(self, syncsketch_payload) -> Dict:
        """ Whenever SyncSket sends an event to the defined webhook, dispatch an
            Ayon event.
        """
        print("syncsketch_payload", syncsketch_payload)
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
            "inherit": False
        }

        id_scope = ["project", "version"]

        id_match_position = None
        id_matches = False

        position = 1

        async for row in Postgres.iterate(query):
            position += 1
            if row["name"] == id_attrib_name:
                # Check if scope is matching ftrack addon requirements
                if (set(row["scope"]) == set(id_scope)):
                    id_matches = True
                id_match_position = row["position"]

        if id_matches:
            return False

        postgres_query = "\n".join((
            "INSERT INTO public.attributes",
            "    (name, position, scope, data)",
            "VALUES",
            "    ($1, $2, $3, $4)",
            "ON CONFLICT (name)",
            "DO UPDATE SET",
            "    scope = $3,",
            "    data = $4",
        ))
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
