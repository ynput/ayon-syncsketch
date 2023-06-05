import pytest
import os
import sys
from pathlib import Path

from .config_tests import set_environment

# setting environment variables
set_environment()

# adding client directory to sys.path
client_dir = Path(os.path.dirname(os.path.abspath(__file__))) \
    / ".." / ".." / "client"

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
