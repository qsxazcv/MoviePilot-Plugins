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

### v0.1.27

- 优化 UI 排序与信息层级，减少不必要的卡片化展示。
- 配置页改为“常用设置 / 登录环境 / 自动检测与通知 / OpenList 同步 / 运行档案”的分区表单。
- 详情页移除冗余功能卡片，改为状态概览、二维码操作区、完整 Cookie 面板和近期结果列表。

### v0.1.26

- 按四大平台节目预告风格重设计配置页与详情页。
- 配置页改为控制台头部、状态卡片、功能卡片和分组设置卡片。
- 详情页统一为状态网格、实时状态卡片、二维码操作区和完整 Cookie 面板。
- 修复 Vue 联邦前端中文显示乱码问题。

### v0.1.25

- 修复 Vue 联邦 Page 组件括号不匹配导致的空白问题。

### v0.1.24

- 修复 Vue 联邦 Page 组件空白：补充 __api_status 返回 enabled/has_cookie/login_type_title/browser_mode_title/qrcode/check_cron 字段。

### v0.1.23

- 更换插件图标为仓库 `icons/weiyuncookie.png`。

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


## v0.1.23

- 升级为 Vue 联邦 UI：重做配置页与扫码登录工作台。
- 保留现有 QQ / 微信扫码、Cookie 提取、有效性检测和 OpenList 同步逻辑。
