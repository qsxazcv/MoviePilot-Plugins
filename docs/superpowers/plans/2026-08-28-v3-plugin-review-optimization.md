# V3 插件审查优化实现计划

> **面向 AI 代理的工作者：** 依据审查结论执行小范围生命周期、安全性与文档优化，并在每个阶段运行验证。

**目标：** 修复微云后台登录资源清理、MediaWarp 子进程与压缩包安全、插件更新器实例状态隔离，并补齐公共中文 docstring；保持现有 API 和功能行为不变。

**架构：** 使用实例级停止事件管理微云登录线程，保留现有后台线程模型；MediaWarp 继续使用内部调度器，但停止进程时采用优雅退出与强制终止兜底。PluginAutoUpdate 只将运行态可变字段移到实例初始化，不改变更新业务流程。

**技术栈：** Python 3.14、MoviePilot V3 SDK、APScheduler、threading、psutil、tarfile、pytest。

---

### 任务 1：微云 Cookie 助手生命周期清理

**文件：**
- 修改：`plugins.v3/weiyuncookie/__init__.py`
- 测试：`tests/v3/weiyuncookie/test_contract.py`

- [x] 增加实例级 `threading.Event` 和浏览器资源引用。
- [x] `init_plugin()` 先清理旧线程/资源，再重置停止事件。
- [x] 登录等待循环检查停止事件；finally 清理资源和线程状态。
- [x] `stop_service()` 设置停止事件、关闭浏览器资源、短暂等待线程，并清理引用。
- [x] 增加静态契约测试，确认停止事件与清理逻辑存在。

### 任务 2：MediaWarp 子进程与下载解压安全

**文件：**
- 修改：`plugins.v3/mediawarp/__init__.py`
- 测试：`tests/v3/mediawarp/test_contract.py`

- [x] 下载请求增加明确超时。
- [x] 解压前拒绝绝对路径和路径穿越成员，只提取预期文件。
- [x] 下载异常使用 error 日志，临时目录清理使用容错方式。
- [x] `stop_service()` 对 MediaWarp 进程执行 terminate、短等待、kill 兜底并清空引用。
- [x] 增加静态契约测试。

### 任务 3：PluginAutoUpdate 实例状态和公共文档

**文件：**
- 修改：`plugins.v3/pluginautoupdate/__init__.py`
- 测试：`tests/v3/pluginautoupdate/test_contract.py`

- [x] 在 `init_plugin()` 建立列表、字典、集合、锁和调度器实例状态。
- [x] 补齐公共类与公共方法的中文 docstring。
- [x] 停止调度器失败时记录 warning/error，不静默吞掉。
- [x] 增加实例状态初始化契约测试。

### 任务 4：微云公共文档与仓库质量验证

**文件：**
- 修改：`plugins.v3/weiyuncookie/__init__.py`
- 测试：`tests/v3/weiyuncookie/test_contract.py`

- [x] 补齐微云公共类、公共方法和事件处理器中文 docstring。
- [x] 保持联邦资源、API 路径和版本元数据不变。
- [x] 运行完整 pytest、compileall、仓库校验、依赖门禁和 git diff 检查。

### 验证命令

```bash
python3 -m compileall -q plugins.v3
python3 -m pytest tests -q
python3 scripts/validate_repo.py
python3 scripts/check_v3_dependency_install.py --static-only
python3 scripts/check_v3_dependency_install.py --python 3.14
```

预期：全部命令退出码为 0；现有测试与新增契约测试全部通过；仓库工作区只包含本次预期修改。
