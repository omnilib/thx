# Copyright 2021 John Reese
# Licensed under the MIT License

from typing import List, Tuple
from unittest import TestCase

from .. import utils
from ..types import Version

from .context import TEST_VERSIONS


class UtilTest(TestCase):
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
