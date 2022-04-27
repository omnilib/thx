# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
import logging
import signal
from pathlib import Path
from time import monotonic_ns
from typing import Any, AsyncGenerator, AsyncIterable, AsyncIterator, List, Sequence

from aioitertools.asyncio import as_generated
from trailrunner.core import gitignore, pathspec
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from thx.config import reload_config

from .context import prepare_contexts, resolve_contexts

from .runner import prepare_job
from .types import (
    Config,
    Context,
    Event,
    Fail,
    Job,
    Options,
    Renderer,
    Reset,
    Result,
    Start,
    Step,
    VenvError,
)
from .utils import timed

DEBOUNCE = 100_000_000  # delay in ns to wait for filesystem to settle down
LOG = logging.getLogger(__name__)

logging.getLogger("fsevents").setLevel(logging.WARNING)


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
) -> AsyncGenerator[Event, None]:
    if all(job.once for job in jobs):
        LOG.debug("all jobs have once=true, trimming contexts")
        contexts = contexts[0:1]

    setup_error = False
    async for event in prepare_contexts(contexts, config):
        if isinstance(event, VenvError):
            setup_error = True
        yield event
    if setup_error:
        return

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
) -> int:
    results: List[Result] = []

    config = options.config
    contexts = resolve_contexts(config, options)

    job_names = options.jobs
    if not job_names:
        if config.default:
            job_names.extend(config.default)
        else:
            LOG.warning("no jobs to run")
            return 1

    jobs = resolve_jobs(job_names, config)

    async def runner() -> None:
        async for event in run_jobs(jobs, contexts, config):
            render(event)

            if isinstance(event, Result):
                results.append(event)

    asyncio.run(runner())

    if any(result.error for result in results):
        render(Fail())
        return 1

    return 0


class ThxWatchdogHandler(FileSystemEventHandler):  # type: ignore
    EXCLUDES = [
        "__pycache__",
        ".git",
        ".hg",
        ".mypy_cache",
        ".coverage*",
        "*.swp",
    ]

    def __init__(
        self,
        options: Options,
        observer: Observer,
        render: Renderer,
    ):
        self.__options = options
        self.__observer = observer
        self.__render = render

        self.__root = options.config.root
        self.__last_event = monotonic_ns()
        self.__resolve = True
        self.__running = True
        self.__excludes = gitignore(self.__root) + pathspec(self.EXCLUDES)

    def on_any_event(self, event: FileSystemEvent) -> None:
        source_path = Path(event.src_path).resolve()

        if source_path.is_dir():
            return

        try:
            rel_path = source_path.relative_to(self.__root)
        except ValueError:
            LOG.warning("ignoring event for outside path %s", source_path)
            return

        if self.__excludes.match_file(rel_path):
            return

        LOG.debug("detected filesystem event %s", source_path)
        if source_path == self.__root / "pyproject.toml":
            self.reload()
        self.__last_event = monotonic_ns()

    def reload(self) -> None:
        old_config = self.__options.config
        new_config = reload_config(old_config)
        if new_config != old_config:
            LOG.info("Config change detected")
            self.__options.config = reload_config(self.__options.config)
            self.__resolve = True
            self.schedule()

    def schedule(self) -> None:
        config = self.__options.config
        observer = self.__observer
        observer.unschedule_all()

        if not config.watch_paths:
            watch_paths = {config.root}
        else:
            watch_paths = {config.root / "pyproject.toml"} | config.watch_paths

        for path in watch_paths:
            observer.schedule(self, config.root / path, recursive=True)

    def signal(self, *args: Any) -> None:
        LOG.warning("ctrl-c")
        self.__running = False

    def render(self, event: Event) -> None:
        if self.__running:
            self.__render(event)

    async def runner(self) -> int:
        exit_code = 0
        results: List[Result] = []
        contexts: Sequence[Context]
        jobs: Sequence[Job]

        while self.__running:
            start = monotonic_ns()

            options = self.__options
            config = options.config

            if self.__resolve:
                self.__resolve = False
                contexts = resolve_contexts(config, options)
                job_names = options.jobs
                if not job_names:
                    if config.default:
                        job_names = list(config.default)
                    else:
                        LOG.warning("no jobs to run")
                        return 1

                jobs = resolve_jobs(job_names, config)

            exit_code = 0
            results.clear()
            self.render(Reset())
            gen = run_jobs(jobs, contexts, config)
            try:
                while self.__running:
                    event = await gen.asend(None)
                    self.render(event)

                    if isinstance(event, Result):
                        results.append(event)

                    now = monotonic_ns()
                    if self.__last_event > start and now > self.__last_event + DEBOUNCE:
                        await gen.aclose()

            except StopAsyncIteration:
                if any(result.error for result in results):
                    self.render(Fail())
                    exit_code = 1

            while self.__running and start > self.__last_event:
                await asyncio.sleep(0.05)

        return exit_code


def watch(
    options: Options,
    render: Renderer = print,
) -> int:
    exit_code: int = 0

    observer = Observer()
    handler = ThxWatchdogHandler(options, observer, render)
    handler.schedule()

    try:
        observer.start()
        signal.signal(signal.SIGINT, handler.signal)
        exit_code = asyncio.run(handler.runner())
    finally:
        observer.stop()
        observer.join()

    return exit_code
