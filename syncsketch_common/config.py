
import ayon_api
from ayon_api import get_addon_project_settings


def get_syncsketch_project_config(project_name, addon_version):
    """Returns the active SyncSketch config for the current project

    Args:
        project_name (str): name of the project
        addon_version (str): version of the addon

    Returns:
        dict: SyncSketch config
    """
    from openpype.settings import get_project_settings
    from openpype.pipeline import get_current_project_name

    project_settings = get_addon_project_settings(
        "syncsketch",
        addon_version,
        project_name
    )

    # fallback to current project settings
    if not project_settings:
        project_settings = get_project_settings(
            get_current_project_name()
        )

    return project_settings["syncsketch_server_config"]


def get_resolved_secrets(syncsk_server_config):
    """ Get resolved secrets from the server config.

    Args:
        syncsk_server_config (dict): The server config dict.

    Returns:
        dict: The resolved secrets.
    """
    from .constants import required_secret_keys

    all_secrets = ayon_api.get_secrets()
    secrets = {secret["name"]: secret["value"] for secret in all_secrets}

    # resolve all secrets from the server config
    resolved_secrets = {
        key_: secrets[syncsk_server_config[key_]]
        for key_ in required_secret_keys
        if syncsk_server_config[key_] in secrets
    }

    return resolved_secrets
