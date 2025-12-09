"""通用 Fernet 加密 JSON 文件解密脚本"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def _resolve_key(encoded_key: str) -> bytes:
    """
    将 base64 字符串密钥转换为 Fernet 所需的 bytes 密钥。
    encoded_key 一般是类似 'p5yN5...==' 这种字符串。
    """
    return encoded_key.encode("utf-8")


def _load_file(path: Path) -> bytes:
    """
    读取指定路径的文件内容（以字节形式返回）。
    如果文件不存在，会抛出 FileNotFoundError。
    """
    return path.expanduser().read_bytes()


def decrypt_payload(raw_payload: bytes, key: bytes) -> Any:
    """
    使用 Fernet 密钥解密原始字节流，并反序列化为 Python 对象（通常是 dict / list）。
    """
    fernet = Fernet(key)
    decrypted = fernet.decrypt(raw_payload)
    return json.loads(decrypted.decode("utf-8"))


def decrypt_file_to_text(
    file_path: str | Path,
    encoded_key: str,
    pretty: bool = True,
) -> str:
    """
    解密指定文件，并返回 JSON 字符串。

    :param file_path: 加密文件路径（字符串或 Path 均可）
    :param encoded_key: base64 字符串形式 Fernet 密钥
    :param pretty: 是否格式化输出（带缩进）
    :return: 解密后的 JSON 文本字符串
    :raises FileNotFoundError: 文件不存在
    :raises InvalidToken: 密钥不正确或文件内容被破坏
    """
    path = Path(file_path)
    raw = _load_file(path)
    key = _resolve_key(encoded_key)
    payload = decrypt_payload(raw, key)

    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(payload, ensure_ascii=False)


def main(file_path: str, encoded_key: str) -> str:
    """
    封装一层 main，接收文件路径和密钥，返回解密后的字符串。
    你可以选择在这里捕获异常并打印友好信息，也可以直接往外抛。
    """
    # 这里不做异常处理，让调用方决定如何处理错误
    return decrypt_file_to_text(file_path, encoded_key, pretty=True)


if __name__ == "__main__":
    # 在这里自定义你的文件路径和密钥
    file_path = r"C:\PATVS\instances\slot-1\patvs\temp_action_and_num.json"       # 比如：r"D:\logs\temp_action_and_num.json.enc"
    encoded_key = "JZfpG9N5K4PQoQMtImxPv80DS-D-WPXr9DN0eF7zhR4="        # 你的 base64 Fernet 密钥字符串

    try:
        result = main(file_path, encoded_key)
        print(result)
    except FileNotFoundError:
        print(f"❌ 文件不存在: {file_path}")
    except InvalidToken:
        print("❌ 解密失败：密钥不正确或文件内容遭到破坏")
    except Exception as exc:
        print(f"❌ 发生未知错误: {exc}")
