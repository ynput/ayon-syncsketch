from pydantic import Field, validator

from ayon_server.settings import (
    BaseSettingsModel,
    ensure_unique_names
)
from ayon_server.settings.enum import secrets_enum

from .publish_plugins import (
    PublishPluginsModel,
    DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS
)


class StatusesMapping(BaseSettingsModel):
    name: str = Field(
        title="SyncSketch Status")
    ftrack_status: str = Field(
        title="Frack Status")


class ServerListSubmodel(BaseSettingsModel):
    url: str = Field(
        title="SyncSketch Server URL")
    auth_user: str = Field(
        enum_resolver=secrets_enum,
        title="Auth Username")
    auth_token: str = Field(
        enum_resolver=secrets_enum,
        title="Auth Token")
    account_id: str = Field(
        enum_resolver=secrets_enum,
        title="Account ID")
    ftrack_url: str = Field(
        title="Ftrack Server URL")
    ftrack_api_key: str = Field(
        enum_resolver=secrets_enum,
        title="Ftrack API Key")
    ftrack_username: str = Field(
        enum_resolver=secrets_enum,
        title="Ftrack Username")


class SyncsketchSettings(BaseSettingsModel):

    syncsketch_server_config:  ServerListSubmodel = Field(
        default_factory=ServerListSubmodel,
        title="SyncSketch server config",
        scope=["studio"]
    )
    statuses_mapping: list[StatusesMapping] = Field(
        default_factory=list,
        title="Statuses Mapping",
        description="Map Ftrack and SyncSketch statuses.",
        scope=["studio"]
    )
    publish: PublishPluginsModel = Field(
        default_factory=PublishPluginsModel,
        title="Publish Plugins",
    )

    @validator("statuses_mapping")
    def ensure_unique_names(cls, value):
        """Ensure name fields within the lists have unique names."""
        ensure_unique_names(value)
        return value


DEFAULT_VALUES = {
    "syncsketch_server_config": {
        "url": "https://www.syncsketch.com",
        "auth_token": "",
        "auth_user": "",
        "account_id": "",
        "ftrack_url": "",
        "ftrack_api_key": "",
        "ftrack_username": "",
    },
    "statuses_mapping": [
        {
            "name": "Reviewed",
            "ftrack_status": "Change Requested",
        },
        {
            "name": "For Review",
            "ftrack_status": "Pending Review",
        },
        {
            "name": "In Progress",
            "ftrack_status": "Pending Review",
        },
        {
            "name": "Approved",
            "ftrack_status": "Approved",
        },
        {
            "name": "On Hold",
            "ftrack_status": "Completed",
        }
    ],
    "publish": DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS
}
