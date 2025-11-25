"""加密保存登录账号密码"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config.settings import SETTINGS
from utils.security import decrypt_password, encrypt_password
from utils.storage import load_json, save_json


@dataclass(slots=True)
class RememberMePayload:
    """记住密码功能"""

    # 明文账号，密码加密存储
    username: str
    password_cipher: str

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "RememberMePayload":
        """
        从字典数据构造 RememberMePayload 实例。

        - 会从 payload 中读取 username 和 password/password_cipher 字段
        - 若缺失必要字段，则抛出 ValueError
        """
        username = payload.get("username")
        # 兼容新老字段：password 或 password_cipher
        cipher = payload.get("password") or payload.get("password_cipher")
        if not username or not cipher:
            raise ValueError("missing username/password")
        return cls(username=username, password_cipher=cipher)

    def to_dict(self) -> dict[str, str]:
        """
        将当前实例转换为可写入 JSON 的字典结构。
        """
        return {"username": self.username, "password": self.password_cipher}

    def decrypt(self) -> "RememberedCredentials":
        """
        将当前对象中的密码密文解密为明文密码，
        并返回包含明文凭据的 RememberedCredentials。
        """
        # 使用项目中封装的解密函数，对存储的密文进行解密
        password = decrypt_password(self.password_cipher)
        if password is None:
            raise ValueError("无法解密存储的密码")
        # 返回明文用户名和密码的凭据对象
        return RememberedCredentials(username=self.username, password=password)


@dataclass(slots=True)
class RememberedCredentials:
    """用于向调用方返回的明文登录凭据（仅存在于内存中）。"""

    username: str
    password: str


class AuthStore:
    """负责读取和写入“记住我”凭据的存储层封装。"""

    def __init__(self) -> None:
        # 从全局配置中读取“记住我”文件的路径
        self._path = SETTINGS.remember_me_file

    def load(self) -> Optional[RememberedCredentials]:
        """
        从磁盘加载已保存的“记住我”信息，并返回明文凭据。
        若不存在或数据无效，则返回 None。
        """
        # 从 JSON 文件中加载数据
        payload = load_json(self._path)
        if not payload:
            return None
        try:
            # 先将字典解析为 RememberMePayload，做字段校验
            stored = RememberMePayload.from_dict(payload)
            # 再将内部密文解密为明文凭据并返回
            return stored.decrypt()
        except ValueError:
            # 若字段缺失或解密失败，直接清理文件
            self.clear()
            return None

    def save(self, credentials: RememberedCredentials) -> None:
        """
        将明文凭据加密后写入磁盘，用于“记住我”功能。
        """
        # 仅对密码进行加密，用户名可明文存储
        cipher = encrypt_password(credentials.password)
        # 构造持久化数据结构
        payload = RememberMePayload(username=credentials.username, password_cipher=cipher)
        # 将字典形式写入 JSON 文件
        save_json(self._path, payload.to_dict())

    def clear(self) -> None:
        """
        清除磁盘上的“记住我”数据文件。
        通常在用户取消记住我或本地数据无效时调用。
        """
        # 若文件存在，则删除该文件
        if self._path.exists():
            self._path.unlink()
