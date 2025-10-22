# TTS 测试执行客户端

基于 PyQt5 的全新测试执行客户端，专注于计划调度、用例执行与硬件监控。项目现已完全迁移至重构后的架构，旧版 PATVS UI 及其依赖已被移除。

## 架构概览
- `main.py` / `TestTrackingSystemAPP.__main__`：向后兼容的入口，统一委托到 `tts_client.app.main`。
- `tts_client/app.py`：Qt 启动器，组装 API 客户端、认证存储、窗口状态、监控管理和 OTA 更新检查。
- `tts_client/core/`：领域逻辑层，包含 REST API 封装、数据模型、凭据加密、日志配置、监控关键字解析、窗口状态持久化和 OTA 更新实现。
- `tts_client/ui/`：PyQt5 界面组件（登录对话框与主窗口），与 `core` 层解耦，通过信号槽驱动业务逻辑。
- `tts_client/monitoring/`：对接遗留的硬件监控脚本，将日志与完成状态转换为 Qt 信号，供主窗口使用。

## 功能特性
- 记住密码的登录体验（本地凭据加密存储）。
- 部门/项目/计划三级筛选与用例树视图，支持目录、机型、优先级、结果过滤。
- 用例执行记录：备注、失败原因、缺陷编号、设备选择、附件上传与执行时间追踪。
- 监控关键字解析与执行，支持多种硬件操作并实时输出日志。
- OTA 更新检测：启动时自动检查 JSON Feed 并提示新版本。
- PyInstaller 打包脚本，生成可分发的桌面应用。

## 快速开始
```bash
pip install -r requirements.txt
python -m TestTrackingSystemAPP.main
```

## 打包
```bash
python -m TestTrackingSystemAPP.build
```
