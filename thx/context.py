# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
import logging
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from packaging.version import Version

from thx.utils import version_match

from .runner import run_command, which

from .types import Config, Context, StrPath

LOG = logging.getLogger(__name__)
PYTHON_VERSION_RE = re.compile(r"Python (\d+\.\d+\S+)")
PYTHON_VERSIONS: Dict[Path, Optional[Version]] = {}


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


def find_runtime(version: Version, venv: Path) -> Optional[Path]:
    if venv.is_dir():
        bin_dir = venv / "bin"
        if bin_dir.is_dir():
            binary_path_str = shutil.which("python", path=f"{bin_dir.as_posix()}")
            if binary_path_str:
                return Path(binary_path_str)

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
                return binary_path

    return None


def resolve_contexts(config: Config) -> List[Context]:
    if not config.versions:
        version = Version(platform.python_version())
        # defer resolving python path to after venv creation
        return [Context(version, Path(""), venv_path(config, version), live=True)]

    contexts: List[Context] = []
    missing_versions: List[Version] = []
    for version in config.versions:
        venv = venv_path(config, version)
        runtime_path = find_runtime(version, venv)

        if runtime_path is None:
            missing_versions.append(version)
        else:
            contexts.append(Context(version, runtime_path, venv))

    if missing_versions:
        LOG.warning("missing Python versions: %r", [str(v) for v in missing_versions])

    return contexts


async def prepare_virtualenv(context: Context, config: Config) -> None:
    """Setup virtualenv and install packages"""
    LOG.info("preparing virtualenv %s", context.venv)
    prompt = f"thx-{context.python_version}"

    # create virtualenv
    if context.live:
        import venv

        venv.create(context.venv, prompt=prompt, with_pip=True)
        new_python_path = find_runtime(context.python_version, context.venv)
        assert new_python_path is not None
        context.python_path = new_python_path

    else:
        await run_command(
            [
                context.python_path,
                "-m",
                "venv",
                "--prompt",
                prompt,
                context.venv,
            ]
        )

    # upgrade pip
    pip = which("pip", context)
    await run_command([pip, "install", "-U", "pip"])

    # install requirements.txt
    requirements: List[StrPath] = []
    if config.requirements:
        requirements += [(config.root / req) for req in config.requirements]
    else:
        requirements += [req for req in config.root.glob("requirements*.txt")]
    if requirements:
        LOG.debug("installing deps from %s", requirements)
        cmd: List[StrPath] = [pip, "install", "-U"]
        for requirement in requirements:
            cmd.extend(["-r", requirement])
        await run_command(cmd)

    # install local project
    await run_command([pip, "install", "-U", config.root])


async def prepare_contexts(contexts: Sequence[Context], config: Config) -> None:
    await asyncio.gather(*[prepare_virtualenv(context, config) for context in contexts])
