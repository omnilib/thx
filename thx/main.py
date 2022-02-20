# Copyright 2021 John Reese
# Licensed under the MIT License

import logging
import shutil
from functools import partial
from typing import Any, cast, List, Optional, Sequence

import click
from rich.logging import RichHandler

from . import __doc__
from .__version__ import __version__
from .cli import RichRenderer
from .config import load_config

from .core import run
from .types import Config, Options, Version
from .utils import get_timings


def queue_job(name: str, ctx: click.Context) -> None:
    """
    Add a job to the options queue
    """
    options: Options = ctx.obj
    options.jobs.append(name)


class ThxGroup(click.Group):
    """
    Generate click commands at runtime from configuration
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.config = load_config()

    def list_commands(self, ctx: click.Context) -> List[str]:
        commands = super().list_commands(ctx)
        commands += [""]
        commands += self.config.jobs.keys()
        return commands

    def create_command(self, name: str) -> Optional[click.Command]:
        if name == "":
            return click.Command("", help="", callback=lambda: True)
        if name in self.config.jobs:
            job = self.config.jobs[name]
            exe = "; ".join(r for r in job.run)
            desc = f"Run `{exe}`"
            cb = partial(queue_job, name)
            cb = click.pass_context(cb)
            return click.Command(name, callback=cb, help=desc)
        return None

    def get_command(self, ctx: click.Context, name: str) -> Optional[click.Command]:
        return super().get_command(ctx, name) or self.create_command(name)


@click.group(cls=ThxGroup, chain=True, invoke_without_command=True, help=__doc__)
@click.option("--benchmark", is_flag=True, default=None, help="Enable benchmarking")
@click.option("--debug", is_flag=True, default=None, help="Enable debug output")
@click.option("--clean", is_flag=True, help="Clean virtualenvs first")
@click.option("--live", is_flag=True, help='Use the "live" Python runtime from thx')
@click.option(
    "--python",
    "--py",
    "-p",
    type=Version,
    help="Run commands on a specific python version",
)
@click.version_option(__version__, "--version", "-V")
@click.pass_context
def main(
    ctx: click.Context,
    benchmark: bool,
    debug: bool,
    clean: bool,
    live: bool,
    python: Optional[Version],
) -> None:
    """
    Setup options and load config
    """
    group = cast(ThxGroup, main)

    if live and python:
        raise click.UsageError("Cannot specify both --live and --python")

    ctx.ensure_object(Options)
    ctx.obj.config = group.config
    ctx.obj.benchmark = benchmark
    ctx.obj.debug = debug
    ctx.obj.clean = clean
    ctx.obj.live = live
    ctx.obj.python = python

    log_format = (
        "%(levelname)s %(module)s:%(lineno)d: %(message)s"
        if debug
        else "%(levelname)s: %(message)s"
    )

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format=log_format,
        handlers=[RichHandler(rich_tracebacks=True)],
    )


@main.result_callback()
@click.pass_context
def process_request(ctx: click.Context, results: Sequence[Any], **kwargs: Any) -> None:
    """
    All click commands finished, start any jobs necessary
    """
    options: Options = ctx.obj
    if options.exit:
        return

    if not options.jobs and not options.config.default:
        ctx.invoke(list_commands)
        ctx.exit(1)

    if options.clean:
        ctx.invoke(clean)

    with RichRenderer() as renderer:
        results = run(options, render=renderer)  # do the thing

    if options.benchmark:
        click.echo("\nbenchmark timings:\n------------------")
        for timing in get_timings():
            click.echo(f"  {timing}")

    if any(result.error for result in results):
        click.secho("FAIL", fg="yellow", err=True)
        ctx.exit(1)


@main.command("clean")
@click.pass_context
def clean(ctx: click.Context) -> None:
    """
    Clean up virtual environments and data created by thx
    """
    config: Config = ctx.obj.config
    thx_dir = config.root / ".thx"
    if thx_dir.exists():
        click.echo(f"Cleaning {thx_dir} ...")
        shutil.rmtree(thx_dir)
    ctx.obj.exit = True


@main.command("list")
@click.pass_context
def list_commands(ctx: click.Context) -> None:
    """
    List available commands and exit.
    """
    print("<list commands here>")
    ctx.obj.exit = True
