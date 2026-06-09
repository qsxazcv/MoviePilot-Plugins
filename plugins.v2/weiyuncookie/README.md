# 微云Cookie助手

微云Cookie助手用于在 MoviePilot 中通过后端浏览器打开腾讯微云登录页，支持 QQ / 微信扫码登录，自动提取并保存 `weiyun.com` / `qq.com` 相关 Cookie。

## 主要功能

- 支持 QQ / 微信扫码登录微云。
- 自动提取完整 Cookie，并在插件页面展示。
- Cookie 显示框支持手动拖动调整高度。
- 支持定时检测 Cookie 有效性，失效后通过 MoviePilot 通知提醒。
- 支持将 Cookie 自动同步到 OpenList 腾讯微云存储。
- 支持 Telegram 命令触发登录、查询状态和立即检测。
- 优化二维码推送：提供可点击二维码链接，并支持本地图片文件推送，减少 Telegram 图片缓存或地址解析导致的异常。

## 命令

| 命令 | 说明 |
| --- | --- |
| `/weiyun_login` | 启动微云扫码登录并推送二维码 |
| `/weiyun_status` | 查询微云 Cookie 状态 |
| `/weiyun_check` | 立即检测微云 Cookie 有效性 |

## OpenList 同步

填写 OpenList 地址、管理员 Token 和目标存储 ID 后，可在扫码成功后自动将最新 Cookie 写入 OpenList 存储配置。也可在 Cookie 失效后重新登录成功时自动同步。

## 版本说明

### v0.1.21

- 修复插件清单 `release` 标记，改为文件列表安装，避免未创建 GitHub Release 时安装报 404。

### v0.1.20

- 新增 `/weiyun_status` 和 `/weiyun_check` 英文命令。
- `/weiyun_check` 检测通知合并为单条结果通知。
- `/weiyun_status` 隐藏 Cookie 有效字段，避免敏感信息暴露。
- 配置页和结果页完整 Cookie 显示框改为可拖动高度。
- 优化微信二维码截图等待逻辑，避免截图过早。
- 优化 Telegram 二维码推送，增加二维码链接和本地文件推送路径。
- 默认二维码图片地址从 `127.0.0.1` 调整为 `192.168.5.100`。
