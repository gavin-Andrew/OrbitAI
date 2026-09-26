import json
import unittest
from unittest.mock import MagicMock, patch

from orbitai.materials.ai_client import request_chat_completion


class AIClientOptionTests(unittest.TestCase):
    def test_extraction_options_do_not_change_legacy_defaults(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"choices":[{"message":{"content":"{}"}}]}'
        with patch('orbitai.materials.ai_client.urlopen', return_value=response) as call:
            client = {'base_url': 'https://api.deepseek.com', 'api_key': 'test-only'}
            request_chat_completion(client, [], max_tokens=1600, thinking=False)
            payload = json.loads(call.call_args.args[0].data)
            self.assertEqual(payload['thinking'], {'type': 'disabled'})
            self.assertEqual(payload['max_tokens'], 1600)
            request_chat_completion(client, [])
            self.assertNotIn('thinking', json.loads(call.call_args.args[0].data))
