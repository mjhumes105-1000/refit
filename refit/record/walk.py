"""Find every Claim inside a record (or any part of one)."""

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from refit.record.claims import Claim


class DuplicateClaimId(ValueError):
    pass


def iter_claims(obj: Any) -> Iterator[Claim]:
    if isinstance(obj, Claim):
        yield obj
    elif isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            yield from iter_claims(getattr(obj, name))
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from iter_claims(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from iter_claims(value)


def claim_index(obj: Any) -> dict[str, Claim]:
    index: dict[str, Claim] = {}
    for claim in iter_claims(obj):
        if claim.id in index:
            raise DuplicateClaimId(claim.id)
        index[claim.id] = claim
    return index
