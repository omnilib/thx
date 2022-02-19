# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
import logging
import shlex
import shutil
from asyncio.subprocess import PIPE
from dataclasses import dataclass
from typing import List, Sequence

from .types import CommandResult, Config, Context, Job, Result, Step, StrPath

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
    run = run.format(**config.values, python_version=context.python_version)
    cmd = shlex.split(run)
    cmd[0] = which(cmd[0], context)
    return tuple(cmd)


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


@dataclass(frozen=True)
class JobStep(Step):
    async def run(self) -> Result:
        result = await run_command(self.cmd)

        return Result(
            step=self,
            context=self.context,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )


def prepare_job(job: Job, context: Context, config: Config) -> Sequence[Step]:
    tasks: List[Step] = []

    for item in job.run:
        cmd = render_command(item, context, config)
        tasks.append(JobStep(cmd=cmd, job=job, context=context))

    return tasks
