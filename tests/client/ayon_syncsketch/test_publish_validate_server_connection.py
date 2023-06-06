import pytest
import logging
from tests.lib import PublishTest


log = logging.getLogger(__name__)


class TestPublishValidateServerConnection(PublishTest):

    @pytest.fixture
    def plugin(self, host_plugins):
        plugin = None
        for plugin_ in host_plugins:
            if plugin_.__name__ == "ValidateServerConnection":
                plugin = plugin_()
                plugin.log = log

        yield plugin

    @pytest.fixture
    def mock_context(self, context):
        context.data.update({
            "projectSyncsketchId": "1234567890",
            "syncsketchServerConfig": {
                "name": "testing",
                "active": True,
                "url": "http://test.com"
            }
        })

        yield context

    @pytest.mark.asyncio
    async def test_get_json(client, mock_server, mock_context, plugin):
        url = 'http://test.com'
        mock_server.get(url, payload={'key': 'value'})
        plugin.process(mock_context)
        resp = await get_json(client, url)
        assert resp == {'key': 'value'}