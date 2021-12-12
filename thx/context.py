# Copyright 2021 John Reese
# Licensed under the MIT License

import logging
import platform
import re
import subprocess
from pathlib import Path
from shutil import which
from typing import Dict, List, Optional

from packaging.version import Version

from .types import Config, Context

LOG = logging.getLogger(__name__)
PYTHON_VERSION_RE = re.compile(r"Python (\d+\.\d+(\.\d+)?)")
PYTHON_VERSIONS: Dict[Path, Optional[Version]] = {}


def venv_path(config: Config, version: Version) -> Path:
    if version.micro:
        return (
            config.root
            / ".thx"
            / "venv"
            / f"{version.major}.{version.minor}.{version.micro}"
        )
    else:
        return config.root / ".thx" / "venv" / f"{version.major}.{version.minor}"


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
            binary_path_str = which("python", path=f"{bin_dir.as_posix()}")
            if binary_path_str:
                return Path(binary_path_str)

    binary_names = [
        f"python{version.major}.{version.minor}",
        f"python{version.major}",
        "python",
    ]
    for binary in binary_names:
        binary_path_str = which(binary)
        LOG.debug("which(%s) -> %s", binary, binary_path_str)
        if binary_path_str is not None:
            binary_path = Path(binary_path_str)
            binary_version = runtime_version(binary_path)

            if binary_version is None:
                continue

            if (
                binary_version.major == version.major
                and binary_version.minor == version.minor
                and (not version.micro or binary_version.micro == version.micro)
            ):
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

    LOG.warning("missing Python versions: %r", [str(v) for v in missing_versions])

    return contexts
