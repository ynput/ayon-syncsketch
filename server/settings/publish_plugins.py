from pydantic import Field

from ayon_server.settings import BaseSettingsModel


class CollectActiveSyncsketchServerModel(BaseSettingsModel):
    """Settings for active SyncSketch server."""

    single: bool = Field(title="Single SyncSketch server")


class PublishPluginsModel(BaseSettingsModel):
    CollectActiveSyncsketchServer: CollectActiveSyncsketchServerModel = \
        Field(
            default_factory=CollectActiveSyncsketchServerModel,
            title="Collect active SyncSketch server"
        )


DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS = {
    "CollectActiveSyncsketchServer":  {
        "single": True
    }
}
