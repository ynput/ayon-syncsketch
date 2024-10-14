# -*- coding: utf-8 -*-
"""Package declaring addon version."""
name = "syncsketch"
title = "SyncSketch"
version = "0.1.2-dev.1"
client_dir = "ayon_syncsketch"

# TODO: need to make sure image is published to docker hub
services = {
    "processor": {"image": f"ynput/ayon-syncsketch-processor:{version}"}
}

ayon_required_addons = {
    "core": ">=0.4.0",
}
ayon_compatible_addons = {}
