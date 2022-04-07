# Copyright 2021 John Reese
# Licensed under the MIT License

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import tomli
from packaging.version import Version
from trailrunner.core import project_root

from .types import Config, ConfigError, Job


def ensure_dict(value: Any, key: str) -> Dict[str, Any]:
    result: Dict[str, Any]

    if value is None:
        result = {}
    elif isinstance(value, Mapping):
        result = {k: v for k, v in value.items()}
    else:
        raise ConfigError(f"Option {key!r} must be a dictionary; {value!r} given")

    return result


def ensure_listish(value: Any, key: str) -> List[str]:
    result: List[str]

    if value is None:
        result = []
    elif isinstance(value, str):
        result = [value]
    elif isinstance(value, (Iterable, Sequence)):
        result = list(value)
    else:
        raise ConfigError(
            f"Option {key!r} must be a string or list of strings; {value!r} given"
        )

    for elem in result:
        if not isinstance(elem, str):
            raise ConfigError(
                f"Option {key!r} must be a string or list of strings; {value!r} given"
            )

    return result


def parse_job(name: str, data: Dict[str, Any]) -> Job:
    run: List[str]
    requires: List[str]
    once: bool = Job.once
    parallel: bool = Job.parallel
    show_output: bool = Job.show_output

    if isinstance(data, str):
        run = [data]
        requires = ()
    elif isinstance(data, list):
        run = ensure_listish(data, f"tool.thx.jobs.{name}")
        requires = ()
    elif isinstance(data, dict):
        run = ensure_listish(data.pop("run", None), f"tool.thx.jobs.{name}.run")
        requires = ensure_listish(
            data.pop("requires", None), f"tool.thx.jobs.{name}.requires"
        )
        if "once" in data:
            once = bool(data.pop("once"))
        if "parallel" in data:
            parallel = bool(data.pop("parallel"))
        if "show_output" in data:
            show_output = bool(data.pop("show_output"))
    else:
        raise ConfigError(
            f"Job {name!r} must be string, list of strings, or dictionary; "
            f"{data!r} given"
        )

    return Job(
        name=name,
        run=tuple(run),
        requires=tuple(requires),
        once=once,
        parallel=parallel,
        show_output=show_output,
    )


def parse_jobs(data: Any) -> List[Job]:
    job_data = ensure_dict(data, "tool.thx.jobs")

    jobs: List[Job] = []
    for name, value in job_data.items():
        name = name.casefold()
        jobs.append(parse_job(name, value))

    return jobs


def validate_config(config: Config) -> Config:
    for name in config.default:
        if name not in config.jobs:
            raise ConfigError(f"Option tool.thx.default: undefined job {name!r}")

    for name, job in config.jobs.items():
        assert name == job.name
        for require in job.requires:
            if require not in config.jobs:
                raise ConfigError(
                    f"Option tool.thx.jobs.{name}.requires: "
                    f"undefined job {require!r}"
                )

    for path in config.watch_paths:
        if path.is_absolute() or path.as_posix().startswith("/"):
            raise ConfigError(
                f"Option tool.thx.watch_paths: absolute paths not supported ({path!r})"
            )

    return config


def load_config(path: Optional[Path] = None) -> Config:
    if path is None:
        path = Path.cwd()
    path = path.resolve()

    root = project_root(path)
    pyproject = root / "pyproject.toml"

    if not pyproject.is_file():
        return Config(root=path)

    content = pyproject.read_text()
    data = tomli.loads(content).get("tool", {}).get("thx", {})

    default: List[str] = ensure_listish(data.pop("default", None), "tool.thx.default")
    jobs: List[Job] = parse_jobs(data.pop("jobs", {}))
    versions: List[Version] = sorted(
        set(
            Version(v)
            for v in ensure_listish(
                data.pop("python_versions", None), "tool.thx.python_versions"
            )
        ),
        reverse=True,
    )
    requirements: List[str] = ensure_listish(
        data.pop("requirements", None), "tool.thx.requirements"
    )
    watch_paths: List[Path] = [
        Path(p)
        for p in ensure_listish(
            data.pop("watch_paths", None),
            "tool.thx.watch_paths",
        )
    ]

    return validate_config(
        Config(
            root=root,
            default=default,
            jobs={cmd.name: cmd for cmd in jobs},
            values=data,
            versions=versions,
            requirements=requirements,
            watch_paths=watch_paths,
        )
    )
