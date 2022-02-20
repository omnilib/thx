# Copyright 2022 John Reese
# Licensed under the MIT License

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from .. import types

FAKE_VERSION = types.Version("3.4")
FAKE_BINARY = Path("/opt/fake/python3.4")


class TypesTest(TestCase):
    def setUp(self) -> None:
        self._td = TemporaryDirectory()
        self._tdp = Path(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def fake_context(self) -> types.Context:
        return types.Context(FAKE_VERSION, self._tdp / "bin" / "python", self._tdp)

    def test_event_base(self) -> None:
        ctx = self.fake_context()
        event = types.Event(ctx)
        self.assertEqual(ctx, event.context)
        self.assertEqual("3.4> Event", str(event))

    def test_event_venv_create(self) -> None:
        ctx = self.fake_context()
        event = types.VenvCreate(ctx, message="creating")
        self.assertEqual(ctx, event.context)
        self.assertEqual("3.4> creating", str(event))

    def test_event_job_start(self) -> None:
        ctx = self.fake_context()
        job = types.Job("foo", ("/bin/echo", "bar"))
        step = types.Step(("/bin/echo", "bar"), job, ctx)

        event = types.Start(ctx, step)
        self.assertEqual("3.4 foo> /bin/echo bar", str(event))

    def test_event_job_result(self) -> None:
        ctx = self.fake_context()
        job = types.Job("foo", ("/bin/echo", "bar"))
        step = types.Step(("/bin/echo", "bar"), job, ctx)

        with self.subTest("success"):
            event = types.Result(
                context=ctx, step=step, exit_code=0, stdout="", stderr=""
            )
            self.assertEqual("3.4 foo> /bin/echo bar OK", str(event))

        with self.subTest("failure"):
            event = types.Result(
                context=ctx, step=step, exit_code=37, stdout="", stderr=""
            )
            self.assertEqual("3.4 foo> /bin/echo bar FAIL", str(event))
