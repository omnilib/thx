# Copyright 2022 Amethyst Reese
# Licensed under the MIT License

import platform
import sys
from asyncio.subprocess import PIPE
from pathlib import Path
from unittest import skipIf, TestCase
from unittest.mock import ANY, call, Mock, patch

from .. import runner
from ..types import CommandError, CommandResult, Config, Context, Job, Result, Version
from .helper import async_test


class RunnerTest(TestCase):
    @patch("thx.runner.shutil.which")
    def test_which(self, which_mock: Mock) -> None:
        context = Context(Version("3.10"), Path(), Path("/fake/venv"))
        fake_venv_bin = (
            "/fake/venv/Scripts" if platform.system() == "Windows" else "/fake/venv/bin"
        )
        with self.subTest("found"):
            which_mock.side_effect = lambda b, path: f"/usr/bin/{b}"
            self.assertEqual("/usr/bin/frobfrob", runner.which("frobfrob", context))
            which_mock.assert_has_calls([call("frobfrob", path=fake_venv_bin)])

        with self.subTest("not in venv"):
            which_mock.side_effect = [None, "/usr/bin/scoop"]
            self.assertEqual("/usr/bin/scoop", runner.which("scoop", context))
            which_mock.assert_has_calls(
                [
                    call("scoop", path=fake_venv_bin),
                    call("scoop"),
                ]
            )

        with self.subTest("not found"):
            which_mock.side_effect = None
            which_mock.return_value = None
            self.assertEqual("frobfrob", runner.which("frobfrob", context))
            which_mock.assert_has_calls(
                [
                    call("frobfrob", path=fake_venv_bin),
                    call("frobfrob"),
                ]
            )

    @patch("thx.runner.which")
    def test_render_command(self, which_mock: Mock) -> None:
        which_mock.return_value = "/opt/bin/frobfrob"
        config = Config(values={"module": "alpha"})
        context = Context(Version("3.8"), Path(), Path())
        result = runner.render_command("frobfrob check {module}.tests", context, config)
        self.assertEqual(("/opt/bin/frobfrob", "check", "alpha.tests"), result)

    @patch("thx.runner.shutil.which", return_value=None)
    def test_prepare_job(self, which_mock: Mock) -> None:
        config = Config(values={"module": "beta"})
        context = Context(Version("3.9"), Path(), Path())
        run = [
            "echo 'hello world'",
            "flake8 {module}",
            "python -m {module}.tests",
        ]
        job = Job(name="foo", run=run)

        expected = [
            runner.JobStep(cmd=("echo", "hello world"), job=job, context=context),
            runner.JobStep(cmd=("flake8", "beta"), job=job, context=context),
            runner.JobStep(
                cmd=("python", "-m", "beta.tests"),
                job=job,
                context=context,
            ),
        ]
        result = list(runner.prepare_job(job, context, config))
        self.assertListEqual(expected, result)

    @skipIf(sys.version_info < (3, 8), "no asyncmock on 3.7")
    @async_test
    async def test_run_command(self) -> None:
        from unittest.mock import AsyncMock

        exec_mock = AsyncMock()
        exec_mock.return_value.returncode = 0
        exec_mock.return_value.communicate.return_value = b"nothing", b"error!"

        with patch("thx.runner.asyncio.create_subprocess_exec", exec_mock):
            result = await runner.run_command(("/fake/binary", "something"))
            expected = CommandResult(0, "nothing", "error!")
            self.assertEqual(expected, result)

            ctx = Context(Version("3.8"), Path("/fake/python"), Path("/fake"))
            result = await runner.run_command(("/fake/binary", "something"), ctx)
            expected = CommandResult(0, "nothing", "error!")
            self.assertEqual(expected, result)
            exec_mock.assert_called_with(
                "/fake/binary", "something", stdout=PIPE, stderr=PIPE, env=ANY
            )
            self.assertIn(
                str(runner.venv_bin_path(ctx)),
                exec_mock.call_args.kwargs["env"]["PATH"],
            )

    @skipIf(sys.version_info < (3, 8), "no asyncmock on 3.7")
    @async_test
    async def test_check_command(self) -> None:
        from unittest.mock import AsyncMock

        exec_mock = AsyncMock()
        exec_mock.return_value.returncode = 0
        exec_mock.return_value.communicate.return_value = b"nothing", b"error!"

        with patch("thx.runner.asyncio.create_subprocess_exec", exec_mock):
            result = await runner.check_command(("/fake/binary", "something"))
            expected = CommandResult(0, "nothing", "error!")
            self.assertEqual(expected, result)

            exec_mock.return_value.returncode = 1

            with self.assertRaises(CommandError):
                await runner.check_command(("/fake/binary", "whatever"))

    @async_test
    async def test_job_echo(self) -> None:
        step = runner.JobStep(
            ["python", "-c", "print('hello world')"],
            Job("echo", ["python -c \"print('hello world')\""]),
            Context(Version("3.9"), Path(), Path()),
        )
        result = await step
        self.assertIsInstance(result, Result)
        self.assertEqual(step, result.step)
        self.assertEqual(0, result.exit_code)
        self.assertEqual("hello world", result.stdout.strip())
        self.assertEqual("", result.stderr)
        self.assertTrue(result.success)
        self.assertFalse(result.error)
