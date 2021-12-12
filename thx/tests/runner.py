# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
from functools import wraps
from typing import Any, Callable, TypeVar
from unittest import TestCase
from unittest.mock import Mock, patch

from .. import runner
from ..types import Config, Job, Result

T = TypeVar("T")


def async_test(fn: Callable[..., T]) -> Callable[..., T]:
    # TODO: find some way of avoiding madness on Python 3.6 and 3.7 around
    # subprocesses, child handlers, and requiring the main/default event loop
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(fn(*args, **kwargs))  # type: ignore

    return wrapper


class RunnerTest(TestCase):
    @patch("thx.runner.shutil.which")
    def test_which(self, which_mock: Mock) -> None:
        with self.subTest("found"):
            which_mock.side_effect = lambda b: f"/usr/bin/{b}"
            self.assertEqual("/usr/bin/frobfrob", runner.which("frobfrob", Config()))

        with self.subTest("not found"):
            which_mock.side_effect = None
            which_mock.return_value = None
            self.assertEqual("frobfrob", runner.which("frobfrob", Config()))

    @patch("thx.runner.which")
    def test_render_command(self, which_mock: Mock) -> None:
        which_mock.return_value = "/opt/bin/frobfrob"
        config = Config(values={"module": "alpha"})
        result = runner.render_command("frobfrob check {module}.tests", config)
        self.assertEqual(["/opt/bin/frobfrob", "check", "alpha.tests"], result)

    @patch("thx.runner.shutil.which", return_value=None)
    def test_prepare_command(self, which_mock: Mock) -> None:
        config = Config(values={"module": "beta"})
        run = [
            "echo 'hello world'",
            "flake8 {module}",
            "python -m {module}.tests",
        ]
        job = Job(name="foo", run=run)

        expected = [
            runner.Step(cmd=["echo", "hello world"], config=config),
            runner.Step(cmd=["flake8", "beta"], config=config),
            runner.Step(cmd=["python", "-m", "beta.tests"], config=config),
        ]
        result = list(runner.prepare_job(job, config))
        self.assertListEqual(expected, result)

    @async_test
    async def test_job_echo(self) -> None:
        job = runner.Step(
            ["echo", "hello world"],
            Config(),
        )
        result = await job
        self.assertIsInstance(result, Result)
        self.assertEqual(["echo", "hello world"], result.command)
        self.assertEqual(0, result.exit_code)
        self.assertEqual("hello world", result.stdout.strip())
        self.assertEqual("", result.stderr)
        self.assertTrue(result.success)
