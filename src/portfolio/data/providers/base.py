"""Minimal public response contract, excluding headers and authentication state."""
from dataclasses import dataclass

@dataclass(frozen=True)
class RawResponse:
    body: bytes
    status_code: int
