
from openpype.settings import get_project_settings
from openpype.pipeline import get_current_project_name
from ayon_api import get_addon_project_settings


def get_syncsketch_project_config(project_name, addon_version):
    """Returns the active SyncSketch config for the current project

    Args:
        project_name (str): name of the project
        addon_version (str): version of the addon

    Returns:
        dict: SyncSketch config
    """

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