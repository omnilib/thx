# Copyright 2021 John Reese
# Licensed under the MIT License

import click

from thx import __doc__, __version__


@click.group(help=__doc__)
@click.version_option(__version__, "--version", "-V")
def main():
    pass


@main.command("list")
def list_commands():
    """
    List available commands and exit.
    """
    pass
