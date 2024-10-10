import os
import sys
from pathlib import Path

import responses
import pytest
from unittest.mock import Base

from .config_tests import set_environment

# setting environment variables
set_environment()

# adding client directory to sys.path
client_dir = Path(os.path.dirname(os.path.abspath(__file__))) \
    / ".." /  "client"
client_api_dir = client_dir / "ayon_syncsketch" / "api"

print("Adding client directory to sys.path: {}".format(client_dir.resolve()))
sys.path.append(str(client_dir))
sys.path.append(str(client_api_dir))


# basic testing class
class BaseTest:
    """Base class for all tests."""

    @pytest.fixture(scope="package")
    def ayon_addons_manager(self):
        import ayon_start  # noqa F401
        from ayon_core.addon import AddonsManager

        yield AddonsManager

    # This is the pytest fixture that creates a mock server
    @pytest.fixture
    def mock_server(self):
        with responses.RequestsMock(
            assert_all_requests_are_fired=False
        ) as rsps:
            yield rsps


class PublishTest(BaseTest):
    @pytest.fixture(scope="package")
    def syncsketch_addon(self, ayon_addons_manager):
        manager = ayon_addons_manager()
        yield manager["syncsketch"]

    @pytest.fixture(scope="package")
    def host_plugins(self, syncsketch_addon):
        import pyblish.api
        from ayon_core.pipeline import install_ayon_plugins
        install_ayon_plugins(host_name="syncsketch")

        yield pyblish.api.discover()

    @pytest.fixture
    def context(self, syncsketch_addon):
        from pyblish.api import Context as PyblishContext

        class Context(PyblishContext):
            data = {
                "ayonAddons": {
                    "syncsketch": syncsketch_addon
                }
            }
        yield Context
