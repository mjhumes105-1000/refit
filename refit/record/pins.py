"""Pin references: one canonical key ("U3.6") for every way people write a pin."""

import re

_PIN_RE = re.compile(
    r"^\s*([A-Z]+\d+[A-Z]?)\s*(?:\.|-|:|\s+PIN\s+|\s+)\s*([A-Z0-9]+)\s*$",
    re.IGNORECASE,
)


def parse_pin_ref(text: str) -> tuple[str, str]:
    match = _PIN_RE.match(text)
    if match is None:
        raise ValueError(f"not a pin reference: {text!r}")
    return match.group(1).upper(), match.group(2).upper()


def pin_key(refdes: str, pin: str) -> str:
    r, p = refdes.strip().upper(), pin.strip().upper()
    if not r or not p:
        raise ValueError(f"empty refdes or pin: {refdes!r}, {pin!r}")
    return f"{r}.{p}"


def normalize_pin(text: str) -> str:
    return pin_key(*parse_pin_ref(text))
