"""材料更新命令行编排测试。"""

import unittest
from unittest.mock import patch

import main


class MainPipelineTests(unittest.TestCase):
    def test_full_pipeline_updates_materials_without_static_generation(self):
        fetch_result = {"ok": True, "message": "fetch"}
        ai_result = {"ok": True, "message": "ai"}

        with (
            patch.object(main, "run_fetch_only", return_value=fetch_result) as fetch,
            patch.object(main, "run_ai_only", return_value=ai_result) as ai,
        ):
            result = main.run_full_pipeline(batch_size=7)

        fetch.assert_called_once_with()
        ai.assert_called_once_with(batch_size=7)
        self.assertEqual(result["fetch"], fetch_result)
        self.assertEqual(result["ai"], ai_result)
        self.assertNotIn("regenerate", result)
        self.assertEqual(result["message"], "材料更新流程运行结束")
        self.assertFalse(hasattr(main, "run_regenerate_static"))
        self.assertFalse(hasattr(main, "process_new_rss"))
        self.assertFalse(hasattr(main, "process_unprocessed_ai"))


if __name__ == "__main__":
    unittest.main()
