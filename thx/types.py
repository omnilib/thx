# Copyright 2021 John Reese
# Licensed under the MIT License

from dataclasses import dataclass, field
from pathlib import Path
from shlex import quote
from typing import Any, Callable, Generator, List, Mapping, Optional, Sequence, Union

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

Renderer = Callable[["Event"], None]
StrPath = Union[str, Path]


class ConfigError(ValueError):
    """Invalid configuration value"""


@dataclass(unsafe_hash=True)
class Job:
    name: str
    run: Sequence[str]
    requires: Sequence[str] = ()
    once: bool = False
    parallel: bool = False
    isolated: bool = False
    show_output: bool = False

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
    watch_paths: Sequence[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.default = tuple(d.casefold() for d in self.default)


@dataclass(unsafe_hash=True)
class Context:
    python_version: Version
    python_path: Path
    venv: Path
    live: bool = False


@dataclass
class Options:
    config: Config = field(default_factory=Config)
    benchmark: bool = False
    debug: bool = False
    jobs: List[str] = field(default_factory=list)
    python: Optional[Version] = None
    live: bool = False
    watch: bool = False
    clean: bool = False
    exit: bool = False


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def error(self) -> bool:
        return self.exit_code != 0


@dataclass(frozen=True)
class Step:
    cmd: Sequence[str]
    job: Job
    context: Context

    def __await__(self) -> Generator[Any, None, "Result"]:
        return self.run().__await__()

    async def run(self) -> "Result":
        raise NotImplementedError


@dataclass
class Event:
    def __str__(self) -> str:
        return self.__class__.__name__


@dataclass
class Reset(Event):
    pass


@dataclass
class Fail(Event):
    pass


@dataclass
class ContextEvent(Event):
    context: Context

    def __str__(self) -> str:
        return f"{self.context.python_version}> {self.__class__.__name__}"


@dataclass
class VenvCreate(ContextEvent):
    message: str = ""

    def __str__(self) -> str:
        return f"{self.context.python_version}> {self.message}"


@dataclass
class VenvReady(ContextEvent):
    def __str__(self) -> str:
        return f"{self.context.python_version}> ready"


@dataclass
class JobEvent(ContextEvent):
    step: Step

    def __str__(self) -> str:
        cmd = " ".join(quote(arg) for arg in self.step.cmd)
        return f"{self.context.python_version} {self.step.job.name}> {cmd}"


@dataclass
class Start(JobEvent):
    pass


@dataclass
class Result(JobEvent, CommandResult):
    def __str__(self) -> str:
        cmd = " ".join(quote(arg) for arg in self.step.cmd)
        status = "OK" if self.success else "FAIL"
        return f"{self.context.python_version} {self.step.job.name}> {cmd} {status}"
