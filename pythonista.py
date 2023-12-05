import os
import re
import platform

PATH_RE = re.compile("iCloud.com.omz.software.Pythonista([\d+])")


def pythonista_version() -> int | None:
    m = PATH_RE.search(os.getcwd())
    if m:
        return int(m.group(1))
    return None


def in_pythonista() -> bool:
    return (
        pythonista_version() is not None
        or platform.platform().startswith("iPadOS")
        or platform.platform().startswith("iOS")
    )


if __name__ == "__main__":
    ver = pythonista_version()
    if ver is None:
        print(
            f"No Pythonista version, path is {os.getcwd()} {platform.platform()} {platform.system()} {platform.release()}"
        )
        if in_pythonista():
            print("In Pythonista")
    else:
        print(f"Pythonista version is {ver}")
