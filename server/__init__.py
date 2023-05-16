from typing import Type

from ayon_server.addons import BaseServerAddon, AddonLibrary

from .settings import SyncsketchSettings, DEFAULT_VALUES


class SyncsketchAddon(BaseServerAddon):
    name = "syncsketch"
    title = "SyncSketch"
    version = "1.0.0"
    settings_model: Type[SyncsketchSettings] = SyncsketchSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)
