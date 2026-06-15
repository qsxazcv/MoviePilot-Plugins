# MoviePilot-Plugins

这是一个面向 MoviePilot v2 的第三方插件仓库，用于存放和分发个人维护的 MoviePilot 插件。

当前仓库包含：

| 插件 ID | 插件名称 | 版本 | 简介 |
| --- | --- | --- | --- |
| `programpreview` | 四大平台节目预告 | `1.0.9` | 抓取爱奇艺、腾讯视频、芒果TV、优酷即将上线/预约节目，提供 Vue 联邦配置页与详情页，可查看运行状态、立即执行并展示最近一次预告。 |
| `weiyuncookie` | 微云Cookie助手 | `0.1.27` | 支持 QQ / 微信扫码登录微云，自动提取完整 Cookie，可检测有效性并同步到 OpenList；Vue 联邦 UI 支持快速弹出二维码并提供二维码占位图。 |

## 插件源地址

在 MoviePilot 的插件市场中添加第三方插件源时，可使用本仓库地址：

```text
https://github.com/qsxazcv/MoviePilot-Plugins
```

插件清单文件：

```text
package.v2.json
```

插件目录：

```text
plugins.v2/
```

## 仓库结构

```text
MoviePilot-Plugins/
├── README.md
├── package.v2.json
└── plugins.v2/
    ├── programpreview/
    │   ├── __init__.py
    │   ├── preview_core.py
    │   ├── requirements.txt
    │   └── dist/assets/        # Vue 联邦 UI 产物
    └── weiyuncookie/
        ├── __init__.py
        └── README.md
```

## 安装方式

1. 进入 MoviePilot 后台。
2. 打开 `插件` 页面。
3. 添加第三方插件源：`https://github.com/qsxazcv/MoviePilot-Plugins`。
4. 刷新插件市场。
5. 搜索并安装需要的插件。
6. 安装完成后进入插件详情页，根据说明填写配置并启用。

如果插件市场刷新后没有显示新插件，请检查：

- 插件源地址是否填写为仓库根地址。
- `package.v2.json` 是否能从 GitHub 正常访问。
- 插件目录是否位于 `plugins.v2/<插件ID>/`。
- MoviePilot 是否已经刷新插件市场缓存。

## 四大平台节目预告

插件 ID：`programpreview`

当前版本：`1.0.9`

核心能力：

- 抓取爱奇艺、腾讯视频、芒果TV、优酷即将上线/预约节目。
- 支持 Cron 周期执行、立即运行一次、通知与强制推送。
- 提供 Vue 联邦 UI：卡片化配置页、运行状态概览、立即运行/刷新按钮、最近一次节目预告详情。
- 预告结果保存到 `/config/plugins/programpreview/latest_preview.md`，避免插件运行目录更新后丢失。

功能说明：

- 抓取爱奇艺、腾讯视频、芒果TV、优酷的即将上线、即将上映或预约节目。
- 爱奇艺接入 `newonline` 与片库 `videolib/list` 即将上线抓取，合并 `prelw`、频道页与搜索页兜底结果。
- 爱奇艺预约数优先通过 `countAndState` 批量查询；搜索页兜底最多重试 3 次，仍失败则保留条目等待下次定时任务重试。
- 爱奇艺节目预告会按真实日期排序，兼容“明天”“本周四”“06月13日”等不同日期格式。
- 爱奇艺推送消息自动过滤无具体上线日期的“即将上线”条目，仅展示有明确日期的节目。
- 支持 Cron 定时执行，默认每天 `08:00`。
- 支持立即运行一次。
- 支持开启通知，将节目预告推送到 MoviePilot 已配置的通知渠道。
- 支持每次强制推送，避免因内容重复导致不通知。
- 插件详情页会展示最近一次节目预告结果。

配置项：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| 启用插件 | 关闭 | 开启后按 Cron 周期自动执行。 |
| 开启通知 | 开启 | 开启后通过 MoviePilot 通知渠道推送结果。 |
| 每次强制推送 | 开启 | 开启后每次运行都会推送结果。 |
| 立即运行一次 | 关闭 | 保存配置后立即触发一次抓取。 |
| 执行周期 Cron | `0 8 * * *` | 默认每天 08:00 执行。 |

Cron 示例：

```text
0 8 * * *      # 每天 08:00
30 21 * * *    # 每天 21:30
```

数据来源说明：

- 插件从公开页面、公开接口和同平台搜索页提取节目预告信息。
- 爱奇艺会从 `newonline`、片库 `videolib/list`、`prelw`、频道页和同平台搜索页提取即将上线节目；缺少预约数时先查 `countAndState`，再按片名搜索页兜底，不跨平台混用数据。
- 节目预约数、上线时间等字段依赖平台公开数据，平台未公开或页面结构变化时可能为空。
- 插件会尽量过滤排期标签、状态标签、推荐流噪声和非目标内容，但平台页面结构调整后仍可能需要更新规则。


## 微云Cookie助手

插件 ID：`weiyuncookie`

功能说明：

- 支持 QQ / 微信扫码登录腾讯微云。
- 通过 MoviePilot 后端浏览器打开微云登录页，扫码后自动提取 `weiyun.com` / `qq.com` 相关 Cookie。
- 插件配置页和详情页已升级为 Vue 联邦 UI，采用左侧导航、二级标签、状态卡片和 sticky toolbar。
- 详情页支持快速弹出二维码、扫码成功自动隐藏；二维码链接未就绪时会显示友好占位图。
- 支持 Cookie 有效性检测：可按 Cron 定时检测，也可手动立即检测。
- Cookie 失效时可通过 MoviePilot 通知提醒重新登录，并避免重复提醒。
- 支持将最新 Cookie 同步到 OpenList 腾讯微云存储。
- 支持扫码成功后自动同步 OpenList，也支持失效重登成功后自动同步。
- 支持 Telegram / MoviePilot 远程命令触发登录、查询状态和立即检测。
- 优化二维码推送：提供可点击二维码链接，并支持本地图片文件推送，减少 Telegram 图片缓存或地址解析导致的异常。

远程命令：

| 命令 | 说明 |
| --- | --- |
| `/weiyun_login` | 启动微云扫码登录并推送二维码。 |
| `/weiyun_status` | 查询微云 Cookie 状态，包括运行状态、Cookie 数量、上次登录、上次检测和 OpenList 同步状态。 |
| `/weiyun_check` | 立即检测微云 Cookie 有效性，并推送单条检测结果通知。 |

配置项：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| 启用插件 | 关闭 | 开启插件功能。 |
| 立即运行一次 | 关闭 | 保存配置后启动一次扫码登录。 |
| 登录方式 | `QQ 扫码登录` | 支持 QQ / 微信扫码登录。 |
| 浏览器内核 | `CloakBrowser` | 可选择 `Playwright Chromium` 或 `CloakBrowser`。 |
| 浏览器预热 | 开启 | 插件启用后后台预热浏览器内核，减少首次扫码冷启动等待。 |
| 无头浏览器 | 开启 | 后端无界面运行浏览器。 |
| 包含 QQ 域 Cookie | 开启 | 同步提取 `qq.com` 相关 Cookie。 |
| 扫码等待秒数 | `180` | 等待用户扫码登录的最长时间。 |
| 启用 MP 通知 | 开启 | 使用 MoviePilot 通知渠道发送登录、检测和同步结果。 |
| 二维码公网地址 | 空 | 微信或外部通知渠道无法访问本机地址时可填写公网域名。 |
| 自动检测 Cookie | 关闭 | 开启后按 Cron 周期检测 Cookie 有效性。 |
| 检测周期 Cron | `0 */6 * * *` | 默认每 6 小时检测一次。 |
| 启用 OpenList 同步 | 关闭 | 开启后可将 Cookie 写入 OpenList 存储。 |
| 每次扫码后同步 | 关闭 | 扫码登录成功后自动同步到 OpenList。 |
| 失效重登后同步 | 开启 | Cookie 失效后重新登录成功时自动同步。 |
| OpenList 地址 | `http://192.168.5.100:5244` | OpenList 服务地址。 |
| OpenList Token | 空 | OpenList 管理员 Token，请在插件配置页填写。 |
| 存储 ID | `2` | 需要写入 Cookie 的 OpenList 存储 ID。 |

使用建议：

- 首次使用先在插件配置页选择登录方式并执行一次扫码登录。
- 如果 Telegram 直接显示的二维码无法扫码，可点击通知中的二维码链接查看原图。
- 如果需要自动同步到 OpenList，请先确认 OpenList 地址、Token 和存储 ID 正确。
- 不要在日志、截图或 issue 中公开完整 Cookie、OpenList Token 或二维码链接中的 API Key。

## 依赖说明

`programpreview` 带有独立的 `requirements.txt`。安装插件后，如运行环境缺少依赖，请按 MoviePilot 插件依赖安装方式处理。

`weiyuncookie` 依赖 MoviePilot 运行环境中的后端浏览器能力。可选择 `Playwright Chromium` 或 `CloakBrowser`；如首次扫码较慢，建议开启浏览器预热。

## 维护与校验

提交插件变更前，建议至少执行以下检查：

```bash
python3 -m json.tool package.v2.json >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile plugins.v2/programpreview/__init__.py plugins.v2/programpreview/preview_core.py plugins.v2/weiyuncookie/__init__.py
git status --short --branch
```

提交前还应确认没有误提交以下内容：

- 真实账号登录态、Cookie、Token、密钥。
- 日志、缓存、临时文件、压缩包。
- `__pycache__`、`*.pyc` 等运行产物。

## 版本历史

### `weiyuncookie`

- `0.1.27`：修复二维码图片链接过早打开显示 `qrcode not ready`；扫码任务运行中会短暂等待二维码生成，未就绪时返回友好 SVG 占位图。

- `0.1.26`：浏览器模式命名调整为真实内核名：`Playwright Chromium` / `CloakBrowser`。

- `0.1.25`：新增浏览器预热开关，插件启用后后台预热 Chromium / CloakBrowser，减少首次扫码冷启动等待。

- `0.1.24`：优化启动扫码后的二维码弹出速度，缩短页面等待、二维码就绪检测和截图超时，并提升前端状态轮询频率。

- `0.1.23`：按 z2561221/MoviePilot-Plugins 设计语言重构为 Vue 联邦 UI，配置页采用左侧导航和二级标签，详情页采用 sticky toolbar、状态卡片、二维码与 Cookie 管理面板。

- `0.1.22`：更换插件图标为仓库 `icons/weiyuncookie.png`。

- `0.1.21`：修复插件清单 `release` 标记，改为文件列表安装，避免未创建 GitHub Release 时安装报 404。

- `0.1.20`：新增 `/weiyun_status`、`/weiyun_check` 英文命令；检测通知合并为单条结果，状态通知隐藏有效字段；完整 Cookie 显示框支持拖动；优化微信二维码截图等待、Telegram 二维码文件推送和二维码图片地址。

### `programpreview`

- `1.0.9`：补齐完整 Vue 联邦 UI，修复详情页未自动加载状态的问题；状态页可展示启用状态、通知、Cron、最近运行与最近预告，并将预告结果保存到持久数据目录。

- `1.0.8`：修复 UI 设计后联邦构建产物缺失导致插件打不开的问题，临时回退稳定渲染并验证配置页/详情页。

- `1.0.7`：新增插件状态与立即运行 API，为 Vue 联邦详情页读取运行状态和触发任务提供接口。

- `1.0.6`：优化插件 UI 结构，为后续 Vue 联邦页面改造准备配置模型与详情数据。

- `1.0.5`：爱奇艺推送消息过滤无具体上线日期的「即将上线」条目，仅展示有明确日期的节目。

- `1.0.4`：接入爱奇艺 `newonline` 与片库 `videolib/list` 即将上线抓取；预约数优先走 `countAndState`，搜索页兜底最多重试 3 次，并按真实日期排序。

- `1.0.3`：爱奇艺强化最终输出前搜索页补数，确保已识别条目缺预约数时继续按片名补齐，并在失败时保留重试空间。

- `1.0.2`：爱奇艺新增搜索页兜底补齐漏项与预约数，修复频道接口偶发遗漏《恶念》等预约节目。
- `1.0.1`：初始版本。

## 免责声明

本仓库插件仅用于个人学习和 MoviePilot 自动化管理。插件依赖第三方平台公开页面、公开接口或用户自行提供的登录态，相关平台页面结构、接口规则、活动规则变化都可能导致插件行为变化。

请遵守相关平台服务条款，妥善保管个人账号与登录态信息。
