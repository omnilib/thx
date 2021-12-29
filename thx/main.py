# Copyright 2021 John Reese
# Licensed under the MIT License

import logging
import shutil
import sys
from functools import partial
from typing import Any, List, Optional, Sequence

import click

from thx.context import resolve_contexts
from . import __doc__
from .__version__ import __version__
from .config import load_config

from .core import resolve_jobs, run
from .types import Config, Options, Version
from .utils import version_match


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
        self._config = load_config()

    def list_commands(self, ctx: click.Context) -> List[str]:
        commands = super().list_commands(ctx)
        commands += [""]
        commands += self._config.jobs.keys()
        return commands

    def create_command(self, name: str) -> Optional[click.Command]:
        if name == "":
            return click.Command("", help="", callback=lambda: True)
        if name in self._config.jobs:
            job = self._config.jobs[name]
            exe = "; ".join(r for r in job.run)
            desc = f"Run `{exe}`"
            cb = partial(queue_job, name)
            cb = click.pass_context(cb)
            return click.Command(name, callback=cb, help=desc)
        return None

    def get_command(self, ctx: click.Context, name: str) -> Optional[click.Command]:
        return super().get_command(ctx, name) or self.create_command(name)


@click.group(cls=ThxGroup, chain=True, invoke_without_command=True, help=__doc__)
@click.option("--debug", is_flag=True, default=None, help="Enable debug output")
@click.option(
    "--python",
    "--py",
    "-p",
    type=Version,
    help="Run commands on a specific python version",
)
@click.version_option(__version__, "--version", "-V")
@click.pass_context
def main(ctx: click.Context, debug: bool, python: Optional[Version]) -> None:
    """
    Setup options and load config
    """
    ctx.ensure_object(Options)
    ctx.obj.config = load_config()
    ctx.obj.python = python
    ctx.obj.debug = debug

    log_format = (
        "%(levelname)s %(module)s:%(lineno)d: %(message)s"
        if debug
        else "%(levelname)s: %(message)s"
    )

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if debug else logging.WARNING,
        format=log_format,
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

    config = options.config

    contexts = resolve_contexts(config)
    if options.python:
        context_versions = [context.python_version for context in contexts]
        matched_versions = version_match(context_versions, options.python)
        contexts = [
            context
            for context in contexts
            if context.python_version in matched_versions
        ]
    print(f"runtimes: {[str(ctx.python_version) for ctx in contexts]}")

    job_names = options.jobs
    if not job_names:
        if config.default:
            job_names.extend(config.default)
        else:
            ctx.invoke(list_commands)
            ctx.exit(1)

    print(f"will run: {job_names!r}")
    jobs = resolve_jobs(job_names, config)
    run(jobs, contexts, config)


@main.command("clean")
@click.pass_context
def clean(ctx: click.Context) -> None:
    """
    Clean up virtual environments and data created by thx
    """
    config: Config = ctx.obj.config
    thx_dir = config.root / ".thx"
    if thx_dir.exists():
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
