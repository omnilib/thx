# Copyright 2021 John Reese
# Licensed under the MIT License

from dataclasses import dataclass, field
from pathlib import Path
from shlex import quote
from typing import List, Mapping, Optional, Sequence, Union

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

StrPath = Union[str, Path]


class ConfigError(ValueError):
    """Invalid configuration value"""


@dataclass
class Job:
    name: str
    run: Sequence[str]
    requires: Sequence[str] = ()
    once: bool = False

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
    requirements: Sequence[str] = field(default_factory=list)

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
    config: Config = field(default_factory=Config)
    debug: bool = False
    jobs: List[str] = field(default_factory=list)
    python: Optional[Version] = None
    exit: bool = False


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class Event:
    command: Sequence[str]
    job: Job
    context: Context

    def __str__(self) -> str:
        cmd = " ".join(quote(arg) for arg in self.command)
        return f"{self.context.python_version} {self.job.name}> {cmd}"


@dataclass
class Start(Event):
    pass


@dataclass
class Result(Event, CommandResult):
    def __str__(self) -> str:
        cmd = " ".join(quote(arg) for arg in self.command)
        status = "OK" if self.success else "FAIL"
        return f"{self.context.python_version} {self.job.name}> {cmd} {status}"
