import os
import click
import shutil
import logging
import contextlib
import warnings

# suppress pandas future warnings
warnings.simplefilter(action="ignore", category=FutureWarning)
import pandas as pd
from click import option, echo_via_pager
from pkg_resources import resource_listdir
from pathlib import Path


def get_style_option(*param_decls, **kwargs):
    """Add a ``--get-style`` option which creates a copy of a
    style.yaml example file.
    :param param_decls: One or more option names. Defaults to the single
        value ``"--get-style"``.
    :param kwargs: Extra arguments are passed to :func:`option`.
    """

    def callback(ctx, param, value):
        if not value or ctx.resilient_parsing:
            return
        fp = __package__ + "/styles/classic.yaml"
        cd = Path.cwd()
        sp = cd.joinpath("classic_example.yaml")
        shutil.copyfile(fp, sp)
        ctx.exit()

    if not param_decls:
        param_decls = ("--get-style",)

    kwargs.setdefault("is_flag", True)
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault("is_eager", True)
    kwargs.setdefault("help", "Get a copy of an example style.yaml file and exit.")
    kwargs["callback"] = callback
    return option(*param_decls, **kwargs)


def get_example_option(*param_decls, **kwargs):
    """Add a ``--get-example`` option which creates a copy of a
    template.yaml example file.
    :param param_decls: One or more option names. Defaults to the single
        value ``"--get-example"``.
    :param kwargs: Extra arguments are passed to :func:`option`.
    """

    def callback(ctx, param, value):
        if not value or ctx.resilient_parsing:
            return
        fp = __package__ + "/docs/example.yaml"
        cd = Path.cwd()
        sp = cd.joinpath("example.yaml")
        shutil.copyfile(fp, sp)
        ctx.exit()

    if not param_decls:
        param_decls = ("--get-example",)

    kwargs.setdefault("is_flag", True)
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault("is_eager", True)
    kwargs.setdefault("help", "Get an example template.yaml file and exit.")
    kwargs["callback"] = callback
    return option(*param_decls, **kwargs)


def show_styles_option(*param_decls, **kwargs):
    """Add a ``--show-styles`` option which immediately prints
    available styles and exits the program.
    :param param_decls: One or more option names. Defaults to the single
        value ``"--show-styles"``.
    :param kwargs: Extra arguments are passed to :func:`option`.
    """

    def callback(ctx, param, value):
        if not value or ctx.resilient_parsing:
            return
        fs = resource_listdir(__package__, "styles")
        for f in fs:
            print(f)
        ctx.exit()

    if not param_decls:
        param_decls = ("--show-styles",)

    kwargs.setdefault("is_flag", True)
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault("is_eager", True)
    kwargs.setdefault("help", "Show available styles and exit.")
    kwargs["callback"] = callback
    return option(*param_decls, **kwargs)


def show_headers_option(*param_decls, **kwargs):
    """Add a ``--show-headers`` option which immediately prints
    available headers and exits the program.
    :param param_decls: One or more option names. Defaults to the single
        value ``"--show-headers"``.
    :param kwargs: Extra arguments are passed to :func:`option`.
    """

    def callback(ctx, param, value):
        if not value or ctx.resilient_parsing:
            return
        pd.set_option("display.max_rows", None)
        fs = resource_listdir(__package__, "headers")
        for f in fs:
            fp = __package__ + "/headers/" + f
            df = pd.read_csv(fp, error_bad_lines=False)
            echo_via_pager(f + "\n\n" + df.to_string())
        ctx.exit()

    if not param_decls:
        param_decls = ("--show-headers",)

    kwargs.setdefault("is_flag", True)
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault("is_eager", True)
    kwargs.setdefault(
        "help", "Scroll through available headers with 'Q' key, and then exit."
    )
    kwargs["callback"] = callback
    return option(*param_decls, **kwargs)


@contextlib.contextmanager
def temp_filename(suffix=None):
    """Context that introduces a temporary file.

    Creates a temporary file, yields the name, and on context exit, deletes it.
    (In contrast, tempfile.NamedTemporaryFile() provides a 'file' object and
    deletes the file as soon as the file object is closed, thus the temporary file
    cannot be safely re-opened by another library or process.)

    Args:
        suffix: desired filename extension (e.g. '.txt').

    Yields:
        The name of the temporary file.
    """

    import tempfile

    try:
        f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        f.readlines()
        tmp_name = f.name
        f.close()
        yield tmp_name
    finally:
        os.unlink(tmp_name)


class ColorFormatter(logging.Formatter):
    def __init__(self, style_kwargs):
        super().__init__()
        self.style_kwargs = style_kwargs

    def formatMessage(self, record):
        # format 'exception' level log event messages
        msg = super().formatMessage(record)
        level = "exception"
        if self.style_kwargs.get(level):
            prefix = click.style("{}: ".format(level), **self.style_kwargs[level])
            return "\n".join(prefix + x for x in msg.splitlines())
        return msg

    def format(self, record):
        if not record.exc_info:
            level = record.levelname.lower()
            msg = record.getMessage()
            if self.style_kwargs.get(level):
                prefix = click.style("{}: ".format(level), **self.style_kwargs[level])
                msg = "\n".join(prefix + x for x in msg.splitlines())
            return msg
        return logging.Formatter.format(self, record)


class ProcLogFileFormatter(logging.Formatter):
    """Logging Formatter

    Styles logging levels for the optional 'processing' logger.
    """

    def format(self, record):
        if record.levelno == logging.INFO:
            self._style._fmt = "%(message)s"
        elif record.levelno == logging.CRITICAL or record.levelno == logging.FATAL:
            self._style._fmt = "[*** %(levelname)s ***]: %(message)s"
        else:  # DEBUG, WARNING, ERROR
            self._style._fmt = "[%(levelname)s]: %(message)s"
        return super().format(record)
