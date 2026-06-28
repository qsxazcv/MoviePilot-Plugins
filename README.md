# MoviePilot-Plugins

> MoviePilot v2 第三方插件仓库
面向 MoviePilot v2 的第三方插件仓库，用于存放和分发个人维护的 MoviePilot 插件。

## 插件列表

| 插件 ID | 插件名称 | 版本 | 简介 |
| --- | --- | --- | --- |
| `programpreview` | 四大平台节目预告 | `1.0.37` | 抓取爱奇艺、腾讯视频、芒果TV、优酷即将上线/预约节目，过滤腾讯过时预告，统一排序并转换相对日期。 |
| `IqiyiDiscover` | 爱奇艺探索 | `1.0.36` | 接入爱奇艺官方片库筛选，覆盖电视剧、电影、综艺、动漫、少儿、短剧、漫剧、纪录片和知识频道。 |
| `P115StrmHelper` | 115网盘STRM助手 | `2.8.53` | 基于 DDSRem 原作维护，提供 115 网盘 STRM 生成、同步、整理和扫码登录能力，补充二维码 uid 修复并适配新版 p115client 云下载接口。 |
| `P115Disk` | 115网盘储存 | `0.2.18` | 基于 DDSRem 原作维护的 115 网盘存储模块，升级 p115client 至 `0.0.9.0.2` 并适配新版云下载接口。 |
| `weiyuncookie` | 微云Cookie助手 | `0.1.45` | 支持 QQ / 微信扫码登录微云，自动提取并保存 Cookie，可检测有效性并同步到 OpenList。 |

## 快速开始

在 MoviePilot 后台 `插件` 页面中添加第三方插件源：

```text
https://github.com/qsxazcv/MoviePilot-Plugins
```

## 致谢 DDSRem-Dev

`P115StrmHelper` 和 `P115Disk` 均源自 [DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins) 的优秀原作，感谢 DDSRem 长期维护 115 网盘生态插件、持续适配 MoviePilot 和 p115client 依赖变化。本仓库仅在原作基础上做个人维护与兼容性修复，保留原作者署名与致谢。

## 插件详情

### 115网盘STRM助手

**插件 ID**：`P115StrmHelper`

**原作者**：DDSRem，来源：[DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)

**功能**：提供 115 网盘 STRM 生成、全量/增量同步、网盘整理、离线下载监控、分享接收、目录上传和扫码登录等一体化能力。

- 修复 115 扫码二维码图片请求未携带 `uid` 导致“无效登录二维码”的问题。
- 适配 `p115client==0.0.9.0.2` 的云下载模块改名：`offline` -> `clouddownload`。
- 使用 `clouddownload_iter` 与 `clouddownload_task_add_urls` 新版接口。

### 115网盘储存

**插件 ID**：`P115Disk`

**原作者**：DDSRem，来源：[DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)

**功能**：提供 115 网盘存储模块，支持文件列表、上传、下载、删除、重命名等 MoviePilot 存储扩展能力。本仓库版本升级 `p115client==0.0.9.0.2`，将慢接口超时包装对齐 `clouddownload_task_add_urls`。

## 安全提醒

请勿在日志、截图、Issue 或公共对话中公开 Cookie、Token、API Key、二维码链接或其他登录凭据。

## 版本历史

### `P115StrmHelper`

- `2.8.53`：感谢 DDSRem 原作与长期维护；升级并适配 `p115client==0.0.9.0.2` 的云下载模块改名，使用 `clouddownload_iter` / `clouddownload_task_add_urls`；保留本仓库补充的 115 扫码二维码 `uid` 修复。

### `P115Disk`

- `0.2.18`：感谢 DDSRem 原作与长期维护；升级 `p115client==0.0.9.0.2`，并将慢接口超时包装对齐新版 `clouddownload_task_add_urls`。
