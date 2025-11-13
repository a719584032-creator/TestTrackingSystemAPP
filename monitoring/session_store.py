"""Persistence helpers for PATVS monitoring state."""
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
    """Handles encrypted session persistence and crash reporting."""

    def __init__(self, temp_path: Path, cache_path: Path, encryption_key: bytes) -> None:
        self._temp_path = temp_path
        self._cache_path = cache_path
        self._fernet = Fernet(encryption_key)
        self._crash_report_path = cache_path.with_name("monitoring_crash.json")
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    def save(self, payload: dict[str, Any]) -> None:
        """Encrypt and persist the session payload to both temp/cache files."""

        try:
            serialized = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            self._logger.warning("序列化监控状态失败: %s", exc)
            return
        try:
            encrypted = self._fernet.encrypt(serialized.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - fernet 初始化异常无法轻易覆写
            self._logger.warning("加密监控状态失败: %s", exc)
            return

        for path in (self._temp_path, self._cache_path):
            try:
                self._atomic_write(path, encrypted)
            except OSError as exc:
                self._logger.warning("写入监控临时文件 %s 失败: %s", path, exc)

    def load(self, case_id: Any) -> Tuple[dict[str, Any] | None, bool]:
        """Load payload for the requested case, restoring from cache if needed."""

        payload = self._read(self._temp_path)
        restored_from_cache = False
        if payload is None:
            payload = self._read(self._cache_path)
            if payload is not None:
                restored_from_cache = True
                self._logger.warning(
                    "检测到 temp_action_and_num.json 缺失，尝试从备份缓存恢复监控进度。"
                )

        if not payload:
            return None, False

        stored_case_id = payload.get("case_id")
        if case_id is not None and stored_case_id not in (None, case_id):
            self._logger.warning(
                "备份缓存中的监控状态与当前用例不匹配，已忽略。(cached=%s, current=%s)",
                stored_case_id,
                case_id,
            )
            return None, restored_from_cache

        if restored_from_cache:
            # 将缓存副本回写到 temp 文件，以防再次崩溃时丢失
            self.save(payload)
        return payload, restored_from_cache

    def discard(self) -> None:
        """Remove both temp and cache files."""

        for path in (self._temp_path, self._cache_path):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                self._logger.warning("删除监控临时文件 %s 失败: %s", path, exc)

    # ------------------------------------------------------------------
    def record_crash(self, case_id: Any, payload: dict[str, Any], exc: BaseException) -> None:
        """Persist a small crash report for post-mortem diagnostics."""

        report = {
            "case_id": case_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "payload": payload,
        }
        try:
            self._atomic_write_text(self._crash_report_path, json.dumps(report, ensure_ascii=False, indent=2))
        except OSError as write_exc:
            self._logger.warning("写入崩溃报告失败: %s", write_exc)

    def read_crash_report(self) -> dict[str, Any] | None:
        """Return the last crash report without removing it."""

        try:
            raw = self._crash_report_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            self._logger.warning("读取崩溃报告失败: %s", exc)
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._logger.warning("崩溃报告文件损坏，已删除。")
            self._crash_report_path.unlink(missing_ok=True)
            return None

    def clear_crash_report(self) -> None:
        """Remove crash report after a successful run."""

        try:
            self._crash_report_path.unlink(missing_ok=True)
        except OSError as exc:
            self._logger.warning("删除崩溃报告失败: %s", exc)

    # ------------------------------------------------------------------
    def _read(self, path: Path) -> dict[str, Any] | None:
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
            self._logger.warning("解密监控临时文件 %s 失败: %s", path, exc)
            self._quarantine_file(path)
        except json.JSONDecodeError as exc:
            self._logger.warning("解析监控临时文件 %s 失败: %s", path, exc)
            self._quarantine_file(path)
        except Exception as exc:  # pragma: no cover - 避免解密库抛出未知异常
            self._logger.warning("处理监控临时文件 %s 失败: %s", path, exc)
            self._quarantine_file(path)
        return None

    def _atomic_write(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, dir=path.parent) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, path)

    def _atomic_write_text(self, path: Path, data: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=path.parent, encoding="utf-8"
        ) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, path)

    def _quarantine_file(self, path: Path) -> None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        quarantine = path.with_suffix(path.suffix + f".corrupted-{timestamp}")
        try:
            path.replace(quarantine)
            self._logger.warning("已将损坏的监控文件移动到 %s 便于排查。", quarantine)
        except OSError:
            self._logger.warning("监控文件 %s 无法隔离，尝试删除。", path)
            path.unlink(missing_ok=True)

