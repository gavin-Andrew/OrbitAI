"""Demonstration confirmation can only affect an explicitly isolated copy."""

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from tests.events import test_event_service as fixtures
from orbitai.events.service import load_event
from orbitai.v42_preview import prepare_preview


class PreviewEnvironmentTests(unittest.TestCase):
    setUp = fixtures.EventServiceTests.setUp
    connection = fixtures.EventServiceTests.connection
    payload = fixtures.EventServiceTests.payload
    save = fixtures.EventServiceTests.save

    def test_demo_confirmation_does_not_change_source(self):
        self.save(self.payload())
        root = Path(self.tmp.name) / 'project'
        (root / 'var').mkdir(parents=True)
        source = root / 'var/orbitai.db'
        shutil.copyfile(self.db, source)
        before = source.read_bytes()
        target = prepare_preview(root)
        self.assertEqual(before, source.read_bytes())
        self.assertEqual(load_event('event_test', source)['status'], 'candidate')
        demo = load_event('event_test', target)
        self.assertEqual(demo['status'], 'confirmed')
        self.assertTrue(demo['title'].startswith('【演示】'))
        self.assertIn('隔离演示', demo['history'][0]['change_reason'])

    def test_preview_environment_rejects_real_database_path(self):
        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ, ORBITAI_PREVIEW_DATABASE=str(root / 'var/orbitai.db'), PYTHONUTF8='1')
        result = subprocess.run([sys.executable, '-c', 'import orbitai.core.config'],
                                cwd=root, env=env, capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('预览数据库必须是', result.stderr)
