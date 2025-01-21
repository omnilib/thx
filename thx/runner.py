# Copyright 2022 Amethyst Reese
# Licensed under the MIT License

import asyncio
import logging
import os
import shlex
from asyncio.subprocess import PIPE
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .types import (
    CommandError,
    CommandResult,
    Config,
    Context,
    Job,
    Result,
    Step,
    StrPath,
)
from .utils import venv_bin_path, which

LOG = logging.getLogger(__name__)


def render_command(run: str, context: Context, config: Config) -> Sequence[str]:
    run = run.format(**config.values, python_version=context.python_version)
    cmd = shlex.split(run)
    cmd[0] = which(cmd[0], context)
    return tuple(cmd)


async def run_command(
    command: Sequence[StrPath], context: Optional[Context] = None
) -> CommandResult:
    cmd: Sequence[str] = [str(c) for c in command]
    new_env: Optional[Dict[str, str]] = None
    if context:
        new_env = os.environ.copy()
        new_env["PATH"] = f"{venv_bin_path(context.venv)}{os.pathsep}{new_env['PATH']}"
        new_env["VIRTUAL_ENV"] = str(context.venv)
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=PIPE, stderr=PIPE, env=new_env
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode is not None
    LOG.debug("command `%s` finished with code %d", shlex.join(cmd), proc.returncode)

    return CommandResult(
        proc.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")
    )


async def check_command(
    command: Sequence[StrPath], context: Optional[Context] = None
) -> CommandResult:
    result = await run_command(command, context)

    if result.error:
        raise CommandError(command, result)

    return result


@dataclass(frozen=True)
class JobStep(Step):
    async def run(self) -> Result:
        result = await run_command(self.cmd, self.context)

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
