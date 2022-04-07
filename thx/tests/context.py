# Copyright 2021 John Reese
# Licensed under the MIT License

import platform
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import AsyncIterator, List, Optional, Sequence, Tuple
from unittest import TestCase
from unittest.mock import call, Mock, patch

from thx.tests.helper import async_test

from .. import context
from ..types import (
    CommandResult,
    Config,
    Context,
    Event,
    Options,
    StrPath,
    VenvCreate,
    VenvReady,
    Version,
)

TEST_VERSIONS = [
    Version(v)
    for v in (
        "3.5",
        "3.6.5",
        "3.8",
        "3.8.10",
        "3.9",
        "3.9.0b1",
        "3.10.42",
        "3.11.0a4",
        "3.11.0.post1",
        "3.12.3dev4",
        "4.0",
        "4.128.1337",
    )
]


class ContextTest(TestCase):
    def setUp(self) -> None:
        context.PYTHON_VERSIONS.clear()

    def test_venv_path(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td)
            config = Config(root=tdp)

            for version in TEST_VERSIONS:
                with self.subTest(version):
                    expected = tdp / ".thx" / "venv" / str(version)
                    result = context.venv_path(config, version)
                    self.assertEqual(expected, result)

    @patch("thx.context.subprocess.run")
    def test_runtime_version(self, run_mock: Mock) -> None:
        binary = Path("/fake/bin/python3")

        with self.subTest("fresh"):
            run_mock.return_value = subprocess.CompletedProcess((), 0, "Python 3.9.3\n")

            expected = Version("3.9.3")
            result = context.runtime_version(binary)
            self.assertEqual(expected, result)

            run_mock.assert_called_once()

        with self.subTest("cached"):
            run_mock.reset_mock()

            result = context.runtime_version(binary)
            self.assertEqual(expected, result)

            run_mock.assert_not_called()

    @patch("thx.context.subprocess.run")
    @patch("thx.context.LOG")
    def test_runtime_version_timeout(self, log_mock: Mock, run_mock: Mock) -> None:
        fake_timeout = subprocess.TimeoutExpired((), 0.5, None)
        run_mock.side_effect = fake_timeout

        binary = Path("/fake/bin/python3")
        expected = None
        result = context.runtime_version(binary)
        self.assertEqual(expected, result)
        log_mock.warning.assert_called_with(
            "running `%s -V` failed: %s", binary, fake_timeout
        )

    @patch("thx.context.subprocess.run")
    @patch("thx.context.LOG")
    def test_runtime_version_weird(self, log_mock: Mock, run_mock: Mock) -> None:
        fake_output = "something went wrong\n"
        run_mock.return_value = subprocess.CompletedProcess((), 0, fake_output)

        binary = Path("/fake/bin/python3")
        expected = None
        result = context.runtime_version(binary)
        self.assertEqual(expected, result)
        log_mock.warning.assert_called_with(
            "running `%s -V` gave unexpected version string: %s", binary, fake_output
        )

    @patch("thx.context.shutil.which")
    @patch("thx.context.runtime_version")
    def test_find_runtime_no_venv_binary_found(
        self, runtime_mock: Mock, which_mock: Mock
    ) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            config = Config(root=tdp)

            which_mock.side_effect = (
                lambda b: f"/fake/bin/{b}" if "." not in b else None
            )

            for version in TEST_VERSIONS:
                runtime_mock.reset_mock()
                runtime_mock.side_effect = lambda b: version
                which_mock.reset_mock()

                with self.subTest(version):
                    venv = context.venv_path(config, version)

                    expected = Path(f"/fake/bin/python{version.major}")
                    result, _ = context.find_runtime(version, venv)
                    self.assertEqual(expected, result)

                    which_mock.assert_has_calls(
                        [
                            call(f"python{version.major}.{version.minor}"),
                            call(f"python{version.major}"),
                        ]
                    )
                    runtime_mock.assert_called_once_with(
                        Path(f"/fake/bin/python{version.major}")
                    )

    @patch("thx.context.shutil.which")
    @patch("thx.context.runtime_version")
    def test_find_runtime_no_venv_no_binary(
        self, runtime_mock: Mock, which_mock: Mock
    ) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            config = Config(root=tdp)

            which_mock.return_value = None

            for version in TEST_VERSIONS:
                runtime_mock.reset_mock()
                which_mock.reset_mock()

                with self.subTest(version):
                    venv = context.venv_path(config, version)

                    expected = None
                    result, _ = context.find_runtime(version, venv)
                    self.assertEqual(expected, result)

                    which_mock.assert_has_calls(
                        [
                            call(f"python{version.major}.{version.minor}"),
                            call(f"python{version.major}"),
                            call("python"),
                        ]
                    )
                    runtime_mock.assert_not_called()

    @patch("thx.context.shutil.which")
    @patch("thx.context.runtime_version")
    def test_find_runtime_no_venv_wrong_version(
        self, runtime_mock: Mock, which_mock: Mock
    ) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            config = Config(root=tdp)

            which_mock.side_effect = lambda b: f"/fake/bin/{b}"
            runtime_mock.return_value = Version("1.2.3")

            for version in TEST_VERSIONS:
                runtime_mock.reset_mock()
                which_mock.reset_mock()

                with self.subTest(version):
                    venv = context.venv_path(config, version)

                    expected = None
                    result, _ = context.find_runtime(version, venv)
                    self.assertEqual(expected, result)

                    which_mock.assert_has_calls(
                        [
                            call(f"python{version.major}.{version.minor}"),
                            call(f"python{version.major}"),
                            call("python"),
                        ]
                    )
                    runtime_mock.assert_has_calls(
                        [
                            call(
                                Path(f"/fake/bin/python{version.major}.{version.minor}")
                            ),
                            call(Path(f"/fake/bin/python{version.major}")),
                            call(Path("/fake/bin/python")),
                        ]
                    )

    @patch("thx.context.shutil.which")
    @patch("thx.context.runtime_version")
    def test_find_runtime_venv(self, runtime_mock: Mock, which_mock: Mock) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            config = Config(root=tdp)

            which_mock.side_effect = lambda b, path: f"{path}/{b}"

            for version in TEST_VERSIONS:
                which_mock.reset_mock()

                with self.subTest(version):
                    venv = context.venv_path(config, version)
                    (venv / "bin").mkdir(parents=True, exist_ok=True)

                    expected = venv / "bin" / "python"
                    result, _ = context.find_runtime(version, venv)
                    self.assertEqual(expected, result)

                    which_mock.assert_has_calls(
                        [
                            call(
                                "python",
                                path=(venv / "bin").as_posix(),
                            ),
                        ]
                    )
                    runtime_mock.assert_not_called()

    @patch("thx.context.find_runtime")
    def test_resolve_contexts_no_config(self, runtime_mock: Mock) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            config = Config(root=tdp)
            active_version = Version(platform.python_version())
            expected = [
                Context(
                    active_version,
                    Path(""),
                    context.venv_path(config, active_version),
                    live=True,
                )
            ]
            result = context.resolve_contexts(config, Options())
            self.assertListEqual(expected, result)
            runtime_mock.assert_not_called()

    @patch("thx.context.find_runtime")
    @patch("thx.context.LOG")
    def test_resolve_contexts_multiple_versions(
        self, log_mock: Mock, runtime_mock: Mock
    ) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            config = Config(root=tdp, versions=TEST_VERSIONS)

            expected_venvs = {
                version: context.venv_path(config, version) for version in TEST_VERSIONS
            }
            expected_runtimes = {
                version: (expected_venvs[version] / "bin" / "python")
                for version in TEST_VERSIONS
            }

            skipped_minors = (5, 128)

            def fake_find_runtime(
                version: Version, venv: Optional[Path] = None
            ) -> Tuple[Optional[Path], Optional[Version]]:
                if version.minor in skipped_minors:
                    return None, None

                return expected_runtimes[version], version

            runtime_mock.side_effect = fake_find_runtime

            expected = [
                Context(version, expected_runtimes[version], expected_venvs[version])
                for version in TEST_VERSIONS
                if version.minor not in skipped_minors
            ]
            result = context.resolve_contexts(config, Options())
            self.assertListEqual(expected, result)
            runtime_mock.assert_has_calls([call(version) for version in TEST_VERSIONS])
            log_mock.warning.assert_called_once()

    @async_test
    async def test_project_requirements(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()

            with self.subTest("empty dir no config"):
                config = Config(root=tdp)
                expected: List[Path] = []
                reqs = list(context.project_requirements(config))
                self.assertListEqual(expected, reqs)

            with self.subTest("empty dir with config"):
                config = Config(
                    root=tdp, requirements=["requirements.txt", "requirements-dev.txt"]
                )
                expected = [tdp / "requirements.txt", tdp / "requirements-dev.txt"]
                reqs = list(context.project_requirements(config))
                self.assertListEqual(expected, reqs)

            (tdp / "requirements.txt").write_text("\n")

            with self.subTest("reqs file no config"):
                config = Config(root=tdp)
                expected = [tdp / "requirements.txt"]
                reqs = list(context.project_requirements(config))
                self.assertListEqual(expected, reqs)

            with self.subTest("reqs file with config"):
                config = Config(
                    root=tdp, requirements=["requirements.txt", "requirements-dev.txt"]
                )
                expected = [tdp / "requirements.txt", tdp / "requirements-dev.txt"]
                reqs = list(context.project_requirements(config))
                self.assertListEqual(expected, reqs)

    @async_test
    async def test_needs_update(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()

            reqs = tdp / "requirements.txt"
            reqs.write_text("\n")

            venv = tdp / ".thx" / "venv" / "3.4"
            ctx = Context(Version("3.4"), venv / "bin" / "python", venv)
            config = Config(root=tdp)

            with self.subTest("no venv"):
                self.assertTrue(context.needs_update(ctx, config))

            with self.subTest("fake venv"):
                venv.mkdir(parents=True)
                (venv / context.TIMESTAMP).write_text("0\n")
                self.assertFalse(context.needs_update(ctx, config))

    @patch("thx.context.run_command")
    @patch("thx.context.which")
    @async_test
    async def test_prepare_virtualenv_live(
        self, which_mock: Mock, run_mock: Mock
    ) -> None:
        async def fake_run_command(cmd: Sequence[StrPath]) -> CommandResult:
            return CommandResult(0, "", "")

        run_mock.side_effect = fake_run_command
        which_mock.side_effect = lambda b, ctx: f"{ctx.venv / 'bin'}/{b}"

        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            reqs = tdp / "requirements.txt"
            reqs.write_text("\n")

            config = Config(root=tdp)
            ctx = context.resolve_contexts(config, Options(live=True))[0]
            self.assertTrue(ctx.live)

            pip = which_mock("pip", ctx)

            events = [event async for event in context.prepare_virtualenv(ctx, config)]
            expected = [VenvReady(ctx)]
            for event in expected:
                self.assertIn(event, events)

            run_mock.assert_has_calls(
                [
                    call([pip, "install", "-U", "pip"]),
                    call([pip, "install", "-U", "-r", reqs]),
                    call([pip, "install", "-U", config.root]),
                ]
            )

            # should reuse virtualenv
            run_mock.reset_mock()

            expected = [VenvReady(ctx)]
            events = [event async for event in context.prepare_virtualenv(ctx, config)]
            self.assertListEqual(expected, events)

            run_mock.assert_not_called()

    @patch("thx.context.prepare_virtualenv")
    @async_test
    async def test_prepare_contexts(self, venv_mock: Mock) -> None:
        async def fake_prepare_virtualenv(
            context: Context, config: Config
        ) -> AsyncIterator[Event]:
            yield VenvCreate(context)
            yield VenvReady(context)

        venv_mock.side_effect = fake_prepare_virtualenv

        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            config = Config(root=tdp)
            contexts = [
                Context(Version("3.4"), Path("/opt/fake/python3.4"), tdp / "venv1"),
                Context(Version("3.5"), Path("/opt/fake/python3.5"), tdp / "venv2"),
            ]
            events = [
                event async for event in context.prepare_contexts(contexts, config)
            ]
            expected = [
                VenvReady(contexts[0]),
                VenvReady(contexts[1]),
            ]
            for event in expected:
                self.assertIn(event, events)
            venv_mock.assert_has_calls([call(ctx, config) for ctx in contexts])
