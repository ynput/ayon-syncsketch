import os
import sys
from dotenv import load_dotenv

load_dotenv()


def set_environment():
    ayon_root = os.getenv("AYON_ROOT")
    if ayon_root:
        ayon_root = os.path.abspath(ayon_root)
        print("AYON_ROOT: {}".format(ayon_root))
        sys.path.append(ayon_root)
    else:
        raise EnvironmentError("AYON_ROOT not set")

    env = {
        "SYNC_SKETCH_API_KEY": os.getenv("SYNC_SKETCH_API_KEY") or "test",
        "USE_AYON_SERVER": os.getenv("USE_AYON_SERVER") or "1",
        "OPENPYPE_ROOT": ayon_root,
        "OPENPYPE_REPOS_ROOT": ayon_root
    }

    for key, value in env.items():
        print("{}: {}".format(key, value))
        if not value:
            raise EnvironmentError("{} not set".format(key))
        os.environ[key] = value
