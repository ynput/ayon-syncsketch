import argparse
from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).parent


def get_package_content() -> dict:
    package_path = CURRENT_DIR.parent.parent / "package.py"
    content = {}
    exec(package_path.read_text(), content)
    return content


def get_addon_version() -> str:
    content = get_package_content()
    return content["version"]


def get_image_name() -> str:
    content = get_package_content()
    return content["services"]["processor"]["image"]


def get_image_version() -> str:
    image_name = get_image_name()
    return image_name.split(":")[-1]


def get_image_base_name() -> str:
    image_name = get_image_name()
    return image_name.split("/")[-1].split(":", maxsplit=1)[0]


def main():
    parser = argparse.ArgumentParser(
        description="Helper script to get information about the addon."
    )
    subparser = parser.add_subparsers(dest="command")
    subparser.add_parser("image", help="Get the full image name.")
    subparser.add_parser("image-version", help="Get the version of image.")
    subparser.add_parser("image-base", help="Get the base name of image.")
    subparser.add_parser("addon-version", help="Get addon version.")
    subparser.add_parser("all", help="Print all information.")

    result = parser.parse_args()
    if result.command is None:
        parser.print_help()
        sys.exit(1)

    if result.command == "image":
        print(get_image_name())
    elif result.command == "image-base":
        print(get_image_base_name())
    elif result.command == "image-version":
        print(get_image_version())
    elif result.command == "addon-version":
        print(get_addon_version())
    elif result.command == "all":
        print("|".join([
            get_image_name(),
            get_image_base_name(),
            get_image_version(),
            get_addon_version(),
        ]))
    else:
        parser.print_help()
        raise RuntimeError(
            f"Unknown command '{result.command}'."
        )


if __name__ == "__main__":
    main()
