# TTS 测试执行客户端

全新一代的 Test Tracking System（TTS）桌面客户端，基于 **Python 3.10+** 与 **PyQt5** 构建，专注于计划调度、用例执行与硬件监控。项目已完成从旧版 PATVS UI 的迁移，保留了核心的硬件监控脚本，并在全新的模块化架构中整合。

## 技术栈
- Python 3.10 或更高版本
- PyQt5（桌面 UI）
- Requests（HTTP 通信）
- Cryptography（本地凭据加密）
- PyInstaller（桌面应用打包）

## 目录总览
```
TestTrackingSystemAPP/
├── main.py / __main__.py     # 兼容入口，委托到新的客户端
├── tts_client/               # 新架构的核心实现
│   ├── app.py                # Qt 启动器 & 应用装配
│   ├── core/                 # 领域逻辑层
│   ├── monitoring/           # Qt 适配层，连接旧版监控脚本
│   └── ui/                   # PyQt5 窗体、对话框
├── monitoring/               # 保留的硬件监控脚本与动作库
├── resources.py / resources/ # 静态资源定位
├── build.py                  # PyInstaller 打包工具
├── scripts/build_exe.py      # 可选的打包脚本
├── requirements.txt          # 运行所需的三方依赖
└── pyproject.toml            # 包元数据与入口定义
```

## 核心模块说明
| 模块 | 说明 |
| --- | --- |
| `main.py`、`TestTrackingSystemAPP/__main__.py` | 命令行入口，简单地调用 `tts_client.app.main`，保证旧调用方式依旧可用。 【F:main.py†L1-L8】 |
| `tts_client/app.py` | 应用装配器：初始化日志、Qt 应用、REST 客户端、认证存储、窗口状态、监控管理与 OTA 更新器，驱动登录流程并展示主窗口。 【F:tts_client/app.py†L1-L87】 |
| `tts_client/core/api_client.py` | 封装与 TTS 后端的 HTTP 交互，包含登录、部门/项目/计划查询、用例详情和结果提交等接口。 【F:tts_client/core/api_client.py†L1-L131】 |
| `tts_client/core/auth.py` | 记住密码功能：使用对称加密保存凭据，必要时读取/清除。 【F:tts_client/core/auth.py†L1-L63】 |
| `tts_client/core/security.py` | 基于机器/用户指纹生成密钥，负责密码的加解密。 【F:tts_client/core/security.py†L1-L43】 |
| `tts_client/core/settings.py` | 维护主窗口几何状态的持久化（读写 JSON）。 【F:tts_client/core/settings.py†L1-L33】 |
| `tts_client/core/storage.py` | 通用 JSON 读写工具，供凭据、窗口状态等模块复用。 【F:tts_client/core/storage.py†L1-L23】 |
| `tts_client/core/config.py` | 定义运行时配置：API 地址、OTA 配置、日志与状态文件位置（默认存储在 `PATVS_ROOT`）。支持通过 `PATVS_ROOT` 环境变量重定向。 【F:tts_client/core/config.py†L1-L39】【F:tts_client/core/paths.py†L1-L14】 |
| `tts_client/core/models.py` | 数据模型层，将后端 JSON 转换为 Python 对象，覆盖部门、项目、测试计划、执行结果、监控关键字等。 【F:tts_client/core/models.py†L1-L200】 |
| `tts_client/core/monitor_parser.py` | 解析监控关键字（如 `S3+5`），转为标准化动作列表，并判断是否需要上传附件。 【F:tts_client/core/monitor_parser.py†L1-L68】 |
| `tts_client/core/logging.py` | 全局日志配置：每天创建新目录，输出控制台 + 文件，并捕获未处理异常到 `crash.log`。 【F:tts_client/core/logging.py†L1-L53】 |
| `tts_client/core/ota.py` | OTA 更新检查器，请求远程 manifest，返回版本信息并在失败时抛出网络错误。 【F:tts_client/core/ota.py†L1-L35】 |
| `tts_client/monitoring/manager.py` | Qt 封装层：在后台线程中驱动遗留 `monitoring.patvs_monitor.Patvs_Fuction`，并将日志/完成事件转换为 Qt 信号。 【F:tts_client/monitoring/manager.py†L1-L68】 |
| `monitoring/` | 旧版 PATVS 监控脚本库，涵盖电源控制、锁屏、显示器、音量、摄像头等具体操作。新的客户端通过 `MonitoringManager` 与其交互。 |
| `tts_client/ui/login_dialog.py`、`tts_client/ui/main_window.py` | PyQt5 界面：登录对话框负责触发认证；主窗口承载计划筛选、用例树、执行结果提交、附件上传、监控日志展示等功能。 【F:tts_client/ui/main_window.py†L1-L135】 |
| `build.py` / `scripts/build_exe.py` | 提供两种 PyInstaller 打包方式：`build.py` 使用自动生成的 spec；`scripts/build_exe.py` 自定义名称并将静态资源打包。 【F:build.py†L1-L52】【F:scripts/build_exe.py†L1-L24】 |
| `resources.py` | 提供统一的资源目录定位，供 UI 加载图标、翻译等静态资产。 【F:resources.py†L1-L7】 |

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
   - 生产环境推荐：
     ```bash
     pip install -r requirements.txt
     ```
   - 或使用项目元数据（包含最小依赖集）：
     ```bash
     pip install .
     ```

3. **启动客户端**
   - 命令行入口：
     ```bash
     python -m TestTrackingSystemAPP
     ```
   - 或显式执行兼容入口：
     ```bash
     python -m TestTrackingSystemAPP.main
     ```
   - 安装为可执行脚本后，也可通过 `tts-client` 命令启动（`pyproject.toml` 中的 `project.scripts` 定义）。

## 配置与运行时数据
- **API 地址**：默认值在 `tts_client/core/config.py` 中，可修改 `ClientSettings.api.base_url` 或在运行前自定义配置模块。
- **本地存储**：
  - 凭据、日志、监控缓存默认位于 `PATVS_ROOT`（Windows 为 `C:\PATVS`，其他平台为 `~/PATVS`）。可通过环境变量 `PATVS_ROOT` 指定新位置。 【F:tts_client/core/config.py†L27-L34】【F:tts_client/core/paths.py†L5-L14】
  - 窗口几何状态保存在 `~/.tts_client/window_state.json`。
  - OTA 下载目录默认为 `~/.tts_client/downloads/`，启动时自动创建。 【F:tts_client/core/config.py†L22-L39】
- **日志**：每日生成 `YYYYMMDD/application.log`，未捕获异常写入 `crash.log`。 【F:tts_client/core/logging.py†L13-L51】

## 打包与分发
### 使用 `build.py`
1. 确认已安装 PyInstaller (`pip install pyinstaller`)。
2. 在项目根目录执行：
   ```bash
   python build.py
   ```
   > 说明：`build.py` 位于仓库根目录。如果希望通过 `python -m TestTrackingSystemAPP.build` 调用，需要在其上一级目录执行，否则 Python 无法定位 `TestTrackingSystemAPP` 包而报 `ModuleNotFoundError`。
3. 首次执行会自动生成 `patvs_client.spec`，随后在 `dist/` 下输出可执行包。 【F:build.py†L1-L52】

### 使用 `scripts/build_exe.py`
1. 适合需要自定义名称或捆绑 `resources/` 目录的场景。
2. 执行：
   ```bash
   python scripts/build_exe.py
   ```
3. 生成的可执行文件位于项目根目录下的 `dist/TTSClient/`。 【F:scripts/build_exe.py†L1-L24】

## 开发者提示
- `tts_client/ui/main_window.py` 包含大量 UI 与业务绑定逻辑，建议通过 `parse_keywords`、`MonitoringManager` 等解耦层进行扩展，避免直接依赖遗留脚本。 【F:tts_client/ui/main_window.py†L1-L135】【F:tts_client/core/monitor_parser.py†L1-L68】【F:tts_client/monitoring/manager.py†L1-L68】
- 需要新增 API 时，在 `tts_client/core/api_client.py` 中补充方法并扩展数据模型。提交结果时可参考 `submit_result` 的参数构建。 【F:tts_client/core/api_client.py†L69-L130】
- 若需调整 OTA 渠道或日志目录，可直接修改 `tts_client/core/config.py` 或在外部封装动态配置加载逻辑。 【F:tts_client/core/config.py†L1-L39】

