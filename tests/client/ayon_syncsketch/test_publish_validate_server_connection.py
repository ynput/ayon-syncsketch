import pytest
import logging
import requests
import responses
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
                "url": "http://test.com",
                "auth_user": "test",
                "auth_token": "test"
            }
        })

        yield context

    def test_connected_correctly(self, mock_server, mock_context, plugin):
        url = 'http://test.com/api/v1/person/connected/'
        mock_server.add(responses.GET, url, status=200)
        plugin.process(mock_context)

    def test_connected_error(self, mock_server, mock_context, plugin):
        url = 'http://test.com/api/v1/person/connecte'
        mock_server.add(responses.GET, url, status=200)

        with pytest.raises(requests.exceptions.ConnectionError):
            plugin.process(mock_context)

    def test_missing_context_data(self, context, plugin):
        with pytest.raises(RuntimeError):
            plugin.process(context)
