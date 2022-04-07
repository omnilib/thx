# Copyright 2021 John Reese
# Licensed under the MIT License

from pathlib import Path
from unittest import TestCase
from unittest.mock import call, Mock, patch

from .. import runner
from ..types import Config, Context, Job, Result, Version
from .helper import async_test


class RunnerTest(TestCase):
    @patch("thx.runner.shutil.which")
    def test_which(self, which_mock: Mock) -> None:
        context = Context(Version("3.10"), Path(), Path("/fake/venv"))
        with self.subTest("found"):
            which_mock.side_effect = lambda b, path: f"/usr/bin/{b}"
            self.assertEqual("/usr/bin/frobfrob", runner.which("frobfrob", context))
            which_mock.assert_has_calls([call("frobfrob", path="/fake/venv/bin")])

        with self.subTest("not in venv"):
            which_mock.side_effect = [None, "/usr/bin/scoop"]
            self.assertEqual("/usr/bin/scoop", runner.which("scoop", context))
            which_mock.assert_has_calls(
                [
                    call("scoop", path="/fake/venv/bin"),
                    call("scoop"),
                ]
            )

        with self.subTest("not found"):
            which_mock.side_effect = None
            which_mock.return_value = None
            self.assertEqual("frobfrob", runner.which("frobfrob", context))
            which_mock.assert_has_calls(
                [
                    call("frobfrob", path="/fake/venv/bin"),
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
