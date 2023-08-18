import os
from openpype.modules import (
    OpenPypeAddOn,
    IPluginPaths,
)
from ayon_syncsketch.common import config
from .version import __version__


SYNCSKETCH_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class SyncsketchAddon(OpenPypeAddOn, IPluginPaths):
    name = "syncsketch"
    enabled = True
    version = __version__

    def get_syncsketch_config(self, project_name):
        """ Returns the active SyncSketch config for the current project """
        addon_settings = config.get_addon_project_settings(
            project_name, self.version
        )
        server_config = addon_settings["syncsketch_server_config"]

        # resolve secrets into the server config
        config.merge_resolved_secrets(server_config)

        return server_config

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
