# MoviePilot-Plugins

MoviePilot 个人维护插件仓库，所有插件均面向 **MoviePilot V3**，覆盖探索扩展和实用工具。

- **V3**：MoviePilot `>=3.0.0` 环境安装 `plugins.v3` 版本（`system_version >=3.0.0`），使用官方媒体身份合同。

## 安装

在 MoviePilot 后台的 `插件` 页面添加第三方插件源：

```text
https://github.com/qsxazcv/MoviePilot-Plugins
```

添加后刷新插件市场，选择需要的插件安装即可。当前仓库仅支持 MoviePilot V3 环境。

## 插件一览

| 插件 | 插件 ID | 类型 | V3 | 简介 |
| --- | --- | --- | --- | --- |
| 插件更新管理 | `PluginAutoUpdate` | 工具 | `3.1.4` | 监测已安装插件，推送更新提醒，可配置自动更新。 |
| 爱奇艺探索 | `IqiyiDiscover` | 探索 | `2.2.1` | 让 MoviePilot 探索支持爱奇艺视频的数据浏览。 |
| 微云Cookie助手 | `weiyuncookie` | 工具 | `1.2.8` | 扫码登录 QQ/微信微云，一键提取 Cookie，支持有效性检测、隐藏展示和同步到 OpenList。 |
| ikuai-cli助手 | `IkuaiAssistant` | 工具 | `2.1.5` | iKuai 路由器命令行工具 — 在终端管理网络、用户、VPN、防火墙等。 |
| MediaWarp | `MediaWarp` | 工具 | `2.0.6` | Emby/Jellyfin 中间件：优化 Strm 播放、自定义前端样式与客户端。基于 DDSRem 作者版本维护。 |

## 插件详情

### 插件更新管理

适合希望自动检查插件更新，并在环境满足条件时自动安装新版本的用户。

- 原作者：`thsrite`，原插件仓库：[thsrite/MoviePilot-Plugins](https://github.com/thsrite/MoviePilot-Plugins)。感谢原作者提供插件更新管理能力，本版本在原作基础上做兼容性和通知体验优化。
- 监测已安装插件，支持仅提醒或自动更新。
- 自动更新前会跳过正在运行的插件，避免任务执行中被覆盖。
- 只对**已绑定可信在线来源**的插件提示更新；未绑定（仅本地安装或无来源绑定）的插件不参与更新检查，避免跨库高版本绕过来源绑定。
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

### MediaWarp

适合把 Emby / Jellyfin 前面套一层中间件，优化 Strm 播放与前端样式的用户。

- **上游原作者**：`AkimioJR` — [AkimioJR/MediaWarp](https://github.com/AkimioJR/MediaWarp)（MediaWarp 二进制本体）。
- **插件原版作者**：`DDSRem` — [DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)（本插件所基于的 MoviePilot 插件实现）。
- **本插件基于 `DDSRem-Dev/MoviePilot-Plugins` 作者版本做 V3 升级维护，在此感谢原作者提供的插件实现，以及 `AkimioJR` 提供的 MediaWarp 二进制。** 本仓库仅做 MoviePilot V3 代际适配与二进制版本跟进维护，核心功能与设计均来自原作者。
- 下载并常驻运行 MediaWarp 二进制，作为 Emby / Jellyfin 反向代理中间件。
- 优化 Strm 文件播放；支持自定义前端样式（CRX 增强、演员页、Fanart、弹幕、外部播放器）、自定义允许访问客户端与访问日志、字幕 `SRT2ASS` 转换。
- 自动读取 MoviePilot 已配置的媒体服务器（Emby / Jellyfin）地址与认证信息。
- V3 适配：`plugins.v3` + `package.v3.json`（`system_version >=3.0.0`）；二进制升级至上游 `AkimioJR/MediaWarp` **v0.2.4**；配置字段迁移为 v0.2.4 小写下划线格式；SDK 导入迁移至 `app.sdk` 体系。
- `web.enable` 参照 [redwebsite/MoviePilot-Plugins](https://github.com/RedWebsite/MoviePilot-Plugins) 的做法，按各前端子开关（CRX / 头像过滤 / 同人图 / 外置播放器 / 弹幕 / 共同观影）自动计算，不再无条件写死。
- 「HTTPStrm 设置」标签页提供五个开关：「HTTPStrm 重定向」（`http_strm.enable`）、「HTTPStrm 代理」（`http_strm.proxy`，开启可串流/转码）、「查找最终地址」（`http_strm.final_url`）、「兼容模式」（`http_strm.compatibility_mode`，默认开启，外部网络播放需保持开启）、「HTTPStrm 缓存」（`cache.enable`，默认关闭）。
- 「基础设置」的「Emby STRM 媒体库路径」上方提供四个缓存有效期输入框（重定向 / Alist API / 图片 / 字幕），对应 `cache.http_strm_ttl`、`cache.alist_api_ttl`、`cache.image_ttl`、`cache.subtitle_ttl`；按 Go duration 格式校验（如 `30s`、`1m`、`2h`、`1h30m`），留空或格式不合法时回退默认值并写日志提示。

## 安全提醒

- 请勿在日志、截图、Issue 或公共对话中公开 Cookie、Token、API Key、二维码链接或其他登录凭据。
- 微云 Cookie 助手会处理登录凭据，请只在可信环境中使用，并避免把运行日志直接公开。
- 如果反馈问题需要提供截图，请先遮挡账号、Cookie、Token、二维码和访问地址中的敏感参数。

## 更新记录

这里只保留每个插件最近的主要更新，完整历史以 `package.v3.json` 为准。

### `PluginAutoUpdate`

- `3.1.4`：新增版本守卫，修复插件被启动备份恢复回旧版本后误报「更新成功」通知的问题。① 已安装版本改以插件身份表 `pluginidentity.declared_version` 为准，内存版本仅作兜底；② 目标版本不高于当前实际版本时直接跳过，不重装也不发送更新通知；③ 内存版本落后于磁盘版本时按磁盘版本校正运行时，日志如实记为版本校正而非升级；④ 版本号无法解析时保持原有行为，避免误拦真实升级。
- `3.1.3`：① 修复插件更新检查在调度线程中执行宿主异步查询失败的问题——新增 `__run_async_catalog_query()`，把协程投递回宿主主事件循环执行（禁止自建事件循环或新线程，否则数据库 worker 会判定循环不匹配并拒绝任务）；② 插件更新候选改读宿主插件页已收敛的目录，并新增 `__get_bound_plugin_ids()` 按可信来源绑定过滤，**只对已绑定在线来源的插件提示更新**，未绑定（仅本地或无绑定）的插件不再提示任何升级，避免跨库高版本绕过来源绑定。
- `3.1.2`：将运行态可变字段改为实例级状态，补充生命周期文档并记录停止调度器异常。
- `3.1.1`：适配 V3 插件开发文档 7.5：补充 `pyproject.toml` 依赖清单（pytz/apscheduler/fastapi）。
- `3.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.plugins` / `app.sdk.events` / `app.sdk.logging` + `app.db.oper.systemconfig` / `app.adapters.external.market`），去除对旧版兼容层的依赖。
- `3.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：纯工具插件代码零改动——无 API 端点、无媒体身份引用、无 Vue 联邦，宿主依赖 `PluginManager` / `PluginHelper` / `Scheduler` / `SystemConfigOper` / `register_plugin_api` 签名 v3 兼容；版本按官方规则跃迁 `2.0.8 → 3.0.0`。
- `2.0.8`：修复配置页“立即运行”和 `/plugin_update` 的结果通知不一致：一次性立即运行会识别为人工触发，遇到已通知过的暂缓项时同样返回“插件更新状态未变化”短摘要，同时保留更新成功通知。

### `IqiyiDiscover`

- `2.2.1`：修复 V3 正式媒体源枚举变化后的来源判断与身份回填，统一使用稳定的 `iqiyidiscover` 来源标识，避免探索识别和订阅转换失败。
- `2.2.0`：采用策略B缓存：短期缓存直读，中期缓存定期反查，接口失败保留旧缓存并增加短期负缓存。
- `2.1.6`：优化识别缓存类型注解，明确识别失败返回值，并限制探索分页参数范围。
- `2.1.5`：增强异常 JSON 响应防护，避免爱奇艺接口返回非对象数据时触发解析错误。
- `2.1.4`：将爱奇艺探索请求迁移至 MoviePilot 宿主 `RequestUtils`，统一代理与网络配置。
- `2.1.3`：修复爱奇艺识别回退路径未限定 TMDB 导致的递归调用。
- `2.1.1`：适配 V3 探索数据源 envelope 响应：`iqiyi_discover` 端点改为返回 `schemas.Response`（success/message/data 三段式），`get_api` 声明 `response_model`，修复探索页「服务器返回了无效响应」。
- `2.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.events` / `app.sdk.logging` / `app.sdk.media` / `app.sdk.network`），去除对旧版兼容层的依赖。
- `2.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：官方 v3 分支已收编爱奇艺来源（`MediaSource.Iqiyi='iqiyidiscover'`，issue #6288 已修复）；识别签名改为 `media_source` / `media_id`（`resolve_media_identity` 归一化 + 非爱奇艺来源拒绝，旧 `source` / `mediaid` 参数由 kwargs 兜底兼容）；MediaInfo 身份统一为 `MediaSource.Iqiyi` 枚举 + `albumId`；`DiscoverSource` 显式注册 `MediaSource.Iqiyi`；新增 `MediaRecognizeConvert` 事件将爱奇艺身份转换为 TMDB 主身份，订阅搜索可跨源搜站点资源；版本按官方规则跃迁 `1.0.45 → 2.0.0`。
- `1.0.45`：v3 兼容改造：识别方法 `recognize_media` / `async_recognize_media` 签名双参数兼容——新增 `media_source` / `media_id`（v3 分支 MediaChain 传参）并保留 `source` / `mediaid`（当前中间态传参），内部归一化后统一识别；配合官方 v3 分支收编 `iqiyi` / `iqiyidiscover`（`MediaSource.Iqiyi`），同一份代码跨中间态与 v3 分支可用。

### `weiyuncookie`
- `1.2.8`：详情页重排。①「近期结果」与「Cookie 管理」重复内容合并为统一的「运行记录」，同一信息只出现一次；② 二维码未生成时不再占 198px 空白，改为紧凑入口，并在左栏补充「启动扫码 → 扫码登录 → 自动保存」三步引导；③ 左右两栏强制并排等高，修复列被上游样式覆盖成 block 导致上下堆叠的问题；④ 状态值长文本单行省略，悬停可看全文，避免撑歪卡片；⑤ 启动扫码与复制 Cookie 提到顶部状态条，主次按钮分级；⑥ 页面底部补充随状态变化的操作提示。
- `1.2.7`：前端改为正规 Vite 工程——仓库补齐 Vue 源码（`src/components/Config.vue`、`Page.vue` 与样式文件）、`vite.config.js`、`package.json`，`dist` 由 `npm run build` 构建产出，不再手工修改编译产物。构建产物结构与暴露项（`./Config`、`./Page`）保持不变，CSS 不含 Vuetify 全局样式污染。界面行为与 1.2.6 一致。详见 `plugins.v3/weiyuncookie/FRONTEND.md`。
- `1.2.6`：设置页改为两段式布局。① 顶部新增常驻操作栏：启用插件、保存后立即运行一次、保存设置三个高频动作直接可见，不用再展开分区查找；②「常用设置」不再作为折叠分区，避免高频项藏在折叠区里；③ 状态卡改成人话：检测周期显示「每 6 小时」而非 cron 原文，Cookie 卡同时体现数量与是否可能失效；④ 保存后给出「正在保存 / 已提交」的即时反馈；⑤ 分区之间补分隔线，长页面更易定位。
- `1.2.5`：修正 1.2.4 遗漏的浏览器模式默认值——类默认值与状态接口兜底仍写作 `playwright`，导致缺少 `browser_mode` 配置时下拉框可能显示为空。现类默认值、兜底值与归一函数全部统一为 `cloakbrowser`。
- `1.2.4`：界面与登录环境优化。① 浏览器模式只保留 CloakBrowser，移除 Playwright 选项；后端默认值与历史配置同步归一为 `cloakbrowser`，旧配置无需手动调整；② 提高分区标题、描述与提示文字的对比度，未展开的分区更易辨认；③ 精简各分区说明文案，检测 Cron 的默认值补充「每 6 小时一次」的白话说明；④ 扫码超时提示与实际建议值对齐（建议 180 秒，范围 30-600）；⑤ 「通知 OpenList 同步结果」说明补充：登录时的同步结果已并入登录摘要，该开关仅用于手动同步。
- `1.2.3`：优化扫码登录通知，一次登录不再推送多条消息。①「微云 Cookie 提取成功」与「已同步到 OpenList」合并为一条摘要，标题统一为「微云 Cookie 已更新」，正文同时给出 Cookie 数量与 OpenList 同步状态，通知顺序不再错乱；② OpenList 同步失败时标题显式标注并在正文说明原因，失败仍单独告警，不会被合并吞掉；③ 去掉价值较低的「微云登录已启动」通知（同一次扫码必然紧跟二维码推送）；④ 修正结果文案中「扫码登录」重复出现的问题；⑤ 手动同步接口行为保持不变。
- `1.2.2`：修复扫码二维码被裁成半张导致无法扫码、进而 Cookie 提取超时失败的问题。① 二维码截图不再只取 iframe 中心 240×240，改为整框截图，二维码大于该范围时不再被截掉边缘；② 二维码元素筛选新增方形判断，logo、小图标、长条文字等非方形候选不再被当作二维码；③ 裁剪时按「方形程度」挑选二维码区块，并把外接框补成正方形、贴边时自适应平移，确保静区完整；④ 裁剪结果不是正方形则保留原截图，不再输出残码。
- `1.2.1`：修复一次性 Cookie 授权读取无法从 JSON 请求体取得令牌的问题。

- `1.2.0`：安全与稳定性优化：新增一次性 Cookie 授权读取、可中断扫码清理、检测状态分类与 OpenList 同步互斥保护。
- `1.1.4`：新增点击复制时的短时一次性 Cookie 授权读取流程，令牌仅内存保存、30 秒有效且只能使用一次。
- `1.1.3`：完善登录流程结束后的浏览器资源引用清理与异常记录。
- `1.1.2`：加强登录线程、浏览器和 Playwright 资源的停止清理与生命周期管理。
- `1.1.1`：适配 V3 插件开发文档 7.5：补充 `pyproject.toml` 依赖清单（`apscheduler` / `fastapi`）。
- `1.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.events` / `app.sdk.logging`），去除对旧版兼容层的依赖。
- `1.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：纯工具插件代码零改动——API 端点本身已返回 `{success, ...}` 格式（业务字段平铺），Vue 前端 `unwrapResponse` 已按 v3 envelope 兼容（`'data' in data` 解包），`qrcode_image` 原生响应由 `_wrap_result` 自动透传；版本按官方规则跃迁 `0.1.47 → 1.0.0`。
- `0.1.47`：显式复用 MoviePilot 容器内已有浏览器内核；Playwright 启动时优先直接调用 `/moviepilot/.cache/ms-playwright` 或 `/moviepilot/.cloakbrowser` 中存在的可执行文件，并为 MP CloakBrowser 设置 `CLOAKBROWSER_BINARY_PATH`，避免路径存在但启动仍误报缺失。

### `IkuaiAssistant`

- `2.1.5`：修复阶段 3 结构拆分后遗漏 `PreviewStore` 导入导致插件无法加载的问题；完成 CLI、格式化器、API 和 Agent 入口拆分。

- `2.1.3`：增加内置 CLI 实际版本探测、页面版本显示和可读的执行错误分类。
- `2.1.2`：修复内置 `ikuai-cli` 二进制损坏并恢复可执行权限，升级至官方 `v1.0.18`。
- `2.1.0`：适配 V3 SDK 导入规范：插件内部导入全面迁移至 `app.sdk` 体系（`app.sdk.events` / `app.sdk.plugins` / `app.sdk.logging`），去除对旧版兼容层的依赖。
- `2.0.0`：V3 代际迁移版（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`）：`get_api()` 全部端点加 `x-moviepilot-raw-response` 标记，绕过 v3 `ResponseAPIRoute` 统一 envelope 自动包装，保持 `{ok: ...}` 自定义响应格式；纯工具插件，不涉及媒体身份/识别/订阅链路；版本按官方规则跃迁 `1.0.0 → 2.0.0`。
- `1.0.0`：通过本地插件安装同步到 Localplugins 本地插件库；v3 环境兼容：`get_api()` 全部端点加 `x-moviepilot-raw-response` 标记，绕过 v3 `ResponseAPIRoute` 统一 envelope 自动包装，保持 `{ok: ...}` 自定义响应格式。

### `MediaWarp`

- `2.0.6`：「基础设置」新增四个缓存有效期输入框（重定向缓存 / Alist API 缓存 / 图片缓存 / 字幕缓存），位于「Emby STRM 媒体库路径」上方，可直接控制 `cache.http_strm_ttl` / `cache.alist_api_ttl` / `cache.image_ttl` / `cache.subtitle_ttl`（默认 `1m` / `10m` / `0m` / `2h`）；按 Go duration 格式校验，留空或格式不合法时回退默认值并写日志提示。
- `2.0.5`：修复「HTTPStrm 设置」标签页图标不显示的问题——原图标名 `mdi-redirect` 在 Material Design Icons 图标库中不存在，导致该标签页前方空白、与前两个标签页不对齐；改用 `mdi-swap-horizontal`。
- `2.0.4`：「HTTPStrm 设置」标签页新增「HTTPStrm 缓存」开关，可直接控制 `cache.enable`（HTTPStrm 重定向内存缓存总开关，默认关闭）；该字段原为 `1.0.7 → 2.0.0` 表单精简后遗留的无效键，本次转正为可用开关。
- `2.0.3`：新增「HTTPStrm 设置」标签页，把 `http_strm.enable`（重定向）、`http_strm.proxy`（代理/串流转码）、`http_strm.final_url`（查找最终地址）做成 UI 开关，并把「兼容模式」一起挪进该标签页，四个开关聚在一起控制 STRM 播放链路；`enable` / `final_url` 不再写死 `true`，`proxy` 不再只能手改配置文件。
- `2.0.2`：新增插件表单「兼容模式」开关（`Web页面配置` 标签页），可直接控制 `http_strm.compatibility_mode`，与 CRX 美化 / 头像过滤等开关用法一致；默认开启，避免外网播放退回 HEAD 跟链导致一直转圈。
- `2.0.1`：参照 `redwebsite/MoviePilot-Plugins` 的处理方式调整配置写入——`http_strm.compatibility_mode` 不再写入 `changes`（配置文件里的值由用户手动决定，插件每次启动不再覆盖；公开线上播放需要该项为 `true`，`config.yaml` 被重建后需手动确认）；`web.enable` 不再写死 `true`，改为按 CRX / 头像过滤 / 同人图 / 外置播放器 / 弹幕 / 共同观影六个子开关 `any` 计算。
- `2.0.0`：**基于 `DDSRem-Dev/MoviePilot-Plugins` 作者版本做 V3 升级维护，感谢原作者。** V3 代际迁移（`plugins.v3` + `package.v3.json`，`system_version >=3.0.0`，版本按官方规则跃迁 `1.0.7 → 2.0.0`）；二进制升级到上游 `AkimioJR/MediaWarp` v0.2.4；配置字段迁移为 v0.2.4 小写下划线格式（`port` / `server.*` / `web.*` / `http_strm.*` / `subtitle.*`）；SDK 导入迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.services` / `app.sdk.logging`）；补充 `pyproject.toml` 依赖清单（`ruamel.yaml` / `psutil`）。
- `1.0.7`：DDSRem 原版（二进制 v0.1.12）。
