# allow module import using: 'from awcy_nfo import ReadMe'
from .readme import ReadMe  # noqa

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError

try:
    __version__ = version(__name__)
except PackageNotFoundError: # frozen app support doesnt work with importlib
    __version__ = "0.1.1"
