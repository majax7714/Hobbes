"""String helpers."""

import os.path


def normalize(item):
    return item.strip().lower()


def data_dir():
    return os.path.join(os.environ["MINIAPP_HOME"], "data")
