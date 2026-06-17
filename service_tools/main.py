import argparse
import os
import sys

from ayon_api.constants import (
    DEFAULT_VARIANT_ENV_KEY,
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(CURRENT_DIR)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--service",
        help="Run processor service",
        choices=["processor"],
    )
    parser.add_argument(
        "--variant",
        default="production",
        help="Settings variant",
    )
    opts = parser.parse_args()
    if opts.variant:
        os.environ[DEFAULT_VARIANT_ENV_KEY] = opts.variant

    service_name = opts.service
    if service_name == "processor":
        sys.path.append(os.path.join(ADDON_DIR, "services", service_name))
        from processor import main as service_main
    else:
        raise ValueError(f"Unknown service name {service_name}")

    service_main()


if __name__ == "__main__":
    main()
