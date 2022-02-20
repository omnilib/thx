# Copyright 2021 John Reese
# Licensed under the MIT License

import time
from pathlib import Path
from typing import Any, List, Tuple
from unittest import TestCase

from .. import utils
from ..types import Context, Job, Step, Version

from .context import TEST_VERSIONS


class UtilTest(TestCase):
    def setUp(self) -> None:
        utils.TIMINGS.clear()

    def test_timed_decorator(self) -> None:
        @utils.timed("test message")
        def foo(value: int, *args: Any, **kwargs: Any) -> int:
            time.sleep(0.02)  # Windows only has precision >15ms
            return value * 2

        foo(9)
        timings = utils.get_timings()

        self.assertEqual(1, len(timings))
        timing = timings[0]
        self.assertIsInstance(timing, utils.timed)
        self.assertEqual("test message", timing.message)
        self.assertGreater(timing.start, 0)
        self.assertGreater(timing.end, 0)
        self.assertGreater(timing.duration, 0)
        self.assertIsNone(timing.context)
        self.assertIsNone(timing.job)
        self.assertIsNone(timing.step)
        self.assertRegex(str(timing), r"test message -> \s+ \d+ ms")

        context = Context(Version("3.8"), Path(), Path())
        job = Job("foo", ())
        step = Step((), job, context)

        foo(5, context, "fake", job=job, bar=step, step="herring")
        timing = utils.get_timings()[0]
        self.assertEqual(context, timing.context)
        self.assertEqual(job, timing.job)
        self.assertEqual(step, timing.step)
        self.assertRegex(str(timing), r"test message 3.8 foo \(\) -> \s+ \d+ ms")

    def test_version_match(self) -> None:
        test_data: Tuple[Tuple[str, List[Version]], ...] = (
            ("3.8", [Version("3.8"), Version("3.8.10")]),
            ("3.8.10", [Version("3.8.10")]),
            ("3.8.11", []),
            ("3.9", [Version("3.9"), Version("3.9.0b1")]),
            ("3.9.0", [Version("3.9.0b1")]),
            ("3.9.0b1", [Version("3.9.0b1")]),
            ("3.9.0b2", []),
            (
                "3",
                [
                    Version("3.5"),
                    Version("3.6.5"),
                    Version("3.8"),
                    Version("3.8.10"),
                    Version("3.9"),
                    Version("3.9.0b1"),
                    Version("3.10.42"),
                    Version("3.11.0a4"),
                ],
            ),
            ("4", [Version("4.0"), Version("4.128.1337")]),
            ("4.0", [Version("4.0")]),
            ("4.0.4", []),
        )
        for target, expected in test_data:
            with self.subTest(target):
                self.assertListEqual(
                    expected, utils.version_match(TEST_VERSIONS, Version(target))
                )
