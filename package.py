# -*- coding: utf-8 -*-
"""Package declaring addon version."""
name = "syncsketch"
title = "SyncSketch"
version = "0.3.0+dev"

services = {
    "processor": {"image": "ynput/ayon-syncsketch-processor:1.0.0"}
}

ayon_required_addons = {
    "core": ">=0.4.0",
}
ayon_compatible_addons = {}
