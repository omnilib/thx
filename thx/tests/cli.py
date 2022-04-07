# Copyright 2021 John Reese
# Licensed under the MIT License

from pathlib import Path
from typing import Dict
from unittest import TestCase
from unittest.mock import ANY, call, MagicMock, patch

from rich.text import Text

from ..cli import RichRenderer

from ..types import (
    Context,
    Event,
    Fail,
    Job,
    Reset,
    Result,
    Start,
    Step,
    VenvCreate,
    VenvReady,
    Version,
)

FAKE_38 = Context(Version("3.8.6"), Path(""), Path(""))
FAKE_39 = Context(Version("3.9.1"), Path(""), Path(""))


@patch("thx.cli.Live", new_callable=MagicMock)
class CliTest(TestCase):
    def test_render_context(self, live_mock: MagicMock) -> None:
        render = RichRenderer()
        with render:
            render(Event())
            render(Fail())

        live_mock.return_value.__enter__.assert_called_once()
        live_mock.return_value.__exit__.assert_called_once()

    def test_render_reset(self, live_mock: MagicMock) -> None:
        render = RichRenderer()
        render(Reset())

        live_mock.return_value.update.assert_called_with(Text(""), refresh=True)

    def test_render_venv(self, live_mock: MagicMock) -> None:
        render = RichRenderer()

        events = [
            VenvCreate(FAKE_38, "running fake command"),
            VenvCreate(FAKE_39, "a different message"),
            VenvReady(FAKE_39),
            VenvReady(FAKE_38),
        ]

        for event in events:
            ctx = event.context
            live_mock.return_value.reset_mock()
            render(event)

            self.assertIn(ctx, render.venvs)
            self.assertEqual(event, render.venvs[ctx])
            live_mock.return_value.update.assert_called_once()

    def test_render_job(self, live_mock: MagicMock) -> None:
        render = RichRenderer()
        event: Event

        job = Job("foo", ("/bin/true", "/bin/false"))
        steps = [Step((cmd,), job, FAKE_39) for cmd in job.run]

        expected: Dict[Job, Dict[Context, Dict[Step, Event]]] = {job: {FAKE_39: {}}}
        for step, code in zip(steps, (0, 1)):
            with self.subTest(step.cmd):
                live_mock.return_value.reset_mock()

                event = Start(step.context, step)
                render(event)
                expected[job][FAKE_39][step] = event
                self.assertDictEqual(expected, render.latest)

                event = Result(code, "", "", step.context, step)
                render(event)
                expected[job][FAKE_39][step] = event
                self.assertDictEqual(expected, render.latest)

                live_mock.return_value.update.assert_has_calls(
                    [
                        call(ANY, refresh=True),
                        call(ANY, refresh=True),
                    ]
                )
