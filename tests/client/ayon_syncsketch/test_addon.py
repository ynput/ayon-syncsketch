import pytest
from tests.lib import BaseTest


class TestSyncsketchAddon(BaseTest):
    # TODO: this is not up to date and needs to be updated
    def test_get_syncsketch_config(self, ayon_module_manager):
        mock_settings = {
            "syncsketch": {
                "syncsketch_server_configs": [
                    {"name": "config1", "active": False},
                    {"name": "config2", "active": True},
                    {"name": "config3", "active": False}
                ]
            }
        }
        manager = ayon_module_manager()
        syncsketch_addon = manager["syncsketch"]

        # Test return value for active config
        active_config = syncsketch_addon.get_syncsketch_config(
            mock_settings
        )
        assert active_config["name"] == "config2"

        # Test raising RuntimeError when no active config found
        mock_settings = {
            "syncsketch": {
                "syncsketch_server_configs": [
                    {"name": "config1", "active": False},
                    {"name": "config2", "active": False},
                    {"name": "config3", "active": False}
                ]
            }
        }

        with pytest.raises(RuntimeError):
            syncsketch_addon.get_syncsketch_config(
                mock_settings
            )
