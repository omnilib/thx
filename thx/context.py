# Copyright 2022 Amethyst Reese
# Licensed under the MIT License

import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from itertools import chain
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional, Sequence, Tuple

from aioitertools.asyncio import as_generated

from .runner import check_command
from .types import (
    Builder,
    CommandError,
    Config,
    ConfigError,
    Context,
    Event,
    Options,
    StrPath,
    VenvCreate,
    VenvError,
    VenvReady,
    Version,
)
from .utils import timed, venv_bin_path, version_match, which

LOG = logging.getLogger(__name__)
PYTHON_VERSION_RE = re.compile(r"Python (\d+\.\d+[a-zA-Z0-9-_.]+)\+?")
PYTHON_VERSIONS: Dict[Path, Optional[Version]] = {}
TIMESTAMP = "thx.timestamp"


def venv_path(config: Config, version: Version) -> Path:
    """
    Return the path for the desired virtual environment for the given version.
    """
    return config.root / ".thx" / "venv" / str(version)


def runtime_version(binary: Path) -> Optional[Version]:
    """Load the version printed by the given Python interpreter.

    Cache the result to avoid repeated calls.
    """
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
                "running `%s -V` gave unexpected version string: %r",
                binary,
                proc.stdout,
            )
            if proc.stderr:
                LOG.warning(
                    "unexpected version string included stderr:\n%s", proc.stderr
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
    """
    Locate a Python interpreter matching the desired `version`. If `venv` is provided
    and is a directory, look for its Python. Otherwise, try typical binary names.
    """
    if venv and venv.is_dir():
        bin_dir = venv_bin_path(venv)
        binary_path_str = shutil.which("python", path=bin_dir.as_posix())
        if binary_path_str:
            binary_path = Path(binary_path_str)
            binary_version = runtime_version(binary_path)
            return binary_path, binary_version

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


def identify_venv(venv_path: Path) -> Tuple[Path, Version]:
    """Read the pyvenv.cfg from a venv to determine the Python version.

    Return a path to the Python interpreter and the version of that interpreter.
    """
    cfg = venv_path / "pyvenv.cfg"

    try:
        f = cfg.open()
    except FileNotFoundError:
        raise ConfigError(f"venv {venv_path} is missing pyvenv.cfg.") from None

    # Canonical parsing of pyvenv.cfg is here:
    # https://github.com/python/cpython/blob/e65a1eb93ae35f9fbab1508606e3fbc89123629f/Modules/getpath.py#L372
    # The file is a simple key=value format and any lines that are malformed
    # are ignored.
    VERSION_KEYS = (
        "version_info",  # uv
        "version",  # venv
    )
    kvs = {}
    version = None
    with f:
        for line in f:
            key, eq, value = line.partition("=")
            if eq and key.strip().lower() in VERSION_KEYS:
                version = Version(value.strip())
                break
            elif eq:
                kvs[key.strip()] = value.strip()

    if version is None:
        raise ConfigError(
            f"pyvenv.cfg in venv {venv_path} does not contain version: {kvs}"
        )

    bin_dir = venv_bin_path(venv_path)
    candidates = [
        f"python{version.major}.{version.minor}",
        f"python{version.major}",
        "python",
    ]
    for candidate in candidates:
        python_path = bin_dir / candidate
        if python_path.exists():
            break
    else:
        raise ConfigError(f"venv {venv_path} does not contain a Python interpreter")
    return python_path, version


@timed("resolve contexts")
def resolve_contexts(config: Config, options: Options) -> List[Context]:
    """Build a list of contexts in which to run.

    We evaluate the list of Python versions from config, as well as
    command-line options refining the list.
    """
    builder = determine_builder(config)

    if options.live or not config.versions:
        version = Version(platform.python_version().rstrip("+"))
        # defer resolving python path to after venv creation
        return [
            Context(
                version,
                Path(sys.executable),
                venv_path(config, version),
                builder,
                live=True,
            )
        ]

    if builder == Builder.UV:
        # If using uv we can let uv resolve the Python path for each version,
        # which may involve installing a new Python version.

        versions = config.versions
        if options.python is not None:
            versions = version_match(config.versions, options.python)
        return [
            Context(version, None, venv_path(config, version), builder)
            for version in versions
        ]

    contexts: List[Context] = []
    missing_versions: List[Version] = []
    for version in config.versions:
        runtime_path, runtime_version = find_runtime(version)

        if runtime_path is None or runtime_version is None:
            missing_versions.append(version)
        else:
            venv = venv_path(config, runtime_version)
            contexts.append(Context(runtime_version, runtime_path, venv, builder))

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
    """Return a list of requirements file paths for the project.

    If config.requirements is given, use those paths. Otherwise, search for
    requirements*.txt files in the project root.
    """
    paths: List[Path] = []
    if config.requirements:
        paths += [(config.root / req) for req in config.requirements]
    else:
        paths += [req for req in config.root.glob("requirements*.txt")]
    return paths


def needs_update(context: Context, config: Config) -> bool:
    """Return True if the environment needs to be rebuilt.

    We currently do this by comparing the modification time of all requirements
    files to a stored timestamp file inside the venv.
    """
    try:
        timestamp = context.venv / TIMESTAMP
        if timestamp.exists():
            base = timestamp.stat().st_mtime_ns
            newest = 0
            for path in chain(
                [config.root / "pyproject.toml"],
                project_requirements(config),
            ):
                if path.exists():
                    mod_time = path.stat().st_mtime_ns
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
    """
    Prepare the virtual environment, either using pip or uv logic,
    depending on config.builder (or auto).
    """
    if needs_update(context, config):
        LOG.info("preparing virtualenv %s", context.venv)
        yield VenvCreate(context, message="creating virtualenv")

        builder = context.builder
        if builder == Builder.UV:
            task = prepare_virtualenv_uv(context, config)
        elif builder == Builder.PIP:
            task = prepare_virtualenv_pip(context, config)
        else:
            raise ConfigError(f"Unknown builder: {builder}")
        async for event in task:
            yield event
    else:
        LOG.debug("reusing existing virtualenv %s", context.venv)
        yield VenvReady(context)


def determine_builder(config: Config) -> Builder:
    """Resolve which builder to use.

    If a builder is explicitly configured, attempt to use it (and fail if it
    is unavailable.)

    If builder is auto, pick uv if available, else pip.
    """
    uv = shutil.which("uv")
    if config.builder == Builder.AUTO:
        if uv is not None:
            return Builder.UV
        return Builder.PIP
    if config.builder == Builder.UV:
        if uv is None:
            raise ConfigError("uv not found on PATH, cannot build with uv")
    return config.builder


async def prepare_virtualenv_pip(
    context: Context, config: Config
) -> AsyncIterator[Event]:
    """Create and populate a venv using venv and pip."""
    try:
        # Create the venv
        if context.live:
            import venv

            venv.create(
                context.venv,
                prompt=f"thx-{context.python_version}",
                with_pip=True,
                symlinks=(os.name != "nt"),
            )
        else:
            assert (
                context.python_path is not None
            ), "python_path must be resolved for non-live venv with pip"
            await check_command(
                [
                    context.python_path,
                    "-m",
                    "venv",
                    "--prompt",
                    f"thx-{context.python_version}",
                    context.venv,
                ]
            )

        # Update runtime in context
        context.python_path, context.python_version = identify_venv(context.venv)

        # Upgrade pip, setuptools
        yield VenvCreate(context, message="upgrading pip")
        await check_command(
            [
                context.python_path,
                "-m",
                "pip",
                "install",
                "-U",
                "pip",
                "setuptools",
            ]
        )
        pip = which("pip", context)

        # Install requirements
        requirements = project_requirements(config)
        if requirements:
            yield VenvCreate(context, message="installing requirements")
            LOG.debug("installing deps from %s", requirements)
            cmd: List[StrPath] = [pip, "install", "-U"]
            for requirement in requirements:
                cmd.extend(["-r", requirement])
            await check_command(cmd)

        # Install local project
        yield VenvCreate(context, message="installing project")
        if config.extras:
            proj = f"{config.root}[{','.join(config.extras)}]"
        else:
            proj = str(config.root)
        await check_command([pip, "install", "-U", proj])

        # Record a timestamp
        (context.venv / TIMESTAMP).write_text(f"{time.time_ns()}\n")

        yield VenvReady(context)

    except CommandError as error:
        yield VenvError(context, error)


async def prepare_virtualenv_uv(
    context: Context, config: Config
) -> AsyncIterator[Event]:
    """Create and populate a venv using uv."""
    try:
        # Create the venv with uv
        uv = shutil.which("uv")
        if not uv:
            raise ConfigError("uv not found on PATH, cannot build with uv")

        await check_command(
            [
                uv,
                "venv",
                f"--prompt=thx-{context.python_version}",
                "-p",
                (
                    str(context.python_path)
                    if context.python_path
                    else str(context.python_version)
                ),
                str(context.venv),
            ]
        )

        context.python_path, context.python_version = identify_venv(context.venv)

        # Install requirements
        requirements = project_requirements(config)
        if requirements:
            yield VenvCreate(context, message="installing requirements via uv")
            LOG.debug("installing deps from %s with uv", requirements)

            # Equivalent to `pip install -U -r <req>`
            reqs = []
            for requirement in requirements:
                reqs.extend(["-r", str(requirement)])
            await check_command(
                [uv, "pip", "install", *reqs],
                context=context,
            )

        # Install local project
        yield VenvCreate(context, message="installing project via uv")
        if config.extras:
            proj = f"{config.root}[{','.join(config.extras)}]"
        else:
            proj = str(config.root)
        await check_command([uv, "pip", "install", proj], context=context)

        # Record a timestamp
        (context.venv / TIMESTAMP).write_text(f"{time.time_ns()}\n")

        yield VenvReady(context)

    except CommandError as error:
        yield VenvError(context, error)


@timed("prepare contexts")
async def prepare_contexts(
    contexts: Sequence[Context], config: Config
) -> AsyncIterator[Event]:
    """
    Prepare each context in parallel (as an async generator of events).
    """
    gens = [prepare_virtualenv(context, config) for context in contexts]
    async for event in as_generated(gens):
        yield event
