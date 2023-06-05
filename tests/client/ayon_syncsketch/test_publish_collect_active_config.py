import pytest
import logging
from tests.lib import BaseTest
from pyblish.api import Context as PyblishContext

log = logging.getLogger(__name__)


class TestSyncsketchAddon(BaseTest):

    @pytest.fixture
    def syncsketch_addon(self, ayon_module_manager):
        manager = ayon_module_manager()
        yield manager["syncsketch"]

    @pytest.fixture
    def context(self, syncsketch_addon):
        class Context(PyblishContext):
            data = {
                "openPypeModules": {
                    "syncsketch": syncsketch_addon
                }
            }
        yield Context


    @pytest.fixture
    def plugin(self, syncsketch_addon):
        import pyblish.api
        from openpype.pipeline import install_openpype_plugins
        install_openpype_plugins(host_name="syncsketch")

        plugins = pyblish.api.discover()
        plugin = None
        for plugin_ in plugins:
            if plugin_.__name__ == "CollectActiveServerConfig":
                plugin = plugin_()
                plugin.log = log

        yield plugin

    def test_active_server_collector_one_active(self, context, plugin):
        context.data["project_settings"] = {
            "syncsketch": {
                "syncsketch_server_configs": [
                    {"name": "config1", "active": False},
                    {"name": "config2", "active": True},
                    {"name": "config3", "active": False}
                ]
            }
        }
        plugin.process(context)
        assert context.data.get("syncsketchServerConfig")["name"] == "config2"

    def test_active_server_collector_none_active(self, context, plugin):
        context.data["project_settings"] = {
            "syncsketch": {
                "syncsketch_server_configs": [
                    {"name": "config1", "active": False},
                    {"name": "config2", "active": False},
                    {"name": "config3", "active": False}
                ]
            }
        }

        with pytest.raises(RuntimeError):
            plugin.process(context)