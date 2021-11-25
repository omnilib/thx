# Copyright 2021 John Reese
# Licensed under the MIT License

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Optional, Iterator
from unittest import TestCase

from ..config import Config, Command, ConfigError, load_config


@contextmanager
def fake_pyproject(content: Optional[str]) -> Iterator[Path]:
    with TemporaryDirectory() as td:
        tdp = Path(td)

        if content is not None:
            content = dedent(content)
            pyproject = tdp / "pyproject.toml"
            pyproject.write_text(content)

        yield tdp


class ConfigTest(TestCase):
    maxDiff = None

    def test_no_pyproject(self):
        with fake_pyproject(None) as td:
            expected = Config()
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_empty_pyproject(self):
        with fake_pyproject("") as td:
            expected = Config()
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_no_config(self):
        with fake_pyproject(
            """
            [tool.black]
            line_length = 37
            """
        ) as td:
            expected = Config()
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_empty_config(self):
        with fake_pyproject(
            """
            [tool.thx]
            # hello

            [tool.black]
            line_length = 37
            """
        ) as td:
            expected = Config()
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_tiny_config(self):
        with fake_pyproject(
            """
            [tool.thx]
            commands = {hello = "echo hello"}

            [tool.black]
            line_length = 37
            """
        ) as td:
            expected = Config(
                commands={"hello": Command(name="hello", run=["echo hello"])}
            )
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_simple_config(self):
        with fake_pyproject(
            """
            [tool.thx]
            default = "hello"
            module = "foobar"

            [tool.thx.commands]
            hello = ["echo hello"]
            lint = ["flake8 {module}", "black --check {module}"]
            """
        ) as td:
            expected = Config(
                default=["hello"],
                commands={
                    "hello": Command(name="hello", run=["echo hello"]),
                    "lint": Command(
                        name="lint", run=["flake8 {module}", "black --check {module}"]
                    ),
                },
                values={"module": "foobar"},
            )
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_complex_config(self):
        with fake_pyproject(
            """
            [tool.thx]
            default = ["test", "lint"]
            module = "foobar"

            [tool.thx.commands]
            format = ["black {module}"]
            lint = ["flake8 {module}", "black --check {module}"]
            test = [
                "python -m unittest {module}",
                "mypy {module}",
            ]

            [tool.thx.commands.publish]
            requires = ["test", "lint"]
            run = ["flit publish"]
            """
        ) as td:
            expected = Config(
                default=["test", "lint"],
                commands={
                    "format": Command(name="format", run=["black {module}"]),
                    "lint": Command(
                        name="lint", run=["flake8 {module}", "black --check {module}"]
                    ),
                    "test": Command(
                        name="test",
                        run=["python -m unittest {module}", "mypy {module}"],
                    ),
                    "publish": Command(
                        name="publish", run=["flit publish"], requires=["test", "lint"]
                    ),
                },
                values={"module": "foobar"},
            )
            result = load_config(td)
            self.assertDictEqual(expected.commands, result.commands)
            self.assertDictEqual(expected.values, result.values)
            self.assertEqual(expected, result)

    def test_bad_value_commands(self):
        with self.assertRaisesRegex(ConfigError, "tool.thx.commands"):
            with fake_pyproject(
                """
                [tool.thx]
                commands = ["foo", "bar"]
                """
            ) as td:
                load_config(td)

    def test_bad_value_default(self):
        with self.assertRaisesRegex(ConfigError, "tool.thx.default"):
            with fake_pyproject(
                """
                [tool.thx]
                default = true
                """
            ) as td:
                load_config(td)

    def test_bad_value_requires(self):
        with self.assertRaisesRegex(ConfigError, "tool.thx.commands.foo.requires"):
            with fake_pyproject(
                """
                [tool.thx.commands.foo]
                requires = 1337
                """
            ) as td:
                load_config(td)

    def test_bad_value_run(self):
        with self.assertRaisesRegex(ConfigError, "tool.thx.commands.foo.run"):
            with fake_pyproject(
                """
                [tool.thx.commands.foo]
                run = [123, 234]
                """
            ) as td:
                load_config(td)

    def test_undefined_default(self):
        with self.assertRaisesRegex(ConfigError, "default: undefined command 'foo'"):
            with fake_pyproject(
                """
                [tool.thx]
                default = "foo"
                """
            ) as td:
                load_config(td)

    def test_undefined_requires(self):
        with self.assertRaisesRegex(
            ConfigError, "foo.requires: undefined command 'bar'"
        ):
            with fake_pyproject(
                """
                [tool.thx.commands]
                foo = {run="echo hello", requires="bar"}
                """
            ) as td:
                config = load_config(td)
                print(config)
