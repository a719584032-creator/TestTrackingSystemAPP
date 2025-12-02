"""TTS 配置管理"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .paths import get_patvs_root


APP_NAME = "Test Tracking System"
APP_VERSION = "2.0.2"
CONFIG_DIR = Path.home() / ".tts_client"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
PATVS_ROOT = get_patvs_root()
DEFAULT_MONITORING_ENCRYPTION_KEY = "JZfpG9N5K4PQoQMtImxPv80DS-D-WPXr9DN0eF7zhR4="


@dataclass(slots=True)
class ApiSettings:
    """API 设置"""

    # base_url: str = "https://patvs.lenovo.com/api" #测试环境
    base_url: str = "http://10.184.46.54:5173/api"  #开发环境
    #base_url: str = "http://172.28.79.247:5173/api"

    timeout: int = 60
    verify_ssl: bool = False


@dataclass(slots=True)
class OTASettings:
    """OTA 升级配置"""

    download_dir: Path = CONFIG_DIR / "downloads"

    def ensure_dirs(self) -> None:
        self.download_dir.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class CryptoSettings:
    """时间加密 key，与后端对应"""

    # result_time_secret: str = os.getenv("SECRET_KEY", "pro-secret-key") #测试环境加密
    result_time_secret: str = os.getenv("SECRET_KEY", "dev-secret-key")  #开发环境加密

@dataclass(slots=True)
class ClientSettings:
    """临时存储，客户端回放等文件"""

    api: ApiSettings = ApiSettings()
    ota: OTASettings = OTASettings()
    crypto: CryptoSettings = CryptoSettings()
    remember_me_file: Path = PATVS_ROOT / "credentials.json"  # 账号密码
    ui_state_file: Path = CONFIG_DIR / "ui_state.json"        # 记录用户选择内容
    window_state_file: Path = CONFIG_DIR / "window_state.json"  # 记录窗口样式
    monitoring_cache_file: Path = CONFIG_DIR / "monitoring_state.json"  # 监控动作进度记录（备份缓存）
    log_root: Path = PATVS_ROOT
    monitoring_temp_file: Path = PATVS_ROOT / "temp_action_and_num.json" # 监控动作进度记录
    monitoring_encryption_key: bytes = os.getenv(
        "MONITORING_ENCRYPTION_KEY", DEFAULT_MONITORING_ENCRYPTION_KEY   # 加密防止破解
    ).encode("utf-8")


SETTINGS = ClientSettings()
