# Copyright 2021 John Reese
# Licensed under the MIT License

import logging
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional, Sequence, Tuple

from aioitertools.asyncio import as_generated
from packaging.version import Version

from thx.utils import version_match

from .runner import run_command, which

from .types import Config, Context, Event, Options, StrPath, VenvCreate, VenvReady
from .utils import timed

LOG = logging.getLogger(__name__)
PYTHON_VERSION_RE = re.compile(r"Python (\d+\.\d+\S+)")
PYTHON_VERSIONS: Dict[Path, Optional[Version]] = {}
TIMESTAMP = "thx.timestamp"


def venv_path(config: Config, version: Version) -> Path:
    return config.root / ".thx" / "venv" / str(version)


def runtime_version(binary: Path) -> Optional[Version]:
    if binary not in PYTHON_VERSIONS:
        try:
            proc = subprocess.run(
                (binary.as_posix(), "-V"),
                capture_output=True,
                encoding="utf-8",
                timeout=1,
            )

        except Exception as e:
            LOG.warning("running `%s -V` failed: %s", binary, e)
            PYTHON_VERSIONS[binary] = None
            return None

        match = PYTHON_VERSION_RE.search(proc.stdout)
        if not match:
            LOG.warning(
                "running `%s -V` gave unexpected version string: %s",
                binary,
                proc.stdout,
            )
            PYTHON_VERSIONS[binary] = None
            return None

        declared = Version(match.group(1))
        LOG.debug("found %s version %s", binary, declared)

        PYTHON_VERSIONS[binary] = declared

    return PYTHON_VERSIONS[binary]


def find_runtime(
    version: Version, venv: Optional[Path] = None
) -> Tuple[Optional[Path], Optional[Version]]:
    if venv and venv.is_dir():
        bin_dir = venv / "bin"
        if bin_dir.is_dir():
            binary_path_str = shutil.which("python", path=f"{bin_dir.as_posix()}")
            if binary_path_str:
                return Path(binary_path_str), None

    # TODO: better way to find specific micro/pre/post versions?
    binary_names = [
        f"python{version.major}.{version.minor}",
        f"python{version.major}",
        "python",
    ]
    for binary in binary_names:
        binary_path_str = shutil.which(binary)
        LOG.debug("which(%s) -> %s", binary, binary_path_str)
        if binary_path_str is not None:
            binary_path = Path(binary_path_str)
            binary_version = runtime_version(binary_path)

            if binary_version is None:
                continue

            if version_match([binary_version], version):
                return binary_path, binary_version

    return None, None


@timed("resolve contexts")
def resolve_contexts(config: Config, options: Options) -> List[Context]:
    if options.live or not config.versions:
        version = Version(platform.python_version())
        # defer resolving python path to after venv creation
        return [Context(version, Path(""), venv_path(config, version), live=True)]

    contexts: List[Context] = []
    missing_versions: List[Version] = []
    for version in config.versions:
        runtime_path, runtime_version = find_runtime(version)

        if runtime_path is None or runtime_version is None:
            missing_versions.append(version)
        else:
            venv = venv_path(config, runtime_version)
            contexts.append(Context(runtime_version, runtime_path, venv))

    if missing_versions:
        LOG.warning("missing Python versions: %r", [str(v) for v in missing_versions])

    context_versions = [context.python_version for context in contexts]
    LOG.info("Available Python versions: %s", context_versions)

    if options.python is not None:
        matched_versions = version_match(context_versions, options.python)
        contexts = [
            context
            for context in contexts
            if context.python_version in matched_versions
        ]

    return contexts


def project_requirements(config: Config) -> Sequence[Path]:
    """Get a list of Path objects for configured or discovered requirements files"""
    paths: List[Path] = []
    if config.requirements:
        paths += [(config.root / req) for req in config.requirements]
    else:
        paths += [req for req in config.root.glob("requirements*.txt")]
    return paths


def needs_update(context: Context, config: Config) -> bool:
    """Compare timestamps of marker file and requirements files"""
    try:
        timestamp = context.venv / TIMESTAMP
        if timestamp.exists():
            base = timestamp.stat().st_mtime_ns
            newest = 0
            reqs = project_requirements(config)
            for req in reqs:
                if req.exists():
                    mod_time = req.stat().st_mtime_ns
                    newest = max(newest, mod_time)
            return newest > base

        else:
            LOG.debug("no timestamp for %s", context.venv)

    except Exception:
        LOG.warning(
            "Failed to read timestamps of virtualenv/requirements for %s",
            context.venv,
            exc_info=True,
        )

    return True


@timed("prepare virtualenv")
async def prepare_virtualenv(context: Context, config: Config) -> AsyncIterator[Event]:
    """Setup virtualenv and install packages"""

    if needs_update(context, config):
        LOG.info("preparing virtualenv %s", context.venv)
        yield VenvCreate(context, message="creating virtualenv")

        # create virtualenv
        prompt = f"thx-{context.python_version}"
        if context.live:
            import venv

            venv.create(context.venv, clear=True, prompt=prompt, with_pip=True)
            new_python_path, _ = find_runtime(context.python_version, context.venv)
            assert new_python_path is not None
            context.python_path = new_python_path

        else:
            await run_command(
                [
                    context.python_path,
                    "-m",
                    "venv",
                    "--clear",
                    "--prompt",
                    prompt,
                    context.venv,
                ]
            )

        # upgrade pip
        yield VenvCreate(context, message="upgrading pip")
        pip = which("pip", context)
        await run_command([pip, "install", "-U", "pip"])

        # install requirements.txt
        yield VenvCreate(context, message="installing requirements")
        requirements = project_requirements(config)
        if requirements:
            LOG.debug("installing deps from %s", requirements)
            cmd: List[StrPath] = [pip, "install", "-U"]
            for requirement in requirements:
                cmd.extend(["-r", requirement])
            await run_command(cmd)

        # install local project
        yield VenvCreate(context, message="installing project")
        await run_command([pip, "install", "-U", config.root])

        # timestamp marker
        content = f"{time.time_ns()}\n"
        (context.venv / TIMESTAMP).write_text(content)

    else:
        LOG.debug("reusing existing virtualenv %s", context.venv)

    yield VenvReady(context)


@timed("prepare contexts")
async def prepare_contexts(
    contexts: Sequence[Context], config: Config
) -> AsyncIterator[Event]:
    gens = [prepare_virtualenv(context, config) for context in contexts]
    async for event in as_generated(gens):
        yield event
