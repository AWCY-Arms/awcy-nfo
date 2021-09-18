# allow module import using: 'from awcy_nfo import ReadMe'
from .readme import ReadMe  # noqa

# TODO: doesnt work with pyinstaller
# get version number from pyproject.toml
# try:
#    from importlib.metadata import version, PackageNotFoundError
# except ImportError:
#    from importlib_metadata import version, PackageNotFoundError
# try:
#    __version__ = version(__name__)
# except PackageNotFoundError:
#    __version__ = "(unknown)"

__version__ = "0.1.0"
