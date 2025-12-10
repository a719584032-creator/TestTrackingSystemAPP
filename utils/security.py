"""加密辅助工具"""
from __future__ import annotations

import base64
import datetime as dt
import getpass
import hashlib
import hmac
import platform
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _derive_key() -> bytes:
    """生成一个绑定到当前机器和用户的稳定密钥。"""

    user = getpass.getuser()
    node = platform.node()
    fingerprint = f"{user}:{node}".encode("utf-8")
    digest = hashlib.sha256(fingerprint).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_password(password: str) -> str:
    """返回 *password* 的加密表示。"""

    if not password:
        raise ValueError("password must not be empty")
    cipher = Fernet(_derive_key())
    token = cipher.encrypt(password.encode("utf-8"))
    return token.decode("ascii")


def decrypt_password(token: str) -> Optional[str]:
    """尝试从 *token* 中解密密码，若解密失败则返回 None。"""

    if not token:
        return None
    cipher = Fernet(_derive_key())
    try:
        return cipher.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def _parse_datetime_to_utc(value: str) -> dt.datetime:
    """将 *value* 解析为 ISO 格式的日期时间字符串并转换为 UTC 时间。"""

    trimmed = (value or "").strip()
    if not trimmed:
        raise ValueError("value must not be empty")

    iso_candidate = trimmed

    # 若以 Z 结尾，替换成 +00:00（ISO 标准的 UTC 表示）
    if iso_candidate.endswith("Z"):
        iso_candidate = iso_candidate[:-1] + "+00:00"

    # 尝试解析为 datetime 对象
    try:
        parsed = dt.datetime.fromisoformat(iso_candidate)
    except ValueError as exc:
        raise ValueError("invalid datetime format") from exc

    # 若无时区信息则视为 UTC，否则转换为 UTC
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        parsed = parsed.astimezone(dt.timezone.utc)

    return parsed


def encode_timestamp_token(value: str, secret: str) -> str:
    """将 *value* 编码成带有 *secret* 签名的时间戳 token。"""

    if not secret:
        raise ValueError("secret must not be empty")

    timestamp = _parse_datetime_to_utc(value)
    millis = int(timestamp.timestamp() * 1000)  # 转为毫秒时间戳
    timestamp_part = str(millis)

    # 使用 secret 对时间戳签名
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp_part.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # 组合 token：毫秒时间戳 + 签名
    token = f"{timestamp_part}.{signature}"

    # 对 token 进行 URL 安全的 Base64 编码
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii")
    return encoded
