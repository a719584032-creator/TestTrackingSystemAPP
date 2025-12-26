# TTS 测试执行客户端

Test Tracking System（TTS）桌面客户端，基于 **Python 3.10+** 与 **PyQt5** 构建，专注于计划调度、用例执行与硬件监控。

## 技术栈
- Python 3.10 或更高版本
- PyQt5（桌面 UI）
- Requests（HTTP 通信）
- Cryptography（本地凭据加密与监控状态持久化）
- PyInstaller（桌面应用打包）
- 监控相关（Windows）
  - pywin32（Win32 API：事件日志、设备通知、会话锁定、电源与窗口消息）
  - WMI + pythoncom（显示/HDMI 相关状态采集）
  - psutil（电源、设备状态探测）
  - pynput（键盘/鼠标事件采集）
  - pycaw + comtypes（音量与音频端点控制/监听）
  - screen-brightness-control（屏幕亮度检测/设置）
  - opencv-python（摄像头与画面采集） 
  - mutagen（录音文件解析与校验）

## 目录总览
```
TestTrackingSystemAPP/
├── run.py                 # 直接启动客户端的入口脚本
├── build.py               # PyInstaller 打包工具
├── config/                # 配置与路径管理
├── services/              # 与后端/本地存储交互的服务层
├── models/                # 领域模型定义
├── monitoring/            # Qt 适配层 + 监控脚本
│   └── actions/            # 具体的监控动作实现
├── ui/                    # PyQt5 界面与状态持久化
├── widgets/               # 预留的复用控件目录
├── utils/                 # 日志、异常、存储等通用工具
├── resources/             # 静态资源目录
├── scripts/               # 辅助脚本
├── logs/                  # 运行时日志输出目录（默认空）
├── data/                  # 运行时数据缓存目录（默认空）
├── requirements.txt       # 运行所需的三方依赖
└── pyproject.toml         # 包元数据与命令行入口
```

## 核心模块说明
| 模块 | 说明 |
| --- | --- |
| `run.py` | 命令行入口，包装并调用 `ui.application.main`，供源码运行与 `tts-client` 脚本复用。 |
| `ui/application.py`、`ui/login_dialog.py`、`ui/main_window.py` | 负责 Qt 应用装配与 UI 交互：登录流程、主界面、监控日志、结果提交流程等。 |
| `ui/state.py` | 处理窗口几何状态的持久化，读取/写入 JSON。 |
| `services/api_client.py` | 封装与 TTS 后端的 HTTP 交互：登录、部门/项目/计划查询、执行结果提交等。 |
| `services/auth.py` | 记住密码功能，使用对称加密保存凭据，并在需要时恢复/清理。 |
| `services/ota.py` | OTA 更新检查器，请求远程 manifest 并返回版本信息。 |
| `config/settings.py`、`config/paths.py` | 定义客户端运行参数（API、OTA、日志、窗口状态等）并根据平台生成默认目录。 |
| `models/domain.py` | 将后端 JSON 转换为 Python 数据类，覆盖部门、项目、计划、用例、执行结果等核心实体。 |
| `monitoring/manager.py`、`monitoring/parser.py` | Qt 适配层，解析监控关键字并调用遗留的硬件监控实现。 |
| `monitoring/actions/*` | 具体监控动作实现（电源/USB/显示/摄像头/音量/键鼠等）。 |
| `monitoring/session_store.py` | 监控执行态与证据缓存的恢复与持久化。 |
| `utils/logging.py`、`utils/storage.py`、`utils/security.py`、`utils/exceptions.py` | 提供日志配置、JSON 读写、凭据加解密、异常定义等通用能力。 |
| `resources/__init__.py` | 指向静态资源目录的路径常量，供 UI 或打包脚本引用。 |
| `build.py` | PyInstaller 打包脚本，生成独立可执行文件。 |

## 安装与运行
1. **准备环境**
   - 安装 Python 3.10 或更高版本（`pyproject.toml` 中定义了 `requires-python = ">=3.10"`）。
   - 建议在虚拟环境中安装依赖：
     ```bash
     python -m venv .venv
     source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
     pip install --upgrade pip
     ```

2. **安装依赖**
     ```bash
     pip install -r requirements.txt
     ```

3. **启动客户端**
   - 直接运行源码：
     ```bash
     python run.py
     ```
   - 若使用 PyInstaller 打包，可直接双击生成的 `.exe` 文件运行。

## 配置与运行时数据
- **API 地址**：默认值定义在 `config/settings.py` 中，可直接修改 `ClientSettings.api.base_url` 或在运行前加载自定义配置。
- **本地存储**：
  - 凭据、日志、监控缓存默认位于 `PATVS_ROOT`（Windows 为 `C:\PATVS`，其他平台为 `~/PATVS`）。可通过环境变量 `PATVS_ROOT` 指定新位置。
  - 窗口几何状态保存在 `~/.tts_client/window_state.json`，由 `ui/state.py` 负责读写。
  - OTA 下载目录默认为 `~/.tts_client/downloads/`，启动时自动创建。
- **日志**：每日生成 `YYYYMMDD/application.log`，未捕获异常写入 `crash.log`，逻辑见 `utils/logging.py`。

## 打包与分发
### 使用 `build.py`
1. 确认已安装 PyInstaller (`pip install pyinstaller`)。
2. 在项目根目录执行：
   ```bash
   python build.py
   ```
   > 说明：请在项目根目录执行命令，以便 PyInstaller 能够正确定位资源与模块。
3. 首次执行会自动生成 `patvs_client.spec`，随后在 `dist/` 下输出可执行包。

## 开发者提示
- `ui/main_window.py` 包含大量 UI 与业务绑定逻辑，建议通过 `monitoring/parser.py`、`monitoring/manager.py` 等解耦层进行扩展，避免直接依赖遗留脚本。
- 需要新增 API 时，在 `services/api_client.py` 中补充方法并扩展数据模型。提交结果时可参考 `submit_result` 的参数构建。
- 若需调整 OTA 渠道或日志目录，可直接修改 `config/settings.py` 或在外部封装动态配置加载逻辑。
