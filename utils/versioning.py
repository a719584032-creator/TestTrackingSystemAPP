"""Helpers for semantic-ish version comparison without external deps."""
from __future__ import annotations

import re
from typing import List, Union

VersionToken = Union[int, str]
_SEPARATOR_RE = re.compile(r"[.\-+_]")


def _tokenize(value: str) -> List[VersionToken]:
    tokens: List[VersionToken] = []
    for part in _SEPARATOR_RE.split(value):
        if not part:
            continue
        if part.isdigit():
            tokens.append(int(part))
        else:
            tokens.append(part.lower())
    return tokens


def compare_versions(current: str, remote: str) -> int:
    """Return -1/0/1 indicating if remote is older/eq/newer than current."""

    left = _tokenize(current)
    right = _tokenize(remote)
    length = max(len(left), len(right))
    for idx in range(length):
        lv: VersionToken = left[idx] if idx < len(left) else 0
        rv: VersionToken = right[idx] if idx < len(right) else 0
        if isinstance(lv, int) and isinstance(rv, int):
            if lv != rv:
                return -1 if lv < rv else 1
            continue
        if isinstance(lv, int) and isinstance(rv, str):
            # release numbers are considered newer than pre-release tags
            return 1
        if isinstance(lv, str) and isinstance(rv, int):
            return -1
        if lv != rv:
            return -1 if str(lv) < str(rv) else 1
    return 0


def is_remote_newer(current: str, remote: str) -> bool:
    """True if the remote version string represents a newer build."""

    if not current:
        return bool(remote)
    if not remote:
        return False
    return compare_versions(current, remote) < 0
