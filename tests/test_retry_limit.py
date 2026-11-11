"""Kiểm tra giới hạn retry khi bị rate limit (bonus). Không gọi LLM thật."""
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from agent import run_agent, MAX_RATE_LIMIT_ATTEMPTS
from bonus.tools import BonusTools
from test_lab import FakeProvider, tool_call, final


class RetryLimitTests(unittest.TestCase):
    def test_stops_calling_tool_after_limit(self):
        calls = [tool_call(str(i), 'get_vercel_status', '{}') for i in range(MAX_RATE_LIMIT_ATTEMPTS + 1)]
        fake = FakeProvider(calls + [final('Không biết trạng thái Vercel')])
        tools = BonusTools(scenario='rate_limit_always')
        result = run_agent('Kiểm tra Vercel', fake, tools, max_steps=10)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], MAX_RATE_LIMIT_ATTEMPTS)
        last = json.loads(fake.histories[-1][-1]['content'])
        self.assertEqual(last['error'], 'RETRY_LIMIT_REACHED')

    def test_other_provider_not_blocked_by_vercel_limit(self):
        calls = [tool_call(str(i), 'get_vercel_status', '{}') for i in range(MAX_RATE_LIMIT_ATTEMPTS)]
        calls.append(tool_call('g', 'get_github_status', '{}'))
        fake = FakeProvider(calls + [final('ok')])
        result = run_agent('x', fake, BonusTools(scenario='rate_limit_always'), max_steps=10)
        self.assertEqual(json.loads(fake.histories[-1][-1]['content'])['provider'], 'github')
        self.assertEqual(result['status'], 'completed')

    def test_core_prompt_unchanged_for_main_tools(self):
        from status_tools import StatusTools
        fake = FakeProvider([final()])
        run_agent('x', fake, StatusTools())
        self.assertNotIn('Quy tắc bổ sung khi điều tra nhiều provider', fake.histories[0][0]['content'])


if __name__ == '__main__':
    unittest.main()
