from pydantic import Field, validator

from ayon_server.settings import BaseSettingsModel, ensure_unique_names

from .publish_plugins import (
    PublishPluginsModel,
    DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS
)


class ServerListSubmodel(BaseSettingsModel):
    active: bool = Field(title="Active")
    name: str = Field(title="Name")
    url: str = Field(title="Value")
    auth_token: str = Field(title="Auth Token")
    auth_user: str = Field(title="Auth Username")
    account_id: str = Field(title="Account ID")


class SyncsketchSettings(BaseSettingsModel):

    syncsketch_server_configs:  list[ServerListSubmodel] = Field(
        default_factory=list,
        title="SyncSketch server configs",
    )

    publish: PublishPluginsModel = Field(
        default_factory=PublishPluginsModel,
        title="Publish Plugins",
    )

    @validator("syncsketch_server_configs")
    def validate_unique_names(cls, value):
        ensure_unique_names(value)
        return value


DEFAULT_VALUES = {
    "syncsketch_server_configs": [
        {
            "active": True,
            "name": "default",
            "url": "https://www.syncsketch.com",
            "auth_token": "",
            "auth_user": "",
            "account_id": "",
        }
    ],
    "publish": DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS
}
