"""四大平台节目预告核心解析测试。"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
PREVIEW_CORE_FILE = REPO_ROOT / "plugins.v2" / "programpreview" / "preview_core.py"


def load_preview_core():
    """加载 preview_core，并避免测试时写入 /config。"""
    sys.modules.pop("programpreview_preview_core_under_test", None)
    spec = importlib.util.spec_from_file_location(
        "programpreview_preview_core_under_test",
        PREVIEW_CORE_FILE,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["programpreview_preview_core_under_test"] = module
    assert spec.loader is not None
    with patch("pathlib.Path.mkdir"), patch("pathlib.Path.touch"):
        spec.loader.exec_module(module)
    return module


class ProgramPreviewCoreTest(unittest.TestCase):
    """节目预告核心解析测试。"""

    def test_youku_text_fallback_pairs_date_with_following_title(self) -> None:
        """优酷文本兜底应把日期行和后续片名合并输出。"""
        module = load_preview_core()

        items = module.extract_youku(
            [
                "独播",
                "预约破",
                "130万",
                "综・06-24 上线",
                "食神·百厨大战",
            ]
        )

        self.assertEqual(items, ["6月24日上线｜食神·百厨大战"])

    def test_youku_text_fallback_splits_inline_date_and_title(self) -> None:
        """优酷文本兜底应拆分同一行里的日期和片名。"""
        module = load_preview_core()

        items = module.extract_youku(["独播 综・06-24 上线 食神·百厨大战"])

        self.assertEqual(items, ["6月24日上线｜食神·百厨大战"])

    def test_youku_initial_data_from_html_accepts_undefined_values(self) -> None:
        """优酷 SSR 数据中的 undefined 值应被兜底解析为 None。"""
        module = load_preview_core()

        html = """
        <script>
        window.__INITIAL_DATA__ = {
          "pageMap": {"title": "新片", "nodeKey": "NEW"},
          "module": {
            "title": "综艺-即将上线",
            "itemList": [{
              "title": "食神·百厨大战",
              "lbTexts": "06-24 12:30上线",
              "selectedTitleImg": undefined,
              "reserve": {"desc": "135.5万人已预约"}
            }]
          }
        }
        </script>
        """

        data = module._youku_initial_data_from_html(html)
        items = module.extract_youku_from_data(data)

        self.assertEqual(items, ["6月24日 12:30上线｜食神·百厨大战（135.5万人预约）"])

    def test_youku_channels_include_new_page(self) -> None:
        """优酷新片页应作为结构化数据源参与合并。"""
        module = load_preview_core()

        urls = [url for _name, url in module.YOUKU_CHANNELS]

        self.assertIn("https://www.youku.com/ku/new", urls)


if __name__ == "__main__":
    unittest.main()
