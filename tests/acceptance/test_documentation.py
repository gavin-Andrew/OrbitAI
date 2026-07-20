"""文档分类与仓库内路径引用验收测试。"""

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT / "docs"

DOC_CATEGORIES = {
    "product",
    "specs",
    "guides",
    "decisions",
    "archive",
}

REPOSITORY_PATH_REFERENCE = re.compile(
    r"`(((?:docs|tests)/|(?:product|specs|guides|decisions|archive)/)"
    r"[^`\s]+?\.(?:md|py))`"
)

MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

RETIRED_PATH_PATTERNS = (
    re.compile(
        r"docs/(?:ORBITAI_ROADMAP|PROJECT_GOALS|V4_INFORMATION_STRATEGY|"
        r"V4_PRODUCT_PAGE_VISION|V4_1_CATALOG_SPEC|"
        r"V4_INDUSTRY_DOSSIER_SPEC|V4_SOURCE_REGISTRY|"
        r"V4_1_CATALOG_IMPORT_GUIDE|V4_1_CATALOG_PAGE_GUIDE|"
        r"V4_1_CATALOG_REVIEW_CHECKLIST|"
        r"PROJECT_STRUCTURE_REFACTOR_[A-Z0-9_]+)\.md"
    ),
    re.compile(
        r"tests/test_(?:catalog_import|catalog_page|migrations|core_paths|"
        r"module_boundaries|runtime_paths|web_structure|main_pipeline)\.py"
    ),
    re.compile(
        r"tests\.test_(?:catalog_import|catalog_page|migrations|core_paths|"
        r"module_boundaries|runtime_paths|web_structure|main_pipeline)"
    ),
)


class DocumentationTests(unittest.TestCase):
    def test_docs_root_is_classified_and_indexed(self):
        self.assertEqual(
            {path.name for path in DOCS_DIR.iterdir() if path.is_dir()},
            DOC_CATEGORIES,
        )
        self.assertEqual(
            {path.name for path in DOCS_DIR.iterdir() if path.is_file()},
            {"README.md"},
        )

        for category in DOC_CATEGORIES:
            self.assertTrue(any((DOCS_DIR / category).glob("*.md")), category)

    def test_repository_markdown_and_test_references_exist(self):
        markdown_files = [PROJECT_ROOT / "AGENTS.md", PROJECT_ROOT / "README.md"]
        markdown_files.extend(DOCS_DIR.rglob("*.md"))

        for markdown_file in markdown_files:
            content = markdown_file.read_text(encoding="utf-8")
            for relative_path, prefix in REPOSITORY_PATH_REFERENCE.findall(content):
                base_dir = (
                    PROJECT_ROOT
                    if prefix in {"docs/", "tests/"}
                    else DOCS_DIR
                )
                with self.subTest(
                    document=markdown_file.relative_to(PROJECT_ROOT),
                    reference=relative_path,
                ):
                    self.assertTrue(
                        (base_dir / relative_path).exists(),
                        relative_path,
                    )

    def test_relative_markdown_links_resolve(self):
        for markdown_file in DOCS_DIR.rglob("*.md"):
            content = markdown_file.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK.findall(content):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue

                path_text = target.split("#", 1)[0]
                if not path_text:
                    continue

                with self.subTest(
                    document=markdown_file.relative_to(PROJECT_ROOT),
                    target=target,
                ):
                    self.assertTrue((markdown_file.parent / path_text).exists())

    def test_retired_flat_paths_do_not_reappear(self):
        files = [PROJECT_ROOT / "AGENTS.md", PROJECT_ROOT / "README.md"]
        files.extend(DOCS_DIR.rglob("*.md"))
        files.extend(PROJECT_ROOT.rglob("*.py"))

        for path in files:
            if "__pycache__" in path.parts:
                continue
            content = path.read_text(encoding="utf-8")
            for pattern in RETIRED_PATH_PATTERNS:
                self.assertIsNone(pattern.search(content), str(path))


if __name__ == "__main__":
    unittest.main()
