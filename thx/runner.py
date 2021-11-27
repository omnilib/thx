# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
from asyncio.subprocess import PIPE
import shlex
import shutil
from dataclasses import dataclass
import subprocess
from typing import Sequence, Dict, Any, Optional, Generator, List

from .types import Config, Command, Result


def which(name: str, config: Config) -> str:
    binary = shutil.which(name)
    if binary is None:
        return name
    return binary


def render_command(run: str, config: Config) -> Sequence[str]:
    run = run.format(**config.values)
    cmd = shlex.split(run)
    cmd[0] = which(cmd[0], config)
    return cmd


@dataclass
class Job:
    cmd: Sequence[str]
    config: Config

    def __await__(self) -> Generator[Any, None, Result]:
        return self.run().__await__()

    async def run(self) -> Result:
        proc = await asyncio.create_subprocess_exec(
            *self.cmd, stdout=PIPE, stderr=PIPE
        )
        stdout, stderr = await proc.communicate()
        assert proc.returncode is not None

        return Result(
            command=self.cmd,
            exit_code=proc.returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )


def prepare_command(command: Command, config: Config) -> Sequence[Job]:
    tasks: List[Job] = []

    for item in command.run:
        cmd = render_command(item, config)
        tasks.append(Job(cmd=cmd, config=config))

    return tasks
