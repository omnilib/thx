# Copyright 2021 John Reese
# Licensed under the MIT License

from functools import partial
from typing import Sequence, Any, List, Optional

import click

from . import __doc__
from .__version__ import __version__
from .config import load_config
from .types import Options


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
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.version_option(__version__, "--version", "-V")
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """
    Setup options and load config
    """
    ctx.ensure_object(Options)
    ctx.obj.debug = debug
    ctx.obj.config = load_config()


@main.result_callback()
@click.pass_context
def process_request(ctx: click.Context, results: Sequence[Any], **kwargs: Any) -> None:
    """
    All click commands finished, start any jobs necessary
    """
    options: Options = ctx.obj
    if options.exit:
        return

    job_names = options.jobs
    if not job_names:
        if options.config.default:
            print(f"using {options.config.default=!r}")
            job_names.extend(options.config.default)
        else:
            ctx.invoke(list_commands)
            ctx.exit(1)
    print(f"will run: {job_names!r}")


@main.command("list")
@click.pass_context
def list_commands(ctx: click.Context) -> None:
    """
    List available commands and exit.
    """
    print("<list commands here>")
    ctx.obj.exit = True
