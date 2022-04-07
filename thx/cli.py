# Copyright 2021 John Reese
# Licensed under the MIT License

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, cast, Dict, List, Optional

from rich.console import Group
from rich.live import Live
from rich.text import Text
from rich.tree import Tree

from .types import (
    Context,
    Event,
    Fail,
    Job,
    JobEvent,
    Reset,
    Result,
    Step,
    VenvCreate,
    VenvReady,
)

LOG = logging.getLogger(__name__)


@dataclass
class RichRenderer:
    venvs: Dict[Context, Event] = field(default_factory=dict)
    latest: Dict[Job, Dict[Context, Dict[Step, Event]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(dict))
    )
    view: Live = field(init=False)

    def __post_init__(self) -> None:
        self.view = Live(auto_refresh=False)
        self.view.update(Group())

    def __enter__(self) -> "RichRenderer":
        self.view.__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        self.view.__exit__(*args, **kwargs)

    def __call__(self, event: Optional[Event]) -> None:
        assert isinstance(event, Event), "must be a thx.Event"

        if isinstance(event, Reset):
            self.venvs.clear()
            self.latest.clear()
            self.view.update(Text(""), refresh=True)
            return

        venvs = self.venvs
        latest = self.latest

        if isinstance(event, Fail):
            group: Group = cast(Group, self.view.get_renderable())
            group.renderables.append(Tree("FAIL", style="red"))
            self.view.update(group, refresh=True)
            return

        if isinstance(event, (VenvCreate, VenvReady)):
            venvs[event.context] = event
        elif isinstance(event, JobEvent):
            step = event.step
            job = step.job
            latest[job][event.context][step] = event

        trees: List[Tree] = []

        if venvs and not all(isinstance(v, VenvReady) for v in venvs.values()):
            tree = Tree("Preparing virtualenvs...")
            for context, event in venvs.items():
                if isinstance(event, VenvReady):
                    text = Text(f"{context.python_version}> done", style="green")
                else:
                    text = Text(f"{event}")
                tree.add(text)
            trees.append(tree)

        for job in latest:
            tree = Tree(job.name)
            job_success = True

            for context in latest[job]:
                context_tree = Tree(str(context.python_version))

                context_success = True
                for step, event in latest[job][context].items():
                    text = Text(str(event))
                    if isinstance(event, Result):
                        text.stylize("green" if event.success else "red")
                        if event.error or job.show_output:
                            text.append("\n", style="")
                            text.append(event.stdout, style="")
                            text.append("\n", style="")
                            text.append(event.stderr, style="")
                        if event.error:
                            context_success = False
                    else:
                        context_success = False
                    context_tree.add(text)

                if context_success:
                    context_tree.label = Text(
                        f"{context.python_version} OK", style="green"
                    )
                    if not job.show_output:
                        pass  # context_tree.expanded = False
                else:
                    job_success = False

                tree.add(context_tree)

            if job_success:
                tree.label = Text(f"{job.name} OK", style="green")
                if not job.show_output:
                    tree.expanded = False

            trees.append(tree)

        self.view.update(Group(*trees), refresh=True)
