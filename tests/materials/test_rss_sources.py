"""材料来源启停配置测试。"""

import unittest

from orbitai.materials.rss import (
    load_disabled_source_names,
    load_sources,
)


class RssSourceConfigurationTests(unittest.TestCase):
    def test_pilot_github_atom_sources_are_disabled(self):
        enabled_names = {source["name"] for source in load_sources()}
        disabled_names = load_disabled_source_names()
        github_atom_names = {
            "Anthropic Claude Code Releases",
            "Meta Llama Models Releases",
            "DeepSeek R1 Repository Updates",
            "DeepSeek V3 Repository Updates",
            "SpaceXAI SDK Releases",
        }

        self.assertTrue(github_atom_names <= disabled_names)
        self.assertTrue(github_atom_names.isdisjoint(enabled_names))
        self.assertIn("OpenAI News", enabled_names)
        self.assertIn("Google DeepMind News", enabled_names)


if __name__ == "__main__":
    unittest.main()
