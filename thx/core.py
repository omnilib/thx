# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
from typing import AsyncIterator, List, Sequence

from thx.context import prepare_contexts

from .runner import prepare_job
from .types import Config, Context, Event, Job, Result, Start


def resolve_jobs(names: Sequence[str], config: Config) -> Sequence[Job]:
    queue: List[Job] = []

    for name in names:
        if name not in config.jobs:
            raise ValueError(f"unknown job {name!r}")
        job = config.jobs[name]

        if job.requires:
            deps = resolve_jobs(job.requires, config)
            for dep in deps:
                if dep not in queue:
                    queue.append(dep)

        queue.append(job)

    return queue


async def run_jobs_on_context(
    jobs: Sequence[Job], context: Context, config: Config
) -> AsyncIterator[Event]:
    for job in jobs:
        steps = prepare_job(job, context, config)
        for step in steps:
            yield Start(command=step.cmd, job=job, context=context)
            result = await step
            yield result
            if not result.success:
                return


async def run_jobs(
    jobs: Sequence[Job], contexts: Sequence[Context], config: Config
) -> AsyncIterator[Event]:
    await prepare_contexts(contexts, config)

    active_jobs: List[Job] = list(jobs)
    for context in contexts:
        async for event in run_jobs_on_context(active_jobs, context, config):
            if isinstance(event, Start) and event.job.once:
                active_jobs.remove(event.job)
            yield event


def run(
    jobs: Sequence[Job], contexts: Sequence[Context], config: Config
) -> List[Result]:
    results: List[Result] = []

    async def runner() -> None:
        async for event in run_jobs(jobs, contexts, config):
            print(event)

            if isinstance(event, Result):
                if not event.success:
                    print(
                        f"------------\nexit code: {event.exit_code}\n"
                        f"stdout:\n{event.stdout}\n\n"
                        f"stderr:\n{event.stderr}\n------------"
                    )
                results.append(event)

    asyncio.run(runner())
    return results
