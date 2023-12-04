import os
import re

PATH_RE = re.compile("iCloud.com.omz.software.Pythonista([\d+])")


def pythonista_version() -> int | None:
    m = PATH_RE.search(os.getcwd())
    if m:
        return int(m.group(1))
    return None


def in_pythonista() -> bool:
    return pythonista_version() is not None
