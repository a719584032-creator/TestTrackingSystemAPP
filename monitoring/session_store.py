"""PATVS 监控状态的持久化辅助工具。"""
from __future__ import annotations

import datetime
import json
import logging
import os
import tempfile
import traceback
from pathlib import Path
from typing import Any, Tuple

from cryptography.fernet import Fernet, InvalidToken


logger = logging.getLogger(__name__)


class SessionStateStore:
    """处理会话状态的加密持久化与崩溃报告。

    主要职责：
    - 将监控会话状态加密后写入临时文件与缓存文件（双写，提升可靠性）
    - 从临时文件读取失败时，从缓存恢复并回写临时文件（自愈）
    - 记录崩溃时的上下文信息，方便事后排查
    """

    def __init__(self, temp_path: Path, cache_path: Path, encryption_key: bytes) -> None:
        # temp_path: 会话状态的临时文件路径（优先读取）
        self._temp_path = temp_path
        # cache_path: 备份缓存文件路径（用于恢复）
        self._cache_path = cache_path
        # Fernet 对称加密实例，负责加解密
        self._fernet = Fernet(encryption_key)
        # 崩溃报告固定写到缓存同目录下
        self._crash_report_path = cache_path.with_name("monitoring_crash.json")
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    def save(self, payload: dict[str, Any]) -> None:
        """加密并持久化会话状态到临时文件和缓存文件。

        设计要点：
        - 先将 payload 序列化为 JSON，再加密，最后分别原子写入两个文件
        - 任一文件写失败只记录日志，不影响另一个文件
        """

        try:
            # ensure_ascii=False 保留中文，避免转义成 \uXXXX
            serialized = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            self._logger.warning("序列化监控状态失败: %s", exc)
            return
        try:
            encrypted = self._fernet.encrypt(serialized.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - fernet 初始化异常无法轻易覆写
            # 一般是密钥非法或 Fernet 内部异常
            self._logger.warning("加密监控状态失败: %s", exc)
            return

        # 同时写入临时和缓存，形成主/备两份数据
        for path in (self._temp_path, self._cache_path):
            try:
                self._atomic_write(path, encrypted)
            except OSError as exc:
                self._logger.warning("写入监控临时文件 %s 失败: %s", path, exc)

    def load(self, case_id: Any) -> Tuple[dict[str, Any] | None, bool]:
        """加载指定用例的会话状态，如有需要从缓存恢复。

        参数：
            case_id: 当前正在处理的用例 ID，用于避免误读其它用例的缓存

        返回：
            (payload, restored_from_cache)
            - payload: 读取到的会话状态，None 表示无可用状态
            - restored_from_cache: 是否是从缓存文件恢复的
        """

        # 优先从临时文件读取
        payload = self._read(self._temp_path)
        restored_from_cache = False

        # 临时文件读取失败/不存在时，从缓存尝试恢复
        if payload is None:
            payload = self._read(self._cache_path)
            if payload is not None:
                restored_from_cache = True
                self._logger.warning(
                    "检测到 temp_action_and_num.json 缺失，尝试从备份缓存恢复监控进度。"
                )

        if not payload:
            # None 或 空 dict 都视为无有效状态
            return None, False

        # case_id 校验：防止误用上一条用例的缓存
        stored_case_id = payload.get("case_id")
        if case_id is not None and stored_case_id not in (None, case_id):
            self._logger.warning(
                "备份缓存中的监控状态与当前用例不匹配，已忽略。(cached=%s, current=%s)",
                stored_case_id,
                case_id,
            )
            return None, restored_from_cache

        if restored_from_cache:
            # 如果是从缓存成功恢复，回写一份到 temp 文件，提高后续鲁棒性
            self.save(payload)
        return payload, restored_from_cache

    def discard(self) -> None:
        """删除临时和缓存文件，用于监控流程顺利完成后的收尾清理。"""

        for path in (self._temp_path, self._cache_path):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                self._logger.warning("删除监控临时文件 %s 失败: %s", path, exc)

    # ------------------------------------------------------------------
    def record_crash(self, case_id: Any, payload: dict[str, Any], exc: BaseException) -> None:
        """记录一次崩溃信息，方便事后排查。

        注意：
        - 崩溃报告为明文 JSON，不再加密
        - payload 会被直接写入，有隐私/敏感字段时建议在调用前做脱敏/裁剪
        """

        report = {
            "case_id": case_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",  # 统一使用 UTC 时间
            "message": str(exc),
            "traceback": traceback.format_exc(),  # 完整堆栈信息
            "payload": payload,
        }
        try:
            self._atomic_write_text(
                self._crash_report_path,
                json.dumps(report, ensure_ascii=False, indent=2),
            )
        except OSError as write_exc:
            self._logger.warning("写入崩溃报告失败: %s", write_exc)

    def read_crash_report(self) -> dict[str, Any] | None:
        """读取最近一次崩溃报告，但不删除文件。"""

        try:
            raw = self._crash_report_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            # 没有崩溃报告视为正常情况
            return None
        except OSError as exc:
            self._logger.warning("读取崩溃报告失败: %s", exc)
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 文件损坏：日志提示并删除，避免下次继续报错
            self._logger.warning("崩溃报告文件损坏，已删除。")
            self._crash_report_path.unlink(missing_ok=True)
            return None

    def clear_crash_report(self) -> None:
        """在成功运行一次后清理崩溃报告。"""

        try:
            self._crash_report_path.unlink(missing_ok=True)
        except OSError as exc:
            self._logger.warning("删除崩溃报告失败: %s", exc)

    # ------------------------------------------------------------------
    def _read(self, path: Path) -> dict[str, Any] | None:
        """从指定路径读取加密文件并解密为 dict。

        读取过程包含以下步骤：
        1. 读原始字节
        2. 使用 Fernet 解密
        3. 将解密后的 JSON 文本反序列化为 dict
        若遇到解密失败/JSON 解析失败，会将该文件隔离到 *.corrupted-<timestamp>
        """

        try:
            encrypted = path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            self._logger.warning("读取监控临时文件 %s 失败: %s", path, exc)
            return None
        if not encrypted:
            self._logger.warning("监控临时文件 %s 内容为空，将忽略该文件。", path)
            return None

        try:
            decrypted = self._fernet.decrypt(encrypted)
            return json.loads(decrypted.decode("utf-8"))
        except InvalidToken as exc:
            # 密钥不匹配或文件被篡改/损坏
            self._logger.warning("解密监控临时文件 %s 失败: %s", path, exc)
            self._quarantine_file(path)
        except json.JSONDecodeError as exc:
            # 解密成功但不是合法 JSON
            self._logger.warning("解析监控临时文件 %s 失败: %s", path, exc)
            self._quarantine_file(path)
        except Exception as exc:  # pragma: no cover - 避免解密库抛出未知异常
            # 兜底异常处理，避免影响调用方逻辑
            self._logger.warning("处理监控临时文件 %s 失败: %s", path, exc)
            self._quarantine_file(path)
        return None

    def _atomic_write(self, path: Path, data: bytes) -> None:
        """使用临时文件 + os.replace 实现二进制内容的原子写入。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, dir=path.parent) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())  # 强制刷盘，尽量保证数据落到磁盘
        # os.replace 在大多数平台上是原子操作，避免读到半写入文件
        os.replace(tmp.name, path)

    def _atomic_write_text(self, path: Path, data: str) -> None:
        """使用临时文件 + os.replace 实现文本内容的原子写入。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=path.parent, encoding="utf-8"
        ) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, path)

    def _quarantine_file(self, path: Path) -> None:
        """将损坏/无法解析的监控文件隔离到新的后缀文件中。

        隔离策略：
        - 将原文件重命名为 *.corrupted-YYYYMMDDHHMMSS
        - 若重命名失败，则尝试直接删除，避免后续继续读到坏数据
        """

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        quarantine = path.with_suffix(path.suffix + f".corrupted-{timestamp}")
        try:
            path.replace(quarantine)
            self._logger.warning("已将损坏的监控文件移动到 %s 便于排查。", quarantine)
        except OSError:
            self._logger.warning("监控文件 %s 无法隔离，尝试删除。", path)
            path.unlink(missing_ok=True)
