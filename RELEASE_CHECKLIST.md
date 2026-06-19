# Release Checklist

这个文件记录本仓库已经踩过的坑。以后发版不能只靠记忆，必须按这里检查。

## 必查项

- Release ZIP 必须使用 POSIX 路径分隔符 `/`，例如 `programpreview/__init__.py`。
- 不要用 PowerShell `Compress-Archive` 直接打 MoviePilot Release 包；它会写入 `\`，Linux 容器解压后可能生成不了插件目录。
- 发布前下载 GitHub Release 附件复验，确认 ZIP 内没有反斜杠路径，并模拟解压后存在 `插件ID/__init__.py`。
- `release: true` 时必须创建 GitHub Release，标签和附件名都按 `插件ID_v版本号`，例如 `programpreview_v1.0.28.zip`。
- 如果没有发布 GitHub Release，就必须把清单里的 `release` 设为 `false`，走文件列表安装。
- 版本号要同步更新：`package.json`、`package.v2.json`、`plugins/*/__init__.py`、`plugins.v2/*/__init__.py`、`README.md`。
- 同一个插件的 `plugins/` 和 `plugins.v2/` 后端核心文件要保持一致，发版前对比哈希。
- 发布前清理 `__pycache__`、临时目录和未跟踪文件，确认 `git status --short` 干净。

## programpreview 已知问题

- 爱奇艺首页新片预告真实数据在 `newOnlinePCW` SSR，不要只依赖可见页面文本。
- `newOnlinePCW` 的 NUXT 压缩变量不一定在 HTML 结尾，解析时要截到 `</script>` 前。
- NUXT 字符串用 `json.loads` 解码，不要用错误的 `unicode_escape` 把中文解坏。
- 首页预告卡片不一定有 `sub.count`，只要 `publishText` 有明确日期和 `上线/上映` 就要抓取，预约数后续兜底补。
- 爱奇艺纪录片即将上线要包含 `list/documentary`、频道号 `3`、预约榜 `ranks1/3/-8`。
- 首页预告和纪录片榜单会重复，最终必须用爱奇艺标题归一化去重。
- 同名条目去重时，优先保留带预约数的版本；预约数状态一致时，优先保留带具体时间的版本。

## Release 包复验命令

用 Python 打包或检查，确保 ZIP 路径是 `/`：

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
from pathlib import Path
from zipfile import ZipFile
import shutil, tempfile

asset = Path(r"C:\Users\qsxaz\AppData\Local\Temp\programpreview_v1.0.28.zip")
with ZipFile(asset) as zf:
    names = zf.namelist()
    bad = [n for n in names if "\\" in n or n.startswith("/")]
    print("bad_paths", bad)
    out = Path(tempfile.mkdtemp(prefix="mp-release-check-"))
    try:
        zf.extractall(out)
        print((out / "programpreview" / "__init__.py").exists())
    finally:
        shutil.rmtree(out, ignore_errors=True)
'@ | python -
```

