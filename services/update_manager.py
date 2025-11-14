"""High-level helpers to download and install OTA packages."""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable, Optional

import requests

from config.settings import APP_VERSION, SETTINGS
from services.ota import OTAUpdater, UpdateInfo
from utils.exceptions import NetworkError, UpdateError
from utils.versioning import is_remote_newer

ProgressCallback = Callable[[int, Optional[int]], None]

logger = logging.getLogger(__name__)


class UpdateManager:
    """Coordinates update checks, downloads, and staged installs."""

    def __init__(self, ota_client: OTAUpdater | None = None) -> None:
        self._ota = ota_client or OTAUpdater()
        self._download_root = SETTINGS.ota.download_dir
        self._download_root.mkdir(parents=True, exist_ok=True)
        self._supports_self_update = getattr(sys, "frozen", False)
        self._install_root = self._resolve_install_root()
        self._executable_name = Path(sys.executable).name
        self._log_file = self._download_root / "update.log"
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ API
    @property
    def supports_in_place_update(self) -> bool:
        return self._supports_self_update and self._install_root.exists()

    @property
    def install_root(self) -> Path:
        return self._install_root

    def current_version(self) -> str:
        return APP_VERSION

    def check_for_updates(self) -> UpdateInfo | None:
        return self._ota.check()

    def is_update_newer(self, remote_version: str) -> bool:
        return is_remote_newer(APP_VERSION, remote_version)

    def stage_update(self, info: UpdateInfo, progress: ProgressCallback | None = None) -> Path:
        archive = self._download_archive(info, progress)
        return self._extract_archive(archive, info.version)

    def launch_installer(self, staged_dir: Path, current_pid: int) -> None:
        if not self.supports_in_place_update:
            raise UpdateError("当前运行于源码环境，无法自动替换文件。")
        command = self._build_install_command(staged_dir, current_pid)
        logger.info("启动外部更新脚本: %s", command)
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=os.name != "nt",
            )
        except OSError as exc:  # pragma: no cover - 平台相关
            raise UpdateError(f"无法启动更新脚本: {exc}") from exc

    # ------------------------------------------------------------------
    def _download_archive(self, info: UpdateInfo, progress: ProgressCallback | None) -> Path:
        if not info.download_url:
            raise UpdateError("更新清单缺少下载链接。")
        target = self._download_root / f"{info.version}.zip"
        temp = target.with_suffix(".part")
        try:
            response = requests.get(info.download_url, stream=True, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - 网络依赖
            raise NetworkError(str(exc)) from exc

        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        digest = hashlib.sha256() if info.checksum else None

        try:
            with temp.open("wb") as fp:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    fp.write(chunk)
                    downloaded += len(chunk)
                    if digest:
                        digest.update(chunk)
                    if progress:
                        progress(downloaded, total or None)
            temp.replace(target)
        except OSError as exc:
            raise UpdateError(f"保存更新包失败: {exc}") from exc

        if digest:
            checksum = digest.hexdigest()
            if checksum.lower() != info.checksum.lower():
                target.unlink(missing_ok=True)
                raise UpdateError("下载文件校验失败，请稍后重试。")
        return target

    def _extract_archive(self, archive: Path, version: str) -> Path:
        staging_dir = self._download_root / f"{version}_staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(archive) as zf:
                root = staging_dir.resolve()
                for info in zf.infolist():
                    dest = root / info.filename
                    resolved = dest.resolve()
                    if not str(resolved).startswith(str(root)):
                        raise UpdateError(f"更新包包含非法路径: {info.filename}")
                zf.extractall(staging_dir)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise UpdateError("更新包已损坏，请重新下载。") from exc
        except OSError as exc:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise UpdateError(f"解压更新包失败: {exc}") from exc
        payload_root = self._select_payload_root(staging_dir)
        logger.info("更新包已解压至: %s", payload_root)
        return payload_root

    def _select_payload_root(self, staging_dir: Path) -> Path:
        candidates = [
            path for path in staging_dir.iterdir() if path.is_dir()
        ]
        if len(candidates) == 1:
            return candidates[0]
        return staging_dir

    def _resolve_install_root(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        # 源码运行模式：退回到仓库根目录
        return Path(__file__).resolve().parents[1]

    def _build_install_command(self, staged_dir: Path, current_pid: int) -> list[str]:
        log_path = self._log_file
        log_path.touch(exist_ok=True)
        target_dir = self._install_root
        exe_path = target_dir / self._executable_name
        if os.name == "nt":
            script_path = self._write_windows_script()
            return [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                str(staged_dir),
                str(target_dir),
                str(exe_path),
                str(current_pid),
                str(log_path),
            ]
        script_path = self._write_posix_script()
        return [
            "bash",
            str(script_path),
            str(staged_dir),
            str(target_dir),
            str(exe_path),
            str(current_pid),
            str(log_path),
        ]

    def _write_windows_script(self) -> Path:
        script_path = self._download_root / "install_update.ps1"
        content = r"""
param(
    [string]$Source,
    [string]$Target,
    [string]$Executable,
    [int]$Pid,
    [string]$LogFile
)

$ErrorActionPreference = "Stop"

function Write-Log($Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "$stamp`t$Message"
}

function Wait-ForProcess($Pid) {
    if ($Pid -le 0) { return }
    while (Get-Process -Id $Pid -ErrorAction SilentlyContinue) {
        Start-Sleep -Seconds 1
    }
}

try {
    Write-Log "等待进程 $Pid 退出"
    Wait-ForProcess $Pid
    Write-Log "开始复制更新文件"

    $targetParent = Split-Path -Parent $Target
    $targetName = Split-Path -Leaf $Target
    $backup = Join-Path $targetParent ($targetName + ".bak")

    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }

    if (Test-Path -LiteralPath $Target) {
        Rename-Item -LiteralPath $Target -NewName ($targetName + ".bak")
    }

    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    Copy-Item -Path (Join-Path $Source '*') -Destination $Target -Recurse -Force

    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }

    Write-Log "启动新版客户端"
    Start-Process -FilePath $Executable -WorkingDirectory $Target
} catch {
    Write-Log ("更新失败: " + $_.Exception.Message)
    throw
} finally {
    try {
        if (Test-Path -LiteralPath $Source) {
            Remove-Item -LiteralPath $Source -Recurse -Force
        }
    } catch {
        Write-Log ("清理失败: " + $_.Exception.Message)
    }
}
"""
        script_path.write_text(content.strip(), encoding="utf-8")
        return script_path

    def _write_posix_script(self) -> Path:
        script_path = self._download_root / "install_update.sh"
        content = r"""#!/bin/sh
set -e
SOURCE="$1"
TARGET="$2"
EXECUTABLE="$3"
PID="$4"
LOGFILE="$5"

log() {
    printf '%s\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOGFILE"
}

log "等待进程 $PID 退出"
if [ -n "$PID" ] && [ "$PID" -gt 0 ] 2>/dev/null; then
    while kill -0 "$PID" 2>/dev/null; do
        sleep 1
    done
fi

log "开始复制更新文件"
BACKUP="${TARGET}.bak"
rm -rf "$BACKUP"
if [ -d "$TARGET" ]; then
    mv "$TARGET" "$BACKUP"
fi

mkdir -p "$TARGET"
cp -a "$SOURCE"/. "$TARGET"/
rm -rf "$BACKUP"

log "启动新版客户端"
nohup "$EXECUTABLE" >/dev/null 2>&1 &
rm -rf "$SOURCE"
"""
        script_path.write_text(content.strip() + "\n", encoding="utf-8")
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
        return script_path
