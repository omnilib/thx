# Copyright 2021 John Reese
# Licensed under the MIT License

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Mapping, Sequence

from packaging.version import Version


__all__ = [
    "Config",
    "ConfigError",
    "Context",
    "Job",
    "Options",
    "Result",
    "Version",
]


class ConfigError(ValueError):
    """Invalid configuration value"""


@dataclass
class Job:
    name: str
    run: Sequence[str]
    requires: Sequence[str] = ()

    def __post_init__(self) -> None:
        self.name = self.name.casefold()
        self.requires = tuple(r.casefold() for r in self.requires)


@dataclass
class Config:
    root: Path = field(default_factory=Path.cwd)
    jobs: Mapping[str, Job] = field(default_factory=dict)
    default: Sequence[str] = field(default_factory=list)
    values: Mapping[str, str] = field(default_factory=dict)
    versions: Sequence[Version] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.default = tuple(d.casefold() for d in self.default)


@dataclass
class Context:
    python_version: Version
    python_path: Path
    venv: Path
    live: bool = False


@dataclass
class Options:
    debug: bool = False
    config: Config = field(default_factory=Config)
    jobs: List[str] = field(default_factory=list)
    exit: bool = False


@dataclass
class Result:
    command: Sequence[str]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0
