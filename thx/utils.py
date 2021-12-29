# Copyright 2021 John Reese
# Licensed under the MIT License

from itertools import zip_longest
from typing import List

from .types import Version


def version_match(versions: List[Version], target: Version) -> List[Version]:
    matches: List[Version] = []
    for version in versions:
        if all(
            v == t or t is None for v, t in zip_longest(version.release, target.release)
        ):
            if target.pre and target.pre != version.pre:
                continue
            if target.post and target.post != version.post:
                continue
            if target.dev and target.dev != version.dev:
                continue
            if target.local and target.local != version.local:
                continue

            matches.append(version)

    return matches
