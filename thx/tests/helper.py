# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
from functools import wraps
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def async_test(fn: Callable[..., T]) -> Callable[..., T]:
    # TODO: find some way of avoiding madness on Python 3.6 and 3.7 around
    # subprocesses, child handlers, and requiring the main/default event loop
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(fn(*args, **kwargs))  # type: ignore

    return wrapper
