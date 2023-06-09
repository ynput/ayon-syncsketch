import pytest
import logging
from tests.lib import PublishTest


log = logging.getLogger(__name__)


class TestPublishCollectActiveConfig(PublishTest):

    @pytest.fixture
    def plugin(self, host_plugins):
        plugin = None
        for plugin_ in host_plugins:
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
