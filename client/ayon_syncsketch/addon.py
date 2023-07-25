import os
from openpype.settings import get_project_settings
from openpype.pipeline import get_current_project_name
from openpype.modules import (
    OpenPypeAddOn,
    IPluginPaths,
)
from ayon_api import get_addon_project_settings

SYNCSKETCH_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class SyncsketchAddon(OpenPypeAddOn, IPluginPaths):
    name = "syncsketch"
    enabled = True

    # TODO: replace constant with dynamic version
    version = "1.0.0"

    def get_syncsketch_project_active_config(self, project_name):
        """ Returns the active SyncSketch config for the current project """

        project_settings = get_addon_project_settings(
            self.name,
            self.version,
            project_name
        )

        # fallback to current project settings
        if not project_settings:
            project_settings = get_project_settings(
                get_current_project_name()
            )

        # get all configs
        configs = (
            project_settings["syncsketch_server_configs"]
        )

        # find the active one
        for config in configs:
            if config["active"]:
                return config

        # no active config found
        raise RuntimeError("No active SyncSketch config found")

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SYNCSKETCH_MODULE_DIR, "plugins", "publish")
            ]
        }

    def get_publish_plugin_paths(self, host_name):
        """Receive publish plugin paths.

        Give addons ability to add publish plugin paths based on host name.

        Notes:
           Default implementation uses 'get_plugin_paths' and always return
               all publish plugin paths.

        Args:
           host_name (str): For which host are the plugins meant.
        """
        return self._get_plugin_paths_by_type("publish")
