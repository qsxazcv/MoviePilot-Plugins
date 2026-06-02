# MoviePilot-Plugins

这是一个面向 MoviePilot v2 的第三方插件仓库，用于存放和分发个人维护的 MoviePilot 插件。

当前仓库包含：

| 插件 ID | 插件名称 | 版本 | 简介 |
| --- | --- | --- | --- |
| `programpreview` | 四大平台节目预告 | `1.0.1` | 抓取爱奇艺、腾讯视频、芒果TV、优酷即将上线/预约节目，并按 Cron 周期推送通知。 |
| `unicomdailyclockin` | 联通签到立减金 | `1.1.9` | 每天自动执行中国联通立减金签到，支持多账号、立即运行、Cron 定时和通知结果。 |

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
    │   └── requirements.txt
    └── unicomdailyclockin/
        └── __init__.py
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

功能说明：

- 抓取爱奇艺、腾讯视频、芒果TV、优酷的即将上线、即将上映或预约节目。
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

- 插件从公开页面和公开接口提取节目预告信息。
- 节目预约数、上线时间等字段依赖平台公开数据，平台未公开或页面结构变化时可能为空。
- 插件会尽量过滤排期标签、状态标签、推荐流噪声和非目标内容，但平台页面结构调整后仍可能需要更新规则。

## 联通签到立减金

插件 ID：`unicomdailyclockin`

功能说明：

- 自动执行中国联通立减金活动页签到。
- 支持多账号配置。
- 支持标准 JSON，也支持未转义的宽松文本格式。
- 支持 Cron 定时执行，默认每天 `06:05`。
- 支持立即运行一次。
- 支持通知签到结果。
- 插件详情页会展示最近一次运行结果。

配置项：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| 启用插件 | 关闭 | 开启后按 Cron 周期自动签到。 |
| 开启通知 | 开启 | 开启后推送签到结果。 |
| 立即运行一次 | 关闭 | 保存配置后立即执行一次签到。 |
| 执行周期 Cron | `5 6 * * *` | 默认每天 06:05 执行。 |
| 多账号配置 | 空 | 支持 JSON 或宽松文本，优先级高于单账号配置。 |
| 单账号配置 | 空 | 兼容旧配置，包括 `authInfo`、`tokenid`、`bizChannelInfo`、`cookie`。 |

多账号宽松文本示例：

```text
账号:0001
authInfo:{...}
bizChannelInfo:{...}
tokenid:...
cookie:...

账号:0002
authInfo:{...}
bizChannelInfo:{...}
tokenid:...
cookie:...
```

多账号 JSON 示例：

```json
[
  {
    "name": "账号:0001",
    "authInfo": {},
    "bizChannelInfo": {},
    "tokenid": "",
    "cookie": ""
  },
  {
    "name": "账号:0002",
    "authInfo": {},
    "bizChannelInfo": {},
    "tokenid": "",
    "cookie": ""
  }
]
```

也可以不在插件配置中填写登录态，改用容器环境变量：

```text
UNICOM_CLOCKIN_AUTHINFO
UNICOM_CLOCKIN_TOKENID
UNICOM_CLOCKIN_BIZCHANNELINFO
UNICOM_CLOCKIN_COOKIE
```

安全提醒：

- `authInfo`、`tokenid`、`bizChannelInfo`、`cookie` 都属于登录态或敏感信息。
- 请只填写在 MoviePilot 插件配置或容器环境变量中。
- 不要把真实登录态提交到 GitHub、README、Issue、PR 或日志截图中。

## 依赖说明

`programpreview` 带有独立的 `requirements.txt`。安装插件后，如运行环境缺少依赖，请按 MoviePilot 插件依赖安装方式处理。

`unicomdailyclockin` 当前主要使用 Python 标准库和 MoviePilot 运行时能力，不额外声明第三方依赖。

## 维护与校验

提交插件变更前，建议至少执行以下检查：

```bash
python3 -m json.tool package.v2.json >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile plugins.v2/programpreview/__init__.py plugins.v2/programpreview/preview_core.py plugins.v2/unicomdailyclockin/__init__.py
git status --short --branch
```

提交前还应确认没有误提交以下内容：

- 真实账号登录态、Cookie、Token、密钥。
- 日志、缓存、临时文件、压缩包。
- `__pycache__`、`*.pyc` 等运行产物。

## 版本历史

### `programpreview`

- `1.0.1`：初始版本。

### `unicomdailyclockin`

- `1.1.9`：初始版本。

## 免责声明

本仓库插件仅用于个人学习和 MoviePilot 自动化管理。插件依赖第三方平台公开页面、公开接口或用户自行提供的登录态，相关平台页面结构、接口规则、活动规则变化都可能导致插件行为变化。

请遵守相关平台服务条款，妥善保管个人账号与登录态信息。
