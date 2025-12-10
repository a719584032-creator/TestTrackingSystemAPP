"""用于在不依赖外部库的情况下进行“类语义化”版本比较的辅助工具。"""
from __future__ import annotations

import re
from typing import List, Union

VersionToken = Union[int, str]
_SEPARATOR_RE = re.compile(r"[.\-+_]")


def _tokenize(value: str) -> List[VersionToken]:
    """将版本字符串拆分为由数字和字符串组成的 token 列表。"""

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
    """比较两个版本号：若 remote 更旧/相等/更新于 current，则返回 -1/0/1。"""

    left = _tokenize(current)
    right = _tokenize(remote)
    length = max(len(left), len(right))

    for idx in range(length):
        lv: VersionToken = left[idx] if idx < len(left) else 0
        rv: VersionToken = right[idx] if idx < len(right) else 0

        # 若两边都是数字，直接按数值比较
        if isinstance(lv, int) and isinstance(rv, int):
            if lv != rv:
                return -1 if lv < rv else 1
            continue

        if isinstance(lv, int) and isinstance(rv, str):
            # 正式版本号（纯数字）被视为比预发布标签（如 alpha、beta 等）更新
            return 1

        if isinstance(lv, str) and isinstance(rv, int):
            return -1

        # 两边都是字符串时，按字符串字典序比较
        if lv != rv:
            return -1 if str(lv) < str(rv) else 1

    return 0


def is_remote_newer(current: str, remote: str) -> bool:
    """若远程版本号 remote 表示的构建比 current 更新，则返回 True。"""

    if not current:
        return bool(remote)
    if not remote:
        return False
    return compare_versions(current, remote) < 0
