# Copyright 2021 John Reese
# Licensed under the MIT License

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Iterator, Optional
from unittest import TestCase

from ..config import load_config
from ..types import Config, ConfigError, Job


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

    def test_no_pyproject(self) -> None:
        with fake_pyproject(None) as td:
            expected = Config(root=Path(td).resolve())
            result = load_config(td)
            self.assertEqual(expected.root, result.root)
            self.assertEqual(expected, result)

    def test_empty_pyproject(self) -> None:
        with fake_pyproject("") as td:
            expected = Config(root=Path(td).resolve())
            result = load_config(td)
            self.assertEqual(expected.root, result.root)
            self.assertEqual(expected, result)

    def test_no_config(self) -> None:
        with fake_pyproject(
            """
            [tool.black]
            line_length = 37
            """
        ) as td:
            expected = Config(root=Path(td).resolve())
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_empty_config(self) -> None:
        with fake_pyproject(
            """
            [tool.thx]
            # hello

            [tool.black]
            line_length = 37
            """
        ) as td:
            expected = Config(root=Path(td).resolve())
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_tiny_config(self) -> None:
        with fake_pyproject(
            """
            [tool.thx]
            jobs = {hello = "echo hello"}

            [tool.black]
            line_length = 37
            """
        ) as td:
            expected = Config(
                root=Path(td).resolve(),
                jobs={"hello": Job(name="hello", run=["echo hello"])},
            )
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_simple_config(self) -> None:
        with fake_pyproject(
            """
            [tool.thx]
            default = "hello"
            module = "foobar"

            [tool.thx.jobs]
            hello = ["echo hello"]
            lint = ["flake8 {module}", "black --check {module}"]
            """
        ) as td:
            expected = Config(
                root=Path(td).resolve(),
                default=["hello"],
                jobs={
                    "hello": Job(name="hello", run=["echo hello"]),
                    "lint": Job(
                        name="lint", run=["flake8 {module}", "black --check {module}"]
                    ),
                },
                values={"module": "foobar"},
            )
            result = load_config(td)
            self.assertEqual(expected, result)

    def test_complex_config(self) -> None:
        with fake_pyproject(
            """
            [tool.thx]
            default = ["test", "lint"]
            module = "foobar"

            [tool.thx.jobs]
            format = ["black {module}"]
            lint = ["flake8 {module}", "black --check {module}"]
            test = [
                "python -m unittest {module}",
                "mypy {module}",
            ]

            [tool.thx.jobs.publish]
            requires = ["test", "lint"]
            run = ["flit publish"]
            """
        ) as td:
            expected = Config(
                root=Path(td).resolve(),
                default=["test", "lint"],
                jobs={
                    "format": Job(name="format", run=["black {module}"]),
                    "lint": Job(
                        name="lint", run=["flake8 {module}", "black --check {module}"]
                    ),
                    "test": Job(
                        name="test",
                        run=["python -m unittest {module}", "mypy {module}"],
                    ),
                    "publish": Job(
                        name="publish", run=["flit publish"], requires=["test", "lint"]
                    ),
                },
                values={"module": "foobar"},
            )
            result = load_config(td)
            self.assertDictEqual(expected.jobs, result.jobs)
            self.assertDictEqual(expected.values, result.values)
            self.assertEqual(expected, result)

    def test_bad_value_jobs(self) -> None:
        with self.assertRaisesRegex(ConfigError, "tool.thx.jobs"):
            with fake_pyproject(
                """
                [tool.thx]
                jobs = ["foo", "bar"]
                """
            ) as td:
                load_config(td)

    def test_bad_value_default(self) -> None:
        with self.assertRaisesRegex(ConfigError, "tool.thx.default"):
            with fake_pyproject(
                """
                [tool.thx]
                default = true
                """
            ) as td:
                load_config(td)

    def test_bad_value_requires(self) -> None:
        with self.assertRaisesRegex(ConfigError, "tool.thx.jobs.foo.requires"):
            with fake_pyproject(
                """
                [tool.thx.jobs.foo]
                requires = 1337
                """
            ) as td:
                load_config(td)

    def test_bad_value_run(self) -> None:
        with self.assertRaisesRegex(ConfigError, "tool.thx.jobs.foo.run"):
            with fake_pyproject(
                """
                [tool.thx.jobs.foo]
                run = [123, 234]
                """
            ) as td:
                load_config(td)

    def test_undefined_default(self) -> None:
        with self.assertRaisesRegex(ConfigError, "default: undefined job 'foo'"):
            with fake_pyproject(
                """
                [tool.thx]
                default = "foo"
                """
            ) as td:
                load_config(td)

    def test_undefined_requires(self) -> None:
        with self.assertRaisesRegex(ConfigError, "foo.requires: undefined job 'bar'"):
            with fake_pyproject(
                """
                [tool.thx.jobs]
                foo = {run="echo hello", requires="bar"}
                """
            ) as td:
                config = load_config(td)
                print(config)
