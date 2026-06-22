from typing import Type

from ayon_server.addons import BaseServerAddon
from ayon_server.actions import (
    ActionExecutor,
    SimpleActionManifest,
    ExecuteResponseModel,
)
from ayon_server.entity_lists import EntityList
from ayon_server.events import dispatch_event

from .settings import SyncsketchSettings, DEFAULT_VALUES


class SyncsketchAddon(BaseServerAddon):
    settings_model: Type[SyncsketchSettings] = SyncsketchSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def get_simple_actions(
        self,
        project_name: str | None = None,
        variant: str = "production",
    ) -> list["SimpleActionManifest"]:
        if not project_name:
            return []

        return [
            SimpleActionManifest(
                label="Push to SyncSketch",
                category="SyncSketch",
                identifier="syncsketch.push",
                entity_type="list",
                entity_subtypes=["version"],
                icon={
                    "type": "material-symbols",
                    "name": "publish",
                    "color": "#ffffff",
                },
                order=100,
            ),
            SimpleActionManifest(
                label="Pull from SyncSketch",
                category="SyncSketch",
                identifier="syncsketch.pull",
                entity_type="list",
                entity_subtypes=["version"],
                icon={
                    "type": "material-symbols",
                    "name": "download",
                    "color": "#ffffff",
                },
                order=100,
            ),
        ]

    async def execute_action(
        self,
        executor: "ActionExecutor",
    ) -> "ExecuteResponseModel":
        context = executor.context
        project_name = context.project_name
        entity_type = context.entity_type
        if entity_type != "list":
            return await executor.get_simple_response(
                "SyncSketch actions can only be executed on version lists.",
                success=False,
            )

        if context.entity_ids is None:
            return await executor.get_simple_response(
                "No selection of lists provided.",
                success=False,
            )

        valid_ids = set()
        for list_id in context.entity_ids:
            list_entity = await EntityList.load(project_name, list_id)
            if list_entity.entity_type == "version":
                valid_ids.add(list_id)

        if not valid_ids:
            return await executor.get_simple_response(
                "Selection does not contain version lists.",
                success=False,
            )

        if executor.identifier == "syncsketch.push":
            topic = "syncsketch.push.review"
            description = (
                "Push to SyncSketch can take a while."
                " Please wait until the action is finished."
            )
        else:
            topic = "syncsketch.pull.review"
            description = (
                "Pull from SyncSketch can take a while."
                " Please wait until the action is finished."
            )

        for list_id in valid_ids:
            await dispatch_event(
                topic,
                project=project_name,
                summary={"listId": list_id},
                finished=False,
                description=description,
            )

        return await executor.get_simple_response(
            "SyncSketch sync has been triggered",
            success=True,
        )
