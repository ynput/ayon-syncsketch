from pydantic import Field, validator

from ayon_server.settings import BaseSettingsModel, ensure_unique_names

from .publish_plugins import (
    PublishPluginsModel,
    DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS
)


class ServerListSubmodel(BaseSettingsModel):
    _layout = "compact"
    name: str = Field(title="Name")
    value: str = Field(title="Value")
    active: bool = Field(title="Active")


class SyncsketchSettings(BaseSettingsModel):

    syncsketch_server_urls:  list[ServerListSubmodel] = Field(
        default_factory=list,
        title="SyncSketch server URLs",
    )

    publish: PublishPluginsModel = Field(
        default_factory=PublishPluginsModel,
        title="Publish Plugins",
    )

    @validator("syncsketch_server_urls")
    def validate_unique_names(cls, value):
        ensure_unique_names(value)
        return value


DEFAULT_VALUES = {
    "syncsketch_server_urls": [
        {
            "name": "default",
            "value": "http://studio.syncsketch.com",
            "active": True
        }
    ],
    "publish": DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS
}
