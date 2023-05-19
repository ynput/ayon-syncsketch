import pytest
import ayon_start
from openpype.modules import ModulesManager


class TestSyncsketchAddon:

    def test_get_syncsketch_project_active_config(self):
        mock_settings = {
            "syncsketch": {
                "syncsketch_server_configs": [
                    {"name": "config1", "active": False},
                    {"name": "config2", "active": True},
                    {"name": "config3", "active": False}
                ]
            }
        }
        manager = ModulesManager()
        syncsketch_addon = manager["syncsketch"]

        # Test return value for active config
        active_config = syncsketch_addon.get_syncsketch_project_active_config(
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
            syncsketch_addon.get_syncsketch_project_active_config(
                mock_settings
            )
