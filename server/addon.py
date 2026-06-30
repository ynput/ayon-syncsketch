from dataclasses import dataclass, field
from typing import Type

from ayon_server.addons import BaseServerAddon
from ayon_server.actions import (
    ActionExecutor,
    SimpleActionManifest,
    ExecuteResponseModel,
)
from ayon_server.entity_lists import EntityList
from ayon_server.events import dispatch_event
from ayon_server.forms import SimpleForm, FormSelectOption

from .settings import SyncsketchSettings, DEFAULT_VALUES


@dataclass
class ActionProjectSelection:
    project_names: list[str] = field(default_factory=list)
    allow_custom_name: bool = False
    selected_project_name: str | None = None


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
        if context.project_name is None:
            return await executor.get_simple_response(
                "SyncSketch actions need project.",
                success=False,
            )

        project_name = context.project_name
        if context.entity_type != "list":
            return await executor.get_simple_response(
                "SyncSketch actions can only be executed on version lists.",
                success=False,
            )

        if context.entity_ids is None:
            return await executor.get_simple_response(
                "No selection of lists provided.",
                success=False,
            )

        list_entities = []
        for list_id in context.entity_ids:
            list_entity = await EntityList.load(project_name, list_id)
            if list_entity.entity_type == "version":
                list_entities.append(list_entity)

        if not list_entities:
            return await executor.get_simple_response(
                "Selection does not contain version lists.",
                success=False,
            )

        if executor.identifier == "syncsketch.push":
            sketch_project_name, response = await self._push_prepare_data(
                project_name, list_entities, executor
            )
            if response is not None:
                return response

            topic = "syncsketch.push.review"
            description = (
                "Push to SyncSketch can take a while."
                " Please wait until the action is finished."
            )
        elif executor.identifier == "syncsketch.push":
            # Pull does not require a project name as each list either has it
            #   filled or current project should be used.
            sketch_project_name = None
            topic = "syncsketch.pull.review"
            description = (
                "Pull from SyncSketch can take a while."
                " Please wait until the action is finished."
            )
        else:
            return await executor.get_simple_response(
                f"Unknown action identifier: {executor.identifier}",
                success=False,
            )

        for list_entity in list_entities:
            summary = {"listId": list_entity.id}
            if sketch_project_name:
                summary["syncsketchProject"] = sketch_project_name

            await dispatch_event(
                topic,
                project=project_name,
                summary=summary,
                finished=False,
                description=description,
            )

        return await executor.get_simple_response(
            "SyncSketch sync has been triggered",
            success=True,
        )

    async def _push_prepare_data(
        self,
        project_name: str,
        list_entities: list[EntityList],
        executor: "ActionExecutor",
    ) -> tuple[str | None, ExecuteResponseModel | None]:
        """Prepare response or SyncSketch project name for sync action.

        Based on settings can show a form. In case settings define that
            current project should be used or if all selected list entities
            already have filled project name then no form is showed and event
            is triggered.

        In case a response is returned, the project should be ignored. The
            project is set to None if the selected project is the same as
            the AYON project.

        Args:
            project_name (str): The AYON project name.
            list_entities (list[EntityList]): List of selected version lists.
            executor (ActionExecutor): The action executor instance.

        Returns:
            tuple[str | None, ExecuteResponseModel | None]: A tuple containing
                SyncSketch project name or action response.

        """
        selection = await self._prepare_push_project_selection(
            project_name, list_entities, executor
        )
        if selection.selected_project_name:
            output_project = selection.selected_project_name
            if output_project.lower() == project_name.lower():
                output_project = None
            return output_project, None

        options = [
            FormSelectOption(
                value=project_name,
                label=project_name,
            )
            for project_name in selection.project_names
        ]
        default = None
        if options:
            default = options[0]["value"]

        if selection.allow_custom_name:
            options.insert(0, FormSelectOption(
                value="__custom__project_name__",
                label="< Custom project name >",
            ))

        if not options:
            return None, await executor.get_simple_response(
                (
                    "Settings is missing SyncSketch project names"
                    " to select from."
                ),
                success=False,
            )

        if default is None:
            default = options[0]["value"]

        form = SimpleForm().select(
            "project_name",
            label="SyncSketch Project",
            options=options,
            value=default,
        )
        if selection.allow_custom_name:
            form.text(
                "custom_project_name",
                label="Custom project name",
                value="",
                placeholder=(
                    "Select '< Custom project name >' to enter"
                    " a custom name"
                ),
            )

        return None, await executor.get_form_response(
            title="Select SyncSketch Project",
            fields=form,
            submit_label="Confirm project",
        )

    async def _prepare_push_project_selection(
        self,
        project_name: str,
        list_entities: list[EntityList],
        executor: "ActionExecutor",
    ) -> ActionProjectSelection:
        output = ActionProjectSelection()
        form_data = executor.context.form_data
        if form_data and form_data.get("project_name"):
            project_name = form_data["project_name"]
            if project_name == "__custom__project_name__":
                project_name = form_data.get("custom_project_name", "").strip()
            output.selected_project_name = project_name
            return output

        project_needed = False
        for list_entity in list_entities:
            syncsketch_meta = list_entity.payload.data.get("syncsketch")
            if not syncsketch_meta or not syncsketch_meta.get("project"):
                project_needed = True
                break

        if not project_needed:
            output.selected_project_name = project_name
            return output

        settings: SyncsketchSettings | None = await self.get_project_settings(
            project_name, variant=executor.variant
        )
        if settings is None:
            return output

        project_mapping = settings.sync.project_mapping
        if project_mapping == "match":
            output.project_names.append(project_name)
            output.selected_project_name = project_name

        elif project_mapping == "selection":
            selection_settings = settings.sync.selection
            output.project_names = list(selection_settings.project_names)
            output.allow_custom_name = selection_settings.allow_custom_name
            if (
                len(output.project_names) == 1
                and not selection_settings.allow_custom_name
            ):
                output.selected_project_name = output.project_names[0]

        return output
