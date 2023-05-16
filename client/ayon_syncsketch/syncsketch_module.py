import os
from openpype.modules import OpenPypeModule
from openpype_interfaces import (
    IPluginPaths,
    ILaunchHookPaths
)

SYNCSKETCH_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class SyncsketchIntegrationModule(OpenPypeModule, IPluginPaths, ILaunchHookPaths):
    """Allows uploading reviewables for SyncSketch review."""

    name = "syncsketch"

    def initialize(self, modules_settings):
        slack_settings = modules_settings[self.name]
        self.enabled = slack_settings["enabled"]

    def get_plugin_paths(self):
        """SyncSketch plugin paths."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return {
            "publish": [os.path.join(current_dir, "plugins", "publish")]
        }
