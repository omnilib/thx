# Copyright 2021 John Reese
# Licensed under the MIT License

from dataclasses import dataclass, field
from typing import List, Mapping, Sequence


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
    jobs: Mapping[str, Job] = field(default_factory=dict)
    default: Sequence[str] = field(default_factory=list)
    values: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.default = tuple(d.casefold() for d in self.default)


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
