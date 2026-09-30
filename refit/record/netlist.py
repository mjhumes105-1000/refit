"""Nets are derived from per-pin net assignments; net IDs are stable for stable membership."""

import hashlib
from collections import defaultdict

from pydantic import BaseModel

from refit.record.claims import StrClaim


class Net(BaseModel):
    id: str
    key: str
    label: str | None
    members: list[str]


def net_id(members: list[str]) -> str:
    joined = ",".join(sorted(members))
    return "N" + hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]


def build_nets(connections: dict[str, StrClaim], *, machine: bool = False) -> list[Net]:
    """Group pins by assigned net key.

    machine=True uses each pin's first automated verdict and skips pins that no
    automated stage produced (e.g. pins a human added).
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for pin, claim in connections.items():
        if machine:
            if claim.machine_status is None:
                continue
            key = claim.machine_value
        else:
            key = claim.value
        groups[key].append(pin)
    nets = [
        Net(
            id=net_id(pins),
            key=key,
            label=None if key.startswith("_") else key,
            members=sorted(pins),
        )
        for key, pins in groups.items()
    ]
    return sorted(nets, key=lambda n: n.members[0])
