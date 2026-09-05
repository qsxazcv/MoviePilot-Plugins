# IkuaiAssistant 第三阶段结构拆分实现计划

> **目标：** 在不改变现有 API、Agent 工具和斜杠命令行为的前提下，逐步拆分过大的插件主文件。

**架构：** 先抽离纯 CLI 执行与安全策略，再抽离格式化逻辑，最后整理 Agent/API 入口。主类保留生命周期、配置和兼容门面，外部调用签名不变。

**技术栈：** Python 3.14、MoviePilot V3 插件、subprocess、pytest 可选，独立回归脚本作为容器内验证方式。

---

### 任务 1：抽离 CLI 执行器

**文件：**
- 创建：`plugins.v3/ikuaiassistant/cli_runner.py`
- 修改：`plugins.v3/ikuaiassistant/__init__.py`
- 测试：`tests/v3/ikuaiassistant/test_cli_runner.py`

- [ ] 保留 `run_cli_command()` 对外方法作为兼容门面；将参数解析、安全判定、环境变量构造、subprocess 执行和结果解析迁入 `CliRunner`。
- [ ] `CliRunner` 接收 executable、base_url、token、timeout、allow_write 和 PreviewStore，不保存 Token 到磁盘。
- [ ] 保持 `raw`、`dry_run`、`preview_id`、`confirm` 行为不变。
- [ ] 用 fake subprocess 验证只读、预览、确认执行、超时和非法命令。

### 任务 2：抽离格式化器

**文件：**
- 创建：`plugins.v3/ikuaiassistant/formatters.py`
- 修改：`plugins.v3/ikuaiassistant/__init__.py`
- 测试：`tests/v3/ikuaiassistant/test_formatters.py`

- [ ] 将纯文本格式化函数迁移为模块级函数或无状态类。
- [ ] 主类保留同名私有门面，保证现有事件处理器不改调用方式。
- [ ] 保持通知文本字段、Token 脱敏和错误输出格式不变。

### 任务 3：整理 Agent 与 API 入口

**文件：**
- 创建：`plugins.v3/ikuaiassistant/agent_tools.py`
- 创建：`plugins.v3/ikuaiassistant/api_handlers.py`
- 修改：`plugins.v3/ikuaiassistant/__init__.py`
- 测试：`tests/v3/ikuaiassistant/test_entrypoints.py`

- [ ] 抽离 Agent 输入模型和工具类，但保持工具名 `ikuai_cli`、`ikuai_skill` 不变。
- [ ] 抽离 API 处理函数时保留实例状态和方法签名。
- [ ] 检查 get_api/get_agent_tools/get_command 返回结构不变。

### 任务 4：完整验证

**文件：**
- 修改：`package.v3.json`
- 修改：`README.md`

- [ ] 对所有新增模块执行 `py_compile`。
- [ ] 执行独立安全回归，验证命令策略与预览缓存。
- [ ] 执行插件元数据 JSON 校验和 `git diff --check`。
- [ ] 仅在所有验证通过后更新版本和发布说明；不自动安装、重载或推送。
