# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
import logging
from collections import defaultdict
from typing import AsyncIterable, AsyncIterator, Dict, List, Sequence

from aioitertools.asyncio import as_generated

from .context import prepare_contexts, resolve_contexts

from .runner import prepare_job
from .types import (
    Config,
    Context,
    Event,
    Job,
    JobEvent,
    Options,
    Result,
    Start,
    Step,
    VenvCreate,
    VenvReady,
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


@timed("run")
def run_rich(options: Options) -> List[Result]:
    from rich.console import Group
    from rich.live import Live
    from rich.text import Text
    from rich.tree import Tree

    config = options.config
    contexts = resolve_contexts(config, options.python)

    job_names = options.jobs
    if not job_names:
        if config.default:
            job_names.extend(config.default)
        else:
            LOG.warning("no jobs to run")
            return []

    LOG.info("running jobs %s", job_names)
    jobs = resolve_jobs(job_names, config)
    results: List[Result] = []

    async def runner() -> None:
        venvs: Dict[Context, Event] = {}
        latest: Dict[Job, Dict[Context, Dict[Step, Event]]] = defaultdict(
            lambda: defaultdict(dict)
        )

        with Live(auto_refresh=False) as live:
            async for event in run_jobs(jobs, contexts, config):
                context = event.context

                if isinstance(event, (VenvCreate, VenvReady)):
                    venvs[context] = event
                elif isinstance(event, JobEvent):
                    step = event.step
                    job = step.job
                    latest[job][context][step] = event

                trees: List[Tree] = []

                if venvs and not all(isinstance(v, VenvReady) for v in venvs.values()):
                    tree = Tree("Preparing virtualenvs...")
                    for context, event in venvs.items():
                        if isinstance(event, VenvReady):
                            text = Text(
                                f"{context.python_version}> done", style="green"
                            )
                        else:
                            text = Text(f"{event}")
                        tree.add(text)
                    trees.append(tree)

                for job in latest:
                    tree = Tree(job.name)
                    job_success = True

                    for context in latest[job]:
                        context_tree = Tree(str(context.python_version))

                        context_success = True
                        for step, event in latest[job][context].items():
                            text = Text(str(event))
                            if isinstance(event, Result):
                                text.stylize("green" if event.success else "red")
                                if event.error:
                                    text.append("\n", style="")
                                    text.append(event.stdout, style="")
                                    text.append("\n", style="")
                                    text.append(event.stderr, style="")
                                    context_success = False
                                results.append(event)
                            else:
                                context_success = False
                            context_tree.add(text)

                        if context_success:
                            tree.add(
                                Text(f"{context.python_version} OK", style="green")
                            )
                        else:
                            job_success = False
                            tree.add(context_tree)

                    if job_success:
                        trees.append(Tree(f"{job.name} OK", style="green"))
                    else:
                        trees.append(tree)

                live.update(Group(*trees), refresh=True)

    asyncio.run(runner())
    return results
