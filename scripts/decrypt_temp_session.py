"""Utility script to inspect the encrypted monitoring session cache."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from config.settings import SETTINGS

# 注意：该密钥需与 ``Patvs_Fuction.ENCRYPTION_KEY`` 中的值保持一致。
DEFAULT_ENCRYPTION_KEY = b"JZfpG9N5K4PQoQMtImxPv80DS-D-WPXr9DN0eF7zhR4="


def _resolve_key(encoded_key: str | None) -> bytes:
    """Return the encryption key to use for decrypting the session file."""

    if encoded_key is None:
        return DEFAULT_ENCRYPTION_KEY
    return encoded_key.encode("utf-8")


def _load_file(path: Path) -> bytes:
    """Return the raw contents of *path*, raising ``FileNotFoundError`` if missing."""

    return path.expanduser().read_bytes()


def decrypt_payload(raw_payload: bytes, key: bytes) -> Any:
    """Decrypt *raw_payload* and deserialize the stored JSON payload."""

    fernet = Fernet(key)
    decrypted = fernet.decrypt(raw_payload)
    return json.loads(decrypted.decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Decrypt the encrypted temp_action_and_num.json cache to aid debugging."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=SETTINGS.monitoring_temp_file,
        help=(
            "Path to the encrypted temp_action_and_num.json file. "
            "Defaults to the standard monitoring temp file location."
        ),
    )
    parser.add_argument(
        "--key",
        dest="encoded_key",
        help="Override the base64 encoded Fernet key used for encryption.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the decrypted JSON data.",
    )

    args = parser.parse_args()

    try:
        raw_payload = _load_file(args.path)
    except FileNotFoundError:
        parser.error(f"Encrypted temp file not found: {args.path}")
        return 1

    key = _resolve_key(args.encoded_key)

    try:
        payload = decrypt_payload(raw_payload, key)
    except InvalidToken as exc:
        parser.error(
            "Failed to decrypt payload. Ensure the encryption key matches "
            "the one used by the monitoring service."
        )
        return 1

    if args.pretty:
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    else:
        text = json.dumps(payload, ensure_ascii=False)

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
