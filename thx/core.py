# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
import logging
from re import A
from time import monotonic_ns
from typing import AsyncIterable, AsyncIterator, List, Optional, Sequence

from aioitertools.asyncio import as_generated
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .context import prepare_contexts, resolve_contexts

from .runner import prepare_job
from .types import (
    Abort,
    Config,
    Context,
    Event,
    Fail,
    Job,
    Options,
    Renderer,
    Result,
    Start,
    Step,
)
from .utils import timed

LOG = logging.getLogger(__name__)


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


async def run_step_on_context(step: Step, context: Context) -> AsyncIterator[Event]:
    yield Start(step=step, context=context)
    result = await step
    yield result


async def run_job_on_context(
    job: Job, context: Context, config: Config
) -> AsyncIterator[Event]:
    with timed("run job", context, job):
        steps = prepare_job(job, context, config)

        if job.parallel:
            generators = [run_step_on_context(step, context) for step in steps]
            async for event in as_generated(generators):
                yield event

        else:
            for step in steps:
                async for event in run_step_on_context(step, context):
                    yield event
                    if isinstance(event, Result) and not event.success:
                        return


async def run_jobs(
    jobs: Sequence[Job], contexts: Sequence[Context], config: Config
) -> AsyncIterator[Event]:
    if all(job.once for job in jobs):
        LOG.debug("all jobs have once=true, trimming contexts")
        contexts = contexts[0:1]

    async for event in prepare_contexts(contexts, config):
        yield event

    generators: List[AsyncIterable[Event]] = []

    success = True
    for job in jobs:
        with timed("run job", job=job):
            if job.once:
                generators = [run_job_on_context(job, contexts[0], config)]
            else:
                generators = [
                    run_job_on_context(job, context, config) for context in contexts
                ]

            async for event in as_generated(generators):
                yield event
                if isinstance(event, Result):
                    if not event.success:
                        success = False

            if not success:
                return


@timed("run")
def run(
    options: Options,
    render: Renderer = print,
) -> List[Result]:
    results: List[Result] = []

    config = options.config
    contexts = resolve_contexts(config, options)

    job_names = options.jobs
    if not job_names:
        if config.default:
            job_names.extend(config.default)
        else:
            LOG.warning("no jobs to run")
            return []

    jobs = resolve_jobs(job_names, config)

    async def runner() -> None:
        async for event in run_jobs(jobs, contexts, config):
            render(event)

            if isinstance(event, Result):
                results.append(event)

    asyncio.run(runner())
    return results


class ThxWatchdogHandler(FileSystemEventHandler):
    def __init__(
        self,
        config: Config,
        contexts: Sequence[Context],
        jobs: Sequence[Job],
        render: Renderer,
    ):
        self.__config = config
        self.__contexts = contexts
        self.__jobs = jobs
        self.__render = render
        self.__last_event = monotonic_ns()

    def on_any_event(self, event: FileSystemEvent) -> None:
        if "__pycache__" in event.src_path:
            return
        LOG.debug("detected filesystem event %s", event)
        self.__last_event = monotonic_ns()

    async def runner_one(self) -> None:
        results: List[Result] = []

        async for event in run_jobs(self.__jobs, self.__contexts, self.__config):
            self.__render(event)

            if isinstance(event, Result):
                results.append(event)

        return results

    async def runner(self) -> None:
        task: Optional[asyncio.Task] = None
        last_run = 0

        while True:
            if self.__last_event > last_run + 50_000_000:
                last_run = monotonic_ns()

                if task and not task.done():
                    LOG.debug("canceling %s", task)
                    task.cancel()
                    try:
                        await task
                    except Exception as e:
                        LOG.debug(e)

                LOG.debug("starting new run")
                self.__render(Abort())
                task = asyncio.create_task(self.runner_one())

            if task and task.done():
                try:
                    results = await task
                    if any(result.error for result in results):
                        self.__render(Fail())
                except Exception as e:
                    LOG.exception("exception in task")
                finally:
                    task = None

            await asyncio.sleep(0.05)


def watch(
    options: Options,
    render: Renderer = print,
) -> List[Result]:
    results: List[Result] = []

    config = options.config
    if not config.watch_paths:
        LOG.error("No configured paths to watch (tool.thx.watch_paths)")
        return []

    contexts = resolve_contexts(config, options)

    job_names = options.jobs
    if not job_names:
        if config.default:
            job_names.extend(config.default)
        else:
            LOG.warning("no jobs to run")
            return []

    jobs = resolve_jobs(job_names, config)

    handler = ThxWatchdogHandler(
        config=config, contexts=contexts, jobs=jobs, render=render
    )
    observer = Observer()
    for path in config.watch_paths:
        observer.schedule(handler, config.root / path, recursive=True)

    try:
        observer.start()
        asyncio.run(handler.runner())
    finally:
        observer.stop()
        observer.join()

    return results
