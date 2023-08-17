from pydantic import Field

from ayon_server.settings import BaseSettingsModel
from ayon_server.settings.enum import secrets_enum

from .publish_plugins import (
    PublishPluginsModel,
    DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS
)


class ServerListSubmodel(BaseSettingsModel):
    url: str = Field(
        title="SyncSketch Server URL")
    auth_user: str = Field(
        enum_resolver=secrets_enum,
        title="Auth Username"
    )
    auth_token: str = Field(
        enum_resolver=secrets_enum,
        title="Auth Token"
    )
    account_id: str = Field(
        enum_resolver=secrets_enum,
        title="Account ID"
    )
    ftrack_url: str = Field(
        title="FTrack Server URL"
    )
    ftrack_api_key: str = Field(
        enum_resolver=secrets_enum,
        title="FTrack API Key"
    )
    ftrack_username: str = Field(
        enum_resolver=secrets_enum,
        title="FTrack Username"
    )


class SyncsketchSettings(BaseSettingsModel):

    syncsketch_server_config:  ServerListSubmodel = Field(
        default_factory=ServerListSubmodel,
        title="SyncSketch server config",
    )

    publish: PublishPluginsModel = Field(
        default_factory=PublishPluginsModel,
        title="Publish Plugins",
    )



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
    "publish": DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS
}
