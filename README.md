# PATVS 桌面客户端

该目录为全新的 PyQt5 客户端实现，聚焦测试计划执行与监控功能。

## 功能概述
- 登录与记住密码
- 部门/项目/计划三级筛选，支持目录、机型、优先级、结果过滤
- 用例执行记录（含图片上传、缺陷信息、起止时间加密）
- 关键字驱动的多种监控动作（时间、电源/USB 插拔、S3/S4/S5/Restart 等）
- OTA 更新检测（JSON Feed）
- 一键打包：运行 `python -m client_app.build`

## 运行
```bash
pip install -r requirements.txt
python -m client_app.main
```
