"""OTA 更新封装：负责检查、下载并安装更新包。"""
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

# 进度回调类型：第一个参数为已下载字节数，第二个为总大小（可能为 None）
ProgressCallback = Callable[[int, Optional[int]], None]

logger = logging.getLogger(__name__)


class UpdateManager:
    """
    更新管理器：负责协调
    - 检查是否有新版本
    - 下载更新包
    - 解压并准备更新文件
    - 调用外部脚本执行就地更新（覆盖当前程序）
    """

    def __init__(self, ota_client: OTAUpdater | None = None) -> None:
        # OTA 客户端，用于与服务器交互获取更新信息
        self._ota = ota_client or OTAUpdater()

        # 更新包下载根目录（从配置中获取）
        self._download_root = SETTINGS.ota.download_dir
        self._download_root.mkdir(parents=True, exist_ok=True)

        # 判断当前程序是否为“打包后运行”（如 PyInstaller 冻结模式）
        # 只有在冻结模式下，才支持就地替换执行文件
        self._supports_self_update = getattr(sys, "frozen", False)

        # 安装根目录（不同运行模式下路径不同）
        self._install_root = self._resolve_install_root()

        # 当前可执行文件名（例如 exe 名字）
        self._executable_name = Path(sys.executable).name

        # 更新日志文件路径
        self._log_file = self._download_root / "update.log"
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ 对外 API

    @property
    def supports_in_place_update(self) -> bool:
        """是否支持“原地更新”（直接替换当前程序所在目录的文件）"""
        return self._supports_self_update and self._install_root.exists()

    @property
    def install_root(self) -> Path:
        """返回当前程序的安装根目录（或源码根目录）"""
        return self._install_root

    def current_version(self) -> str:
        """返回本地当前版本号"""
        return APP_VERSION

    def check_for_updates(self) -> UpdateInfo | None:
        """向服务器查询是否有可用更新，返回更新信息或 None"""
        return self._ota.check()

    def is_update_newer(self, remote_version: str) -> bool:
        """对比远端版本号是否比本地版本新"""
        return is_remote_newer(APP_VERSION, remote_version)

    def stage_update(self, info: UpdateInfo, progress: ProgressCallback | None = None) -> Path:
        """
        下载并解压更新包，返回“准备好的更新文件所在目录”。

        :param info: 更新信息（包含版本号、下载链接、校验信息等）
        :param progress: 下载进度回调，可选
        """
        archive = self._download_archive(info, progress)
        return self._extract_archive(archive, info.version)

    def launch_installer(self, staged_dir: Path, current_pid: int) -> None:
        """
        启动外部更新脚本，在当前进程退出后替换安装目录并重启新版本。

        :param staged_dir: 已解压好的更新文件目录
        :param current_pid: 当前正在运行的进程 PID，用于脚本等待本进程退出
        """
        if not self.supports_in_place_update:
            # 源码运行时无法就地替换，只能提示用户手动更新
            raise UpdateError("当前运行于源码环境，无法自动替换文件。")

        command = self._build_install_command(staged_dir, current_pid)
        logger.info("启动外部更新脚本: %s", command)
        try:
            # 使用 Popen 启动外部更新脚本，不阻塞当前进程
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=os.name != "nt",
            )
        except OSError as exc:  # pragma: no cover - 平台相关
            raise UpdateError(f"无法启动更新脚本: {exc}") from exc

    # ------------------------------------------------------------------ 内部实现

    def _download_archive(self, info: UpdateInfo, progress: ProgressCallback | None) -> Path:
        """
        下载更新 zip 包到本地目录，并做可选的 SHA-256 校验。

        :param info: 更新信息，包含 download_url / checksum 等
        :param progress: 下载进度回调
        :return: 下载完成的 zip 包路径
        """
        if not info.download_url:
            raise UpdateError("更新清单缺少下载链接。")

        # 目标 zip 路径，如：<download_root>/1.2.3.zip
        target = self._download_root / f"{info.version}.zip"
        # 临时文件路径，下载完成后再原子替换为 target
        temp = target.with_suffix(".part")

        # --- 发起 HTTP 流式下载 ---
        try:
            response = requests.get(info.download_url, stream=True, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - 网络依赖
            # 网络错误统一包装为 NetworkError，方便上层区分
            raise NetworkError(str(exc)) from exc

        total = int(response.headers.get("Content-Length", 0))  # 内容总长度（可能为 0）
        downloaded = 0
        # 如果提供了 checksum，则边下载边计算 SHA-256
        digest = hashlib.sha256() if info.checksum else None

        try:
            with temp.open("wb") as fp:
                # 分块下载，避免一次性占用过多内存
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    fp.write(chunk)
                    downloaded += len(chunk)

                    if digest:
                        digest.update(chunk)

                    # 有进度回调就上报当前进度
                    if progress:
                        progress(downloaded, total or None)

            # 下载完成后，使用 replace 原子替换最终文件
            temp.replace(target)
        except OSError as exc:
            raise UpdateError(f"保存更新包失败: {exc}") from exc

        # --- 可选的 SHA-256 校验 ---
        if digest:
            checksum = digest.hexdigest()
            if checksum.lower() != info.checksum.lower():
                # 校验失败，删除下载文件并抛出异常
                target.unlink(missing_ok=True)
                raise UpdateError("下载文件校验失败，请稍后重试。")

        return target

    def _extract_archive(self, archive: Path, version: str) -> Path:
        """
        解压更新包到 staging 目录并做路径安全检查，返回真正的负载根目录。

        :param archive: zip 更新包路径
        :param version: 版本号，用于生成 staging 目录名
        """
        staging_dir = self._download_root / f"{version}_staging"
        # 若已存在旧的 staging 目录，先清理
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(archive) as zf:
                root = staging_dir.resolve()

                # --- 路径安全检查：防止 zip 内含有 ../../ 之类的路径穿越 ---
                for info in zf.infolist():
                    dest = root / info.filename
                    resolved = dest.resolve()
                    if not str(resolved).startswith(str(root)):
                        raise UpdateError(f"更新包包含非法路径: {info.filename}")

                # 安全检查通过后再真正解压
                zf.extractall(staging_dir)

        except zipfile.BadZipFile as exc:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise UpdateError("更新包已损坏，请重新下载。") from exc
        except OSError as exc:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise UpdateError(f"解压更新包失败: {exc}") from exc

        # 部分压缩包内部可能再套一层目录，这里自动选择真正的根目录
        payload_root = self._select_payload_root(staging_dir)
        logger.info("更新包已解压至: %s", payload_root)
        return payload_root

    def _select_payload_root(self, staging_dir: Path) -> Path:
        """
        选择更新负载的根目录：
        - 如果解压后只有一个子目录，则返回该子目录
        - 否则返回 staging_dir 本身
        """
        candidates = [
            path for path in staging_dir.iterdir() if path.is_dir()
        ]
        if len(candidates) == 1:
            return candidates[0]
        return staging_dir

    def _resolve_install_root(self) -> Path:
        """
        解析当前程序的“安装根目录”：
        - 冻结模式（打包成 exe）：返回可执行文件所在目录
        - 源码运行：返回仓库根目录（当前文件的上上级目录）
        """
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        # 源码运行模式：退回到仓库根目录
        return Path(__file__).resolve().parents[1]

    def _build_install_command(self, staged_dir: Path, current_pid: int) -> list[str]:
        """
        构建外部更新脚本的启动命令（Windows / POSIX 不同）。

        :param staged_dir: 已解压好的更新目录
        :param current_pid: 当前进程 PID（脚本会等待其退出）
        :return: 用于 Popen 的命令行列表
        """
        log_path = self._log_file
        log_path.touch(exist_ok=True)

        target_dir = self._install_root
        exe_path = target_dir / self._executable_name

        if os.name == "nt":
            # Windows 下写入一个 PowerShell 更新脚本，并用 powershell 调用
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

        # POSIX（Linux/macOS）下写入一个 shell 脚本，并用 bash 调用
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
        """
        生成 Windows 专用的 PowerShell 更新脚本，负责：
        - 等待旧进程退出
        - 备份旧目录
        - 拷贝新文件
        - 启动新版本客户端
        - 清理临时目录

        同时做了两点鲁棒性处理：
        - 自动下钻：如果 Source 目录下只有一个子目录，则进入该子目录
        - 启动新程序时只使用可执行文件名，在 Target 下拼路径，避免路径不一致
        """
        script_path = self._download_root / "install_update.ps1"
        content = r"""
param(
    [string]$Source,
    [string]$Target,
    [string]$Executable,
    [int]$TargetProcessId,
    [string]$LogFile
)

$ErrorActionPreference = "Stop"

function Write-Log($Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "$stamp`t$Message"
}

function Wait-ForProcess($ProcessId) {
    if ($ProcessId -le 0) { return }
    while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Start-Sleep -Seconds 1
    }
}

function Resolve-PayloadPath([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Source path '$Path' does not exist."
    }
    if (Test-Path -LiteralPath $Path -PathType Container) {
        $entries = Get-ChildItem -LiteralPath $Path
        if ($entries.Count -eq 1 -and $entries[0].PSIsContainer) {
            return $entries[0].FullName
        }
    }
    return $Path
}

function Invoke-WithRetry {
    param(
        [scriptblock]$Action,
        [string]$Description,
        [int]$Retries = 30,
        [int]$DelaySeconds = 1
    )

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            & $Action
            return
        } catch {
            if ($attempt -ge $Retries) {
                throw
            }
            Write-Log ("$Description failed (attempt $attempt): " + $_.Exception.Message)
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

$sourceRoot = $Source

try {
    $payloadSource = Resolve-PayloadPath -Path $sourceRoot
    Write-Log "Waiting for process $TargetProcessId to exit"
    Wait-ForProcess $TargetProcessId
    Write-Log "Copying update files"

    $targetParent = Split-Path -Parent $Target
    $targetName = Split-Path -Leaf $Target
    $backup = Join-Path $targetParent ($targetName + ".bak")

    Invoke-WithRetry -Description "Remove old backup" -Action {
        if (Test-Path -LiteralPath $backup) {
            Remove-Item -LiteralPath $backup -Recurse -Force
        }
    }

    Invoke-WithRetry -Description "Rotate existing installation" -Action {
        if (Test-Path -LiteralPath $Target) {
            Rename-Item -LiteralPath $Target -NewName ($targetName + ".bak")
        }
    }

    Invoke-WithRetry -Description "Create target directory" -Action {
        New-Item -ItemType Directory -Path $Target -Force | Out-Null
    }

    Invoke-WithRetry -Description "Copy payload" -Action {
        Copy-Item -Path (Join-Path $payloadSource '*') -Destination $Target -Recurse -Force
    }

    Invoke-WithRetry -Description "Remove backup" -Action {
        if (Test-Path -LiteralPath $backup) {
            Remove-Item -LiteralPath $backup -Recurse -Force
        }
    }

    $exeName = Split-Path -Leaf $Executable
    $exePathInTarget = Join-Path $Target $exeName

    Write-Log "Launching updated client: $exePathInTarget"
    Start-Process -FilePath $exePathInTarget -WorkingDirectory $Target
} catch {
    Write-Log ("Update failed: " + $_.Exception.Message)
    throw
} finally {
    try {
        if (Test-Path -LiteralPath $sourceRoot) {
            Remove-Item -LiteralPath $sourceRoot -Recurse -Force
        }
    } catch {
        Write-Log ("Cleanup failed: " + $_.Exception.Message)
    }
}
"""
        script_path.write_text(content.strip(), encoding="utf-8")
        return script_path

    def _write_posix_script(self) -> Path:
        """
        生成 POSIX（Linux/macOS）环境下的更新 shell 脚本，负责：
        - 等待旧进程退出
        - 备份旧目录
        - 拷贝新文件
        - 启动新版本客户端
        - 清理临时目录

        同时做了两点鲁棒性处理：
        - 自动下钻：如果 SOURCE 下只有一个子目录，则进入该子目录
        - 启动新程序时在 TARGET 下拼接可执行文件名
        """
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

log "Waiting for process $PID to exit"
if [ -n "$PID" ] && [ "$PID" -gt 0 ] 2>/dev/null; then
    while kill -0 "$PID" 2>/dev/null; do
        sleep 1
    done
fi

# Auto descend: if SOURCE has exactly one child directory, use it
if [ -d "$SOURCE" ]; then
    subdirs=$(find "$SOURCE" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
    if [ "$subdirs" -eq 1 ]; then
        SOURCE=$(find "$SOURCE" -mindepth 1 -maxdepth 1 -type d)
    fi
fi

log "Copying update files"
BACKUP="${TARGET}.bak"
rm -rf "$BACKUP"
if [ -d "$TARGET" ]; then
    mv "$TARGET" "$BACKUP"
fi

mkdir -p "$TARGET"
cp -a "$SOURCE"/. "$TARGET"/
rm -rf "$BACKUP"

# Build executable path inside the target directory
EXEC_NAME=$(basename "$EXECUTABLE")
EXEC_IN_TARGET="$TARGET/$EXEC_NAME"

log "Launching updated client: $EXEC_IN_TARGET"
nohup "$EXEC_IN_TARGET" >/dev/null 2>&1 &
rm -rf "$SOURCE"
"""
        script_path.write_text(content.strip() + "\n", encoding="utf-8")
        # 增加执行权限（chmod +x）
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
        return script_path
