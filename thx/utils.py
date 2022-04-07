# Copyright 2021 John Reese
# Licensed under the MIT License

import logging
from asyncio import iscoroutinefunction
from dataclasses import dataclass, field, replace
from functools import wraps
from itertools import zip_longest
from time import monotonic_ns
from typing import Any, Callable, List, Optional, TypeVar

from typing_extensions import ParamSpec

from .types import Context, Job, Step, Version

P = ParamSpec("P")
R = TypeVar("R")


LOG = logging.getLogger(__name__)
TIMINGS: List["timed"] = []


@dataclass(order=True)
class timed:
    start: int = field(default=0, init=False)
    end: int = field(default=0, init=False)
    duration: int = field(default=-1, init=False)

    message: str = field()
    context: Optional[Context] = field(default=None, compare=False)
    job: Optional[Job] = field(default=None, compare=False)
    step: Optional[Step] = field(default=None, compare=False)

    def __str__(self) -> str:
        message = self.message
        if self.context:
            message += f" {self.context.python_version}"
        if self.job:
            message += f" {self.job.name}"
        if self.step:
            message += f" {self.step.cmd}"
        message += " -> "
        if self.duration >= 0:
            return f"{message:<40} {self.duration//1000000:>7} ms"
        elif self.start:
            return f"{message} (started)"
        else:
            return f"{message} (not started)"

    def __call__(self, fn: Callable[P, R]) -> Callable[P, R]:
        if iscoroutinefunction(fn):

            @wraps(fn)
            async def wrapped_async(*args: Any, **kwargs: Any) -> R:
                timer = replace(self)
                combined: List[Any] = list(args) + list(kwargs.values())

                for arg in combined:
                    if isinstance(arg, Context) and timer.context is None:
                        timer.context = arg
                    elif isinstance(arg, Job) and timer.job is None:
                        timer.job = arg
                    elif isinstance(arg, Step) and timer.step is None:
                        timer.step = arg

                with timer:
                    return await fn(*args, **kwargs)  # type: ignore

            return wrapped_async  # type: ignore

        else:

            @wraps(fn)
            def wrapped(*args: Any, **kwargs: Any) -> R:
                timer = replace(self)
                combined: List[Any] = list(args) + list(kwargs.values())

                for arg in combined:
                    if isinstance(arg, Context) and timer.context is None:
                        timer.context = arg
                    elif isinstance(arg, Job) and timer.job is None:
                        timer.job = arg
                    elif isinstance(arg, Step) and timer.step is None:
                        timer.step = arg

                with timer:
                    return fn(*args, **kwargs)

            return wrapped

    def __enter__(self) -> "timed":
        self.start = monotonic_ns()
        return self

    def __exit__(self, *args: Any) -> None:
        now = monotonic_ns()
        self.end = now
        self.duration = now - self.start

        TIMINGS.append(self)


def get_timings() -> List[timed]:
    global TIMINGS

    result = list(sorted(TIMINGS))
    TIMINGS.clear()
    return result


def version_match(versions: List[Version], target: Version) -> List[Version]:
    matches: List[Version] = []
    for version in versions:
        if all(
            v == t or t is None for v, t in zip_longest(version.release, target.release)
        ):
            if target.pre and target.pre != version.pre:
                continue
            if target.post and target.post != version.post:
                continue
            if target.dev and target.dev != version.dev:
                continue

            matches.append(version)

    return matches
