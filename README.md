# MoviePilot-Plugins

MoviePilot 个人维护插件仓库，所有插件均提供 **V2 / V3 双代版本**，覆盖探索扩展和实用工具。

- **V3（推荐）**：MoviePilot `>=3.0.0` 环境自动安装 `plugins.v3` 版本（`system_version >=3.0.0`），使用官方媒体身份合同。
- **V2**：MoviePilot V2 环境自动安装 `plugins.v2` 版本，代际相互独立、互不影响。

## 安装

在 MoviePilot 后台的 `插件` 页面添加第三方插件源：

```text
https://github.com/qsxazcv/MoviePilot-Plugins
```

添加后刷新插件市场，选择需要的插件安装即可。V2 / V3 宿主会自动匹配对应代际版本，无需手动区分。

## 插件一览

| 插件 | 插件 ID | 类型 | V2 | V3 | 简介 |
| --- | --- | --- | --- | --- | --- |
| 插件更新管理 | `PluginAutoUpdate` | 工具 | `2.0.8` | `3.1.0` | 监测已安装插件，推送更新提醒，可配置自动更新。 |
| 爱奇艺探索 | `IqiyiDiscover` | 探索 | `1.0.45` | `2.1.1` | 让 MoviePilot 探索支持爱奇艺视频的数据浏览。 |
| MediaWarp | `MediaWarp` | 云盘 | `1.0.8` | `2.1.0` | EmbyServer/Jellyfin 中间件，优化 STRM 播放、前端样式、客户端访问和脚本嵌入。 |
| 微云Cookie助手 | `weiyuncookie` | 工具 | `0.1.47` | `1.1.0` | 扫码登录 QQ/微信微云，一键提取 Cookie，支持有效性检测、隐藏展示和同步到 OpenList。 |
| ikuai-cli助手 | `IkuaiAssistant` | 工具 | `1.0.0` | `2.1.0` | iKuai 路由器命令行工具 — 在终端管理网络、用户、VPN、防火墙等。 |

## 插件详情

### 插件更新管理

适合希望自动检查插件更新，并在环境满足条件时自动安装新版本的用户。

- 原作者：`thsrite`，原插件仓库：[thsrite/MoviePilot-Plugins](https://github.com/thsrite/MoviePilot-Plugins)。感谢原作者提供插件更新管理能力，本版本在原作基础上做兼容性和通知体验优化。
- 监测已安装插件，支持仅提醒或自动更新。
- 自动更新前会跳过正在运行的插件，避免任务执行中被覆盖。
- 当目标插件要求更高 MoviePilot 版本时，会标记为暂缓更新并说明最低版本要求。
- MoviePilot 升级到兼容版本后，下次自动更新任务会继续安装待更新版本。
- V3 适配：`plugins.v3` + `package.v3.json`（`system_version >=3.0.0`），纯工具插件代码零改动代际迁移。

### 爱奇艺探索

适合希望在 MoviePilot 探索页直接浏览爱奇艺内容库的用户。

- 让 MoviePilot 探索支持爱奇艺视频的数据浏览。
- 覆盖电视剧、电影、综艺、动漫、少儿、短剧、漫剧、纪录片和知识频道。
- 适配爱奇艺官方片库筛选与媒体转换逻辑。
- 修复部分频道返回非标准媒体类型导致的类型标签和详情展示问题。
- V3 适配：`plugins.v3` + `package.v3.json`，识别身份走官方 `MediaSource.Iqiyi`（`media_source` / `media_id`），并支持订阅跨源转换（`MediaRecognizeConvert`）。

### MediaWarp

适合需要在 EmbyServer/Jellyfin 前面增强 STRM 播放、样式和客户端访问控制的用户。

- 原作者：`DDSRem`，原插件仓库：[DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)。感谢原作者提供 MoviePilot 插件适配基础。
- 上游服务：[AkimioJR/MediaWarp](https://github.com/AkimioJR/MediaWarp)，当前适配 `v0.2.4`。
- 支持自动下载 MediaWarp 二进制并生成新版小写配置结构。
- 配置页保持 1.0.7 风格的简洁结构；缓存、HTTPStrm、AlistStrm 等高级参数如需调整，请直接修改 `config.yaml`。
- V3 适配：`plugins.v3` + `package.v3.json`，纯工具插件代码零改动代际迁移。

### 微云Cookie助手

适合需要把腾讯微云 Cookie 接入 OpenList 或定期检查 Cookie 状态的用户。

- 支持 QQ/微信扫码登录微云并提取 Cookie。
- 支持 Cookie 有效性检测、复制和 OpenList 存储同步。
- 主页面与配置页默认隐藏 Cookie 明文，降低误泄露风险。
- 支持 Telegram / MoviePilot 通知辅助重新登录。
- 浏览器启动优先复用 MoviePilot 容器内 `/moviepilot` 已存在的 Playwright 或 CloakBrowser 内核。
- V3 适配：`plugins.v3` + `package.v3.json`，纯工具插件代码零改动代际迁移（Vue 联邦产物原样复用）。

### ikuai-cli助手

适合希望通过命令行方式管理爱快路由器网络、用户、VPN、防火墙等设备的用户。

- 封装 `ikuai-cli`（Go 二进制，随插件打包）管理 iKuai 路由器。
- 提供 8 个斜杠命令（`/ikuai_system`、`/ikuai_online`、`/ikuai_dns`、`/ikuai_logs` 等）和 2 个 AI 工具（`ikuai_cli` / `ikuai_skill`）。
- 默认按只读方式排查问题；修改路由、规则、用户和系统配置等写操作需在插件配置开启并二次确认。
- 自带 17 个领域技能文档（monitor / network / routing / security / vpn / users 等）。
- V3 适配：`plugins.v3` + `package.v3.json`，`get_api()` 端点带 `x-moviepilot-raw-response` 标记保持自定义响应格式。

## 安全提醒

- 请勿在日志、截图、Issue 或公共对话中公开 Cookie、Token、API Key、二维码链接或其他登录凭据。
- 微云 Cookie 助手会处理登录凭据，请只在可信环境中使用，并避免把运行日志直接公开。
- 如果反馈问题需要提供截图，请先遮挡账号、Cookie、Token、二维码和访问地址中的敏感参数。

## 更新记录

这里只保留每个插件最近的主要更新，完整历史以 `package.v2.json` / `package.v3.json` 为准。

### `PluginAutoUpdate`

- `3.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.plugins` / `app.sdk.events` / `app.sdk.logging` + `app.db.oper.systemconfig` / `app.adapters.external.market`），去除对旧版兼容层的依赖。
- `3.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：纯工具插件代码零改动——无 API 端点、无媒体身份引用、无 Vue 联邦，宿主依赖 `PluginManager` / `PluginHelper` / `Scheduler` / `SystemConfigOper` / `register_plugin_api` 签名 v3 兼容；版本按官方规则跃迁 `2.0.8 → 3.0.0`。
- `2.0.8`：修复配置页“立即运行”和 `/plugin_update` 的结果通知不一致：一次性立即运行会识别为人工触发，遇到已通知过的暂缓项时同样返回“插件更新状态未变化”短摘要，同时保留更新成功通知。

### `IqiyiDiscover`

- `2.1.1`：适配 V3 探索数据源 envelope 响应：`iqiyi_discover` 端点改为返回 `schemas.Response`（success/message/data 三段式），`get_api` 声明 `response_model`，修复探索页「服务器返回了无效响应」。
- `2.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.events` / `app.sdk.logging` / `app.sdk.media` / `app.sdk.network`），去除对旧版兼容层的依赖。
- `2.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：官方 v3 分支已收编爱奇艺来源（`MediaSource.Iqiyi='iqiyidiscover'`，issue #6288 已修复）；识别签名改为 `media_source` / `media_id`（`resolve_media_identity` 归一化 + 非爱奇艺来源拒绝，旧 `source` / `mediaid` 参数由 kwargs 兜底兼容）；MediaInfo 身份统一为 `MediaSource.Iqiyi` 枚举 + `albumId`；`DiscoverSource` 显式注册 `MediaSource.Iqiyi`；新增 `MediaRecognizeConvert` 事件将爱奇艺身份转换为 TMDB 主身份，订阅搜索可跨源搜站点资源；版本按官方规则跃迁 `1.0.45 → 2.0.0`。
- `1.0.45`：v3 兼容改造：识别方法 `recognize_media` / `async_recognize_media` 签名双参数兼容——新增 `media_source` / `media_id`（v3 分支 MediaChain 传参）并保留 `source` / `mediaid`（当前中间态传参），内部归一化后统一识别；配合官方 v3 分支收编 `iqiyi` / `iqiyidiscover`（`MediaSource.Iqiyi`），同一份代码跨中间态与 v3 分支可用。

### `MediaWarp`

- `2.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.services` / `app.sdk.logging`），去除对旧版兼容层的依赖。
- `2.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：纯工具插件代码零改动——无 API 端点、无媒体身份引用、无 Vue 联邦，宿主依赖 `MediaServerHelper` 签名 v3 兼容；版本按官方规则跃迁 `1.0.8 → 2.0.0`。
- `1.0.8`：适配 [AkimioJR/MediaWarp](https://github.com/AkimioJR/MediaWarp) `v0.2.4`，保留 1.0.7 风格简洁配置页，修复启动工作目录并包含运行依赖；高级参数改由 `config.yaml` 手动维护；感谢原作者 `DDSRem` 及 [DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)。

### `weiyuncookie`

- `1.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.events` / `app.sdk.logging`），去除对旧版兼容层的依赖。
- `1.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：纯工具插件代码零改动——API 端点本身已返回 `{success, ...}` 格式（业务字段平铺），Vue 前端 `unwrapResponse` 已按 v3 envelope 兼容（`'data' in data` 解包），`qrcode_image` 原生响应由 `_wrap_result` 自动透传；版本按官方规则跃迁 `0.1.47 → 1.0.0`。
- `0.1.47`：显式复用 MoviePilot 容器内已有浏览器内核；Playwright 启动时优先直接调用 `/moviepilot/.cache/ms-playwright` 或 `/moviepilot/.cloakbrowser` 中存在的可执行文件，并为 MP CloakBrowser 设置 `CLOAKBROWSER_BINARY_PATH`，避免路径存在但启动仍误报缺失。

### `IkuaiAssistant`

- `2.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.events` / `app.sdk.plugins` / `app.sdk.logging`），去除对旧版兼容层的依赖。
- `2.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：`get_api()` 全部端点加 `x-moviepilot-raw-response` 标记，绕过 v3 `ResponseAPIRoute` 统一 envelope 自动包装，保持 `{ok: ...}` 自定义响应格式；纯工具插件，不涉及媒体身份/识别/订阅链路；版本按官方规则跃迁 `1.0.0 → 2.0.0`。
- `1.0.0`：通过本地插件安装同步到 Localplugins 本地插件库；v3 环境兼容：`get_api()` 全部端点加 `x-moviepilot-raw-response` 标记，绕过 v3 `ResponseAPIRoute` 统一 envelope 自动包装，保持 `{ok: ...}` 自定义响应格式。
