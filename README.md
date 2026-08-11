# MoviePilot-Plugins

MoviePilot v2 个人维护插件仓库，提供探索扩展和实用工具插件。

## 安装

在 MoviePilot 后台的 `插件` 页面添加第三方插件源：

```text
https://github.com/qsxazcv/MoviePilot-Plugins
```

添加后刷新插件市场，选择需要的插件安装即可。

## 插件一览

| 插件 | 插件 ID | 类型 | 版本 | 简介 |
| --- | --- | --- | --- | --- |
| 插件更新管理 | `PluginAutoUpdate` | 工具 | `2.0.8` | 监测已安装插件，推送更新提醒，可配置自动更新。 |
| 爱奇艺探索 | `IqiyiDiscover` | 探索 | `1.0.40` | 让 MoviePilot 探索支持爱奇艺视频的数据浏览。 |
| MediaWarp | `MediaWarp` | 云盘 | `1.0.8` | EmbyServer/Jellyfin 中间件，优化 STRM 播放、前端样式、客户端访问和脚本嵌入。 |
| 微云Cookie助手 | `weiyuncookie` | 工具 | `0.1.47` | 扫码登录 QQ/微信微云，一键提取 Cookie，支持有效性检测、隐藏展示和同步到 OpenList。 |

## 插件详情

### 插件更新管理

适合希望自动检查插件更新，并在环境满足条件时自动安装新版本的用户。

- 原作者：`thsrite`，原插件仓库：[thsrite/MoviePilot-Plugins](https://github.com/thsrite/MoviePilot-Plugins)。感谢原作者提供插件更新管理能力，本版本在原作基础上做兼容性和通知体验优化。
- 监测已安装插件，支持仅提醒或自动更新。
- 自动更新前会跳过正在运行的插件，避免任务执行中被覆盖。
- 当目标插件要求更高 MoviePilot 版本时，会标记为暂缓更新并说明最低版本要求。
- MoviePilot 升级到兼容版本后，下次自动更新任务会继续安装待更新版本。

### 爱奇艺探索

适合希望在 MoviePilot 探索页直接浏览爱奇艺内容库的用户。

- 让 MoviePilot 探索支持爱奇艺视频的数据浏览。
- 覆盖电视剧、电影、综艺、动漫、少儿、短剧、漫剧、纪录片和知识频道。
- 适配爱奇艺官方片库筛选与媒体转换逻辑。
- 修复部分频道返回非标准媒体类型导致的类型标签和详情展示问题。

### MediaWarp

适合需要在 EmbyServer/Jellyfin 前面增强 STRM 播放、样式和客户端访问控制的用户。

- 原作者：`DDSRem`，原插件仓库：[DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)。感谢原作者提供 MoviePilot 插件适配基础。
- 上游服务：[AkimioJR/MediaWarp](https://github.com/AkimioJR/MediaWarp)，当前适配 `v0.2.4`。
- 支持自动下载 MediaWarp 二进制并生成新版小写配置结构。
- 配置页保持 1.0.7 风格的简洁结构；缓存、HTTPStrm、AlistStrm 等高级参数如需调整，请直接修改 `config.yaml`。

### 微云Cookie助手

适合需要把腾讯微云 Cookie 接入 OpenList 或定期检查 Cookie 状态的用户。

- 支持 QQ/微信扫码登录微云并提取 Cookie。
- 支持 Cookie 有效性检测、复制和 OpenList 存储同步。
- 主页面与配置页默认隐藏 Cookie 明文，降低误泄露风险。
- 支持 Telegram / MoviePilot 通知辅助重新登录。
- 浏览器启动优先复用 MoviePilot 容器内 `/moviepilot` 已存在的 Playwright 或 CloakBrowser 内核。

## 安全提醒

- 请勿在日志、截图、Issue 或公共对话中公开 Cookie、Token、API Key、二维码链接或其他登录凭据。
- 微云 Cookie 助手会处理登录凭据，请只在可信环境中使用，并避免把运行日志直接公开。
- 如果反馈问题需要提供截图，请先遮挡账号、Cookie、Token、二维码和访问地址中的敏感参数。

## 更新记录

这里只保留每个插件最近的主要更新，完整历史以 `package.v2.json` 为准。

### `PluginAutoUpdate`

- `2.0.8`：修复配置页“立即运行”和 `/plugin_update` 的结果通知不一致：一次性立即运行会识别为人工触发，遇到已通知过的暂缓项时同样返回“插件更新状态未变化”短摘要，同时保留更新成功通知。
- `2.0.7`：优化手动触发 `/plugin_update` 的重复回执体验：移除即时开始通知，同一会话 5 分钟内相同暂缓结果只返回“插件更新状态未变化”短摘要，并在任务已运行时返回检查中提示。
- `2.0.6`：修复手动触发 `/plugin_update` 时遇到已通知过的版本不兼容暂缓项，只收到开始消息、没有任务结束回执的问题；保留暂缓通知去重，同时向当前命令频道返回本次仍暂缓的插件摘要。
- `2.0.5`：修复自动更新插件后动态注册插件 API 时透传 `allow_anonymous` 等 MoviePilot 扩展字段导致 `APIRouter.add_api_route()` 抛出 `unexpected keyword argument` 的异常；优先调用系统插件 API 注册流程，兼容旧环境时过滤非 FastAPI 原生字段。
- `2.0.4`：基于原作者 `thsrite` 版本继续维护，原插件仓库：[thsrite/MoviePilot-Plugins](https://github.com/thsrite/MoviePilot-Plugins)，感谢原作者贡献；优化 MoviePilot 版本不兼容场景，自动更新时暂缓安装并说明当前版本、目标版本和最低要求；支持官方 `>=`/`>` 版本约束、安全读取主程序版本、持久化通知去重，等待 MoviePilot 升级兼容后自动继续更新并发送恢复成功提醒；同时修复定时任务并发保护，避免同一轮自动更新重复执行和重复通知。

### `IqiyiDiscover`

- `1.0.40`：`to_media` 补 `source=iqiyi` 身份字段，修复爱奇艺探索卡片订阅弹窗因媒体库状态查询（`/mediaserver/notexists`）无法识别来源而默认「全集洗版」，恢复默认普通订阅。
- `1.0.39`：本地维护版（合并 v1.0.39~v1.0.44 全部修复）：新增 `iqiyi` / `iqiyidiscover` 识别模块并接入 MediaChain 分发（`get_module` 返回方法名 → 函数 dict）；爱奇艺 vlist 接口失效时按探索页缓存或推荐接口兜底找回剧名；识别改为 `search_meta.year` 传参修复 TypeError；探索页缓存按 7 天自动清理。
- `1.0.38`：优化安全图片域名配置：仅保留 `iqiyipic.com` 主域名，子域由非严格匹配自动覆盖，减少安全域名配置项。
- `1.0.37`：按功能区拆分爱奇艺探索源码，分离常量、筛选、请求、媒体转换和探索页 UI 生成逻辑，便于后续维护官方分类和接口适配。
- `1.0.36`：修复短剧、综艺、动漫、少儿、漫剧、纪录片和知识频道返回非标准媒体类型导致的类型标签和详情展示问题。

### `MediaWarp`

- `1.0.8`：适配 [AkimioJR/MediaWarp](https://github.com/AkimioJR/MediaWarp) `v0.2.4`，保留 1.0.7 风格简洁配置页，修复启动工作目录并包含运行依赖；高级参数改由 `config.yaml` 手动维护；感谢原作者 `DDSRem` 及 [DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)。

### `weiyuncookie`

- `0.1.47`：显式复用 MoviePilot 容器内已有浏览器内核；Playwright 启动时优先直接调用 `/moviepilot/.cache/ms-playwright` 或 `/moviepilot/.cloakbrowser` 中存在的可执行文件，并为 MP CloakBrowser 设置 `CLOAKBROWSER_BINARY_PATH`，避免路径存在但启动仍误报缺失。
- `0.1.46`：按功能区拆分微云 Cookie 助手源码，分离 Cookie 工具、二维码图片处理、OpenList 客户端和浏览器环境辅助逻辑，主插件类保留生命周期、API 与登录编排。
- `0.1.45`：优化状态轮询安全性，状态接口不再反复返回完整 Cookie，复制时才按需读取，并加锁避免重复启动扫码线程。
