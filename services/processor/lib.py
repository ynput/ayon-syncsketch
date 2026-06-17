from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ayon_api
import requests


@dataclass
class SyncsketchConfig:
    username: str
    api_key: str
    server_url: str


def get_syncksketch_settings() -> dict[str, Any]:
    """Get SyncSketch addon settings from AYON server."""
    addon_name = ayon_api.get_service_addon_name()
    addon_version = ayon_api.get_service_addon_version()
    variant = ayon_api.get_default_settings_variant()
    return ayon_api.get_addon_settings(
        addon_name,
        addon_version,
        variant=variant,
    )


def get_syncsketch_config(
    settings: dict[str, Any] | None = None,
) -> SyncsketchConfig:
    """Get SyncSketch server config from AYON server"""
    if settings is None:
        settings = get_syncksketch_settings()
    config = settings["config"]

    username_secret = config["username"]
    api_key_secret = config["api_key"]

    secrets = {s["name"]: s["value"] for s in ayon_api.get_secrets()}
    username = secrets.get(username_secret, "")
    api_key = secrets.get(api_key_secret, "")

    return SyncsketchConfig(
        username=username,
        api_key=api_key,
        server_url=config["server_url"] or "https://www.syncsketch.com",
    )


def validate_syncsketch_credentials(
    config: SyncsketchConfig | None = None,
    settings: dict[str, Any] | None = None,
) -> bool:
    """Check if SyncSketch credentials are set in the addon settings."""
    if config is None:
        config = get_syncsketch_config(settings)
    if not config.username or not config.api_key:
        return False

    response = requests.get(
        f"{config.server_url}/api/v1/person/connected/",
        params={
            "api_key": config.api_key,
            "username": config.username,
        },
    )
    return response.status_code == 200
