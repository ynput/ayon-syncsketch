# -*- coding: utf-8 -*-
"""Package declaring addon version."""
name = "syncsketch"
title = "SyncSketch"
version = "0.4.0+dev"

services = {
    "processor": {"image": "ynput/ayon-syncsketch-processor:1.0.0"}
}

ayon_server_version = ">=1.15.9"
ayon_required_addons = {
    "core": ">=0.4.0",
}
ayon_compatible_addons = {
    "review": ">=0.6.0",
}
