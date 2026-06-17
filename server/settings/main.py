from pydantic import validator

from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    ensure_unique_names
)
from ayon_server.settings.enum import secrets_enum


class ServerConfigModel(BaseSettingsModel):
    username: str = SettingsField(
        "",
        enum_resolver=secrets_enum,
        title="API Username",
    )
    api_token: str = SettingsField(
        "",
        enum_resolver=secrets_enum,
        title="API Key",
    )
    server_url: str = SettingsField(
        "",
        title="SyncSketch Server URL",
        placeholder="https://www.syncsketch.com",
    )


class SyncsketchSettings(BaseSettingsModel):
    config: ServerConfigModel = SettingsField(
        default_factory=ServerConfigModel,
        title="SyncSketch server config",
    )


DEFAULT_VALUES = {
    "syncsketch_server_config": {
        "api_token": "",
        "username": "",
        "server_url": "",
    },
}
