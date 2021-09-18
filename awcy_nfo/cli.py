import click
import logging
import click_logging

from click_logging.core import ClickHandler

from . import __version__
from .helpers import (
    ColorFormatter,
    show_headers_option,
    show_styles_option,
    get_example_option,
    get_style_option,
)
from .readme import ReadMe, app_name


# when used as an app: default stream handler
logger = logging.getLogger(__package__)
# redirect err levels to stderr
log_echo = {
    "error": dict(err=True),
    "exception": dict(err=True),
    "critical": dict(err=True),
}
shndl = ClickHandler(echo_kwargs=log_echo)
shndl.name = __package__ + "_stream"
shndl.level = logging.DEBUG
# stylize log levels for terminal display
log_style = {
    "debug": dict(fg="blue"),
    "warning": dict(fg="yellow"),
    "error": dict(fg="red", blink=False),
    "exception": dict(fg="red", blink=False),
    "critical": dict(fg="white", bg="red", blink=True),
}
shndl.formatter = ColorFormatter(style_kwargs=log_style)
logger.addHandler(shndl)


@click.command()
@click.argument(
    "yamlfile",
    type=click.Path(exists=True, readable=True),
)
@click.option(
    "-o",
    "--output",
    help="Complete filepath or directory to output readme file. (optional)",
    type=click.Path(writable=True),
)
@click.option(
    "-f",
    "--filename",
    help="Readme filename, overrides '--output' if given a filepath. (optional)",
)
@click.option(
    "-h",
    "--header",
    help="Filepath/name of ascii header file, overrides template header. (optional)",
)
@click.option(
    "-s",
    "--style",
    help="Filepath/name of yaml style file, overrides template style. (optional)",
)
@click.option(
    "-l",
    "--log",
    help="Create a log file of the readme.txt creation processes. [True or False]",
    type=bool,
    show_default=True,
    default=True,
)
@click_logging.simple_verbosity_option(
    logger,
    help="Application verbosity level. [CRITICAL, ERROR, WARNING, INFO, or DEBUG].",
    show_default=True,
    default="ERROR",
)
@show_headers_option()
@show_styles_option()
@get_example_option()
@get_style_option()
@click.version_option(version=__version__, prog_name=app_name)
def create_readme(yamlfile, output, filename, header, style, log):
    """... Create AWCY? readme.txt using a .yaml template file ..."""

    # file logger verbosity defaults to 'info', can only be overriden by 'debug'
    file_log_verbosity = (
        logging.DEBUG if logger.level == logging.DEBUG else logging.INFO
    )

    # Unfortunately logger level is reset by click_logger's 'simple_verbosity_option'.
    # This is retarded. Instead, set the logger level back to debug, and update the
    # stream handler's level with the users desired verbosity level.
    for handler in logger.handlers:
        if handler.get_name() == __package__ + "_stream":
            handler.setLevel(logger.level)
            logger.setLevel(logging.DEBUG)

    # Preheat the oven....
    ReadMe(
        yamlfile=yamlfile,
        output=output,
        filename=filename,
        header=header,
        style=style,
        log_to_file=log,
        log_verbosity=file_log_verbosity,
    ).create_readme()
