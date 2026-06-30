from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)
from ayon_server.settings.enum import secrets_enum


class ServerConfigModel(BaseSettingsModel):
    username: str = SettingsField(
        "",
        enum_resolver=secrets_enum,
        title="API Username",
    )
    api_key: str = SettingsField(
        "",
        enum_resolver=secrets_enum,
        title="API Key",
    )
    server_url: str = SettingsField(
        "",
        title="SyncSketch Server URL",
        placeholder="https://www.syncsketch.com",
    )


def _project_mapping_enum():
    return [
        {"value": "match", "label": "Match Project Name"},
        {"value": "selection", "label": "Select from list"},
    ]


class SyncProjectSelection(BaseSettingsModel):
    _layout = "expanded"
    project_names: list[str] = SettingsField(
        default_factory=list,
        title="SyncSketch Project Names",
        description="SyncSketch projects to select from.",
    )
    allow_custom_name: bool = SettingsField(
        False,
        title="Allow custom project name",
        description="Allow user to enter a custom project name.",
    )


class SyncModel(BaseSettingsModel):
    _isGroup = True
    project_mapping: str = SettingsField(
        "match",
        title="Project Mapping",
        description="Mapping between AYON project and SyncSketch project.",
        enum_resolver=_project_mapping_enum,
        conditional_enum=True,
    )
    selection: SyncProjectSelection = SettingsField(
        default_factory=SyncProjectSelection,
    )


class SyncsketchSettings(BaseSettingsModel):
    config: ServerConfigModel = SettingsField(
        default_factory=ServerConfigModel,
        title="SyncSketch server config",
    )
    sync: SyncModel = SettingsField(
        default_factory=SyncModel,
        title="Sync options",
    )


DEFAULT_VALUES = {
    "syncsketch_server_config": {
        "api_key": "",
        "username": "",
        "server_url": "",
    },
}
