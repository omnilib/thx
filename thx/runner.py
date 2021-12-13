# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
import logging
import shlex
import shutil
from asyncio.subprocess import PIPE
from dataclasses import dataclass
from typing import Any, Generator, List, Sequence

from .types import CommandResult, Config, Context, Job, Result, StrPath

LOG = logging.getLogger(__name__)


def which(name: str, context: Context) -> str:
    bin_path = (context.venv / "bin").as_posix()
    binary = shutil.which(name, path=bin_path)
    if binary is None:
        binary = shutil.which(name)
        if binary is None:
            return name
    return binary


def render_command(run: str, context: Context, config: Config) -> Sequence[str]:
    run = run.format(**config.values)
    cmd = shlex.split(run)
    cmd[0] = which(cmd[0], context)
    return cmd


async def run_command(command: Sequence[StrPath]) -> CommandResult:
    cmd: Sequence[str] = [str(c) for c in command]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    assert proc.returncode is not None
    cmd_str = " ".join(shlex.quote(arg) for arg in cmd)
    LOG.debug("command `%s` finished with code %d", cmd_str, proc.returncode)

    return CommandResult(
        proc.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")
    )


@dataclass
class Step:
    cmd: Sequence[str]
    job: Job
    context: Context
    config: Config

    def __await__(self) -> Generator[Any, None, Result]:
        return self.run().__await__()

    async def run(self) -> Result:
        result = await run_command(self.cmd)

        return Result(
            command=self.cmd,
            job=self.job,
            context=self.context,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )


def prepare_job(job: Job, context: Context, config: Config) -> Sequence[Step]:
    tasks: List[Step] = []

    for item in job.run:
        cmd = render_command(item, context, config)
        tasks.append(Step(cmd=cmd, job=job, context=context, config=config))

    return tasks
