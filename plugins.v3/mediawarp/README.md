# MediaWarp

EmbyServer / Jellyfin 中间件插件：优化播放 Strm 文件、自定义前端样式、自定义允许访问客户端、嵌入脚本。

## 来源与致谢

- **上游原作者**：`AkimioJR` — [AkimioJR/MediaWarp](https://github.com/AkimioJR/MediaWarp)（MediaWarp 二进制本体）
- **插件原版作者**：`DDSRem` — [DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)（本插件所基于的 MoviePilot 插件实现）

**本插件基于 `DDSRem-Dev/MoviePilot-Plugins` 作者版本做 V3 升级维护**，在此感谢原作者 `DDSRem` 提供的插件实现，以及 `AkimioJR` 提供的 MediaWarp 二进制。本仓库仅做 MoviePilot V3 代际适配与二进制版本跟进维护，核心功能与设计均来自原作者。

## 功能

- 下载并常驻运行 MediaWarp 二进制，作为 Emby / Jellyfin 的反向代理中间件。
- 优化 Strm 文件播放：直连 302 跳转、可配置是否允许串流/转码。
- 自定义前端样式：CRX 增强、演员页增强、Fanart 展示、弹幕、外部播放器、VideoTogether。
- 自定义允许访问客户端与访问日志。
- 字幕 `SRT2ASS` 转换。
- 自动读取 MoviePilot 已配置的媒体服务器（Emby / Jellyfin）地址与认证信息。

## V3 适配说明

- 目录：`plugins.v3/mediawarp/` + `package.v3.json`（`system_version >=3.0.0`）。
- 插件版本 `2.0.0` 对应官方 `1.0.7` 的 V3 代际迁移版（主版本跃迁），二进制升级至上游 `AkimioJR/MediaWarp` **v0.2.4**。
- 内部导入已迁移至 `app.sdk` 体系（`app.sdk.config` / `app.sdk.services` / `app.sdk.logging`）。
- 配置文件字段已从旧版大写驼峰迁移到 v0.2.4 的小写下划线格式（`port` / `server.*` / `web.*` / `http_strm.*` / `subtitle.*`）。

## 依赖

见 `pyproject.toml`：`ruamel.yaml`、`psutil`。

## 使用提示

- 插件会在数据目录下载 MediaWarp 二进制并常驻运行，请确保监听端口未被占用。
- 若 STRM 内容使用内网地址而需要外网播放，请确认 `http_strm` 的跟链/兼容模式配置符合你的场景。
- 修改插件配置后建议重载插件，使生成 `config.yaml` 与进程重启生效。
