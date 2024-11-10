from platformdirs import PlatformDirs


def get_dirs(app_name: str, app_author: str, version: str):
    # ensure best practice: use versioned path
    return PlatformDirs(appname=app_name, appauthor=app_author, version=version)


__all__ = ['get_dirs']
