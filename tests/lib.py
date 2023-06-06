from unittest.mock import Base
import pytest
import os
import sys
import responses
from pathlib import Path


from .config_tests import set_environment

# setting environment variables
set_environment()

# adding client directory to sys.path
client_dir = Path(os.path.dirname(os.path.abspath(__file__))) \
    / ".." /  "client"

print("Adding client directory to sys.path: {}".format(client_dir.resolve()))
sys.path.append(str(client_dir))

# basic testing class
class BaseTest:
    """Base class for all tests."""

    @pytest.fixture(scope="package")
    def ayon_module_manager(self):
        import ayon_start
        from openpype.modules import ModulesManager

        yield ModulesManager

    # This is the pytest fixture that creates a mock server
    @pytest.fixture
    def mock_server(self):
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            yield rsps


class PublishTest(BaseTest):
    @pytest.fixture(scope="package")
    def syncsketch_addon(self, ayon_module_manager):
        manager = ayon_module_manager()
        yield manager["syncsketch"]

    @pytest.fixture(scope="package")
    def host_plugins(self, syncsketch_addon):
        import pyblish.api
        from openpype.pipeline import install_openpype_plugins
        install_openpype_plugins(host_name="syncsketch")

        yield pyblish.api.discover()

    @pytest.fixture
    def context(self, syncsketch_addon):
        from pyblish.api import Context as PyblishContext

        class Context(PyblishContext):
            data = {
                "openPypeModules": {
                    "syncsketch": syncsketch_addon
                }
            }
        yield Context