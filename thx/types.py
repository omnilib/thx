# Copyright 2021 John Reese
# Licensed under the MIT License

from dataclasses import dataclass, field
from typing import Sequence, Mapping


class ConfigError(ValueError):
    """Invalid configuration value"""


@dataclass
class Command:
    name: str
    run: Sequence[str]
    requires: Sequence[str] = ()

    def __post_init__(self):
        self.name = self.name.casefold()
        self.requires = tuple(r.casefold() for r in self.requires)


@dataclass
class Config:
    commands: Mapping[str, Command] = field(default_factory=dict)
    default: Sequence[str] = field(default_factory=list)
    values: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.default = tuple(d.casefold() for d in self.default)


@dataclass
class Result:
    command: Sequence[str]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0
