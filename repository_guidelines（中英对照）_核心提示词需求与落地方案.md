# Repository Guidelines（中英对照）+ 核心提示词需求与落地方案

> 本文为你仓库规范的 **中英对照版**，并新增了“**核心提示词（Prompt）需求**”与落地方案，方便直接放入仓库并执行。建议保存路径：`docs/Repository-Guidelines.zh-en.md`。

---

## 1) Project Structure & Module Organization｜项目结构与模块组织

**EN**  
`run.py` boots the desktop client and `build.py` orchestrates PyInstaller. Feature code lives in `services/`, `models/`, and `monitoring/` for backend I/O, domain objects, and hardware orchestration. `ui/` and `widgets/` hold all PyQt5 windows, with shared helpers in `utils/`. Defaults and file locations are defined in `config/`, static assets in `resources/`, and runtime artifacts should stay within `data/` or `logs/`.

**ZH**  
`run.py` 用于启动桌面客户端；`build.py` 负责协调 PyInstaller 打包。功能代码位于 `services/`、`models/`、`monitoring/`，分别用于后端 I/O、领域对象、硬件/系统监控编排。界面在 `ui/`、`widgets/`（PyQt5 窗口与控件），共用辅助在 `utils/`。默认配置与路径在 `config/`，静态资源在 `resources/`，运行期产物应放在 `data/` 或 `logs/`。

---

## 2) Build, Test, and Development Commands｜构建、测试与开发命令

**EN**  
Set up a virtual environment before installing dependencies:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
Run the client locally with `python run.py`. Package a distributable with `python build.py` from the repository root; the script wires PyInstaller with the expected resource paths.

**ZH**  
安装依赖前先建立虚拟环境：
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
本地运行：`python run.py`。在仓库根目录执行 `python build.py` 进行打包，脚本会为 PyInstaller 配好资源路径。

---

## 3) Coding Style & Naming Conventions｜编码风格与命名

**EN**  
Follow PEP 8, 4-space indentation, type hints, and concise docstrings. Use `snake_case` for modules/packages/functions and `CapWords` for classes. Prefer explicit imports (e.g., `from services.api_client import ApiClient`) and keep `logger = logging.getLogger(__name__)` at module level. Run `python -m compileall .` or your editor’s formatter before submitting; Black-compatible formatting is encouraged but not enforced.

**ZH**  
遵循 PEP 8：4 空格缩进、类型标注、简明 docstring。模块/包/函数用 `snake_case`，类名用 `CapWords`。更倾向显式导入；模块级保留 `logger = logging.getLogger(__name__)`。提交前运行 `python -m compileall .` 或使用编辑器格式化；推荐 Black 风格但不强制。

---

## 4) Testing Guidelines｜测试规范

**EN**  
There is no committed automated suite yet. Add `pytest` tests under a `tests/` directory mirroring the source layout (`tests/services/test_api_client.py`, etc.). Name files `test_<module>.py`, keep fixtures focused on API boundaries, and mock HTTP calls with `requests-mock` instead of live services. Always perform a smoke run of `python run.py` to ensure the UI still boots, and capture screenshots when you touch visible widgets.

**ZH**  
暂未提交自动化用例。请在 `tests/` 下新增 `pytest` 测试，目录结构镜像源码（例如 `tests/services/test_api_client.py`）。文件命名 `test_<module>.py`。用 `requests-mock` 模拟 HTTP，避免直连外部服务。每次改动 UI 前后都要 `python run.py` 做冒烟，并附上截图。

---

## 5) Commit & Pull Request Guidelines｜提交与 PR 规范

**EN**  
Use sentence-case imperatives in commit messages (e.g., `Ensure monitoring message loops stop on manual abort`). Squash noisy intermediates before opening a PR. PRs should describe the problem, approach, and UI impacts; attach logs/screenshots for visual changes and link tracking issues. Confirm local packaging via `python build.py` for release-facing updates and note any manual steps reviewers must execute.

**ZH**  
提交信息使用“祈使句+句首大写”（如 `Ensure monitoring message loops stop on manual abort`），PR 前合并零碎提交。PR 需描述问题、方案、UI 影响；视觉改动附日志/截图并关联追踪 issue。涉及发版路径的改动，需在本地执行 `python build.py` 验证，并在 PR 中注明评审者要做的手动步骤。

---

## 6) Security & Configuration Tips｜安全与配置建议

**EN**  
Never commit real credentials or tokens—use encrypted helpers under `services/auth.py` and sanitize logs. When changing defaults, update `config/settings.py` and document new environment variables in the PR description. For OTA adjustments, ensure paths align with the `PATVS_ROOT` logic so installers remain portable across Windows and Linux.

**ZH**  
切勿提交真实凭据/令牌——使用 `services/auth.py` 的加密助手并先做日志脱敏。变更默认项时，更新 `config/settings.py` 并在 PR 说明新增环境变量。OTA 调整需遵循 `PATVS_ROOT` 路径规则，确保安装器在 Windows 与 Linux 上可移植。

---

## 7) Core Prompt Requirements（Product Rules）｜核心提示词（产品规则）

> 建议保存路径：`prompts/core_monitoring_prompt.md`，并在 `config/settings.py` 指定其路径，运行时由 `services/prompt_loader.py` 读取。

**中文（权威版本）**  
这是一款用来监控用例执行的 Windows 客户端工具：
1. 当用户执行用例时，系统应根据用例**关键字**自动匹配并启用相应的**监控选项**（如进程、服务、硬件、网络、日志等）。
2. 只有**所有监控动作均完成**后才能标记为**通过（Pass）**；但允许随时提前标记为**失败（Fail）**或**阻塞（Blocked）**。
3. 当用例录入并提交了最终结果后，系统必须**停止所有已启用的监控项**并释放资源（进程/线程/句柄/文件句柄/定时器等）。
4. 用例执行过程中可能发生**关机/重启**；必须保证客户端**下次启动时自动恢复**到上一次的**执行记录与监控状态**，并按需继续或清理：
   - 恢复上一次尚未提交结果的用例、监控开关、计时与已采集的证据（日志、截图、指标）。
   - 如上次状态无法安全恢复，应提示人工处理并提供“一键清理与重试”。

**English (authoritative translation)**  
This Windows client monitors test case execution:
1. When a test case runs, the system **auto-selects and enables monitoring options** based on the case **keywords** (processes, services, hardware, network, logs, etc.).
2. A test case can be marked **Pass only after all monitoring actions have completed**; users may mark **Fail** or **Blocked** at any time.
3. Once the final result is submitted, the client must **stop all active monitors** and release resources (processes/threads/handles/file handles/timers, etc.).
4. The run may include **shutdowns/reboots**. On the next client start, the app must **automatically restore** the **previous execution record and monitoring state**, then continue or clean up as appropriate:
   - Restore unsubmitted cases, monitor toggles, timers, and collected evidence (logs, screenshots, metrics).
   - If resuming safely is impossible, prompt for manual intervention and provide a “one-click cleanup & retry”.

