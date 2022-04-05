# Copyright 2021 John Reese
# Licensed under the MIT License

from collections import defaultdict
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from rich.console import Group
from rich.live import Live
from rich.text import Text
from rich.tree import Tree

from .types import (
    Abort,
    Context,
    Event,
    Fail,
    Job,
    JobEvent,
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

    def __enter__(self) -> "RichRenderer":
        self.view.__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        self.view.__exit__(*args, **kwargs)

    def __call__(self, event: Event) -> None:
        venvs = self.venvs
        latest = self.latest

        if isinstance(event, Abort):
            self.venvs.clear()
            self.latest.clear()
            self.view.update(Text(""), refresh=True)
            return

        if isinstance(event, Fail):
            group: Group = self.view.get_renderable()
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
                        if event.error:
                            text.append("\n", style="")
                            text.append(event.stdout, style="")
                            text.append("\n", style="")
                            text.append(event.stderr, style="")
                            context_success = False
                    else:
                        context_success = False
                    context_tree.add(text)

                if context_success:
                    tree.add(Text(f"{context.python_version} OK", style="green"))
                else:
                    job_success = False
                    tree.add(context_tree)

            if job_success:
                trees.append(Tree(f"{job.name} OK", style="green"))
            else:
                trees.append(tree)

        self.view.update(Group(*trees), refresh=True)